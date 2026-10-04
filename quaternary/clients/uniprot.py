"""UniProtKB client adapter retrieving subunit annotations and structural cross-references."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from quaternary.clients.base import BaseBioClient

logger = logging.getLogger(__name__)


class UniProtClient(BaseBioClient):
    """Client for querying UniProtKB protein records and extracting quaternary annotations."""

    # Strict standard UniProt accession regex without commas (enforcing D-16)
    ACCESSION_REGEX = re.compile(
        r"^[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9])([A-Z][A-Z0-9]{2}[0-9])?$"
    )

    @classmethod
    def is_valid_accession(cls, accession: str) -> bool:
        """Validate string against canonical UniProtKB accession grammar."""
        clean_acc = accession.strip().upper()
        return bool(cls.ACCESSION_REGEX.fullmatch(clean_acc))

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
        function_texts: List[str] = []

        for c in comments:
            c_type = c.get("commentType")
            if c_type == "SUBUNIT":
                texts = c.get("texts", [])
                for t in texts:
                    val = t.get("value") if isinstance(t, dict) else str(t)
                    if val:
                        subunit_texts.append(val)
            elif c_type in ("FUNCTION", "CATALYTIC_ACTIVITY"):
                texts = c.get("texts", [])
                for t in texts:
                    val = t.get("value") if isinstance(t, dict) else str(t)
                    if val:
                        function_texts.append(val)

        subunit_text = " ".join(subunit_texts) if subunit_texts else "No subunit annotation found."
        function_text = " ".join(function_texts) if function_texts else ""

        # 4. Cross references & GO Terms
        pdb_ids: List[str] = []
        complex_portal_ids: List[str] = []
        go_terms: List[Dict[str, str]] = []
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
            elif db == "GO":
                props = {p.get("key"): p.get("value") for p in xref.get("properties", []) if isinstance(p, dict)}
                term_name = props.get("GoTerm", "")
                go_terms.append({"id": x_id, "name": term_name})

        # 5. Canonical Sequence
        seq_data = data.get("sequence", {})
        sequence = seq_data.get("value") if isinstance(seq_data, dict) else (seq_data if isinstance(seq_data, str) else None)

        return {
            "accession": accession,
            "gene_name": gene_name,
            "organism": organism_name,
            "taxonomy_id": taxon_id,
            "subunit_text": subunit_text,
            "function_text": function_text,
            "go_terms": go_terms,
            "pdb_ids": pdb_ids,
            "complex_portal_ids": complex_portal_ids,
            "raw_comments": subunit_texts,
            "sequence": sequence,
        }
