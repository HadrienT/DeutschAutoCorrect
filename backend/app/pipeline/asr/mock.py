"""Deterministic ASR used for tests and the offline demo."""
from __future__ import annotations

from pathlib import Path

from ...models import Segment
from ..demo import scenario_segments
from .base import ProgressCb


class MockAsr:
    name = "mock"

    def __init__(self, lines: list[str] | None = None):
        self._lines = lines

    def transcribe(self, wav_path: Path, progress: ProgressCb | None = None) -> list[Segment]:
        segs = scenario_segments(self._lines)
        if progress:
            progress(1.0)
        return segs
