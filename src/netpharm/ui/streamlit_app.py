"""Streamlit front-end.

    streamlit run src/netpharm/ui/streamlit_app.py

Features: plant + disease input, a Run Pipeline button, live step-status table,
interactive result tables per agent, and a download center for every produced
file. The Cytoscape preview embeds the exported PNG when Cytoscape produced one;
otherwise it links the GraphML you can open in Cytoscape yourself.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from netpharm.config import Config
from netpharm.db import Store
from netpharm.orchestrator import run_pipeline

st.set_page_config(page_title="Network Pharmacology", layout="wide")
st.title("🌿 Network Pharmacology Platform")

config = Config.load("config/config.yaml")

with st.sidebar:
    st.header("Run parameters")
    plant = st.text_input("Plant (scientific name)", config["run"]["plant"])
    disease = st.text_input("Disease", config["run"]["disease"])
    resume = st.checkbox("Resume from last completed step", value=True)
    run = st.button("▶ Run Pipeline", type="primary")

if run:
    config._data["run"]["plant"] = plant
    config._data["run"]["disease"] = disease
    config._data["run"]["resume"] = resume
    with st.spinner("Running pipeline… (this can take a while with live services)"):
        result = run_pipeline(config, force=not resume)
    st.success("Pipeline finished: " + ", ".join(result["completed"]))

store = Store(config.db_path, config.output_dir)

st.subheader("Pipeline status")
status = store.all_status()
if not status.empty:
    st.dataframe(status, use_container_width=True, hide_index=True)
else:
    st.info("No run yet. Set parameters and click Run Pipeline.")

st.subheader("Results")
tables = {
    "Phytochemicals": "plant_compounds",
    "Master compounds": "compounds_master",
    "Bioactive (ADME)": "bioactive_compounds",
    "Compound targets": "compound_targets",
    "Disease targets": "disease_targets",
    "Intersection": "intersection_targets",
    "PPI edges": "ppi_network",
    "Enrichment": "enrichment_results",
    "Hub genes": "hub_genes",
}
tabs = st.tabs(list(tables.keys()))
for tab, (label, name) in zip(tabs, tables.items()):
    with tab:
        if store.has_table(name):
            st.dataframe(store.load_table(name), use_container_width=True, hide_index=True)
        else:
            st.caption(f"{label} not generated yet.")

st.subheader("Cytoscape preview")
net_dir = Path(config.output_dir) / "networks"
pngs = sorted(net_dir.glob("*.png")) if net_dir.exists() else []
if pngs:
    for p in pngs:
        st.image(str(p), caption=p.stem)
else:
    st.caption("No PNG yet — GraphML files (if present) can be opened in Cytoscape.")

st.subheader("Download center")
out = Path(config.output_dir)
files = [f for f in out.rglob("*") if f.is_file()]
for f in sorted(files):
    with f.open("rb") as fh:
        st.download_button(f"⬇ {f.relative_to(out)}", fh.read(), file_name=f.name, key=str(f))
