/** Compare tab: two recordings, or one clip clean vs noisy, on aligned timelines. */
import * as DocumentPicker from 'expo-document-picker';
import { useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';

import { LineChart, Timeline } from '@/components/charts';
import { Screen } from '@/components/shell';
import { Banner, Button, Card, Loading, Row, Segmented, Select, SliderRow, T, Table, Toggle, Verdict } from '@/components/ui';
import { api } from '@/lib/api';
import { rhythm } from '@/lib/rhythm';
import { useApp } from '@/lib/state';
import { Brand, Space } from '@/lib/theme';
import type { Analysis, LocalFile } from '@/lib/types';

import { demoLabel } from './analyze/SourcePanel';

const UPLOAD = 'Upload a file…';
type Side = { src: string | null; file: LocalFile | null; noiseOn: boolean; kind: string; snr: number };
type Result = { a: Analysis | null; busy: boolean; error: string | null };

/** Loads and analyses one side; busy/error are derived from the request key rather than set inside the effect. */
function useSideAnalysis(side: Side): Result {
  const { settings, meta } = useApp();
  const [done, setDone] = useState<{ key: string; a?: Analysis; error?: string } | null>(null);
  const ready = !!meta && !!side.src && (side.src !== UPLOAD || !!side.file);
  const key = ready ? JSON.stringify([side.src, side.file?.uri, side.noiseOn, side.kind, side.snr, settings]) : null;
  useEffect(() => {
    if (!key) return;
    let live = true;
    (async () => {
      const l = side.src === UPLOAD ? await api.loadFile(side.file!) : await api.loadDemo(side.src!);
      return api.analyze(l.rec_id, settings, { noise_kind: side.noiseOn ? side.kind : null, snr: side.noiseOn ? side.snr : null });
    })().then((a) => live && setDone({ key, a }))
      .catch((e: Error) => live && setDone({ key, error: e.message }));
    return () => { live = false; };
    // side and settings are captured through key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  if (!key) return { a: null, busy: false, error: null };
  const current = done?.key === key;
  return { a: current ? done?.a ?? null : null, busy: !current, error: current ? done?.error ?? null : null };
}

export default function CompareScreen() {
  const { meta, settings } = useApp();
  const names = useMemo(() => meta?.demos.map((d) => d.name) ?? [], [meta]);
  const kinds = meta?.noise_kinds ?? ['White'];
  const [pickA, setA] = useState<Side>({ src: null, file: null, noiseOn: false, kind: 'White', snr: 5 });
  const [pickB, setB] = useState<Side>({ src: null, file: null, noiseOn: true, kind: 'White', snr: 5 });
  const [spec, setSpec] = useState(false);
  // Until a clip is chosen, both sides default to the first demo clip (B with noise).
  const A = useMemo(() => (pickA.src ? pickA : { ...pickA, src: names[0] ?? null }), [pickA, names]);
  const B = useMemo(() => (pickB.src ? pickB : { ...pickB, src: names[0] ?? null }), [pickB, names]);
  const ra = useSideAnalysis(A); const rb = useSideAnalysis(B);

  const preset = (kind: 'noise' | 'clips') => {
    if (!names.length) return;
    setA({ src: names[0], file: null, noiseOn: false, kind: kinds[0], snr: 5 });
    setB(kind === 'noise' ? { src: names[0], file: null, noiseOn: true, kind: kinds[0], snr: 5 }
      : { src: names[Math.min(2, names.length - 1)], file: null, noiseOn: false, kind: kinds[0], snr: 5 });
  };

  return (
    <Screen>
      <T v="h2">Compare two recordings</T>
      <T v="caption">Analyse two recordings with the same detector settings and see them on aligned timelines.</T>
      <Row wrap>
        <Button flex small label="Same clip: clean vs noisy" onPress={() => preset('noise')} />
        <Button flex small label="Two different clips" onPress={() => preset('clips')} />
      </Row>
      <SideCard title="Recording A" colour={Brand.teal} side={A} setSide={setA} names={names} kinds={kinds} />
      <SideCard title="Recording B" colour={Brand.amber} side={B} setSide={setB} names={names} kinds={kinds} />
      {ra.error || rb.error ? <Banner kind="error">{ra.error ?? rb.error ?? ''}</Banner> : null}
      {!ra.a || !rb.a ? (ra.busy || rb.busy ? <Loading /> : <Banner kind="info">Choose a recording on both sides to compare.</Banner>) : (
        <Results a={ra.a} b={rb.a} spec={spec} setSpec={setSpec} hi={settings.hi} lo={settings.lo} />
      )}
    </Screen>
  );
}

function SideCard({ title, colour, side, setSide, names, kinds }: {
  title: string; colour: string; side: Side; setSide: (s: Side) => void; names: string[]; kinds: string[];
}) {
  const pick = async () => {
    const r = await DocumentPicker.getDocumentAsync({ type: ['audio/*', 'application/octet-stream'], copyToCacheDirectory: true });
    if (!r.canceled && r.assets?.length) { const x = r.assets[0]; setSide({ ...side, src: UPLOAD, file: { uri: x.uri, name: x.name, mimeType: x.mimeType, file: x.file } }); }
  };
  return (
    <Card style={{ gap: Space.sm }}>
      <T bold><T bold color={colour}>● </T>{title}</T>
      <Select value={side.src} options={[...names, UPLOAD]} onChange={(v) => (v === UPLOAD ? void pick() : setSide({ ...side, src: v, file: null }))}
        format={(v) => (v === UPLOAD ? (side.file ? `File: ${side.file.name}` : UPLOAD) : demoLabel(v))} />
      <Toggle label="Add noise" value={side.noiseOn} onChange={(v) => setSide({ ...side, noiseOn: v })} />
      {side.noiseOn ? (<>
        <Segmented options={kinds} value={side.kind} onChange={(k) => setSide({ ...side, kind: k })} />
        <SliderRow label="SNR" value={side.snr} min={-5} max={30} step={1} format={(v) => `${v} dB`} onCommit={(v) => setSide({ ...side, snr: v })} />
      </>) : null}
    </Card>
  );
}

function summary(a: Analysis) {
  const ev = a.faded ? [] : a.events; const rel = ev.map((e) => e.reliability); const rh = rhythm(a.events, a.duration_s);
  return {
    Status: a.status, 'Confident events': a.counts.confident, 'Low-confidence events': a.counts.low, 'Withheld candidates': a.counts.withheld,
    'Estimated SNR (dB)': +a.quality.snr_db.toFixed(1), 'Mean reliability': rel.length ? +(rel.reduce((s, v) => s + v, 0) / rel.length).toFixed(2) : null,
    'Events per minute': +a.rate_per_min.toFixed(1), 'Mean interval (s)': rh.mean_iei !== null ? +rh.mean_iei.toFixed(1) : null,
    'F1 vs expert': a.expert ? +a.expert.f1.toFixed(2) : null,
  } as Record<string, string | number | null>;
}

function Results({ a, b, spec, setSpec, hi, lo }: { a: Analysis; b: Analysis; spec: boolean; setSpec: (v: boolean) => void; hi: number; lo: number }) {
  const sa = summary(a); const sb = summary(b);
  const rows = Object.keys(sa).map((k) => {
    const va = sa[k], vb = sb[k];
    const d = typeof va === 'number' && typeof vb === 'number' ? +(vb - va).toFixed(2) : null;
    return { metric: k, a: va ?? '–', b: vb ?? '–', change: d === null ? '' : `${d > 0 ? '+' : ''}${d}` };
  });
  const xMax = Math.max(a.duration_s, b.duration_s);
  return (
    <View style={{ gap: Space.md }}>
      <T v="h3">Side by side</T>
      <Table columns={[{ key: 'metric', label: '', width: 150 }, { key: 'a', label: `A · ${a.label}${a.stress ? ' (noisy)' : ''}`, width: 130 },
        { key: 'b', label: `B · ${b.label}${b.stress ? ' (noisy)' : ''}`, width: 130 }, { key: 'change', label: 'B − A', width: 70, align: 'right' }]} rows={rows} />
      <T v="h3">Detector score, overlaid</T>
      <Card pad={false} style={{ paddingVertical: Space.sm }}>
        <LineChart series={[{ name: `A · ${a.label}`, x: a.frames.t, y: a.frames.p, color: Brand.teal, width: 1.5 },
          { name: `B · ${b.label}${b.stress ? ` + ${b.stress}` : ''}`, x: b.frames.t, y: b.frames.p, color: Brand.amber, width: 1.5 }]}
          x={[0, xMax]} y={[0, 1]} xLabel="time (s)" yLabel="score" hlines={[{ v: hi, color: Brand.slate, label: `start ${hi.toFixed(2)}` }]} />
      </Card>
      <Toggle label="Show spectrograms" value={spec} onChange={setSpec} />
      {[['A', a], ['B', b]].map(([k, r]) => {
        const x = r as Analysis;
        return (
          <View key={k as string} style={{ gap: Space.sm }}>
            <Verdict verdict={x.verdict} codes={x.reason_codes} subtitle={`Recording ${k} · ${x.label}${x.stress ? ` + ${x.stress}` : ''}`} />
            <Card pad={false} style={{ paddingVertical: Space.sm }}>
              <Timeline a={x} events={x.events} faded={x.faded} showSpec={spec} showRef={x.ref.length > 0} hi={hi} lo={Math.min(lo, hi)} xMax={xMax} compact />
            </Card>
          </View>
        );
      })}
      <T v="caption">Both timelines share the same time axis. Dotted green outlines are expert labels where available.</T>
    </View>
  );
}
