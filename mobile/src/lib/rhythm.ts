/** Same rhythm numbers as app/views/common.py rhythm(), so "Confident only" can be recomputed on the phone. */
import type { Rhythm, SwEvent } from './types';

export function rhythm(events: SwEvent[], duration: number): Rhythm {
  const ev = [...events].sort((a, b) => a.onset_s - b.onset_s); const on = ev.map((e) => e.onset_s); const n = ev.length;
  const iei = on.slice(1).map((t, i) => t - on[i]);
  const mean = iei.length ? iei.reduce((s, v) => s + v, 0) / iei.length : null;
  const sd = iei.length > 1 && mean ? Math.sqrt(iei.reduce((s, v) => s + (v - mean) ** 2, 0) / iei.length) : null;
  const cv = sd !== null && mean ? sd / mean : null;
  const gaps = n ? [ev[0].onset_s, ...ev.slice(1).map((e, i) => e.onset_s - ev[i].offset_s), duration - ev[n - 1].offset_s] : [duration];
  const sorted = [...iei].sort((a, b) => a - b);
  return {
    n, rate: n / Math.max(duration / 60, 1e-9), iei, onsets: on, mean_iei: mean,
    median_iei: sorted.length ? (sorted.length % 2 ? sorted[(sorted.length - 1) / 2] : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2) : null,
    cv, regularity: cv === null ? null : cv < 0.25 ? 'steady' : cv < 0.5 ? 'moderate' : 'irregular', longest_gap: Math.max(...gaps),
  };
}
