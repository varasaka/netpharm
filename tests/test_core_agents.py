"""Tests for the deterministic, dependency-light agents.

These run without any external service, exercising the real logic in the
intersection and hub-gene agents plus the network builders.
"""
import networkx as nx
import pandas as pd
import pytest

from netpharm.agents.hubgenes import HubGeneAgent
from netpharm.agents.intersection import IntersectionAgent
from netpharm import networks


class FakeStore:
    """Minimal in-memory Store stand-in for unit tests."""
    def __init__(self, tables):
        self._t = dict(tables)
        self.saved = {}

    def load_table(self, name):
        return self._t[name]

    def has_table(self, name):
        return name in self._t

    def save_table(self, name, df, csv_name=None):
        self.saved[name] = df


class FakeConfig:
    def __init__(self, data):
        self._data = data

    def __getitem__(self, k):
        return self._data[k]

    def section(self, name):
        return self._data.get(name, {})


def test_intersection_finds_shared_targets_and_frequency():
    ct = pd.DataFrame({
        "compound_name": ["A", "A", "B", "C"],
        "gene_name": ["PPARG", "TNF", "PPARG", "XYZ"],
    })
    dt = pd.DataFrame({"gene_symbol": ["pparg", "TNF", "IRS1"], "relevance_score": [1, 1, 1]})
    store = FakeStore({"compound_targets": ct, "disease_targets": dt})
    out = IntersectionAgent().run(store, FakeConfig({"run": {}}))

    genes = set(out["gene_symbol"])
    assert genes == {"PPARG", "TNF"}          # XYZ and IRS1 excluded
    freq = dict(zip(out["gene_symbol"], out["compound_frequency"]))
    assert freq["PPARG"] == 2                  # hit by compounds A and B
    assert freq["TNF"] == 1
    assert "intersection_venn" in store.saved


def test_mcc_matches_definition_on_triangle():
    # A triangle is one maximal clique of size 3 -> MCC = (3-1)! = 2 for each node.
    G = nx.Graph([("a", "b"), ("b", "c"), ("a", "c")])
    mcc = HubGeneAgent._mcc(G)
    assert mcc == {"a": 2.0, "b": 2.0, "c": 2.0}


def test_mcc_falls_back_to_degree_for_isolated_edge_node():
    # A node in no clique >1 gets its degree as MCC.
    G = nx.Graph([("a", "b")])  # single edge = clique size 2 -> (2-1)! = 1
    mcc = HubGeneAgent._mcc(G)
    assert mcc == {"a": 1.0, "b": 1.0}


def test_hub_agent_ranks_and_flags_top_n():
    edges = pd.DataFrame({
        "protein_a": ["h", "h", "h", "h", "x"],
        "protein_b": ["a", "b", "c", "d", "a"],
    })
    store = FakeStore({"ppi_network": edges})
    cfg = FakeConfig({"hub_genes": {
        "methods": ["Degree", "Betweenness", "Closeness", "MCC", "MNC", "DMNC"],
        "top_n": 1,
    }})
    out = HubGeneAgent().run(store, cfg)
    assert out.iloc[0]["gene"] == "h"          # highest-degree node ranks first
    assert out["is_hub"].sum() == 1
    for col in ["Degree", "Betweenness", "Closeness", "MCC", "MNC", "DMNC"]:
        assert col in out.columns


def test_network_builder_tags_node_types():
    ct = pd.DataFrame({
        "compound_name": ["Cmp1"], "gene_name": ["PPARG"], "probability": [0.9],
    })
    inter = pd.DataFrame({"gene_symbol": ["PPARG"]})
    G = networks.compound_target_disease(ct, inter, "T2DM")
    assert G.nodes["Cmp1"]["node_type"] == "compound"
    assert G.nodes["PPARG"]["node_type"] == "target"
    assert G.nodes["T2DM"]["node_type"] == "disease"
    assert G.has_edge("PPARG", "T2DM")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
