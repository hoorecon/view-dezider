/**
 * Catch-all short URL router — /tps, /sangamam, /launch, whatever.
 *
 * Expo Router picks concrete files (app/quiz.tsx, app/tools/, app/admin/, etc.)
 * before this dynamic segment, so this file only fires for previously-unmatched
 * single-segment paths. We ping /api/lp/{slug}: if a landing page exists we
 * render its HTML/CSS/JS on web (dangerouslySetInnerHTML) or in a WebView on
 * native. Otherwise we render the standard "Unmatched Route" screen.
 */
import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ActivityIndicator, ScrollView,
  Platform, TouchableOpacity,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';

const API = (process.env.EXPO_PUBLIC_BACKEND_URL || '') + '/api';

type LP = {
  slug: string;
  title: string;
  html: string;
  css: string;
  js: string;
  meta_description?: string;
  meta_og_image?: string;
  active?: boolean;
};

// Slugs that must NEVER be treated as landing pages even if the URL survives
// the router fallback (defence-in-depth against DB rows created before the
// backend reserved-slug check landed).
const NEVER_MATCH = new Set([
  'admin','api','auth','quiz','tools','prr','pricing','contact','legal',
  'p','embed','decider-store','journal','profile','home','solution-box',
  'whatsapp-verify','trash','subscription-plans','test123','settings',
  'docs','about','dashboard','index','share','shared','favicon.ico',
]);

export default function PromoSlugScreen() {
  const router = useRouter();
  const { promo } = useLocalSearchParams<{ promo?: string }>();
  const slug = String(promo || '').toLowerCase();

  const [state, setState] = useState<'loading' | 'found' | 'not_found'>('loading');
  const [lp, setLp] = useState<LP | null>(null);

  useEffect(() => {
    if (!slug || NEVER_MATCH.has(slug)) { setState('not_found'); return; }
    axios.get(`${API}/lp/${encodeURIComponent(slug)}`)
      .then((r) => { setLp(r.data as LP); setState('found'); })
      .catch(() => setState('not_found'));
  }, [slug]);

  // Web-only: patch <title>, <meta name="description">, and injected CSS on
  // the actual document so the LP behaves like a real landing page for SEO
  // and social-share unfurls (og:image inherited from meta_og_image).
  useEffect(() => {
    if (Platform.OS !== 'web' || !lp) return;
    try {
      if (lp.title) document.title = lp.title;
      const meta = (name: string, content: string) => {
        if (!content) return;
        let el = document.querySelector(`meta[name="${name}"]`) as HTMLMetaElement | null;
        if (!el) { el = document.createElement('meta'); el.setAttribute('name', name); document.head.appendChild(el); }
        el.setAttribute('content', content);
      };
      const ogMeta = (prop: string, content: string) => {
        if (!content) return;
        let el = document.querySelector(`meta[property="${prop}"]`) as HTMLMetaElement | null;
        if (!el) { el = document.createElement('meta'); el.setAttribute('property', prop); document.head.appendChild(el); }
        el.setAttribute('content', content);
      };
      meta('description', lp.meta_description || '');
      ogMeta('og:title', lp.title);
      ogMeta('og:description', lp.meta_description || '');
      if (lp.meta_og_image) ogMeta('og:image', lp.meta_og_image);

      // Inject CSS into a dedicated style tag we own (idempotent).
      const styleId = `lp-css-${lp.slug}`;
      let styleEl = document.getElementById(styleId) as HTMLStyleElement | null;
      if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = styleId;
        document.head.appendChild(styleEl);
      }
      styleEl.textContent = lp.css || '';

      // Inject JS if provided (rare — most LPs are static).
      if (lp.js) {
        const scriptId = `lp-js-${lp.slug}`;
        const existing = document.getElementById(scriptId);
        if (existing) existing.remove();
        const s = document.createElement('script');
        s.id = scriptId;
        s.text = lp.js;
        document.body.appendChild(s);
      }
    } catch { /* ignore SSR/DOM issues */ }
  }, [lp]);

  if (state === 'loading') {
    return (
      <SafeAreaView style={styles.center}>
        <ActivityIndicator color="#7C3AED" />
      </SafeAreaView>
    );
  }

  if (state === 'not_found') {
    return (
      <SafeAreaView style={styles.center}>
        <Text style={styles.notFoundTitle}>Unmatched Route</Text>
        <Text style={styles.notFoundSub}>Page &quot;/{slug}&quot; could not be found.</Text>
        <View style={{ flexDirection: 'row', gap: 16, marginTop: 24 }}>
          <TouchableOpacity onPress={() => router.replace('/' as any)} style={styles.linkBtn}>
            <Text style={styles.linkT}>Go home</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => router.replace('/quiz' as any)} style={styles.linkBtn}>
            <Text style={styles.linkT}>Take the free quiz</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // Found — render HTML on web via dangerouslySetInnerHTML.
  if (Platform.OS === 'web' && lp) {
    // NOTE: We deliberately DO NOT wrap the injected HTML in a react-native
    // <View>. On React Native Web the root <View> gets `flex:1` + the app
    // shell locks `body { overflow: hidden; height: 100vh }`, which clips
    // any admin-authored landing page taller than the viewport (the /tps
    // Business Model Chooser callout was invisible for this exact reason).
    // Instead we render a plain block-level <div> and force body/html to
    // regain natural document scroll while this page is mounted.
    return (
      <>
        {React.createElement('style', { key: 'lp-scroll-unlock' }, `
          html { overflow: auto !important; height: auto !important; }
          body { overflow: visible !important; height: auto !important; position: static !important; }
          #root { position: static !important; height: auto !important; min-height: 100vh; display: block !important; overflow: visible !important; }
          #root > div,
          #root .css-view-g5y9jx { height: auto !important; min-height: 100vh; overflow: visible !important; flex: none !important; display: block !important; position: static !important; }
        `)}
        {React.createElement('div', {
          key: 'lp-body',
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML: { __html: lp.html },
          style: { minHeight: '100vh', background: '#F8FAFC' },
        })}
      </>
    );
  }

  // Native fallback — render raw text (unlikely users hit this; short-URL
  // marketing pages are almost always visited from a web browser).
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#fff' }}>
      <ScrollView contentContainerStyle={{ padding: 20 }}>
        <Text style={{ fontSize: 22, fontWeight: '800', marginBottom: 12 }}>{lp?.title || slug}</Text>
        <Text style={{ fontSize: 14, color: '#334155', lineHeight: 22 }}>{lp?.meta_description || 'Open this page in a browser for the full experience.'}</Text>
        <TouchableOpacity onPress={() => router.push('/auth/register' as any)} style={[styles.linkBtn, { marginTop: 24, backgroundColor: '#7C3AED' }]}>
          <Text style={[styles.linkT, { color: '#fff' }]}>Book Your Spot</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#000', minHeight: '100vh' as any },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: '#0F172A' },
  notFoundTitle: { fontSize: 32, fontWeight: '800', color: '#fff', marginTop: 8 },
  notFoundSub: { fontSize: 14, color: '#94A3B8', marginTop: 8 },
  linkBtn: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 8, backgroundColor: '#334155' },
  linkT: { color: '#fff', fontWeight: '700' },
});
