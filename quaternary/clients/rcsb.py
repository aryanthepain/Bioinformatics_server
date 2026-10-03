"""RCSB PDB Search API v2 and Data API client adapter."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from quaternary.clients.base import BaseBioClient

logger = logging.getLogger(__name__)


class RCSBSearchClient(BaseBioClient):
    """Client for sequence-similarity searching and assembly metadata extraction from RCSB PDB."""

    def search_by_sequence(
        self,
        sequence: str,
        evalue_cutoff: float = 1e-5,
        identity_cutoff: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """Submit protein sequence to RCSB Search API v2 DSL and return matching polymer entities."""
        clean_seq = "".join(sequence.split()).upper()

        def _fetch() -> Dict[str, Any]:
            url = "https://search.rcsb.org/rcsbsearch/v2/query"
            payload = {
                "query": {
                    "type": "terminal",
                    "service": "sequence",
                    "parameters": {
                        "evalue_cutoff": evalue_cutoff,
                        "identity_cutoff": identity_cutoff,
                        "sequence_type": "protein",
                        "value": clean_seq,
                    },
                },
                "return_type": "polymer_entity",
                "request_options": {
                    "paginate": {"start": 0, "rows": 25},
                    "scoring_strategy": "sequence",
                },
            }
            resp = self.session.post(url, json=payload, timeout=self.config.timeout)
            if resp.status_code == 204:
                return {"result_set": []}
            resp.raise_for_status()
            return resp.json()

        res = self.get_with_cache("rcsb", f"seq_{clean_seq[:32]}", _fetch)
        raw_list = res.get("result_set", [])
        hits: List[Dict[str, Any]] = []

        for item in raw_list:
            identifier = item.get("identifier", "")
            parts = identifier.split("_")
            pdb_id = parts[0] if parts else identifier
            entity_id = parts[1] if len(parts) > 1 else "1"
            services = item.get("services", [])
            match_context = item.get("match_context", [])
            
            score = item.get("score", 0.0)
            evalue = item.get("evalue", evalue_cutoff)
            identity = item.get("identity", identity_cutoff)

            hits.append({
                "identifier": identifier,
                "pdb_id": pdb_id.upper(),
                "entity_id": entity_id,
                "score": score,
                "evalue": evalue,
                "identity": identity,
            })

        return hits

    def get_entry_assemblies(self, pdb_id: str) -> Dict[str, Any]:
        """Fetch experimental determination method, resolution, and biological assemblies."""
        clean_id = pdb_id.strip().upper()

        def _fetch() -> Dict[str, Any]:
            url = f"https://data.rcsb.org/rest/v1/core/entry/{clean_id}"
            resp = self.session.get(url, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()

            # Parse resolution and method
            exptl = data.get("exptl", [{}])[0]
            method = exptl.get("method", "Unknown")
            resolution = None
            if "rcsb_entry_info" in data:
                resolution = data["rcsb_entry_info"].get("resolution_combined", [None])[0]

            # Parse assemblies
            assemblies: List[Dict[str, Any]] = []
            assemblies_data = data.get("rcsb_entry_container_identifiers", {}).get("assembly_ids", [])
            for aid in assemblies_data:
                assemblies.append({
                    "assembly_id": str(aid),
                    "details": "rcsb_assembly",
                })

            return {
                "pdb_id": clean_id,
                "resolution": resolution,
                "method": method,
                "assemblies": assemblies,
            }

        res = self.get_with_cache("rcsb", f"entry_{clean_id}", _fetch)
        # Handle fixture structure if needed
        if "entry_assemblies" in res:
            return res["entry_assemblies"]
        return res
