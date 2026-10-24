/** Method & results tab: how the pipeline works and what the experiments showed (from results/ via the API). */
import { useState } from 'react';
import { View } from 'react-native';

import { GroupedBars, LineChart } from '@/components/charts';
import { Screen } from '@/components/shell';
import { Card, Collapsible, Segmented, T, Table } from '@/components/ui';
import { useApp } from '@/lib/state';
import { Brand, Space } from '@/lib/theme';

const LEVELS = ['clean', '20', '10', '5', '0'] as const;
const STEPS = [
  ['🛡 1 · Quality gate', 'Estimate SNR and check clipping, dropouts, bandwidth and length. A failing recording is reported Inconclusive and its events are withheld instead of guessed.'],
  ['🌲 2 · Detector', 'A noise-trained Random Forest scores every 64 ms frame (16 ms hop) for how swallow-like it sounds.'],
  ['🔗 3 · Event assembly', 'A higher threshold starts an event, a lower one continues it, and events close together are merged.'],
  ['🧠 4 · Reliability', 'A second model scores each event for how likely it is to be correct. That score, not the detector’s own confidence, decides the tier.'],
];
const HEADLINE = [
  { finding: 'Event detection on clean audio', number: 'F1 about 0.49 (energy baseline 0.28)' },
  { finding: 'Raw model confidence as a guide to correctness', number: 'AUROC 0.53, barely better than chance' },
  { finding: 'Learned reliability score', number: 'AUROC 0.79' },
  { finding: 'Reliability-aware output, clean audio', number: 'Precision 0.41 → 0.69, recall 0.63 → 0.33' },
  { finding: 'Noise-trained vs clean-trained at 10 dB', number: 'F1 0.39 vs 0.00' },
];

export default function MethodScreen() {
  const { meta } = useApp();
  const [lvl, setLvl] = useState<(typeof LEVELS)[number]>('clean');
  const e24 = meta?.results.E2_E4 ?? {}; const e3 = meta?.results.E3?.[lvl === 'clean' ? 'clean' : `${lvl} dB`];   // E3 is keyed "clean", "20 dB", …
  const lab = (l: string) => (l === 'clean' ? 'clean' : `${l} dB`);
  return (
    <Screen>
      <T v="h2">How SWALLOHear works</T>
      {STEPS.map(([h, b]) => <Card key={h} style={{ gap: 4 }}><T bold>{h}</T><T v="caption">{b}</T></Card>)}

      <T v="h2" style={{ marginTop: Space.md }}>What the experiments showed</T>
      <T v="caption">Held-out test set: 27 participants, 171 recordings, 288 labelled swallows. Thresholds were fit on training and validation participants only.</T>
      {Object.keys(e24).length ? (<>
        <T v="h3">Noise robustness (F1)</T>
        <Card pad={false} style={{ paddingVertical: Space.sm }}>
          <LineChart x={[-0.2, 4.2]} y={[0, 0.6]} xLabel="white noise added" yLabel="F1" xTicks={LEVELS.map((l, i) => ({ v: i, label: lab(l) }))}
            series={[['RF clean-trained', Brand.slate], ['RF noise-augmented', Brand.teal]].map(([name, color]) => ({
              name: name.replace('RF ', ''), color, width: 3, dots: true, x: LEVELS.map((_, i) => i), y: LEVELS.map((l) => e24[name]?.[l]?.f1 ?? null),
            }))} />
        </Card>
        <T v="caption">Training with noise keeps the detector working where the clean-trained one collapses.</T>

        <T v="h3">Ordinary vs reliability-aware output</T>
        <Segmented options={LEVELS} value={lvl} onChange={setLvl} format={lab} />
        <Card pad={false} style={{ paddingVertical: Space.sm }}>
          <GroupedBars categories={['Precision', 'Recall', 'F1']} groups={[
            { name: 'Ordinary', color: Brand.slate, values: [e3?.ordinary?.precision ?? null, e3?.ordinary?.recall ?? null, e3?.ordinary?.f1 ?? null] },
            { name: 'Reliability-aware', color: Brand.teal, values: [e3?.reliability_aware?.precision ?? null, e3?.reliability_aware?.recall ?? null, e3?.reliability_aware?.f1 ?? null] },
          ]} />
        </Card>
        {e3?.auroc_learned !== undefined ? (
          <T v="caption">Learned reliability AUROC {e3.auroc_learned.toFixed(2)} vs raw detector confidence {e3.auroc_mean_prob?.toFixed(2)}. Reporting only Confident events trades recall for precision.</T>
        ) : null}
      </>) : <T v="caption">Connect to the analysis server to load the experiment results.</T>}

      <T v="h3">Headline numbers</T>
      <Table columns={[{ key: 'finding', label: 'Finding', width: 220 }, { key: 'number', label: 'Number', width: 220 }]} rows={HEADLINE} />
      <Collapsible title="⚠ Limits you should hold in mind" open>
        <View style={{ gap: Space.sm }}>
          <T v="small">Accuracy is modest and nowhere near clinical standard. The noise tests use synthetic white noise, not real rooms. Results come from one split of one public dataset with 27 test participants. The dataset’s participant groups were never verified, so no stroke-specific claim is made. Nothing here has been validated on Philippine data, phones or low-cost microphones.</T>
          <T v="caption">Full method, numbers and confidence intervals: README.md and results/ in the repository.</T>
        </View>
      </Collapsible>
    </Screen>
  );
}
