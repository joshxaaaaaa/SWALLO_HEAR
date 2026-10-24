/** Building blocks styled like the Streamlit web app: bordered cards, teal primary, pill badges. */
import Slider from '@react-native-community/slider';
import { useState, type ReactNode } from 'react';
import {
  ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Switch, Text, View,
  type StyleProp, type TextStyle, type ViewStyle,
} from 'react-native';

import { useApp } from '@/lib/state';
import { Brand, Radius, Space, tint } from '@/lib/theme';

// ----------------------------------------------------------------------------- text
const SIZES = { h1: 26, h2: 20, h3: 16.5, body: 15, small: 13, caption: 12 } as const;

export function T({ v = 'body', color, bold, center, style, children, numberOfLines }: {
  v?: keyof typeof SIZES; color?: string; bold?: boolean; center?: boolean; style?: StyleProp<TextStyle>; children: ReactNode; numberOfLines?: number;
}) {
  const { colors } = useApp();
  const heading = v === 'h1' || v === 'h2' || v === 'h3';
  return (
    <Text numberOfLines={numberOfLines} style={[{
      fontSize: SIZES[v], lineHeight: SIZES[v] * (heading ? 1.25 : 1.45),
      color: color ?? (v === 'caption' ? colors.muted : colors.text),
      fontWeight: bold || heading ? '700' : '400', textAlign: center ? 'center' : undefined,
    }, style]}>{children}</Text>
  );
}

// ----------------------------------------------------------------------------- containers
export function Card({ children, style, pad = true }: { children: ReactNode; style?: StyleProp<ViewStyle>; pad?: boolean }) {
  const { colors } = useApp();
  return <View style={[{ borderWidth: 1, borderColor: colors.border, borderRadius: Radius.md, backgroundColor: colors.card,
    padding: pad ? Space.md : 0 }, style]}>{children}</View>;
}

export function Row({ children, gap = Space.sm, style, wrap }: { children: ReactNode; gap?: number; style?: StyleProp<ViewStyle>; wrap?: boolean }) {
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap, flexWrap: wrap ? 'wrap' : 'nowrap' }, style]}>{children}</View>;
}

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <View style={{ gap: Space.sm, marginTop: Space.lg }}>
      <Row style={{ justifyContent: 'space-between' }}><T v="h3">{title}</T>{right}</Row>
      {children}
    </View>
  );
}

export function Banner({ kind = 'warn', children }: { kind?: 'warn' | 'info' | 'error' | 'success'; children: ReactNode }) {
  const { colors } = useApp();
  const c = kind === 'warn' ? null : kind === 'error' ? Brand.red : kind === 'success' ? Brand.green : Brand.teal;
  return (
    <View style={{ borderRadius: Radius.md, padding: Space.md, borderWidth: 1,
      backgroundColor: c ? tint(c, 0.1) : colors.warnBg, borderColor: c ? tint(c, 0.35) : colors.warnBorder }}>
      {typeof children === 'string' ? <T v="small" color={c ?? colors.warnText}>{children}</T> : children}
    </View>
  );
}

// ----------------------------------------------------------------------------- inputs
export function Button({ label, onPress, kind = 'secondary', disabled, small, flex, loading, style }: {
  label: string; onPress?: () => void; kind?: 'primary' | 'secondary' | 'ghost'; disabled?: boolean; small?: boolean; flex?: boolean;
  loading?: boolean; style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useApp();
  const primary = kind === 'primary';
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled || loading} onPress={onPress}
      style={({ pressed }) => [{
        flex: flex ? 1 : undefined, minHeight: small ? 34 : 42, paddingHorizontal: small ? Space.md : Space.lg,
        borderRadius: Radius.sm, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: Space.xs,
        backgroundColor: primary ? Brand.teal : kind === 'ghost' ? 'transparent' : colors.card,
        borderWidth: kind === 'ghost' ? 0 : 1, borderColor: primary ? Brand.teal : colors.border,
        opacity: disabled ? 0.45 : pressed ? 0.75 : 1,
      }, style]}>
      {loading && <ActivityIndicator size="small" color={primary ? '#fff' : Brand.teal} />}
      <Text style={{ color: primary ? '#fff' : colors.text, fontSize: small ? 13 : 15, fontWeight: '600' }}>{label}</Text>
    </Pressable>
  );
}

/** Pills that act as one choice; `columns` lays them out as an equal-width grid. */
export function Segmented<V extends string | number>({ options, value, onChange, format, columns, disabled }: {
  options: readonly V[]; value: V | null; onChange: (v: V) => void; format?: (v: V) => string; columns?: number; disabled?: boolean;
}) {
  const { colors } = useApp();
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm, opacity: disabled ? 0.45 : 1 }}>
      {options.map((o) => {
        const on = o === value;
        return (
          <Pressable key={String(o)} disabled={disabled} onPress={() => onChange(o)} accessibilityRole="button" accessibilityState={{ selected: on }}
            style={{ flexBasis: columns ? `${100 / columns - 3}%` : undefined, flexGrow: columns ? 1 : 0, minHeight: 38,
              paddingHorizontal: Space.md, borderRadius: Radius.sm, borderWidth: 1, alignItems: 'center', justifyContent: 'center',
              borderColor: on ? Brand.teal : colors.border, backgroundColor: on ? Brand.teal : colors.card }}>
            <Text style={{ color: on ? '#fff' : colors.text, fontSize: 14, fontWeight: on ? '700' : '500' }}>{format ? format(o) : String(o)}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Toggle({ label, value, onChange, disabled }: { label: string; value: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <Row style={{ justifyContent: 'space-between', opacity: disabled ? 0.45 : 1 }}>
      <T v="small" style={{ flex: 1 }}>{label}</T>
      <Switch value={value} disabled={disabled} onValueChange={onChange} trackColor={{ true: Brand.teal, false: '#9AA3AB' }}
        thumbColor="#fff" accessibilityLabel={label} />
    </Row>
  );
}

/** Shows the value live while dragging and reports it once on release, so the server isn't flooded. */
export function SliderRow({ label, value, min, max, step, format = (v) => v.toFixed(2), onCommit, disabled, help }: {
  label: string; value: number; min: number; max: number; step: number; format?: (v: number) => string;
  onCommit: (v: number) => void; disabled?: boolean; help?: string;
}) {
  const { colors } = useApp();
  const [live, setLive] = useState<number | null>(null);
  return (
    <View style={{ opacity: disabled ? 0.45 : 1 }}>
      <Row style={{ justifyContent: 'space-between' }}>
        <T v="small" style={{ flex: 1 }}>{label}</T>
        <T v="small" bold color={Brand.teal}>{format(live ?? value)}</T>
      </Row>
      <Slider value={value} minimumValue={min} maximumValue={max} step={step} disabled={disabled}
        onValueChange={setLive} onSlidingComplete={(v) => { setLive(null); onCommit(Math.round(v / step) * step); }}
        minimumTrackTintColor={Brand.teal} maximumTrackTintColor={colors.border} thumbTintColor={Brand.teal} style={{ height: 36 }} />
      {help ? <T v="caption">{help}</T> : null}
    </View>
  );
}

export function Select<V extends string>({ label, value, options, onChange, format }: {
  label?: string; value: V | null; options: readonly V[]; onChange: (v: V) => void; format?: (v: V) => string;
}) {
  const { colors } = useApp();
  const [open, setOpen] = useState(false);
  const fmt = format ?? ((v: V) => v);
  return (
    <View style={{ gap: Space.xs }}>
      {label ? <T v="small">{label}</T> : null}
      <Pressable onPress={() => setOpen(true)} accessibilityRole="button" accessibilityLabel={label ?? 'Choose'}
        style={{ borderWidth: 1, borderColor: colors.border, borderRadius: Radius.sm, backgroundColor: colors.surface,
          paddingHorizontal: Space.md, minHeight: 42, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <T>{value ? fmt(value) : 'Choose…'}</T><T color={colors.muted}>▾</T>
      </Pressable>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <View style={[styles.sheet, { backgroundColor: colors.bg, borderColor: colors.border }]}>
            {label ? <T v="h3" style={{ marginBottom: Space.sm }}>{label}</T> : null}
            <ScrollView style={{ maxHeight: 420 }}>
              {options.map((o) => (
                <Pressable key={o} onPress={() => { onChange(o); setOpen(false); }}
                  style={{ paddingVertical: Space.md, paddingHorizontal: Space.sm, borderRadius: Radius.sm,
                    backgroundColor: o === value ? tint(Brand.teal, 0.12) : 'transparent' }}>
                  <T bold={o === value} color={o === value ? Brand.teal : undefined}>{fmt(o)}</T>
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

export function Collapsible({ title, children, open: initial = false, right }: { title: string; children: ReactNode; open?: boolean; right?: ReactNode }) {
  const { colors } = useApp();
  const [open, setOpen] = useState(initial);
  return (
    <Card pad={false}>
      <Pressable onPress={() => setOpen(!open)} accessibilityRole="button" accessibilityState={{ expanded: open }}
        style={{ padding: Space.md, flexDirection: 'row', alignItems: 'center', gap: Space.sm }}>
        <T color={colors.muted}>{open ? '▾' : '▸'}</T><T bold style={{ flex: 1 }}>{title}</T>{right}
      </Pressable>
      {open ? <View style={{ paddingHorizontal: Space.md, paddingBottom: Space.md, gap: Space.md }}>{children}</View> : null}
    </Card>
  );
}

// ----------------------------------------------------------------------------- display
export function Badge({ label, color, solid }: { label: string; color?: string; solid?: boolean }) {
  const { colors } = useApp();
  const c = color ?? colors.muted;
  return (
    <View style={{ alignSelf: 'flex-start', borderRadius: Radius.pill, paddingHorizontal: 9, paddingVertical: 2,
      backgroundColor: solid ? c : tint(c.startsWith('#') ? c : Brand.slate, 0.14), borderWidth: solid ? 0 : 1,
      borderColor: tint(c.startsWith('#') ? c : Brand.slate, 0.4) }}>
      <Text style={{ fontSize: 12, fontWeight: '600', color: solid ? '#fff' : c }}>{label}</Text>
    </View>
  );
}

export function Metric({ label, value, delta, deltaColor, help, style }: {
  label: string; value: string | number; delta?: string; deltaColor?: string; help?: string; style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useApp();
  const [show, setShow] = useState(false);
  return (
    <Card style={[{ flexGrow: 1, flexBasis: '46%', gap: 2 }, style]}>
      <Pressable disabled={!help} onPress={() => setShow(!show)} accessibilityRole={help ? 'button' : undefined}>
        <T v="small" color={colors.muted} numberOfLines={1}>{label}{help ? '  ⓘ' : ''}</T>
      </Pressable>
      <T v="h1" style={{ fontWeight: '500' }} numberOfLines={1}>{value}</T>
      {delta ? <Badge label={delta} color={deltaColor ?? colors.muted} /> : null}
      {show && help ? <T v="caption">{help}</T> : null}
    </Card>
  );
}

export function Progress({ value, color = Brand.teal, width = 70 }: { value: number; color?: string; width?: number }) {
  const { colors } = useApp();
  return (
    <View style={{ width, height: 8, borderRadius: 4, backgroundColor: colors.grid, overflow: 'hidden' }}>
      <View style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, height: 8, backgroundColor: color }} />
    </View>
  );
}

export type Column<R> = { key: string; label: string; width: number; align?: 'left' | 'right'; render?: (row: R, i: number) => ReactNode };

/** A horizontally scrollable table; tap a row to select it. */
export function Table<R extends Record<string, unknown>>({ columns, rows, selected, onRowPress }: {
  columns: Column<R>[]; rows: R[]; selected?: number | null; onRowPress?: (i: number) => void;
}) {
  const { colors } = useApp();
  return (
    <Card pad={false} style={{ overflow: 'hidden' }}>
      <ScrollView horizontal showsHorizontalScrollIndicator>
        <View>
          <View style={{ flexDirection: 'row', backgroundColor: colors.surface }}>
            {columns.map((c) => (
              <View key={c.key} style={[styles.cell, { width: c.width, alignItems: c.align === 'right' ? 'flex-end' : 'flex-start' }]}>
                <T v="caption" bold>{c.label}</T>
              </View>
            ))}
          </View>
          {rows.map((r, i) => (
            <Pressable key={i} disabled={!onRowPress} onPress={() => onRowPress?.(i)}
              style={{ flexDirection: 'row', borderTopWidth: 1, borderTopColor: colors.border,
                backgroundColor: selected === i ? tint(Brand.teal, 0.12) : 'transparent' }}>
              {columns.map((c) => (
                <View key={c.key} style={[styles.cell, { width: c.width, alignItems: c.align === 'right' ? 'flex-end' : 'flex-start' }]}>
                  {c.render ? c.render(r, i) : <T v="small">{r[c.key] === null || r[c.key] === undefined ? '–' : String(r[c.key])}</T>}
                </View>
              ))}
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </Card>
  );
}

export function Verdict({ verdict, codes, help, subtitle }: {
  verdict: { colour: string; icon: string; headline: string; text: string }; codes: string[]; help?: Record<string, string>; subtitle?: string;
}) {
  const c = verdict.colour;
  return (
    <View style={{ flexDirection: 'row', gap: Space.md, borderRadius: Radius.lg, padding: Space.lg, borderWidth: 1,
      backgroundColor: tint(c, 0.13), borderColor: tint(c, 0.45) }}>
      <View style={{ width: 38, height: 38, borderRadius: 19, backgroundColor: c, alignItems: 'center', justifyContent: 'center' }}>
        <Text style={{ color: '#fff', fontWeight: '800', fontSize: 19 }}>{verdict.icon}</Text>
      </View>
      <View style={{ flex: 1, gap: 4 }}>
        <T v="h2">{verdict.headline}</T>
        <T v="small">{verdict.text}</T>
        {codes.length ? (
          <View style={{ gap: 4, marginTop: 4 }}>
            {codes.map((code) => (
              <Row key={code} style={{ alignItems: 'flex-start' }}>
                <Badge label={code.replace(/_/g, ' ').toLowerCase().replace(/^\w/, (m) => m.toUpperCase())} color={c} />
                {help?.[code] ? <T v="caption" style={{ flex: 1 }}>{help[code]}</T> : null}
              </Row>
            ))}
          </View>
        ) : null}
        {subtitle ? <T v="caption">{subtitle}</T> : null}
      </View>
    </View>
  );
}

export function Loading({ label = 'Analysing…' }: { label?: string }) {
  return <Row style={{ padding: Space.lg, justifyContent: 'center' }}><ActivityIndicator color={Brand.teal} /><T v="small">{label}</T></Row>;
}

const styles = StyleSheet.create({
  cell: { paddingHorizontal: 10, paddingVertical: 9, justifyContent: 'center' },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', padding: Space.xl },
  sheet: { borderRadius: Radius.lg, padding: Space.lg, borderWidth: 1, maxWidth: 520, width: '100%', alignSelf: 'center' },
});
