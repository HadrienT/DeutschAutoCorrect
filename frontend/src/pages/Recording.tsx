import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { Category, DetectedError, EditResult, RecordingDetail, Rubric, Segment } from "../api/types";
import { ErrorPanel } from "../components/ErrorPanel";
import { GradeCard } from "../components/GradeCard";
import { IconDownload, IconPause, IconPlay, IconPlus, IconPrint, IconRefresh, IconSkip } from "../components/Icons";
import { useToast } from "../components/Toast";
import { Transcript } from "../components/Transcript";
import { Waveform } from "../components/Waveform";
import { CATEGORIES, CATEGORY_LABEL, STAGES, needsReview, nextError, stageLabel } from "../lib/errors";
import { usePlayer } from "../lib/usePlayer";
import { formatTime } from "../lib/time";

export function RecordingPage({ id }: { id: string }) {
  const toast = useToast();
  const [rec, setRec] = useState<RecordingDetail | null>(null);
  const [rubrics, setRubrics] = useState<Rubric[]>([]);
  const [peaks, setPeaks] = useState<number[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [active, setActive] = useState<Set<Category>>(new Set(CATEGORIES));
  const [showRejected, setShowRejected] = useState(false);
  const [onlyReview, setOnlyReview] = useState(false);
  const [collapsed, setCollapsed] = useState<Set<Category>>(new Set());
  const [adding, setAdding] = useState(false);
  const [loadError, setLoadError] = useState("");

  const done = rec?.status === "done" && rec.analysis != null;
  const player = usePlayer(done ? api.audioUrl(id) : null, rec?.duration ?? 0);

  const load = useCallback(() => api.getRecording(id).then(setRec).catch((e) => setLoadError(e.message)), [id]);
  useEffect(() => { void load(); api.listRubrics().then(setRubrics).catch(() => {}); }, [load]);
  useEffect(() => {
    if (!rec || rec.status === "done" || rec.status === "failed") return;
    const t = setInterval(() => void load(), 1200);
    return () => clearInterval(t);
  }, [rec, load]);
  useEffect(() => {
    if (done) api.peaks(id).then((p) => setPeaks(p.peaks)).catch(() => setPeaks(null));
  }, [done, id]);

  const apply = useCallback((res: EditResult) => {
    setRec((r) => (r ? { ...r, analysis: res.analysis, grade: res.grade } : r));
    res.warnings?.forEach((w) => toast(w, true));
  }, [toast]);
  const guard = useCallback(async (p: Promise<EditResult>) => {
    try { apply(await p); } catch (e) { toast((e as Error).message, true); }
  }, [apply, toast]);

  const analysis = rec?.analysis;
  const visible = useMemo(() => (analysis?.errors ?? []).filter((e) =>
    active.has(e.category) && (showRejected || e.status !== "rejected") && (!onlyReview || needsReview(e))),
  [analysis, active, showRejected, onlyReview]);
  const selected = analysis?.errors.find((e) => e.id === selectedId) ?? null;

  const select = useCallback((e: DetectedError) => { setSelectedId(e.id); player.playWindow(e.start, e.end); }, [player]);
  const patch = useCallback((eid: string, p: Partial<DetectedError>) => void guard(api.patchError(id, eid, p)), [guard, id]);

  useEffect(() => {
    const on = (ev: KeyboardEvent) => {
      const t = ev.target as HTMLElement;
      if (/INPUT|TEXTAREA|SELECT/.test(t.tagName) || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      if (ev.key === " ") { ev.preventDefault(); player.toggle(); }
      else if (ev.key === "ArrowLeft") player.skip(-3);
      else if (ev.key === "ArrowRight") player.skip(3);
      else if (ev.key === "j" || ev.key === "k") {
        const e = nextError(visible, player.time, ev.key === "k" ? 1 : -1);
        if (e) select(e);
      } else if ((ev.key === "c" || ev.key === "r") && selected) {
        patch(selected.id, { status: ev.key === "c" ? "confirmed" : "rejected" });
      }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [player, visible, select, selected, patch]);

  if (loadError) return <div className="page"><div className="banner bad">{loadError}</div></div>;
  if (!rec) return <div className="page muted">Chargement…</div>;

  if (rec.status !== "done" || !analysis) return <Processing rec={rec} onRetry={() => api.reanalyze(id).then(load)} />;

  const toggleCat = (c: Category) => setActive((s) => { const n = new Set(s); if (n.has(c)) n.delete(c); else n.add(c); return n; });
  const onToggleGraded = (s: Segment) => void guard(api.patchSegment(id, s.id, { graded: !s.graded }));
  const counts = Object.fromEntries(CATEGORIES.map((c) => [c, analysis.errors.filter((e) => e.category === c && e.status !== "rejected").length])) as Record<Category, number>;

  return (
    <div className="page">
      <div className="rec-head">
        <a href="#/" className="muted">← Enregistrements</a>
        <h1>{rec.title}</h1>
        {rec.student_name && <span className="badge primary">{rec.student_name}</span>}
        <span className="muted mono">{formatTime(rec.duration)}</span>
        <div className="grow" />
        <div className="row no-print">
          <button className="btn btn-sm" onClick={() => api.reanalyze(id).then(load)} title="Relancer toute l'analyse (efface vos corrections)"><span style={{ width: 15, display: "inline-flex" }}><IconRefresh /></span> Réanalyser</button>
          <a className="btn btn-sm" href={api.exportUrl(id, "csv")}><span style={{ width: 15, display: "inline-flex" }}><IconDownload /></span> CSV</a>
          <a className="btn btn-sm" href={api.exportUrl(id, "json")}>JSON</a>
          <button className="btn btn-sm" onClick={() => window.print()}><span style={{ width: 15, display: "inline-flex" }}><IconPrint /></span> Imprimer</button>
        </div>
      </div>
      {analysis.warnings.map((w) => <div className="banner" key={w} style={{ marginBottom: 10 }}>⚠️ {w}</div>)}

      <div className="card player">
        <div className="player-top">
          <button className="play-btn" onClick={player.toggle} aria-label={player.playing ? "Pause" : "Lecture"} title="Espace">
            {player.playing ? <IconPause /> : <IconPlay />}
          </button>
          <div className="mono" style={{ fontSize: 15 }}>{formatTime(player.time, 1)} <span className="muted">/ {formatTime(player.duration || rec.duration)}</span></div>
          <div className="grow" />
          <button className="icon-btn" title="Erreur précédente (J)" aria-label="Erreur précédente" style={{ transform: "scaleX(-1)" }}
            onClick={() => { const e = nextError(visible, player.time, -1); if (e) select(e); }}><IconSkip /></button>
          <button className="icon-btn" title="Erreur suivante (K)" aria-label="Erreur suivante"
            onClick={() => { const e = nextError(visible, player.time, 1); if (e) select(e); }}><IconSkip /></button>
          <select className="speed" aria-label="Vitesse" value={player.rate} onChange={(e) => player.setRate(Number(e.target.value))}>
            {[0.6, 0.8, 1, 1.25, 1.5].map((r) => <option key={r} value={r}>×{r}</option>)}
          </select>
        </div>
        {peaks
          ? <Waveform peaks={peaks} duration={player.duration || rec.duration} time={player.time} errors={visible} segments={analysis.segments}
              selectedId={selectedId} onSeek={player.seek} onSelect={select} />
          : <div className="wave-wrap" />}
        <div className="wave-legend">
          {CATEGORIES.map((c) => (
            <button key={c} className="chip" aria-pressed={active.has(c)} onClick={() => toggleCat(c)} title="Afficher / masquer">
              <span className="dot" style={{ background: `var(--c-${c})` }} />{CATEGORY_LABEL[c]} <b>{counts[c]}</b>
            </button>
          ))}
          <span>▨ passages non notés (enseignant / français)</span>
          <span className="muted no-print" style={{ marginLeft: "auto" }}>Espace · J/K erreurs · C/R confirmer/rejeter · ←/→ ±3 s</span>
        </div>
      </div>

      <div className="layout">
        <div className="card card-pad">
          <div className="section-title">Transcription fidèle <span className="badge">erreurs conservées</span></div>
          <Transcript segments={analysis.segments} errors={visible} time={player.time} selectedId={selectedId} playing={player.playing}
            onSeek={(t) => { player.seek(t); }} onSelectError={select} onToggleGraded={onToggleGraded} />
        </div>
        <div className="side">
          {rec.grade && (
            <GradeCard grade={rec.grade} rubric={rec.rubric} rubrics={rubrics} manual={rec.manual} stats={analysis.stats}
              onRubric={(rid) => void api.assignRubric(id, { rubric_id: rid }).then((r) => setRec((x) => x && { ...x, grade: r.grade, rubric: r.rubric, manual: r.manual }))}
              onManual={(cid, v) => void api.assignRubric(id, { manual: { ...rec.manual, [cid]: v } }).then((r) => setRec((x) => x && { ...x, grade: r.grade, manual: r.manual }))} />
          )}
          <div className="card card-pad">
            <div className="section-title">
              Erreurs <span className="badge">{visible.length}</span>
              <button className="btn btn-sm no-print" style={{ marginLeft: "auto" }} onClick={() => setAdding(!adding)}><span style={{ width: 14, display: "inline-flex" }}><IconPlus /></span> Ajouter</button>
            </div>
            <div className="filters no-print">
              <button className="chip" aria-pressed={showRejected} onClick={() => setShowRejected(!showRejected)}>Rejetées</button>
              <button className="chip" aria-pressed={onlyReview} onClick={() => setOnlyReview(!onlyReview)}>À vérifier</button>
            </div>
            {adding && <AddError time={player.time} onCancel={() => setAdding(false)}
              onSubmit={(b) => { void guard(api.addError(id, b)); setAdding(false); }} />}
            <ErrorPanel errors={visible} selectedId={selectedId} collapsed={collapsed}
              onToggleGroup={(c) => setCollapsed((s) => { const n = new Set(s); if (n.has(c)) n.delete(c); else n.add(c); return n; })}
              onSelect={select} onPatch={patch} onDelete={(eid) => void guard(api.deleteError(id, eid))} />
          </div>
          <div className="muted" style={{ fontSize: 12.5 }}>
            Moteurs — ASR : {analysis.engines.asr} · correction : {analysis.engines.corrector} · prononciation : {analysis.engines.pronunciation}
          </div>
        </div>
      </div>
    </div>
  );
}

function AddError({ time, onSubmit, onCancel }: { time: number; onSubmit: (b: Partial<DetectedError>) => void; onCancel: () => void }) {
  const [f, setF] = useState({ category: "grammar" as Category, severity: "minor" as "minor" | "major", heard: "", expected: "", explanation: "" });
  return (
    <form className="edit-form" style={{ marginBottom: 12, paddingBottom: 12, borderBottom: "1px dashed var(--border)", borderTop: 0 }}
      onSubmit={(e) => { e.preventDefault(); onSubmit({ ...f, start: Math.max(0, time - 0.2), end: time + 0.6 }); }}>
      <div className="muted" style={{ fontSize: 13 }}>Erreur manuelle à <b className="mono">{formatTime(time, 1)}</b> (placez la lecture au bon endroit)</div>
      <div className="grid-2">
        <label className="field">Catégorie
          <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value as Category })}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
          </select></label>
        <label className="field">Gravité
          <select value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value as "minor" | "major" })}>
            <option value="minor">Légère</option><option value="major">Grave</option></select></label>
      </div>
      <div className="grid-2">
        <label className="field">Entendu<input type="text" value={f.heard} onChange={(e) => setF({ ...f, heard: e.target.value })} /></label>
        <label className="field">Attendu<input type="text" value={f.expected} onChange={(e) => setF({ ...f, expected: e.target.value })} /></label>
      </div>
      <label className="field">Explication<input type="text" value={f.explanation} onChange={(e) => setF({ ...f, explanation: e.target.value })} /></label>
      <div className="row"><button className="btn btn-primary btn-sm" type="submit">Ajouter</button><button className="btn btn-sm" type="button" onClick={onCancel}>Annuler</button></div>
    </form>
  );
}

function Processing({ rec, onRetry }: { rec: RecordingDetail; onRetry: () => void }) {
  const failed = rec.status === "failed";
  const idx = STAGES.indexOf(rec.stage);
  return (
    <div className="page page-narrow">
      <a href="#/" className="muted">← Enregistrements</a>
      <div className="card card-pad" style={{ marginTop: 14 }}>
        <h1 style={{ fontSize: 22, marginBottom: 6 }}>{rec.title}</h1>
        {failed ? (
          <>
            <div className="banner bad" style={{ margin: "12px 0" }}>{rec.error || "L'analyse a échoué."}</div>
            <button className="btn btn-primary" onClick={onRetry}>Relancer l'analyse</button>
          </>
        ) : (
          <>
            <p className="muted">Analyse en cours : {stageLabel(rec.stage)}…</p>
            <div className="progress" style={{ margin: "10px 0 18px" }}><i style={{ width: `${rec.progress}%` }} /></div>
            <ol style={{ display: "grid", gap: 8, paddingLeft: 20, margin: 0 }}>
              {STAGES.map((s, i) => (
                <li key={s} style={{ color: i < idx ? "var(--ok)" : i === idx ? "var(--text)" : "var(--muted)", fontWeight: i === idx ? 650 : 400 }}>
                  {stageLabel(s)}{i < idx ? " ✓" : ""}
                </li>
              ))}
            </ol>
          </>
        )}
      </div>
    </div>
  );
}
