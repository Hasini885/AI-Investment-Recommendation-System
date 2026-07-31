"""Rule-based financial assistant.

This is deliberately a keyword-matching expert assistant, not a language
model - the README and report now describe it that way rather than calling it
an AI chatbot.

Two real improvements over plain substring matching:

  * Matching is word-boundary based, so "risk" no longer fires on "brisk"
    and topics are matched on whole words.
  * The assistant can see the user's own latest recommendation, so
    "what should I invest in?" and "why?" get profile-specific answers.
    The report describes the chatbot reading from the database; this is what
    makes that true.
"""

import re

GENERAL_ANSWERS = [
    (
        ("diversify", "diversification", "allocation", "portfolio"),
        "Diversification is the golden rule. Spreading capital across asset classes - equity, "
        "debt, gold - means one bad performer cannot sink the whole portfolio. Rebalance once "
        "or twice a year to keep the mix close to target.",
    ),
    (
        ("risk", "risky", "volatility", "volatile"),
        "Risk has two halves. **Capacity** is what your age, income and goal say you can afford "
        "to lose; **tolerance** is what you can sleep through. A sound plan uses whichever is "
        "lower - which is exactly how this system decides your profile.",
    ),
    (
        ("crypto", "bitcoin", "cryptocurrency"),
        "Crypto is highly speculative. If you hold any at all, keep it to roughly 5-10% of a "
        "high-risk portfolio - which is why the aggressive allocation here caps it at 8% - and "
        "never invest money you need within five years.",
    ),
    (
        ("nifty", "sensex", "index", "etf", "etfs"),
        "Index funds and ETFs tracking the Nifty 50, Sensex or S&P 500 give you broad market "
        "exposure at very low cost, without needing to pick individual winners. For most "
        "long-term investors they are the sensible core holding.",
    ),
    (
        ("safe", "safety", "secure", "preserve", "preservation"),
        "For capital preservation, look at government and high-grade corporate bonds, fixed "
        "deposits and gold. Returns are lower, but your principal is far more protected - "
        "appropriate when your goal is near-term or your surplus is small.",
    ),
    (
        ("stock", "stocks", "equity", "equities", "shares"),
        "Equities are ownership in businesses. Over long horizons they have historically beaten "
        "other asset classes, but they can fall sharply in the short term - which is why the "
        "equity share of your portfolio should track your investment horizon.",
    ),
    (
        ("sip", "mutual", "fund", "funds"),
        "A systematic investment plan into a diversified mutual fund is the simplest way to "
        "invest regularly. Fixed monthly contributions also average out your entry price "
        "instead of betting on one moment in the market.",
    ),
    (
        ("emergency", "fund", "savings"),
        "Before investing at all, hold three to six months of expenses in an easily accessible "
        "account. That emergency buffer is what stops you selling investments at a loss when "
        "something unexpected happens.",
    ),
    (
        ("tax", "taxes", "80c", "elss"),
        "Tax treatment varies by instrument and holding period. ELSS funds and PPF carry "
        "Section 80C benefits in India, and long-term capital gains are usually taxed more "
        "favourably than short-term. Confirm current rules with a qualified tax adviser.",
    ),
    (
        ("invest", "investing", "investment", "start", "begin"),
        "Start with the order of operations: clear high-interest debt, build an emergency fund, "
        "then invest the surplus according to your risk profile. Generate a recommendation on "
        "the Advisor page and I can talk you through your specific allocation.",
    ),
]

FALLBACK = (
    "I can help with diversification, risk, equities, mutual funds, index funds, crypto, "
    "emergency funds and capital safety. You can also ask **\"what is my profile?\"** or "
    "**\"why did I get this?\"** once you have generated a recommendation."
)

_PROFILE_TRIGGERS = ("my profile", "my risk", "my portfolio", "my recommendation",
                     "what should i invest", "what do i", "my allocation", "my strategy")
_WHY_TRIGGERS = ("why", "explain", "reason", "how did you", "justify")


def _mentions(text, keywords):
    return any(re.search(rf"\b{re.escape(k)}\b", text) for k in keywords)


def _contains_any(text, phrases):
    return any(p in text for p in phrases)


def _describe_profile(context):
    return (
        f"Your profile is **{context['risk_label']} risk**, and the matching strategy is "
        f"**{context['title']}**:\n\n{context['strategy']}.\n\n"
        "Ask me *why* if you want the reasoning behind it."
    )


def _explain_profile(context):
    reasons = context.get("reasons") or []
    if not reasons:
        return (
            f"You were placed in the **{context['risk_label']} risk** band, but no detailed "
            "reasoning was recorded for it. Generate a fresh recommendation to see the full trace."
        )
    bullets = "\n".join(f"- {r}" for r in reasons)
    return f"Here is exactly why you were assessed as **{context['risk_label']} risk**:\n\n{bullets}"


def get_chatbot_response(user_input, context=None):
    """Answer a user question.

    ``context`` is the user's latest recommendation (as returned by
    ``advisor.get_recommendation`` or reconstructed from the database).  When
    present, profile-specific questions are answered from it.
    """
    text = str(user_input).lower().strip()
    if not text:
        return FALLBACK

    if context:
        if _contains_any(text, _PROFILE_TRIGGERS):
            return _describe_profile(context)
        if _contains_any(text, _WHY_TRIGGERS) and _mentions(
            text, ("risk", "profile", "portfolio", "strategy", "allocation", "this", "that")
        ):
            return _explain_profile(context)
    elif _contains_any(text, _PROFILE_TRIGGERS):
        return (
            "I do not have a recommendation for you yet. Head to the **Advisor** page, set your "
            "profile in the sidebar and generate one - then I can explain it in detail."
        )

    for keywords, answer in GENERAL_ANSWERS:
        if _mentions(text, keywords):
            return answer

    return FALLBACK
