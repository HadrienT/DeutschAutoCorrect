"""LLM correctors (Claude, or any OpenAI-compatible server): structured JSON output over the
faithful transcript."""
from __future__ import annotations

import copy
import json
import re
from typing import Any

from ...models import DetectedError, Segment
from .base import locate, norm, seg_words

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

SUBTYPES = ["case", "gender", "word_order", "agreement", "preposition", "article", "negation",
            "plural", "person_ending", "auxiliary", "participle", "tense", "separable_verb", "modal",
            "irregular", "wrong_word", "french_word", "false_friend", "invented_word",
            "missing_word", "other"]
# Smaller local models drift without a closed list (French labels, free text).
LOCAL_SCHEMA: dict[str, Any] = copy.deepcopy(SCHEMA)
LOCAL_SCHEMA["properties"]["errors"]["items"]["properties"]["subtype"]["enum"] = SUBTYPES

CHUNK = 40
LOCAL_CHUNK = 4  # local models lose recall on long segment lists
LOW_CONF = 0.6
_CONF_MARK = re.compile(r"\{\d+%\}")  # low-confidence annotation, sometimes copied in quotes


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
            quote = _CONF_MARK.sub("", str(it.get("quote", "")))
            expected = _CONF_MARK.sub("", str(it.get("expected", "")))
            if norm(quote) == norm(expected):
                continue  # no-op "correction": the model flagged a correct phrase
            start, end = locate(seg, quote)
            cat = it["category"]
            if cat not in ("grammar", "conjugation", "vocabulary"):
                continue
            sev = it.get("severity", "minor")
            out.append(DetectedError(
                category=cat, subtype=str(it.get("subtype") or "other"),
                severity=sev if sev in ("minor", "major") else "minor",
                segment_id=seg.id, start=start, end=end, heard=quote,
                expected=expected, explanation=str(it.get("explanation", "")),
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


class OpenAICompatCorrector:
    """Corrector on a local OpenAI-compatible server (llama.cpp, vLLM, Ollama...)."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000/v1", model: str = "",
                 api_key: str = "", timeout: float = 300.0, chunk: int = LOCAL_CHUNK,
                 client: Any = None):
        if client is None:
            import httpx  # lazy
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            client = httpx.Client(base_url=base_url.rstrip("/") + "/", headers=headers,
                                  timeout=timeout)
        self._client = client
        self._model = model
        self._chunk = max(1, chunk)
        self.name = f"openai:{model or 'auto'}"

    def _served_model(self) -> str:
        """Model to request. The server may hot-swap models: refuse to grade with another one."""
        try:
            resp = self._client.get("models")
            resp.raise_for_status()
            served = [str(m["id"]) for m in resp.json()["data"]]
        except Exception as e:
            raise RuntimeError(f"Serveur LLM local injoignable ({e})") from e
        if not served:
            raise RuntimeError("Le serveur LLM local ne sert aucun modèle")
        if not self._model:
            return served[0]
        if self._model not in served:
            raise RuntimeError(f"Le serveur LLM local sert « {', '.join(served)} » et non "
                               f"« {self._model} »")
        return self._model

    def _call(self, model: str, segments: list[Segment]) -> str:
        resp = self._client.post("chat/completions", json={
            "model": model,
            "max_tokens": 8000,
            "temperature": 0,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": build_user_message(segments)}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "errors", "strict": True, "schema": LOCAL_SCHEMA}},
        })
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        if choice.get("finish_reason") == "length":
            raise RuntimeError("Réponse du correcteur tronquée (max_tokens)")
        return choice["message"].get("content") or ""

    def correct(self, segments: list[Segment]) -> list[DetectedError]:
        if not segments:
            return []
        model = self._served_model()
        out: list[DetectedError] = []
        for i in range(0, len(segments), self._chunk):
            chunk = segments[i:i + self._chunk]
            out.extend(parse_errors(self._call(model, chunk), chunk))
        return out
