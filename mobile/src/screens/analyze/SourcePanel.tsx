/** The web app's sidebar "Recording" and "Stress test" sections. */
import {
  RecordingPresets, requestRecordingPermissionsAsync, setAudioModeAsync, useAudioRecorder, useAudioRecorderState,
} from 'expo-audio';
import * as DocumentPicker from 'expo-document-picker';
import { useEffect, useRef, useState } from 'react';
import { Platform, Pressable, Text, View } from 'react-native';

import { Banner, Button, Card, Collapsible, Segmented, Select, SliderRow, T, Toggle } from '@/components/ui';
import { useApp } from '@/lib/state';
import { Brand, Space } from '@/lib/theme';
import type { Loaded, LocalFile } from '@/lib/types';

export type Source = 'Demo' | 'Upload' | 'Record' | 'Synthetic';
export const SOURCES: Source[] = ['Demo', 'Upload', 'Record', 'Synthetic'];
const ICON: Record<Source, string> = { Demo: '🎧', Upload: '⬆', Record: '🎙', Synthetic: '⚗' };
export type Syn = { n: number; dur: number; seed: number };
export type StressUi = { noiseOn: boolean; kind: string; snr: number; clip: boolean };
const MAX_RECORD_MS = 120000;

export const demoLabel = (n: string) => n.replace('_noisy', ' · noisy ').replace('dB', ' dB');

export function SourcePanel({ source, setSource, demo, setDemo, syn, setSyn, onFile, loaded, busy }: {
  source: Source; setSource: (s: Source) => void; demo: string | null; setDemo: (d: string) => void;
  syn: Syn; setSyn: (s: Syn) => void; onFile: (f: LocalFile) => void; loaded: Loaded | null; busy: boolean;
}) {
  const { meta } = useApp();
  const demos = meta?.demos ?? [];
  const info = demos.find((d) => d.name === demo);
  return (
    <Card style={{ gap: Space.md }}>
      <T v="h3">Recording</T>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm }}>
        {SOURCES.map((s) => (
          <Pressable key={s} onPress={() => setSource(s)} accessibilityRole="button" accessibilityState={{ selected: s === source }}
            style={{ flexBasis: '47%', flexGrow: 1, minHeight: 42, borderRadius: 6, borderWidth: 1, alignItems: 'center', justifyContent: 'center',
              flexDirection: 'row', gap: 6, borderColor: s === source ? Brand.teal : '#9AA3AB66', backgroundColor: s === source ? Brand.teal : 'transparent' }}>
            <Text style={{ fontSize: 14 }}>{ICON[s]}</Text>
            <SourceLabel on={s === source}>{s}</SourceLabel>
          </Pressable>
        ))}
      </View>

      {source === 'Demo' ? (
        <View style={{ gap: Space.sm }}>
          <Select label="Clip" value={demo} options={demos.map((d) => d.name)} onChange={setDemo} format={demoLabel} />
          {info ? <T v="caption">{info.note ? `${info.note[0].toUpperCase()}${info.note.slice(1)} · ` : ''}{info.labels} expert-labelled swallow{info.labels === 1 ? '' : 's'} · Khalifa et al. (2021), CC BY 4.0</T> : null}
        </View>
      ) : null}
      {source === 'Upload' ? <UploadPicker onFile={onFile} loaded={loaded} busy={busy} /> : null}
      {source === 'Record' ? <Recorder onFile={onFile} loaded={loaded} busy={busy} /> : null}
      {source === 'Synthetic' ? (
        <View style={{ gap: Space.sm }}>
          <SliderRow label="Swallow-like bursts" value={syn.n} min={1} max={10} step={1} format={(v) => String(v)} onCommit={(v) => setSyn({ ...syn, n: v })} />
          <SliderRow label="Length" value={syn.dur} min={10} max={60} step={5} format={(v) => `${v} s`} onCommit={(v) => setSyn({ ...syn, dur: v })} />
          <SliderRow label="Random seed" value={syn.seed} min={0} max={50} step={1} format={(v) => String(v)} onCommit={(v) => setSyn({ ...syn, seed: v })} />
          <T v="caption">Generated bursts are the reference labels. Synthetic signal for smoke-testing, not clinical data.</T>
        </View>
      ) : null}
    </Card>
  );
}

function SourceLabel({ on, children }: { on: boolean; children: string }) {
  const { colors } = useApp();
  return <Text style={{ color: on ? '#fff' : colors.text, fontWeight: on ? '700' : '500', fontSize: 15 }}>{children}</Text>;
}

function UploadPicker({ onFile, loaded, busy }: { onFile: (f: LocalFile) => void; loaded: Loaded | null; busy: boolean }) {
  const pick = async () => {
    const res = await DocumentPicker.getDocumentAsync({ type: ['audio/*', 'video/mp4', 'application/octet-stream'], copyToCacheDirectory: true });
    if (res.canceled || !res.assets?.length) return;
    const a = res.assets[0];
    onFile({ uri: a.uri, name: a.name, mimeType: a.mimeType, file: a.file });
  };
  return (
    <View style={{ gap: Space.sm }}>
      <Button label={loaded ? `Replace file (${loaded.label})` : 'Choose an audio file'} onPress={pick} loading={busy} />
      <T v="caption">WAV, FLAC, M4A, MP3 or WebM, up to 120 s and 20 MB. Do not upload identifiable patient audio to a shared server.</T>
    </View>
  );
}

function Recorder({ onFile, loaded, busy }: { onFile: (f: LocalFile) => void; loaded: Loaded | null; busy: boolean }) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const state = useAudioRecorderState(recorder);
  const [err, setErr] = useState<string | null>(null);
  const stopping = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = async () => {
    if (stopping.current) return;
    stopping.current = true;
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    try {
      await recorder.stop();
      await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });   // back to the loudspeaker for playback on iOS
    } finally {
      stopping.current = false;
    }
    if (!recorder.uri) { setErr('The recording could not be saved.'); return; }
    const web = Platform.OS === 'web';
    onFile({ uri: recorder.uri, name: web ? 'recording.webm' : 'recording.m4a', mimeType: web ? 'audio/webm' : 'audio/mp4' });
  };
  const start = async () => {
    setErr(null);
    const perm = await requestRecordingPermissionsAsync();
    if (!perm.granted) { setErr('Microphone permission was declined. Allow it in the phone settings to record.'); return; }
    await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
    await recorder.prepareToRecordAsync();
    recorder.record();
    timer.current = setTimeout(() => void stop(), MAX_RECORD_MS);   // the model only accepts up to 120 s
  };
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const secs = Math.floor((state.durationMillis ?? 0) / 1000);
  return (
    <View style={{ gap: Space.sm }}>
      {state.isRecording ? (
        <Button kind="primary" label={`■ Stop recording  ·  ${secs}s`} onPress={stop} style={{ backgroundColor: Brand.red, borderColor: Brand.red }} />
      ) : (
        <Button kind="primary" label={loaded ? '● Record again' : '● Start recording'} onPress={start} loading={busy} />
      )}
      <T v="caption">Rest the microphone lightly against the side of the throat, stay quiet, then swallow a few times. Stops automatically at 120 s.</T>
      {err ? <Banner kind="error">{err}</Banner> : null}
    </View>
  );
}

export function StressPanel({ stress, setStress, kinds }: { stress: StressUi; setStress: (s: StressUi) => void; kinds: string[] }) {
  const active = stress.noiseOn || stress.clip;
  return (
    <Collapsible title="Stress test" open={active} right={active ? <T v="caption" color={Brand.amber}>on</T> : undefined}>
      <Toggle label="Add noise" value={stress.noiseOn} onChange={(v) => setStress({ ...stress, noiseOn: v })} />
      <Segmented options={kinds} value={stress.kind} onChange={(k) => setStress({ ...stress, kind: k })} disabled={!stress.noiseOn} />
      <SliderRow label="Noise level (SNR)" value={stress.snr} min={-5} max={30} step={1} format={(v) => `${v} dB`} disabled={!stress.noiseOn}
        onCommit={(v) => setStress({ ...stress, snr: v })} help="Lower means louder noise, relative to the whole recording." />
      <Toggle label="Simulate clipping (4× gain, hard-clipped)" value={stress.clip} onChange={(v) => setStress({ ...stress, clip: v })} />
    </Collapsible>
  );
}
