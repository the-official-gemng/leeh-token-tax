"""
harness/router.py -- Efficient-Language Router

Given a harness.detector.DetectionResult, decides whether reasoning should
be routed through English before answering.

Policy (as specified when this harness was commissioned -- there's no
separate docs/ design doc beyond that; see detector.py's docstring for the
same note):
  - English input -> passthrough, no intervention.
  - Non-English input -> route through English, for BOTH single_turn and
    agentic tasks. task_type doesn't currently change the routing outcome;
    it's carried through the decision anyway for downstream modules
    (Packer/Executor need it) and for logging, since a future policy could
    plausibly split single_turn vs. agentic differently.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from harness.detector import DetectionResult

ROOT = Path(__file__).resolve().parent.parent
_PHASE1_COST_RATIOS_CSV = ROOT / "results" / "phase1_cost_ratios.csv"


@dataclass
class RouteDecision:
    route_through_english: bool
    original_language: str
    task_type: str


def route(detection: DetectionResult) -> RouteDecision:
    return RouteDecision(
        route_through_english=detection.language != "en",
        original_language=detection.language,
        task_type=detection.task_type,
    )


def _load_phase1_ci_high() -> dict:
    """Returns {(model, language): ci_high} from Phase 1's own measured
    cost-ratio CIs (results/phase1_cost_ratios.csv). Empty dict (never
    skip) if that file doesn't exist yet -- same fallback philosophy as
    harness/equalizer.py's fertility-multiplier lookup: an unmeasured or
    missing case should never silently gate behavior, only a measured
    one should."""
    if not _PHASE1_COST_RATIOS_CSV.exists():
        return {}
    df = pd.read_csv(_PHASE1_COST_RATIOS_CSV)
    return {(row["model"], row["language"]): float(row["ci_high"]) for _, row in df.iterrows()}


_PHASE1_CI_HIGH = _load_phase1_ci_high()


def should_skip_intervention(model_name: str, language: str, threshold: float = 1.2) -> bool:
    """First-pass definition of the "Router low-tax-skip" idea (recorded
    as a forward-looking point in docs/phase4_writing_reference.md
    Section A, not previously implemented): skip intervention entirely
    for a (model, language) pair whose own Phase 1 baseline cost-ratio CI
    upper bound already clears the same 1.2x target C2 was built to hit
    -- there's nothing to fix for that pair. Falls back to False (don't
    skip -- intervene) for any (model, language) Phase 1 didn't measure,
    rather than guessing. Used only by C4 (harness/conditions.py's
    run_c4()); C0/C1/C2/C3a's existing route() above is untouched by
    this -- none of them call this function."""
    ci_high = _PHASE1_CI_HIGH.get((model_name, language))
    if ci_high is None:
        return False
    return ci_high <= threshold
