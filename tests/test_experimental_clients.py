"""Unit tests for primary and experimental quaternary clients and async polling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
import requests

from quaternary.clients import (
    BaseBioClient,
    ComplexPortalClient,
    PisaClient,
    RCSBSearchClient,
    UniProtClient,
)
from quaternary.config import QuaternaryConfig


# ==========================================
# BaseBioClient & HTTP 303 Tests
# ==========================================

def test_base_bio_client_session_setup() -> None:
    cfg = QuaternaryConfig(max_retries=4, backoff_factor=0.5)
    client = BaseBioClient(cfg)
    assert client.session is not None
    # Verify adapters mounted
    assert "https://" in client.session.adapters
    assert "http://" in client.session.adapters


def test_poll_async_job_http_303_redirect_interception() -> None:
    """Verifies Roadblock 2 resolution: HTTP 303 is intercepted with allow_redirects=False and target Location is queried."""
    cfg = QuaternaryConfig(timeout=5.0)
    client = BaseBioClient(cfg)

    # Mock response 1: HTTP 303 See Other with Location header
    resp_303 = MagicMock(spec=requests.Response)
    resp_303.status_code = 303
    resp_303.headers = {"Location": "https://rest.uniprot.org/results/job_final_result"}

    # Mock response 2: HTTP 200 with result payload
    resp_200 = MagicMock(spec=requests.Response)
    resp_200.status_code = 200
    resp_200.json.return_value = {"job_id": "test_123", "status": "COMPLETED", "data": [1, 2, 3]}
    resp_200.raise_for_status = MagicMock()

    with patch.object(client.session, "get") as mock_get:
        mock_get.side_effect = [resp_303, resp_200]

        result = client.poll_async_job("https://rest.uniprot.org/status/job_123", timeout_sec=10)

        assert result["status"] == "COMPLETED"
        assert result["data"] == [1, 2, 3]

        # Verify allow_redirects=False was used on status_url
        mock_get.assert_any_call(
            "https://rest.uniprot.org/status/job_123",
            allow_redirects=False,
            timeout=5.0,
        )
        # Verify Location header was fetched
        mock_get.assert_any_call(
            "https://rest.uniprot.org/results/job_final_result",
            timeout=5.0,
        )


def test_poll_async_job_running_then_303() -> None:
    """Simulates job running, then 303 redirect."""
    cfg = QuaternaryConfig(timeout=5.0)
    client = BaseBioClient(cfg)

    resp_running = MagicMock(spec=requests.Response)
    resp_running.status_code = 200
    resp_running.json.return_value = {"jobStatus": "RUNNING"}

    resp_303 = MagicMock(spec=requests.Response)
    resp_303.status_code = 303
    resp_303.headers = {"Location": "https://rest.uniprot.org/results/final"}

    resp_final = MagicMock(spec=requests.Response)
    resp_final.status_code = 200
    resp_final.json.return_value = {"results": ["hit1", "hit2"]}
    resp_final.raise_for_status = MagicMock()

    with patch.object(client.session, "get") as mock_get:
        mock_get.side_effect = [resp_running, resp_303, resp_final]

        result = client.poll_async_job("https://rest.uniprot.org/status/job_123", timeout_sec=10, poll_interval=0.01)
        assert "results" in result


def test_poll_async_job_timeout() -> None:
    cfg = QuaternaryConfig(timeout=0.1)
    client = BaseBioClient(cfg)

    resp_running = MagicMock(spec=requests.Response)
    resp_running.status_code = 200
    resp_running.json.return_value = {"jobStatus": "RUNNING"}

    with patch.object(client.session, "get", return_value=resp_running):
        with pytest.raises(TimeoutError):
            client.poll_async_job("https://rest.uniprot.org/status/job_123", timeout_sec=0.05, poll_interval=0.01)


# ==========================================
# Primary & Experimental Client Tests (Offline Mode)
# ==========================================

def test_uniprot_client_offline_fixture() -> None:
    cfg = QuaternaryConfig(offline_mode=True)
    client = UniProtClient(cfg)
    res = client.get_subunit_annotations("P0A6F5")

    assert res["accession"] == "P0A6F5"
    assert "Tetradecamer" in res["subunit_text"]
    assert "1GFL" in res["pdb_ids"]
    assert "CPX-1882" in res["complex_portal_ids"]
    assert res["organism"] == "Escherichia coli (strain K12)"


def test_complex_portal_client_offline_fixture() -> None:
    cfg = QuaternaryConfig(offline_mode=True)
    client = ComplexPortalClient(cfg)
    res = client.get_complex("CPX-1882")

    assert res["complex_id"] == "CPX-1882"
    assert res["stoichiometry"] == "A14B7"
    assert len(res["participants"]) == 2
    identifiers = [p["identifier"] for p in res["participants"]]
    assert "P0A6F5" in identifiers


def test_rcsb_search_client_offline_fixture() -> None:
    cfg = QuaternaryConfig(offline_mode=True)
    client = RCSBSearchClient(cfg)

    # Sequence search
    hits = client.search_by_sequence("MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHG")
    assert len(hits) >= 1
    assert hits[0]["pdb_id"] == "1GFL"

    # Entry assemblies
    entry = client.get_entry_assemblies("1GFL")
    assert entry["pdb_id"] == "1GFL"
    assert entry["resolution"] == 2.4
    assert len(entry["assemblies"]) >= 1


def test_pisa_client_offline_fixture() -> None:
    cfg = QuaternaryConfig(offline_mode=True)
    client = PisaClient(cfg)
    res = client.get_assembly_interfaces("1GFL")

    assert res["pdb_id"] == "1GFL"
    assert res["dissociation_energy_kcal_mol"] == -124.5
    assert res["status"] == "stable"
    assert len(res["interfaces"]) >= 1
    iface = res["interfaces"][0]
    assert iface["buried_surface_area_angstrom2"] == 2150.0
    assert iface["hydrogen_bonds_count"] == 12
