/**
 * /admin/crawler-embed-docs — DEO + Partner crawler embed reference
 *
 * Three-tab in-app docs for:
 *   • Embed Script  — static markup + JS snippet sites can drop in
 *   • Admin Guide   — DEO/Embed Console operating instructions
 *   • Partner Guide — partner-side usage of Import URL / Deep Import
 *
 * Wrapped by app/admin/_layout.tsx (admin auth + AdminShell).
 */
import React, { useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { showAlert } from '../../src/utils/alert';

type TabKey = 'embed' | 'admin' | 'partner';

const PRIMARY = '#7C3AED';
const INK = '#0F172A';
const MUTED = '#64748B';
const BORDER = '#E2E8F0';
const SOFT = '#F8FAFC';

const SITE_DOMAIN = 'https://dynamicdecide.com';

const ROBOTS_TXT = `# Allow Dynamic Dezider crawler (Earth Dezider Import URL / Deep Import)
User-agent: DynamicDeziderBot
Allow: /
Crawl-delay: 2

# Optional: scope to the sections you actually want analysed
# Disallow: /admin/
# Disallow: /cart/
`;

const META_TAG = `<!-- Place inside <head> on pages you want analysed -->
<meta name="dynamicdecide-bot" content="index,follow,deep-import" />
<meta name="dynamicdecide-owner" content="partner_id_or_email@yourdomain.com" />
<meta name="dynamicdecide-verify" content="DD-VERIFY-TOKEN-FROM-ADMIN-CONSOLE" />`;

const JSONLD = `<!-- Optional: helps the crawler skip irrelevant pages and rank by importance -->
<script type="application/ld+json">
{
  "@context": "https://dynamicdecide.com/schema",
  "@type": "DDSitemap",
  "owner": "partner_id_or_email@yourdomain.com",
  "primary_decision": "${SITE_DOMAIN}/products",
  "include": [
    "${SITE_DOMAIN}/products/*",
    "${SITE_DOMAIN}/reviews/*",
    "${SITE_DOMAIN}/specs/*"
  ],
  "exclude": [
    "${SITE_DOMAIN}/account/*",
    "${SITE_DOMAIN}/cart/*"
  ],
  "factors_hint": ["price", "warranty", "rating", "availability"]
}
</script>`;

const JS_EMBED = `<!-- Lightweight runtime ping (~3KB, async, non-blocking) -->
<script async src="${SITE_DOMAIN}/embed/dd-crawler.js"
        data-owner="partner_id_or_email@yourdomain.com"
        data-verify="DD-VERIFY-TOKEN-FROM-ADMIN-CONSOLE"
        data-deep-import="true"
        data-factors="price,warranty,rating,availability"></script>

<!-- What it does:
     1. Registers this URL with Dynamic Dezider as a crawl-friendly source
     2. Sends a signed heartbeat so we know the page is live
     3. Streams OG/JSON-LD metadata to speed up Deep Import (cuts crawl cost ~40%)
     4. Honours Do-Not-Track + your meta tags above
     Zero PII collected. Source: https://github.com/dynamicdecide/dd-crawler-js -->`;

const HEADER_CHECK = `# Verify Dynamic Dezider crawler by IP + signed header
# All requests come from:    crawler.dynamicdecide.com (resolves via reverse DNS)
# Every request carries:     X-DD-Signature: sha256=<hmac of url + ts>
#                            X-DD-Owner: partner_id_or_email@yourdomain.com
#                            User-Agent: DynamicDeziderBot/1.0 (+${SITE_DOMAIN}/bot)
# Reject anything that fails reverse DNS or HMAC verification.`;

// ──────────────────────────────────────────────────────────────────────────────
const ADMIN_GUIDE: { h: string; body: string }[] = [
  {
    h: '1.  Who this is for',
    body:
      'Use this console when you (the Admin / DEO) need to onboard a comparison site, marketplace, or partner so users can Import-URL and Deep-Import decisions from their pages without us paying full ScraperAPI cost.',
  },
  {
    h: '2.  Onboarding a new partner (5-minute flow)',
    body:
      '• Open /admin/embed-partners → click "New Partner"\n' +
      '• Fill name, allowed origins, contact email\n' +
      '• Toggle the flows you want enabled (MyDezider / Pros & Cons / Screener)\n' +
      '• Toggle "Deep Import allowed" and set their per-decision Top-N budget cap\n' +
      '• Click "Generate Verify Token" → copy and email to the partner\n' +
      '• Partner pastes the meta-tag / script (see Embed Script tab)\n' +
      '• Return to console → "Verify Now" → green check means crawler is allowed\n' +
      '• Save. They are now live.',
  },
  {
    h: '3.  ScraperAPI metering & Top-N',
    body:
      '• Every Deep Import call deducts from the partner\'s monthly ScraperAPI quota first, then falls back to platform credits.\n' +
      '• Top-N budget picker (Step 8) lets the user pick 5 / 10 / 20 / unlimited candidates.\n' +
      '• "Top By AI" badge appears on the candidates that survived the auto-rank.\n' +
      '• Admin can override quota in /admin/embed-partners → Quotas tab.',
  },
  {
    h: '4.  Free-tier OpenAI opt-in',
    body:
      '• If the partner\'s end-users tick "Allow OpenAI to use my prompts to improve their models" (in /ai-wallet), their AI calls route to OpenAI free-tier credits first.\n' +
      '• Admin can force-disable per partner if their data policy forbids it.\n' +
      '• Toggle: /admin/embed-partners → "AI Routing" → "Allow free-tier opt-in".',
  },
  {
    h: '5.  Loader Music slots',
    body:
      '• /admin/appearance → Loader Music section.\n' +
      '• Slots: deep_import_loader, top_5_loader, assess_all_loader, mpps_loader, url_import_loader.\n' +
      '• 30MB per slot, base64-stored in Mongo, default volume configurable per platform (web/ios/android).\n' +
      '• Users can pre-mute via the speaker chip on Step 8 / Step 9. Mute is persisted in AsyncStorage.',
  },
  {
    h: '6.  Troubleshooting',
    body:
      '• Crawler 403 → check robots.txt and the meta verify token\n' +
      '• Empty Deep Import results → partner may have JS-rendered content; toggle "Use ScraperAPI render" on the partner row\n' +
      '• Quota exhausted → /admin/embed-partners → Quotas tab → "Grant burst"\n' +
      '• Verify Now stuck "pending" → ask partner to clear CDN cache for their homepage',
  },
];

const PARTNER_GUIDE: { h: string; body: string }[] = [
  {
    h: '1.  What you get',
    body:
      '• A white-label /embed/* console where your users can build decisions from any URL on your site\n' +
      '• Deep Import: we crawl two hops deep and extract factors (price, rating, warranty, etc.) automatically\n' +
      '• Top-N ranker so big result sets stay within budget\n' +
      '• Optional loader music + your branding colours',
  },
  {
    h: '2.  One-time setup',
    body:
      '• Receive your Verify Token from the Admin (see Embed Script tab)\n' +
      '• Paste the <meta> tags on every page you want analysed\n' +
      '• (Optional) Drop the JS snippet for faster Deep Import + heartbeat\n' +
      '• Update /robots.txt to allow "DynamicDeziderBot"\n' +
      '• Email admin@dynamicdecide.com → they\'ll click "Verify Now" → you\'re live',
  },
  {
    h: '3.  Using Import URL on your decisions',
    body:
      '• In any decision, Step 2 → "Import URL" → paste a page from your verified domain\n' +
      '• Pick "Deep Import" if you want the crawler to follow links\n' +
      '• Choose Top-N (5 / 10 / 20 / All) — pricier crawls deduct from your monthly quota\n' +
      '• Loader will play your branded music (mute via the speaker icon top-right)',
  },
  {
    h: '4.  Quotas, billing & metering',
    body:
      '• Your ScraperAPI quota is in /partner/usage (or ask Admin)\n' +
      '• Each Deep Import call = 1 ScraperAPI hit per candidate page\n' +
      '• Top-N caps protect you from runaway crawls\n' +
      '• Overflow falls back to platform credits (billable at 1.3× cost)',
  },
  {
    h: '5.  Free-tier OpenAI (optional, cheaper)',
    body:
      '• If you tick "Allow OpenAI to use my prompts" in /ai-wallet, factor extraction routes to OpenAI free-tier first → 0 credits used\n' +
      '• Your data is sent to OpenAI for model training (per their TOS)\n' +
      '• Disable any time — falls back to AI Wallet credits seamlessly',
  },
  {
    h: '6.  Support',
    body:
      '• Email: partners@dynamicdecide.com\n' +
      '• Status: https://status.dynamicdecide.com\n' +
      '• Docs: ' + SITE_DOMAIN + '/admin/crawler-embed-docs',
  },
];

// ──────────────────────────────────────────────────────────────────────────────
function CodeBlock({ title, code }: { title: string; code: string }) {
  const copy = async () => {
    try {
      await Clipboard.setStringAsync(code);
      showAlert('Copied', `${title} copied to clipboard.`);
    } catch (e) {
      showAlert('Error', 'Copy failed — try selecting manually.');
    }
  };
  return (
    <View style={styles.codeBlockWrap}>
      <View style={styles.codeBlockHeader}>
        <Text style={styles.codeBlockTitle}>{title}</Text>
        <TouchableOpacity style={styles.copyBtn} onPress={copy} activeOpacity={0.7}>
          <Ionicons name="copy-outline" size={14} color="#FFF" />
          <Text style={styles.copyBtnText}>Copy</Text>
        </TouchableOpacity>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator>
        <Text style={styles.codeBlock} selectable>{code}</Text>
      </ScrollView>
    </View>
  );
}

function GuideBlock({ items }: { items: { h: string; body: string }[] }) {
  return (
    <View>
      {items.map((it, idx) => (
        <View key={idx} style={styles.guideRow}>
          <Text style={styles.guideH}>{it.h}</Text>
          <Text style={styles.guideBody}>{it.body}</Text>
        </View>
      ))}
    </View>
  );
}

export default function CrawlerEmbedDocs() {
  const [tab, setTab] = useState<TabKey>('embed');

  const tabs: { k: TabKey; l: string; icon: string }[] = useMemo(
    () => [
      { k: 'embed',   l: 'Embed Script',     icon: 'code-slash' },
      { k: 'admin',   l: 'Admin Guidelines', icon: 'shield-checkmark' },
      { k: 'partner', l: 'Partner Guidelines', icon: 'people' },
    ],
    [],
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.headerCard}>
        <View style={styles.headerRow}>
          <View style={styles.headerIcon}>
            <Ionicons name="git-network" size={22} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerTitle}>Crawler Embed & Partner Console Docs</Text>
            <Text style={styles.headerSub}>
              Drop-in snippets for sites that prefer to be crawled, plus operating guides for DEO Admins and Embed Partners.
            </Text>
          </View>
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabsRow}>
        {tabs.map(t => (
          <TouchableOpacity
            key={t.k}
            testID={`tab-${t.k}`}
            style={[styles.tabBtn, tab === t.k && styles.tabBtnActive]}
            onPress={() => setTab(t.k)}
            activeOpacity={0.7}
          >
            <Ionicons name={t.icon as any} size={16} color={tab === t.k ? '#FFF' : MUTED} />
            <Text style={[styles.tabLabel, tab === t.k && styles.tabLabelActive]}>{t.l}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Embed tab */}
      {tab === 'embed' && (
        <View>
          <Text style={styles.sectionLead}>
            Sites that <Text style={{ fontWeight: '700' }}>want</Text> to be crawled by Dynamic Dezider can use any of the
            snippets below. You can pick (a) static markup, (b) the lightweight JS, or (c) both for maximum compatibility.
          </Text>

          <Text style={styles.sectionHead}>(a)  Static markup — zero JS</Text>
          <CodeBlock title="robots.txt" code={ROBOTS_TXT} />
          <CodeBlock title="<meta> tags (paste into <head>)" code={META_TAG} />
          <CodeBlock title="JSON-LD sitemap hint (optional, speeds Deep Import)" code={JSONLD} />

          <Text style={styles.sectionHead}>(b)  Lightweight runtime script (~3KB async)</Text>
          <CodeBlock title="dd-crawler.js embed" code={JS_EMBED} />

          <Text style={styles.sectionHead}>(c)  How to verify the crawler is genuine</Text>
          <CodeBlock title="Reverse-DNS + HMAC header check" code={HEADER_CHECK} />

          <View style={styles.callout}>
            <Ionicons name="information-circle" size={18} color={PRIMARY} />
            <Text style={styles.calloutText}>
              The <Text style={{ fontWeight: '700' }}>Verify Token</Text> is generated per partner in{' '}
              <Text style={{ fontWeight: '700' }}>/admin/embed-partners</Text>. Replace
              <Text style={{ fontFamily: Platform.select({ web: 'monospace', default: 'Courier' }) }}> DD-VERIFY-TOKEN-FROM-ADMIN-CONSOLE </Text>
              with the real token before publishing.
            </Text>
          </View>
        </View>
      )}

      {/* Admin tab */}
      {tab === 'admin' && (
        <View>
          <Text style={styles.sectionLead}>
            Admin / DEO operating guide for the Crawler Embed Console and Import-URL / Deep-Import features.
          </Text>
          <GuideBlock items={ADMIN_GUIDE} />
        </View>
      )}

      {/* Partner tab */}
      {tab === 'partner' && (
        <View>
          <Text style={styles.sectionLead}>
            Share this with your embed partners. Walks them through setup, usage, quotas, and the free-tier OpenAI opt-in.
          </Text>
          <GuideBlock items={PARTNER_GUIDE} />
          <View style={styles.callout}>
            <Ionicons name="document-text" size={18} color={PRIMARY} />
            <Text style={styles.calloutText}>
              A copy of this page is publicly accessible at <Text style={{ fontWeight: '700' }}>{SITE_DOMAIN}/admin/crawler-embed-docs</Text>{' '}
              for partner reference (no auth required for the partner-tab content if you choose to expose it later).
            </Text>
          </View>
        </View>
      )}

      <View style={{ height: 48 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: SOFT },
  content: { padding: 16, maxWidth: 1100, alignSelf: 'stretch', width: '100%' },

  headerCard: {
    backgroundColor: '#FFF',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: BORDER,
    marginBottom: 12,
  },
  headerRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  headerIcon: {
    width: 40, height: 40, borderRadius: 10, backgroundColor: PRIMARY,
    alignItems: 'center', justifyContent: 'center',
  },
  headerTitle: { fontSize: 17, fontWeight: '700', color: INK, marginBottom: 4 },
  headerSub: { fontSize: 13, color: MUTED, lineHeight: 18 },

  tabsRow: { flexDirection: 'row', gap: 8, marginBottom: 16, flexWrap: 'wrap' },
  tabBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 8, borderWidth: 1, borderColor: BORDER, backgroundColor: '#FFF',
  },
  tabBtnActive: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  tabLabel: { fontSize: 13, fontWeight: '600', color: MUTED },
  tabLabelActive: { color: '#FFF' },

  sectionLead: { fontSize: 14, color: INK, marginBottom: 14, lineHeight: 20 },
  sectionHead: { fontSize: 14, fontWeight: '700', color: INK, marginTop: 14, marginBottom: 8 },

  codeBlockWrap: {
    backgroundColor: '#0F172A',
    borderRadius: 10,
    marginBottom: 10,
    overflow: 'hidden',
  },
  codeBlockHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 8,
    backgroundColor: '#1E293B',
  },
  codeBlockTitle: { color: '#E2E8F0', fontSize: 12, fontWeight: '600' },
  copyBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 6, backgroundColor: PRIMARY,
  },
  copyBtnText: { color: '#FFF', fontSize: 11, fontWeight: '600' },
  codeBlock: {
    padding: 12,
    color: '#E2E8F0',
    fontFamily: Platform.select({ web: 'monospace', default: 'Courier' }),
    fontSize: 12,
    lineHeight: 18,
  },

  guideRow: {
    backgroundColor: '#FFF',
    borderRadius: 10,
    padding: 14,
    borderWidth: 1,
    borderColor: BORDER,
    marginBottom: 10,
  },
  guideH: { fontSize: 14, fontWeight: '700', color: INK, marginBottom: 6 },
  guideBody: { fontSize: 13, color: '#334155', lineHeight: 20 },

  callout: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    backgroundColor: '#F5F3FF', borderColor: '#DDD6FE', borderWidth: 1,
    borderRadius: 10, padding: 12, marginTop: 14,
  },
  calloutText: { flex: 1, fontSize: 12, color: '#5B21B6', lineHeight: 18 },
});
