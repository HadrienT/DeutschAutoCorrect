"""Background analysis jobs (thread pool) and targeted re-checks of single segments."""
from __future__ import annotations

import logging

from .context import AppContext
from .models import Analysis, Segment
from .pipeline.merge import merge_errors
from .pipeline.orchestrator import PipelineError, run_pipeline
from .pipeline.pronunciation.step import analyze_pronunciation
from .pipeline.segments import compute_stats

log = logging.getLogger(__name__)


def submit_analysis(ctx: AppContext, rec_id: str) -> None:
    ctx.db.update_recording(rec_id, status="queued", stage="queued", progress=0, error="")
    assert ctx.executor is not None
    ctx.executor.submit(_run, ctx, rec_id)


def _run(ctx: AppContext, rec_id: str) -> None:
    rec = ctx.db.get_recording(rec_id)
    if rec is None:
        return
    ctx.db.update_recording(rec_id, status="processing", stage="audio", progress=1)

    def progress(stage: str, pct: float) -> None:
        ctx.db.update_recording(rec_id, stage=stage, progress=round(pct, 1))

    try:
        analysis, wav = run_pipeline(
            ctx.recording_dir(rec_id) / rec["audio_path"], ctx.recording_dir(rec_id),
            ctx.engines, progress)
        ctx.db.save_analysis(rec_id, analysis)
        ctx.db.update_recording(rec_id, status="done", stage="done", progress=100,
                                duration=analysis.stats.duration, error="")
    except PipelineError as e:
        ctx.db.update_recording(rec_id, status="failed", stage="failed", error=str(e))
    except Exception as e:  # unexpected: never leave a job stuck in "processing"
        log.exception("job %s crashed", rec_id)
        ctx.db.update_recording(rec_id, status="failed", stage="failed", error=f"Erreur interne : {e}")


def requeue_unfinished(ctx: AppContext) -> int:
    n = 0
    for r in ctx.db.list_recordings():
        if r["status"] in {"queued", "processing"}:
            submit_analysis(ctx, r["id"])
            n += 1
    return n


def recheck_segment(ctx: AppContext, rec_id: str, analysis: Analysis, seg: Segment) -> list[str]:
    """Run correction + pronunciation on one segment that just became graded."""
    warnings: list[str] = []
    new = []
    try:
        new += ctx.engines.corrector.correct([seg])
    except Exception as e:
        warnings.append(f"Correction du segment impossible : {e}")
    wav = ctx.recording_dir(rec_id) / "audio.wav"
    try:
        if wav.exists():
            new += analyze_pronunciation(ctx.engines.pronunciation, wav, [seg])
    except Exception as e:
        warnings.append(f"Prononciation du segment impossible : {e}")
    existing = [e for e in analysis.errors if e.segment_id != seg.id or e.source == "manual"]
    analysis.errors = merge_errors(existing, new)
    analysis.stats = compute_stats(analysis, analysis.stats.duration)
    return warnings
