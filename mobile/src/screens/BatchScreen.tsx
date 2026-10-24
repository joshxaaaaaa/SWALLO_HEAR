/** Batch tab: analyse many recordings with the current detector settings. */
import * as DocumentPicker from 'expo-document-picker';
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Scatter } from '@/components/charts';
import { Screen } from '@/components/shell';
import { Banner, Button, Card, Metric, Progress, Row, Segmented, SliderRow, T, Table, Toggle } from '@/components/ui';
import { api } from '@/lib/api';
import { shareText, toCsv } from '@/lib/share';
import { useApp } from '@/lib/state';
import { Brand, Space } from '@/lib/theme';
import type { BatchRow, LocalFile } from '@/lib/types';

const STATUS_COLOUR: Record<string, string> = { Analyzable: Brand.teal, 'No event': Brand.slate, Inconclusive: Brand.amber };

export default function BatchScreen() {
  const { meta, settings, colors } = useApp();
  const names = meta?.demos.map((d) => d.name) ?? [];
  const [picked, setPicked] = useState<string[] | null>(null);
  const chosen = picked ?? names;
  const [files, setFiles] = useState<LocalFile[]>([]);
  const [noise, setNoise] = useState({ on: false, kind: 'White', snr: 10 });
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const [res, setRes] = useState<{ rows: BatchRow[]; settings: string } | null>(null);

  const addFiles = async () => {
    const r = await DocumentPicker.getDocumentAsync({ type: ['audio/*', 'application/octet-stream'], multiple: true, copyToCacheDirectory: true });
    if (!r.canceled && r.assets) setFiles([...files, ...r.assets.map((x) => ({ uri: x.uri, name: x.name, mimeType: x.mimeType, file: x.file }))]);
  };
  const run = async () => {
    setBusy(true); setError(null);
    try {
      const out = await api.batch(chosen, files, settings, noise.on ? { kind: noise.kind, snr: noise.snr } : null);
      setRes({ rows: out.rows, settings: JSON.stringify(settings) });
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const rows = res?.rows ?? []; const ok = rows.filter((r) => r.status in STATUS_COLOUR);
  const f1s = ok.map((r) => r.f1).filter((v): v is number => typeof v === 'number');
  const cols = ['recording', 'status', 'reasons', 'duration_s', 'snr_db', 'confident', 'low', 'mean_reliability', 'per_min', 'labels', 'f1'];

  return (
    <Screen>
      <T v="h2">Batch analysis</T>
      <T v="caption">Analyse several recordings in one go with the detector settings (⚙), then compare them side by side.</T>
      <Card style={{ gap: Space.md }}>
        <Row style={{ justifyContent: 'space-between' }}>
          <T v="small" bold>Demo clips ({chosen.length}/{names.length})</T>
          <Row><Button small kind="ghost" label="All" onPress={() => setPicked(names)} /><Button small kind="ghost" label="None" onPress={() => setPicked([])} /></Row>
        </Row>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {names.map((n) => {
            const on = chosen.includes(n);
            return (
              <Pressable key={n} onPress={() => setPicked(on ? chosen.filter((x) => x !== n) : [...chosen, n])}
                style={{ borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5, borderWidth: 1,
                  borderColor: on ? Brand.teal : colors.border, backgroundColor: on ? Brand.teal : 'transparent' }}>
                <Text style={{ color: on ? '#fff' : colors.text, fontSize: 13 }}>{n}</Text>
              </Pressable>
            );
          })}
        </View>
        <Button label={files.length ? `Add more files (${files.length} added)` : 'Add your own files'} onPress={addFiles} />
        {files.length ? <Row wrap>{files.map((f, i) => (
          <Button key={i} small label={`✕ ${f.name}`} onPress={() => setFiles(files.filter((_, k) => k !== i))} />))}</Row> : null}
        <Toggle label="Add noise to every file" value={noise.on} onChange={(v) => setNoise({ ...noise, on: v })} />
        {noise.on ? (<>
          <Segmented options={meta?.noise_kinds ?? ['White']} value={noise.kind} onChange={(k) => setNoise({ ...noise, kind: k })} />
          <SliderRow label="SNR" value={noise.snr} min={-5} max={30} step={1} format={(v) => `${v} dB`} onCommit={(v) => setNoise({ ...noise, snr: v })} />
        </>) : null}
        <Button kind="primary" label={`▶ Analyse ${chosen.length + files.length} recordings`} onPress={run} loading={busy} disabled={!(chosen.length + files.length)} />
      </Card>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {!res ? <Banner kind="info">Choose recordings above and press Analyse.</Banner> : (
        <View style={{ gap: Space.md }}>
          {res.settings !== JSON.stringify(settings) ? <Banner>Detector settings changed since this batch ran. Press Analyse again to refresh.</Banner> : null}
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm }}>
            <Metric label="Recordings" value={rows.length} />
            <Metric label="Withheld" value={ok.filter((r) => r.status === 'Inconclusive').length} />
            <Metric label="Confident events" value={ok.reduce((s, r) => s + (r.confident ?? 0), 0)} />
            <Metric label="Mean F1 vs expert" value={f1s.length ? (f1s.reduce((s, v) => s + v, 0) / f1s.length).toFixed(2) : '–'} help="Only recordings with expert labels." />
          </View>
          <Table columns={[
            { key: 'recording', label: 'Recording', width: 150 },
            { key: 'status', label: 'Status', width: 100, render: (r) => <T v="small" bold color={STATUS_COLOUR[r.status] ?? Brand.red}>{r.status}</T> },
            { key: 'reasons', label: 'Reasons', width: 80 }, { key: 'duration_s', label: 'Length', width: 60, align: 'right' },
            { key: 'snr_db', label: 'SNR dB', width: 64, align: 'right' }, { key: 'confident', label: 'Conf.', width: 50, align: 'right' },
            { key: 'low', label: 'Low', width: 44, align: 'right' },
            { key: 'mean_reliability', label: 'Mean reliability', width: 130, render: (r) => (typeof r.mean_reliability === 'number'
              ? <Row gap={6}><Progress value={r.mean_reliability} width={60} /><T v="small">{r.mean_reliability.toFixed(2)}</T></Row> : <T v="small">–</T>) },
            { key: 'per_min', label: 'Events/min', width: 80, align: 'right' }, { key: 'labels', label: 'Labels', width: 56, align: 'right' },
            { key: 'f1', label: 'F1 vs expert', width: 120, render: (r) => (typeof r.f1 === 'number'
              ? <Row gap={6}><Progress value={r.f1} width={56} /><T v="small">{r.f1.toFixed(2)}</T></Row> : <T v="small">–</T>) },
          ]} rows={rows} />
          {ok.length ? (
            <Card pad={false} style={{ paddingVertical: Space.sm }}>
              <Scatter points={ok.map((r) => ({ x: r.snr_db ?? 0, y: (r.confident ?? 0) + (r.low ?? 0), color: STATUS_COLOUR[r.status], label: r.recording }))}
                xLabel="estimated SNR (dB)" yLabel="events reported" vline={{ v: settings.snr_min, color: Brand.red, label: 'quality gate' }} />
            </Card>
          ) : null}
          <Row wrap>
            <Button flex label="Batch results (CSV)" onPress={() => shareText('swallohear_batch.csv', toCsv(rows, cols), 'text/csv')} />
            <Button flex label="Batch results (JSON)" onPress={() => shareText('swallohear_batch.json', JSON.stringify(res, null, 1), 'application/json')} />
          </Row>
        </View>
      )}
    </Screen>
  );
}
