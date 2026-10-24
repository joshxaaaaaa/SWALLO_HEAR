/** Colours and spacing shared by every screen. They mirror the Streamlit web app (app/views/common.py). */
import { Platform } from 'react-native';

export const Brand = {
  teal: '#1B7F7A',
  amber: '#E0A458',
  slate: '#7A8A94',
  green: '#2E9E6B',
  red: '#C8553D',
} as const;

export const TierColor: Record<string, string> = { Confident: Brand.teal, 'Low-confidence': Brand.amber };

const light = {
  mode: 'light' as const,
  bg: '#FFFFFF',
  surface: '#F0F2F6',      // Streamlit's sidebar / secondary background
  card: '#FFFFFF',
  border: '#DDE3E0',
  text: '#31333F',
  muted: '#6A7780',
  ink: '#244668',          // waveform and spectrum lines
  grid: 'rgba(49,51,63,0.10)',
  warnBg: '#FFFBE6',
  warnBorder: '#F2DFA7',
  warnText: '#7A5B12',
};

const dark: typeof light = {
  mode: 'dark' as unknown as 'light',
  bg: '#0E1117',
  surface: '#262730',
  card: '#0E1117',
  border: 'rgba(250,250,250,0.18)',
  text: '#FAFAFA',
  muted: '#A3A8B4',
  ink: '#C9D6E3',
  grid: 'rgba(250,250,250,0.10)',
  warnBg: '#3A3519',
  warnBorder: '#5E5424',
  warnText: '#F4E3A3',
};

export const Palettes = { light, dark };
export type Palette = typeof light;

export const Space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const;
export const Radius = { sm: 6, md: 10, lg: 14, pill: 999 } as const;
export const MaxWidth = 960;

export const Mono = Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' });

/** Mix a hex colour with transparency, e.g. tint('#1B7F7A', 0.13). */
export function tint(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}
