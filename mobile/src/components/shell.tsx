/** Screen frame shared by every tab: brand header, theme switch, settings sheet and the research disclaimer. */
import { useState, type ReactNode } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { defaultApiBase } from '@/lib/api';
import { useApp } from '@/lib/state';
import { Brand, MaxWidth, Radius, Space } from '@/lib/theme';

import { Banner, Button, Row, SliderRow, T } from './ui';

export function Screen({ children }: { children: ReactNode }) {
  const { colors } = useApp();
  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: Space.lg, paddingBottom: 120 }}>
        <View style={{ width: '100%', maxWidth: MaxWidth, alignSelf: 'center', gap: Space.md }}>
          <Header />
          {children}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function Header() {
  const { colors, dark, setDark, changed, metaError, reloadMeta } = useApp();
  const [settingsOpen, setSettingsOpen] = useState(false);
  return (
    <View style={{ gap: Space.md }}>
      <Row style={{ justifyContent: 'space-between' }}>
        <View style={{ flexShrink: 1 }}>
          <Text style={{ fontSize: 26, fontWeight: '800', color: colors.text, letterSpacing: -0.5 }}>
            SWALLO<Text style={{ color: Brand.teal }}>Hear</Text>
          </Text>
          <T v="caption" numberOfLines={2}>Reliability-aware swallowing-event analysis · Team RIPARION</T>
        </View>
        <Row gap={Space.xs}>
          <View style={{ flexDirection: 'row', borderWidth: 1, borderColor: colors.border, borderRadius: Radius.sm, overflow: 'hidden' }}>
            {[false, true].map((d) => (
              <Pressable key={String(d)} onPress={() => setDark(d)} accessibilityRole="button" accessibilityLabel={d ? 'Dark mode' : 'Light mode'}
                accessibilityState={{ selected: dark === d }}
                style={{ width: 38, height: 34, alignItems: 'center', justifyContent: 'center',
                  backgroundColor: dark === d ? (dark ? 'rgba(27,127,122,0.35)' : 'rgba(27,127,122,0.15)') : 'transparent' }}>
                <Text style={{ fontSize: 16, color: dark === d ? Brand.teal : colors.muted }}>{d ? '☾' : '☀'}</Text>
              </Pressable>
            ))}
          </View>
          <Pressable onPress={() => setSettingsOpen(true)} accessibilityRole="button" accessibilityLabel="Detector settings"
            style={{ height: 36, paddingHorizontal: 10, borderRadius: Radius.sm, borderWidth: 1, alignItems: 'center', justifyContent: 'center',
              borderColor: changed.length ? Brand.teal : colors.border, backgroundColor: changed.length ? 'rgba(27,127,122,0.12)' : 'transparent' }}>
            <Text style={{ fontSize: 17, color: changed.length ? Brand.teal : colors.text }}>⚙</Text>
          </Pressable>
        </Row>
      </Row>
      <Banner><T v="small" color={colors.warnText}><T v="small" bold color={colors.warnText}>Research prototype, not a diagnostic device. </T>
        It detects swallowing-related acoustic events. It does not assess dysphagia, aspiration or pneumonia, and must not be used to make care decisions.</T></Banner>
      {metaError ? (
        <Banner kind="error"><View style={{ gap: Space.sm }}><T v="small" color={Brand.red}>{metaError}</T>
          <Row><Button small label="Retry" onPress={reloadMeta} /><Button small label="Server settings" onPress={() => setSettingsOpen(true)} /></Row></View></Banner>
      ) : null}
      <SettingsSheet open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </View>
  );
}

/** The web app's sidebar "Detector settings", plus where to find the analysis server. */
export function SettingsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { colors, settings, setSetting, resetSettings, changed, apiBase, setServer } = useApp();
  const [server, setServerText] = useState(apiBase);
  const { width: winW } = useWindowDimensions();
  return (
    <Modal visible={open} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose} transparent={false}>
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
        <ScrollView contentContainerStyle={{ padding: Space.lg }}>
          <View style={{ width: Math.min(640, winW - 2 * Space.lg), alignSelf: 'center', gap: Space.lg }}>
          <Row style={{ justifyContent: 'space-between' }}>
            <T v="h2">Detector settings</T>
            <Button small kind="primary" label="Done" onPress={onClose} />
          </Row>
          <SliderRow label="Reliability threshold (Confident tier)" value={settings.tau} min={0.2} max={0.9} step={0.05}
            onCommit={(v) => setSetting('tau', v)} help="Events whose reliability reaches this are Confident. Higher = fewer events, more of them correct." />
          <SliderRow label="Start threshold" value={settings.hi} min={0.3} max={0.95} step={0.05} onCommit={(v) => setSetting('hi', v)}
            help="Frame score that starts an event." />
          <SliderRow label="Continue threshold" value={settings.lo} min={0.2} max={0.95} step={0.05} onCommit={(v) => setSetting('lo', v)}
            help="Frame score that keeps an event going. Capped at the start threshold." />
          <SliderRow label="Merge events closer than" value={settings.merge} min={0} max={1.5} step={0.1} format={(v) => `${v.toFixed(1)} s`}
            onCommit={(v) => setSetting('merge', v)} />
          <SliderRow label="Quality gate: minimum SNR" value={settings.snr_min} min={0} max={25} step={0.5} format={(v) => `${v.toFixed(1)} dB`}
            onCommit={(v) => setSetting('snr_min', v)} help="Below this the result is withheld." />
          {changed.length ? <T v="caption">Moved off the validated values ({changed.join(', ')}). Reported results use the validated values.</T> : null}
          <Button label="Reset to validated" onPress={resetSettings} disabled={!changed.length} />

          <View style={{ gap: Space.sm, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: Space.lg }}>
            <T v="h3">Analysis server</T>
            <T v="caption">The app sends audio to the SWALLOHear API (python api/server.py). Automatic goes through the Expo server this app was loaded from, which forwards to the API on the same computer; you only need an address here for a separately hosted server.</T>
            <TextInput value={server} onChangeText={setServerText} autoCapitalize="none" autoCorrect={false} keyboardType="url"
              style={{ borderWidth: 1, borderColor: colors.border, borderRadius: Radius.sm, padding: Space.md, color: colors.text, backgroundColor: colors.surface }} />
            <Row>
              <Button flex label="Use this address" kind="primary" onPress={() => setServer(server.trim() || null)} />
              <Button flex label="Automatic" onPress={() => { setServer(null); setServerText(defaultApiBase()); }} />
            </Row>
            <T v="caption">Now using: {apiBase}</T>
          </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}
