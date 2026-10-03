"""UniProtKB client adapter retrieving subunit annotations and structural cross-references."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from quaternary.clients.base import BaseBioClient

logger = logging.getLogger(__name__)


class UniProtClient(BaseBioClient):
    """Client for querying UniProtKB protein records and extracting quaternary annotations."""

    def get_subunit_annotations(self, accession: str) -> Dict[str, Any]:
        """Fetch subunit annotation, gene name, organism, and PDB/ComplexPortal cross-references."""
        clean_acc = accession.strip().upper()

        def _fetch() -> Dict[str, Any]:
            url = f"https://rest.uniprot.org/uniprotkb/{clean_acc}.json"
            resp = self.session.get(url, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_uniprot_json(data, clean_acc)

        return self.get_with_cache("uniprot", clean_acc, _fetch)

    def _parse_uniprot_json(self, data: Dict[str, Any], accession: str) -> Dict[str, Any]:
        """Extract quaternary fields from raw UniProt REST JSON."""
        # 1. Gene name
        gene_name = None
        genes = data.get("genes", [])
        if genes and isinstance(genes, list):
            gene_name = genes[0].get("geneName", {}).get("value")

        # 2. Organism
        org_data = data.get("organism", {})
        organism_name = org_data.get("scientificName", "Unknown organism")
        taxon_id = org_data.get("taxonId")

        # 3. Subunit comments
        comments = data.get("comments", [])
        subunit_texts: List[str] = []
        for c in comments:
            if c.get("commentType") == "SUBUNIT":
                texts = c.get("texts", [])
                for t in texts:
                    val = t.get("value") if isinstance(t, dict) else str(t)
                    if val:
                        subunit_texts.append(val)

        subunit_text = " ".join(subunit_texts) if subunit_texts else "No subunit annotation found."

        # 4. Cross references
        pdb_ids: List[str] = []
        complex_portal_ids: List[str] = []
        xrefs = data.get("uniProtKBCrossReferences", [])
        for xref in xrefs:
            db = xref.get("database")
            x_id = xref.get("id")
            if not x_id:
                continue
            if db == "PDB" and x_id not in pdb_ids:
                pdb_ids.append(x_id)
            elif db == "ComplexPortal" and x_id not in complex_portal_ids:
                complex_portal_ids.append(x_id)

        return {
            "accession": accession,
            "gene_name": gene_name,
            "organism": organism_name,
            "taxonomy_id": taxon_id,
            "subunit_text": subunit_text,
            "pdb_ids": pdb_ids,
            "complex_portal_ids": complex_portal_ids,
            "raw_comments": subunit_texts,
        }
