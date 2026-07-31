"""Tests for the recommendation engine.

Run with:  python -m unittest -v        (no third-party dependencies)

The equivalence test is the important one: it drives the full input grid
through both the Prolog expert system and the Python mirror and asserts they
agree. That is what stops the two engines drifting apart the way they had.
It skips automatically when SWI-Prolog is not installed.
"""

import itertools
import unittest

import advisor
from advisor import (
    GOALS,
    STRATEGIES,
    TOLERANCES,
    InvalidProfile,
    _python_infer,
    _prolog_infer,
    get_recommendation,
)

AGES = [18, 25, 30, 31, 40, 45, 46, 55, 60, 61, 80]
INCOMES = [0, 10_000, 24_999, 25_000, 39_999, 40_000, 74_999, 75_000, 250_000]
SENTIMENTS = ["positive", "neutral", "negative"]

LEVEL = {"low": 1, "medium": 2, "high": 3}


def grid():
    return itertools.product(AGES, INCOMES, TOLERANCES, GOALS, SENTIMENTS)


class TestStrategyTable(unittest.TestCase):
    def test_allocations_sum_to_100(self):
        for risk, entry in STRATEGIES.items():
            self.assertEqual(sum(entry["allocation"].values()), 100, f"{risk} allocation")

    def test_allocations_are_positive_whole_numbers(self):
        for risk, entry in STRATEGIES.items():
            for asset, pct in entry["allocation"].items():
                self.assertIsInstance(pct, int, f"{risk}/{asset}")
                self.assertGreater(pct, 0, f"{risk}/{asset}")

    def test_crypto_stays_within_the_band_the_assistant_advises(self):
        crypto = STRATEGIES["high"]["allocation"].get("Cryptocurrency", 0)
        self.assertLessEqual(crypto, 10, "high-risk crypto share exceeds the advised 5-10% band")

    def test_donut_segment_count_stays_readable(self):
        for risk, entry in STRATEGIES.items():
            self.assertLessEqual(len(entry["allocation"]), 6, f"{risk} has too many segments")


class TestInferenceInvariants(unittest.TestCase):
    """Properties that must hold for every profile in the grid."""

    def test_safety_goal_is_always_low_risk(self):
        for age, income, tol, _, sent in grid():
            risk, _ = _python_infer(age, income, tol, "safety", sent)
            self.assertEqual(risk, "low", f"age={age} income={income} tol={tol}")

    def test_no_investable_surplus_is_always_low_risk(self):
        for age, tol, goal, sent in itertools.product(AGES, TOLERANCES, GOALS, SENTIMENTS):
            for income in (0, 10_000, 24_999):
                risk, _ = _python_infer(age, income, tol, goal, sent)
                self.assertEqual(risk, "low", f"age={age} income={income} goal={goal}")

    def test_never_exceeds_stated_tolerance(self):
        for age, income, tol, goal, sent in grid():
            risk, _ = _python_infer(age, income, tol, goal, sent)
            self.assertLessEqual(
                LEVEL[risk], LEVEL[tol],
                f"age={age} income={income} tol={tol} goal={goal} gave {risk}",
            )

    def test_more_income_never_lowers_risk(self):
        for age, tol, goal, sent in itertools.product(AGES, TOLERANCES, GOALS, SENTIMENTS):
            levels = [LEVEL[_python_infer(age, i, tol, goal, sent)[0]] for i in INCOMES]
            self.assertEqual(levels, sorted(levels), f"age={age} tol={tol} goal={goal}")

    def test_older_never_raises_risk(self):
        for income, tol, goal, sent in itertools.product(INCOMES, TOLERANCES, GOALS, SENTIMENTS):
            levels = [LEVEL[_python_infer(a, income, tol, goal, sent)[0]] for a in AGES]
            self.assertEqual(levels, sorted(levels, reverse=True),
                             f"income={income} tol={tol} goal={goal}")

    def test_higher_tolerance_never_lowers_risk(self):
        for age, income, goal, sent in itertools.product(AGES, INCOMES, GOALS, SENTIMENTS):
            levels = [LEVEL[_python_infer(age, income, t, goal, sent)[0]] for t in TOLERANCES]
            self.assertEqual(levels, sorted(levels), f"age={age} income={income} goal={goal}")

    def test_bearish_sentiment_never_increases_risk(self):
        for age, income, tol, goal in itertools.product(AGES, INCOMES, TOLERANCES, GOALS):
            neutral, _ = _python_infer(age, income, tol, goal, "neutral")
            bearish, _ = _python_infer(age, income, tol, goal, "negative")
            self.assertLessEqual(LEVEL[bearish], LEVEL[neutral])

    def test_bullish_sentiment_never_increases_risk(self):
        """Sentiment is a one-way defensive lever - it must not make us braver."""
        for age, income, tol, goal in itertools.product(AGES, INCOMES, TOLERANCES, GOALS):
            neutral, _ = _python_infer(age, income, tol, goal, "neutral")
            bullish, _ = _python_infer(age, income, tol, goal, "positive")
            self.assertEqual(LEVEL[bullish], LEVEL[neutral])

    def test_every_result_carries_at_least_one_reason(self):
        for age, income, tol, goal, sent in grid():
            _, rules = _python_infer(age, income, tol, goal, sent)
            self.assertTrue(rules)
            for rule in rules:
                self.assertIn(rule, advisor.RULE_EXPLANATIONS, f"unexplained rule {rule}")


class TestRegressions(unittest.TestCase):
    """Specific behaviours that used to be wrong."""

    def test_young_investor_with_no_income_is_not_aggressive(self):
        # rules.pl previously matched "age <= 25" first and unguarded, so this
        # profile was handed a portfolio containing crypto.
        rec = get_recommendation(22, 0, "high", "wealth")
        self.assertEqual(rec["risk"], "low")
        self.assertNotIn("Cryptocurrency", rec["allocation"])

    def test_high_earner_wanting_low_risk_gets_low_risk(self):
        rec = get_recommendation(28, 200_000, "low", "wealth")
        self.assertEqual(rec["risk"], "low")
        self.assertIn("tolerance_limits", rec["rules"])

    def test_risk_appetite_actually_changes_the_outcome(self):
        # The appetite selector used to be collected and discarded.
        low = get_recommendation(30, 90_000, "low", "wealth")
        high = get_recommendation(30, 90_000, "high", "wealth")
        self.assertNotEqual(low["risk"], high["risk"])

    def test_moderate_earner_is_not_forced_to_low_by_precedence_bug(self):
        # `goal == "retirement" and age > 45 or income < 30000` made every
        # profile under 30k low, whatever else was true.
        rec = get_recommendation(30, 50_000, "high", "wealth")
        self.assertIn(rec["risk"], ("medium", "high"))

    def test_strategy_text_matches_allocation_exactly(self):
        for tol, goal in itertools.product(TOLERANCES, GOALS):
            rec = get_recommendation(35, 80_000, tol, goal)
            for asset, pct in rec["allocation"].items():
                self.assertIn(f"{pct}% {asset}", rec["strategy"])

    def test_near_retirement_is_protected(self):
        rec = get_recommendation(58, 200_000, "high", "retirement")
        self.assertEqual(rec["risk"], "low")


class TestValidation(unittest.TestCase):
    def test_rejects_out_of_range_age(self):
        for bad_age in (17, 81, -1):
            with self.assertRaises(InvalidProfile):
                get_recommendation(bad_age, 50_000, "medium", "wealth")

    def test_rejects_negative_income(self):
        with self.assertRaises(InvalidProfile):
            get_recommendation(30, -1, "medium", "wealth")

    def test_rejects_unknown_goal_and_tolerance(self):
        with self.assertRaises(InvalidProfile):
            get_recommendation(30, 50_000, "medium", "yacht")
        with self.assertRaises(InvalidProfile):
            get_recommendation(30, 50_000, "reckless", "wealth")

    def test_accepts_mixed_case_input(self):
        rec = get_recommendation(30, 50_000, "Medium", "Wealth")
        self.assertIn(rec["risk"], ("low", "medium", "high"))

    def test_unknown_sentiment_degrades_to_neutral(self):
        rec = get_recommendation(30, 50_000, "medium", "wealth", "euphoric")
        self.assertEqual(rec["sentiment"], "neutral")


@unittest.skipUnless(advisor.PROLOG_AVAILABLE, "SWI-Prolog not installed")
class TestEngineEquivalence(unittest.TestCase):
    """The Prolog expert system and the Python mirror must never disagree."""

    def test_engines_agree_across_the_grid(self):
        mismatches = []
        for age, income, tol, goal, sent in grid():
            prolog = _prolog_infer(age, income, tol, goal, sent)
            self.assertIsNotNone(prolog, f"Prolog produced no solution for {age}/{income}")
            python = _python_infer(age, income, tol, goal, sent)
            if (prolog[0], sorted(prolog[1])) != (python[0], sorted(python[1])):
                mismatches.append((age, income, tol, goal, sent, prolog, python))

        self.assertEqual(mismatches[:5], [], f"{len(mismatches)} disagreements")

    def test_prolog_is_deterministic(self):
        """recommend/7 must have exactly one solution - no leftover choice points."""
        for age, income, tol, goal, sent in itertools.islice(grid(), 0, None, 37):
            query = f"recommend({age}, {income}, {tol}, {goal}, {sent}, R, Rules)"
            solutions = list(advisor._prolog.query(query))
            self.assertEqual(len(solutions), 1, f"{query} gave {len(solutions)} solutions")


if __name__ == "__main__":
    unittest.main(verbosity=2)
