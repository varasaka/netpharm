"""Agent 10 — Hub gene analysis.

Fully real, using NetworkX on the STRING PPI edge table. Implements the
cytoHubba-family metrics directly so the ranking does not depend on Cytoscape
being available:

  * Degree        — node degree.
  * Betweenness   — networkx betweenness centrality.
  * Closeness     — networkx closeness centrality.
  * MNC           — Maximum Neighborhood Component: size of the largest
                    connected component of the node's neighborhood subgraph.
  * MCC           — Maximal Clique Centrality: for node v,
                    sum over maximal cliques C containing v of (|C|-1)!.
  * DMNC          — Density of Maximum Neighborhood Component:
                    E / N**(epsilon) over the MNC subgraph (epsilon=1.7).

Each metric yields a per-node score; nodes are then ranked and the top-N by MCC
(cytoHubba's default recommendation) are flagged as hubs, with all scores kept.

Output: hub_genes.csv
"""
from __future__ import annotations

import math
from collections import defaultdict

import networkx as nx
import pandas as pd

from ..config import Config
from ..db import Store
from .base import AgentError, BaseAgent

_EPSILON = 1.7  # DMNC exponent, per the cytoHubba definition


class HubGeneAgent(BaseAgent):
    name = "hubgenes"
    output_table = "hub_genes"
    requires = ("ppi_network",)

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        cfg = config.section("hub_genes")
        edges = store.load_table("ppi_network")
        if edges.empty:
            raise AgentError("PPI network is empty; cannot rank hub genes.")

        G = nx.from_pandas_edgelist(edges, "protein_a", "protein_b")
        G.remove_edges_from(nx.selfloop_edges(G))
        self.log.info("graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

        scores = pd.DataFrame({"gene": list(G.nodes())})
        methods = set(cfg.get("methods", []))
        if "Degree" in methods:
            scores["Degree"] = scores["gene"].map(dict(G.degree()))
        if "Betweenness" in methods:
            scores["Betweenness"] = scores["gene"].map(nx.betweenness_centrality(G))
        if "Closeness" in methods:
            scores["Closeness"] = scores["gene"].map(nx.closeness_centrality(G))
        if "MNC" in methods:
            scores["MNC"] = scores["gene"].map(self._mnc(G))
        if "DMNC" in methods:
            scores["DMNC"] = scores["gene"].map(self._dmnc(G))
        if "MCC" in methods:
            scores["MCC"] = scores["gene"].map(self._mcc(G))

        rank_by = "MCC" if "MCC" in scores.columns else "Degree"
        scores = scores.sort_values(rank_by, ascending=False).reset_index(drop=True)
        scores["rank"] = scores.index + 1
        top_n = cfg.get("top_n", 10)
        scores["is_hub"] = scores["rank"] <= top_n
        self.log.info("top hubs by %s: %s", rank_by,
                      ", ".join(scores.loc[scores["is_hub"], "gene"].tolist()))
        return scores

    # --------------------------------------------------------- metrics
    @staticmethod
    def _mnc(G: nx.Graph) -> dict[str, int]:
        out = {}
        for v in G.nodes():
            sub = G.subgraph(list(G.neighbors(v)))
            out[v] = (max((len(c) for c in nx.connected_components(sub)), default=0))
        return out

    @staticmethod
    def _dmnc(G: nx.Graph) -> dict[str, float]:
        out = {}
        for v in G.nodes():
            nbrs = list(G.neighbors(v))
            sub = G.subgraph(nbrs)
            comps = list(nx.connected_components(sub))
            if not comps:
                out[v] = 0.0
                continue
            largest = max(comps, key=len)
            mnc_sub = sub.subgraph(largest)
            n = mnc_sub.number_of_nodes()
            e = mnc_sub.number_of_edges()
            out[v] = 0.0 if n == 0 else e / (n ** _EPSILON)
        return out

    @staticmethod
    def _mcc(G: nx.Graph) -> dict[str, float]:
        """Maximal Clique Centrality.

        MCC(v) = sum over maximal cliques C containing v of (|C|-1)!.
        If v is in no clique of size > 1, MCC(v) = its degree (cytoHubba rule).
        """
        score: dict[str, float] = defaultdict(float)
        in_clique: dict[str, bool] = defaultdict(bool)
        for clique in nx.find_cliques(G):
            if len(clique) < 2:
                continue
            contrib = math.factorial(len(clique) - 1)
            for v in clique:
                score[v] += contrib
                in_clique[v] = True
        for v in G.nodes():
            if not in_clique[v]:
                score[v] = float(G.degree(v))
        return dict(score)
