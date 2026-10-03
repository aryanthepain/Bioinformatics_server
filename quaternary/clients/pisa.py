"""PDBe PISA client adapter retrieving assembly thermodynamics and interface interactions."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from quaternary.clients.base import BaseBioClient

logger = logging.getLogger(__name__)


class PisaClient(BaseBioClient):
    """Client for querying PDBe PISA thermodynamic assembly stability and interface chemistry."""

    def get_assembly_interfaces(
        self,
        pdb_id: str,
        assembly_id: Optional[str] = "1",
    ) -> Dict[str, Any]:
        """Fetch macromolecular assembly thermodynamics, dissociation delta_g, and interface contacts."""
        clean_id = pdb_id.strip().lower()
        target_asm = str(assembly_id or "1")

        def _fetch() -> Dict[str, Any]:
            url = f"https://www.ebi.ac.uk/pdbe/api/pisa/assembly/{clean_id}"
            resp = self.session.get(url, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()
            return self._parse_pisa_json(data, clean_id, target_asm)

        return self.get_with_cache("pisa", f"{clean_id}_{target_asm}", _fetch)

    def _parse_pisa_json(
        self,
        data: Dict[str, Any],
        pdb_id: str,
        assembly_id: str,
    ) -> Dict[str, Any]:
        """Extract biophysical and interface parameters from PISA API JSON."""
        # Check if fixture format
        if "dissociation_energy_kcal_mol" in data and "interfaces" in data:
            return data

        entry_data = data.get(pdb_id, {})
        assemblies = entry_data.get("assemblies", [])

        selected_asm = None
        for a in assemblies:
            if str(a.get("assembly_id")) == assembly_id:
                selected_asm = a
                break
        if not selected_asm and assemblies:
            selected_asm = assemblies[0]

        if not selected_asm:
            return {
                "pdb_id": pdb_id.upper(),
                "assembly_id": assembly_id,
                "macromolecular_size": 1,
                "composition": "A",
                "dissociation_energy_kcal_mol": 0.0,
                "accessible_surface_area_angstrom2": 0.0,
                "buried_surface_area_angstrom2": 0.0,
                "status": "unknown",
                "interfaces": [],
            }

        delta_g = selected_asm.get("dissociation_energy", selected_asm.get("delta_g", 0.0))
        status = "stable" if delta_g < 0 else "dissociated/lattice"
        interfaces_raw = selected_asm.get("interfaces", [])
        interfaces: List[Dict[str, Any]] = []

        for iface in interfaces_raw:
            interfaces.append({
                "chain_1": iface.get("chain1", iface.get("chain_1", "A")),
                "chain_2": iface.get("chain2", iface.get("chain_2", "B")),
                "buried_surface_area_angstrom2": float(iface.get("bsa", iface.get("buried_surface_area_angstrom2", 0.0))),
                "solvation_free_energy_kcal_mol": float(iface.get("delta_g", iface.get("solvation_free_energy_kcal_mol", 0.0))),
                "hydrogen_bonds_count": int(iface.get("h_bonds", iface.get("hydrogen_bonds_count", 0))),
                "salt_bridges_count": int(iface.get("salt_bridges", iface.get("salt_bridges_count", 0))),
                "interface_residues_chain_1": iface.get("interface_residues_chain_1", []),
                "interface_residues_chain_2": iface.get("interface_residues_chain_2", []),
            })

        return {
            "pdb_id": pdb_id.upper(),
            "assembly_id": str(selected_asm.get("assembly_id", assembly_id)),
            "macromolecular_size": int(selected_asm.get("macromolecular_size", 1)),
            "composition": selected_asm.get("composition", "A"),
            "dissociation_energy_kcal_mol": float(delta_g),
            "accessible_surface_area_angstrom2": float(selected_asm.get("asa", 0.0)),
            "buried_surface_area_angstrom2": float(selected_asm.get("bsa", 0.0)),
            "status": status,
            "interfaces": interfaces,
        }
