import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Category, Criterion, Grade, RecordingSummary, Rubric } from "../api/types";
import { IconPlus, IconTrash } from "../components/Icons";
import { useToast } from "../components/Toast";
import { CATEGORIES, CATEGORY_LABEL } from "../lib/errors";
import { fmtNum } from "../lib/time";

const blank = (): Rubric => ({
  id: null, name: "Nouveau barème", total_points: 20, rounding: "half", repeat_policy: "once_per_expected", min_confidence: 0.5,
  criteria: [{ id: "c1", label: "Grammaire", kind: "errors", category: "grammar", max_points: 5, penalty_minor: 0.5, penalty_major: 1, cap_deduction: null, tiers: [] }],
});

const num = (v: string) => (v === "" || Number.isNaN(Number(v.replace(",", "."))) ? 0 : Number(v.replace(",", ".")));

export function RubricsPage() {
  const toast = useToast();
  const [list, setList] = useState<Rubric[]>([]);
  const [draft, setDraft] = useState<Rubric | null>(null);
  const [recs, setRecs] = useState<RecordingSummary[]>([]);
  const [recId, setRecId] = useState("");
  const [grade, setGrade] = useState<Grade | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async (selectId?: number | null) => {
    const l = await api.listRubrics();
    setList(l);
    setDraft((d) => (selectId !== undefined ? l.find((r) => r.id === selectId) ?? l[0] ?? null : d ?? l[0] ?? null));
  }, []);
  useEffect(() => { void load(); api.listRecordings().then((r) => { const done = r.filter((x) => x.status === "done"); setRecs(done); if (done[0]) setRecId(done[0].id); }); }, [load]);

  useEffect(() => {
    if (!draft || !recId) { setGrade(null); return; }
    const t = setTimeout(() => { api.preview(recId, draft).then(setGrade).catch(() => setGrade(null)); }, 250);
    return () => clearTimeout(t);
  }, [draft, recId]);

  const setField = <K extends keyof Rubric>(k: K, v: Rubric[K]) => setDraft((d) => d && { ...d, [k]: v });
  const setCrit = (i: number, p: Partial<Criterion>) => setDraft((d) => d && { ...d, criteria: d.criteria.map((c, j) => (j === i ? { ...c, ...p } : c)) });
  const sumMax = draft?.criteria.reduce((a, c) => a + c.max_points, 0) ?? 0;

  const save = async () => {
    if (!draft) return;
    try {
      const saved = draft.id == null ? await api.createRubric(draft) : await api.updateRubric(draft);
      toast("Barème enregistré");
      await load(saved.id);
    } catch (e) { toast((e as Error).message, true); }
  };
  const remove = async () => {
    if (!draft?.id || !confirm(`Supprimer le barème « ${draft.name} » ?`)) return;
    try { await api.deleteRubric(draft.id); toast("Barème supprimé"); await load(null); } catch (e) { toast((e as Error).message, true); }
  };
  const importJson = async (f: File) => {
    try { const r = JSON.parse(await f.text()) as Rubric; setDraft({ ...r, id: null }); toast("Barème importé : pensez à l'enregistrer"); }
    catch { toast("Fichier JSON invalide", true); }
  };
  const exportJson = () => {
    if (!draft) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify({ ...draft, id: null }, null, 2)], { type: "application/json" }));
    a.download = `${draft.name}.json`;
    a.click();
  };

  return (
    <div className="page">
      <h1 style={{ fontSize: 26, marginBottom: 16 }}>Barèmes de notation</h1>
      <div className="rub-layout">
        <div className="card card-pad">
          <div className="section-title">Mes barèmes
            <button className="btn btn-sm" style={{ marginLeft: "auto" }} onClick={() => setDraft(blank())}><span style={{ width: 14, display: "inline-flex" }}><IconPlus /></span> Nouveau</button></div>
          {list.map((r) => (
            <button key={r.id} className={`rub-item ${draft?.id === r.id ? "active" : ""}`} onClick={() => setDraft(r)}>
              <b>{r.name}</b><div className="muted" style={{ fontSize: 12.5 }}>/ {fmtNum(r.total_points)} · {r.criteria.length} critères</div>
            </button>
          ))}
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn btn-sm" onClick={() => fileInput.current?.click()}>Importer</button>
            <button className="btn btn-sm" onClick={exportJson}>Exporter</button>
            <input ref={fileInput} type="file" accept="application/json" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) void importJson(f); e.target.value = ""; }} />
          </div>
        </div>

        {draft && (
          <div style={{ display: "grid", gap: 16 }}>
            <div className="card card-pad">
              <div className="grid-4">
                <label className="field" style={{ gridColumn: "span 2" }}>Nom<input type="text" value={draft.name} onChange={(e) => setField("name", e.target.value)} /></label>
                <label className="field">Note sur<input type="number" min={1} step="any" value={draft.total_points} onChange={(e) => setField("total_points", num(e.target.value) || 1)} /></label>
                <label className="field">Arrondi
                  <select value={draft.rounding} onChange={(e) => setField("rounding", e.target.value as Rubric["rounding"])}>
                    <option value="none">Aucun (0,01)</option><option value="half">Au demi-point</option><option value="integer">À l'entier</option></select></label>
              </div>
              <div className="grid-2" style={{ marginTop: 10 }}>
                <label className="field">Fautes répétées
                  <select value={draft.repeat_policy} onChange={(e) => setField("repeat_policy", e.target.value as Rubric["repeat_policy"])}>
                    <option value="count_all">Toutes comptées</option>
                    <option value="once_per_expected">Une seule fois par forme correcte (recommandé)</option>
                    <option value="once_per_subtype">Une seule fois par type d'erreur</option></select></label>
                <label className="field">Confiance minimale des détections non confirmées : {Math.round(draft.min_confidence * 100)} %
                  <input type="range" min={0} max={1} step={0.05} value={draft.min_confidence} onChange={(e) => setField("min_confidence", Number(e.target.value))} /></label>
              </div>
            </div>

            {draft.criteria.map((c, i) => (
              <div className="crit-edit" key={i} data-testid="criterion">
                <div className="grid-4">
                  <label className="field" style={{ gridColumn: "span 2" }}>Critère<input type="text" value={c.label} onChange={(e) => setCrit(i, { label: e.target.value })} /></label>
                  <label className="field">Type
                    <select value={c.kind} onChange={(e) => setCrit(i, { kind: e.target.value as Criterion["kind"], category: e.target.value === "errors" ? c.category ?? "grammar" : null,
                      tiers: e.target.value === "volume" && c.tiers.length === 0 ? [{ min_words: 0, points: 0 }, { min_words: 30, points: c.max_points }] : c.tiers })}>
                      <option value="errors">Erreurs d'une catégorie</option><option value="volume">Quantité de langue</option><option value="manual">Saisie manuelle</option></select></label>
                  <label className="field">Points max<input type="number" min={0} step="any" value={c.max_points} onChange={(e) => setCrit(i, { max_points: num(e.target.value) })} /></label>
                </div>
                {c.kind === "errors" && (
                  <div className="grid-4">
                    <label className="field">Catégorie
                      <select value={c.category ?? "grammar"} onChange={(e) => setCrit(i, { category: e.target.value as Category })}>
                        {CATEGORIES.map((k) => <option key={k} value={k}>{CATEGORY_LABEL[k]}</option>)}</select></label>
                    <label className="field">− par erreur légère<input type="number" min={0} step="any" value={c.penalty_minor} onChange={(e) => setCrit(i, { penalty_minor: num(e.target.value) })} /></label>
                    <label className="field">− par erreur grave<input type="number" min={0} step="any" value={c.penalty_major} onChange={(e) => setCrit(i, { penalty_major: num(e.target.value) })} /></label>
                    <label className="field">Retrait maximum<input type="number" min={0} step="any" placeholder="illimité" value={c.cap_deduction ?? ""} onChange={(e) => setCrit(i, { cap_deduction: e.target.value === "" ? null : num(e.target.value) })} /></label>
                  </div>
                )}
                {c.kind === "volume" && (
                  <div style={{ display: "grid", gap: 6 }}>
                    <span className="muted" style={{ fontSize: 12.5 }}>Paliers : à partir de N mots prononcés par l'élève → points</span>
                    {c.tiers.map((t, j) => (
                      <div className="tier-row" key={j}>
                        <input type="number" min={0} aria-label="Mots minimum" value={t.min_words} onChange={(e) => setCrit(i, { tiers: c.tiers.map((x, k) => (k === j ? { ...x, min_words: num(e.target.value) } : x)) })} /> mots →
                        <input type="number" min={0} step="any" aria-label="Points" value={t.points} onChange={(e) => setCrit(i, { tiers: c.tiers.map((x, k) => (k === j ? { ...x, points: num(e.target.value) } : x)) })} /> pts
                        <button className="icon-btn bad" aria-label="Supprimer le palier" onClick={() => setCrit(i, { tiers: c.tiers.filter((_, k) => k !== j) })}><IconTrash /></button>
                      </div>
                    ))}
                    <button className="btn btn-sm" style={{ justifySelf: "start" }} onClick={() => setCrit(i, { tiers: [...c.tiers, { min_words: 0, points: 0 }] })}>+ palier</button>
                  </div>
                )}
                {c.kind === "manual" && <span className="muted" style={{ fontSize: 12.5 }}>La note de ce critère est saisie par vous sur chaque enregistrement.</span>}
                <div><button className="btn btn-sm btn-danger" onClick={() => setDraft((d) => d && { ...d, criteria: d.criteria.filter((_, j) => j !== i) })}>Retirer ce critère</button></div>
              </div>
            ))}
            <div className="row wrap">
              <button className="btn" onClick={() => setDraft((d) => d && { ...d, criteria: [...d.criteria, { id: `c${Date.now().toString(36)}`, label: "Nouveau critère", kind: "errors", category: "grammar", max_points: 2, penalty_minor: 0.5, penalty_major: 1, cap_deduction: null, tiers: [] }] })}>
                <span style={{ width: 15, display: "inline-flex" }}><IconPlus /></span> Ajouter un critère</button>
              <span className="muted">Total des critères : <b>{fmtNum(sumMax)}</b> pts, ramené sur {fmtNum(draft.total_points)}.</span>
              <div className="grow" />
              {draft.id != null && <button className="btn btn-danger" onClick={() => void remove()}>Supprimer</button>}
              <button className="btn btn-primary" onClick={() => void save()}>Enregistrer</button>
            </div>

            <div className="card card-pad">
              <div className="section-title">Aperçu sur un enregistrement
                <select style={{ marginLeft: "auto", width: "auto", maxWidth: 260 }} value={recId} onChange={(e) => setRecId(e.target.value)} aria-label="Enregistrement d'aperçu">
                  {recs.length === 0 && <option value="">Aucun enregistrement analysé</option>}
                  {recs.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}</select></div>
              {grade ? (
                <div data-testid="preview">
                  <div className="grade-top"><span className="grade-num">{fmtNum(grade.total)}</span><span className="grade-out">/ {fmtNum(grade.out_of)}</span></div>
                  {grade.criteria.map((c) => (
                    <div className="crit" key={c.id}>
                      <div className="row"><span className="grow">{c.label}</span><span className="mono">{fmtNum(c.earned)} / {fmtNum(c.max)}</span></div>
                      <div className="bar"><i style={{ width: `${c.max > 0 ? (c.earned / c.max) * 100 : 0}%` }} /></div>
                      <div className="muted" style={{ fontSize: 12.5 }}>{c.detail}</div>
                    </div>
                  ))}
                </div>
              ) : <div className="muted">Choisissez un enregistrement analysé pour voir la note simulée en direct.</div>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
