def get_chatbot_response(user_input):
    user_input = user_input.lower()

    if "investment" in user_input or "invest" in user_input:
        return "Diversification is the golden rule of investing. By spreading your capital across different asset classes like stocks, bonds, and gold, you reduce the impact of a single asset's poor performance."

    elif "risk" in user_input:
        return "Risk appetite is personal. Generally, younger investors can afford higher risk for higher potential returns, while those nearing retirement should pivot towards capital preservation."

    elif "stock" in user_input:
        return "Equities offer ownership in companies. Over the long term, they have historically outperformed most other asset classes, but they come with significant short-term volatility."

    elif "safe" in user_input or "secure" in user_input:
        return "For maximum safety, consider Government Bonds, Fixed Deposits, or Gold. While returns may be lower, your principal amount is much more secure."

    elif "crypto" in user_input:
        return "Cryptocurrencies are highly speculative and volatile. They should only form a small part (e.g., 5-10%) of a high-risk portfolio."

    elif "nifty" in user_input or "index" in user_input:
        return "Index funds or ETFs tracking the Nifty 50 or S&P 500 are excellent low-cost ways to gain market exposure without picking individual stocks."

    else:
        return "I'm here to help with your financial journey! You can ask me about stock market basics, risk management, or specific asset classes. What's on your mind?"