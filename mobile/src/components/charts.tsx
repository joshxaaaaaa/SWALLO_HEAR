/** SVG charts matching the web app's Plotly figures: timeline, gauge, waterfall, sweep, rhythm, quality, lanes, scatter. */
import { useState, type ReactNode } from 'react';
import { Image, Pressable, ScrollView, Text, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Circle, G, Line, Path, Rect, Text as SvgText } from 'react-native-svg';

import { useApp } from '@/lib/state';
import { Brand, TierColor, tint } from '@/lib/theme';
import type { Analysis, Explain, SwEvent } from '@/lib/types';

// ----------------------------------------------------------------------------- plumbing
export function useWidth(initial = 320): [number, (e: LayoutChangeEvent) => void] {
  const [w, setW] = useState(initial);
  // Hidden or collapsing views report ~0 width; keep the last real width instead of drawing a degenerate chart.
  return [w, (e) => { const nw = Math.round(e.nativeEvent.layout.width); if (nw >= 80 && Math.abs(nw - w) > 1) setW(nw); }];
}

export function niceTicks(a: number, b: number, n = 4): number[] {
  const span = b - a;
  if (!(span > 0)) return [a];
  const raw = span / n; const mag = 10 ** Math.floor(Math.log10(raw)); const r = raw / mag;
  const step = (r >= 7.5 ? 10 : r >= 3.5 ? 5 : r >= 1.5 ? 2 : 1) * mag;
  const out: number[] = [];
  for (let v = Math.ceil(a / step) * step; v <= b + step * 1e-6; v += step) out.push(+v.toFixed(10));
  return out;
}

type Scale = (v: number) => number;
type Pad = { l: number; r: number; t: number; b: number };
const PAD: Pad = { l: 40, r: 10, t: 18, b: 26 };

/** One chart panel: grid, axes and a coordinate system; `children` draws into it, `under` sits beneath (images). */
export function Plot({ width, height, x, y, pad = PAD, title, xLabel, yLabel, xTicks, yTicks, xFmt = fmtNum, yFmt = fmtNum,
  hideX, children, under, over }: {
  width: number; height: number; x: [number, number]; y: [number, number]; pad?: Partial<Pad>; title?: string;
  xLabel?: string; yLabel?: string; xTicks?: number[] | { v: number; label: string }[]; yTicks?: number[];
  xFmt?: (v: number) => string; yFmt?: (v: number) => string; hideX?: boolean;
  children?: (sx: Scale, sy: Scale, inner: { w: number; h: number; l: number; t: number }) => ReactNode;
  under?: (inner: { w: number; h: number; l: number; t: number }) => ReactNode;
  /** Native views on top of the chart, in the same coordinates (touch targets: SVG press handling differs per platform). */
  over?: (sx: Scale, sy: Scale) => ReactNode;
}) {
  const { colors } = useApp();
  const p = { ...PAD, ...pad };
  const w = Math.max(10, width - p.l - p.r); const h = Math.max(10, height - p.t - p.b);
  const sx: Scale = (v) => p.l + ((v - x[0]) / (x[1] - x[0] || 1)) * w;
  const sy: Scale = (v) => p.t + h - ((v - y[0]) / (y[1] - y[0] || 1)) * h;
  const xt = (xTicks ?? niceTicks(x[0], x[1], Math.max(2, Math.floor(w / 70)))).map((t) => (typeof t === 'number' ? { v: t, label: xFmt(t) } : t));
  const yt = yTicks ?? niceTicks(y[0], y[1], Math.max(2, Math.floor(h / 32)));
  const inner = { w, h, l: p.l, t: p.t };
  return (
    <View style={{ width, height }}>
      {under ? <View style={{ position: 'absolute', left: p.l, top: p.t, width: w, height: h }}>{under(inner)}</View> : null}
      <Svg width={width} height={height} style={{ position: 'absolute' }}>
        {title ? <SvgText x={p.l} y={12} fontSize={11} fill={colors.muted} fontWeight="600">{title}</SvgText> : null}
        {yt.map((t) => (
          <G key={`y${t}`}>
            <Line x1={p.l} x2={p.l + w} y1={sy(t)} y2={sy(t)} stroke={colors.grid} strokeWidth={1} />
            <SvgText x={p.l - 5} y={sy(t) + 3.5} fontSize={10} fill={colors.muted} textAnchor="end">{yFmt(t)}</SvgText>
          </G>
        ))}
        {!hideX && xt.map((t) => (
          <SvgText key={`x${t.v}`} x={sx(t.v)} y={p.t + h + 14} fontSize={10} fill={colors.muted} textAnchor="middle">{t.label}</SvgText>
        ))}
        {xLabel && !hideX ? <SvgText x={p.l + w / 2} y={height - 2} fontSize={10} fill={colors.muted} textAnchor="middle">{xLabel}</SvgText> : null}
        {yLabel ? <SvgText x={10} y={p.t + h / 2} fontSize={10} fill={colors.muted} textAnchor="middle" transform={`rotate(-90 10 ${p.t + h / 2})`}>{yLabel}</SvgText> : null}
        {children?.(sx, sy, inner)}
      </Svg>
      {over ? <View pointerEvents="box-none" style={{ position: 'absolute', left: 0, top: 0, width, height }}>{over(sx, sy)}</View> : null}
    </View>
  );
}

export const fmtNum =(v: number) => (Math.abs(v) >= 100 || Number.isInteger(v) ? String(Math.round(v)) : v.toFixed(Math.abs(v) < 1 ? 2 : 1));

function linePath(xs: number[], ys: number[], sx: Scale, sy: Scale, step = false): string {
  let d = '';
  xs.forEach((x, i) => {
    if (ys[i] === null || ys[i] === undefined || Number.isNaN(ys[i])) return;
    if (!d) d = `M${sx(x)},${sy(ys[i])}`;
    else d += step ? `H${sx(x)}V${sy(ys[i])}` : `L${sx(x)},${sy(ys[i])}`;
  });
  return d;
}

function waveformPath(env: Analysis['envelope'], sx: Scale, sy: Scale, t0 = -Infinity, t1 = Infinity): string {
  let d = '';
  env.t.forEach((t, i) => { if (t >= t0 && t <= t1) { const X = sx(t).toFixed(1); d += `M${X},${sy(env.lo[i]).toFixed(1)}V${sy(env.hi[i]).toFixed(1)}`; } });
  return d;
}

// ----------------------------------------------------------------------------- timeline
/** Waveform, spectrogram and detector score sharing one time axis. Tap a numbered marker to select an event. */
export function Timeline({ a, events, faded, showSpec = true, showRef = false, selected, onSelect, hi, lo, zoom = 1, xMax, compact }: {
  a: Analysis; events: SwEvent[]; faded?: boolean; showSpec?: boolean; showRef?: boolean; selected?: number | null;
  onSelect?: (i: number) => void; hi: number; lo: number; zoom?: number; xMax?: number; compact?: boolean;
}) {
  const { colors } = useApp();
  const [box, onLayout] = useWidth();
  const W = box * zoom; const dur = xMax ?? a.duration_s; const X: [number, number] = [0, dur];
  const amp = Math.max(1e-6, ...a.envelope.hi.map(Math.abs), ...a.envelope.lo.map(Math.abs));
  const pad = { l: 36, r: 8 };

  const bands = (sx: Scale, inner: { h: number; t: number }, row: 'top' | 'bottom') => (
    <G>
      {showRef && a.ref.map(([s, e], j) => (
        <Rect key={`r${j}`} x={sx(s)} y={inner.t} width={Math.max(1, sx(e) - sx(s))} height={inner.h} fill="none"
          stroke={Brand.green} strokeWidth={1.5} strokeDasharray="4,3" />
      ))}
      {events.map((e, i) => {
        const c = TierColor[e.tier]; const sel = i === selected;
        return (
          <Rect key={`e${i}`} x={sx(e.onset_s)} y={inner.t} width={Math.max(1.5, sx(e.offset_s) - sx(e.onset_s))} height={inner.h}
            fill={c} fillOpacity={sel ? 0.35 : faded ? 0.08 : 0.2} stroke={sel ? c : 'none'} strokeWidth={sel ? 2 : 0} />
        );
      })}
    </G>
  );

  const H = compact ? { w: 80, s: 80, p: 110 } : { w: 110, s: 105, p: 140 };
  const body = (
    <View style={{ width: W }}>
      <Plot width={W} height={H.w} x={X} y={[-amp, amp]} pad={{ ...pad, b: 4 }} yTicks={[]} title="Waveform" hideX>
        {(sx, sy, inner) => (<>
          {bands(sx, inner, 'top')}
          <Path d={waveformPath(a.envelope, sx, sy)} stroke={colors.ink} strokeWidth={1} />
        </>)}
      </Plot>
      {showSpec && a.spectrogram ? (
        <Plot width={W} height={H.s} x={X} y={[0, 2000]} pad={{ ...pad, b: 4 }} yTicks={[0, 1000, 2000]} title="Spectrogram (0–2 kHz)" hideX
          under={() => <Image source={{ uri: a.spectrogram! }} resizeMode="stretch" style={{ width: '100%', height: '100%' }} />}>
          {(sx, _sy, inner) => bands(sx, inner, 'top')}
        </Plot>
      ) : null}
      <Plot width={W} height={H.p} x={X} y={[0, 1.15]} pad={pad} yTicks={[0, 0.5, 1]} title="Detector score per 16 ms frame" xLabel="time (s)"
        over={onSelect ? (sx, sy) => events.map((e, i) => (
          <Pressable key={i} onPress={() => onSelect(i)} accessibilityRole="button" accessibilityLabel={`Event ${i + 1}`} hitSlop={6}
            style={{ position: 'absolute', left: sx((e.onset_s + e.offset_s) / 2) - 16, top: sy(1.07) - 16, width: 32, height: 32, borderRadius: 16 }} />
        )) : undefined}>
        {(sx, sy, inner) => {
          const line = linePath(a.frames.t, a.frames.p, sx, sy);
          return (<>
            {bands(sx, inner, 'bottom')}
            <Path d={`${line}V${sy(0)}H${sx(a.frames.t[0] ?? 0)}Z`} fill={tint(Brand.slate, 0.12)} />
            <Path d={line} stroke={Brand.slate} strokeWidth={1.4} fill="none" />
            <Line x1={inner.l} x2={inner.l + inner.w} y1={sy(hi)} y2={sy(hi)} stroke={Brand.teal} strokeDasharray="5,4" />
            <Line x1={inner.l} x2={inner.l + inner.w} y1={sy(lo)} y2={sy(lo)} stroke={Brand.teal} strokeDasharray="2,3" />
            <SvgText x={inner.l + 4} y={sy(hi) - 3} fontSize={9} fill={Brand.teal}>{`start ${hi.toFixed(2)}`}</SvgText>
            {events.map((e, i) => {
              const cx = sx((e.onset_s + e.offset_s) / 2); const r = i === selected ? 12 : 10;
              return (
                <G key={`m${i}`}>
                  <Circle cx={cx} cy={sy(1.07)} r={r} fill={TierColor[e.tier]} stroke="#fff" strokeWidth={2} opacity={faded ? 0.55 : 1} />
                  <SvgText x={cx} y={sy(1.07) + 4} fontSize={11} fontWeight="700" fill="#fff" textAnchor="middle">{String(i + 1)}</SvgText>
                </G>
              );
            })}
          </>);
        }}
      </Plot>
    </View>
  );
  return (
    <View onLayout={onLayout}>
      {zoom > 1 ? <ScrollView horizontal showsHorizontalScrollIndicator>{body}</ScrollView> : body}
    </View>
  );
}

export function EventZoom({ a, e, pad = 1 }: { a: Analysis; e: SwEvent; pad?: number }) {
  const { colors } = useApp();
  const [w, onLayout] = useWidth();
  const t0 = Math.max(0, e.onset_s - pad); const t1 = Math.min(a.duration_s, e.offset_s + pad);
  const idx = a.envelope.t.map((t, i) => (t >= t0 && t <= t1 ? i : -1)).filter((i) => i >= 0);
  const amp = Math.max(1e-6, ...idx.map((i) => Math.max(Math.abs(a.envelope.lo[i]), Math.abs(a.envelope.hi[i]))));
  const c = TierColor[e.tier];
  const band = (sx: Scale, inner: { h: number; t: number }) =>
    <Rect x={sx(e.onset_s)} y={inner.t} width={sx(e.offset_s) - sx(e.onset_s)} height={inner.h} fill={c} fillOpacity={0.22} />;
  return (
    <View onLayout={onLayout}>
      <Plot width={w} height={80} x={[t0, t1]} y={[-amp, amp]} yTicks={[]} hideX pad={{ l: 30, b: 2, t: 6 }}>
        {(sx, sy, inner) => (<>{band(sx, inner)}<Path d={waveformPath(a.envelope, sx, sy, t0, t1)} stroke={colors.ink} strokeWidth={1} /></>)}
      </Plot>
      <Plot width={w} height={100} x={[t0, t1]} y={[0, 1]} yTicks={[0, 0.5, 1]} pad={{ l: 30, t: 6 }}>
        {(sx, sy, inner) => {
          const xs = a.frames.t.filter((t) => t >= t0 && t <= t1); const ys = a.frames.p.filter((_, i) => a.frames.t[i] >= t0 && a.frames.t[i] <= t1);
          return (<>{band(sx, inner)}<Path d={linePath(xs, ys, sx, sy)} stroke={Brand.slate} strokeWidth={1.5} fill="none" /></>);
        }}
      </Plot>
    </View>
  );
}

// ----------------------------------------------------------------------------- gauge & explanation
export function Gauge({ value, tau, tier }: { value: number; tau: number; tier: string }) {
  const { colors } = useApp();
  const W = 220, H = 128, cx = W / 2, cy = 110, R = 86;
  const pt = (v: number, r = R) => { const a = Math.PI * (1 - v); return [cx + r * Math.cos(a), cy - r * Math.sin(a)]; };
  const arc = (v0: number, v1: number, r = R) => { const [x0, y0] = pt(v0, r); const [x1, y1] = pt(v1, r); return `M${x0},${y0}A${r},${r} 0 0 1 ${x1},${y1}`; };
  const [tx0, ty0] = pt(tau, R - 18); const [tx1, ty1] = pt(tau, R + 10);
  return (
    <View style={{ alignItems: 'center' }}>
      <Svg width={W} height={H}>
        <Path d={arc(0, tau)} stroke={tint(Brand.amber, 0.25)} strokeWidth={18} fill="none" />
        <Path d={arc(tau, 1)} stroke={tint(Brand.teal, 0.25)} strokeWidth={18} fill="none" />
        <Path d={arc(0, Math.max(0.001, Math.min(1, value)))} stroke={TierColor[tier]} strokeWidth={10} fill="none" />
        <Line x1={tx0} y1={ty0} x2={tx1} y2={ty1} stroke={colors.ink} strokeWidth={3} />
        <SvgText x={tx1} y={ty1 - 4} fontSize={10} fill={colors.muted} textAnchor="middle">{tau.toFixed(2)}</SvgText>
        <SvgText x={cx} y={cy - 6} fontSize={32} fill={colors.text} textAnchor="middle">{value.toFixed(2)}</SvgText>
        <SvgText x={cx - R} y={cy + 14} fontSize={10} fill={colors.muted} textAnchor="middle">0</SvgText>
        <SvgText x={cx + R} y={cy + 14} fontSize={10} fill={colors.muted} textAnchor="middle">1</SvgText>
      </Svg>
    </View>
  );
}

/** The reliability score as a sum: average event, then each measurement's push, then this event. */
export function Waterfall({ ex, names, tau }: { ex: Explain; names: string[]; tau: number }) {
  const { colors } = useApp();
  const [w, onLayout] = useWidth();
  const order = ex.contrib.map((_, i) => i).sort((i, j) => Math.abs(ex.contrib[j]) - Math.abs(ex.contrib[i]));
  const total = ex.intercept + ex.contrib.reduce((s, v) => s + v, 0); const p = 1 / (1 + Math.exp(-total));
  const thr = Math.log(tau / (1 - tau));
  const steps: { label: string; from: number; to: number; color: string; text: string }[] = [{ label: 'Average event', from: 0, to: ex.intercept, color: Brand.slate, text: ex.intercept.toFixed(2) }];
  let run = ex.intercept;
  for (const i of order) { steps.push({ label: names[i], from: run, to: run + ex.contrib[i], color: ex.contrib[i] >= 0 ? Brand.teal : Brand.amber, text: `${ex.contrib[i] >= 0 ? '+' : ''}${ex.contrib[i].toFixed(2)}` }); run += ex.contrib[i]; }
  steps.push({ label: 'This event', from: 0, to: total, color: Brand.slate, text: `${total.toFixed(2)} → ${p.toFixed(2)}` });
  const vals = steps.flatMap((s) => [s.from, s.to]).concat(thr, 0);
  const lo = Math.min(...vals) - 0.3, hi = Math.max(...vals) + 0.6;
  const labelW = Math.min(150, w * 0.42); const rowH = 26; const H = steps.length * rowH + 34;
  return (
    <View onLayout={onLayout}>
      <Plot width={w} height={H} x={[lo, hi]} y={[0, steps.length]} yTicks={[]} pad={{ l: labelW, r: 72, t: 8, b: 26 }} xLabel="← less reliable · log-odds · more reliable →">
        {(sx, sy, inner) => (<>
          <Line x1={sx(thr)} x2={sx(thr)} y1={inner.t} y2={inner.t + inner.h} stroke={Brand.red} strokeDasharray="5,4" />
          {steps.map((s, k) => {
            const y = sy(steps.length - k) + 4; const x0 = sx(Math.min(s.from, s.to)); const x1 = sx(Math.max(s.from, s.to));
            return (
              <G key={k}>
                <SvgText x={labelW - 6} y={y + 12} fontSize={10.5} fill={colors.text} textAnchor="end">{s.label.length > 24 ? `${s.label.slice(0, 23)}…` : s.label}</SvgText>
                <Rect x={x0} y={y} width={Math.max(2, x1 - x0)} height={rowH - 8} fill={s.color} rx={2} />
                <SvgText x={x1 + 4} y={y + 12} fontSize={10} fill={colors.muted}>{s.text}</SvgText>
              </G>
            );
          })}
        </>)}
      </Plot>
    </View>
  );
}

// ----------------------------------------------------------------------------- generic charts
export type Series = { name: string; x: number[]; y: (number | null)[]; color: string; dash?: string; step?: boolean; width?: number; dots?: boolean };

export function LineChart({ series, height = 220, x, y, xLabel, yLabel, xTicks, hlines = [], vlines = [], legend = true }: {
  series: Series[]; height?: number; x?: [number, number]; y?: [number, number]; xLabel?: string; yLabel?: string;
  xTicks?: { v: number; label: string }[]; hlines?: { v: number; color: string; label?: string }[]; vlines?: { v: number; color: string; label?: string }[]; legend?: boolean;
}) {
  const [w, onLayout] = useWidth();
  const allX = series.flatMap((s) => s.x); const allY = series.flatMap((s) => s.y.filter((v): v is number => v !== null)).concat(hlines.map((h) => h.v));
  const X = x ?? [Math.min(...allX), Math.max(...allX)]; const Y = y ?? [Math.min(...allY), Math.max(...allY) * 1.05 || 1];
  return (
    <View onLayout={onLayout} style={{ gap: 4 }}>
      <Plot width={w} height={height} x={X} y={Y} xLabel={xLabel} yLabel={yLabel} xTicks={xTicks}>
        {(sx, sy, inner) => (<>
          {hlines.map((h, k) => (<G key={`h${k}`}><Line x1={inner.l} x2={inner.l + inner.w} y1={sy(h.v)} y2={sy(h.v)} stroke={h.color} strokeDasharray="5,4" />
            {h.label ? <SvgText x={inner.l + inner.w - 2} y={sy(h.v) - 3} fontSize={9} fill={h.color} textAnchor="end">{h.label}</SvgText> : null}</G>))}
          {vlines.map((v, k) => (<G key={`v${k}`}><Line x1={sx(v.v)} x2={sx(v.v)} y1={inner.t} y2={inner.t + inner.h} stroke={v.color} strokeWidth={1.5} />
            {v.label ? <SvgText x={sx(v.v) + 3} y={inner.t + 9} fontSize={9} fill={v.color}>{v.label}</SvgText> : null}</G>))}
          {series.map((s) => (
            <G key={s.name}>
              <Path d={linePath(s.x, s.y as number[], sx, sy, s.step)} stroke={s.color} strokeWidth={s.width ?? 2} strokeDasharray={s.dash} fill="none" />
              {s.dots && s.x.map((xv, i) => (s.y[i] === null ? null : <Circle key={i} cx={sx(xv)} cy={sy(s.y[i] as number)} r={3.5} fill={s.color} />))}
            </G>
          ))}
        </>)}
      </Plot>
      {legend && series.length > 1 ? <Legend items={series.map((s) => ({ label: s.name, color: s.color }))} /> : null}
    </View>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  const { colors } = useApp();
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, paddingLeft: 36 }}>
      {items.map((it) => (
        <View key={it.label} style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
          <View style={{ width: 12, height: 4, borderRadius: 2, backgroundColor: it.color }} />
          <Text style={{ fontSize: 11, color: colors.muted }}>{it.label}</Text>
        </View>
      ))}
    </View>
  );
}

/** Categorical bars; each category can stack several segments. `line` adds a series on a right-hand axis. */
export function Bars({ categories, stacks, height = 240, yLabel, line, hline, yMax }: {
  categories: string[]; stacks: { name: string; values: number[]; color: string }[]; height?: number; yLabel?: string;
  line?: { name: string; values: (number | null)[]; color: string; range: [number, number]; label?: string; ref?: { v: number; color: string; label: string } };
  hline?: { v: number; color: string; label?: string }; yMax?: number;
}) {
  const { colors } = useApp();
  const [w, onLayout] = useWidth();
  const totals = categories.map((_, i) => stacks.reduce((s, st) => s + (st.values[i] ?? 0), 0));
  const top = yMax ?? Math.max(1, ...totals, hline?.v ?? 0) * 1.12; const n = categories.length;
  return (
    <View onLayout={onLayout} style={{ gap: 4 }}>
      <Plot width={w} height={height} x={[0, n]} y={[0, top]} yLabel={yLabel} pad={{ r: line ? 40 : 10 }}
        xTicks={categories.map((c, i) => ({ v: i + 0.5, label: c }))}>
        {(sx, sy, inner) => {
          const bw = (inner.w / n) * 0.62;
          const ly = line ? (v: number) => inner.t + inner.h - ((v - line.range[0]) / (line.range[1] - line.range[0])) * inner.h : null;
          return (<>
            {categories.map((_, i) => {
              let acc = 0;
              return stacks.map((st) => {
                const v = st.values[i] ?? 0; const y0 = sy(acc); acc += v; const y1 = sy(acc);
                return v > 0 ? <Rect key={`${st.name}${i}`} x={sx(i + 0.5) - bw / 2} y={y1} width={bw} height={Math.max(0, y0 - y1)} fill={st.color} /> : null;
              });
            })}
            {hline ? <Line x1={inner.l} x2={inner.l + inner.w} y1={sy(hline.v)} y2={sy(hline.v)} stroke={hline.color} strokeDasharray="5,4" /> : null}
            {hline?.label ? <SvgText x={inner.l + inner.w - 2} y={sy(hline.v) - 3} fontSize={9} fill={hline.color} textAnchor="end">{hline.label}</SvgText> : null}
            {line && ly ? (<>
              {line.ref ? <Line x1={inner.l} x2={inner.l + inner.w} y1={ly(line.ref.v)} y2={ly(line.ref.v)} stroke={line.ref.color} strokeDasharray="6,4" strokeWidth={1.5} /> : null}
              <Path d={line.values.map((v, i) => (v === null ? '' : `${i === 0 ? 'M' : 'L'}${sx(i + 0.5)},${ly(v)}`)).join('')} stroke={line.color} strokeWidth={2} fill="none" />
              {line.values.map((v, i) => (v === null ? null : <Circle key={i} cx={sx(i + 0.5)} cy={ly(v)} r={3.5} fill={line.color} />))}
              {niceTicks(line.range[0], line.range[1], 4).map((t) => (
                <SvgText key={t} x={inner.l + inner.w + 4} y={ly(t) + 3} fontSize={9.5} fill={colors.muted}>{fmtNum(t)}</SvgText>
              ))}
            </>) : null}
          </>);
        }}
      </Plot>
      <Legend items={[...stacks.map((s) => ({ label: s.name, color: s.color })), ...(line ? [{ label: line.name, color: line.color }] : []),
        ...(line?.ref ? [{ label: line.ref.label, color: line.ref.color }] : [])]} />
    </View>
  );
}

export function GroupedBars({ categories, groups, height = 220, yMax = 1 }: {
  categories: string[]; groups: { name: string; values: (number | null)[]; color: string }[]; height?: number; yMax?: number;
}) {
  const { colors } = useApp();
  const [w, onLayout] = useWidth();
  const n = categories.length; const g = groups.length;
  return (
    <View onLayout={onLayout} style={{ gap: 4 }}>
      <Plot width={w} height={height} x={[0, n]} y={[0, yMax]} xTicks={categories.map((c, i) => ({ v: i + 0.5, label: c }))}>
        {(sx, sy, inner) => {
          const slot = inner.w / n; const bw = (slot * 0.7) / g;
          return groups.map((gr, k) => gr.values.map((v, i) => {
            if (v === null) return null;
            const x = sx(i) + slot * 0.15 + k * bw;
            return (<G key={`${k}${i}`}><Rect x={x} y={sy(v)} width={Math.max(1, bw - 2)} height={Math.max(0, sy(0) - sy(v))} fill={gr.color} />
              <SvgText x={x + bw / 2 - 1} y={sy(v) - 3} fontSize={9.5} fill={colors.muted} textAnchor="middle">{v.toFixed(2)}</SvgText></G>);
          }));
        }}
      </Plot>
      <Legend items={groups.map((gr) => ({ label: gr.name, color: gr.color }))} />
    </View>
  );
}

export function Histogram({ counts, edges, marks, xLabel }: { counts: number[]; edges: number[]; marks: { v: number; color: string; label: string }[]; xLabel: string }) {
  const [w, onLayout] = useWidth();
  return (
    <View onLayout={onLayout}>
      <Plot width={w} height={200} x={[edges[0], edges[edges.length - 1]]} y={[0, Math.max(...counts) * 1.15]} xLabel={xLabel} yLabel="frames">
        {(sx, sy, inner) => (<>
          {counts.map((c, i) => <Rect key={i} x={sx(edges[i]) + 0.5} y={sy(c)} width={Math.max(1, sx(edges[i + 1]) - sx(edges[i]) - 1)} height={sy(0) - sy(c)} fill={tint(Brand.slate, 0.6)} />)}
          {marks.map((m, k) => (<G key={k}><Line x1={sx(m.v)} x2={sx(m.v)} y1={inner.t} y2={inner.t + inner.h} stroke={m.color} strokeWidth={2} />
            <SvgText x={sx(m.v) + (k ? -3 : 3)} y={inner.t + 10 + k * 12} fontSize={9.5} fill={m.color} textAnchor={k ? 'end' : 'start'}>{m.label}</SvgText></G>))}
        </>)}
      </Plot>
    </View>
  );
}

export function Scatter({ points, height = 240, x, y, xLabel, yLabel, hline, vline }: {
  points: { x: number; y: number; color: string; label?: string; big?: boolean }[]; height?: number; x?: [number, number]; y?: [number, number];
  xLabel?: string; yLabel?: string; hline?: { v: number; color: string; label?: string }; vline?: { v: number; color: string; label?: string };
}) {
  const { colors } = useApp();
  const [w, onLayout] = useWidth();
  const X = x ?? [Math.min(...points.map((p) => p.x), vline?.v ?? Infinity) - 1, Math.max(...points.map((p) => p.x), vline?.v ?? -Infinity) + 1];
  const Y = y ?? [0, Math.max(1, ...points.map((p) => p.y)) * 1.2];
  return (
    <View onLayout={onLayout}>
      <Plot width={w} height={height} x={X} y={Y} xLabel={xLabel} yLabel={yLabel}>
        {(sx, sy, inner) => (<>
          {hline ? <Line x1={inner.l} x2={inner.l + inner.w} y1={sy(hline.v)} y2={sy(hline.v)} stroke={hline.color} strokeDasharray="5,4" /> : null}
          {hline?.label ? <SvgText x={inner.l + inner.w - 2} y={sy(hline.v) - 3} fontSize={9} fill={hline.color} textAnchor="end">{hline.label}</SvgText> : null}
          {vline ? <Line x1={sx(vline.v)} x2={sx(vline.v)} y1={inner.t} y2={inner.t + inner.h} stroke={vline.color} strokeDasharray="5,4" /> : null}
          {vline?.label ? <SvgText x={sx(vline.v) + 3} y={inner.t + 9} fontSize={9} fill={vline.color}>{vline.label}</SvgText> : null}
          {points.map((p, i) => (
            <G key={i}>
              <Circle cx={sx(p.x)} cy={sy(p.y)} r={p.big ? 8 : 6} fill={p.color} stroke="#fff" strokeWidth={1.5} />
              {p.label ? <SvgText x={sx(p.x)} y={sy(p.y) - 10} fontSize={9.5} fill={colors.muted} textAnchor="middle">{p.label}</SvgText> : null}
            </G>
          ))}
        </>)}
      </Plot>
    </View>
  );
}

/** Expert vs System event lanes: green = matched, red = unmatched. */
export function Lanes({ events, refs, pairs, matchedRef, duration }: {
  events: SwEvent[]; refs: [number, number][]; pairs: Record<string, number>; matchedRef: number[]; duration: number;
}) {
  const { colors } = useApp();
  const [w, onLayout] = useWidth();
  return (
    <View onLayout={onLayout}>
      <Plot width={w} height={150} x={[0, duration]} y={[0, 2]} yTicks={[]} pad={{ l: 56 }} xLabel="time (s)">
        {(sx, sy) => (<>
          <SvgText x={50} y={sy(1.5) + 4} fontSize={11} fill={colors.text} textAnchor="end">Expert</SvgText>
          <SvgText x={50} y={sy(0.5) + 4} fontSize={11} fill={colors.text} textAnchor="end">System</SvgText>
          {refs.map(([s, e], j) => <Rect key={`r${j}`} x={sx(s)} y={sy(1.85)} width={Math.max(2, sx(e) - sx(s))} height={sy(1.15) - sy(1.85)}
            fill={matchedRef.includes(j) ? Brand.green : Brand.red} opacity={0.85} rx={3} />)}
          {events.map((e, i) => (
            <G key={`s${i}`}>
              <Rect x={sx(e.onset_s)} y={sy(0.85)} width={Math.max(2, sx(e.offset_s) - sx(e.onset_s))} height={sy(0.15) - sy(0.85)}
                fill={String(i) in pairs ? Brand.green : Brand.red} opacity={0.85} rx={3} />
              <SvgText x={sx((e.onset_s + e.offset_s) / 2)} y={sy(0.5) + 4} fontSize={10} fill="#fff" textAnchor="middle" fontWeight="700">{String(i + 1)}</SvgText>
            </G>
          ))}
        </>)}
      </Plot>
    </View>
  );
}
