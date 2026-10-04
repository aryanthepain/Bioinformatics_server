"""IntAct client adapter retrieving physical protein interaction partners."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from quaternary.clients.base import BaseBioClient

logger = logging.getLogger(__name__)

PHYSICAL_INTERACTION_KEYWORDS = (
    "physical",
    "direct",
    "association",
    "binding",
    "covalent",
    "enzymatic",
    "complex",
)

EXCLUDED_GENETIC_KEYWORDS = (
    "genetic",
    "synthetic",
    "suppression",
    "lethality",
)


class IntActClient(BaseBioClient):
    """Client for querying IntAct molecular interactions and filtering candidate physical partners."""

    def get_physical_interactors(self, accession: str) -> List[Dict[str, Any]]:
        """Fetch and filter physical protein interactors for candidate heteromer analysis."""
        clean_acc = accession.strip().upper()

        def _fetch() -> Dict[str, Any]:
            # Use IntAct REST interactor search
            url = f"https://www.ebi.ac.uk/intact/ws/interaction/findInteractions/{clean_acc}"
            try:
                import requests as direct_requests
                resp = direct_requests.get(url, timeout=3.0)
                if resp.status_code == 404:
                    return {"interactors": []}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.warning(f"IntAct API fetch failed or timed out for {clean_acc}: {e}")
                return {"interactors": []}

        data = self.get_with_cache("intact", clean_acc, _fetch)
        raw_interactors = data.get("interactors", [])

        # Parse and filter physical interactions
        physical_partners: List[Dict[str, Any]] = []
        seen_partners = set()

        for item in raw_interactors:
            p_acc = item.get("partner_accession", "")
            if not p_acc or p_acc == clean_acc:
                continue
            if p_acc in seen_partners:
                continue

            itype = str(item.get("interaction_type", "")).lower()
            # Discard genetic synthetics
            if any(k in itype for k in EXCLUDED_GENETIC_KEYWORDS):
                continue
            # Must match physical criteria
            if not any(k in itype for k in PHYSICAL_INTERACTION_KEYWORDS):
                continue

            seen_partners.add(p_acc)
            physical_partners.append({
                "partner_accession": p_acc,
                "gene_name": item.get("gene_name"),
                "interaction_type": item.get("interaction_type", "physical association"),
                "confidence": float(item.get("confidence", 0.5)),
            })

        return physical_partners
