from app.models import Analysis, Criterion, Rubric, VolumeTier, default_rubric
from app.scoring.engine import compute_grade, graded_word_count
from tests.conftest import mk_error, mk_segment


def rubric(**kw):
    crit = kw.pop("criteria", [Criterion(id="g", label="Gram", category="grammar", max_points=10,
                                          penalty_minor=1, penalty_major=3)])
    return Rubric(name="t", total_points=kw.pop("total", 10), criteria=crit,
                  rounding=kw.pop("rounding", "none"), min_confidence=0.0, repeat_policy=kw.pop("policy", "count_all"))


def an(errors, segs=None):
    return Analysis(segments=segs or [mk_segment()], errors=errors)


def test_no_errors_full_marks():
    assert compute_grade(an([]), rubric()).total == 10


def test_penalties_by_severity():
    g = compute_grade(an([mk_error(severity="minor", expected="a"),
                          mk_error(severity="major", expected="b", start=2)]), rubric())
    assert g.total == 6  # 10 - 1 - 3


def test_floor_at_zero():
    errs = [mk_error(severity="major", expected=str(i), start=i) for i in range(10)]
    assert compute_grade(an(errs), rubric()).total == 0


def test_rejected_errors_ignored():
    e = mk_error(severity="major")
    e.status = "rejected"
    assert compute_grade(an([e]), rubric()).total == 10


def test_ungraded_segment_errors_ignored():
    segs = [mk_segment("s1"), mk_segment("s2", graded=False)]
    g = compute_grade(an([mk_error(sid="s2")], segs), rubric())
    assert g.total == 10


def test_cap_deduction():
    c = Criterion(id="g", label="G", category="grammar", max_points=10, penalty_minor=2,
                  penalty_major=2, cap_deduction=4)
    errs = [mk_error(expected=str(i), start=i) for i in range(6)]
    assert compute_grade(an(errs), rubric(criteria=[c])).total == 6


def test_repeat_policy_once_per_expected_keeps_most_severe():
    errs = [mk_error(expected="den Mann", severity="minor", start=1),
            mk_error(expected="den  mann!", severity="major", start=5)]
    g = compute_grade(an(errs), rubric(policy="once_per_expected"))
    assert g.criteria[0].error_count == 1 and g.total == 7
    assert compute_grade(an(errs), rubric(policy="count_all")).total == 6


def test_repeat_policy_once_per_subtype():
    errs = [mk_error(expected="a", subtype="case", start=1), mk_error(expected="b", subtype="case", start=2),
            mk_error(expected="c", subtype="gender", start=3)]
    assert compute_grade(an(errs), rubric(policy="once_per_subtype")).total == 8


def test_volume_tiers():
    c = Criterion(id="v", label="V", kind="volume", max_points=2,
                  tiers=[VolumeTier(min_words=0, points=0), VolumeTier(min_words=5, points=1),
                         VolumeTier(min_words=20, points=2)])
    r = rubric(criteria=[c], total=2)
    assert graded_word_count(an([])) == 5
    assert compute_grade(an([]), r).total == 1


def test_manual_clamped_and_scaled():
    c = Criterion(id="m", label="M", kind="manual", max_points=4)
    r = rubric(criteria=[c], total=20)
    assert compute_grade(an([]), r, {"m": 2}).total == 10
    assert compute_grade(an([]), r, {"m": 99}).total == 20
    assert compute_grade(an([]), r).total == 0


def test_rounding_modes():
    c = Criterion(id="g", label="G", category="grammar", max_points=3, penalty_minor=1)
    errs = [mk_error(expected="a")]
    assert compute_grade(an(errs), rubric(criteria=[c], total=20, rounding="integer")).total == 13
    assert compute_grade(an(errs), rubric(criteria=[c], total=7, rounding="half")).total == 4.5


def test_default_rubric_perfect_without_manual():
    g = compute_grade(an([]), default_rubric())
    assert g.out_of == 20 and 0 < g.total < 20  # volume low + manual missing


def test_low_confidence_pending_ignored_unless_confirmed():
    e = mk_error(severity="major", confidence=0.3)
    r = rubric()
    r.min_confidence = 0.5
    assert compute_grade(an([e]), r).total == 10
    e.status = "confirmed"
    assert compute_grade(an([e]), r).total == 7
