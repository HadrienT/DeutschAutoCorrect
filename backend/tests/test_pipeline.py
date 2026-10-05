from pathlib import Path

import pytest

from app.models import default_rubric
from app.pipeline.asr.mock import MockAsr
from app.pipeline.correction.rules import RulesCorrector
from app.pipeline.demo import write_demo_wav
from app.pipeline.merge import merge_errors
from app.pipeline.orchestrator import Engines, PipelineError, run_pipeline
from app.pipeline.pronunciation.mock import MockPronunciation
from app.scoring.engine import compute_grade
from tests.conftest import mk_error


@pytest.fixture
def demo_wav(tmp_path) -> Path:
    p = tmp_path / "in.wav"
    write_demo_wav(p)
    return p


def engines(**kw):
    return Engines(asr=kw.get("asr", MockAsr()), corrector=kw.get("corrector", RulesCorrector()),
                   pronunciation=kw.get("pron", MockPronunciation()))


def test_full_pipeline_on_demo(demo_wav, tmp_path):
    steps = []
    analysis, wav = run_pipeline(demo_wav, tmp_path / "w", engines(), lambda s, p: steps.append(s))
    assert wav.exists() and steps[0] == "audio" and steps[-1] == "done"
    cats = {e.category for e in analysis.errors}
    assert cats == {"grammar", "conjugation", "vocabulary", "pronunciation"}
    sub = {(e.category, e.subtype) for e in analysis.errors}
    assert ("pronunciation", "ich_laut") in sub and ("conjugation", "auxiliary") in sub
    assert ("grammar", "word_order") in sub and ("vocabulary", "french_word") in sub
    # nothing detected inside teacher/French segments
    ungraded = {s.id for s in analysis.segments if not s.graded}
    assert not [e for e in analysis.errors if e.segment_id in ungraded]
    assert analysis.stats.teacher_segments == 3 and analysis.stats.french_segments >= 2
    assert all(e.id.startswith("e_") for e in analysis.errors)
    assert len({e.id for e in analysis.errors}) == len(analysis.errors)
    assert [e.start for e in analysis.errors] == sorted(e.start for e in analysis.errors)
    g = compute_grade(analysis, default_rubric())
    assert 0 < g.total < g.out_of


def test_optional_stage_failure_degrades(demo_wav, tmp_path):
    class Boom:
        name = "boom"

        def correct(self, segs):
            raise RuntimeError("api down")

    analysis, _ = run_pipeline(demo_wav, tmp_path / "w", engines(corrector=Boom()))
    assert any("Correction grammaticale indisponible" in w for w in analysis.warnings)
    assert {e.category for e in analysis.errors} == {"pronunciation"}


def test_asr_failure_is_fatal(demo_wav, tmp_path):
    class Boom:
        name = "boom"

        def transcribe(self, wav, progress=None):
            raise RuntimeError("gpu oom")

    with pytest.raises(PipelineError, match="transcription"):
        run_pipeline(demo_wav, tmp_path / "w", engines(asr=Boom()))


def test_unreadable_audio_is_fatal(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not audio")
    with pytest.raises(PipelineError):
        run_pipeline(bad, tmp_path / "w", engines())


def test_merge_dedupes_overlap_keeping_most_confident():
    a = mk_error(expected="x", start=1.0, confidence=0.5, id="")
    b = mk_error(expected="y", start=1.1, confidence=0.9, id="")
    c = mk_error(category="vocabulary", expected="z", start=1.0, id="")
    out = merge_errors([a], [b, c])
    assert len(out) == 2 and {e.expected for e in out} == {"y", "z"}
