/** Shapes returned by api/server.py. */

export type Settings = { tau: number; hi: number; lo: number; merge: number; snr_min: number };
export type Stress = { noise_kind?: string | null; snr?: number | null; clip?: boolean };
export type Status = 'Analyzable' | 'No event' | 'Inconclusive';

export type Explain = { intercept: number; contrib: number[]; typical: number[] };

export type SwEvent = {
  index: number;
  onset_s: number;
  offset_s: number;
  duration_ms: number;
  reliability: number;
  model_confidence: number;
  tier: 'Confident' | 'Low-confidence';
  features: number[];
  explain: Explain | null;
  up: string[];
  down: string[];
};

export type Rhythm = {
  n: number;
  rate: number;
  iei: number[];
  onsets: number[];
  mean_iei: number | null;
  median_iei: number | null;
  cv: number | null;
  regularity: string | null;
  longest_gap: number;
};

export type Analysis = {
  id: string;
  rec_id: string;
  label: string;
  note: string;
  source: string;
  status: Status;
  verdict: { colour: string; icon: string; headline: string; text: string };
  reason_codes: string[];
  reason_help: Record<string, string>;
  settings: Settings;
  changed: string[];
  stress: string | null;
  duration_s: number;
  orig_fs: number;
  nyquist: number;
  latency_s: number;
  quality: { snr_db: number; clip_frac: number; flat_frac: number; duration_s: number };
  checks: { name: string; value: string; limit: string; ok: boolean }[];
  counts: { confident: number; low: number; withheld: number };
  rate_per_min: number;
  events: SwEvent[];
  faded: boolean;
  frames: { t: number[]; p: number[] };
  envelope: { t: number[]; lo: number[]; hi: number[] };
  spectrogram: string | null;
  energy: { counts: number[]; edges: number[]; floor: number; peak: number };
  psd: { f: number[]; db: number[] };
  ref: [number, number][];
  expert: null | {
    tp: number; fp: number; fn: number; precision: number; recall: number; f1: number;
    onset_err_ms: number | null; offset_err_ms: number | null;
    pairs: Record<string, number>; matched_ref: number[];
  };
  rhythm: Rhythm;
  audio_url: string;
};

export type Loaded = { rec_id: string; label: string; duration_s: number; labels: number; note: string };

export type Meta = {
  validated: Settings;
  noise_kinds: string[];
  demos: { name: string; note: string; labels: number; duration_s: number }[];
  features: { name: string; help: string; fmt: string }[];
  code_help: Record<string, string>;
  status: Record<string, { colour: string; icon: string; headline: string; text: string }>;
  results: {
    E2_E4: Record<string, Record<string, { precision: number; recall: number; f1: number }>>;
    E3: Record<string, {
      auroc_mean_prob?: number; auroc_learned?: number;
      ordinary?: { precision: number; recall: number; f1: number };
      reliability_aware?: { precision: number; recall: number; f1: number };
    }>;
  };
};

export type SweepRow = { level: string; status: Status; confident: number; low: number; withheld: number; est_snr: number; f1: number | null };

export type BatchRow = {
  recording: string; status: string; reasons?: string; duration_s?: number; snr_db?: number; confident?: number; low?: number;
  mean_reliability?: number | null; per_min?: number; labels?: number | null; f1?: number | null;
};

/** A local file chosen with the document picker or produced by the recorder. */
export type LocalFile = { uri: string; name: string; mimeType?: string; file?: Blob };
