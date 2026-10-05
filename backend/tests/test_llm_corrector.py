import json
from types import SimpleNamespace

import pytest

from app.pipeline.correction.llm import (
    SCHEMA,
    AnthropicCorrector,
    build_user_message,
    parse_errors,
)
from tests.conftest import mk_segment


class FakeClient:
    def __init__(self, text, stop_reason="end_turn"):
        self.calls = []
        self._text, self._stop = text, stop_reason
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(stop_reason=self._stop,
                               content=[SimpleNamespace(type="text", text=self._text)])


PAYLOAD = {"errors": [
    {"segment_id": "s1", "quote": "gehe in", "category": "grammar", "subtype": "case",
     "severity": "major", "expected": "gehe ins", "explanation": "x", "confidence": 0.9},
    {"segment_id": "zz", "quote": "?", "category": "grammar", "subtype": "x", "severity": "minor",
     "expected": "", "explanation": "", "confidence": 1},
    {"segment_id": "s1", "quote": "schule", "category": "pronunciation", "subtype": "x",
     "severity": "minor", "expected": "", "explanation": "", "confidence": 1},
]}


def test_parse_anchors_and_filters():
    seg = mk_segment(text="ich gehe in die schule", start=5.0)
    errs = parse_errors(json.dumps(PAYLOAD), [seg])
    assert len(errs) == 1  # unknown segment and non-allowed category dropped
    e = errs[0]
    assert e.source == "llm" and e.start == seg.words[1].start and e.end == seg.words[2].end


def test_invalid_json_raises():
    with pytest.raises(ValueError):
        parse_errors("not json", [mk_segment()])


def test_corrector_request_shape_no_forced_tool_or_sampling():
    fc = FakeClient(json.dumps(PAYLOAD))
    errs = AnthropicCorrector(client=fc).correct([mk_segment()])
    kw = fc.calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"]["format"]["schema"] == SCHEMA
    assert "tool_choice" not in kw and "temperature" not in kw and "thinking" not in kw
    assert len(errs) == 1


def test_refusal_and_truncation_raise():
    for reason in ("refusal", "max_tokens"):
        with pytest.raises(RuntimeError):
            AnthropicCorrector(client=FakeClient("{}", reason)).correct([mk_segment()])


def test_low_confidence_words_are_annotated():
    seg = mk_segment(text="ich gehe")
    seg.words[1].prob = 0.4
    assert "gehe{40%}" in build_user_message([seg])
