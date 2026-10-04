"""The data contract shared by the backend and the frontend.

Every structural level (primary, secondary, tertiary, quaternary) reports
its findings in exactly the same shape: a LevelResult. The frontend only
knows how to draw that shape. A new or changed analysis module therefore
only has to translate its own output into a LevelResult, and the interface
keeps working without any changes.

See docs/LEVEL_CONTRACT.md for a field-by-field guide with an example.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# --- Vocabulary ----------------------------------------------------------------

LevelKey = Literal["primary", "secondary", "tertiary", "quaternary"]
LEVEL_KEYS: tuple[LevelKey, ...] = ("primary", "secondary", "tertiary", "quaternary")

# Status of one step (a structural level, or the final integration step).
StepStatus = Literal["pending", "running", "completed", "failed", "skipped", "cancelled"]

# Status of a whole analysis job.
JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]

# "live" = produced by a real analysis module, "placeholder" = stand-in data.
DataSource = Literal["live", "placeholder"]

# How a residue-map track is drawn:
#   blocks = labelled regions (e.g. domains)
#   states = a continuous colour strip covering every residue (e.g. helix/strand/coil)
#   marks  = thin markers at specific positions (e.g. interface residues)
TrackStyle = Literal["blocks", "states", "marks"]

# Named colours from the design system. Modules choose a tone, never a hex
# code, so every level automatically matches the rest of the interface.
Tone = Literal[
    "accent",
    "ink",
    "neutral",
    "helix",
    "strand",
    "coil",
    "uncertain",
    "confidence-very-high",
    "confidence-high",
    "confidence-low",
    "confidence-very-low",
]

Polarity = Literal["positive", "negative", "neutral"]
SupportState = Literal["supports", "neutral", "contradicts", "placeholder", "unavailable"]
ConfidenceTier = Literal["high", "moderate", "low", "undetermined"]
NoteKind = Literal["recommendation", "observation", "caution"]
ColumnAlign = Literal["left", "right"]
GoAspect = Literal["molecular_function", "biological_process", "cellular_component"]


# --- Building blocks of a level result ---------------------------------------


class Headline(BaseModel):
    """The single most important number of a level, shown large on its card."""

    value: str = Field(description="Display-ready value, e.g. '90 / 90' or '84%'.")
    label: str = Field(description="What the value measures, e.g. 'evidence score'.")


class Metric(BaseModel):
    """One labelled fact.

    Metrics without a group appear as large "key figure" tiles; metrics with a
    group are listed under that group's heading (e.g. "Physicochemical").
    """

    label: str
    value: str
    hint: str | None = Field(default=None, description="Optional tooltip text.")
    group: str | None = Field(default=None, description="Heading to list this metric under.")


class EvidenceItem(BaseModel):
    """One line of reasoning, e.g. a passed or failed threshold."""

    polarity: Polarity
    text: str


class Link(BaseModel):
    """An external reference such as a UniProt, Pfam or PDB page."""

    label: str
    url: str


class Segment(BaseModel):
    """A stretch of residues on a residue-map track (1-based, inclusive)."""

    start: int = Field(ge=1, description="First residue, 1-based, inclusive.")
    end: int = Field(ge=1, description="Last residue, 1-based, inclusive.")
    tone: Tone
    label: str | None = None


class LegendItem(BaseModel):
    label: str
    tone: Tone


class Track(BaseModel):
    """One row of the residue map."""

    key: str
    label: str = Field(description="Row title, e.g. 'Domains'.")
    caption: str = Field(description="Small text under the title, e.g. 'Primary · Pfam'.")
    style: TrackStyle
    segments: list[Segment] = Field(default_factory=list)
    legend: list[LegendItem] = Field(default_factory=list)
    overview: bool = Field(
        default=True,
        description="Show on the combined residue map (False = only in the level's own section).",
    )


class TableColumn(BaseModel):
    key: str = Field(description="The key used for this column in each row.")
    label: str
    align: ColumnAlign = "left"
    mono: bool = Field(default=False, description="Monospaced, for identifiers and numbers.")


class Table(BaseModel):
    """A small table such as homology hits or structural matches."""

    key: str
    title: str
    caption: str | None = None
    columns: list[TableColumn]
    rows: list[dict[str, str]] = Field(default_factory=list)


class Note(BaseModel):
    """A highlighted piece of advice or interpretation."""

    kind: NoteKind
    title: str
    text: str


class LevelResult(BaseModel):
    """Everything one structural level found, in the shape the UI draws."""

    source: DataSource
    headline: Headline
    summary: str = Field(description="One or two plain-language sentences.")
    metrics: list[Metric] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    tracks: list[Track] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    notes: list[Note] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    raw: dict[str, Any] | None = Field(
        default=None,
        description="The module's original output, included in JSON exports.",
    )


class LevelReport(BaseModel):
    """Progress and result of one structural level within a job."""

    key: LevelKey
    title: str
    tools: list[str] = Field(default_factory=list)
    status: StepStatus = "pending"
    message: str | None = Field(default=None, description="Live progress or error text.")
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: LevelResult | None = None


# --- The integrated answer ---------------------------------------------------------


class GoTerm(BaseModel):
    id: str = Field(description="Gene Ontology identifier, e.g. 'GO:0004674'.")
    term: str
    aspect: GoAspect


class LevelSupport(BaseModel):
    key: LevelKey
    state: SupportState


class Verdict(BaseModel):
    """The final predicted function, combining all levels."""

    source: DataSource
    function: str
    description: str
    confidence_tier: ConfidenceTier
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    go_terms: list[GoTerm] = Field(default_factory=list)
    level_support: list[LevelSupport] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


# --- Jobs ---------------------------------------------------------------------------


class QueryInfo(BaseModel):
    name: str
    sequence: str
    length: int


class AnalysisJob(BaseModel):
    """The full state of one analysis; the frontend polls for this."""

    id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    query: QueryInfo
    levels: list[LevelReport]
    verdict_status: StepStatus = "pending"
    verdict: Verdict | None = None
    error: str | None = None


# --- Requests and other responses ------------------------------------------------


class AnalysisRequest(BaseModel):
    sequence: str = Field(
        min_length=1,
        max_length=50_000,
        description="A raw amino-acid sequence or a single FASTA record.",
    )
    name: str | None = Field(default=None, max_length=80)


class ExampleSequence(BaseModel):
    key: str
    name: str
    organism: str
    reference: str
    sequence: str
    length: int


class HealthResponse(BaseModel):
    status: str
    version: str
    live_levels: list[LevelKey] = Field(default_factory=list)
