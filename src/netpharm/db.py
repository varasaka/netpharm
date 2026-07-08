"""SQLite-backed intermediate store.

Two jobs:
  1. Persist every agent's output table so the pipeline is restartable and
     nothing is recomputed unnecessarily.
  2. Record step status (pending / running / done / failed) so the
     orchestrator can resume from the last completed step.

Each agent writes a named table (e.g. 'compound_targets'); the same data is
also mirrored to a CSV in outputs/ for the user, matching the spec's filenames.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .logging_setup import get_logger

log = get_logger("db")


class Store:
    def __init__(self, db_path: str, output_dir: str | Path = "outputs"):
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS step_status (
                    step        TEXT PRIMARY KEY,
                    status      TEXT NOT NULL,
                    rows        INTEGER,
                    updated_at  TEXT NOT NULL,
                    message     TEXT
                )
                """
            )

    # -- step bookkeeping ---------------------------------------------------
    def mark(self, step: str, status: str, rows: int | None = None, message: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO step_status(step,status,rows,updated_at,message)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(step) DO UPDATE SET
                     status=excluded.status, rows=excluded.rows,
                     updated_at=excluded.updated_at, message=excluded.message""",
                (step, status, rows, datetime.now(timezone.utc).isoformat(), message),
            )

    def status(self, step: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT status FROM step_status WHERE step=?", (step,)
            ).fetchone()
        return row[0] if row else None

    def is_done(self, step: str) -> bool:
        return self.status(step) == "done"

    def all_status(self) -> pd.DataFrame:
        with self._conn() as conn:
            return pd.read_sql("SELECT * FROM step_status ORDER BY updated_at", conn)

    # -- data tables --------------------------------------------------------
    def save_table(self, name: str, df: pd.DataFrame, csv_name: str | None = None) -> None:
        """Persist a dataframe to SQLite and mirror it to a CSV in outputs/."""
        if df.shape[1] == 0:
            # A zero-column frame is not a valid SQL table; record it as empty.
            log.warning("table %s has no columns — writing empty CSV only", name)
            (self.output_dir / (csv_name or f"{name}.csv")).write_text("", encoding="utf-8")
            return
        with self._conn() as conn:
            df.to_sql(name, conn, if_exists="replace", index=False)
        csv_path = self.output_dir / (csv_name or f"{name}.csv")
        df.to_csv(csv_path, index=False)
        log.info("saved %-24s rows=%-6d -> %s", name, len(df), csv_path.name)

    def load_table(self, name: str) -> pd.DataFrame:
        with self._conn() as conn:
            return pd.read_sql(f"SELECT * FROM '{name}'", conn)

    def has_table(self, name: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
        return row is not None
