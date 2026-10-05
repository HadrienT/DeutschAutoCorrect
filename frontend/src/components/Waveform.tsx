import { useEffect, useMemo, useRef, useState } from "react";
import type { DetectedError, Segment } from "../api/types";

interface Props {
  peaks: number[]; duration: number; time: number; errors: DetectedError[]; segments: Segment[];
  selectedId: string | null; onSeek: (t: number) => void; onSelect: (e: DetectedError) => void;
}

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";

export function Waveform({ peaks, duration, time, errors, segments, selectedId, onSeek, onSelect }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const progress = duration > 0 ? time / duration : 0;

  useEffect(() => {
    const c = canvas.current, w = wrap.current;
    if (!c || !w) return;
    const dpr = window.devicePixelRatio || 1;
    const W = w.clientWidth, H = w.clientHeight;
    if (c.width !== W * dpr || c.height !== H * dpr) { c.width = W * dpr; c.height = H * dpr; }
    const g = c.getContext("2d");
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    const n = peaks.length;
    const bw = W / n;
    const mid = H / 2 + 6;
    const wave = css("--wave"), played = css("--wave-played");
    for (let i = 0; i < n; i++) {
      const h = Math.max(2, peaks[i] * (H - 22));
      g.fillStyle = i / n <= progress ? played : wave;
      g.fillRect(i * bw + 0.5, mid - h / 2, Math.max(1, bw - 1.2), h);
    }
    g.fillStyle = css("--text");
    g.fillRect(progress * W - 1, 0, 2, H);
  }, [peaks, progress, width]);

  useEffect(() => {
    const w = wrap.current;
    if (!w) return;
    const ro = new ResizeObserver(() => setWidth(w.clientWidth));
    ro.observe(w);
    return () => ro.disconnect();
  }, []);

  const bands = useMemo(() => segments.filter((s) => !s.graded), [segments]);
  const click = (e: React.MouseEvent) => {
    const r = wrap.current!.getBoundingClientRect();
    onSeek(((e.clientX - r.left) / r.width) * duration);
  };

  return (
    <div className="wave-wrap" ref={wrap} onClick={click} role="slider" aria-label="Position dans l'enregistrement"
      aria-valuemin={0} aria-valuemax={Math.round(duration)} aria-valuenow={Math.round(time)} tabIndex={-1}>
      {bands.map((s) => (
        <div key={s.id} className="wave-band" style={{ left: `${(s.start / duration) * 100}%`, width: `${((s.end - s.start) / duration) * 100}%` }} />
      ))}
      <canvas ref={canvas} />
      {errors.map((e) => (
        <button key={e.id} className={`wave-marker ${e.id === selectedId ? "sel" : ""}`}
          style={{ left: `${(e.start / duration) * 100}%`, ["--mc" as string]: `var(--c-${e.category})` }}
          title={`${e.heard || "…"} → ${e.expected || "?"}`} aria-label={`Erreur à ${e.start.toFixed(1)} s`}
          onClick={(ev) => { ev.stopPropagation(); onSelect(e); }} />
      ))}
    </div>
  );
}
