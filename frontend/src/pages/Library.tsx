import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Health, RecordingSummary, Rubric } from "../api/types";
import { IconTrash, IconUpload } from "../components/Icons";
import { useToast } from "../components/Toast";
import { stageLabel } from "../lib/errors";
import { fmtNum, formatTime } from "../lib/time";

export function LibraryPage() {
  const toast = useToast();
  const [recs, setRecs] = useState<RecordingSummary[] | null>(null);
  const [rubrics, setRubrics] = useState<Rubric[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [title, setTitle] = useState("");
  const [student, setStudent] = useState("");
  const [rubricId, setRubricId] = useState<number | null>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => api.listRecordings().then(setRecs).catch((e) => toast(e.message, true)), [toast]);
  useEffect(() => { void refresh(); api.listRubrics().then(setRubrics).catch(() => {}); api.health().then(setHealth).catch(() => {}); }, [refresh]);
  const pending = recs?.some((r) => r.status === "queued" || r.status === "processing");
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => void refresh(), 1500);
    return () => clearInterval(t);
  }, [pending, refresh]);

  const upload = async (files: FileList | File[]) => {
    setBusy(true);
    try {
      for (const f of Array.from(files)) {
        await api.upload(f, files.length === 1 ? title : "", student, rubricId);
      }
      setTitle("");
      toast(`${files.length} enregistrement(s) envoyé(s)`);
      await refresh();
    } catch (e) { toast((e as Error).message, true); } finally { setBusy(false); }
  };

  return (
    <div className="page">
      {health?.degraded && (
        <div className="banner" style={{ marginBottom: 16 }}>
          Mode démonstration : {health.notices.length ? health.notices.join(" ") : "la transcription utilise un moteur factice (aucun modèle chargé)."} Voir le README pour activer Whisper et Claude.
        </div>
      )}
      <div className="hero">
        <div>
          <h1 style={{ fontSize: 30, marginBottom: 8 }}>Corrigez vos oraux d'allemand en quelques minutes</h1>
          <p className="muted" style={{ maxWidth: 520 }}>
            Déposez un enregistrement : transcription fidèle (erreurs conservées), détection des fautes de grammaire,
            conjugaison, vocabulaire et prononciation, avec timecodes cliquables, puis note automatique selon votre barème.
          </p>
          <div className="grid-3" style={{ marginTop: 18 }}>
            <label className="field">Titre<input type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Oral 3 — Ma famille" /></label>
            <label className="field">Élève<input type="text" value={student} onChange={(e) => setStudent(e.target.value)} placeholder="Léa M." /></label>
            <label className="field">Barème
              <select value={rubricId ?? ""} onChange={(e) => setRubricId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Par défaut</option>
                {rubrics.map((r) => <option key={r.id} value={r.id ?? ""}>{r.name}</option>)}
              </select></label>
          </div>
        </div>
        <div className={`dropzone ${over ? "over" : ""}`} role="button" tabIndex={0} aria-label="Déposer un fichier audio"
          onClick={() => input.current?.click()} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") input.current?.click(); }}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) void upload(e.dataTransfer.files); }}>
          <span style={{ width: 40, height: 40 }}><IconUpload /></span>
          <strong>{busy ? "Envoi en cours…" : "Glissez un enregistrement ici"}</strong>
          <span className="muted">ou cliquez pour parcourir — mp3, m4a, wav, ogg, mp4…</span>
          <input ref={input} type="file" accept="audio/*,video/mp4,video/webm" multiple className="sr-only" data-testid="file-input"
            onChange={(e) => { if (e.target.files?.length) void upload(e.target.files); e.target.value = ""; }} />
        </div>
      </div>

      <h2 style={{ fontSize: 18, marginBottom: 12 }}>Enregistrements</h2>
      {recs === null ? <div className="muted">Chargement…</div> : recs.length === 0
        ? <div className="card empty">Aucun enregistrement pour l'instant.</div>
        : <div className="rec-list">{recs.map((r) => <RecCard key={r.id} r={r} onDelete={async () => {
          if (confirm(`Supprimer « ${r.title} » ?`)) { await api.deleteRecording(r.id); void refresh(); }
        }} />)}</div>}
    </div>
  );
}

function RecCard({ r, onDelete }: { r: RecordingSummary; onDelete: () => void }) {
  const initial = (r.student_name || r.title).trim().charAt(0).toUpperCase() || "?";
  const date = new Date(r.created_at * 1000).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
  const proc = r.status === "queued" || r.status === "processing";
  return (
    <div className="card rec-card" data-testid="rec-card">
      <a href={`#/r/${r.id}`} className="avatar" aria-hidden="true" tabIndex={-1}>{initial}</a>
      <a href={`#/r/${r.id}`} style={{ color: "inherit", minWidth: 0 }}>
        <div style={{ fontWeight: 650, fontSize: 16 }}>{r.title}</div>
        <div className="muted" style={{ fontSize: 13 }}>
          {r.student_name && <>{r.student_name} · </>}{date}{r.duration > 0 && <> · <span className="mono">{formatTime(r.duration)}</span></>}
        </div>
        {proc && <div style={{ marginTop: 8 }}><div className="progress"><i style={{ width: `${r.progress}%` }} /></div>
          <span className="muted" style={{ fontSize: 12.5 }}>{stageLabel(r.stage)}…</span></div>}
        {r.status === "failed" && <div style={{ marginTop: 4 }}><span className="badge bad">Échec</span> <span className="muted" style={{ fontSize: 12.5 }}>{r.error}</span></div>}
        {r.grade && (
          <div className="mini-cats">
            {r.grade.criteria.filter((c) => c.kind === "errors").map((c) => (
              <span key={c.id} className="badge" title={c.detail}>{c.label} · {c.error_count}</span>
            ))}
          </div>
        )}
      </a>
      <div className="score">
        {r.grade ? <><b>{fmtNum(r.grade.total)}</b><span className="muted"> / {fmtNum(r.grade.out_of)}</span></> : <span className="badge">{proc ? "…" : "—"}</span>}
      </div>
      <div className="actions">
        <button className="icon-btn bad" aria-label={`Supprimer ${r.title}`} onClick={onDelete}><IconTrash /></button>
      </div>
    </div>
  );
}
