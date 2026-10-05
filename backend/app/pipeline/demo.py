"""Built-in demo scenario used by the mock engines (tests, offline demo).

Word DSL: ``text`` or ``text|prob|expected_phonemes|observed_phonemes``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..models import Segment, Word
from .audio import SAMPLE_RATE, write_wav

WORD_SECONDS = 0.42
GAP_SECONDS = 0.9


@dataclass
class DemoWord:
    text: str
    prob: float = 0.95
    expected: str = ""
    observed: str = ""


@dataclass
class DemoUtterance:
    words: list[DemoWord] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


def parse_utterance(dsl: str) -> DemoUtterance:
    words = []
    for tok in dsl.split():
        parts = tok.split("|")
        words.append(DemoWord(
            text=parts[0],
            prob=float(parts[1]) if len(parts) > 1 and parts[1] else 0.95,
            expected=parts[2] if len(parts) > 2 else "",
            observed=parts[3] if len(parts) > 3 else "",
        ))
    return DemoUtterance(words)


DEMO_SCENARIO: list[str] = [
    "Silence, s'il vous plaît, on écoute Léa.",
    "Hallo, ich|0.93|ɪç|ɪk heiße Léa und ich|0.91|ɪç|ɪʃ bin zwölf|0.88|tsvœlf|svœlf Jahre alt.",
    "Ich wohnen in Lyon mit meine Mutter und mein Bruder.",
    "Madame, comment on dit frère ?",
    "Der Bruder. Weiter.",
    "Am Wochenende ich habe gegangen in die Kino.",
    "Ruhe bitte !",
    "Mein Lieblingsfach ist Sport, weil es ist très amusant.",
    "Meine Schule|0.55|ʃuːlə|skuːlə ist groß und ich|0.9|ɪç|ɪk mag die Lehrer|0.9|leːʁɐ|leːʁɐ.",
]


def scenario_segments(lines: list[str] | None = None) -> list[Segment]:
    t = 0.6
    segs: list[Segment] = []
    for i, line in enumerate(lines or DEMO_SCENARIO, start=1):
        utt = parse_utterance(line)
        start = t
        words = []
        for w in utt.words:
            words.append(Word(text=w.text, start=round(t, 3), end=round(t + WORD_SECONDS - 0.05, 3),
                              prob=w.prob))
            t += WORD_SECONDS
        segs.append(Segment(id=f"s{i}", start=round(start, 3), end=round(t, 3), text=utt.text,
                            words=words))
        t += GAP_SECONDS
    return segs


def pronunciation_overrides(lines: list[str] | None = None) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for line in lines or DEMO_SCENARIO:
        for w in parse_utterance(line).words:
            if w.expected:
                key = w.text.strip(".,;:!?").lower()
                out.setdefault(key, (w.expected, w.observed))
    return out


def write_demo_wav(path, segs: list[Segment] | None = None) -> float:
    """Synthesise a wav whose energy follows the scenario's word timings (no real speech)."""
    segs = segs or scenario_segments()
    total = segs[-1].end + 0.8
    n = int(total * SAMPLE_RATE)
    rng = np.random.default_rng(7)
    x = rng.normal(0, 0.004, n).astype(np.float32)
    tt = np.arange(n) / SAMPLE_RATE
    for s in segs:
        base = 190.0 if s.text.split()[0].strip(",.!?") in {"Silence", "Ruhe", "Der"} else 140.0
        for w in s.words:
            a, b = int(w.start * SAMPLE_RATE), int(w.end * SAMPLE_RATE)
            env = np.hanning(b - a) * (0.25 + 0.2 * rng.random())
            f = base * (1 + 0.15 * rng.random())
            x[a:b] += (env * (np.sin(2 * np.pi * f * tt[a:b]) + 0.5 * np.sin(2 * np.pi * 2.1 * f * tt[a:b]))).astype(np.float32)
    write_wav(path, x)
    return float(total)
