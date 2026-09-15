"""
harness/detector.py -- Language & Task Detector

Given a raw prompt, detects:
  - language: ISO 639-1 code, normalized to match the codes used throughout
    this project (Phase 1's data/results use 'en'/'es'/'ar'/'zh')
  - task_type: 'single_turn' or 'agentic'

Deliberately lightweight, per spec ("don't overbuild this"):
  - language detection uses `langdetect` (statistical n-gram model, no API
    call, no training) rather than an LLM call or a custom classifier.
  - task-type detection is a cheap keyword heuristic, not a classifier --
    Phase 3's conditions.py already knows the source dataset for every task
    it feeds through the harness (MGSM -> single_turn, MAPS -> agentic) and
    should pass that via `task_type_hint` rather than rely on the heuristic.
    The heuristic exists only for callers that don't already know.
"""

from dataclasses import dataclass
from typing import Optional

from langdetect import detect as _langdetect_detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# langdetect is nondeterministic by default (randomized n-gram sampling for
# long text); pin the seed so repeated calls on the same input agree --
# matters for reproducibility given everything else in this project is
# seeded (see SEED in scripts/run_phase1.py).
DetectorFactory.seed = 0

# langdetect returns locale-flavored codes for some languages (e.g. 'zh-cn',
# 'zh-tw') that don't match the plain codes used in Phase 1's data/results
# filenames and CSV columns. Normalize the ones this project actually deals
# with; anything else passes through as langdetect returns it.
_LANG_NORMALIZE = {"zh-cn": "zh", "zh-tw": "zh"}

# Cheap markers for agentic-style tasks (GAIA-like: research/lookup/
# real-world-entity questions) vs. single-turn tasks (MGSM-like: self-
# contained arithmetic word problems). Not a classifier -- a default for
# callers that don't pass task_type_hint.
_AGENTIC_MARKERS = (
    "how many", "what is the name", "according to", "as of", "search",
    "find the", "attached", "file", "spreadsheet", "website", "article",
)


@dataclass
class DetectionResult:
    language: str               # normalized ISO code, e.g. 'en', 'es', 'ar', 'zh'
    task_type: str              # 'single_turn' | 'agentic'
    language_confidence: str    # 'detected' | 'fallback'


def detect_language(text: str) -> tuple:
    """Returns (iso_code, confidence). Falls back to ('en', 'fallback') on
    detection failure (e.g. very short/ambiguous/empty text) rather than
    raising -- a caller mid-conditions-run shouldn't crash on one hard-to-
    detect prompt."""
    try:
        code = _langdetect_detect(text)
        return _LANG_NORMALIZE.get(code, code), "detected"
    except LangDetectException:
        return "en", "fallback"


def detect_task_type(text: str, task_type_hint: Optional[str] = None) -> str:
    if task_type_hint in ("single_turn", "agentic"):
        return task_type_hint
    lower = text.lower()
    return "agentic" if any(m in lower for m in _AGENTIC_MARKERS) else "single_turn"


def detect(prompt: str, task_type_hint: Optional[str] = None) -> DetectionResult:
    language, confidence = detect_language(prompt)
    task_type = detect_task_type(prompt, task_type_hint)
    return DetectionResult(language=language, task_type=task_type, language_confidence=confidence)
