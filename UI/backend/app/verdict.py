"""The integration step: combine the level results into one verdict.

The real aggregation logic depends on what the tertiary and quaternary
modules produce, so for now this builds a clearly marked placeholder:
  * for the built-in example proteins it uses their known function, so
    demos look right;
  * for any other sequence it reports an undetermined function.

It already computes how each level contributed, which the interface shows
as the agreement strip next to the verdict.
"""

from .examples import find_example
from .schemas import AnalysisJob, LevelReport, LevelSupport, SupportState, Verdict


def _support_state(level: LevelReport) -> SupportState:
    if level.status != "completed" or level.result is None:
        return "unavailable"
    if level.result.source == "placeholder":
        return "placeholder"
    return "neutral"  # real modules are connected but not yet weighed


def build_verdict(job: AnalysisJob) -> Verdict:
    support = [LevelSupport(key=level.key, state=_support_state(level)) for level in job.levels]
    reported = sum(1 for item in support if item.state != "unavailable")
    coverage_note = f"{reported} of {len(support)} structural levels returned results."

    example = find_example(job.query.sequence)
    if example is not None:
        return Verdict(
            source="placeholder",
            function=example.function,
            description=example.description,
            confidence_tier="high",
            confidence_score=0.9,
            go_terms=[term.model_copy() for term in example.go_terms],
            level_support=support,
            rationale=[
                "Placeholder verdict: this is a built-in example with a known function.",
                coverage_note,
                "Evidence integration will replace this once all four modules are connected.",
            ],
        )

    return Verdict(
        source="placeholder",
        function="Function not yet determined",
        description=(
            "The integrated prediction will appear here once the analysis modules "
            "are connected."
        ),
        confidence_tier="undetermined",
        confidence_score=None,
        go_terms=[],
        level_support=support,
        rationale=[
            "Placeholder verdict: evidence integration is not implemented yet.",
            coverage_note,
        ],
    )
