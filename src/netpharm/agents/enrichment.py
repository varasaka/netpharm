"""Agent 8 — Functional enrichment (GO / KEGG / Reactome).

Fully real, using Enrichr's public REST API. Workflow:
  1. POST the intersection gene list -> receive a userListId,
  2. GET enrichment against each requested library (GO BP/MF/CC, KEGG, Reactome),
  3. keep terms below the adjusted p-value cutoff, take the top N per library.

Enrichr already returns Benjamini–Hochberg adjusted p-values. Output columns are
uniform across libraries so the report and plots can treat them together.

Output: enrichment_results.csv
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from ..config import Config
from ..db import Store
from .base import AgentError, BaseAgent

# Enrichr result tuple layout (see its API docs).
_RANK, _TERM, _P, _ZSCORE, _COMBINED, _GENES, _ADJP = 0, 1, 2, 3, 4, 5, 6


class EnrichmentAgent(BaseAgent):
    name = "enrichment"
    output_table = "enrichment_results"
    requires = ("intersection_targets",)

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        cfg = config.section("enrichment")
        genes = list(store.load_table("intersection_targets")["gene_symbol"].dropna().unique())
        if not genes:
            raise AgentError("No genes available for enrichment.")

        base = cfg["enrichr_base"]
        list_id = self._add_list(base, genes)
        frames = []
        for lib in cfg["libraries"]:
            try:
                frames.append(self._enrich(base, list_id, lib, cfg))
            except Exception as exc:  # noqa: BLE001
                self.log.warning("enrichment failed for %s: %s", lib, exc)
            time.sleep(0.3)

        if not frames:
            raise AgentError("Enrichr returned no results for any library.")
        out = pd.concat(frames, ignore_index=True)
        self.log.info("enriched terms kept: %d across %d libraries", len(out), len(frames))
        return out

    def _add_list(self, base: str, genes: list[str]) -> str:
        r = requests.post(
            f"{base}/addList",
            files={"list": (None, "\n".join(genes)), "description": (None, "netpharm")},
            timeout=60,
        )
        r.raise_for_status()
        return str(r.json()["userListId"])

    def _enrich(self, base: str, list_id: str, library: str, cfg: dict) -> pd.DataFrame:
        r = requests.get(
            f"{base}/enrich",
            params={"userListId": list_id, "backgroundType": library},
            timeout=60,
        )
        r.raise_for_status()
        rows = r.json().get(library, [])
        recs = []
        for item in rows:
            adjp = item[_ADJP]
            if adjp > cfg["adj_pvalue_max"]:
                continue
            category = _category_of(library)
            recs.append({
                "library": library,
                "category": category,
                "term": item[_TERM],
                "p_value": item[_P],
                "adj_p_value": adjp,
                "combined_score": item[_COMBINED],
                "gene_count": len(item[_GENES]),
                "genes": ";".join(item[_GENES]),
            })
        df = pd.DataFrame(recs).sort_values("adj_p_value").head(cfg["top_n"])
        return df


def _category_of(library: str) -> str:
    up = library.upper()
    if "GO_BIOLOGICAL" in up:
        return "GO:BP"
    if "GO_MOLECULAR" in up:
        return "GO:MF"
    if "GO_CELLULAR" in up:
        return "GO:CC"
    if "KEGG" in up:
        return "KEGG"
    if "REACTOME" in up:
        return "Reactome"
    return library
