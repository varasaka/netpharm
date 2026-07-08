"""Agent 6 — Target intersection.

Fully real. Intersects compound targets with disease targets on gene symbol,
records how many compounds hit each shared target (frequency), and writes Venn
counts to the log + a small stats table. The intersection genes are the core
node set for every downstream network.

Output: intersection_targets.csv
"""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..db import Store
from .base import BaseAgent


class IntersectionAgent(BaseAgent):
    name = "intersection"
    output_table = "intersection_targets"
    requires = ("compound_targets", "disease_targets")

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        ct = store.load_table("compound_targets")
        dt = store.load_table("disease_targets")

        compound_genes = set(ct["gene_name"].dropna().str.upper())
        disease_genes = set(dt["gene_symbol"].dropna().str.upper())
        shared = compound_genes & disease_genes

        # frequency = number of distinct compounds hitting each shared target
        freq = (
            ct.assign(gene=ct["gene_name"].str.upper())
            .loc[lambda d: d["gene"].isin(shared)]
            .groupby("gene")["compound_name"]
            .nunique()
            .rename("compound_frequency")
        )

        out = (
            pd.DataFrame({"gene_symbol": sorted(shared)})
            .merge(freq, left_on="gene_symbol", right_index=True, how="left")
            .fillna({"compound_frequency": 0})
            .sort_values("compound_frequency", ascending=False)
            .reset_index(drop=True)
        )
        out["compound_frequency"] = out["compound_frequency"].astype(int)

        # Venn counts — persisted as a tiny sibling table for the report/UI.
        venn = pd.DataFrame(
            [{
                "only_compound": len(compound_genes - disease_genes),
                "only_disease": len(disease_genes - compound_genes),
                "shared": len(shared),
                "compound_total": len(compound_genes),
                "disease_total": len(disease_genes),
            }]
        )
        store.save_table("intersection_venn", venn, csv_name="intersection_venn.csv")
        self.log.info(
            "Venn — compound=%d disease=%d shared=%d",
            len(compound_genes), len(disease_genes), len(shared),
        )
        return out
