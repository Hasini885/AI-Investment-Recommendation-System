"""Live market data and news-sentiment analysis.

Two things this module is careful about, because both were previously silent
failure modes:

  * yfinance changed its ``Ticker.news`` payload - headlines moved from
    ``item["title"]`` to ``item["content"]["title"]``.  Both shapes are
    handled, and if neither is present we say so instead of quietly
    reporting "Neutral" forever.
  * A failed price fetch used to raise straight through into the UI.  Each
    instrument now degrades on its own without taking the page down.
"""

import logging

import yfinance as yf
from textblob import TextBlob

log = logging.getLogger(__name__)

# The abstract targets Indian retail investors, so the watchlist leads with
# Indian benchmarks and keeps two global reference points.
INSTRUMENTS = {
    "^NSEI": "Nifty 50",
    "^BSESN": "BSE Sensex",
    "RELIANCE.NS": "Reliance Industries",
    "^GSPC": "S&P 500",
    "AAPL": "Apple",
}

# Polarity above/below which we call a headline set bullish/bearish.
SENTIMENT_THRESHOLD = 0.05

# How many headlines to score per instrument.
HEADLINE_LIMIT = 5


def _headline(item):
    """Pull the title out of a yfinance news item across payload versions."""
    if not isinstance(item, dict):
        return None
    title = item.get("title")
    if title:
        return title
    content = item.get("content")
    if isinstance(content, dict):
        return content.get("title")
    return None


def get_sentiment(ticker_symbol, ticker=None):
    """Return ``(label, detail)`` for an instrument's recent news.

    ``label`` is one of Positive / Negative / Neutral / Unavailable.
    ``detail`` explains how the label was reached, so a missing news feed is
    visible in the UI rather than masquerading as genuine neutrality.
    """
    try:
        ticker = ticker or yf.Ticker(ticker_symbol)
        news = ticker.news or []
    except Exception as exc:
        log.warning("News fetch failed for %s: %s", ticker_symbol, exc)
        return "Unavailable", "News feed could not be reached."

    headlines = [h for h in (_headline(i) for i in news[:HEADLINE_LIMIT]) if h]
    if not headlines:
        if news:
            log.warning(
                "No usable headline field in %s news payload (keys: %s)",
                ticker_symbol,
                sorted(news[0].keys()) if isinstance(news[0], dict) else type(news[0]),
            )
            return "Unavailable", "News feed returned an unrecognised format."
        return "Unavailable", "No recent headlines published."

    # Average over the headlines we actually scored, not a hardcoded count -
    # dividing by a fixed 5 dragged every result towards neutral.
    polarity = sum(TextBlob(h).sentiment.polarity for h in headlines) / len(headlines)
    detail = f"Average polarity {polarity:+.3f} across {len(headlines)} headline(s)."

    if polarity > SENTIMENT_THRESHOLD:
        return "Positive", detail
    if polarity < -SENTIMENT_THRESHOLD:
        return "Negative", detail
    return "Neutral", detail


def get_market_trends(period="5d"):
    """Fetch recent closes and news sentiment for every tracked instrument.

    Each entry is ``{name, dates, prices, change_pct, sentiment, detail,
    error}``.  A failure on one instrument never breaks the others.
    """
    trends = {}

    for symbol, name in INSTRUMENTS.items():
        entry = {
            "name": name,
            "dates": [],
            "prices": [],
            "change_pct": None,
            "sentiment": "Unavailable",
            "detail": "",
            "error": None,
        }

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)

            if hist is None or hist.empty or "Close" not in hist:
                entry["error"] = "No price data returned."
            else:
                closes = hist["Close"].dropna()
                entry["dates"] = [d.strftime("%d %b") for d in closes.index]
                entry["prices"] = [float(p) for p in closes.tolist()]
                if len(entry["prices"]) >= 2 and entry["prices"][0]:
                    first, last = entry["prices"][0], entry["prices"][-1]
                    entry["change_pct"] = (last - first) / first * 100

            entry["sentiment"], entry["detail"] = get_sentiment(symbol, ticker)

        except Exception as exc:
            log.warning("Market fetch failed for %s: %s", symbol, exc)
            entry["error"] = "Live data unavailable right now."

        trends[symbol] = entry

    return trends


def aggregate_sentiment(trends):
    """Collapse per-instrument sentiment into one market-wide signal.

    Returns ``(signal, summary)`` where signal is ``positive`` / ``neutral`` /
    ``negative`` - the value ``advisor.get_recommendation`` consumes.  A tie,
    or no usable readings at all, deliberately yields ``neutral`` so the
    advisor is never nudged on weak evidence.
    """
    positive = sum(1 for e in trends.values() if e.get("sentiment") == "Positive")
    negative = sum(1 for e in trends.values() if e.get("sentiment") == "Negative")
    scored = sum(
        1 for e in trends.values()
        if e.get("sentiment") in ("Positive", "Negative", "Neutral")
    )

    if not scored:
        return "neutral", "No usable news sentiment; treating the market as neutral."

    summary = f"{positive} bullish / {negative} bearish out of {scored} instruments scored."
    if positive > negative:
        return "positive", summary
    if negative > positive:
        return "negative", summary
    return "neutral", summary
