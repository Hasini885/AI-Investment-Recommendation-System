import yfinance as yf
from textblob import TextBlob

def get_market_trends():
    stocks = ["AAPL", "TSLA", "^GSPC"]
    data = {}

    for stock in stocks:
        ticker = yf.Ticker(stock)
        hist = ticker.history(period="5d")
        data[stock] = {
            "prices": hist["Close"].tolist(),
            "sentiment": get_sentiment(stock)
        }

    return data

def get_sentiment(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        # Fetch news headlines
        news = ticker.news
        if not news:
            return "Neutral"
        
        # Combine headlines and analyze
        total_sentiment = 0
        for item in news[:5]: # Analyze top 5 headlines
            analysis = TextBlob(item['title'])
            total_sentiment += analysis.sentiment.polarity
        
        avg_sentiment = total_sentiment / 5
        
        if avg_sentiment > 0.05:
            return "Positive"
        elif avg_sentiment < -0.05:
            return "Negative"
        else:
            return "Neutral"
    except Exception:
        return "Neutral"