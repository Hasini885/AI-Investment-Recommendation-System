"""SQLite persistence for recommendation history.

Changes worth knowing about:

  * ``risk_appetite`` and ``market_sentiment`` are now stored.  The report
    describes sentiment flowing into the database; previously nothing ever
    wrote it.
  * Rows carry a ``session_id`` so the History page can show *your* history
    instead of every visitor's.
  * ``init_schema`` migrates older databases in place by adding missing
    columns, so an existing investments.db keeps working.
  * Rows come back as dicts, so callers no longer depend on column order.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).with_name("investments.db")

# column name -> DDL type, in display order
_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "session_id": "TEXT",
    "age": "INTEGER",
    "income": "INTEGER",
    "risk_appetite": "TEXT",
    "goal": "TEXT",
    "market_sentiment": "TEXT",
    "risk": "TEXT",
    "strategy_title": "TEXT",
    "strategy_details": "TEXT",
    "reasoning": "TEXT",
    "engine": "TEXT",
    "timestamp": "TEXT",
}


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema():
    """Create the table if absent, and add any columns an older file lacks."""
    ddl = ", ".join(f"{name} {decl}" for name, decl in _COLUMNS.items())
    with get_connection() as conn:
        conn.execute(f"CREATE TABLE IF NOT EXISTS recommendations ({ddl})")

        existing = {row["name"] for row in conn.execute("PRAGMA table_info(recommendations)")}
        for name, decl in _COLUMNS.items():
            if name not in existing:
                # PRIMARY KEY / AUTOINCREMENT cannot be added retrospectively;
                # only ever true for `id`, which exists on any real table.
                column_type = decl.split()[0]
                log.info("Migrating recommendations table: adding %s", name)
                conn.execute(f"ALTER TABLE recommendations ADD COLUMN {name} {column_type}")

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_recommendations_session "
            "ON recommendations(session_id, timestamp DESC)"
        )


def save_recommendation(session_id, age, income, risk_appetite, goal, recommendation):
    """Persist a recommendation, skipping an exact repeat of the last one.

    Streamlit re-runs the script on every interaction, so an unguarded insert
    produced duplicate rows on a single click.  Returns True if a row was
    written.
    """
    reasoning = " | ".join(recommendation.get("reasons", []))

    with get_connection() as conn:
        last = conn.execute(
            "SELECT age, income, risk_appetite, goal, risk, strategy_title, market_sentiment "
            "FROM recommendations WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()

        candidate = (
            age,
            income,
            risk_appetite,
            goal,
            recommendation["risk"],
            recommendation["title"],
            recommendation.get("sentiment", "neutral"),
        )
        if last is not None and tuple(last) == candidate:
            return False

        conn.execute(
            "INSERT INTO recommendations ("
            "session_id, age, income, risk_appetite, goal, market_sentiment, "
            "risk, strategy_title, strategy_details, reasoning, engine, timestamp"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                age,
                income,
                risk_appetite,
                goal,
                recommendation.get("sentiment", "neutral"),
                recommendation["risk"],
                recommendation["title"],
                recommendation["strategy"],
                reasoning,
                recommendation.get("engine", "python"),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    return True


def get_recommendations(session_id=None, limit=200):
    """Return saved recommendations, newest first.

    Pass ``session_id`` to scope to one visitor; omit it for the full table.
    """
    query = "SELECT * FROM recommendations"
    params = []
    if session_id is not None:
        query += " WHERE session_id = ?"
        params.append(session_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        return [dict(row) for row in conn.execute(query, params)]


def latest_recommendation(session_id):
    """Most recent recommendation for a session, or None."""
    rows = get_recommendations(session_id=session_id, limit=1)
    return rows[0] if rows else None


init_schema()
