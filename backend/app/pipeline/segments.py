"""Per-segment language detection and speaker-role classification.

Language: lexical scoring (function words + diacritics) — robust on short utterances where
ASR language ID is unreliable. Role: teacher cues (FR/DE injunctions, feedback), optional
diarization labels, and "who speaks most German" as the student.
"""
from __future__ import annotations

import re
from collections import Counter

from ..models import Analysis, Language, Role, Segment, Stats

_TOKEN = re.compile(r"[\wÀ-ÿß']+", re.UNICODE)

FR_WORDS = set("""le la les un une des du de et est sont je tu il elle on nous vous ils elles ne pas
que qui quoi comment pourquoi quand avec pour dans sur sous mais ou donc alors très oui non voilà
madame monsieur s'il c'est j'ai suis ai as a avons avez ont fait dit dire sais peux peut veux
voulez comprends comprends frère soeur mère père maison école bonjour merci excusez attends
répète répétez écoute écoutez silence chut taisez calme doucement bien d'accord euh
ça ce cet cette ces mon ma mes ton ta tes son sa ses notre votre leur leurs ici là
""".split())
DE_WORDS = set("""der die das ein eine einen einem einer den dem des und ist sind bin bist habe hat haben
ich du er sie es wir ihr nicht kein keine mit von zu in im am an auf aus bei nach für über
auch aber oder wie was wo wer wann warum weil dass wenn ja nein bitte danke hallo heiße heisse
mein meine meiner meinem meinen dein sein ihre unser gern gut sehr schon noch nur dann jetzt
heute gestern morgen ich's wohne wohnen mag mache gehe gehst geht gegangen kino schule
""".split())

_FR_CHARS = set("éèêàçùâîôûëïœ")
_DE_CHARS = set("äöüß")

TEACHER_FR = [
    r"\bsilence\b", r"\bchut\b", r"\btaisez", r"\bon se tait\b", r"\bécoutez\b", r"\bécoute\b",
    r"\bdoucement\b", r"\brépète\b", r"\brépétez\b", r"\battendez\b", r"\bcalmez\b",
    r"\btrès bien\b", r"\bc'est bien\b", r"\bcontinue\b", r"\bcontinuez\b", r"\bon écoute\b",
    r"\bdu calme\b", r"\bpas de bavardage\b", r"\bregarde\b", r"\bessaie\b", r"\bessayez\b",
    r"\bje t'écoute\b", r"\bà toi\b", r"\bstop\b", r"\bpose\b",
]
TEACHER_DE = [
    r"\bruhe\b", r"\bruhig\b", r"\bpsst?\b", r"\bleise\b", r"\bstill\b", r"\bhört zu\b",
    r"\bsehr gut\b", r"\bweiter\b", r"\bwiederhol", r"\bnoch (einmal|mal)\b", r"\bstopp\b",
    r"\bgenau\b", r"\bsuper\b", r"\bprima\b", r"\bkonzentriert\b", r"\bnächste[rn]?\b",
    r"\bzuhören\b", r"\bsprich\b", r"\bsprecht\b",
]
_TEACHER_RE = re.compile("|".join(TEACHER_FR + TEACHER_DE), re.IGNORECASE)


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def detect_language(text: str) -> tuple[Language, float]:
    toks = tokens(text)
    if not toks:
        return "other", 0.0
    fr = sum(t in FR_WORDS for t in toks) + sum(any(c in _FR_CHARS for c in t) for t in toks)
    de = sum(t in DE_WORDS for t in toks) + sum(any(c in _DE_CHARS for c in t) for t in toks)
    # apostrophe elisions are distinctively French (c'est, s'il, j'ai, qu'...)
    fr += sum(("'" in t or "’" in t) for t in toks)
    if fr == de == 0:
        return "de", 0.3  # unknown short utterance: assume the target language
    if fr > de:
        return "fr", fr / (fr + de)
    return "de", de / (fr + de) if de else 0.3


def teacher_cue(text: str, n_tokens: int | None = None) -> bool:
    """A teacher injunction/feedback phrase dominating a short utterance."""
    n = n_tokens if n_tokens is not None else len(tokens(text))
    m = _TEACHER_RE.search(text)
    if not m:
        return False
    cue_tokens = len(tokens(m.group(0)))
    return n <= 8 or cue_tokens / max(n, 1) >= 0.3


def classify_segments(segments: list[Segment]) -> list[Segment]:
    """Fill language/role/graded on each segment (mutates and returns them)."""
    for s in segments:
        s.language, _ = detect_language(s.text)
    # dominant speaker (if diarization labels exist) = who produced most German words
    de_words: Counter[str] = Counter()
    for s in segments:
        if s.speaker and s.language == "de":
            de_words[s.speaker] += len(tokens(s.text))
    main = de_words.most_common(1)[0][0] if de_words else None
    for s in segments:
        role: Role = "student"
        if teacher_cue(s.text):
            role = "teacher"
        elif main and s.speaker and s.speaker != main:
            role = "other" if s.language == "de" else "teacher"
        s.role = role
        s.graded = s.role == "student" and s.language == "de" and len(tokens(s.text)) > 0
    return segments


def compute_stats(analysis: Analysis, duration: float) -> Stats:
    graded = [s for s in analysis.segments if s.graded]
    words = sum(len(s.words) if s.words else len(s.text.split()) for s in graded)
    secs = sum(max(0.0, s.end - s.start) for s in graded)
    return Stats(
        duration=round(duration, 2), student_words=words, student_speech_seconds=round(secs, 2),
        speech_ratio=round(secs / duration, 3) if duration > 0 else 0.0,
        graded_segments=len(graded),
        teacher_segments=sum(s.role == "teacher" for s in analysis.segments),
        french_segments=sum(s.language == "fr" for s in analysis.segments),
    )
