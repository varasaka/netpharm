"""Base agent contract.

Every agent is an independent unit with the same shape:

    * a stable `name` and `output_table` (the spec's CSV name without extension)
    * a `run(store, config)` entry point
    * it reads its inputs from the Store (previous agents' tables), does its
      work, writes exactly one output table, and returns it.

The base class handles the cross-cutting concerns so each concrete agent only
contains domain logic: skip-if-already-done (restartability), status marking,
timing, and structured error capture.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod

import pandas as pd

from ..config import Config
from ..db import Store
from ..logging_setup import get_logger


class AgentError(RuntimeError):
    """Raised when an agent cannot produce its output."""


class BaseAgent(ABC):
    #: unique step id, used for status + graph node names
    name: str = "base"
    #: SQLite table + CSV filename (without .csv) this agent produces
    output_table: str = "base_output"
    #: tables this agent expects to already exist
    requires: tuple[str, ...] = ()

    def __init__(self) -> None:
        self.log = get_logger(f"agent.{self.name}")

    # ------------------------------------------------------------------ API
    def execute(self, store: Store, config: Config, force: bool = False) -> pd.DataFrame:
        """Run the agent, honouring resume semantics and recording status."""
        if not force and store.is_done(self.name) and store.has_table(self.output_table):
            self.log.info("skip (already done) -> loading cached %s", self.output_table)
            return store.load_table(self.output_table)

        self._check_requirements(store)
        self.log.info("start")
        store.mark(self.name, "running")
        t0 = time.perf_counter()
        try:
            df = self.run(store, config)
        except Exception as exc:  # noqa: BLE001 - we want to record every failure
            store.mark(self.name, "failed", message=str(exc))
            self.log.exception("failed: %s", exc)
            raise AgentError(f"{self.name} failed: {exc}") from exc

        if not isinstance(df, pd.DataFrame):
            raise AgentError(f"{self.name} must return a DataFrame, got {type(df)}")

        store.save_table(self.output_table, df, csv_name=f"{self.output_table}.csv")
        store.mark(self.name, "done", rows=len(df))
        self.log.info("done in %.1fs, rows=%d", time.perf_counter() - t0, len(df))
        return df

    def _check_requirements(self, store: Store) -> None:
        missing = [t for t in self.requires if not store.has_table(t)]
        if missing:
            raise AgentError(
                f"{self.name} requires upstream tables {missing} which do not exist. "
                "Run the earlier agents first."
            )

    # ------------------------------------------------------------- override
    @abstractmethod
    def run(self, store: Store, config: Config) -> pd.DataFrame:
        """Do the work and return the output dataframe. Implemented per agent."""
        raise NotImplementedError
