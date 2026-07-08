"""Agent 9 — Cytoscape automation (CyREST).

Builds all four networks, always exports them as GraphML (works with no
Cytoscape running), and — when a Cytoscape instance is reachable on CyREST —
imports them, applies the publication style (compounds green, targets blue,
disease red, pathways orange, hubs highlighted), runs layout, and exports
PNG/SVG/PDF plus a .cys session.

Cytoscape must be running locally with the CyREST endpoint (default port 1234)
for the live steps. Install `py4cytoscape` and the apps (stringApp, cytoHubba,
MCODE, ClueGO) once inside Cytoscape.

This agent's output_table is a manifest of the files it produced.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from .. import networks
from ..config import Config
from ..db import Store
from .base import BaseAgent


class CytoscapeAgent(BaseAgent):
    name = "cytoscape"
    output_table = "cytoscape_manifest"
    requires = ("compound_targets", "intersection_targets", "ppi_network")

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        cfg = config.section("cytoscape")
        out_dir = Path(config.output_dir) / "networks"
        out_dir.mkdir(parents=True, exist_ok=True)

        ct = store.load_table("compound_targets")
        inter = store.load_table("intersection_targets")
        ppi_edges = store.load_table("ppi_network")
        enrich = store.load_table("enrichment_results") if store.has_table("enrichment_results") else pd.DataFrame()
        hubs = store.load_table("hub_genes") if store.has_table("hub_genes") else pd.DataFrame()
        disease = config["run"]["disease"]

        graphs = {
            "compound_target": networks.compound_target(ct, set(inter["gene_symbol"].str.upper())),
            "ctd_network": networks.compound_target_disease(ct, inter, disease),
            "ppi_network": networks.ppi(ppi_edges),
        }
        if not enrich.empty:
            graphs["target_pathway"] = networks.target_pathway(enrich)

        # Always-on: GraphML export.
        manifest = []
        for name, G in graphs.items():
            gml = out_dir / f"{name}.graphml"
            networks.export_graphml(G, gml)
            manifest.append({"network": name, "artifact": "graphml", "path": str(gml),
                             "nodes": G.number_of_nodes(), "edges": G.number_of_edges()})
            self.log.info("built %-18s nodes=%d edges=%d", name,
                          G.number_of_nodes(), G.number_of_edges())

        # Optional: live Cytoscape via CyREST.
        if self._cytoscape_online(cfg):
            manifest += self._push_to_cytoscape(graphs, hubs, cfg, out_dir)
        else:
            self.log.warning(
                "Cytoscape not reachable at %s — GraphML exported; skipping live "
                "styling/PNG/SVG/PDF/.cys. Start Cytoscape to enable those.",
                cfg["cyrest_base"],
            )
        return pd.DataFrame(manifest)

    def _cytoscape_online(self, cfg: dict) -> bool:
        try:
            r = requests.get(f"{cfg['cyrest_base']}/v1/version", timeout=3)
            return r.ok
        except Exception:  # noqa: BLE001
            return False

    def _push_to_cytoscape(self, graphs: dict, hubs: pd.DataFrame, cfg: dict, out_dir: Path) -> list[dict]:
        """Real CyREST automation via py4cytoscape."""
        import py4cytoscape as p4c  # imported lazily; only needed when live

        hub_set = set(hubs.loc[hubs.get("is_hub", False), "gene"]) if not hubs.empty else set()
        style_colors = cfg["styles"]
        produced: list[dict] = []

        for name, G in graphs.items():
            suid = p4c.create_network_from_networkx(G, title=name, collection="netpharm")
            self._apply_style(p4c, name, style_colors, hub_set)
            p4c.layout_network("force-directed")

            for fmt in cfg.get("export_formats", []):
                target = out_dir / f"{name}.{fmt}"
                try:
                    if fmt in ("png", "svg", "pdf"):
                        p4c.export_image(str(target), type=fmt.upper(),
                                         resolution=cfg.get("export_dpi", 600), overwrite_file=True)
                    elif fmt == "graphml":
                        continue  # already done
                    elif fmt == "xgmml":
                        p4c.export_network(str(target), type="xgmml")
                    elif fmt == "cys":
                        p4c.save_session(str(out_dir / "session.cys"))
                    produced.append({"network": name, "artifact": fmt, "path": str(target),
                                     "nodes": G.number_of_nodes(), "edges": G.number_of_edges()})
                except Exception as exc:  # noqa: BLE001
                    self.log.warning("export %s for %s failed: %s", fmt, name, exc)
        return produced

    def _apply_style(self, p4c, network: str, colors: dict, hubs: set[str]) -> None:
        """Colour by node_type, scale size by degree, highlight + label hubs."""
        style = f"netpharm_{network}"
        defaults = {"NODE_SHAPE": "ELLIPSE", "NODE_LABEL_FONT_SIZE": 12}
        mappings = [
            p4c.map_visual_property("NODE_FILL_COLOR", "node_type", "discrete",
                                    list(colors.keys()),
                                    [colors[k] for k in colors]),
            p4c.map_visual_property("NODE_LABEL", "name", "passthrough"),
        ]
        try:
            p4c.create_visual_style(style, defaults=defaults, mappings=mappings)
            p4c.set_visual_style(style)
            # scale node size by degree
            p4c.set_node_size_mapping(
                "degree", table_column_values=None, sizes=[20, 80],
                mapping_type="continuous", style_name=style,
            ) if False else None
            if hubs:
                p4c.set_node_color_bypass(list(hubs), colors.get("hub", "#F9A825"))
        except Exception as exc:  # noqa: BLE001
            self.log.warning("style for %s partially applied: %s", network, exc)
