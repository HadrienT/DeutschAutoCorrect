from __future__ import annotations

from fastapi import HTTPException, Request

from ..context import AppContext
from ..models import Analysis, Rubric


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def load_recording(ctx: AppContext, rec_id: str) -> dict:
    rec = ctx.db.get_recording(rec_id)
    if rec is None:
        raise HTTPException(404, "Enregistrement introuvable")
    return rec


def load_analysis(ctx: AppContext, rec_id: str) -> Analysis:
    load_recording(ctx, rec_id)
    analysis = ctx.db.get_analysis(rec_id)
    if analysis is None:
        raise HTTPException(409, "Analyse non disponible (traitement en cours ou échoué)")
    return analysis


def rubric_for(ctx: AppContext, rec: dict) -> Rubric:
    rubric = ctx.db.get_rubric(rec["rubric_id"]) if rec["rubric_id"] else None
    return rubric or ctx.db.get_rubric(ctx.db.default_rubric_id())  # type: ignore[return-value]
