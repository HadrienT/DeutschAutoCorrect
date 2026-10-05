import type { ReactNode } from "react";

const base = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" } as const;
const mk = (d: ReactNode) => () => (<svg viewBox="0 0 24 24" aria-hidden="true" {...base}>{d}</svg>);

export const IconPlay = () => (<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>);
export const IconPause = () => (<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M7 5h4v14H7zM13 5h4v14h-4z" /></svg>);
export const IconCheck = mk(<path d="M20 6 9 17l-5-5" />);
export const IconX = mk(<path d="M18 6 6 18M6 6l12 12" />);
export const IconEdit = mk(<><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></>);
export const IconTrash = mk(<><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /></>);
export const IconUpload = mk(<><path d="M12 16V4" /><path d="m7 9 5-5 5 5" /><path d="M4 20h16" /></>);
export const IconDownload = mk(<><path d="M12 4v12" /><path d="m7 11 5 5 5-5" /><path d="M4 20h16" /></>);
export const IconRefresh = mk(<><path d="M21 12a9 9 0 1 1-3-6.7" /><path d="M21 4v5h-5" /></>);
export const IconPlus = mk(<path d="M12 5v14M5 12h14" />);
export const IconPrint = mk(<><path d="M6 9V3h12v6" /><rect x="6" y="14" width="12" height="7" /><path d="M6 17H4a1 1 0 0 1-1-1v-5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5a1 1 0 0 1-1 1h-2" /></>);
export const IconChevron = mk(<path d="m6 9 6 6 6-6" />);
export const IconSkip = mk(<><path d="m5 4 10 8-10 8z" /><path d="M19 5v14" /></>);
export const IconMoon = mk(<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />);
export const IconUser = mk(<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>);

export const Logo = () => (
  <svg viewBox="0 0 32 32" aria-hidden="true">
    <rect width="32" height="32" rx="9" fill="#4f46e5" />
    <path d="M7 17h3l2.2-6 3.3 12 3-9 2 3h4.5" stroke="#fff" strokeWidth="2.3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
