"""Pure grading engine: (analysis, rubric, manual values) -> Grade. No I/O."""
from __future__ import annotations

import math
import re

from ..models import (
    Analysis,
    Criterion,
    CriterionGrade,
    DetectedError,
    Grade,
    Rubric,
)


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def graded_word_count(analysis: Analysis) -> int:
    n = 0
    for seg in analysis.segments:
        if seg.graded:
            n += len(seg.words) if seg.words else len(seg.text.split())
    return n


def counted_errors(analysis: Analysis, criterion: Criterion, policy: str,
                   min_confidence: float = 0.0) -> list[DetectedError]:
    """Errors that count for a criterion: not rejected, on graded segments, repeat policy applied."""
    graded_ids = {s.id for s in analysis.segments if s.graded}
    pool = [
        e for e in analysis.errors
        if e.category == criterion.category and e.status != "rejected"
        and (not e.segment_id or e.segment_id in graded_ids)
        and (e.status == "confirmed" or e.confidence >= min_confidence)
    ]
    if policy == "count_all":
        return pool
    best: dict[tuple, DetectedError] = {}
    order: list[tuple] = []
    for e in sorted(pool, key=lambda x: x.start):
        if policy == "once_per_subtype":
            key: tuple = (e.category, e.subtype)
        else:
            key = (e.category, _norm(e.expected) or _norm(e.heard) or e.id)
        if key not in best:
            best[key] = e
            order.append(key)
        elif e.severity == "major" and best[key].severity == "minor":
            best[key] = e
    return [best[k] for k in order]


def _round(value: float, mode: str) -> float:
    if mode == "integer":
        return float(math.floor(value + 0.5))
    if mode == "half":
        return math.floor(value * 2 + 0.5) / 2
    return round(value, 2)


def _grade_errors(analysis: Analysis, c: Criterion, policy: str,
                  min_conf: float) -> CriterionGrade:
    errs = counted_errors(analysis, c, policy, min_conf)
    minors = sum(1 for e in errs if e.severity == "minor")
    majors = len(errs) - minors
    deduction = minors * c.penalty_minor + majors * c.penalty_major
    if c.cap_deduction is not None:
        deduction = min(deduction, c.cap_deduction)
    earned = max(0.0, c.max_points - deduction)
    detail = f"{majors} grave(s), {minors} légère(s) → −{min(deduction, c.max_points):g}"
    return CriterionGrade(id=c.id, label=c.label, kind=c.kind, earned=round(earned, 4),
                          max=c.max_points, detail=detail, error_count=len(errs))


def _grade_volume(analysis: Analysis, c: Criterion) -> CriterionGrade:
    words = graded_word_count(analysis)
    pts = 0.0
    for t in sorted(c.tiers, key=lambda t: t.min_words):
        if words >= t.min_words:
            pts = t.points
    pts = min(pts, c.max_points)
    return CriterionGrade(id=c.id, label=c.label, kind=c.kind, earned=pts, max=c.max_points,
                          detail=f"{words} mot(s) d'élève")


def rhythm_suggestion(analysis: Analysis, c: Criterion) -> tuple[float, str]:
    """Automatic rhythm mark from long pauses and speech rate (a heuristic the teacher reviews)."""
    stats = analysis.stats
    long_pauses = sum(1 for p in stats.pauses if p >= c.pause_seconds)
    slow = 0 < stats.words_per_minute < c.min_wpm
    value = c.max_points - long_pauses * c.pause_penalty - (c.slow_penalty if slow else 0.0)
    detail = (f"{stats.words_per_minute:g} mots/min{' (lent)' if slow else ''}, "
              f"{long_pauses} pause(s) de plus de {c.pause_seconds:g} s")
    return min(max(value, 0.0), c.max_points), detail


def _grade_rhythm(analysis: Analysis, c: Criterion, manual: dict[str, float]) -> CriterionGrade:
    suggested, detail = rhythm_suggestion(analysis, c)
    if c.id in manual:
        earned = min(max(float(manual[c.id]), 0.0), c.max_points)
        detail += f" → suggestion {suggested:g}, note saisie par l'enseignant"
    else:
        earned = suggested
        detail += " → note suggérée (modifiable)"
    return CriterionGrade(id=c.id, label=c.label, kind=c.kind, earned=round(earned, 4),
                          max=c.max_points, detail=detail, suggested=round(suggested, 4))


def compute_grade(analysis: Analysis, rubric: Rubric,
                  manual: dict[str, float] | None = None) -> Grade:
    manual = manual or {}
    crits: list[CriterionGrade] = []
    for c in rubric.criteria:
        if c.kind == "errors":
            crits.append(_grade_errors(analysis, c, rubric.repeat_policy, rubric.min_confidence))
        elif c.kind == "volume":
            crits.append(_grade_volume(analysis, c))
        elif c.kind == "rhythm":
            crits.append(_grade_rhythm(analysis, c, manual))
        else:
            v = min(max(float(manual.get(c.id, 0.0)), 0.0), c.max_points)
            crits.append(CriterionGrade(id=c.id, label=c.label, kind=c.kind, earned=v,
                                        max=c.max_points,
                                        detail="saisie manuelle" if c.id in manual else "non saisi"))
    # Weighted mean of the criteria; with the default weight (= max points) it is the plain sum.
    for c, g in zip(rubric.criteria, crits, strict=True):
        g.weight = c.max_points if c.weight is None else c.weight
    raw_total = sum(c.earned for c in crits)
    raw_max = sum(c.max for c in crits)
    weights = sum(g.weight for g in crits if g.max > 0)
    ratio = sum(g.weight * g.earned / g.max for g in crits if g.max > 0) / weights if weights else 0
    scaled = ratio * rubric.total_points
    total = min(_round(scaled, rubric.rounding), rubric.total_points)
    return Grade(raw_total=round(raw_total, 4), raw_max=raw_max, total=total,
                 out_of=rubric.total_points, criteria=crits)
