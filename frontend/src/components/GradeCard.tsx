import { useState } from "react";
import type { Grade, Rubric, Stats } from "../api/types";
import { fmtNum } from "../lib/time";

interface Props {
  grade: Grade; rubric: Rubric; rubrics: Rubric[]; manual: Record<string, number>; stats: Stats;
  onRubric: (id: number) => void; onManual: (id: string, v: number) => void;
}

export function GradeCard({ grade, rubric, rubrics, manual, stats, onRubric, onManual }: Props) {
  return (
    <div className="card card-pad" aria-label="Note">
      <div className="section-title" style={{ marginBottom: 10 }}>
        <span>Note</span>
        <select aria-label="Barème" value={rubric.id ?? ""} onChange={(e) => onRubric(Number(e.target.value))} style={{ marginLeft: "auto", width: "auto", minWidth: 0, flex: "1 1 0", maxWidth: 260 }}>
          {rubrics.map((r) => <option key={r.id} value={r.id ?? ""}>{r.name}</option>)}
        </select>
      </div>
      <div className="grade-top" data-testid="grade-total">
        <span className="grade-num">{fmtNum(grade.total)}</span>
        <span className="grade-out">/ {fmtNum(grade.out_of)}</span>
        <span className="muted" style={{ marginLeft: "auto", fontSize: 12.5, textAlign: "right" }}>
          {stats.student_words} mots d'élève<br />{Math.round(stats.student_speech_seconds)} s de parole
        </span>
      </div>
      <div style={{ marginTop: 12 }}>
        {grade.criteria.map((c) => (
          <div className="crit" key={c.id}>
            <div className="row">
              <span className="grow" style={{ fontWeight: 600 }}>{c.label}</span>
              {c.kind === "manual"
                ? <ManualInput value={manual[c.id]} max={c.max} onCommit={(v) => onManual(c.id, v)} />
                : <span className="mono">{fmtNum(c.earned)}</span>}
              <span className="muted mono">/ {fmtNum(c.max)}</span>
            </div>
            <div className="bar"><i style={{ width: `${c.max > 0 ? (c.earned / c.max) * 100 : 0}%` }} /></div>
            <div className="muted" style={{ fontSize: 12.5 }}>{c.detail}</div>
          </div>
        ))}
      </div>
      <div className="muted no-print" style={{ fontSize: 12.5, marginTop: 8 }}>
        Les erreurs rejetées ne comptent pas ; les fautes répétées : {({
          count_all: "toutes comptées", once_per_subtype: "une fois par type", once_per_expected: "une fois par forme correcte",
        } as const)[rubric.repeat_policy]}. <a href="#/rubrics">Modifier le barème</a>
      </div>
    </div>
  );
}

function ManualInput({ value, max, onCommit }: { value: number | undefined; max: number; onCommit: (v: number) => void }) {
  const [text, setText] = useState<string | null>(null);
  const shown = text ?? (value === undefined ? "" : String(value).replace(".", ","));
  const commit = () => {
    if (text === null) return;
    const v = Number(text.replace(",", "."));
    setText(null);
    if (text.trim() !== "" && Number.isFinite(v)) onCommit(Math.min(max, Math.max(0, v)));
  };
  return (
    <input className="manual-input" type="text" inputMode="decimal" placeholder="saisir" value={shown} aria-label="Points saisis"
      onChange={(e) => setText(e.target.value)} onBlur={commit} onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
  );
}
