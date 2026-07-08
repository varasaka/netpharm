"""Network construction.

Builds the four networks the study needs as NetworkX graphs with a `node_type`
attribute on every node (compound / target / disease / pathway). These export to
GraphML directly (so results exist even with no Cytoscape), and Agent 9 also
pushes them to Cytoscape via CyREST for publication styling.
"""
from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd


def _typed_node(G: nx.Graph, name: str, node_type: str) -> None:
    G.add_node(name, node_type=node_type, name=name)


def compound_target(compound_targets: pd.DataFrame, keep_genes: set[str] | None = None) -> nx.Graph:
    G = nx.Graph()
    for _, r in compound_targets.iterrows():
        gene = str(r["gene_name"]).upper()
        if keep_genes is not None and gene not in keep_genes:
            continue
        cpd = str(r["compound_name"])
        _typed_node(G, cpd, "compound")
        _typed_node(G, gene, "target")
        G.add_edge(cpd, gene, weight=float(r.get("probability", 1.0) or 1.0))
    return G


def target_pathway(enrichment: pd.DataFrame, categories=("KEGG",)) -> nx.Graph:
    G = nx.Graph()
    sub = enrichment[enrichment["category"].isin(categories)]
    for _, r in sub.iterrows():
        pathway = str(r["term"])
        _typed_node(G, pathway, "pathway")
        for gene in str(r["genes"]).split(";"):
            gene = gene.strip().upper()
            if not gene:
                continue
            _typed_node(G, gene, "target")
            G.add_edge(gene, pathway, weight=float(r.get("combined_score", 1.0)))
    return G


def compound_target_disease(
    compound_targets: pd.DataFrame, intersection: pd.DataFrame, disease_name: str
) -> nx.Graph:
    shared = set(intersection["gene_symbol"].str.upper())
    G = compound_target(compound_targets, keep_genes=shared)
    _typed_node(G, disease_name, "disease")
    for gene in shared:
        if G.has_node(gene):
            G.add_edge(gene, disease_name, weight=1.0)
    return G


def ppi(edges: pd.DataFrame) -> nx.Graph:
    G = nx.Graph()
    for _, r in edges.iterrows():
        for p in (r["protein_a"], r["protein_b"]):
            _typed_node(G, str(p), "target")
        G.add_edge(str(r["protein_a"]), str(r["protein_b"]),
                   weight=float(r.get("combined_score", 1.0)))
    return G


def export_graphml(G: nx.Graph, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(G, str(path))
