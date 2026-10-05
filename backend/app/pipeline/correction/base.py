from __future__ import annotations

import re
from typing import Protocol

from ...models import DetectedError, Segment, Word


class Corrector(Protocol):
    name: str

    def correct(self, segments: list[Segment]) -> list[DetectedError]:
        """Grammar / conjugation / vocabulary errors on (graded) student segments."""
        ...


_PUNCT = re.compile(r"[^\wäöüÄÖÜßéèêàçùâîôûëïœ'’-]+")


def norm(text: str) -> str:
    return _PUNCT.sub("", text).lower()


def seg_words(seg: Segment) -> list[Word]:
    """Segment words; synthesises evenly spaced timings when the ASR gave none."""
    if seg.words:
        return seg.words
    toks = seg.text.split()
    if not toks:
        return []
    step = (seg.end - seg.start) / len(toks)
    return [Word(text=t, start=seg.start + i * step, end=seg.start + (i + 1) * step)
            for i, t in enumerate(toks)]


def locate(seg: Segment, quote: str) -> tuple[float, float]:
    """Time span of the quoted words inside the segment (falls back to the whole segment)."""
    words = seg_words(seg)
    q = [norm(t) for t in quote.split() if norm(t)]
    toks = [norm(w.text) for w in words]
    if q:
        for i in range(len(toks) - len(q) + 1):
            if toks[i:i + len(q)] == q:
                return words[i].start, words[i + len(q) - 1].end
        for i, t in enumerate(toks):  # partial: first quoted token present
            if t == q[0]:
                j = min(len(toks), i + len(q))
                return words[i].start, words[j - 1].end
    return seg.start, seg.end
