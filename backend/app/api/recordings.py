from __future__ import annotations

import csv
import io
import json
import mimetypes
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..context import AppContext
from ..jobs import recheck_segment, submit_analysis
from ..models import (
    Analysis,
    DetectedError,
    ErrorCategory,
    ErrorStatus,
    Grade,
    Language,
    Role,
    Rubric,
    Severity,
)
from ..pipeline.audio import compute_peaks, read_wav
from ..pipeline.merge import error_id
from ..pipeline.segments import compute_stats
from ..scoring.engine import compute_grade
from .deps import get_ctx, load_analysis, load_recording, rubric_for

router = APIRouter(prefix="/api/recordings", tags=["recordings"])
BROWSER_AUDIO = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".oga", ".webm", ".mp4", ".flac"}


def summary(rec: dict, grade: Grade | None = None) -> dict:
    return {
        "id": rec["id"], "title": rec["title"], "student_name": rec["student_name"],
        "filename": rec["filename"], "status": rec["status"], "stage": rec["stage"],
        "progress": rec["progress"], "error": rec["error"], "duration": rec["duration"],
        "created_at": rec["created_at"], "rubric_id": rec["rubric_id"],
        "grade": grade.model_dump() if grade else None,
    }


def _grade(ctx: AppContext, rec: dict, analysis: Analysis | None) -> Grade | None:
    if analysis is None:
        return None
    return compute_grade(analysis, rubric_for(ctx, rec), ctx.db.get_manual(rec["id"]))


@router.get("")
def list_recordings(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    out = []
    for r in ctx.db.list_recordings():
        analysis = ctx.db.get_analysis(r["id"]) if r["status"] == "done" else None
        out.append(summary(r, _grade(ctx, r, analysis)))
    return out


@router.post("", status_code=201)
async def create_recording(
    file: UploadFile = File(...), title: str = Form(""), student_name: str = Form(""),
    rubric_id: int | None = Form(None), ctx: AppContext = Depends(get_ctx),
) -> dict:
    rec_id = uuid.uuid4().hex[:12]
    ext = Path(file.filename or "audio").suffix.lower() or ".bin"
    folder = ctx.recording_dir(rec_id)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"original{ext}"
    limit = ctx.settings.max_upload_mb * 1024 * 1024
    size = 0
    with dest.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Fichier trop volumineux (max {ctx.settings.max_upload_mb} Mo)")
            f.write(chunk)
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "Fichier vide")
    if rubric_id is not None and ctx.db.get_rubric(rubric_id) is None:
        raise HTTPException(400, "Barème inconnu")
    name = file.filename or dest.name
    ctx.db.create_recording(rec_id, title.strip() or Path(name).stem, student_name.strip(), name,
                            rubric_id or ctx.db.default_rubric_id())
    ctx.db.update_recording(rec_id, audio_path=dest.name)
    submit_analysis(ctx, rec_id)
    return summary(ctx.db.get_recording(rec_id))  # type: ignore[arg-type]


@router.get("/{rec_id}")
def get_recording(rec_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    rec = load_recording(ctx, rec_id)
    analysis = ctx.db.get_analysis(rec_id)
    rubric = rubric_for(ctx, rec)
    out = summary(rec, _grade(ctx, rec, analysis))
    out.update(analysis=analysis.model_dump() if analysis else None, rubric=rubric.model_dump(),
               manual=ctx.db.get_manual(rec_id))
    return out


@router.delete("/{rec_id}", status_code=204)
def delete_recording(rec_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    import shutil
    load_recording(ctx, rec_id)
    ctx.db.delete_recording(rec_id)
    shutil.rmtree(ctx.recording_dir(rec_id), ignore_errors=True)
    return Response(status_code=204)


@router.post("/{rec_id}/reanalyze", status_code=202)
def reanalyze(rec_id: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    load_recording(ctx, rec_id)
    submit_analysis(ctx, rec_id)
    return summary(ctx.db.get_recording(rec_id))  # type: ignore[arg-type]


# ---- audio ----
@router.get("/{rec_id}/audio")
def audio(rec_id: str, ctx: AppContext = Depends(get_ctx)) -> FileResponse:
    """Original upload when browser-playable, else the normalised WAV. Range requests supported."""
    rec = load_recording(ctx, rec_id)
    folder = ctx.recording_dir(rec_id)
    path = folder / rec["audio_path"]
    if path.suffix.lower() not in BROWSER_AUDIO and (folder / "audio.wav").exists():
        path = folder / "audio.wav"
    if not path.exists():
        raise HTTPException(404, "Fichier audio introuvable")
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "audio/wav")


@router.get("/{rec_id}/peaks")
def peaks(rec_id: str, bins: int = 900, ctx: AppContext = Depends(get_ctx)) -> dict:
    load_recording(ctx, rec_id)
    cache = ctx.recording_dir(rec_id) / f"peaks_{bins}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    wav = ctx.recording_dir(rec_id) / "audio.wav"
    if not wav.exists():
        raise HTTPException(409, "Audio pas encore normalisé")
    samples, sr = read_wav(wav)
    data = {"peaks": compute_peaks(samples, max(50, min(bins, 4000))), "duration": len(samples) / sr}
    cache.write_text(json.dumps(data))
    return data


# ---- edits ----
class ErrorPatch(BaseModel):
    status: ErrorStatus | None = None
    category: ErrorCategory | None = None
    severity: Severity | None = None
    subtype: str | None = None
    expected: str | None = None
    explanation: str | None = None
    note: str | None = None


class ErrorCreate(BaseModel):
    category: ErrorCategory
    subtype: str = "other"
    severity: Severity = "minor"
    start: float
    end: float
    heard: str = ""
    expected: str = ""
    explanation: str = ""
    note: str = ""


class SegmentPatch(BaseModel):
    role: Role | None = None
    language: Language | None = None
    graded: bool | None = None


class RubricAssign(BaseModel):
    rubric_id: int | None = None
    manual: dict[str, float] | None = None


def _result(ctx: AppContext, rec_id: str, analysis: Analysis, **extra) -> dict:
    ctx.db.save_analysis(rec_id, analysis)
    rec = ctx.db.get_recording(rec_id)
    return {"analysis": analysis.model_dump(), "grade": _grade(ctx, rec, analysis).model_dump(), **extra}  # type: ignore[union-attr,arg-type]


@router.patch("/{rec_id}/errors/{eid}")
def patch_error(rec_id: str, eid: str, body: ErrorPatch, ctx: AppContext = Depends(get_ctx)) -> dict:
    analysis = load_analysis(ctx, rec_id)
    err = next((e for e in analysis.errors if e.id == eid), None)
    if err is None:
        raise HTTPException(404, "Erreur introuvable")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(err, k, v)
    return _result(ctx, rec_id, analysis)


@router.delete("/{rec_id}/errors/{eid}")
def delete_error(rec_id: str, eid: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    analysis = load_analysis(ctx, rec_id)
    before = len(analysis.errors)
    analysis.errors = [e for e in analysis.errors if e.id != eid]
    if len(analysis.errors) == before:
        raise HTTPException(404, "Erreur introuvable")
    return _result(ctx, rec_id, analysis)


@router.post("/{rec_id}/errors", status_code=201)
def add_error(rec_id: str, body: ErrorCreate, ctx: AppContext = Depends(get_ctx)) -> dict:
    analysis = load_analysis(ctx, rec_id)
    if body.end < body.start:
        raise HTTPException(422, "end < start")
    mid = (body.start + body.end) / 2
    seg = next((s for s in analysis.segments if s.start <= mid <= s.end), None)
    err = DetectedError(**body.model_dump(), segment_id=seg.id if seg else "", confidence=1.0,
                        source="manual", status="confirmed")
    err.id = "m_" + error_id(err)[2:]
    while any(e.id == err.id for e in analysis.errors):
        err.id += "x"
    analysis.errors.append(err)
    analysis.errors.sort(key=lambda e: e.start)
    return _result(ctx, rec_id, analysis, created=err.id)


@router.patch("/{rec_id}/segments/{sid}")
def patch_segment(rec_id: str, sid: str, body: SegmentPatch,
                  ctx: AppContext = Depends(get_ctx)) -> dict:
    analysis = load_analysis(ctx, rec_id)
    seg = next((s for s in analysis.segments if s.id == sid), None)
    if seg is None:
        raise HTTPException(404, "Segment introuvable")
    was_graded = seg.graded
    if body.role is not None:
        seg.role = body.role
    if body.language is not None:
        seg.language = body.language
    seg.graded = (body.graded if body.graded is not None
                  else seg.role == "student" and seg.language == "de")
    warnings: list[str] = []
    if seg.graded and not was_graded and not any(e.segment_id == sid for e in analysis.errors):
        warnings = recheck_segment(ctx, rec_id, analysis, seg)
    analysis.stats = compute_stats(analysis, analysis.stats.duration)
    return _result(ctx, rec_id, analysis, warnings=warnings)


@router.put("/{rec_id}/rubric")
def assign_rubric(rec_id: str, body: RubricAssign, ctx: AppContext = Depends(get_ctx)) -> dict:
    rec = load_recording(ctx, rec_id)
    if body.rubric_id is not None:
        if ctx.db.get_rubric(body.rubric_id) is None:
            raise HTTPException(404, "Barème introuvable")
        ctx.db.update_recording(rec_id, rubric_id=body.rubric_id)
    if body.manual is not None:
        ctx.db.set_manual(rec_id, body.manual)
    rec = ctx.db.get_recording(rec_id)
    return {"grade": _grade(ctx, rec, ctx.db.get_analysis(rec_id)),  # type: ignore[arg-type]
            "rubric": rubric_for(ctx, rec).model_dump(), "manual": ctx.db.get_manual(rec_id)}  # type: ignore[arg-type]


@router.get("/{rec_id}/grade")
def grade(rec_id: str, ctx: AppContext = Depends(get_ctx)) -> Grade:
    rec = load_recording(ctx, rec_id)
    g = _grade(ctx, rec, load_analysis(ctx, rec_id))
    assert g is not None
    return g


def _attachment(name: str) -> dict[str, str]:
    from urllib.parse import quote
    ascii_name = name.encode("ascii", "ignore").decode() or "export"
    return {"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; "
            f"filename*=UTF-8''{quote(name)}"}


def _tc(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


@router.get("/{rec_id}/export.{fmt}")
def export(rec_id: str, fmt: Literal["csv", "json"], ctx: AppContext = Depends(get_ctx)) -> Response:
    rec = load_recording(ctx, rec_id)
    analysis = load_analysis(ctx, rec_id)
    g = _grade(ctx, rec, analysis)
    assert g is not None
    base = f"{rec['title'] or rec_id}".replace("/", "_").replace('"', "")
    if fmt == "json":
        body = json.dumps({"recording": summary(rec, g), "analysis": analysis.model_dump()},
                          ensure_ascii=False, indent=2)
        return Response(body, media_type="application/json",
                        headers=_attachment(f"{base}.json"))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timecode", "categorie", "type", "gravite", "statut", "entendu", "attendu",
                "explication", "note"])
    for e in analysis.errors:
        w.writerow([_tc(e.start), e.category, e.subtype, e.severity, e.status, e.heard,
                    e.expected, e.explanation, e.note])
    w.writerow([])
    w.writerow(["NOTE", f"{g.total:g}/{g.out_of:g}"])
    for c in g.criteria:
        w.writerow([c.label, f"{c.earned:g}/{c.max:g}", c.detail])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers=_attachment(f"{base}.csv"))


# re-exported for the grading preview route
__all__ = ["router", "Rubric"]
