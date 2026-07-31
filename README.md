# SmartWealth | Personalised Investment Advisor 📈

SmartWealth recommends a personalised investment strategy from a user's profile — age,
monthly investable income, stated risk appetite and financial goal — and tempers that
recommendation with live market news sentiment.

The reasoning is a **symbolic expert system**, not a black box: every recommendation
comes back with the exact chain of rules that produced it.

> ⚠️ **Educational project — not investment advice.** SmartWealth is coursework. It is not
> produced by a SEBI-registered adviser, does not consider your full financial position,
> tax situation or liabilities, and past performance does not predict future returns.
> Consult a qualified financial adviser before investing.

---

## How the recommendation is made

The engine models the two halves of risk separately, which is standard financial-planning
practice — and then takes the lower of the two.

1. **Risk capacity** — what you can objectively afford to risk, scored from age, income
   and goal.
2. **Hard caps** — constraints that override the score downwards: a capital-preservation
   goal, an investable surplus under ₹25,000/month, nearing or past retirement.
3. **Risk tolerance** — what you say you are comfortable with. The final level is
   `min(capacity, tolerance)`, so the system never recommends more risk than *either*
   your circumstances or your stated comfort allow.
4. **Market sentiment** — a one-way defensive lever. A bearish news signal shifts the
   allocation one step more conservative; a bullish one never makes it more aggressive.

Each step records a rule id, which the UI renders as a plain-English "why this
recommendation" trace.

### Two engines, one behaviour

Inference has two implementations:

| | |
|---|---|
| `rules.pl` | The SWI-Prolog expert system. Used whenever SWI-Prolog is installed. |
| `advisor._python_infer` | A line-for-line mirror, used otherwise (e.g. Streamlit Cloud). |

They must agree on every input. `test_advisor.py` drives the entire input grid through
both and fails if they diverge — the two engines previously used different income
thresholds, so the same user got different advice depending on the machine.

Portfolio composition lives in exactly one place, `advisor.STRATEGIES`. The donut chart,
the strategy sentence and the rupee breakdown all render from it, so they cannot disagree.

---

## Features

- **Expert system reasoning** — deterministic Prolog rules with an explainable trace.
- **News sentiment** — TextBlob polarity over recent headlines for each tracked instrument.
- **Live market pulse** — Nifty 50, Sensex, Reliance, S&P 500 and Apple via yfinance,
  each degrading independently if a fetch fails.
- **Session-scoped history** — SQLite persistence with CSV export.
- **Rule-based assistant** — answers investing fundamentals, and explains *your* specific
  recommendation from the database.

---

## Tech stack

Python · SWI-Prolog + PySwip · Streamlit · yfinance · TextBlob · SQLite · Plotly

---

## Getting started

**Prerequisites**

1. Python 3.10+
2. *(Recommended)* [SWI-Prolog](https://www.swi-prolog.org/download/stable) on your PATH.
   Without it the app still runs — it falls back to the equivalent Python engine and says
   so in the UI — but the expert system is the point of the project.

**Install and run**

```bash
pip install -r requirements.txt
streamlit run app.py
```

**Run the tests**

```bash
python -m unittest -v
```

The Prolog/Python equivalence tests skip automatically when SWI-Prolog is absent.

---

## Project structure

| File | Role |
|---|---|
| `app.py` | Streamlit UI and page routing. |
| `rules.pl` | The Prolog expert system — risk inference only. |
| `advisor.py` | Validation, the Python inference mirror, and the single strategy table. |
| `market.py` | yfinance price fetching and TextBlob news sentiment. |
| `database.py` | SQLite persistence, schema migration, session scoping. |
| `chatbot.py` | Rule-based financial assistant. |
| `test_advisor.py` | Invariants, regressions, and engine-equivalence tests. |

`investments.db` is created on first run and is git-ignored — it holds user data and
should not be committed.

---

## Known limitations

- Sentiment uses TextBlob, a general-purpose polarity model that does not understand
  financial jargon. FinBERT would be the domain-appropriate replacement.
- Rules are hand-authored and must be updated by a developer as thresholds change.
- SQLite and the browser-session identifier are prototype-grade; real multi-user use
  needs authentication and a server database.
- The system advises only — there is no brokerage integration or holdings tracking.
