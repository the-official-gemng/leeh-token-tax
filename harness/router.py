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

from harness.detector import DetectionResult


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
