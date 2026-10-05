import { useEffect, useState } from "react";

export function useHashPath(): string {
  const get = () => window.location.hash.replace(/^#/, "") || "/";
  const [path, setPath] = useState(get);
  useEffect(() => {
    const on = () => setPath(get());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return path;
}

export const go = (path: string) => { window.location.hash = path; };
