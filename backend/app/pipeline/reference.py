"""Fidelity to a reference text (recitation / reading): omitted and wrong words. Pure functions."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from ..models import Analysis, DetectedError, Segment, Word
from .correction.base import seg_words
from .merge import merge_errors

_UNITS = ["null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn",
          "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn", "achtzehn",
          "neunzehn"]
_TENS = ["", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig",
         "neunzig"]
_NOT_WORD = re.compile(r"[^\wäöüÄÖÜß]+")


def spell_number(n: int) -> str:
    """German spelling of 0..999 (the ASR writes numbers as digits)."""
    if n < 20:
        return _UNITS[n]
    if n < 100:
        tens, unit = divmod(n, 10)
        if unit == 0:
            return _TENS[tens]
        return ("ein" if unit == 1 else _UNITS[unit]) + "und" + _TENS[tens]
    hundreds, rest = divmod(n, 100)
    head = ("ein" if hundreds == 1 else _UNITS[hundreds]) + "hundert"
    return head + (spell_number(rest) if rest else "")


def norm_word(text: str) -> str:
    w = _NOT_WORD.sub("", text).lower()
    if w.isdigit() and int(w) < 1000:
        return spell_number(int(w))
    return w


def reference_words(text: str) -> list[str]:
    return [t.strip(".,;:!?«»\"„“”()…") for t in text.split() if norm_word(t)]


def compare_to_reference(reference: str, segments: list[Segment]) -> list[DetectedError]:
    """One error per reference word the student skipped or replaced. Extra words are ignored."""
    ref = reference_words(reference)
    said: list[tuple[Segment, Word]] = [(s, w) for s in segments for w in seg_words(s)
                                        if norm_word(w.text)]
    if not ref or not said:
        return []
    ops = SequenceMatcher(None, [norm_word(t) for t in ref], [norm_word(w.text) for _, w in said],
                          autojunk=False).get_opcodes()
    out: list[DetectedError] = []

    def omitted(word: str, j: int) -> None:
        seg, w = said[min(j, len(said) - 1)]
        t = w.start if j < len(said) else w.end  # just before the word that follows the gap
        out.append(DetectedError(
            category="text", subtype="omitted_word", severity="major", segment_id=seg.id,
            start=max(0.0, t - 0.1), end=t + 0.1, heard="", expected=word,
            explanation=f"Mot du texte de référence oublié : « {word} ».",
            confidence=0.9, source="reference"))

    for tag, i1, i2, j1, j2 in ops:
        if tag == "delete":
            for i in range(i1, i2):
                omitted(ref[i], j1)
        elif tag == "replace":
            for k, i in enumerate(range(i1, i2)):
                if j1 + k >= j2:
                    omitted(ref[i], j2)
                    continue
                seg, w = said[j1 + k]
                heard = w.text.strip(".,;:!?")
                out.append(DetectedError(
                    category="text", subtype="wrong_word", severity="major", segment_id=seg.id,
                    start=w.start, end=w.end, heard=heard, expected=ref[i],
                    explanation=f"L'élève a dit « {heard} » au lieu de « {ref[i]} ».",
                    confidence=0.9 if w.prob >= 0.5 else 0.6, source="reference"))
    return out


def apply_reference(analysis: Analysis, reference: str) -> None:
    """(Re)compute the reference errors of an analysis, keeping the teacher's decisions."""
    kept = {e.id: e for e in analysis.errors if e.source == "reference"}
    others = [e for e in analysis.errors if e.source != "reference"]
    fresh = compare_to_reference(reference, [s for s in analysis.segments if s.graded])
    analysis.errors = merge_errors(others, fresh)
    for e in analysis.errors:
        old = kept.get(e.id)
        if e.source == "reference" and old is not None:
            e.status, e.note = old.status, old.note
