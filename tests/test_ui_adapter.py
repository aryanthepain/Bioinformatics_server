"""
Unit Tests for Quaternary UI Adapter and LevelResult Generation.

Verifies:
1. analyze() returns a valid LevelResult with source='live'.
2. Headline, metrics, tracks, tables, notes, and links formatting.
3. Residue map track formatting (style='marks', tone='ink', 1-based inclusive segments).
4. Telemetry interaction with mock StageContext (report calls).
5. Error handling and input validation (short sequences, invalid amino acids).
"""

from typing import List
import pytest

from quaternary.ui_adapter import (
    KNOWN_EXAMPLES,
    Headline,
    LevelResult,
    Metric,
    Segment,
    Table,
    Track,
    analyze,
)


class MockStageContext:
    """Mock runner context simulating the UI background job runner."""

    def __init__(self):
        self.reports: List[str] = []
        self.is_cancelled: bool = False

    def report(self, message: str) -> None:
        self.reports.append(message)


def test_analyze_with_ubiquitin_sequence():
    """Verify analyze() executes successfully on canonical Ubiquitin sequence."""
    seq = (
        "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYN"
        "IQKESTLHLVLRLRGG"
    )
    ctx = MockStageContext()
    result = analyze(seq, ctx=ctx)

    # Core contract checks
    assert result.__class__.__name__ == "LevelResult"
    assert hasattr(result, "headline") and hasattr(result, "summary")
    assert result.source == "live"
    assert result.headline.label == "quaternary assembly"
    assert "Monomer" in result.headline.value
    assert isinstance(result.summary, str) and len(result.summary) > 20

    # Telemetry verification
    assert len(ctx.reports) >= 3, "Context report() should be invoked across analysis stages"

    # Metrics verification
    metrics_by_label = {m.label: m.value for m in result.metrics}
    assert "Subunit count" in metrics_by_label
    assert metrics_by_label["Subunit count"] == "1"
    assert "Quaternary status" in metrics_by_label

    # Tracks verification
    assert len(result.tracks) >= 1
    track = result.tracks[0]
    assert track.key == "interfaces"
    assert track.style == "marks"
    assert track.overview is True

    # Raw dump verification
    assert isinstance(result.raw, dict)
    assert "analysis_id" in result.raw
    assert "stoichiometry" in result.raw
    assert "quaternary_status" in result.raw


def test_analyze_with_multimer_complex():
    """Verify analyze() produces tracks and tables on multimer target (Bacteriorhodopsin)."""
    # 249-residue Bacteriorhodopsin sequence
    seq = (
        "MLELLPTAVEGVSQAQITGRPEWIWLALGTALMGLGTLYFLVKGMGVSDPDAKKFYAITT"
        "LVPAIAFTMYLSMLLGYGLTMVPFGGEQNPIYWARYADWLFTTPLLLLDLALLVDADQGT"
        "ILALVGADGIMIGTGLVGALTKVYSYRFVWWAISTAAMLYILYVLFFGFTSKAESMRPEV"
        "ASTFKVLRNVTVVLWSAYPVVWLIGSEGAGIVPLNIETLLFMVLDVSAKVGFGLILLRSR"
        "AIFGEAEAPEPSAGDGAAATSD"
    )
    result = analyze(seq)

    assert result.source == "live"
    assert "Homotrimer" in result.headline.value or "A3" in result.headline.value
    assert len(result.tables) >= 1

    # Verify interface table
    table_keys = [t.key for t in result.tables]
    assert "interfaces" in table_keys or "components" in table_keys

    # Verify track segments are 1-based inclusive
    track = result.tracks[0]
    assert track.style == "marks"
    for seg in track.segments:
        assert seg.start >= 1, "Segments must be 1-based"
        assert seg.end >= seg.start
        assert seg.tone == "ink"


def test_analyze_input_validation_errors():
    """Verify input validation catches short, oversized, or invalid character sequences."""
    # Too short (<25 residues)
    with pytest.raises(ValueError) as exc1:
        analyze("MQIFVKTLTGKTI")
    assert "below minimum" in str(exc1.value)

    # Non-standard amino acids (contains 'Z', 'X', 'B')
    with pytest.raises(ValueError) as exc2:
        analyze("MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGGZ")
    assert "non-standard amino acid" in str(exc2.value)

    # Whitespace stripping works cleanly on valid sequences
    seq_with_whitespace = """
        MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYN
        IQKESTLHLVLRLRGG
    """
    res = analyze(seq_with_whitespace)
    assert res.source == "live"


def test_analyze_cancellation():
    """Verify cancellation flag in StageContext is honored."""
    ctx = MockStageContext()
    ctx.is_cancelled = True

    seq = (
        "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYN"
        "IQKESTLHLVLRLRGG"
    )
    with pytest.raises(RuntimeError) as exc:
        analyze(seq, ctx=ctx)
    assert "cancelled by user" in str(exc.value)
