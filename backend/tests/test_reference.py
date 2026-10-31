from app.models import Analysis
from app.pipeline.reference import (
    apply_reference,
    compare_to_reference,
    norm_word,
    reference_words,
    spell_number,
)
from tests.conftest import mk_segment


def test_numbers_and_punctuation_are_normalised():
    assert [spell_number(n) for n in (0, 13, 21, 30, 101, 999)] == [
        "null", "dreizehn", "einundzwanzig", "dreißig", "einhunderteins",
        "neunhundertneunundneunzig"]
    assert norm_word("13") == norm_word("Dreizehn,") == "dreizehn"
    assert reference_words("Hallo, ich – bin „da“!") == ["Hallo", "ich", "bin", "da"]


def test_identical_recitation_has_no_error():
    seg = mk_segment(text="Ich bin 13 Jahre alt.")
    assert compare_to_reference("ich bin dreizehn Jahre alt", [seg]) == []


def test_omitted_and_wrong_words_one_error_each():
    seg = mk_segment(text="ich gehe in Schule und spiele")
    errs = compare_to_reference("Ich gehe heute in die große Schule und singe", [seg])
    got = sorted((e.subtype, e.heard, e.expected) for e in errs)
    assert got == [("omitted_word", "", "die"), ("omitted_word", "", "große"),
                   ("omitted_word", "", "heute"), ("wrong_word", "spiele", "singe")]
    wrong = next(e for e in errs if e.subtype == "wrong_word")
    assert (wrong.start, wrong.end) == (seg.words[5].start, seg.words[5].end)
    assert all(e.category == "text" and e.source == "reference" for e in errs)


def test_extra_words_and_ungraded_segments_are_ignored():
    student = mk_segment(text="ich äh ich gehe nach Hause")
    teacher = mk_segment(sid="s2", start=10, text="Ruhe bitte", graded=False)
    a = Analysis(segments=[student, teacher])
    apply_reference(a, "Ich gehe nach Hause")
    assert a.errors == []


def test_end_of_text_forgotten_and_decisions_kept():
    a = Analysis(segments=[mk_segment(text="eins zwei")])
    apply_reference(a, "eins zwei drei vier")
    assert [e.expected for e in a.errors] == ["drei", "vier"]  # neighbours are not merged
    assert len({e.id for e in a.errors}) == 2
    a.errors[0].status = "rejected"
    apply_reference(a, "eins zwei drei vier")
    assert [e.status for e in a.errors] == ["rejected", "pending"]
