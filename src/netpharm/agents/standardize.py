"""Agent 2 — Chemical standardization.

Fully real, using RDKit. For each compound we:
  * parse the SMILES,
  * run RDKit's standardization (cleanup, largest-fragment, uncharge),
  * recompute canonical SMILES, molecular formula and exact weight,
  * derive an InChIKey and use it to drop duplicates.

Rows whose SMILES cannot be parsed are flagged 'invalid' and excluded from the
master database (but logged). Output: compounds_master.csv
"""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..db import Store
from .base import AgentError, BaseAgent


class StandardizeAgent(BaseAgent):
    name = "standardize"
    output_table = "compounds_master"
    requires = ("plant_compounds",)

    def run(self, store: Store, config: Config) -> pd.DataFrame:
        try:
            from rdkit import Chem, RDLogger
            from rdkit.Chem import Descriptors, rdMolDescriptors
            from rdkit.Chem.MolStandardize import rdMolStandardize
        except ImportError as exc:  # pragma: no cover
            raise AgentError("RDKit is required for Agent 2: pip install rdkit") from exc

        RDLogger.DisableLog("rdApp.*")
        df = store.load_table("plant_compounds")

        enumerator = rdMolStandardize.TautomerEnumerator()
        lfc = rdMolStandardize.LargestFragmentChooser()
        uncharger = rdMolStandardize.Uncharger()

        records, invalid = [], 0
        for _, row in df.iterrows():
            smiles = row.get("canonical_smiles")
            if not isinstance(smiles, str) or not smiles:
                invalid += 1
                continue
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                invalid += 1
                self.log.warning("unparseable SMILES for %s", row.get("compound_name"))
                continue

            mol = rdMolStandardize.Cleanup(mol)
            mol = lfc.choose(mol)
            mol = uncharger.uncharge(mol)
            mol = enumerator.Canonicalize(mol)

            records.append(
                {
                    "compound_name": row.get("compound_name"),
                    "cid": row.get("cid"),
                    "std_smiles": Chem.MolToSmiles(mol),
                    "molecular_formula": rdMolDescriptors.CalcMolFormula(mol),
                    "molecular_weight": round(Descriptors.MolWt(mol), 3),
                    "inchikey": Chem.MolToInchiKey(mol),
                    "num_heavy_atoms": mol.GetNumHeavyAtoms(),
                }
            )

        master = pd.DataFrame(records)
        before = len(master)
        master = master.drop_duplicates(subset="inchikey").reset_index(drop=True)
        self.log.info(
            "standardized=%d  invalid=%d  deduped=%d",
            before, invalid, before - len(master),
        )
        return master
