export type Category = "grammar" | "conjugation" | "vocabulary" | "pronunciation";
export type Severity = "minor" | "major";
export type ErrorStatus = "pending" | "confirmed" | "rejected";
export type Role = "student" | "teacher" | "other";
export type Language = "de" | "fr" | "other";

export interface Word { text: string; start: number; end: number; prob: number }
export interface Segment {
  id: string; start: number; end: number; text: string; language: Language; role: Role;
  speaker: string | null; graded: boolean; words: Word[]; no_speech_prob: number;
}
export interface DetectedError {
  id: string; category: Category; subtype: string; severity: Severity; segment_id: string;
  start: number; end: number; heard: string; expected: string; explanation: string;
  confidence: number; source: string; status: ErrorStatus; note: string;
}
export interface Stats {
  duration: number; student_words: number; student_speech_seconds: number; speech_ratio: number;
  graded_segments: number; teacher_segments: number; french_segments: number;
}
export interface Analysis {
  segments: Segment[]; errors: DetectedError[]; stats: Stats;
  engines: Record<string, string>; warnings: string[];
}
export interface VolumeTier { min_words: number; points: number }
export interface Criterion {
  id: string; label: string; kind: "errors" | "volume" | "manual"; category: Category | null;
  max_points: number; penalty_minor: number; penalty_major: number; cap_deduction: number | null;
  tiers: VolumeTier[];
}
export interface Rubric {
  id: number | null; name: string; total_points: number; rounding: "none" | "half" | "integer";
  repeat_policy: "count_all" | "once_per_subtype" | "once_per_expected"; min_confidence: number;
  criteria: Criterion[];
}
export interface CriterionGrade {
  id: string; label: string; kind: Criterion["kind"]; earned: number; max: number; detail: string;
  error_count: number;
}
export interface Grade {
  raw_total: number; raw_max: number; total: number; out_of: number; criteria: CriterionGrade[];
}
export interface RecordingSummary {
  id: string; title: string; student_name: string; filename: string;
  status: "queued" | "processing" | "done" | "failed"; stage: string; progress: number;
  error: string; duration: number; created_at: number; rubric_id: number | null; grade: Grade | null;
}
export interface RecordingDetail extends RecordingSummary {
  analysis: Analysis | null; rubric: Rubric; manual: Record<string, number>;
}
export interface Health {
  status: string; engines: Record<string, string>; degraded: boolean; notices: string[];
}
export interface EditResult { analysis: Analysis; grade: Grade; warnings?: string[]; created?: string }
