"""Merge/dedupe detected errors, assign stable ids, sort chronologically."""
from __future__ import annotations

import hashlib

from ..models import DetectedError
from .correction.base import norm


def error_id(e: DetectedError) -> str:
    key = f"{e.category}|{round(e.start, 2)}|{norm(e.heard)}|{norm(e.expected)}"
    return "e_" + hashlib.sha1(key.encode()).hexdigest()[:8]


def _overlap(a: DetectedError, b: DetectedError) -> bool:
    return min(a.end, b.end) - max(a.start, b.start) > 0.05


def merge_errors(*groups: list[DetectedError]) -> list[DetectedError]:
    """Same category + overlapping time span = same error; keep the most confident/explained."""
    merged: list[DetectedError] = []
    for e in (x for g in groups for x in g):
        dup = next((m for m in merged if m.category == e.category and _overlap(m, e)), None)
        if dup is None:
            merged.append(e)
            continue
        if (e.confidence, bool(e.explanation)) > (dup.confidence, bool(dup.explanation)):
            merged[merged.index(dup)] = e
    merged.sort(key=lambda x: (x.start, x.category))
    seen: set[str] = set()
    for e in merged:
        eid = error_id(e)
        while eid in seen:
            eid += "x"
        e.id = eid
        seen.add(eid)
    return merged
