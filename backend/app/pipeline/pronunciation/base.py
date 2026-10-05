from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ...models import Segment


@dataclass
class WordPhonemes:
    segment_id: str
    word_index: int
    text: str
    start: float
    end: float
    expected: str | list[str]
    observed: str | list[str]


class PronunciationEngine(Protocol):
    name: str

    def analyze(self, wav_path: Path, segments: list[Segment]) -> list[WordPhonemes]:
        """Expected vs. actually-pronounced phonemes for every word of the given segments."""
        ...
