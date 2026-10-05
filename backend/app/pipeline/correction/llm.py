"""Claude-based corrector: structured JSON output over the faithful transcript."""
from __future__ import annotations

import json
from typing import Any

from ...models import DetectedError, Segment
from .base import locate, seg_words

SYSTEM_PROMPT = """\
Tu es un professeur d'allemand (collège, niveaux A1–B1) qui corrige une évaluation orale.

Le transcript que tu reçois est FIDÈLE : il a été produit par reconnaissance vocale et les erreurs \
de l'élève ont volontairement été conservées. Ne les corrige pas en silence : relève-les.

Relève UNIQUEMENT ces catégories :
- grammar : cas (case), genre (gender), ordre des mots (word_order), accord (agreement), \
préposition (preposition), article (article), négation (negation), pluriel (plural), autre (other)
- conjugation : terminaison/personne (person_ending), auxiliaire (auxiliary), participe passé \
(participle), temps (tense), verbe séparable (separable_verb), verbe de modalité (modal), \
verbe irrégulier (irregular), autre (other)
- vocabulary : mot inadapté (wrong_word), mot français (french_word), faux ami (false_friend), \
mot inventé (invented_word), mot manquant (missing_word), autre (other)

Ne signale PAS : la prononciation (traitée ailleurs), l'orthographe, la ponctuation, les \
majuscules (artefacts de la transcription), les hésitations, ni les choix de style. \
N'invente pas d'erreur : une phrase correcte ne donne aucune entrée. Les mots suivis de {NN%} ont \
été reconnus avec une faible confiance : en cas de doute sur ces mots, baisse `confidence` ou \
abstiens-toi.

Pour chaque erreur :
- segment_id : l'identifiant du segment ;
- quote : le plus petit groupe de mots fautifs, COPIÉ EXACTEMENT du transcript ;
- expected : la forme correcte pour ce groupe de mots ;
- severity : "major" si l'erreur gêne la compréhension ou porte sur une structure fondamentale du \
niveau (auxiliaire, ordre des mots, verbe absent), sinon "minor" ;
- explanation : 1 à 2 phrases en français, simples, qui donnent la règle ;
- confidence : de 0 à 1.
Une même faute répétée dans plusieurs phrases est signalée à chaque occurrence.
"""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string"},
                    "quote": {"type": "string"},
                    "category": {"type": "string", "enum": ["grammar", "conjugation", "vocabulary"]},
                    "subtype": {"type": "string"},
                    "severity": {"type": "string", "enum": ["minor", "major"]},
                    "expected": {"type": "string"},
                    "explanation": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["segment_id", "quote", "category", "subtype", "severity", "expected",
                             "explanation", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["errors"],
    "additionalProperties": False,
}

CHUNK = 40
LOW_CONF = 0.6


def render_segment(seg: Segment) -> str:
    parts = []
    for w in seg_words(seg):
        parts.append(f"{w.text}{{{round(w.prob * 100)}%}}" if w.prob < LOW_CONF else w.text)
    return f"[{seg.id}] {' '.join(parts)}"


def build_user_message(segments: list[Segment]) -> str:
    lines = "\n".join(render_segment(s) for s in segments)
    return ("Voici les segments de parole de l'élève (allemand), dans l'ordre chronologique.\n\n"
            f"{lines}\n\nRelève les erreurs.")


def parse_errors(raw: str, segments: list[Segment]) -> list[DetectedError]:
    try:
        data = json.loads(raw)
        items = data["errors"]
    except (ValueError, KeyError, TypeError):
        raise ValueError("Réponse du correcteur illisible (JSON invalide)") from None
    by_id = {s.id: s for s in segments}
    out: list[DetectedError] = []
    for it in items:
        try:
            seg = by_id.get(str(it["segment_id"]))
            if seg is None:
                continue
            start, end = locate(seg, str(it.get("quote", "")))
            cat = it["category"]
            if cat not in ("grammar", "conjugation", "vocabulary"):
                continue
            sev = it.get("severity", "minor")
            out.append(DetectedError(
                category=cat, subtype=str(it.get("subtype") or "other"),
                severity=sev if sev in ("minor", "major") else "minor",
                segment_id=seg.id, start=start, end=end, heard=str(it.get("quote", "")),
                expected=str(it.get("expected", "")), explanation=str(it.get("explanation", "")),
                confidence=min(1.0, max(0.0, float(it.get("confidence", 0.7)))), source="llm"))
        except (KeyError, TypeError, ValueError):
            continue
    return out


class AnthropicCorrector:
    def __init__(self, model: str = "claude-opus-5-5", effort: str = "medium", client: Any = None):
        if client is None:
            import anthropic  # lazy
            client = anthropic.Anthropic()
        self._client = client
        self._model = model
        self._effort = effort
        self.name = f"anthropic:{model}"

    def _call(self, segments: list[Segment]) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            output_config={"effort": self._effort,
                           "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": build_user_message(segments)}],
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("Le modèle a refusé de traiter cette requête")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("Réponse du correcteur tronquée (max_tokens)")
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    def correct(self, segments: list[Segment]) -> list[DetectedError]:
        out: list[DetectedError] = []
        for i in range(0, len(segments), CHUNK):
            chunk = segments[i:i + CHUNK]
            out.extend(parse_errors(self._call(chunk), chunk))
        return out
