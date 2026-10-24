/** Client for the SWALLOHear API (repo/api/server.py). */
import Constants from 'expo-constants';
import { Platform } from 'react-native';

import type { Analysis, BatchRow, Loaded, LocalFile, Meta, Settings, Stress, SweepRow } from './types';

export const API_PORT = 8000;

/**
 * Where the API lives when no override is set: the Expo dev server the app was loaded from. Its metro.config.js
 * forwards /api/* to api/server.py on the same computer, so whatever address the phone used to load the app
 * (home Wi-Fi, a hotspot, a tunnel) also reaches the analysis, with no configuration.
 * Builds without a dev server fall back to port 8000 on this device; set the address under ⚙ instead.
 */
export function defaultApiBase(): string {
  if (Platform.OS === 'web' && typeof window !== 'undefined') return window.location.origin;
  const hostUri = Constants.expoConfig?.hostUri;
  return hostUri ? `http://${hostUri}` : `http://localhost:${API_PORT}`;
}

let base = defaultApiBase();
export const setApiBase = (url: string | null) => { base = (url || defaultApiBase()).replace(/\/+$/, ''); };
export const getApiBase = () => base;
export const absolute = (path: string) => (path.startsWith('http') ? path : `${base}${path}`);

async function request<T>(path: string, init?: RequestInit, timeoutMs = 120000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(absolute(path), { ...init, signal: ctrl.signal });
  } catch {
    throw new Error(`Can't reach the analysis server at ${base}. Check that "npx expo start" and "python api/server.py" are both running on the computer, then reload the app.`);
  } finally {
    clearTimeout(timer);
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body?.error ?? `Server error ${res.status}`);
  return body as T;
}

const json = (obj: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj) });

/** Adds a picked or recorded file to a form in the shape each platform's fetch understands. */
async function appendFile(form: FormData, field: string, f: LocalFile) {
  if (Platform.OS === 'web') {
    const blob = f.file ?? (await (await fetch(f.uri)).blob());
    form.append(field, blob, f.name);
  } else {
    // React Native's FormData takes a { uri, name, type } descriptor and streams the file itself.
    form.append(field, { uri: f.uri, name: f.name, type: f.mimeType ?? 'application/octet-stream' } as unknown as Blob);
  }
}

export const api = {
  health: () => request<{ ok: boolean }>('/api/health', undefined, 4000),
  meta: () => request<Meta>('/api/meta'),

  loadDemo(name: string) {
    const f = new FormData(); f.append('source', 'demo'); f.append('demo', name);
    return request<Loaded>('/api/load', { method: 'POST', body: f });
  },
  loadSynthetic(n: number, duration: number, seed: number) {
    const f = new FormData(); f.append('source', 'synthetic');
    f.append('n', String(n)); f.append('duration', String(duration)); f.append('seed', String(seed));
    return request<Loaded>('/api/load', { method: 'POST', body: f });
  },
  async loadFile(file: LocalFile, label?: string) {
    const f = new FormData(); f.append('source', 'upload');
    if (label) f.append('label', label);
    await appendFile(f, 'file', file);
    return request<Loaded>('/api/load', { method: 'POST', body: f });
  },

  analyze: (rec_id: string, settings: Settings, stress: Stress) => request<Analysis>('/api/analyze', json({ rec_id, settings, stress })),
  sweep: (rec_id: string, settings: Settings, noise_kind: string) =>
    request<{ rows: SweepRow[]; snr_min: number }>('/api/sweep', json({ rec_id, settings, noise_kind }), 300000),
  saveNotes: (aid: string, notes: Record<string, string>) =>
    request<{ report_url: string }>(`/api/analysis/${aid}/notes`, json({ notes })),

  async batch(demos: string[], files: LocalFile[], settings: Settings, noise: { kind: string; snr: number } | null) {
    const f = new FormData();
    f.append('demos', JSON.stringify(demos)); f.append('settings', JSON.stringify(settings));
    if (noise) { f.append('noise_kind', noise.kind); f.append('snr', String(noise.snr)); }
    for (const file of files) await appendFile(f, 'files', file);
    return request<{ rows: BatchRow[]; settings: Settings }>('/api/batch', { method: 'POST', body: f }, 600000);
  },

  /** The server adds 0.25 s either side, like the web app's event clips. */
  clipUrl: (a: Analysis, t0: number, t1: number) => absolute(`${a.audio_url}?t0=${t0.toFixed(3)}&t1=${t1.toFixed(3)}`),
};
