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
            url = f"https://www.ebi.ac.uk/pdbe/api/pisa/interfaces/{clean_id}/{target_asm}"
            resp = self.session.get(url, timeout=self.config.timeout)
            if resp.status_code == 404:
                url_asm = f"https://www.ebi.ac.uk/pdbe/api/pisa/assembly/{clean_id}/{target_asm}"
                resp = self.session.get(url_asm, timeout=self.config.timeout)
                if resp.status_code == 404:
                    return {
                        "pdb_id": clean_id.upper(),
                        "assembly_id": target_asm,
                        "macromolecular_size": 1,
                        "composition": "A",
                        "dissociation_energy_kcal_mol": 0.0,
                        "accessible_surface_area_angstrom2": 0.0,
                        "buried_surface_area_angstrom2": 0.0,
                        "status": "unknown",
                        "interfaces": [],
                    }
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
        if not isinstance(entry_data, dict):
            entry_data = {}

        selected_asm = entry_data.get("assembly")
        if not selected_asm:
            assemblies = entry_data.get("assemblies", [])
            for a in assemblies:
                if str(a.get("assembly_id") or a.get("id")) == assembly_id:
                    selected_asm = a
                    break
            if not selected_asm and assemblies:
                selected_asm = assemblies[0]

        if not selected_asm or not isinstance(selected_asm, dict):
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

        delta_g = float(selected_asm.get("dissociation_energy", selected_asm.get("delta_g", 0.0)) or 0.0)
        status = "stable" if (delta_g > 0 or delta_g < -10) else "dissociated/lattice"
        interfaces_raw = selected_asm.get("interfaces", [])
        interfaces: List[Dict[str, Any]] = []

        for iface in interfaces_raw:
            molecules = iface.get("molecules", [])
            c1 = molecules[0].get("chain_id", "A") if len(molecules) >= 1 else iface.get("chain1", iface.get("chain_1", "A"))
            c2 = molecules[1].get("chain_id", "B") if len(molecules) >= 2 else iface.get("chain2", iface.get("chain_2", "B"))
            bsa = float(iface.get("interface_area", iface.get("bsa", iface.get("buried_surface_area_angstrom2", 0.0))) or 0.0)
            solv_g = float(iface.get("solvation_energy", iface.get("delta_g", iface.get("solvation_free_energy_kcal_mol", 0.0))) or 0.0)
            hb = int(iface.get("number_hydrogen_bonds", iface.get("h_bonds", iface.get("hydrogen_bonds_count", 0))) or 0)
            sb = int(iface.get("number_salt_bridges", iface.get("salt_bridges", iface.get("salt_bridges_count", 0))) or 0)

            # Extract interface residues with buried surface area > 0
            res1: List[int] = []
            res2: List[int] = []
            if len(molecules) >= 1:
                m1 = molecules[0]
                seq_ids1 = m1.get("residue_seq_ids") or m1.get("residue_label_seq_ids") or []
                bsas1 = m1.get("buried_surface_areas", [])
                for idx, b in enumerate(bsas1):
                    if b > 0 and idx < len(seq_ids1):
                        try:
                            res1.append(int(seq_ids1[idx]))
                        except (ValueError, TypeError):
                            pass
            if len(molecules) >= 2:
                m2 = molecules[1]
                seq_ids2 = m2.get("residue_seq_ids") or m2.get("residue_label_seq_ids") or []
                bsas2 = m2.get("buried_surface_areas", [])
                for idx, b in enumerate(bsas2):
                    if b > 0 and idx < len(seq_ids2):
                        try:
                            res2.append(int(seq_ids2[idx]))
                        except (ValueError, TypeError):
                            pass

            if not res1 and iface.get("interface_residues_chain_1"):
                for r in iface["interface_residues_chain_1"]:
                    try:
                        res1.append(int(r))
                    except (ValueError, TypeError):
                        pass
            if not res2 and iface.get("interface_residues_chain_2"):
                for r in iface["interface_residues_chain_2"]:
                    try:
                        res2.append(int(r))
                    except (ValueError, TypeError):
                        pass

            interfaces.append({
                "chain_1": c1,
                "chain_2": c2,
                "buried_surface_area_angstrom2": bsa,
                "solvation_free_energy_kcal_mol": solv_g,
                "hydrogen_bonds_count": hb,
                "salt_bridges_count": sb,
                "interface_residues_chain_1": res1,
                "interface_residues_chain_2": res2,
            })

        mmsize = selected_asm.get("mmsize") or selected_asm.get("macromolecular_size") or 1
        return {
            "pdb_id": pdb_id.upper(),
            "assembly_id": str(selected_asm.get("assembly_id", assembly_id)),
            "macromolecular_size": int(mmsize),
            "composition": selected_asm.get("composition", "A"),
            "dissociation_energy_kcal_mol": float(delta_g),
            "accessible_surface_area_angstrom2": float(selected_asm.get("accessible_surface_area", selected_asm.get("asa", 0.0)) or 0.0),
            "buried_surface_area_angstrom2": float(selected_asm.get("buried_surface_area", selected_asm.get("bsa", 0.0)) or 0.0),
            "status": status,
            "interfaces": interfaces,
        }
