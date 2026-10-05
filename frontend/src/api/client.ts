import type {
  DetectedError, EditResult, Grade, Health, RecordingDetail, RecordingSummary, Rubric,
} from "./types";

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* not json */ }
    throw new Error(msg || `Erreur ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export const api = {
  health: () => req<Health>("/api/health"),
  listRecordings: () => req<RecordingSummary[]>("/api/recordings"),
  getRecording: (id: string) => req<RecordingDetail>(`/api/recordings/${id}`),
  upload: (file: File, title: string, student: string, rubricId: number | null) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title);
    fd.append("student_name", student);
    if (rubricId != null) fd.append("rubric_id", String(rubricId));
    return req<RecordingSummary>("/api/recordings", { method: "POST", body: fd });
  },
  deleteRecording: (id: string) => req<void>(`/api/recordings/${id}`, { method: "DELETE" }),
  reanalyze: (id: string) => req<RecordingSummary>(`/api/recordings/${id}/reanalyze`, { method: "POST" }),
  peaks: (id: string, bins = 900) =>
    req<{ peaks: number[]; duration: number }>(`/api/recordings/${id}/peaks?bins=${bins}`),
  audioUrl: (id: string) => `/api/recordings/${id}/audio`,
  exportUrl: (id: string, fmt: "csv" | "json") => `/api/recordings/${id}/export.${fmt}`,
  patchError: (id: string, eid: string, patch: Partial<DetectedError>) =>
    req<EditResult>(`/api/recordings/${id}/errors/${eid}`, json("PATCH", patch)),
  deleteError: (id: string, eid: string) =>
    req<EditResult>(`/api/recordings/${id}/errors/${eid}`, { method: "DELETE" }),
  addError: (id: string, body: Partial<DetectedError>) =>
    req<EditResult>(`/api/recordings/${id}/errors`, json("POST", body)),
  patchSegment: (id: string, sid: string, patch: Record<string, unknown>) =>
    req<EditResult>(`/api/recordings/${id}/segments/${sid}`, json("PATCH", patch)),
  assignRubric: (id: string, body: { rubric_id?: number; manual?: Record<string, number> }) =>
    req<{ grade: Grade; rubric: Rubric; manual: Record<string, number> }>(
      `/api/recordings/${id}/rubric`, json("PUT", body)),
  listRubrics: () => req<Rubric[]>("/api/rubrics"),
  createRubric: (r: Rubric) => req<Rubric>("/api/rubrics", json("POST", r)),
  updateRubric: (r: Rubric) => req<Rubric>(`/api/rubrics/${r.id}`, json("PUT", r)),
  deleteRubric: (id: number) => req<void>(`/api/rubrics/${id}`, { method: "DELETE" }),
  preview: (recordingId: string, rubric: Rubric, manual?: Record<string, number>) =>
    req<Grade>("/api/grading/preview", json("POST", { recording_id: recordingId, rubric, manual })),
};
