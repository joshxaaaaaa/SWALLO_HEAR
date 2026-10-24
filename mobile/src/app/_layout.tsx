import { setAudioModeAsync } from 'expo-audio';
import { DarkTheme, DefaultTheme, ThemeProvider } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';

import AppTabs from '@/components/app-tabs';
import { AppProvider, useApp } from '@/lib/state';
import { Brand } from '@/lib/theme';

export default function RootLayout() {
  useEffect(() => { void setAudioModeAsync({ playsInSilentMode: true }); }, []);
  return (
    <AppProvider>
      <Themed />
    </AppProvider>
  );
}

function Themed() {
  const { dark, colors } = useApp();
  const base = dark ? DarkTheme : DefaultTheme;
  return (
    <ThemeProvider value={{ ...base, colors: { ...base.colors, primary: Brand.teal, background: colors.bg, card: colors.bg, text: colors.text, border: colors.border } }}>
      <StatusBar style={dark ? 'light' : 'dark'} />
      <AppTabs />
    </ThemeProvider>
  );
}
