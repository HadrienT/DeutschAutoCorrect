from app.pipeline.correction.rules import correct_segment
from tests.conftest import mk_segment


def run(text):
    return correct_segment(mk_segment(text=text))


def sig(errs):
    return [(e.category, e.subtype, e.expected) for e in errs]


def test_clean_sentence_has_no_errors():
    assert run("Ich wohne in Lyon mit meiner Mutter und meinem Bruder.") == []
    assert run("Am Wochenende bin ich ins Kino gegangen.") == []
    assert run("Mein Lieblingsfach ist Sport, weil es sehr lustig ist.") == []


def test_ich_infinitive():
    assert sig(run("Ich wohnen in Lyon")) == [("conjugation", "person_ending", "ich wohne")]


def test_wrong_sein_and_haben():
    assert sig(run("Ich bist müde"))[0][2] == "ich bin"
    assert sig(run("Er habe einen Hund"))[0][2] == "er hat"


def test_er_infinitive_and_du():
    assert sig(run("Er spielen Fußball"))[0][2] == "er spielt"
    assert sig(run("Du spielen Fußball"))[0][2] == "du spielst"


def test_auxiliary_motion_verb():
    e = run("Ich habe gegangen")
    assert [(x.subtype, x.expected, x.heard) for x in e] == [("auxiliary", "bin", "habe")]


def test_dative_possessive_after_mit():
    e = run("Ich wohne mit meine Mutter und mein Bruder.")
    assert [x.expected for x in e if x.subtype == "case"] == ["meiner Mutter", "meinem Bruder"]


def test_gender_article():
    e = run("Ich gehe in die Kino")
    assert ("grammar", "gender", "das Kino") in sig(e)


def test_v2_after_adverbial():
    e = run("Am Wochenende ich habe gegangen in die Kino.")
    s = sig(e)
    assert ("grammar", "word_order", "Am Wochenende habe ich") in s
    assert any(x.subtype == "auxiliary" for x in e)


def test_verb_final_in_weil_clause():
    e = run("Mein Lieblingsfach ist Sport, weil es ist lustig.")
    assert ("grammar", "word_order", "weil es lustig ist.") in sig(e)


def test_french_words_merged():
    e = run("Es ist très amusant")
    assert len(e) == 1 and e[0].heard == "très amusant" and e[0].subtype == "french_word"


def test_timecodes_anchor_on_faulty_words():
    seg = mk_segment(text="Ich wohnen in Lyon", start=10.0)
    e = correct_segment(seg)[0]
    assert abs(e.start - seg.words[0].start) < 1e-9 and abs(e.end - seg.words[1].end) < 1e-9
