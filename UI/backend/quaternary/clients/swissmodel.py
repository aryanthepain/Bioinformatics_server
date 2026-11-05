"""SWISS-MODEL Repository client adapter retrieving homology models and oligomeric templates."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from quaternary.clients.base import BaseBioClient

logger = logging.getLogger(__name__)


class SwissModelClient(BaseBioClient):
    """Client for querying SWISS-MODEL precomputed homology models and template oligomeric states."""

    def get_homology_models(self, accession: str) -> List[Dict[str, Any]]:
        """Fetch precomputed homology models for target UniProt accession."""
        clean_acc = accession.strip().upper()

        def _fetch() -> Dict[str, Any]:
            url = f"https://swissmodel.expasy.org/repository/uniprot/{clean_acc}.json"
            resp = self.session.get(url, timeout=self.config.timeout)
            if resp.status_code == 404:
                return {"result": []}
            resp.raise_for_status()
            return resp.json()

        data = self.get_with_cache("swissmodel", clean_acc, _fetch)
        raw_models: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            res = data.get("result", {})
            if isinstance(res, dict):
                raw_models = res.get("structures", [])
            elif isinstance(res, list):
                raw_models = res
            elif "structures" in data:
                raw_models = data.get("structures", [])
        elif isinstance(data, list):
            raw_models = data

        parsed_models: List[Dict[str, Any]] = []
        for m in raw_models:
            if not isinstance(m, dict):
                continue
            tpl = m.get("template", "")
            tpl_pdb = m.get("template_pdb_id") or (tpl.split(".")[0].upper() if tpl else "UNKNOWN")
            oligo = m.get("template_oligomeric_state") or m.get("oligo-state") or "unknown"
            raw_qmqe = m.get("template_qsqe") or m.get("qsqe") or m.get("qmqe")
            qmqe = float(raw_qmqe) if raw_qmqe is not None else 0.0
            raw_gmqe = m.get("gmqe")
            gmqe = float(raw_gmqe) if raw_gmqe is not None else 0.0
            identity = float(m.get("seq_identity", m.get("identity", 0.0)))
            coverage = float(m.get("coverage", 0.0))

            if m.get("qualifying_homology") is not None:
                qualifying = bool(m.get("qualifying_homology"))
            else:
                qualifying = qmqe >= 0.70 or gmqe >= 0.70

            parsed_models.append({
                "template_pdb_id": tpl_pdb,
                "template_oligomeric_state": oligo,
                "qmqe": qmqe,
                "gmqe": gmqe,
                "seq_identity": identity,
                "coverage": coverage,
                "qualifying_homology": qualifying,
            })

        return parsed_models
