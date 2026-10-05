import pytest

from app.pipeline.pronunciation.compare import (
    compare_word,
    is_pronunciation_error,
    severity_of,
    tokenize,
)


def test_tokenize_handles_digraphs_and_stress():
    assert tokenize("ˈtsvaɪ") == ["ts", "v", "aɪ"]
    assert tokenize("ʃuːlə") == ["ʃ", "u", "l", "ə"]
    assert tokenize(["ʃ", "uː", "l", "ə"]) == ["ʃ", "u", "l", "ə"]


def test_identical_is_clean():
    c = compare_word("ɪç", "ɪç")
    assert c.distance == 0 and not is_pronunciation_error(c)


def test_ich_laut_detected():
    c = compare_word("ɪç", "ɪk")
    assert [i.subtype for i in c.issues] == ["ich_laut"]
    assert is_pronunciation_error(c)
    c2 = compare_word("ɪç", "ɪʃ")
    assert c2.issues[0].subtype == "ich_laut"


def test_uvular_r_variants_are_not_errors():
    assert not is_pronunciation_error(compare_word("leːʁɐ", "leːrə"))
    assert not is_pronunciation_error(compare_word("leːʁɐ", "leːɐ"))  # dropped r at end tolerated


def test_umlaut_and_w_v_and_z():
    assert compare_word("ʃyːlɐ", "ʃuːlɐ").issues[0].subtype == "umlaut"
    assert compare_word("vasɐ", "fasɐ").issues[0].subtype == "w_v"
    assert compare_word("tsvaɪ", "svaɪ").issues[0].subtype == "z_laut"


def test_h_aspire_and_final_devoicing_and_ei_ie():
    assert compare_word("haʊs", "aʊs").issues[0].subtype == "h_aspire"
    assert compare_word("hunt", "hund").issues[0].subtype == "auslautverhaertung"
    assert compare_word("aɪn", "iːn").issues[0].subtype == "ei_ie"


def test_sch_laut_and_schwa():
    c = compare_word("ʃuːlə", "skuːlə")
    assert is_pronunciation_error(c)
    assert not is_pronunciation_error(compare_word("ʃuːlə", "ʃuːlɛ"))  # near-equivalent vowel


def test_noise_below_threshold_ignored_but_big_mismatch_flagged():
    assert not is_pronunciation_error(compare_word("kaɪnə", "kaɪnɛ"))
    c = compare_word("fɛrɡeːbən", "buːtzɪŋ")
    assert is_pronunciation_error(c) and severity_of(c) == "major"


@pytest.mark.parametrize("exp,obs", [("a", "a"), ("ʃtraːsə", "ʃtraːzə")])
def test_clean_cases(exp, obs):
    assert not is_pronunciation_error(compare_word(exp, obs))
