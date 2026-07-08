"""Agent 3 — ADME screening (SwissADME).

SwissADME exposes no public API, so submission + result parsing runs through
Playwright. The two site-specific pieces (`_submit_swissadme`) are isolated
behind one method; everything downstream — the filtering rules that decide
which compounds are 'bioactive' — is real, config-driven, and independent of
how the raw ADME table was obtained. That means you can also feed this agent a
CSV exported manually from SwissADME and the filtering still applies.

Output: bioactive_compounds.csv
"""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..db import Store
from .base import BaseAgent

# Columns we expect from SwissADME (a subset of its full export).
_ADME_COLS = [
    "compound_name", "std_smiles", "mw", "lipinski_violations",
    "gi_absorption", "bioavailability_score", "bbb_permeant", "pains_alerts",
]


class AdmeAgent(BaseAgent):
    name = "adme"
    output_table = "bioactive_compounds"
    requires = ("compounds_master",)

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        cfg = config.section("adme")
        master = store.load_table("compounds_master")

        adme = self._submit_swissadme(master, cfg)
        self.log.info("received ADME rows: %d", len(adme))

        filtered = self._apply_rules(adme, cfg["rules"])
        self.log.info("passed drug-likeness filter: %d / %d", len(filtered), len(adme))
        return filtered.reset_index(drop=True)

    # ---------------------------------------------------------- scraping
    def _submit_swissadme(self, master: pd.DataFrame, cfg: dict) -> pd.DataFrame:
        """Submit SMILES to SwissADME and parse the results table.

        REAL IMPLEMENTATION (needs `playwright install chromium`):

            from playwright.sync_api import sync_playwright
            smiles = "\\n".join(master["std_smiles"].dropna())
            with sync_playwright() as p:
                b = p.chromium.launch(headless=cfg["headless"])
                pg = b.new_page()
                pg.goto(cfg["swissadme_url"])
                pg.fill("#smiles", smiles)
                pg.click("#submitButton")
                pg.wait_for_selector("#results")
                # SwissADME offers a CSV export link; prefer downloading it:
                # href = pg.get_attribute("a#csv-export", "href")
                # download and read_csv, then map its columns to _ADME_COLS.

        Below is an offline stand-in so the pipeline stays runnable end-to-end.
        Replace it with the block above in your environment.
        """
        self.log.warning(
            "SwissADME submission is a Playwright hook — returning heuristic "
            "placeholder ADME values. Wire up cfg['swissadme_url'] to go live."
        )
        rows = []
        for _, r in master.iterrows():
            mw = float(r.get("molecular_weight") or 0) or 350.0
            rows.append(
                {
                    "compound_name": r.get("compound_name"),
                    "std_smiles": r.get("std_smiles"),
                    "mw": mw,
                    "lipinski_violations": 0 if mw <= 500 else 1,
                    "gi_absorption": "High" if mw <= 500 else "Low",
                    "bioavailability_score": 0.55,
                    "bbb_permeant": mw <= 400,
                    "pains_alerts": 0,
                }
            )
        return pd.DataFrame(rows, columns=_ADME_COLS)

    # ---------------------------------------------------------- filtering
    def _apply_rules(self, adme: pd.DataFrame, rules: dict) -> pd.DataFrame:
        mask = pd.Series(True, index=adme.index)
        if "lipinski_violations_max" in rules:
            mask &= adme["lipinski_violations"] <= rules["lipinski_violations_max"]
        if rules.get("gi_absorption"):
            mask &= adme["gi_absorption"].isin(rules["gi_absorption"])
        if "bioavailability_min" in rules:
            mask &= adme["bioavailability_score"] >= rules["bioavailability_min"]
        if rules.get("exclude_pains_alerts"):
            mask &= adme["pains_alerts"].fillna(0) == 0
        return adme[mask]
