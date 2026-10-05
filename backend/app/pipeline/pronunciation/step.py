"""Pronunciation step: phoneme comparison + ASR-confidence signal -> DetectedError list."""
from __future__ import annotations

from pathlib import Path

from ...models import DetectedError, Segment
from .base import PronunciationEngine, WordPhonemes
from .compare import compare_word, is_pronunciation_error, severity_of, tokenize

LOW_PROB = 0.5


def _ipa(x: str | list[str]) -> str:
    return "".join(tokenize(x))


def errors_from_phonemes(items: list[WordPhonemes]) -> list[DetectedError]:
    errors = []
    for it in items:
        cmp = compare_word(it.expected, it.observed)
        if not is_pronunciation_error(cmp):
            continue
        main = next((i for i in cmp.issues if i.salient), cmp.issues[0])
        word = it.text.strip(".,;:!?")
        errors.append(DetectedError(
            category="pronunciation", subtype=main.subtype, severity=severity_of(cmp),  # type: ignore[arg-type]
            segment_id=it.segment_id, start=it.start, end=it.end,
            heard=f"{word} [{_ipa(it.observed)}]", expected=f"{word} [{_ipa(it.expected)}]",
            explanation=f"« {word} » : {main.explanation}",
            confidence=0.78 if main.salient else 0.5, source="phonemes"))
    return errors


def errors_from_asr_confidence(segments: list[Segment], already: list[DetectedError]
                               ) -> list[DetectedError]:
    seen = {(e.segment_id, round(e.start, 2)) for e in already}
    out = []
    for seg in segments:
        for w in seg.words:
            if w.prob < LOW_PROB and (seg.id, round(w.start, 2)) not in seen:
                word = w.text.strip(".,;:!?")
                out.append(DetectedError(
                    category="pronunciation", subtype="unclear", severity="minor", segment_id=seg.id,
                    start=w.start, end=w.end, heard=word, expected="",
                    explanation=f"« {word} » a été reconnu avec une faible confiance "
                                f"({w.prob:.0%}) : prononciation peu claire ? À vérifier à l'écoute.",
                    confidence=0.35, source="asr_confidence"))
    return out


def analyze_pronunciation(engine: PronunciationEngine | None, wav: Path,
                          segments: list[Segment]) -> list[DetectedError]:
    errs: list[DetectedError] = []
    if engine is not None:
        errs = errors_from_phonemes(engine.analyze(wav, segments))
    return errs + errors_from_asr_confidence(segments, errs)
