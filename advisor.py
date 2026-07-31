"""Advisor bridge: validates the user profile, runs risk inference, and maps
the inferred risk level onto a concrete portfolio.

Risk *inference* has two interchangeable implementations:

  * ``rules.pl``      - the SWI-Prolog expert system (preferred).
  * ``_python_infer`` - a line-for-line mirror, used when SWI-Prolog is not
                        installed (e.g. Streamlit Cloud).

Both must return identical results for every input; ``test_advisor.py``
asserts that across the full input grid.

Portfolio *composition* lives here only, in ``STRATEGIES``.  The UI derives
both the donut chart and the strategy text from that one table, so the chart
and the wording can never disagree.
"""

import logging
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain vocabulary
# ---------------------------------------------------------------------------
GOALS = ("wealth", "retirement", "education", "safety")
TOLERANCES = ("low", "medium", "high")
SENTIMENTS = ("positive", "neutral", "negative")

LEVEL_NAMES = {1: "low", 2: "medium", 3: "high"}

MIN_AGE, MAX_AGE = 18, 80

# ---------------------------------------------------------------------------
# Single source of truth for portfolio composition.
#
# Percentages are whole numbers and must sum to 100 - enforced at import time
# so a bad edit fails loudly instead of silently producing a broken chart.
# Crypto is held at 8% to stay inside the 5-10% band the assistant itself
# advises; the two are no longer allowed to contradict each other.
# ---------------------------------------------------------------------------
STRATEGIES = {
    "low": {
        "title": "Safety First Portfolio",
        "allocation": {
            "Government & Corporate Bonds": 40,
            "Fixed Deposits": 25,
            "Gold": 20,
            "Large-Cap Equity": 15,
        },
    },
    "medium": {
        "title": "Balanced Growth Portfolio",
        "allocation": {
            "Diversified Mutual Funds": 35,
            "Blue-Chip Equity": 25,
            "Index Funds": 20,
            "Debt Funds": 12,
            "Gold": 8,
        },
    },
    "high": {
        "title": "Aggressive Wealth Portfolio",
        "allocation": {
            "Growth & Mid-Cap Equity": 45,
            "Index & International ETFs": 25,
            "Sectoral / Thematic Funds": 15,
            "Cryptocurrency": 8,
            "Gold": 7,
        },
    },
}

for _risk, _entry in STRATEGIES.items():
    _total = sum(_entry["allocation"].values())
    if _total != 100:
        raise ValueError(f"STRATEGIES['{_risk}'] allocation sums to {_total}, not 100")

# ---------------------------------------------------------------------------
# Rule identifiers -> plain-English explanations.
#
# The expert system returns rule ids; this is what turns them into the
# "why did I get this?" trace shown in the UI.
# ---------------------------------------------------------------------------
RULE_EXPLANATIONS = {
    "capacity_high": "Your age, income and goal together give you a high capacity to absorb short-term volatility.",
    "capacity_medium": "Your age, income and goal give you a moderate capacity for market volatility.",
    "capacity_low": "Your age, income and goal give you a limited capacity to absorb losses.",
    "safety_goal_cap": "You chose capital safety as your goal, so growth assets are capped out.",
    "insufficient_surplus": "Your monthly investable surplus is under Rs 25,000 - building an emergency fund takes priority over market exposure.",
    "retirement_near_term": "You are within about five years of retirement, so protecting capital outweighs chasing returns.",
    "retirement_mid_term": "Retirement is on a 10-20 year horizon, which calls for a moderate rather than aggressive stance.",
    "senior_cap": "Past normal retirement age, capital preservation takes precedence over growth.",
    "tolerance_limits": "You could take more risk on paper, but we respect your stated comfort level and did not exceed it.",
    "bearish_defensive": "Current market news sentiment is negative, so the allocation was shifted one step more defensive.",
}


class InvalidProfile(ValueError):
    """Raised when the incoming user profile cannot be used for inference."""


# ---------------------------------------------------------------------------
# Prolog engine (optional)
# ---------------------------------------------------------------------------
_RULES_PATH = Path(__file__).with_name("rules.pl")

try:
    from pyswip import Prolog

    _prolog = Prolog()
    # as_posix() matters on Windows: SWI-Prolog treats a backslash inside a
    # quoted path as an escape character.
    _prolog.consult(_RULES_PATH.as_posix())
    PROLOG_AVAILABLE = True
except Exception as exc:  # pragma: no cover - depends on local SWI install
    _prolog = None
    PROLOG_AVAILABLE = False
    log.info("SWI-Prolog unavailable (%s); using the Python inference mirror.", exc)


def _as_text(value):
    """Normalise a pyswip term into a plain ``str``."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(getattr(value, "value", value))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_profile(age, income, tolerance, goal, sentiment="neutral"):
    """Check and normalise a profile, returning canonical lowercase values.

    Raises ``InvalidProfile`` with an actionable message on bad input.
    """
    try:
        age = int(age)
        income = int(income)
    except (TypeError, ValueError):
        raise InvalidProfile("Age and income must be whole numbers.")

    if not MIN_AGE <= age <= MAX_AGE:
        raise InvalidProfile(f"Age must be between {MIN_AGE} and {MAX_AGE}.")
    if income < 0:
        raise InvalidProfile("Income cannot be negative.")

    tolerance = str(tolerance).strip().lower()
    goal = str(goal).strip().lower()
    sentiment = str(sentiment).strip().lower()

    if tolerance not in TOLERANCES:
        raise InvalidProfile(f"Risk appetite must be one of {', '.join(TOLERANCES)}.")
    if goal not in GOALS:
        raise InvalidProfile(f"Goal must be one of {', '.join(GOALS)}.")
    if sentiment not in SENTIMENTS:
        sentiment = "neutral"

    return age, income, tolerance, goal, sentiment


# ---------------------------------------------------------------------------
# Inference - Python mirror of rules.pl
# ---------------------------------------------------------------------------
def _age_score(age):
    if age <= 30:
        return 3
    if age <= 45:
        return 2
    if age <= 60:
        return 1
    return 0


def _income_score(income):
    if income >= 75000:
        return 3
    if income >= 40000:
        return 2
    if income >= 25000:
        return 1
    return 0


def _goal_score(goal):
    return {"wealth": 2, "education": 1, "retirement": 1, "safety": 0}.get(goal, 1)


def _tolerance_level(tolerance):
    return {"low": 1, "medium": 2, "high": 3}.get(tolerance, 2)


def _base_capacity(age, income, goal):
    score = _age_score(age) + _income_score(income) + _goal_score(goal)
    if score >= 6:
        return 3
    if score >= 3:
        return 2
    return 1


def _cap_rules(age, income, goal):
    """Yield ``(rule_id, max_level)`` for every hard cap that applies."""
    if goal == "safety":
        yield "safety_goal_cap", 1
    if income < 25000:
        yield "insufficient_surplus", 1
    if goal == "retirement" and age >= 55:
        yield "retirement_near_term", 1
    if goal == "retirement" and 45 <= age < 55:
        yield "retirement_mid_term", 2
    if age > 60:
        yield "senior_cap", 2


def _python_infer(age, income, tolerance, goal, sentiment):
    """Mirror of ``recommend/7`` in rules.pl.  Returns ``(risk, rule_ids)``."""
    base = _base_capacity(age, income, goal)
    rules = [{3: "capacity_high", 2: "capacity_medium", 1: "capacity_low"}[base]]

    # Only caps that actually bind are reported, and only the tightest ones -
    # identical to applied_caps/6.
    binding = [(level, rule) for rule, level in _cap_rules(age, income, goal) if level < base]
    if binding:
        capped = min(level for level, _ in binding)
        rules.extend(rule for level, rule in binding if level == capped)
    else:
        capped = base

    tol = _tolerance_level(tolerance)
    if tol < capped:
        combined = tol
        rules.append("tolerance_limits")
    else:
        combined = capped

    if sentiment == "negative" and combined > 1:
        final = combined - 1
        rules.append("bearish_defensive")
    else:
        final = combined

    return LEVEL_NAMES[final], rules


def _prolog_infer(age, income, tolerance, goal, sentiment):
    """Run the SWI-Prolog engine.  Returns ``(risk, rule_ids)`` or ``None``."""
    if not PROLOG_AVAILABLE:
        return None

    query = (
        f"recommend({age}, {income}, {tolerance}, {goal}, {sentiment}, Risk, Rules)"
    )
    try:
        solutions = list(_prolog.query(query))
    except Exception as exc:
        log.warning("Prolog query failed (%s); falling back to Python inference.", exc)
        return None

    if not solutions:
        log.warning("Prolog returned no solution for %s; falling back.", query)
        return None

    risk = _as_text(solutions[0]["Risk"]).lower()
    rule_text = _as_text(solutions[0]["Rules"])
    rules = [r for r in rule_text.split(",") if r]

    if risk not in STRATEGIES:
        log.warning("Prolog returned unknown risk level %r; falling back.", risk)
        return None

    return risk, rules


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def strategy_text(allocation):
    """Render an allocation mapping as the human-readable strategy line."""
    return ", ".join(f"{pct}% {asset}" for asset, pct in allocation.items())


def get_recommendation(age, income, tolerance, goal, sentiment="neutral"):
    """Produce a full recommendation for a user profile.

    ``sentiment`` is the aggregated market news sentiment from ``market.py``;
    it can only ever make the recommendation more defensive, never more
    aggressive.

    Returns a dict with ``risk``, ``title``, ``strategy``, ``allocation``,
    ``rules``, ``reasons`` and ``engine``.
    """
    age, income, tolerance, goal, sentiment = validate_profile(
        age, income, tolerance, goal, sentiment
    )

    result = _prolog_infer(age, income, tolerance, goal, sentiment)
    engine = "prolog"
    if result is None:
        result = _python_infer(age, income, tolerance, goal, sentiment)
        engine = "python"

    risk, rules = result
    entry = STRATEGIES[risk]
    allocation = dict(entry["allocation"])

    return {
        "risk": risk,
        "risk_label": risk.capitalize(),
        "title": entry["title"],
        "strategy": strategy_text(allocation),
        "allocation": allocation,
        "rules": rules,
        "reasons": [RULE_EXPLANATIONS[r] for r in rules if r in RULE_EXPLANATIONS],
        "engine": engine,
        "sentiment": sentiment,
    }
