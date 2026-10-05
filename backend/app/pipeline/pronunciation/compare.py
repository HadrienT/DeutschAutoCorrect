"""Weighted phoneme comparison tuned for French-speaking learners of German. Pure functions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

DIGRAPHS = ["tʃ", "dʒ", "ts", "pf", "aɪ", "aʊ", "ɔɪ", "ɔʏ", "ai", "au", "oi"]
_STRIP = re.compile(r"[ˈˌːˑ‿͡ ̯̩̥̬̃ʰʲˠ.͜͡|]")
_ALIASES = {"ʁ": "r", "ʀ": "r", "ɾ": "r", "ɐ": "ə", "ɚ": "ə", "ɑ": "a", "ɡ": "g", "ɫ": "l",
            "ai": "aɪ", "au": "aʊ", "oi": "ɔɪ", "ɔʏ": "ɔɪ", "ɜ": "ə", "ʌ": "ə", "ɘ": "ə"}
R_CLASS = {"r"}
VOWELS = set("aeiouyøœɛɪɔʊʏəæ") | {"aɪ", "aʊ", "ɔɪ"}

# cheap substitutions (allophones / near-equivalents that a CTC recogniser blurs)
NEAR = {frozenset(p): c for p, c in [
    (("ə", "ɛ"), 0.4), (("ə", "ɪ"), 0.4), (("ə", "a"), 0.5), (("ɛ", "e"), 0.5), (("ɔ", "o"), 0.5),
    (("ɪ", "i"), 0.5), (("ʊ", "u"), 0.5), (("ç", "x"), 0.5), (("s", "z"), 0.6), (("t", "d"), 0.6),
    (("k", "g"), 0.6), (("p", "b"), 0.6), (("f", "v"), 0.7), (("ɛ", "a"), 0.7), (("ʊ", "ɔ"), 0.7),
    (("ʏ", "y"), 0.4), (("œ", "ø"), 0.4),
]}


def tokenize(ph: str | list[str]) -> list[str]:
    """Normalise an IPA string (or token list) into comparison tokens."""
    if isinstance(ph, list):
        toks = [_ALIASES.get(_STRIP.sub("", t), _STRIP.sub("", t)) for t in ph]
        return [t for t in toks if t]
    s = _STRIP.sub("", ph)
    out: list[str] = []
    i = 0
    while i < len(s):
        two = s[i:i + 2]
        if two in DIGRAPHS:
            out.append(two)
            i += 2
        else:
            out.append(s[i])
            i += 1
    return [_ALIASES.get(t, t) for t in out]


def sub_cost(a: str, b: str) -> float:
    if a == b:
        return 0.0
    return NEAR.get(frozenset((a, b)), 1.0)


@dataclass
class Op:
    kind: str  # match | sub | ins | del
    exp: str | None
    obs: str | None
    exp_idx: int  # position in expected sequence (for ins: position it was inserted before)


@dataclass
class Issue:
    subtype: str
    exp: str
    obs: str
    explanation: str
    salient: bool = True


@dataclass
class WordComparison:
    distance: float
    per: float
    ops: list[Op] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


def align(exp: list[str], obs: list[str]) -> tuple[float, list[Op]]:
    n, m = len(exp), len(obs)
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        D[i][0] = float(i)
    for j in range(1, m + 1):
        D[0][j] = float(j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1,
                          D[i - 1][j - 1] + sub_cost(exp[i - 1], obs[j - 1]))
    ops: list[Op] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and abs(D[i][j] - (D[i - 1][j - 1] + sub_cost(exp[i - 1], obs[j - 1]))) < 1e-9:
            kind = "match" if exp[i - 1] == obs[j - 1] else "sub"
            ops.append(Op(kind, exp[i - 1], obs[j - 1], i - 1))
            i, j = i - 1, j - 1
        elif i > 0 and abs(D[i][j] - (D[i - 1][j] + 1)) < 1e-9:
            ops.append(Op("del", exp[i - 1], None, i - 1))
            i -= 1
        else:
            ops.append(Op("ins", None, obs[j - 1], i))
            j -= 1
    ops.reverse()
    return D[n][m], ops


def _classify(op: Op, exp: list[str]) -> Issue | None:
    e, o, last = op.exp, op.obs, op.exp_idx == len(exp) - 1
    if e == "ç" and o != "ç":
        return Issue("ich_laut", e, o or "", "Le « ch » après i, e, ä, ö, ü, ei ou une consonne se "
                     "prononce [ç] (souffle doux contre le palais), pas [k] ni [ʃ].")
    if e == "x" and o != "x":
        return Issue("ach_laut", e, o or "", "Le « ch » après a, o, u, au se prononce [x] "
                     "(son râpé au fond de la gorge), pas [k] ni [ʃ].")
    if e in {"y", "ʏ", "ø", "œ"} and o in {"i", "u", "e", "o", "ɪ", "ʊ", "ɛ", "ɔ", "ə", "a"}:
        return Issue("umlaut", e, o or "", "Les voyelles ü/ö s'arrondissent : prononcez [i]/[e] "
                     "en arrondissant fortement les lèvres.")
    if e == "h" and op.kind == "del":
        return Issue("h_aspire", e, "", "Le « h » allemand en début de mot est expiré (souffle), "
                     "il ne doit pas être muet comme en français.")
    if (e in {"v", "f"} and o in {"v", "f", "w"}) and op.kind == "sub":
        return Issue("w_v", e, o or "", "En allemand « w » se lit [v] et « v » se lit souvent [f] "
                     "(Vater, vier).")
    if e == "ts" and o in {"s", "z", "t", "ʃ", "ʒ"}:
        return Issue("z_laut", e, o or "", "« z » et « tz » se prononcent [ts] (t + s collés), "
                     "pas [s] ni [z].")
    if e == "aɪ" and o in {"i", "e", "ɪ", "ɛ", "a"}:
        return Issue("ei_ie", e, o or "", "« ei » se prononce [aɪ] (comme « aï »), « ie » se "
                     "prononce [i].")
    if e == "i" and o in {"aɪ"}:
        return Issue("ei_ie", e, o or "", "« ie » se prononce [i] (long) ; « ei » se prononce [aɪ].")
    if e == "ʃ" and o in {"s", "sk", "k", "ʒ", "tʃ"}:
        return Issue("sch_laut", e, o or "", "« sch » (et « s » devant t/p en début de mot) se "
                     "prononce [ʃ] comme « ch » en français.")
    if last and e in {"t", "k", "p", "s", "f"} and o in {"d", "g", "b", "z", "v"}:
        return Issue("auslautverhaertung", e, o or "", "En fin de mot les consonnes sonores se "
                     "durcissent : « -d » → [t], « -g » → [k], « -b » → [p].", salient=True)
    if last and e == "ə" and op.kind == "del":
        return Issue("schwa_final", e, "", "Le « -e » final allemand se prononce [ə] "
                     "(voyelle brève et faible) : ne l'avalez pas.", salient=False)
    if e == "r" and op.kind == "del" and not last:
        return None
    if op.kind == "sub" and sub_cost(e or "", o or "") < 1.0:
        return None  # allophonic variation, not an error
    return Issue("phoneme_mismatch", e or "", o or "", "Le son attendu et le son entendu "
                 "diffèrent.", salient=False)


def compare_word(expected: str | list[str], observed: str | list[str]) -> WordComparison:
    exp, obs = tokenize(expected), tokenize(observed)
    if not exp:
        return WordComparison(0.0, 0.0)
    dist, ops = align(exp, obs)
    issues: list[Issue] = []
    for op in ops:
        if op.kind == "match":
            continue
        # ignore inserted schwa / r-class noise typical of CTC output
        if op.kind == "ins" and (op.obs in R_CLASS or op.obs == "ə"):
            continue
        iss = _classify(op, exp)
        if iss:
            issues.append(iss)
    return WordComparison(distance=dist, per=dist / len(exp), ops=ops, issues=issues)


def is_pronunciation_error(cmp: WordComparison, generic_per_threshold: float = 0.4) -> bool:
    if any(i.salient for i in cmp.issues):
        return True
    return cmp.per >= generic_per_threshold and any(
        i.subtype == "phoneme_mismatch" for i in cmp.issues)


def severity_of(cmp: WordComparison) -> str:
    salient = sum(i.salient for i in cmp.issues)
    return "major" if cmp.per >= 0.5 or salient >= 2 else "minor"
