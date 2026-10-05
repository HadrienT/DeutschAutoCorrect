import pytest

from app.models import Segment
from app.pipeline.demo import scenario_segments
from app.pipeline.segments import classify_segments, detect_language, teacher_cue


@pytest.mark.parametrize("text,lang", [
    ("Ich wohne in Lyon mit meiner Mutter", "de"),
    ("Madame, comment on dit frère ?", "fr"),
    ("Silence, s'il vous plaît", "fr"),
    ("Ich habe gegangen", "de"),
    ("euh", "fr"),
    ("Schokolade", "de"),
])
def test_language(text, lang):
    assert detect_language(text)[0] == lang


@pytest.mark.parametrize("text,expected", [
    ("Ruhe bitte !", True),
    ("Silence s'il vous plaît, on écoute Léa.", True),
    ("Sehr gut", True),
    ("Der Bruder. Weiter.", True),
    ("Ich bin ruhig und mache meine Hausaufgaben jeden Tag gern mit meinen Freunden", False),
    ("Ich wohne in Lyon", False),
])
def test_teacher_cue(text, expected):
    assert teacher_cue(text) is expected


def test_demo_scenario_roles():
    segs = classify_segments(scenario_segments())
    by = {s.id: s for s in segs}
    assert by["s1"].role == "teacher" and not by["s1"].graded
    assert by["s2"].graded and by["s3"].graded
    assert by["s4"].language == "fr" and not by["s4"].graded  # student asks for help in French
    assert by["s5"].role == "teacher"
    assert by["s7"].role == "teacher"
    assert by["s8"].graded  # mixed sentence, majority German
    assert [s.id for s in segs if s.graded] == ["s2", "s3", "s6", "s8", "s9"]


def test_diarization_labels_mark_other_speakers():
    segs = [Segment(id="a", start=0, end=1, text="Ich wohne in Lyon und ich mag Hunde", speaker="A"),
            Segment(id="b", start=1, end=2, text="Ich bin Tom und ich spiele Fußball", speaker="B"),
            Segment(id="c", start=2, end=4, text="Ich habe einen Hund und eine Katze zu Hause", speaker="A")]
    out = classify_segments(segs)
    assert [s.role for s in out] == ["student", "other", "student"]
    assert [s.graded for s in out] == [True, False, True]
