import json
from types import SimpleNamespace

import httpx
import pytest

from app.pipeline.correction.llm import (
    LOCAL_SCHEMA,
    SCHEMA,
    AnthropicCorrector,
    OpenAICompatCorrector,
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


def test_noop_correction_is_dropped():
    item = dict(PAYLOAD["errors"][0], quote="gehe in", expected="Gehe in.")
    assert parse_errors(json.dumps({"errors": [item]}), [mk_segment()]) == []


def test_confidence_marks_are_stripped_from_quotes():
    item = dict(PAYLOAD["errors"][0], quote="gehe{40%} in", expected="gehe ins")
    seg = mk_segment()
    err = parse_errors(json.dumps({"errors": [item]}), [seg])[0]
    assert err.heard == "gehe in" and err.start == seg.words[1].start


def local_corrector(model="", served="gemma", content=None, finish="stop"):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": served}]})
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{
            "finish_reason": finish,
            "message": {"content": content or json.dumps(PAYLOAD)}}]})

    client = httpx.Client(base_url="http://llm.test/v1/", transport=httpx.MockTransport(handler))
    return OpenAICompatCorrector(model=model, client=client), seen


def test_local_corrector_request_shape():
    corrector, seen = local_corrector()
    errs = corrector.correct([mk_segment()])
    assert len(errs) == 1 and errs[0].source == "llm"
    body = seen[0]
    assert body["model"] == "gemma"  # empty DAC_LLM_MODEL: whatever the server serves
    assert body["response_format"]["json_schema"]["schema"] == LOCAL_SCHEMA
    assert body["messages"][0]["role"] == "system"


def test_local_corrector_sends_small_batches():
    corrector, seen = local_corrector()
    corrector.correct([mk_segment(sid=f"s{i}") for i in range(1, 20)])
    assert len(seen) == 5  # 4 + 4 + 4 + 4 + 3 segments


def test_local_corrector_refuses_another_served_model():
    corrector, seen = local_corrector(model="gemma", served="qwen-coder")
    with pytest.raises(RuntimeError, match="qwen-coder"):
        corrector.correct([mk_segment()])
    assert seen == []


def test_local_corrector_truncation_and_unreachable():
    with pytest.raises(RuntimeError):
        local_corrector(finish="length")[0].correct([mk_segment()])

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = httpx.Client(base_url="http://llm.test/v1/", transport=httpx.MockTransport(down))
    with pytest.raises(RuntimeError, match="injoignable"):
        OpenAICompatCorrector(client=client).correct([mk_segment()])
