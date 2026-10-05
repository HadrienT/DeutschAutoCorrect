from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from ..context import AppContext
from ..models import Grade, Rubric
from ..scoring.engine import compute_grade
from .deps import get_ctx, load_analysis, load_recording

router = APIRouter(prefix="/api", tags=["rubrics"])


def _validate(r: Rubric) -> Rubric:
    ids = [c.id for c in r.criteria]
    if len(set(ids)) != len(ids):
        raise HTTPException(422, "Identifiants de critères dupliqués")
    if not r.criteria:
        raise HTTPException(422, "Un barème doit contenir au moins un critère")
    for c in r.criteria:
        if c.kind == "errors" and c.category is None:
            raise HTTPException(422, f"Le critère « {c.label} » doit avoir une catégorie")
    return r


@router.get("/rubrics")
def list_rubrics(ctx: AppContext = Depends(get_ctx)) -> list[Rubric]:
    return ctx.db.list_rubrics()


@router.post("/rubrics", status_code=201)
def create_rubric(body: Rubric, ctx: AppContext = Depends(get_ctx)) -> Rubric:
    return ctx.db.save_rubric(_validate(body))


@router.put("/rubrics/{rid}")
def update_rubric(rid: int, body: Rubric, ctx: AppContext = Depends(get_ctx)) -> Rubric:
    if ctx.db.get_rubric(rid) is None:
        raise HTTPException(404, "Barème introuvable")
    return ctx.db.save_rubric(_validate(body), rid)


@router.delete("/rubrics/{rid}", status_code=204)
def delete_rubric(rid: int, ctx: AppContext = Depends(get_ctx)) -> Response:
    if ctx.db.get_rubric(rid) is None:
        raise HTTPException(404, "Barème introuvable")
    if not ctx.db.delete_rubric(rid):
        raise HTTPException(409, "Impossible de supprimer le dernier barème")
    return Response(status_code=204)


class PreviewRequest(BaseModel):
    recording_id: str
    rubric: Rubric
    manual: dict[str, float] | None = None


@router.post("/grading/preview")
def preview(body: PreviewRequest, ctx: AppContext = Depends(get_ctx)) -> Grade:
    load_recording(ctx, body.recording_id)
    analysis = load_analysis(ctx, body.recording_id)
    manual = body.manual if body.manual is not None else ctx.db.get_manual(body.recording_id)
    return compute_grade(analysis, _validate(body.rubric), manual)
