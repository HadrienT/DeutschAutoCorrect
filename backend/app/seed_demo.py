"""Inject a synthetic demo recording (mock engines, no models needed): python -m app.seed_demo"""
from __future__ import annotations

from .config import get_settings
from .context import AppContext
from .db import Database
from .jobs import _run
from .pipeline.asr.mock import MockAsr
from .pipeline.correction.rules import RulesCorrector
from .pipeline.demo import write_demo_wav
from .pipeline.orchestrator import Engines
from .pipeline.pronunciation.mock import MockPronunciation


def seed() -> str:
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(s.db_path)
    ctx = AppContext(s, db, Engines(MockAsr(), RulesCorrector(), MockPronunciation()))
    rec_id = "demo" + str(len(db.list_recordings()) + 1)
    folder = ctx.recording_dir(rec_id)
    folder.mkdir(parents=True, exist_ok=True)
    write_demo_wav(folder / "original.wav")
    db.create_recording(rec_id, "Démo — Léa se présente", "Léa", "demo.wav", db.default_rubric_id())
    db.update_recording(rec_id, audio_path="original.wav")
    _run(ctx, rec_id)
    assert ctx.executor is not None
    ctx.executor.shutdown(wait=False)
    return rec_id


if __name__ == "__main__":
    print("demo recording:", seed())
