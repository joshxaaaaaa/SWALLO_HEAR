/** Timeline tab: waveform + spectrogram + score, tap a marker to open the event card. */
import { useState } from 'react';
import { View } from 'react-native';

import { AudioBar } from '@/components/audio';
import { EventZoom, Gauge, Timeline } from '@/components/charts';
import { Badge, Button, Card, Row, Segmented, T, Toggle } from '@/components/ui';
import { absolute, api } from '@/lib/api';
import { noteKey, useApp } from '@/lib/state';
import { Brand, Space, TierColor } from '@/lib/theme';
import type { Analysis, SwEvent } from '@/lib/types';

export const CALLS = ['Swallow', 'Not swallow', 'Unsure'] as const;
const ZOOMS = [1, 2, 4, 8] as const;

export function TimelineTab({ a, events, selected, setSelected }: {
  a: Analysis; events: SwEvent[]; selected: number; setSelected: (i: number) => void;
}) {
  const { settings } = useApp();
  const [spec, setSpec] = useState(true);
  const [ref, setRef] = useState(true);
  const [zoom, setZoom] = useState<(typeof ZOOMS)[number]>(1);
  const hasRef = a.ref.length > 0;
  return (
    <View style={{ gap: Space.md }}>
      <Row wrap gap={Space.lg}>
        <View style={{ flexBasis: 150, flexGrow: 1 }}><Toggle label="Spectrogram" value={spec} onChange={setSpec} /></View>
        <View style={{ flexBasis: 150, flexGrow: 1 }}><Toggle label="Expert labels" value={ref && hasRef} onChange={setRef} disabled={!hasRef} /></View>
      </Row>
      <Row><T v="small">Zoom</T><Segmented options={ZOOMS} value={zoom} onChange={setZoom} format={(z) => `${z}×`} /></Row>
      {a.faded && events.length ? <T v="caption" color={Brand.amber}>Result withheld: candidates are shown faded for inspection only.</T> : null}
      <Card pad={false} style={{ paddingVertical: Space.sm, paddingRight: Space.xs }}>
        <Timeline a={a} events={events} faded={a.faded} showSpec={spec} showRef={ref && hasRef} selected={selected} onSelect={setSelected}
          hi={settings.hi} lo={Math.min(settings.lo, settings.hi)} zoom={zoom} />
      </Card>
      <T v="caption">Teal = Confident, amber = Low-confidence{ref && hasRef ? ', dotted green = expert labels' : ''}. Tap a numbered marker to inspect that event{zoom > 1 ? '; swipe sideways to scroll' : ''}.</T>
      <AudioBar url={absolute(a.audio_url)} />
      {events.length ? <EventCard a={a} events={events} i={Math.min(selected, events.length - 1)} setSelected={setSelected} /> : null}
    </View>
  );
}

export function EventCard({ a, events, i, setSelected }: { a: Analysis; events: SwEvent[]; i: number; setSelected: (i: number) => void }) {
  const { settings, notes, setNote } = useApp();
  const e = events[i]; const n = events.length;
  const call = notes[noteKey(a.label, e.onset_s)] ?? null;
  return (
    <Card style={{ gap: Space.md }}>
      <Row style={{ justifyContent: 'space-between' }}>
        <Button small label="‹ Prev" onPress={() => setSelected((i - 1 + n) % n)} disabled={n < 2} />
        <View style={{ alignItems: 'center', flexShrink: 1 }}>
          <T bold>Event {i + 1} of {n}</T>
          <T v="caption">{e.onset_s.toFixed(2)}–{e.offset_s.toFixed(2)} s · {Math.round(e.duration_ms)} ms</T>
        </View>
        <Button small label="Next ›" onPress={() => setSelected((i + 1) % n)} disabled={n < 2} />
      </Row>
      <Badge label={e.tier === 'Confident' ? '✓ Confident' : '? Low-confidence'} color={TierColor[e.tier]} />
      <AudioBar compact url={api.clipUrl(a, e.onset_s, e.offset_s)} />
      <T v="caption">Clip includes 0.25 s either side of the event.</T>
      <View style={{ gap: Space.xs }}>
        <T v="small">Your call</T>
        <Segmented options={CALLS} value={call as (typeof CALLS)[number] | null}
          onChange={(c) => setNote(a.label, e.onset_s, c === call ? null : c)} />
      </View>
      <Gauge value={e.reliability} tau={settings.tau} tier={e.tier} />
      <T v="caption" center>Reliability score; the marker is the threshold ({settings.tau.toFixed(2)}). Raw detector confidence: {e.model_confidence.toFixed(2)}.</T>
      {e.up.length || e.down.length ? (
        <View style={{ gap: 2 }}>
          {e.up.length ? <T v="small"><T v="small" bold color={Brand.green}>↑ </T>{e.up.join(', ')}</T> : null}
          {e.down.length ? <T v="small"><T v="small" bold color={Brand.amber}>↓ </T>{e.down.join(', ')}</T> : null}
          <T v="caption">What pushed this event’s reliability up or down most. Full breakdown on the Events tab.</T>
        </View>
      ) : null}
      <EventZoom a={a} e={e} />
    </Card>
  );
}
