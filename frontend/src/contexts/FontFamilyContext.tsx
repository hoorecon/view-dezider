/**
 * FontFamilyContext — central, admin-configurable UI font.
 *
 * Source of truth: backend GET /api/appearance (admin sets it via the Admin →
 * Appearance screen). The choice is cached in AsyncStorage for instant paint on
 * reload, then reconciled with the server.
 *
 * WEB: we inject the Google Fonts <link> for the chosen family and set
 *   document font-family on <html>/<body>. The browser renders every weight
 *   (400–800) from one family, matching jelcos.ai. Icon fonts are untouched
 *   because @expo/vector-icons sets its family inline on each glyph.
 *
 * NATIVE: dynamic web-font swapping isn't available; the app keeps the system
 *   font (Inter is the bundled default). Selection still persists and applies
 *   on web. Font SIZE responsiveness continues to be handled by FontScale.
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { DEFAULT_FONT_KEY, FONT_OPTIONS, getFontOption } from '../constants/fonts';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const STORAGE_KEY = 'app_font_family_v1';
const LINK_ID = 'app-google-font-link';

interface FontFamilyValue {
  fontKey: string;
  ready: boolean;
  setFont: (key: string) => void;
}

const FontFamilyContext = createContext<FontFamilyValue>({
  fontKey: DEFAULT_FONT_KEY,
  ready: false,
  setFont: () => {},
});

function applyWebFont(key: string) {
  if (Platform.OS !== 'web' || typeof document === 'undefined') return;
  const opt = getFontOption(key);
  try {
    // 1) Inject / update the Google Fonts stylesheet for this family.
    let link = document.getElementById(LINK_ID) as HTMLLinkElement | null;
    if (opt.googleHref) {
      if (!link) {
        link = document.createElement('link');
        link.id = LINK_ID;
        link.rel = 'stylesheet';
        document.head.appendChild(link);
      }
      if (link.href !== opt.googleHref) link.href = opt.googleHref;
    } else if (link) {
      // System font — remove any previously injected link.
      link.parentNode?.removeChild(link);
    }
    // 2) Apply the family at the document root (no !important → inline icon
    //    fonts keep precedence). Cascades to all RN-web text without an
    //    explicit fontFamily.
    document.documentElement.style.fontFamily = opt.webStack;
    if (document.body) document.body.style.fontFamily = opt.webStack;
  } catch {
    /* no-op */
  }
}

export const FontFamilyProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [fontKey, setFontKey] = useState<string>(DEFAULT_FONT_KEY);
  const [ready, setReady] = useState(false);

  const apply = useCallback((key: string) => {
    const valid = FONT_OPTIONS.some((f) => f.key === key) ? key : DEFAULT_FONT_KEY;
    setFontKey(valid);
    applyWebFont(valid);
  }, []);

  // Hydrate from cache instantly, then reconcile with the server.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cached = await AsyncStorage.getItem(STORAGE_KEY);
        if (cached && !cancelled) apply(cached);
      } catch { /* ignore */ }

      try {
        const res = await fetch(`${API_URL}/api/appearance`);
        if (res.ok) {
          const data = await res.json();
          const serverFont = data?.font_family || DEFAULT_FONT_KEY;
          if (!cancelled) {
            apply(serverFont);
            AsyncStorage.setItem(STORAGE_KEY, serverFont).catch(() => {});
          }
        }
      } catch { /* offline — keep cached/default */ }
      finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => { cancelled = true; };
  }, [apply]);

  const setFont = useCallback((key: string) => {
    apply(key);
    AsyncStorage.setItem(STORAGE_KEY, key).catch(() => {});
  }, [apply]);

  return (
    <FontFamilyContext.Provider value={{ fontKey, ready, setFont }}>
      {children}
    </FontFamilyContext.Provider>
  );
};

export const useFontFamily = () => useContext(FontFamilyContext);
