"""Complex Portal client adapter retrieving curated macromolecular complex stoichiometry."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from quaternary.clients.base import BaseBioClient

logger = logging.getLogger(__name__)


class ComplexPortalClient(BaseBioClient):
    """Client for querying EBI Complex Portal curated complex definitions."""

    def get_complex(self, complex_id: str) -> Dict[str, Any]:
        """Fetch complex name, stoichiometry, and participant components."""
        clean_id = complex_id.strip().upper()

        def _fetch() -> Dict[str, Any]:
            url = f"https://www.ebi.ac.uk/intact/complex-ws/complex/{clean_id}"
            resp = self.session.get(url, headers={"Accept": "application/json"}, timeout=self.config.timeout)
            if resp.status_code == 404:
                return {"complex_id": clean_id, "stoichiometry": "Unknown", "participants": []}
            resp.raise_for_status()
            data = resp.json()
            return self._parse_complex_portal_json(data, clean_id)

        return self.get_with_cache("complex_portal", clean_id, _fetch)

    def _parse_complex_portal_json(self, data: Dict[str, Any], complex_id: str) -> Dict[str, Any]:
        """Extract stoichiometry and participants from Complex Portal JSON."""
        name = data.get("name") or data.get("recommendedName") or complex_id
        systematic_name = data.get("systematicName")
        stoichiometry = data.get("stoichiometry")

        if not stoichiometry and systematic_name:
            import re
            parts = re.findall(r"(\d+)\s*x\s*([A-Za-z0-9_]+)", systematic_name)
            if parts:
                stoichiometry = "".join(f"{chr(65+i)}{count}" for i, (count, _) in enumerate(parts))
            else:
                stoichiometry = systematic_name

        stoichiometry = stoichiometry or "Unknown"

        participants: List[Dict[str, Any]] = []
        raw_participants = data.get("participants", [])
        for p in raw_participants:
            p_id = p.get("identifier") or p.get("accession")
            p_name = p.get("name") or p.get("description")
            p_stoich = p.get("stoichiometry")
            p_role = p.get("role") or p.get("biologicalRole")
            participants.append({
                "identifier": p_id,
                "name": p_name,
                "stoichiometry": p_stoich,
                "role": p_role,
            })

        return {
            "complex_id": complex_id,
            "name": name,
            "systematic_name": systematic_name,
            "stoichiometry": stoichiometry,
            "participants": participants,
        }
