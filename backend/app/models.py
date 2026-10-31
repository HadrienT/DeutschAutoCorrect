"""Domain models shared by pipeline, scoring and API."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["de", "fr", "other"]
Role = Literal["student", "teacher", "other"]
# "text": fidelity to a reference text (recitation / reading): omitted or wrong words
ErrorCategory = Literal["grammar", "conjugation", "vocabulary", "pronunciation", "text"]
Severity = Literal["minor", "major"]
ErrorStatus = Literal["pending", "confirmed", "rejected"]
CATEGORIES: tuple[ErrorCategory, ...] = ("grammar", "conjugation", "vocabulary", "pronunciation",
                                         "text")


class Word(BaseModel):
    text: str
    start: float
    end: float
    prob: float = 1.0


class Segment(BaseModel):
    id: str
    start: float
    end: float
    text: str
    language: Language = "de"
    role: Role = "student"
    speaker: str | None = None
    graded: bool = True
    words: list[Word] = Field(default_factory=list)
    no_speech_prob: float = 0.0


class DetectedError(BaseModel):
    id: str = ""
    category: ErrorCategory
    subtype: str = "other"
    severity: Severity = "minor"
    segment_id: str = ""
    start: float
    end: float
    heard: str = ""
    expected: str = ""
    explanation: str = ""
    confidence: float = 0.7
    source: str = "llm"  # llm | rules | phonemes | asr_confidence | reference | manual
    status: ErrorStatus = "pending"
    note: str = ""


class Stats(BaseModel):
    duration: float = 0.0
    student_words: int = 0
    student_speech_seconds: float = 0.0
    speech_ratio: float = 0.0
    graded_segments: int = 0
    teacher_segments: int = 0
    french_segments: int = 0
    # Rhythm signals (0 / empty on analyses made before they existed)
    words_per_minute: float = 0.0
    pauses: list[float] = Field(default_factory=list)  # silences >= MIN_PAUSE between student words


class Analysis(BaseModel):
    segments: list[Segment] = Field(default_factory=list)
    errors: list[DetectedError] = Field(default_factory=list)
    stats: Stats = Field(default_factory=Stats)
    engines: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# ---- Rubric & grade -------------------------------------------------------------------------

RepeatPolicy = Literal["count_all", "once_per_subtype", "once_per_expected"]
CriterionKind = Literal["errors", "volume", "manual", "rhythm"]
Rounding = Literal["none", "half", "integer"]


class VolumeTier(BaseModel):
    min_words: int = Field(ge=0)
    points: float = Field(ge=0)


class Criterion(BaseModel):
    id: str
    label: str
    kind: CriterionKind = "errors"
    category: ErrorCategory | None = None
    max_points: float = Field(ge=0)
    penalty_minor: float = Field(default=0.5, ge=0)
    penalty_major: float = Field(default=1.0, ge=0)
    cap_deduction: float | None = Field(default=None, ge=0)
    tiers: list[VolumeTier] = Field(default_factory=list)
    # Coefficient in the weighted mean of criteria (each taken as earned/max). None = max_points,
    # i.e. the plain sum of points.
    weight: float | None = Field(default=None, ge=0)
    # kind "rhythm": suggested mark = max − pause_penalty per pause longer than pause_seconds
    # − slow_penalty when the speech rate is under min_wpm. The teacher can override it.
    pause_seconds: float = Field(default=1.5, gt=0)
    pause_penalty: float = Field(default=0.5, ge=0)
    min_wpm: float = Field(default=60, ge=0)
    slow_penalty: float = Field(default=0.5, ge=0)


class Rubric(BaseModel):
    id: int | None = None
    name: str
    total_points: float = Field(default=20, gt=0)
    rounding: Rounding = "half"
    repeat_policy: RepeatPolicy = "once_per_expected"
    # Unconfirmed errors below this confidence do not count (confirmed ones always do).
    min_confidence: float = Field(default=0.5, ge=0, le=1)
    criteria: list[Criterion]


class CriterionGrade(BaseModel):
    id: str
    label: str
    kind: CriterionKind
    earned: float
    max: float
    detail: str = ""
    error_count: int = 0
    weight: float = 0.0
    suggested: float | None = None  # kind "rhythm": automatic suggestion, even when overridden


class Grade(BaseModel):
    raw_total: float
    raw_max: float
    total: float
    out_of: float
    criteria: list[CriterionGrade]


def default_rubric() -> Rubric:
    return Rubric(
        name="Barème standard /20",
        total_points=20,
        rounding="half",
        repeat_policy="once_per_expected",
        criteria=[
            Criterion(id="pron", label="Prononciation", category="pronunciation", max_points=5,
                      penalty_minor=0.5, penalty_major=1),
            Criterion(id="gram", label="Grammaire", category="grammar", max_points=5,
                      penalty_minor=0.5, penalty_major=1),
            Criterion(id="conj", label="Conjugaison", category="conjugation", max_points=3,
                      penalty_minor=0.5, penalty_major=1),
            Criterion(id="voc", label="Vocabulaire", category="vocabulary", max_points=3,
                      penalty_minor=0.5, penalty_major=1),
            Criterion(id="vol", label="Quantité de langue produite", kind="volume", max_points=2,
                      tiers=[VolumeTier(min_words=0, points=0), VolumeTier(min_words=20, points=1),
                             VolumeTier(min_words=40, points=2)]),
            Criterion(id="flu", label="Aisance / communication (saisie enseignant)", kind="manual",
                      max_points=2),
        ],
    )


def recitation_rubric() -> Rubric:
    """Recitation / reading against a reference text: two marks out of 20 and a rhythm mark."""
    return Rubric(
        name="Récitation / lecture (texte de référence)",
        total_points=20,
        rounding="half",
        repeat_policy="count_all",
        criteria=[
            Criterion(id="text", label="Texte (mots oubliés ou erronés)", category="text",
                      max_points=20, penalty_minor=2, penalty_major=2),
            Criterion(id="pron", label="Prononciation", category="pronunciation", max_points=20,
                      penalty_minor=2, penalty_major=2),
            Criterion(id="rhythm", label="Rythme", kind="rhythm", max_points=2),
        ],
    )
