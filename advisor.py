try:
    from pyswip import Prolog
    prolog = Prolog()
    prolog.consult("rules.pl")
    PROLOG_AVAILABLE = True
except Exception:
    PROLOG_AVAILABLE = False

def get_recommendation(age, income, goal):
    goal = goal.lower()
    
    if PROLOG_AVAILABLE:
        try:
            query = f"recommend({age}, {income}, {goal}, Risk, Title, Strategy)"
            result = list(prolog.query(query))
            if result:
                # Correct capitalization from Prolog variables
                risk_lvl = result[0]['Risk'].decode('utf-8') if isinstance(result[0]['Risk'], bytes) else result[0]['Risk']
                title_val = result[0]['Title'].decode('utf-8') if isinstance(result[0]['Title'], bytes) else result[0]['Title']
                strat_val = result[0]['Strategy'].decode('utf-8') if isinstance(result[0]['Strategy'], bytes) else result[0]['Strategy']
                
                return {
                    "risk": risk_lvl.capitalize(), 
                    "title": title_val,
                    "strategy": strat_val
                }
        except Exception:
            pass # Fallback to python if query fails


    # --- PURE PYTHON FALLBACK LOGIC ---
    # Matches the logic in rules.pl exactly
    if goal == "retirement" and age > 45 or income < 30000:
        risk = "low"
    elif goal == "education" and age > 40:
        risk = "low"
    elif goal == "wealth" and age <= 35 and income > 60000:
        risk = "high"
    elif age <= 25 and income > 40000:
        risk = "high"
    elif age <= 50 and age > 30 and income >= 30000:
        risk = "medium"
    else:
        risk = "medium"

    strategies = {
        "low": {"title": "Safety First Portfolio", "strategy": "60% Bonds, 20% FD, 10% Gold, 10% Large Cap Stocks"},
        "medium": {"title": "Balanced Growth Portfolio", "strategy": "40% Mutual Funds, 30% Blue-chip Stocks, 20% Index Funds, 10% Gold"},
        "high": {"title": "Aggressive Wealth Portfolio", "strategy": "50% Growth Stocks, 20% Crypto, 20% Mid-cap Funds, 10% International ETFs"}
    }
    res = strategies.get(risk, strategies["medium"])
    res["risk"] = risk.capitalize()
    return res





import yfinance as yf

def get_market_trends():
    stocks = ["AAPL", "TSLA", "^GSPC"]
    data = {}

    for stock in stocks:
        ticker = yf.Ticker(stock)
        hist = ticker.history(period="5d")
        data[stock] = hist["Close"].tolist()

    return data