"""Agent 4 — Target prediction (SwissTargetPrediction).

Same pattern as Agent 3: the site interaction is a Playwright hook, the
probability filtering is real and config-driven. One row per (compound, target)
pair above the probability threshold. BindingDB / ChEMBL are future sources and
can be added as extra hooks that append to the same output schema.

Output: compound_targets.csv
"""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..db import Store
from .base import BaseAgent

_COLS = ["compound_name", "gene_name", "target_protein", "probability", "species"]


class TargetsAgent(BaseAgent):
    name = "targets"
    output_table = "compound_targets"
    requires = ("bioactive_compounds",)

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        cfg = config.section("targets")
        species = config["run"]["species_taxon"]
        compounds = store.load_table("bioactive_compounds")

        preds = self._predict(compounds, species, cfg)
        thr = cfg.get("probability_min", 0.1)
        kept = preds[preds["probability"] >= thr].reset_index(drop=True)
        self.log.info(
            "predictions=%d  kept(prob>=%.2f)=%d  unique genes=%d",
            len(preds), thr, len(kept), kept["gene_name"].nunique(),
        )
        return kept

    def _predict(self, compounds: pd.DataFrame, species: int, cfg: dict) -> pd.DataFrame:
        """Query SwissTargetPrediction per compound.

        REAL IMPLEMENTATION (Playwright):
            for each std_smiles:
                pg.goto(cfg['swiss_target_url'])
                pg.select_option("#organism", str(species))
                pg.fill("#smilesBox", smiles)
                pg.click("#submitButton")
                pg.wait_for_selector("table#resultTable")
                # parse gene name, target, probability from the results table,
                # or download the CSV export the site provides.

        Offline stand-in below keeps the demo runnable.
        """
        self.log.warning(
            "SwissTargetPrediction is a Playwright hook — returning demo targets. "
            "Wire up cfg['swiss_target_url'] in your environment."
        )
        demo_genes = ["PPARG", "AKT1", "PIK3CA", "TNF", "INSR", "GSK3B", "PTPN1", "DPP4"]
        rows = []
        for i, (_, c) in enumerate(compounds.iterrows()):
            for j, g in enumerate(demo_genes):
                rows.append(
                    {
                        "compound_name": c.get("compound_name"),
                        "gene_name": g,
                        "target_protein": f"{g}_HUMAN",
                        "probability": round(max(0.05, 0.9 - 0.1 * ((i + j) % 8)), 2),
                        "species": species,
                    }
                )
        return pd.DataFrame(rows, columns=_COLS)
