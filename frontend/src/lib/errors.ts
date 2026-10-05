import type { Category, DetectedError, Segment, Word } from "../api/types";

export const CATEGORIES: Category[] = ["pronunciation", "grammar", "conjugation", "vocabulary"];

export const CATEGORY_LABEL: Record<Category, string> = {
  grammar: "Grammaire",
  conjugation: "Conjugaison",
  vocabulary: "Vocabulaire",
  pronunciation: "Prononciation",
};

export const SUBTYPE_LABEL: Record<string, string> = {
  case: "Cas", gender: "Genre", word_order: "Ordre des mots", agreement: "Accord",
  preposition: "Préposition", article: "Article", negation: "Négation", plural: "Pluriel",
  person_ending: "Terminaison", auxiliary: "Auxiliaire", participle: "Participe passé",
  tense: "Temps", separable_verb: "Verbe séparable", modal: "Modal", irregular: "Verbe irrégulier",
  wrong_word: "Mot inadapté", french_word: "Mot français", false_friend: "Faux ami",
  invented_word: "Mot inventé", missing_word: "Mot manquant",
  ich_laut: "ch doux [ç]", ach_laut: "ch dur [x]", umlaut: "Umlaut ü/ö", h_aspire: "h expiré",
  w_v: "w / v", z_laut: "z = [ts]", ei_ie: "ei / ie", sch_laut: "sch [ʃ]",
  auslautverhaertung: "Durcissement final", schwa_final: "-e final", phoneme_mismatch: "Son différent",
  unclear: "Peu clair", other: "Autre",
};

export const SOURCE_LABEL: Record<string, string> = {
  llm: "IA", rules: "Règles", phonemes: "Phonèmes", asr_confidence: "Confiance ASR", manual: "Manuel",
};

export const subtypeLabel = (s: string) => SUBTYPE_LABEL[s] ?? s.replace(/_/g, " ");

export function groupByCategory(errors: DetectedError[]): Record<Category, DetectedError[]> {
  const out: Record<Category, DetectedError[]> = { pronunciation: [], grammar: [], conjugation: [], vocabulary: [] };
  for (const e of [...errors].sort((a, b) => a.start - b.start)) out[e.category].push(e);
  return out;
}

/** Low-confidence, unconfirmed detections: shown as "à vérifier". */
export const needsReview = (e: DetectedError) => e.status === "pending" && e.confidence < 0.5;

/** Errors counting towards the grade (client-side hint; the server is authoritative). */
export const isActive = (e: DetectedError) => e.status !== "rejected";

export function nextError(errors: DetectedError[], t: number, dir: 1 | -1): DetectedError | undefined {
  const sorted = [...errors].sort((a, b) => a.start - b.start);
  if (dir === 1) return sorted.find((e) => e.start > t + 0.05) ?? sorted[0];
  return [...sorted].reverse().find((e) => e.start < t - 0.5) ?? sorted[sorted.length - 1];
}

/** Indices of words of a segment overlapping the error's time span. */
export function wordsOfError(seg: Segment, e: DetectedError): number[] {
  const idx: number[] = [];
  seg.words.forEach((w: Word, i) => {
    if (Math.min(w.end, e.end) - Math.max(w.start, e.start) > 0.01) idx.push(i);
  });
  return idx;
}

export function stageLabel(stage: string): string {
  return ({
    queued: "En attente", audio: "Préparation de l'audio", asr: "Transcription fidèle",
    segments: "Langue et locuteurs", pronunciation: "Prononciation", correction: "Correction",
    merge: "Consolidation", done: "Terminé", failed: "Échec",
  } as Record<string, string>)[stage] ?? stage;
}

export const STAGES = ["audio", "asr", "segments", "pronunciation", "correction", "merge"];
