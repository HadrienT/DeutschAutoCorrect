from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ...models import Segment

ProgressCb = Callable[[float], None]


class AsrEngine(Protocol):
    name: str

    def transcribe(self, wav_path: Path, progress: ProgressCb | None = None) -> list[Segment]:
        """Faithful transcription with word timestamps. Must NOT normalise learner errors."""
        ...
