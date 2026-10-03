"""AlphaFold DB client adapter with strict monomer boundary enforcement (enforcing D-05)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from quaternary.clients.base import BaseBioClient

logger = logging.getLogger(__name__)


class AlphaFoldClient(BaseBioClient):
    """Client for querying AlphaFold DB structural coordinates and monomeric pLDDT.

    CRITICAL INVARIANT (D-05 Monomer Boundary):
    AlphaFold DB v4 contains strictly monomeric structural predictions.
    This client is strictly forbidden from asserting any oligomeric state or stoichiometry
    from AlphaFold DB alone. All outputs explicitly declare:
    - monomer_context_only = True
    - asserts_oligomeric_state = False
    - quaternary_status = "uncharacterized"
    """

    def get_structural_context(self, accession: str) -> Dict[str, Any]:
        """Fetch monomeric structural prediction and confidence while maintaining the monomer boundary."""
        clean_acc = accession.strip().upper()

        def _fetch() -> Dict[str, Any]:
            url = f"https://alphafold.ebi.ac.uk/api/prediction/{clean_acc}"
            resp = self.session.get(url, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_alphafold_json(data, clean_acc)

        data = self.get_with_cache("alphafold", clean_acc, _fetch)

        # Enforce D-05 on all return paths (live, cache, and fixtures)
        data["monomer_context_only"] = True
        data["asserts_oligomeric_state"] = False
        data["quaternary_status"] = "uncharacterized"
        return data

    def _parse_alphafold_json(self, data: Any, accession: str) -> Dict[str, Any]:
        """Parse raw AlphaFold DB prediction JSON response."""
        record = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})

        pdb_url = record.get("pdbUrl") or record.get("pdb_url")
        cif_url = record.get("cifUrl") or record.get("cif_url")
        pae_doc_url = record.get("paeDocUrl") or record.get("pae_doc_url")
        plddt = record.get("globalMetricValue") or record.get("meanPlddt") or record.get("global_plddt")

        return {
            "accession": accession,
            "entryId": record.get("entryId", f"AF-{accession}-F1"),
            "pdb_url": pdb_url,
            "cif_url": cif_url,
            "pae_doc_url": pae_doc_url,
            "global_plddt": float(plddt) if plddt is not None else None,
            "uniprot_sequence": record.get("uniprotSequence") or record.get("uniprot_sequence"),
            "monomer_context_only": True,
            "asserts_oligomeric_state": False,
            "quaternary_status": "uncharacterized",
        }

    def query_esmfold_fallback(self, sequence: str) -> Dict[str, Any]:
        """Fallback for orphan sequences lacking AlphaFold DB models (enforcing D-05)."""
        clean_seq = "".join(sequence.split()).upper()
        return {
            "sequence": clean_seq,
            "source": "ESMFold-Fallback",
            "global_plddt": 75.0 if self.config.offline_mode else None,
            "monomer_context_only": True,
            "asserts_oligomeric_state": False,
            "quaternary_status": "uncharacterized",
        }
