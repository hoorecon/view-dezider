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
import { COMPANY, CompanyInfo } from '../constants/company';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const STORAGE_KEY = 'app_font_family_v1';
const COMPANY_KEY = 'app_company_v1';
const LINK_ID = 'app-google-font-link';

/** Merge the Admin /api/appearance payload over the static defaults. */
function buildCompany(d: any): CompanyInfo {
  if (!d) return COMPANY;
  const address = d.address || COMPANY.addressLines.join('\n');
  const addressLines = String(address).split('\n').map((s) => s.trim()).filter(Boolean);
  const website = d.website || COMPANY.website;
  const websiteUrl = /^https?:\/\//i.test(website) ? website : `https://${String(website).replace(/^\/+/, '')}`;
  const phone = d.phone || COMPANY.phone;
  const phoneDial = '+' + String(phone).replace(/[^0-9]/g, '');
  return {
    product: d.brand_name || COMPANY.product,
    tagline: d.tagline || COMPANY.tagline,
    legalName: d.legal_name || d.company_name || COMPANY.legalName,
    website,
    websiteUrl,
    email: d.email || COMPANY.email,
    phone,
    phoneDial,
    addressLines: addressLines.length ? addressLines : COMPANY.addressLines,
    addressShort: addressLines.slice(-1)[0] || COMPANY.addressShort,
    jurisdiction: COMPANY.jurisdiction,
    lastUpdated: COMPANY.lastUpdated,
    supportHours: d.support_hours || COMPANY.supportHours,
  };
}

interface FontFamilyValue {
  fontKey: string;
  companyName: string;
  company: CompanyInfo;
  logoUri: string | null;
  ready: boolean;
  setFont: (key: string) => void;
  setCompanyName: (name: string) => void;
  refreshAppearance: () => Promise<void>;
}

const FontFamilyContext = createContext<FontFamilyValue>({
  fontKey: DEFAULT_FONT_KEY,
  companyName: COMPANY.legalName,
  company: COMPANY,
  logoUri: null,
  ready: false,
  setFont: () => {},
  setCompanyName: () => {},
  refreshAppearance: async () => {},
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
  const [companyName, setCompanyNameState] = useState<string>(COMPANY.legalName);
  const [company, setCompany] = useState<CompanyInfo>(COMPANY);
  const [logoUri, setLogoUri] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const apply = useCallback((key: string) => {
    const valid = FONT_OPTIONS.some((f) => f.key === key) ? key : DEFAULT_FONT_KEY;
    setFontKey(valid);
    applyWebFont(valid);
  }, []);

  const fetchAppearance = useCallback(async () => {
    const res = await fetch(`${API_URL}/api/appearance`);
    if (!res.ok) return;
    const data = await res.json();
    apply(data?.font_family || DEFAULT_FONT_KEY);
    AsyncStorage.setItem(STORAGE_KEY, data?.font_family || DEFAULT_FONT_KEY).catch(() => {});
    const co = buildCompany(data);
    setCompany(co);
    setCompanyNameState(co.legalName);
    AsyncStorage.setItem(COMPANY_KEY, JSON.stringify(co)).catch(() => {});
    const uri = data?.has_logo ? `${API_URL}/api/appearance/logo?v=${data?.logo_version || 0}` : null;
    setLogoUri(uri);
    AsyncStorage.setItem('app_logo_uri_v1', uri || '').catch(() => {});
  }, [apply]);

  // Hydrate from cache instantly, then reconcile with the server.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cached = await AsyncStorage.getItem(STORAGE_KEY);
        if (cached && !cancelled) apply(cached);
        const cachedCo = await AsyncStorage.getItem(COMPANY_KEY);
        if (cachedCo && !cancelled) {
          try {
            const co = JSON.parse(cachedCo) as CompanyInfo;
            setCompany(co);
            setCompanyNameState(co.legalName);
          } catch { /* ignore */ }
        }
        const cachedLogo = await AsyncStorage.getItem('app_logo_uri_v1');
        if (cachedLogo && !cancelled) setLogoUri(cachedLogo || null);
      } catch { /* ignore */ }

      try {
        if (!cancelled) await fetchAppearance();
      } catch { /* offline — keep cached/default */ }
      finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => { cancelled = true; };
  }, [apply, fetchAppearance]);

  const setFont = useCallback((key: string) => {
    apply(key);
    AsyncStorage.setItem(STORAGE_KEY, key).catch(() => {});
  }, [apply]);

  const setCompanyName = useCallback((name: string) => {
    setCompanyNameState(name);
    AsyncStorage.setItem('app_company_name_v1', name).catch(() => {});
  }, []);

  return (
    <FontFamilyContext.Provider value={{ fontKey, companyName, company, logoUri, ready, setFont, setCompanyName, refreshAppearance: fetchAppearance }}>
      {children}
    </FontFamilyContext.Provider>
  );
};

export const useFontFamily = () => useContext(FontFamilyContext);
export const useCompanyName = () => useContext(FontFamilyContext).companyName;
export const useCompany = () => useContext(FontFamilyContext).company;
export const useAppLogo = () => useContext(FontFamilyContext).logoUri;
