import { useCallback, useEffect, useRef, useState } from "react";
import { seekWindow } from "./time";

export interface Player {
  time: number; playing: boolean; duration: number; rate: number; ready: boolean;
  toggle: () => void; seek: (t: number) => void; playWindow: (start: number, end: number) => void;
  setRate: (r: number) => void; skip: (d: number) => void;
}

/** Thin wrapper around an HTMLAudioElement with a smooth (rAF) clock and "play this span" support. */
export function usePlayer(src: string | null, fallbackDuration = 0): Player {
  const audio = useRef<HTMLAudioElement | null>(null);
  const stopAt = useRef<number | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [duration, setDuration] = useState(fallbackDuration);
  const [rate, setRateState] = useState(1);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!src) return;
    const a = new Audio();
    a.preload = "metadata";
    a.src = src;
    audio.current = a;
    const onMeta = () => { setDuration(Number.isFinite(a.duration) ? a.duration : fallbackDuration); setReady(true); };
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    a.addEventListener("loadedmetadata", onMeta);
    a.addEventListener("play", onPlay);
    a.addEventListener("pause", onPause);
    a.addEventListener("ended", onPause);
    return () => {
      a.pause();
      a.removeAttribute("src");
      a.load();
      a.removeEventListener("loadedmetadata", onMeta);
      a.removeEventListener("play", onPlay);
      a.removeEventListener("pause", onPause);
      a.removeEventListener("ended", onPause);
      audio.current = null;
    };
  }, [src, fallbackDuration]);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const a = audio.current;
      if (a) {
        setTime(a.currentTime);
        if (stopAt.current != null && a.currentTime >= stopAt.current) {
          a.pause();
          stopAt.current = null;
        }
      }
      raf = requestAnimationFrame(tick);
    };
    if (playing) raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  const seek = useCallback((t: number) => {
    const a = audio.current;
    if (!a) return;
    a.currentTime = Math.max(0, t);
    setTime(a.currentTime);
  }, []);

  const toggle = useCallback(() => {
    const a = audio.current;
    if (!a) return;
    stopAt.current = null;
    if (a.paused) void a.play().catch(() => {}); else a.pause();
  }, []);

  const playWindow = useCallback((start: number, end: number) => {
    const a = audio.current;
    if (!a) return;
    const [s, e] = seekWindow(start, end, a.duration || Infinity);
    a.currentTime = s;
    stopAt.current = e;
    setTime(s);
    void a.play().catch(() => {});
  }, []);

  const setRate = useCallback((r: number) => {
    setRateState(r);
    if (audio.current) audio.current.playbackRate = r;
  }, []);

  const skip = useCallback((d: number) => {
    const a = audio.current;
    if (a) seek(Math.min(a.duration || Infinity, a.currentTime + d));
  }, [seek]);

  return { time, playing, duration, rate, ready, toggle, seek, playWindow, setRate, skip };
}
