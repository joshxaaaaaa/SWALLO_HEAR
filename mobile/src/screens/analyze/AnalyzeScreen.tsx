/** Analyze tab: the web app's main page. */
import { useEffect, useState } from 'react';
import { ScrollView, View } from 'react-native';

import { Screen } from '@/components/shell';
import { Badge, Banner, Button, Card, Loading, Metric, Row, Segmented, T, Verdict } from '@/components/ui';
import { absolute, api } from '@/lib/api';
import { openUrl } from '@/lib/share';
import { useApp } from '@/lib/state';
import { Brand, Space } from '@/lib/theme';
import type { Analysis, Loaded, LocalFile, SweepRow } from '@/lib/types';

import { SourcePanel, StressPanel, type Source, type StressUi, type Syn } from './SourcePanel';
import { EventsTab, ExpertTab, QualityTab, RhythmTab, RobustnessTab, SessionTab } from './tabs';
import { TimelineTab } from './TimelineTab';

const TABS = ['Timeline', 'Events', 'Rhythm', 'Robustness', 'Quality', 'Expert', 'Session'] as const;
type Tab = (typeof TABS)[number];

type Done<T> = { key: string; value?: T; error?: string };

export default function AnalyzeScreen() {
  const { meta, settings, changed, notes, logHistory } = useApp();
  const [source, setSourceState] = useState<Source>('Demo');
  const [demoPick, setDemo] = useState<string | null>(null);
  const [syn, setSyn] = useState<Syn>({ n: 4, dur: 20, seed: 0 });
  const [fileKey, setFileKey] = useState<string | null>(null);
  const [stress, setStress] = useState<StressUi>({ noiseOn: false, kind: 'White', snr: 10, clip: false });
  const [loadDone, setLoadDone] = useState<Done<Loaded> | null>(null);
  const [anaDone, setAnaDone] = useState<Done<Analysis> | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);
  const [sel, setSel] = useState({ key: '', i: 0 });
  const [tab, setTab] = useState<Tab>('Timeline');
  const [sweeps, setSweeps] = useState<Record<string, SweepRow[]>>({});
  const demo = demoPick ?? meta?.demos[0]?.name ?? null;

  // Every request is identified by a key; busy and error states are derived by comparing keys, not set in effects.
  const fromFile = source === 'Upload' || source === 'Record';
  const loadKey = fromFile ? fileKey
    : !meta ? null : source === 'Demo' ? (demo ? `demo|${demo}` : null) : `syn|${syn.n}|${syn.dur}|${syn.seed}`;
  const loaded = loadDone && loadDone.key === loadKey ? loadDone.value ?? null : null;
  const stressReq = { noise_kind: stress.noiseOn ? stress.kind : null, snr: stress.noiseOn ? stress.snr : null, clip: stress.clip };
  const anaKey = loaded ? `${loaded.rec_id}|${JSON.stringify(settings)}|${JSON.stringify(stressReq)}` : null;
  const a = anaDone?.value && loaded && anaDone.value.rec_id === loaded.rec_id ? anaDone.value : null;   // keep showing the last result while updating
  const busy = (loadKey !== null && loadDone?.key !== loadKey) || (anaKey !== null && anaDone?.key !== anaKey);
  const error = (loadDone?.key === loadKey ? loadDone?.error : undefined) ?? (anaDone?.key === anaKey ? anaDone?.error : undefined) ?? reportError;

  const setSource = (s: Source) => {
    setSourceState(s); setReportError(null);
    if (s === 'Upload' || s === 'Record') setFileKey(null);   // wait for a file, like the web app
  };

  // Load the demo clip or synthetic signal whenever its choice changes.
  useEffect(() => {
    if (!loadKey || fromFile) return;
    let live = true;
    const [kind, ...p] = loadKey.split('|');
    const job = kind === 'demo' ? api.loadDemo(p[0]) : api.loadSynthetic(Number(p[0]), Number(p[1]), Number(p[2]));
    job.then((v) => live && setLoadDone({ key: loadKey, value: v })).catch((e: Error) => live && setLoadDone({ key: loadKey, error: e.message }));
    return () => { live = false; };
  }, [loadKey, fromFile]);

  const onFile = (f: LocalFile) => {
    const key = `file|${f.name}|${Date.now()}`; setFileKey(key);
    api.loadFile(f, source === 'Record' ? `microphone_${new Date().toTimeString().slice(0, 8).replace(/:/g, '')}` : undefined)
      .then((v) => setLoadDone({ key, value: v })).catch((e: Error) => setLoadDone({ key, error: e.message }));
  };

  // Re-analyse when the recording, detector settings or stress test change (scoring is cached on the server).
  useEffect(() => {
    if (!anaKey || !loaded) return;
    let live = true;
    api.analyze(loaded.rec_id, settings, stressReq)
      .then((v) => live && setAnaDone({ key: anaKey, value: v })).catch((e: Error) => live && setAnaDone({ key: anaKey, error: e.message }));
    return () => { live = false; };
    // stressReq and settings are captured through anaKey
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anaKey]);

  // The selected event resets when the recording or stress test changes.
  const recKey = a ? `${a.rec_id}|${a.stress}` : '';
  const selected = sel.key === recKey ? sel.i : 0;
  const setSelected = (i: number) => setSel({ key: recKey, i });

  useEffect(() => {
    if (!a) return;
    logHistory({
      time: new Date().toTimeString().slice(0, 8), recording: a.label, stress: a.stress ?? 'none', status: a.status,
      confident: a.counts.confident, low: a.counts.low, snr_db: Math.round(a.quality.snr_db * 10) / 10,
      settings: a.changed.length ? `custom: ${a.changed.join(', ')}` : 'validated',
    }, `${a.rec_id}|${a.stress}|${JSON.stringify(a.settings)}`);
  }, [a, logHistory]);

  const events = a?.events ?? [];
  const selIdx = Math.min(selected, Math.max(0, events.length - 1));

  const openReport = async () => {
    if (!a) return;
    const mine = Object.fromEntries(Object.entries(notes).filter(([k]) => k.startsWith(`${a.label}|`)).map(([k, v]) => [k.split('|')[1], v]));
    setReportError(null);
    try { const r = await api.saveNotes(a.id, mine); await openUrl(absolute(r.report_url)); } catch (e) { setReportError((e as Error).message); }
  };

  return (
    <Screen>
      <SourcePanel source={source} setSource={setSource} demo={demo} setDemo={setDemo} syn={syn} setSyn={setSyn}
        onFile={onFile} loaded={loaded} busy={busy && !a} />
      <StressPanel stress={stress} setStress={setStress} kinds={meta?.noise_kinds ?? ['White']} />
      {error ? <Banner kind="error">{error}</Banner> : null}

      {!a ? (busy ? <Loading /> : <EmptyState />) : (
        <View style={{ gap: Space.md, opacity: busy ? 0.6 : 1 }}>
          <View style={{ gap: Space.sm }}>
            <Row style={{ justifyContent: 'space-between' }}>
              <T v="h2" style={{ flexShrink: 1 }} numberOfLines={1}>{a.label}</T>
              <Button small label="📄 Report" onPress={openReport} />
            </Row>
            <Row wrap gap={6}>
              <Badge label={`⏱ ${a.duration_s.toFixed(1)} s`} />
              <Badge label={`${(a.orig_fs / 1000).toFixed(1)} kHz source`} />
              {a.stress ? <Badge label={`⚡ ${a.stress}`} color={Brand.amber} /> : null}
              {changed.length ? <Badge label="custom settings" color="#7D5BA6" /> : null}
              {busy ? <Badge label="updating…" color={Brand.teal} /> : null}
            </Row>
          </View>
          <Verdict verdict={a.verdict} codes={a.reason_codes} help={a.reason_help} subtitle={a.note ? `Note: ${a.note}` : undefined} />
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm }}>
            <Metric label="Confident events" value={a.counts.confident} help="Reliability score at or above the threshold." />
            <Metric label="Low-confidence" value={a.counts.low} help="Detected, but the reliability model does not trust them." />
            <Metric label="Event rate" value={`${a.rate_per_min.toFixed(1)}/min`} help="Detected events per minute (withheld candidates included)." />
            <Metric label="Estimated SNR" value={`${a.quality.snr_db.toFixed(1)} dB`}
              delta={`${a.quality.snr_db - settings.snr_min >= 0 ? '↑ +' : '↓ '}${(a.quality.snr_db - settings.snr_min).toFixed(1)} dB vs gate`}
              deltaColor={a.quality.snr_db >= settings.snr_min ? Brand.green : Brand.red} help={`The quality gate needs at least ${settings.snr_min.toFixed(1)} dB.`} />
            <Metric label="Processing time" value={`${a.latency_s.toFixed(2)} s`} help={`Server time to analyse ${a.duration_s.toFixed(1)} s of audio.`} style={{ flexBasis: '100%' }} />
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: Space.sm, paddingVertical: 2 }}>
            <Segmented options={TABS} value={tab} onChange={setTab} format={(t) => (t === 'Events' ? `Events (${events.length})` : t)} />
          </ScrollView>
          {tab === 'Timeline' ? <TimelineTab a={a} events={events} selected={selIdx} setSelected={setSelected} /> : null}
          {tab === 'Events' ? <EventsTab a={a} events={events} selected={selIdx} setSelected={setSelected} /> : null}
          {tab === 'Rhythm' ? <RhythmTab a={a} events={events} /> : null}
          {tab === 'Robustness' ? <RobustnessTab a={a} sweeps={sweeps} setSweep={(k, rows) => setSweeps((s) => ({ ...s, [k]: rows }))} /> : null}
          {tab === 'Quality' ? <QualityTab a={a} /> : null}
          {tab === 'Expert' ? <ExpertTab a={a} events={events} /> : null}
          {tab === 'Session' ? <SessionTab /> : null}
        </View>
      )}
    </Screen>
  );
}

function EmptyState() {
  return (
    <View style={{ gap: Space.md }}>
      <T v="h2">Analyse a recording</T>
      <T v="small">Pick a source above to get started. Demo clips come from held-out test participants and carry expert labels.</T>
      {[
        ['📈 See every event', 'Waveform, spectrogram and detector score on one timeline. Tap an event to inspect it.'],
        ['🎚 Tune and stress-test', 'Move the detector thresholds (⚙), add white, pink or mains-hum noise, and watch the quality gate react.'],
        ['✅ Check and export', 'Compare with expert labels, record your own call on each event, and share everything.'],
      ].map(([h, b]) => (<Card key={h} style={{ gap: 4 }}><T bold>{h}</T><T v="caption">{b}</T></Card>))}
    </View>
  );
}
