/**
 * Central font catalogue. Keep `key` values in sync with the backend
 * ALLOWED_FONTS list in routes/app_appearance.py.
 *
 * `webStack`  — the CSS font-family stack applied on web (browser renders all
 *               weights from a single family, matching jelcos.ai).
 * `googleHref`— Google Fonts CSS2 URL (web only; omitted for System).
 * `nativeFamily` — best-effort family name for native (only Inter is bundled
 *               today; others gracefully fall back to the system font).
 */
import { Platform } from 'react-native';

export interface FontOption {
  key: string;
  label: string;
  webStack: string;
  googleHref?: string;
  nativeFamily?: string;
}

const SYSTEM_WEB_STACK =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji"';

export const DEFAULT_FONT_KEY = 'Inter';

export const FONT_OPTIONS: FontOption[] = [
  { key: 'System', label: 'System default', webStack: SYSTEM_WEB_STACK },
  {
    key: 'Inter',
    label: 'Inter (recommended)',
    webStack: `'Inter', ${SYSTEM_WEB_STACK}`,
    googleHref: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap',
    nativeFamily: 'Inter',
  },
  {
    key: 'Roboto',
    label: 'Roboto',
    webStack: `'Roboto', ${SYSTEM_WEB_STACK}`,
    googleHref: 'https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&display=swap',
  },
  {
    key: 'Poppins',
    label: 'Poppins',
    webStack: `'Poppins', ${SYSTEM_WEB_STACK}`,
    googleHref: 'https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap',
  },
  {
    key: 'Plus Jakarta Sans',
    label: 'Plus Jakarta Sans',
    webStack: `'Plus Jakarta Sans', ${SYSTEM_WEB_STACK}`,
    googleHref: 'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap',
  },
  {
    key: 'Hind',
    label: 'Hind',
    webStack: `'Hind', ${SYSTEM_WEB_STACK}`,
    googleHref: 'https://fonts.googleapis.com/css2?family=Hind:wght@400;500;600;700&display=swap',
  },
  {
    key: 'Noto Sans Devanagari',
    label: 'Noto Sans Devanagari (Regional)',
    webStack: `'Noto Sans Devanagari', ${SYSTEM_WEB_STACK}`,
    googleHref: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap',
  },
  {
    key: 'JetBrains Mono',
    label: 'JetBrains Mono',
    webStack: `'JetBrains Mono', ui-monospace, monospace`,
    googleHref: 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap',
  },
];

export function getFontOption(key?: string | null): FontOption {
  return FONT_OPTIONS.find((f) => f.key === key) || FONT_OPTIONS.find((f) => f.key === DEFAULT_FONT_KEY)!;
}

export const SUPPORTS_DYNAMIC_FONT = Platform.OS === 'web';
