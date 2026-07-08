"""Configuration loading.

A single YAML file (config/config.yaml) is the one source of truth for every
tunable in the pipeline. Agents receive a plain dict slice of it; they never
reach into global state or hard-code thresholds. This keeps every run
reproducible from its config file alone.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class Config:
    """Thin, dotted-access wrapper around the parsed YAML."""

    def __init__(self, data: dict[str, Any], source: Path | None = None):
        self._data = data
        self.source = source

    @classmethod
    def load(cls, path: str | Path = "config/config.yaml") -> "Config":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"Config not found at {path!s}. Copy config/config.yaml and edit it."
            )
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls(data, source=path)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def section(self, name: str) -> dict[str, Any]:
        """Return one top-level section (e.g. 'ppi') as a dict."""
        return dict(self._data.get(name, {}))

    @property
    def output_dir(self) -> Path:
        d = Path(self._data.get("run", {}).get("output_dir", "outputs"))
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def db_path(self) -> str:
        return self._data.get("run", {}).get("db_path", "outputs/netpharm.sqlite")

    @staticmethod
    def env(name: str, required: bool = False) -> str | None:
        """Fetch a secret from the environment. Secrets never live in YAML."""
        val = os.environ.get(name)
        if required and not val:
            raise RuntimeError(f"Environment variable {name} is required but unset.")
        return val

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)
