"""Agent 7 — Protein–Protein Interaction (STRING).

Fully real, against STRING's public REST API. Two calls:
  1. map the intersection gene symbols to STRING identifiers,
  2. fetch the interaction network among them, filtered by confidence score.

Emits an edge table (ppi_network.csv), a node table, and network statistics.
STRING's terms allow programmatic access for reasonable volumes; keep the gene
set to the intersection targets (typically tens–hundreds of genes).
"""
from __future__ import annotations

import io

import pandas as pd
import requests

from ..config import Config
from ..db import Store
from .base import AgentError, BaseAgent


class PpiAgent(BaseAgent):
    name = "ppi"
    output_table = "ppi_network"
    requires = ("intersection_targets",)

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        cfg = config.section("ppi")
        species = config["run"]["species_taxon"]
        genes = list(store.load_table("intersection_targets")["gene_symbol"].dropna().unique())
        if not genes:
            raise AgentError("No intersection targets to build a PPI network from.")

        base = cfg["string_base"]
        mapped = self._map_ids(base, genes, species, cfg)
        edges = self._network(base, mapped, species, cfg)

        # Node table with degree.
        deg = pd.concat([edges["protein_a"], edges["protein_b"]]).value_counts()
        nodes = deg.rename_axis("gene").reset_index(name="degree")
        store.save_table("ppi_nodes", nodes, csv_name="ppi_nodes.csv")

        stats = pd.DataFrame([{
            "nodes": len(nodes),
            "edges": len(edges),
            "avg_degree": round(2 * len(edges) / max(len(nodes), 1), 3),
            "min_score": cfg["min_score"],
        }])
        store.save_table("ppi_stats", stats, csv_name="ppi_stats.csv")
        self.log.info("PPI nodes=%d edges=%d", len(nodes), len(edges))
        return edges

    def _map_ids(self, base: str, genes: list[str], species: int, cfg: dict) -> list[str]:
        r = requests.post(
            f"{base}/tsv/get_string_ids",
            data={"identifiers": "\r".join(genes), "species": species,
                  "limit": 1, "caller_identity": "netpharm"},
            timeout=60,
        )
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), sep="\t")
        return df["stringId"].tolist()

    def _network(self, base: str, string_ids: list[str], species: int, cfg: dict) -> pd.DataFrame:
        r = requests.post(
            f"{base}/tsv/network",
            data={"identifiers": "\r".join(string_ids), "species": species,
                  "caller_identity": "netpharm"},
            timeout=120,
        )
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), sep="\t")
        # STRING 'score' is 0-1; convert to 0-1000 to compare with min_score.
        df["combined_score"] = (df["score"] * 1000).round().astype(int)
        df = df[df["combined_score"] >= cfg["min_score"]]
        edges = df.rename(
            columns={"preferredName_A": "protein_a", "preferredName_B": "protein_b"}
        )[["protein_a", "protein_b", "combined_score"]]
        # de-duplicate undirected edges
        edges["key"] = edges.apply(
            lambda r: tuple(sorted((r["protein_a"], r["protein_b"]))), axis=1
        )
        edges = edges.drop_duplicates("key").drop(columns="key").reset_index(drop=True)
        return edges
