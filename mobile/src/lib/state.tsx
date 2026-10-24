/** App-wide state: theme, detector settings, server address, metadata, your calls on events and the session log. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, defaultApiBase, getApiBase, setApiBase } from './api';
import { Palettes, type Palette } from './theme';
import type { Meta, Settings } from './types';

export type HistoryRow = {
  time: string; recording: string; stress: string; status: string; confident: number; low: number; snr_db: number; settings: string;
};

export const SETTING_KEYS: (keyof Settings)[] = ['tau', 'hi', 'lo', 'merge', 'snr_min'];
const FALLBACK: Settings = { tau: 0.5, hi: 0.7, lo: 0.65, merge: 0.4, snr_min: 11.5 };

type Ctx = {
  dark: boolean; setDark: (v: boolean) => void; colors: Palette;
  settings: Settings; setSetting: (k: keyof Settings, v: number) => void; resetSettings: () => void;
  validated: Settings; changed: (keyof Settings)[];
  meta: Meta | null; metaError: string | null; reloadMeta: () => void;
  apiBase: string; setServer: (url: string | null) => void;
  notes: Record<string, string>; setNote: (label: string, onset: number, call: string | null) => void;
  history: HistoryRow[]; logHistory: (row: HistoryRow, key: string) => void; clearSession: () => void;
};

const AppContext = createContext<Ctx | null>(null);
export const noteKey = (label: string, onset: number) => `${label}|${onset.toFixed(2)}`;

export function AppProvider({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(false);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [settings, setSettings] = useState<Settings>(FALLBACK);
  const [apiBase, setApiBaseState] = useState(getApiBase());
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [lastKey, setLastKey] = useState('');
  const [metaTick, setMetaTick] = useState(0);

  useEffect(() => {
    let live = true;
    api.meta()
      .then((m) => { if (live) { setMeta(m); setSettings(m.validated); setMetaError(null); } })
      .catch((e: Error) => { if (live) setMetaError(e.message); });
    return () => { live = false; };
  }, [apiBase, metaTick]);
  const reloadMeta = useCallback(() => setMetaTick((t) => t + 1), []);

  const validated = meta?.validated ?? FALLBACK;
  const value = useMemo<Ctx>(() => ({
    dark, setDark, colors: dark ? Palettes.dark : Palettes.light,
    settings,
    setSetting: (k, v) => setSettings((s) => {
      const next = { ...s, [k]: v };
      if (next.lo > next.hi) next.lo = next.hi;   // continue threshold can't exceed the start threshold
      return next;
    }),
    resetSettings: () => setSettings(validated),
    validated,
    changed: SETTING_KEYS.filter((k) => Math.abs(settings[k] - validated[k]) > 1e-6),
    meta, metaError, reloadMeta,
    apiBase,
    setServer: (url) => { setApiBase(url); setApiBaseState(url ? getApiBase() : defaultApiBase()); },
    notes,
    setNote: (label, onset, call) => setNotes((n) => {
      const next = { ...n }; const k = noteKey(label, onset);
      if (call) next[k] = call; else delete next[k];
      return next;
    }),
    history,
    logHistory: (row, key) => {
      if (key === lastKey) return;
      setLastKey(key); setHistory((h) => [...h, row]);
    },
    clearSession: () => { setHistory([]); setNotes({}); setLastKey(''); },
  }), [dark, settings, validated, meta, metaError, reloadMeta, apiBase, notes, history, lastKey]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): Ctx {
  const c = useContext(AppContext);
  if (!c) throw new Error('useApp must be used inside <AppProvider>');
  return c;
}
