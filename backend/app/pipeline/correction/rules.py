"""Offline rule-based corrector: a small, high-precision net used without an LLM.

It only flags patterns that are unambiguous for collège-level German; the LLM corrector is
far more complete. Every rule returns DetectedError objects anchored on the faulty words.
"""
from __future__ import annotations

import re

from ...models import DetectedError, Segment, Word
from .base import norm, seg_words

SEIN = {"ich": "bin", "du": "bist", "er": "ist", "es": "ist", "wir": "sind", "ihr": "seid"}
HABEN = {"ich": "habe", "du": "hast", "er": "hat", "es": "hat", "wir": "haben", "ihr": "habt"}
ALL_SEIN = {"bin", "bist", "ist", "sind", "seid"}
ALL_HABEN = {"habe", "hast", "hat", "haben", "habt"}
HABEN_TO_SEIN = {"habe": "bin", "hast": "bist", "hat": "ist", "haben": "sind", "habt": "seid"}
MOTION = set("""gegangen gefahren gekommen geflogen gelaufen gereist geschwommen gewesen geblieben
gestiegen gerannt gesprungen aufgestanden abgefahren angekommen ausgegangen eingestiegen
umgezogen""".split())
NOT_VERBS = set("""einen keinen meinen deinen seinen unseren diesen jeden wegen neben hinten oben unten
außen innen vorgestern gestern morgen abend""".split())
PRONOUNS = {"ich", "du", "er", "sie", "es", "wir", "ihr", "man"}
ADV_START = set("""heute morgen gestern dann danach jetzt abends morgens manchmal oft später zuerst
hier dort leider normalerweise nachmittags vormittags""".split())
SUBORDINATORS = {"weil", "dass", "ob", "wenn", "damit", "obwohl"}
FINITE = ALL_SEIN | ALL_HABEN | {"kann", "kannst", "muss", "musst", "will", "willst", "möchte",
                                  "soll", "darf", "wird", "wurde"}
DAT_PREPS = {"mit", "bei", "von", "zu", "nach", "aus", "seit"}
POSSESSIVES = {"mein", "meine", "dein", "deine", "sein", "seine", "ihr", "ihre", "unser", "unsere",
               "euer", "eure"}
FR_TOKENS = set("""et mais très avec pour je suis est sont amusant chocolat donc alors oui parce
beaucoup voilà difficile facile frère soeur maison école""".split())

GENDER = {}
for g, nouns in {
    "m": "bruder vater hund tisch freund lehrer stuhl apfel rucksack tag film park garten computer "
         "fußball kaffee sport onkel sohn kuchen",
    "f": "mutter schwester schule katze familie stadt wohnung tasche freundin lehrerin hausaufgabe "
         "woche pizza musik farbe uhr tante tochter küche",
    "n": "kino buch haus auto heft zimmer wasser mädchen kind fahrrad handy geschenk spiel essen "
         "wochenende eis",
}.items():
    for n in nouns.split():
        GENDER[n] = g
DEF = {"m": "der", "f": "die", "n": "das"}
INDEF = {"m": "ein", "f": "eine", "n": "ein"}


def _cap(noun_raw: str) -> str:
    return re.sub(r"[^\wäöüÄÖÜß]", "", noun_raw)


class _Ctx:
    def __init__(self, seg: Segment):
        self.seg = seg
        self.words: list[Word] = seg_words(seg)
        self.n = [norm(w.text) for w in self.words]
        self.raw = [re.sub(r"[.,;:!?]+$", "", w.text) for w in self.words]
        self.errors: list[DetectedError] = []
        self.consumed: set[int] = set()

    def clause_end(self, i: int) -> int:
        """Index of the last token of the clause/sentence containing token i."""
        for j in range(i, len(self.words)):
            if re.search(r"[,;:.!?]$", self.words[j].text):
                return j
        return len(self.words) - 1

    def is_sentence_start(self, i: int) -> bool:
        return i == 0 or bool(re.search(r"[.!?]$", self.words[i - 1].text))

    def add(self, i: int, j: int, category: str, subtype: str, severity: str, heard: str,
            expected: str, explanation: str, confidence: float = 0.85) -> None:
        self.errors.append(DetectedError(
            category=category, subtype=subtype, severity=severity,  # type: ignore[arg-type]
            segment_id=self.seg.id, start=self.words[i].start, end=self.words[j].end, heard=heard,
            expected=expected, explanation=explanation, confidence=confidence, source="rules"))
        self.consumed.update(range(i, j + 1))

    def span(self, i: int, j: int) -> str:
        return " ".join(self.raw[i:j + 1])


def _rule_agreement(c: _Ctx) -> None:
    for i, t in enumerate(c.n[:-1]):
        if t not in PRONOUNS | {"sie"}:
            continue
        j, v = i + 1, c.n[i + 1]
        if t in HABEN and v in ALL_HABEN and v != HABEN[t] and not (t == "sie"):
            c.add(i, j, "conjugation", "person_ending", "minor", c.span(i, j),
                  f"{t} {HABEN[t]}",
                  f"Avec « {t} », « haben » se conjugue « {HABEN[t]} ».")
        elif t in SEIN and v in ALL_SEIN and v != SEIN[t]:
            c.add(i, j, "conjugation", "person_ending", "minor", c.span(i, j), f"{t} {SEIN[t]}",
                  f"Avec « {t} », « sein » se conjugue « {SEIN[t]} ».")
        elif (c.raw[j][:1].islower() and v not in NOT_VERBS and v not in FINITE
              and len(v) > 4 and v.endswith(("en", "ern"))):
            stem = v[:-2] if v.endswith("en") else v[:-1]
            if t == "ich":
                new = v[:-1]
                rule = "à la 1re personne du singulier le verbe se termine par « -e »"
            elif t == "du":
                new = stem + ("t" if stem[-1] in "sßzx" else "est" if stem[-1] in "td" else "st")
                new = new if v.endswith("en") else v
                rule = "avec « du » le verbe se termine par « -st »"
            elif t in {"er", "es"}:
                new = stem + ("et" if stem[-1] in "td" else "t")
                rule = "avec « er/es » le verbe se termine par « -t »"
            elif t == "ihr":
                new = stem + ("et" if stem[-1] in "td" else "t")
                rule = "avec « ihr » le verbe se termine par « -t »"
            else:
                continue
            if new != v:
                c.add(i, j, "conjugation", "person_ending", "minor", c.span(i, j), f"{t} {new}",
                      f"Verbe à l'infinitif après le sujet « {t} » : {rule} ({v} → {new}).")


def _rule_auxiliary(c: _Ctx) -> None:
    n = len(c.n)
    for i in range(n):
        if c.n[i] in HABEN_TO_SEIN:
            end = c.clause_end(i)
            start = i
            while start > 0 and not c.is_sentence_start(start):
                start -= 1
            part = next((k for k in range(start, max(end, i) + 1) if c.n[k] in MOTION), None)
            if part is not None:
                new = HABEN_TO_SEIN[c.n[i]]
                c.add(i, i, "conjugation", "auxiliary", "major", c.raw[i], new,
                      f"« {c.n[part]} » (verbe de mouvement) se conjugue avec « sein » au parfait : "
                      f"« {new} {c.n[part]} ».")


def _dat_form(det: str, gender: str) -> str | None:
    d = det.lower()
    if d in {"der", "die", "das"}:
        return "der" if gender == "f" else "dem"
    if d in {"ein", "eine"}:
        return "einer" if gender == "f" else "einem"
    if d in POSSESSIVES:
        stem = d[:-1] if d.endswith("e") and d not in {"eure"} else d
        stem = "eur" if d in {"euer", "eure"} else stem
        return stem + ("er" if gender == "f" else "em")
    return None


def _rule_dative(c: _Ctx) -> None:
    for i, t in enumerate(c.n):
        if t not in DAT_PREPS:
            continue
        k = i + 1
        while k + 1 < len(c.n):
            det, noun = c.n[k], c.n[k + 1]
            g = GENDER.get(noun)
            exp = _dat_form(det, g) if g else None
            if exp is None:
                break
            if det != exp:
                c.add(k, k + 1, "grammar", "case", "minor", c.span(k, k + 1),
                      f"{exp} {_cap(c.raw[k + 1])}",
                      f"Après « {t} », il faut le datif : « {exp} {_cap(c.raw[k + 1])} ».")
            else:
                c.consumed.update({k, k + 1})
            k += 2
            if k < len(c.n) and c.n[k] == "und":
                k += 1
            else:
                break


def _rule_gender(c: _Ctx) -> None:
    for i, t in enumerate(c.n[:-1]):
        if i in c.consumed or i + 1 in c.consumed:
            continue
        g = GENDER.get(c.n[i + 1])
        if not g:
            continue
        if t in {"der", "die", "das"}:
            ok_here = t == DEF[g] or (t == "der" and g == "f")  # "der" = dative/genitive feminine
            exp = DEF[g]
        elif t in {"ein", "eine"}:
            ok_here = t == INDEF[g]
            exp = INDEF[g]
        else:
            continue
        if not ok_here:
            c.add(i, i + 1, "grammar", "gender", "minor", c.span(i, i + 1),
                  f"{exp} {_cap(c.raw[i + 1])}",
                  f"« {_cap(c.raw[i + 1])} » est {'masculin' if g == 'm' else 'féminin' if g == 'f' else 'neutre'}"
                  f" : « {exp} {_cap(c.raw[i + 1])} ».")


def _rule_v2(c: _Ctx) -> None:
    for i in range(len(c.n)):
        if not c.is_sentence_start(i):
            continue
        ln = 2 if c.n[i] in {"am", "im"} else 1 if c.n[i] in ADV_START else 0
        if not ln:
            continue
        s, p, v = i + ln - 1, i + ln, i + ln + 1
        if v < len(c.n) and c.n[p] in PRONOUNS and c.n[v] not in {"und", "aber"}:
            c.add(i, v, "grammar", "word_order", "major", c.span(i, v),
                  f"{c.span(i, s)} {c.raw[v]} {c.raw[p]}",
                  "Le verbe conjugué est toujours en 2e position : après un complément de temps/lieu "
                  "en tête de phrase, le verbe passe avant le sujet.")


def _rule_verb_final(c: _Ctx) -> None:
    for i, t in enumerate(c.n):
        if t in SUBORDINATORS and i + 2 < len(c.n):
            if c.n[i + 1] in PRONOUNS and c.n[i + 2] in FINITE:
                end = c.clause_end(i)
                if end > i + 2:
                    rest = [re.sub(r"[.,;:!?]+$", "", w.text) for w in c.words[i + 3:end + 1]]
                    tail = c.words[end].text
                    punct = re.search(r"[.,;:!?]+$", tail)
                    exp = " ".join([c.raw[i], c.raw[i + 1], *rest, c.raw[i + 2]]) + (punct.group(0) if punct else "")
                    c.add(i, end, "grammar", "word_order", "major", c.span(i, end), exp,
                          f"Après « {c.raw[i]} », la phrase est une subordonnée : "
                          "le verbe conjugué part à la fin.")


def _rule_french(c: _Ctx) -> None:
    i = 0
    while i < len(c.n):
        if c.n[i] in FR_TOKENS:
            j = i
            while j + 1 < len(c.n) and c.n[j + 1] in FR_TOKENS:
                j += 1
            c.add(i, j, "vocabulary", "french_word", "minor", c.span(i, j), "",
                  "Mot(s) français dans une phrase allemande : cherchez l'équivalent allemand.",
                  confidence=0.8)
            i = j + 1
        else:
            i += 1


def correct_segment(seg: Segment) -> list[DetectedError]:
    c = _Ctx(seg)
    for rule in (_rule_french, _rule_dative, _rule_agreement, _rule_auxiliary, _rule_verb_final,
                 _rule_v2, _rule_gender):
        rule(c)
    return c.errors


class RulesCorrector:
    name = "rules"

    def correct(self, segments: list[Segment]) -> list[DetectedError]:
        out: list[DetectedError] = []
        for s in segments:
            out.extend(correct_segment(s))
        return out
