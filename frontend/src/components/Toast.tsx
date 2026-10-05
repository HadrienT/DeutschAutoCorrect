import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Toast = { id: number; text: string; bad?: boolean };
const Ctx = createContext<(text: string, bad?: boolean) => void>(() => {});
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, bad?: boolean) => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, bad }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), bad ? 6000 : 3000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (<div key={t.id} className={`toast ${t.bad ? "bad" : ""}`}>{t.text}</div>))}
      </div>
    </Ctx.Provider>
  );
}
