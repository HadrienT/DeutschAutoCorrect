import pytest

from app.models import Analysis, DetectedError, Segment, Word


def mk_segment(sid="s1", start=0.0, text="ich gehe in die schule", graded=True, **kw):
    toks = text.split()
    words = [Word(text=t, start=start + i * 0.4, end=start + i * 0.4 + 0.35) for i, t in enumerate(toks)]
    return Segment(id=sid, start=start, end=start + 0.4 * len(toks), text=text, graded=graded,
                   words=words, **kw)


def mk_error(category="grammar", severity="minor", expected="x", start=1.0, sid="s1", **kw):
    return DetectedError(id=kw.pop("id", f"e{start}{category}"), category=category, severity=severity,
                         expected=expected, heard=kw.pop("heard", "y"), start=start, end=start + 0.3,
                         segment_id=sid, **kw)


@pytest.fixture
def analysis():
    return Analysis(segments=[mk_segment()], errors=[])
