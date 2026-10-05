/** 83.4 -> "01:23" (or "01:23.4" with decimals). */
export function formatTime(t: number, decimals = 0): string {
  const safe = Math.max(0, t);
  const m = Math.floor(safe / 60);
  const s = safe - m * 60;
  const secs = decimals > 0 ? s.toFixed(decimals).padStart(decimals + 3, "0") : String(Math.floor(s)).padStart(2, "0");
  return `${String(m).padStart(2, "0")}:${secs}`;
}

/** French number formatting: 13.5 -> "13,5". */
export function fmtNum(n: number, max = 2): string {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: max }).format(n);
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, v));
}

/** Where to start playback so the faulty word is heard with a bit of lead-in context. */
export const LEAD_IN = 0.8;
export const LEAD_OUT = 0.6;
export function seekWindow(start: number, end: number, duration: number): [number, number] {
  return [clamp(start - LEAD_IN, 0, duration || Infinity), clamp(end + LEAD_OUT, 0, duration || Infinity)];
}
