"""Agent 5 — Disease gene collection.

Aggregates disease-associated genes from several sources and merges them. Each
source is a small method returning a common schema, so adding OpenTargets or
PharmGKB later is a one-method change.

  * DisGeNET  — has a REST API (now key-gated for most endpoints). Real request
    structure is provided; set DISGENET_API_KEY to enable it.
  * GeneCards — licensed / no open API; scraping hook.
  * OMIM      — API needs a registered key; hook provided.

Genes are merged on gene symbol, keeping the max relevance score, then filtered.
Output: disease_targets.csv
"""
from __future__ import annotations

import pandas as pd
import requests

from ..config import Config
from ..db import Store
from .base import BaseAgent

_COLS = ["gene_symbol", "gene_id", "relevance_score", "source"]


class DiseaseAgent(BaseAgent):
    name = "disease"
    output_table = "disease_targets"

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        cfg = config.section("disease")
        disease = config["run"]["disease"]
        self.log.info("collecting disease genes for %r", disease)

        frames = []
        if "disgenet" in cfg.get("sources", []):
            frames.append(self._disgenet(disease, cfg, config))
        if "genecards" in cfg.get("sources", []):
            frames.append(self._genecards(disease, cfg))
        if "omim" in cfg.get("sources", []):
            frames.append(self._omim(disease, cfg, config))

        merged = pd.concat([f for f in frames if not f.empty], ignore_index=True)
        merged = (
            merged.sort_values("relevance_score", ascending=False)
            .drop_duplicates(subset="gene_symbol", keep="first")
            .reset_index(drop=True)
        )
        thr = cfg.get("relevance_score_min", 0.0)
        merged = merged[merged["relevance_score"] >= thr].reset_index(drop=True)
        self.log.info("disease genes after merge+filter: %d", len(merged))
        return merged

    # ---------------------------------------------------------- DisGeNET
    def _disgenet(self, disease: str, cfg: dict, config: Config) -> pd.DataFrame:
        key = config.env("DISGENET_API_KEY")
        if not key:
            self.log.warning("DISGENET_API_KEY unset — returning demo disease genes.")
            demo = ["PPARG", "TNF", "INSR", "GSK3B", "DPP4", "SLC2A4", "IRS1", "AKT1"]
            return pd.DataFrame(
                {"gene_symbol": demo, "gene_id": pd.NA,
                 "relevance_score": [0.6] * len(demo), "source": "disgenet(demo)"}
            )
        # REAL request structure (v1 GDA endpoint):
        #   headers = {"Authorization": f"Bearer {key}"}
        #   r = requests.get(f"{cfg['disgenet_base']}/gda/disease/{cui}",
        #                    headers=headers, params={"source": "CURATED"})
        #   parse r.json() -> gene_symbol, geneid, score
        headers = {"Authorization": f"Bearer {key}"}
        try:
            r = requests.get(
                f"{cfg['disgenet_base']}/gda/disease",
                headers=headers, params={"disease": disease}, timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            return pd.DataFrame(
                [
                    {"gene_symbol": d["gene_symbol"], "gene_id": d.get("geneid"),
                     "relevance_score": d.get("score", 0.0), "source": "disgenet"}
                    for d in data
                ]
            )
        except Exception as exc:  # noqa: BLE001
            self.log.warning("DisGeNET request failed: %s", exc)
            return pd.DataFrame(columns=_COLS)

    def _genecards(self, disease: str, cfg: dict) -> pd.DataFrame:
        """GeneCards is licensed; provide a scraping hook or import an export."""
        self.log.info("GeneCards is a licensed hook — skipping (empty).")
        return pd.DataFrame(columns=_COLS)

    def _omim(self, disease: str, cfg: dict, config: Config) -> pd.DataFrame:
        """OMIM needs a registered API key (OMIM_API_KEY)."""
        if not config.env("OMIM_API_KEY"):
            self.log.info("OMIM_API_KEY unset — skipping OMIM (empty).")
        return pd.DataFrame(columns=_COLS)
