/**
 * FontScaleContext.tsx — global font-zoom for the web app.
 *
 * Three discrete buckets: A (1.00), A+ (1.15), A++ (1.30).
 * Persisted to AsyncStorage so the choice survives reloads.
 *
 * Implementation:
 *   • On WEB, we apply CSS `zoom` to `document.documentElement` — this scales
 *     every rendered element proportionally without forcing each Text/View to
 *     re-render. Supported in Chrome/Edge/Safari/Firefox (modern).
 *   • On NATIVE we set the same scale on a React context that components can
 *     consume via `useFontScale()` and apply to a `fontSize` multiplier in
 *     their own StyleSheet entries (future opt-in; not enforced yet).
 */
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type FontScaleKey = 'A' | 'A+' | 'A++';

export const FONT_SCALE_MAP: Record<FontScaleKey, number> = {
  'A': 1.0,
  'A+': 1.15,
  'A++': 1.3,
};

const STORAGE_KEY = 'display_font_scale_v1';

interface FontScaleContextValue {
  scaleKey: FontScaleKey;
  scale: number;
  setScale: (key: FontScaleKey) => void;
  ready: boolean;
}

const FontScaleContext = createContext<FontScaleContextValue>({
  scaleKey: 'A',
  scale: 1,
  setScale: () => {},
  ready: false,
});

function applyWebZoom(scale: number) {
  if (Platform.OS !== 'web' || typeof document === 'undefined') return;
  try {
    // `zoom` is the simplest cross-element scaling primitive on web. It
    // proportionally scales font, spacing, images. Modern browsers
    // (incl. Firefox 126+) support it.
    (document.documentElement.style as any).zoom = String(scale);
  } catch {
    /* no-op */
  }
}

export const FontScaleProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [scaleKey, setScaleKeyState] = useState<FontScaleKey>('A');
  const [ready, setReady] = useState(false);

  // Hydrate from storage on mount
  useEffect(() => {
    (async () => {
      try {
        const v = await AsyncStorage.getItem(STORAGE_KEY);
        if (v && (v === 'A' || v === 'A+' || v === 'A++')) {
          setScaleKeyState(v as FontScaleKey);
          applyWebZoom(FONT_SCALE_MAP[v as FontScaleKey]);
        } else {
          applyWebZoom(1);
        }
      } catch {
        applyWebZoom(1);
      } finally {
        setReady(true);
      }
    })();
  }, []);

  const setScale = useCallback((key: FontScaleKey) => {
    setScaleKeyState(key);
    applyWebZoom(FONT_SCALE_MAP[key]);
    AsyncStorage.setItem(STORAGE_KEY, key).catch(() => {});
  }, []);

  return (
    <FontScaleContext.Provider
      value={{
        scaleKey,
        scale: FONT_SCALE_MAP[scaleKey],
        setScale,
        ready,
      }}
    >
      {children}
    </FontScaleContext.Provider>
  );
};

export const useFontScale = () => useContext(FontScaleContext);
