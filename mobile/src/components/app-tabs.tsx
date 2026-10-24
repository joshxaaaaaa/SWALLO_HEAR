import { NativeTabs } from 'expo-router/native-tabs';

import { useApp } from '@/lib/state';
import { Brand } from '@/lib/theme';

/** Bottom tab bar on iOS and Android: the web app's four pages. */
export default function AppTabs() {
  const { colors } = useApp();
  return (
    <NativeTabs backgroundColor={colors.bg} tintColor={Brand.teal} labelStyle={{ selected: { color: Brand.teal } }}>
      <NativeTabs.Trigger name="index">
        <NativeTabs.Trigger.Label>Analyze</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="waveform" md="graphic_eq" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="compare">
        <NativeTabs.Trigger.Label>Compare</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="rectangle.split.2x1" md="compare" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="batch">
        <NativeTabs.Trigger.Label>Batch</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="square.stack" md="library_music" />
      </NativeTabs.Trigger>
      <NativeTabs.Trigger name="method">
        <NativeTabs.Trigger.Label>Method</NativeTabs.Trigger.Label>
        <NativeTabs.Trigger.Icon sf="flask" md="science" />
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
