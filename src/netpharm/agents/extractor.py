"""Agent 1 — Plant phytochemical extraction.

Two-stage design because no single service does both jobs:

  * IMPPAT maps a *plant* to its list of phytochemicals. It has no REST API, so
    `_imppat_phytochemicals` is a scraping hook (BeautifulSoup over the plant
    page). It is isolated so you can swap in a curated CSV, NPASS, or a
    licensed export without touching the rest of the pipeline.

  * PubChem PUG REST then enriches each compound name/ID with formula, weight,
    canonical SMILES, InChI and synonyms. This part uses the real, public
    PubChem API and works as-is.

Output: plant_compounds.csv
"""
from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

from ..config import Config
from ..db import Store
from .base import BaseAgent

_COLUMNS = [
    "compound_name", "source", "cid", "molecular_formula",
    "molecular_weight", "canonical_smiles", "inchi", "synonyms",
]


class ExtractorAgent(BaseAgent):
    name = "extractor"
    output_table = "plant_compounds"

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        cfg = config.section("extractor")
        plant = config["run"]["plant"]
        self.log.info("extracting phytochemicals for %r", plant)

        candidates = self._imppat_phytochemicals(plant, cfg)
        self.log.info("candidate phytochemicals: %d", len(candidates))
        cap = cfg.get("max_compounds", 0)
        if cap:
            candidates = candidates[:cap]

        rows: list[dict[str, Any]] = []
        for nm, fallback_smiles in candidates:
            try:
                rows.append(self._pubchem_enrich(nm, cfg))
            except Exception as exc:  # noqa: BLE001
                # Offline / lookup failure: keep the demo SMILES so downstream
                # standardization still has something to work on.
                self.log.warning("pubchem lookup failed for %r: %s", nm, exc)
                rows.append({
                    "compound_name": nm, "source": "imppat(offline)",
                    "canonical_smiles": fallback_smiles,
                })
            time.sleep(0.2)  # be polite to PubChem's rate limits

        df = pd.DataFrame(rows)
        for col in _COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA
        return df[_COLUMNS]

    # ------------------------------------------------------------- IMPPAT
    def _imppat_phytochemicals(self, plant: str, cfg: dict) -> list[tuple[str, str]]:
        """Return [(phytochemical_name, fallback_smiles)] for a plant.

        IMPPAT has no API. Replace the body with real scraping against
        cfg['imppat_base'] using requests + BeautifulSoup, or point it at a
        curated CSV. The demo fallback keeps the pipeline runnable offline; the
        SMILES let standardization proceed without a live PubChem call.
        """
        # --- REAL IMPLEMENTATION SKETCH (needs live IMPPAT + BeautifulSoup) ---
        # from bs4 import BeautifulSoup
        # url = f"{cfg['imppat_base']}/phytochemical/{plant.replace(' ', '%20')}"
        # html = requests.get(url, timeout=cfg['request_timeout']).text
        # soup = BeautifulSoup(html, "html.parser")
        # names = [a.text.strip() for a in soup.select("table.phytochemicals a")]
        # return [(n, "") for n in names]   # PubChem then fills SMILES
        # ---------------------------------------------------------------------
        self.log.warning(
            "IMPPAT scraping is a hook — returning a small demo list. "
            "Wire up cfg['imppat_base'] scraping or a curated CSV in your env."
        )
        return [
            ("Quercetin", "O=c1c(O)c(-c2ccc(O)c(O)c2)oc2cc(O)cc(O)c12"),
            ("Kaempferol", "O=c1c(O)c(-c2ccc(O)cc2)oc2cc(O)cc(O)c12"),
            ("Withaferin A",
             "CC1=C(C)C(=O)O[C@@H]1[C@]1(O)CC[C@H]2[C@@H]3CC=C4C[C@@H](O)C(=O)"
             "C=C4[C@]3(C)[C@H](O)C[C@]12C"),
            ("Luteolin", "O=c1cc(-c2ccc(O)c(O)c2)oc2cc(O)cc(O)c12"),
            ("Apigenin", "O=c1cc(-c2ccc(O)cc2)oc2cc(O)cc(O)c12"),
        ]

    # ------------------------------------------------------------- PubChem
    def _pubchem_enrich(self, name: str, cfg: dict) -> dict[str, Any]:
        base = cfg["pubchem_base"]
        timeout = cfg.get("request_timeout", 30)

        cids = requests.get(
            f"{base}/compound/name/{requests.utils.quote(name)}/cids/JSON", timeout=timeout
        ).json()["IdentifierList"]["CID"]
        cid = cids[0]

        props = requests.get(
            f"{base}/compound/cid/{cid}/property/"
            "MolecularFormula,MolecularWeight,CanonicalSMILES,InChI/JSON",
            timeout=timeout,
        ).json()["PropertyTable"]["Properties"][0]

        try:
            syn = requests.get(
                f"{base}/compound/cid/{cid}/synonyms/JSON", timeout=timeout
            ).json()["InformationList"]["Information"][0]["Synonym"][:5]
        except Exception:  # noqa: BLE001
            syn = []

        return {
            "compound_name": name,
            "source": "pubchem",
            "cid": cid,
            "molecular_formula": props.get("MolecularFormula"),
            "molecular_weight": props.get("MolecularWeight"),
            "canonical_smiles": props.get("CanonicalSMILES"),
            "inchi": props.get("InChI"),
            "synonyms": "; ".join(syn),
        }
