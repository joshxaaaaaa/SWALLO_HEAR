/** Events, Rhythm, Robustness lab, Signal quality, Expert comparison and Session tabs. */
import { useState } from 'react';
import { View } from 'react-native';

import { Bars, Histogram, Lanes, LineChart, Scatter, Waterfall } from '@/components/charts';
import { Badge, Banner, Button, Card, Collapsible, Metric, Progress, Row, Segmented, T, Table, Toggle, type Column } from '@/components/ui';
import { api } from '@/lib/api';
import { rhythm } from '@/lib/rhythm';
import { shareText, toCsv } from '@/lib/share';
import { noteKey, useApp } from '@/lib/state';
import { Brand, Space, TierColor } from '@/lib/theme';
import type { Analysis, SweepRow, SwEvent } from '@/lib/types';

const fmt = (f: string, v: number) => f.replace(/\{:\.(\d)f\}/, (_m, d) => v.toFixed(Number(d)));

// ----------------------------------------------------------------------------- events
export function EventsTab({ a, events, selected, setSelected }: { a: Analysis; events: SwEvent[]; selected: number; setSelected: (i: number) => void }) {
  const { meta, settings, notes } = useApp();
  if (!events.length) return <Banner kind="info">No events to list for this recording.</Banner>;
  const i = Math.min(selected, events.length - 1); const e = events[i];
  const names = (meta?.features ?? []).map((f) => f.name);
  const rows = events.map((ev, k) => ({
    '#': k + 1, onset_s: ev.onset_s.toFixed(2), offset_s: ev.offset_s.toFixed(2), duration_ms: Math.round(ev.duration_ms),
    reliability: ev.reliability, model_confidence: ev.model_confidence.toFixed(2), tier: ev.tier, your_call: notes[noteKey(a.label, ev.onset_s)] ?? '',
  }));
  const cols: Column<(typeof rows)[number]>[] = [
    { key: '#', label: '#', width: 36 }, { key: 'onset_s', label: 'Onset (s)', width: 76, align: 'right' },
    { key: 'offset_s', label: 'Offset (s)', width: 76, align: 'right' }, { key: 'duration_ms', label: 'Duration (ms)', width: 100, align: 'right' },
    { key: 'reliability', label: 'Reliability', width: 120, render: (r) => <Row gap={6}><Progress value={r.reliability} color={TierColor[r.tier]} width={60} /><T v="small">{r.reliability.toFixed(2)}</T></Row> },
    { key: 'model_confidence', label: 'Raw conf.', width: 76, align: 'right' },
    { key: 'tier', label: 'Tier', width: 120, render: (r) => <T v="small" bold color={TierColor[r.tier]}>{r.tier}</T> },
    { key: 'your_call', label: 'Your call', width: 100 },
  ];
  const csvCols = ['#', 'onset_s', 'offset_s', 'duration_ms', 'reliability', 'model_confidence', 'tier', 'your_call'];
  const ann = rows.filter((r) => r.your_call);
  const payload = {
    input: a.label, status: a.status, reason_codes: a.reason_codes, settings: a.settings, stress_test: a.stress,
    events: a.faded ? [] : events, withheld_candidates: a.faded ? events : [], quality: a.quality,
    annotations: Object.fromEntries(Object.entries(notes).filter(([k]) => k.startsWith(`${a.label}|`))),
  };
  const ex = e.explain;
  return (
    <View style={{ gap: Space.md }}>
      {a.faded ? <Banner>These candidates were withheld because the recording failed the quality gate. They are shown for inspection only.</Banner> : null}
      <Table columns={cols} rows={rows} selected={i} onRowPress={setSelected} />
      <T v="caption">Tap a row to make it the inspected event here and on the Timeline tab. Raw confidence is the detector’s own score, a poor guide to correctness (AUROC 0.53).</T>

      <T v="h3">Why event {i + 1} scored {e.reliability.toFixed(2)}</T>
      {ex ? (<>
        <Card pad={false} style={{ paddingVertical: Space.sm }}><Waterfall ex={ex} names={names} tau={settings.tau} /></Card>
        <Table
          columns={[
            { key: 'name', label: 'Measurement', width: 190 }, { key: 'value', label: 'This event', width: 90, align: 'right' },
            { key: 'typical', label: 'Typical', width: 80, align: 'right' },
            { key: 'effect', label: 'Effect', width: 70, align: 'right', render: (r) => <T v="small" bold color={Number(r.effect) >= 0 ? Brand.teal : Brand.amber}>{`${Number(r.effect) >= 0 ? '+' : ''}${Number(r.effect).toFixed(2)}`}</T> },
          ]}
          rows={(meta?.features ?? []).map((f, k) => ({ name: f.name, value: fmt(f.fmt, e.features[k]), typical: fmt(f.fmt, ex.typical[k]), effect: ex.contrib[k] }))
            .sort((p, q) => Math.abs(q.effect) - Math.abs(p.effect))} />
        <T v="caption">The reliability model starts from an average event and adds or subtracts evidence for each measurement.
          {e.up[0] ? ` Here ${e.up[0].toLowerCase()} helped most` : ' Nothing pushed it up much'}{e.down[0] ? ` and ${e.down[0].toLowerCase()} hurt most.` : '.'}</T>
      </>) : <Banner kind="info">The reliability model can’t be broken down exactly.</Banner>}

      <Collapsible title="Raw detector confidence vs reliability">
        <Scatter points={events.map((ev, k) => ({ x: ev.model_confidence, y: ev.reliability, color: TierColor[ev.tier], label: String(k + 1), big: k === i }))}
          x={[0, 1]} y={[0, 1.05]} xLabel="raw detector confidence" yLabel="reliability" hline={{ v: settings.tau, color: Brand.slate, label: `threshold ${settings.tau.toFixed(2)}` }} />
        <T v="caption">The tier comes from the separately trained reliability model, not the detector’s own confidence.</T>
      </Collapsible>

      <View style={{ gap: Space.sm }}>
        <Button label="⇪ Events (CSV)" onPress={() => shareText(`${a.label}_events.csv`, toCsv(rows, csvCols), 'text/csv')} />
        <Button label="⇪ Full result (JSON)" onPress={() => shareText(`${a.label}_swallohear.json`, JSON.stringify(payload, null, 1), 'application/json')} />
        <Button label={`⇪ My annotations (${ann.length})`} disabled={!ann.length} onPress={() => shareText(`${a.label}_annotations.csv`, toCsv(ann, csvCols), 'text/csv')} />
      </View>
    </View>
  );
}

// ----------------------------------------------------------------------------- rhythm
export function RhythmTab({ a, events }: { a: Analysis; events: SwEvent[] }) {
  const [confOnly, setConfOnly] = useState(false);
  if (events.length < 2) return <Banner kind="info">Rhythm needs at least two events. Try a longer recording, or the Synthetic source with 60 s and 8–10 bursts.</Banner>;
  const evs = confOnly ? events.filter((e) => e.tier === 'Confident') : events;
  const rh = rhythm(evs, a.duration_s);
  const sorted = [...events].sort((p, q) => p.onset_s - q.onset_s);
  const step = (list: SwEvent[]) => ({ x: [0, ...list.map((e) => e.onset_s), a.duration_s], y: [0, ...list.map((_, k) => k + 1), list.length] });
  const all = step(sorted); const conf = step(sorted.filter((e) => e.tier === 'Confident'));
  const base = evs.length >= 2 ? evs : events; const iei = rhythm(base, a.duration_s).iei;
  return (
    <View style={{ gap: Space.md }}>
      {a.faded ? <Banner>The result was withheld; rhythm uses the withheld candidates.</Banner> : null}
      <Toggle label="Confident events only" value={confOnly} onChange={setConfOnly} />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm }}>
        <Metric label="Events" value={rh.n} />
        <Metric label="Rate" value={`${rh.rate.toFixed(1)}/min`} />
        <Metric label="Mean interval" value={rh.mean_iei !== null ? `${rh.mean_iei.toFixed(1)} s` : '–'} help="Average time from one event's onset to the next." />
        <Metric label="Regularity" value={rh.regularity ? rh.regularity[0].toUpperCase() + rh.regularity.slice(1) : '–'} delta={rh.cv !== null ? `CV ${rh.cv.toFixed(2)}` : undefined}
          help="Spread of the intervals (coefficient of variation): under 0.25 steady, 0.25–0.5 moderate, over 0.5 irregular." />
        <Metric label="Longest quiet gap" value={`${rh.longest_gap.toFixed(1)} s`} help="Longest stretch with no event, including the start and end." />
      </View>
      <T v="h3">Events over time</T>
      <Card pad={false} style={{ paddingVertical: Space.sm }}>
        <LineChart series={[{ name: 'All events', ...all, color: Brand.slate, step: true, width: 2.5 }, { name: 'Confident only', ...conf, color: Brand.teal, step: true, width: 2.5 }]}
          x={[0, a.duration_s]} y={[0, all.y[all.y.length - 1] * 1.15 + 0.5]} xLabel="time (s)" yLabel="events so far" />
      </Card>
      <T v="caption">A steady slope means steady swallowing; flat stretches are pauses.</T>
      <T v="h3">Time between consecutive events</T>
      <Card pad={false} style={{ paddingVertical: Space.sm }}>
        <Bars categories={iei.map((_, k) => `${k + 1}→${k + 2}`)} stacks={[{ name: 'seconds apart', values: iei, color: Brand.teal }]} yLabel="seconds"
          hline={iei.length ? { v: iei.reduce((s, v) => s + v, 0) / iei.length, color: Brand.slate, label: 'mean' } : undefined} />
      </Card>
      <T v="caption">Rhythm is descriptive only. Short clips give few intervals, and missed or false detections distort these numbers.</T>
    </View>
  );
}

// ----------------------------------------------------------------------------- robustness
export function RobustnessTab({ a, sweeps, setSweep }: { a: Analysis; sweeps: Record<string, SweepRow[]>; setSweep: (k: string, rows: SweepRow[]) => void }) {
  const { meta, settings } = useApp();
  const kinds = meta?.noise_kinds ?? ['White'];
  const [kind, setKind] = useState(kinds[0]);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<string | null>(null);
  const key = `${a.rec_id}|${kind}|${JSON.stringify(settings)}`; const rows = sweeps[key];
  const run = async () => {
    setBusy(true); setErr(null);
    try { setSweep(key, (await api.sweep(a.rec_id, settings, kind)).rows); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <View style={{ gap: Space.md }}>
      <T v="h3">How does this recording hold up as noise gets louder?</T>
      <T v="caption">Re-runs the full analysis at 7 noise levels on the original recording (stress-test settings are ignored here).</T>
      <Segmented options={kinds} value={kind} onChange={setKind} />
      <Button kind="primary" label={busy ? 'Analysing 7 levels…' : '▶ Run sweep'} onPress={run} loading={busy} />
      {err ? <Banner kind="error">{err}</Banner> : null}
      {rows ? (<>
        <Card pad={false} style={{ paddingVertical: Space.sm }}>
          <Bars categories={rows.map((r) => r.level.replace(' dB', ''))} yLabel="events"
            stacks={[{ name: 'Confident', values: rows.map((r) => r.confident), color: Brand.teal },
              { name: 'Low-confidence', values: rows.map((r) => r.low), color: Brand.amber },
              { name: 'Withheld', values: rows.map((r) => r.withheld), color: 'rgba(122,138,148,0.45)' }]}
            line={{ name: 'Estimated SNR (dB)', values: rows.map((r) => r.est_snr), color: Brand.slate,
              range: [Math.min(0, ...rows.map((r) => r.est_snr)), Math.max(settings.snr_min, ...rows.map((r) => r.est_snr)) * 1.1],
              ref: { v: settings.snr_min, color: Brand.red, label: 'Quality gate' } }} />
        </Card>
        <Table columns={[
          { key: 'level', label: 'Noise', width: 64 }, { key: 'status', label: 'Status', width: 100 },
          { key: 'confident', label: 'Conf.', width: 52, align: 'right' }, { key: 'low', label: 'Low', width: 48, align: 'right' },
          { key: 'withheld', label: 'Withheld', width: 70, align: 'right' }, { key: 'est_snr', label: 'SNR dB', width: 64, align: 'right' },
          { key: 'f1', label: 'F1 vs expert', width: 120, render: (r) => (r.f1 === null ? <T v="small">–</T> : <Row gap={6}><Progress value={r.f1} width={56} /><T v="small">{r.f1.toFixed(2)}</T></Row>) },
        ]} rows={rows} />
        <T v="caption">Once the estimated SNR drops below the gate the system withholds its result instead of reporting events it cannot trust.</T>
      </>) : <Banner kind="info">Press Run sweep to analyse the recording at 7 noise levels.</Banner>}
    </View>
  );
}

// ----------------------------------------------------------------------------- quality
export function QualityTab({ a }: { a: Analysis }) {
  const { colors, settings } = useApp();
  return (
    <View style={{ gap: Space.md }}>
      <T v="h3">Quality gate</T>
      {a.checks.map((c) => (
        <Card key={c.name} style={{ flexDirection: 'row', alignItems: 'center', gap: Space.md }}>
          <T v="h3" color={c.ok ? Brand.green : Brand.red}>{c.ok ? '✓' : '✕'}</T>
          <View style={{ flex: 1 }}><T bold>{c.name}</T><T v="caption">limit {c.limit}</T></View>
          <T bold color={c.ok ? Brand.teal : Brand.red}>{c.value}</T>
        </Card>
      ))}
      {a.stress ? <Banner kind="info">{`Stress test active: ${a.stress}. This approximates, but does not exactly reproduce, the noise protocol in the reported experiments.`}</Banner> : null}
      <T v="h3">How SNR is estimated</T>
      <Card pad={false} style={{ paddingVertical: Space.sm }}>
        <Histogram counts={a.energy.counts} edges={a.energy.edges} xLabel="frame energy (dB)"
          marks={[{ v: a.energy.floor, color: Brand.amber, label: 'noise floor' }, { v: a.energy.peak, color: Brand.teal, label: 'peaks' }]} />
      </Card>
      <T v="caption">SNR = peaks (95th percentile) − floor (10th percentile) = {(a.energy.peak - a.energy.floor).toFixed(1)} dB. The {settings.snr_min.toFixed(1)} dB gate is roughly the worst clean recording seen in validation.</T>
      <T v="h3">Average spectrum</T>
      <Card pad={false} style={{ paddingVertical: Space.sm }}>
        <LineChart series={[{ name: 'power', x: a.psd.f, y: a.psd.db, color: colors.ink, width: 1.4 }]} x={[0, 2000]} xLabel="frequency (Hz)" yLabel="dB" legend={false}
          vlines={[{ v: 20, color: Brand.teal, label: 'analysis band' }, { v: 1800, color: Brand.teal }]} />
      </Card>
      <T v="caption">Sharp spikes at 60, 120, 180 Hz point to mains hum; a raised flat line points to broadband hiss.</T>
    </View>
  );
}

// ----------------------------------------------------------------------------- expert
export function ExpertTab({ a, events }: { a: Analysis; events: SwEvent[] }) {
  const x = a.expert;
  if (!x) return <Banner kind="info">This recording has no expert reference labels, so agreement cannot be scored. Demo clips and synthetic signals carry labels.</Banner>;
  return (
    <View style={{ gap: Space.md }}>
      {a.faded ? <Banner>The result was withheld; the comparison uses the withheld candidates.</Banner> : null}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm }}>
        <Metric style={{ flexBasis: '30%' }} label="Matched" value={x.tp} help="Detected and overlapping a label by at least half." />
        <Metric style={{ flexBasis: '30%' }} label="False det." value={x.fp} help="Detected, but no label there." />
        <Metric style={{ flexBasis: '30%' }} label="Missed" value={x.fn} help="Labelled, but not detected." />
        <Metric style={{ flexBasis: '30%' }} label="Precision" value={x.precision.toFixed(2)} />
        <Metric style={{ flexBasis: '30%' }} label="Recall" value={x.recall.toFixed(2)} />
        <Metric style={{ flexBasis: '30%' }} label="F1" value={x.f1.toFixed(2)} />
      </View>
      <Card pad={false} style={{ paddingVertical: Space.sm }}>
        <Lanes events={events} refs={a.ref} pairs={x.pairs} matchedRef={x.matched_ref} duration={a.duration_s} />
      </Card>
      <T v="caption">Green = matched, red = unmatched (a false detection in the System lane, a miss in the Expert lane).</T>
      {x.onset_err_ms !== null ? <T v="caption">Median onset error {x.onset_err_ms >= 0 ? '+' : ''}{Math.round(x.onset_err_ms)} ms · median offset error {x.offset_err_ms! >= 0 ? '+' : ''}{Math.round(x.offset_err_ms!)} ms. Negative means the system fired early.</T> : null}
      <T v="caption">One clip proves nothing. Across the 27 held-out test participants the system scores F1 around 0.49, and some “false detections” are likely real swallows the dataset never labelled.</T>
    </View>
  );
}

// ----------------------------------------------------------------------------- session
export function SessionTab() {
  const { history, notes, clearSession } = useApp();
  if (!history.length) return <Banner kind="info">Analyses you run in this session will be listed here.</Banner>;
  const cols = ['time', 'recording', 'stress', 'status', 'confident', 'low', 'snr_db', 'settings'];
  const noteRows = Object.entries(notes).map(([k, v]) => ({ recording: k.split('|')[0], onset_s: k.split('|')[1], your_call: v }));
  return (
    <View style={{ gap: Space.md }}>
      <T v="h3">{history.length} analys{history.length === 1 ? 'is' : 'es'} this session</T>
      <Table columns={[
        { key: 'time', label: 'Time', width: 70 }, { key: 'recording', label: 'Recording', width: 140 }, { key: 'stress', label: 'Stress test', width: 150 },
        { key: 'status', label: 'Status', width: 100, render: (r) => <Badge label={r.status} color={r.status === 'Inconclusive' ? Brand.amber : r.status === 'Analyzable' ? Brand.teal : Brand.slate} /> },
        { key: 'confident', label: 'Conf.', width: 50, align: 'right' }, { key: 'low', label: 'Low', width: 44, align: 'right' },
        { key: 'snr_db', label: 'SNR', width: 54, align: 'right' }, { key: 'settings', label: 'Settings', width: 160 },
      ]} rows={[...history].reverse()} />
      <Row wrap>
        <Button flex label="Session log (CSV)" onPress={() => shareText('swallohear_session.csv', toCsv(history, cols), 'text/csv')} />
        <Button flex label={`All annotations (${noteRows.length})`} disabled={!noteRows.length}
          onPress={() => shareText('swallohear_annotations.csv', toCsv(noteRows, ['recording', 'onset_s', 'your_call']), 'text/csv')} />
        <Button flex label="Clear session" onPress={clearSession} />
      </Row>
      <T v="caption">Your calls and this log live only while the app is open. Export them to keep them.</T>
    </View>
  );
}
