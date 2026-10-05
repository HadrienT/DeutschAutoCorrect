import { useEffect, useRef, useState } from "react";
import type { Category, DetectedError } from "../api/types";
import { CATEGORIES, CATEGORY_LABEL, SOURCE_LABEL, groupByCategory, needsReview, subtypeLabel } from "../lib/errors";
import { formatTime } from "../lib/time";
import { IconCheck, IconChevron, IconEdit, IconTrash, IconX } from "./Icons";

interface Props {
  errors: DetectedError[]; selectedId: string | null; collapsed: Set<Category>;
  onToggleGroup: (c: Category) => void; onSelect: (e: DetectedError) => void;
  onPatch: (id: string, patch: Partial<DetectedError>) => void; onDelete: (id: string) => void;
}

export function ErrorPanel({ errors, selectedId, collapsed, onToggleGroup, onSelect, onPatch, onDelete }: Props) {
  const groups = groupByCategory(errors);
  if (errors.length === 0) return <div className="empty">Aucune erreur à afficher 🎉</div>;
  return (
    <div>
      {CATEGORIES.filter((c) => groups[c].length > 0).map((c) => {
        const open = !collapsed.has(c);
        return (
          <section className="group" key={c}>
            <button className="group-head" aria-expanded={open} onClick={() => onToggleGroup(c)}
              style={{ ["--gbg" as string]: `var(--c-${c}-soft)`, ["--gfg" as string]: `var(--c-${c})` }}>
              <span style={{ transform: open ? "none" : "rotate(-90deg)", display: "inline-flex", width: 16 }}><IconChevron /></span>
              {CATEGORY_LABEL[c]}
              <span className="count">{groups[c].filter((e) => e.status !== "rejected").length}</span>
            </button>
            {open && groups[c].map((e) => (
              <ErrorCard key={e.id} e={e} selected={e.id === selectedId} onSelect={onSelect} onPatch={onPatch} onDelete={onDelete} />
            ))}
          </section>
        );
      })}
    </div>
  );
}

function ErrorCard({ e, selected, onSelect, onPatch, onDelete }: {
  e: DetectedError; selected: boolean; onSelect: (e: DetectedError) => void;
  onPatch: (id: string, patch: Partial<DetectedError>) => void; onDelete: (id: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ expected: e.expected, explanation: e.explanation, note: e.note, category: e.category });
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (selected) ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [selected]);
  const review = needsReview(e);
  return (
    <div ref={ref} className={`err-card ${selected ? "sel" : ""} ${e.status === "rejected" ? "rejected" : ""}`}
      style={{ ["--mc" as string]: `var(--c-${e.category})` }} data-testid="error-card" data-error-id={e.id}>
      <div className="row wrap" style={{ gap: 8 }}>
        <button className="tc" onClick={() => onSelect(e)} aria-label={`Écouter à ${formatTime(e.start)}`} title="Écouter ce passage">
          ▶ {formatTime(e.start, 1)}
        </button>
        <span className="badge" style={{ background: `var(--c-${e.category}-soft)`, color: `var(--c-${e.category})` }}>{subtypeLabel(e.subtype)}</span>
        {review && <span className="badge warn">à vérifier</span>}
        {e.status === "confirmed" && <span className="badge ok">confirmée</span>}
      </div>
      <div className="err-main fix">
        {e.heard && <span className="heard">{e.heard}</span>}
        {e.heard && e.expected && <span className="arrow">→</span>}
        {e.expected && <span className="expected">{e.expected}</span>}
      </div>
      {e.explanation && <div className="err-expl">{e.explanation}</div>}
      {e.note && <div className="err-expl">📝 {e.note}</div>}
      <div className="err-foot">
        <div className="grow">
          <button className={`badge sev ${e.severity === "major" ? "bad" : ""}`} title="Changer la gravité"
            onClick={() => onPatch(e.id, { severity: e.severity === "major" ? "minor" : "major" })}>
            {e.severity === "major" ? "Grave" : "Légère"}
          </button>
          <span className="badge" title={`Confiance ${Math.round(e.confidence * 100)} %`}>{SOURCE_LABEL[e.source] ?? e.source}</span>
        </div>
        {e.status !== "confirmed" && <button className="icon-btn ok" title="Confirmer (C)" aria-label="Confirmer l'erreur" onClick={() => onPatch(e.id, { status: "confirmed" })}><IconCheck /></button>}
        {e.status !== "rejected"
          ? <button className="icon-btn bad" title="Rejeter (R) : ne compte plus dans la note" aria-label="Rejeter l'erreur" onClick={() => onPatch(e.id, { status: "rejected" })}><IconX /></button>
          : <button className="btn btn-sm" onClick={() => onPatch(e.id, { status: "pending" })}>Rétablir</button>}
        <button className="icon-btn" title="Modifier" aria-label="Modifier l'erreur" onClick={() => setEditing(!editing)}><IconEdit /></button>
        {e.source === "manual" && <button className="icon-btn bad" title="Supprimer" aria-label="Supprimer" onClick={() => onDelete(e.id)}><IconTrash /></button>}
      </div>
      {editing && (
        <form className="edit-form" onSubmit={(ev) => { ev.preventDefault(); onPatch(e.id, draft); setEditing(false); }}>
          <div className="grid-2">
            <label className="field">Catégorie
              <select value={draft.category} onChange={(ev) => setDraft({ ...draft, category: ev.target.value as Category })}>
                {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
              </select>
            </label>
            <label className="field">Forme correcte
              <input type="text" value={draft.expected} onChange={(ev) => setDraft({ ...draft, expected: ev.target.value })} />
            </label>
          </div>
          <label className="field">Explication
            <textarea rows={2} value={draft.explanation} onChange={(ev) => setDraft({ ...draft, explanation: ev.target.value })} />
          </label>
          <label className="field">Note personnelle
            <input type="text" value={draft.note} onChange={(ev) => setDraft({ ...draft, note: ev.target.value })} />
          </label>
          <div className="row"><button className="btn btn-primary btn-sm" type="submit">Enregistrer</button>
            <button className="btn btn-sm" type="button" onClick={() => setEditing(false)}>Annuler</button></div>
        </form>
      )}
    </div>
  );
}
