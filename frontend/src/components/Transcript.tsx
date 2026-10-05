import { useEffect, useMemo, useRef } from "react";
import type { DetectedError, Segment } from "../api/types";
import { wordsOfError } from "../lib/errors";
import { formatTime } from "../lib/time";

interface Props {
  segments: Segment[]; errors: DetectedError[]; time: number; selectedId: string | null; playing: boolean;
  onSeek: (t: number) => void; onSelectError: (e: DetectedError) => void;
  onToggleGraded: (s: Segment) => void;
}

const ROLE_LABEL = { student: "Élève", teacher: "Enseignant", other: "Autre voix" } as const;

export function Transcript({ segments, errors, time, selectedId, playing, onSeek, onSelectError, onToggleGraded }: Props) {
  const byseg = useMemo(() => {
    const m = new Map<string, DetectedError[]>();
    for (const e of errors) m.set(e.segment_id, [...(m.get(e.segment_id) ?? []), e]);
    return m;
  }, [errors]);
  const activeId = segments.find((s) => time >= s.start && time <= s.end + 0.2)?.id;
  const activeRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (playing) activeRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeId, playing]);

  if (segments.length === 0) return <div className="empty">Aucune parole détectée.</div>;
  return (
    <div role="list" aria-label="Transcription">
      {segments.map((s) => {
        const errs = byseg.get(s.id) ?? [];
        const wordErr = new Map<number, DetectedError>();
        for (const e of errs) for (const i of wordsOfError(s, e)) {
          const cur = wordErr.get(i);
          if (!cur || cur.status === "rejected") wordErr.set(i, e);
        }
        const dim = !s.graded;
        const tagColor = s.role === "teacher" ? "var(--warn)" : s.language === "fr" ? "var(--muted)" : "var(--primary)";
        return (
          <div key={s.id} role="listitem" ref={s.id === activeId ? activeRef : undefined}
            className={`seg ${dim ? "dim" : ""} ${s.id === activeId ? "active" : ""}`}>
            <div>
              <button className="tc" onClick={() => onSeek(s.start)} aria-label={`Aller à ${formatTime(s.start)}`}>{formatTime(s.start)}</button>
              <div className="role-tag" style={{ color: tagColor, marginTop: 4 }}>
                {ROLE_LABEL[s.role]}{s.language === "fr" ? " · FR" : ""}
              </div>
            </div>
            <div className="words" lang={s.language === "fr" ? "fr" : "de"}>
              {s.words.length === 0 ? s.text : s.words.map((w, i) => {
                const e = wordErr.get(i);
                const now = time >= w.start && time < w.end && s.id === activeId;
                const cls = ["w", e ? "err" : "", e?.status === "rejected" ? "rejected" : "", e && e.id === selectedId ? "sel" : "",
                  now ? "now" : "", w.prob < 0.5 && s.graded ? "low" : ""].filter(Boolean).join(" ");
                return (
                  <span key={i}>
                    <span className={cls} style={e ? { ["--mc" as string]: `var(--c-${e.category})` } : undefined}
                      title={e ? `${e.expected ? "→ " + e.expected + " — " : ""}${e.explanation}` : w.prob < 0.5 ? `Confiance ${Math.round(w.prob * 100)} %` : undefined}
                      onClick={() => (e ? onSelectError(e) : onSeek(w.start))}>{w.text}</span>{" "}
                  </span>
                );
              })}
            </div>
            <div className="seg-actions">
              <button className="btn btn-sm" onClick={() => onToggleGraded(s)}
                title={s.graded ? "Ne plus compter ce passage dans la note" : "Compter ce passage dans la note"}>
                {s.graded ? "Exclure" : "Compter"}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
