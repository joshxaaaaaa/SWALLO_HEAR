import { TabList, TabSlot, TabTrigger, Tabs, type TabTriggerSlotProps } from 'expo-router/ui';
import { useEffect } from 'react';
import { Pressable, Text, useWindowDimensions, type PressableProps } from 'react-native';
import Svg, { Path, Rect } from 'react-native-svg';

import { useApp } from '@/lib/state';
import { Brand } from '@/lib/theme';

type Icon = 'analyze' | 'compare' | 'batch' | 'method';
const TABS: { name: string; href: '/' | '/compare' | '/batch' | '/method'; label: string; wide: string; icon: Icon }[] = [
  { name: 'index', href: '/', label: 'Analyze', wide: '📈 Analyze', icon: 'analyze' },
  { name: 'compare', href: '/compare', label: 'Compare', wide: '⇆ Compare', icon: 'compare' },
  { name: 'batch', href: '/batch', label: 'Batch', wide: '▤ Batch', icon: 'batch' },
  { name: 'method', href: '/method', label: 'Method', wide: '⚗ Method & results', icon: 'method' },
];

/**
 * Web navigation. Phone-sized windows get a bottom tab bar like the iOS/Android app;
 * wider windows get a top bar like the Streamlit web app.
 */
export default function AppTabs() {
  const { colors } = useApp();
  const { width } = useWindowDimensions();
  const phone = width < 640;
  useEffect(() => {
    // Browsers default SVG text to a serif font; match the rest of the UI.
    const s = document.createElement('style');
    s.textContent = 'svg text { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }';
    document.head.appendChild(s);
    return () => s.remove();
  }, []);

  const list = (
    <TabList style={phone
      ? { flexDirection: 'row', backgroundColor: colors.bg, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 6, paddingBottom: 16 }
      : { flexDirection: 'row', gap: 6, paddingHorizontal: 16, paddingVertical: 8, backgroundColor: colors.bg,
          borderBottomWidth: 1, borderBottomColor: colors.border, justifyContent: 'center' }}>
      {TABS.map((t) => (
        <TabTrigger key={t.name} name={t.name} href={t.href} asChild>
          {phone ? <BottomTab icon={t.icon}>{t.label}</BottomTab> : <TopTab>{t.wide}</TopTab>}
        </TabTrigger>
      ))}
    </TabList>
  );
  return (
    <Tabs>
      {phone ? null : list}
      <TabSlot style={{ flex: 1 }} />
      {phone ? list : null}
    </Tabs>
  );
}

function TopTab({ children, isFocused, ...props }: TabTriggerSlotProps) {
  const { colors } = useApp();
  return (
    <Pressable {...(props as PressableProps)} style={{ paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6,
      backgroundColor: isFocused ? 'rgba(27,127,122,0.14)' : 'transparent' }}>
      <Text style={{ fontSize: 14, fontWeight: isFocused ? '700' : '500', color: isFocused ? Brand.teal : colors.text }}>{children}</Text>
    </Pressable>
  );
}

function BottomTab({ children, isFocused, icon, ...props }: TabTriggerSlotProps & { icon: Icon }) {
  const { colors } = useApp();
  const c = isFocused ? Brand.teal : colors.muted;
  return (
    <Pressable {...(props as PressableProps)} accessibilityRole="tab" style={{ flex: 1, alignItems: 'center', gap: 3, paddingVertical: 2 }}>
      <TabIcon name={icon} color={c} />
      <Text style={{ fontSize: 11, fontWeight: isFocused ? '600' : '500', color: c }}>{children}</Text>
    </Pressable>
  );
}

/** Outline icons echoing the native tab bar's SF Symbols (waveform, split view, stack, flask). */
function TabIcon({ name, color }: { name: Icon; color: string }) {
  const s = { stroke: color, strokeWidth: 1.8, fill: 'none', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  return (
    <Svg width={26} height={24} viewBox="0 0 26 24">
      {name === 'analyze' ? <Path d="M3 12v0M7 8v8M11 4v16M15 7v10M19 9v6M23 11v2" {...s} /> : null}
      {name === 'compare' ? (<><Rect x={3} y={4} width={20} height={16} rx={3} {...s} /><Path d="M13 4v16" {...s} /></>) : null}
      {name === 'batch' ? (<><Rect x={5} y={8} width={16} height={13} rx={2.5} {...s} /><Path d="M7 5h12M9 2.5h8" {...s} /></>) : null}
      {name === 'method' ? <Path d="M10 2.5h6M11 2.5v7L5 20a1.5 1.5 0 0 0 1.3 2h13.4A1.5 1.5 0 0 0 21 20l-6-10.5v-7M8 15h10" {...s} /> : null}
    </Svg>
  );
}
