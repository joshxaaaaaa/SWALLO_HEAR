/** Compact audio player for the analysed recording or one event's clip (expo-audio, streamed from the API). */
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { Pressable, Text, View } from 'react-native';

import { useApp } from '@/lib/state';
import { Brand, Radius, Space } from '@/lib/theme';

import { T } from './ui';

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

export function AudioBar({ url, compact }: { url: string; compact?: boolean }) {
  const { colors } = useApp();
  const player = useAudioPlayer(url);
  const st = useAudioPlayerStatus(player);
  const dur = st.duration || 0; const pos = Math.min(st.currentTime || 0, dur || Infinity);

  const toggle = async () => {
    if (st.playing) { player.pause(); return; }
    if (dur && pos >= dur - 0.05) await player.seekTo(0);
    player.play();
  };

  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: Space.md, borderRadius: Radius.pill, backgroundColor: colors.surface,
      paddingVertical: compact ? 6 : 8, paddingHorizontal: Space.md }}>
      <Pressable onPress={toggle} accessibilityRole="button" accessibilityLabel={st.playing ? 'Pause' : 'Play'}
        style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: Brand.teal, alignItems: 'center', justifyContent: 'center' }}>
        <Text style={{ color: '#fff', fontSize: 13, fontWeight: '800' }}>{st.playing ? '❚❚' : '▶'}</Text>
      </Pressable>
      <View style={{ flex: 1, height: 4, borderRadius: 2, backgroundColor: colors.border, overflow: 'hidden' }}>
        <View style={{ width: `${dur ? (pos / dur) * 100 : 0}%`, height: 4, backgroundColor: Brand.teal }} />
      </View>
      <T v="caption">{mmss(pos)} / {mmss(dur)}</T>
    </View>
  );
}
