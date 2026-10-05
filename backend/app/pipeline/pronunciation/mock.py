from __future__ import annotations

from pathlib import Path

from ...models import Segment
from ..demo import pronunciation_overrides
from .base import WordPhonemes


class MockPronunciation:
    """Reports the scripted (expected, observed) pairs of the demo scenario; others are clean."""
    name = "mock"

    def __init__(self, overrides: dict[str, tuple[str, str]] | None = None):
        self._ov = overrides if overrides is not None else pronunciation_overrides()

    def analyze(self, wav_path: Path, segments: list[Segment]) -> list[WordPhonemes]:
        out = []
        for seg in segments:
            for i, w in enumerate(seg.words):
                key = w.text.strip(".,;:!?").lower()
                if key in self._ov:
                    exp, obs = self._ov[key]
                    out.append(WordPhonemes(seg.id, i, w.text, w.start, w.end, exp, obs))
        return out
