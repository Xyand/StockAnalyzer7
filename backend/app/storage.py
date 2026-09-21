"""Portfolio persistence in a local SQLite file.

Deliberately local-only: holdings are private data and never leave the
machine. There is no account system because there is no server to have one on.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .models import Portfolio

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
    name        TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

DEFAULT_NAME = "default"


class PortfolioStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, portfolio: Portfolio, name: str = DEFAULT_NAME) -> None:
        payload = portfolio.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO portfolios (name, payload, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
                (name, payload, datetime.utcnow().isoformat()),
            )

    def load(self, name: str = DEFAULT_NAME) -> Portfolio | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM portfolios WHERE name = ?", (name,)).fetchone()
        if row is None:
            return None
        return Portfolio(**json.loads(row["payload"]))

    def list_names(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, updated_at FROM portfolios ORDER BY updated_at DESC"
            ).fetchall()
        return [{"name": r["name"], "updated_at": r["updated_at"]} for r in rows]

    def delete(self, name: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM portfolios WHERE name = ?", (name,))
        return cursor.rowcount > 0
