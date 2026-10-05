"""Pipeline orchestration: audio -> ASR -> segments -> (pronunciation, correction) -> merge."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..models import Analysis
from .asr.base import AsrEngine
from .audio import duration_seconds, normalize_to_wav
from .correction.base import Corrector
from .merge import merge_errors
from .pronunciation.base import PronunciationEngine
from .pronunciation.step import analyze_pronunciation
from .segments import classify_segments, compute_stats

log = logging.getLogger(__name__)
ProgressFn = Callable[[str, float], None]


@dataclass
class Engines:
    asr: AsrEngine
    corrector: Corrector
    pronunciation: PronunciationEngine | None = None


class PipelineError(RuntimeError):
    """Fatal, user-readable failure (audio unreadable, ASR failed)."""


def run_pipeline(src: Path, workdir: Path, engines: Engines,
                 progress: ProgressFn | None = None) -> tuple[Analysis, Path]:
    def report(stage: str, pct: float) -> None:
        if progress:
            progress(stage, pct)

    report("audio", 2)
    try:
        wav = normalize_to_wav(src, workdir / "audio.wav")
        duration = duration_seconds(wav)
    except Exception as e:
        raise PipelineError(str(e)) from e

    report("asr", 8)
    try:
        segments = engines.asr.transcribe(wav, lambda f: report("asr", 8 + 52 * f))
    except Exception as e:
        log.exception("ASR failed")
        raise PipelineError(f"Échec de la transcription : {e}") from e
    report("segments", 62)
    classify_segments(segments)
    analysis = Analysis(segments=segments)
    warnings = analysis.warnings
    if not segments:
        warnings.append("Aucune parole détectée dans l'enregistrement.")
    graded = [s for s in segments if s.graded]

    report("pronunciation", 66)
    pron_errors = []
    try:
        pron_errors = analyze_pronunciation(engines.pronunciation, wav, graded)
    except Exception as e:  # optional stage: degrade, don't fail the job
        log.exception("pronunciation failed")
        warnings.append(f"Analyse de la prononciation indisponible : {e}")

    report("correction", 80)
    lang_errors = []
    try:
        lang_errors = engines.corrector.correct(graded)
    except Exception as e:
        log.exception("correction failed")
        warnings.append(f"Correction grammaticale indisponible : {e}")

    report("merge", 96)
    analysis.errors = merge_errors(lang_errors, pron_errors)
    analysis.stats = compute_stats(analysis, duration)
    analysis.engines = {
        "asr": engines.asr.name,
        "corrector": engines.corrector.name,
        "pronunciation": engines.pronunciation.name if engines.pronunciation else "désactivée",
    }
    report("done", 100)
    return analysis, wav
