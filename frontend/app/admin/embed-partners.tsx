/**
 * /admin/embed-partners — Partner Embed self-serve console (P4)
 *
 * Manage every comparison-platform partner's white-label embed:
 *   • Branding (white-label / co-brand, render mode, colors, hide "Powered by")
 *   • Enabled flows (MyDezider / Pros & Cons / Screener)
 *   • Auth (OTP required, dev-code), allowed origins
 *   • Screener pricing + dual billing
 *   • Ingestion sources + scrape legal/ToS acknowledgements (gated)
 *   • Copy embed snippet · preview the generated Partner Page
 *   • Analytics: screener runs + billing totals
 *
 * Wrapped by app/admin/_layout.tsx (admin auth + AdminShell).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const FLOWS = [
  { key: 'mydezider', label: 'MyDezider' },
  { key: 'pros_cons', label: 'Pros & Cons' },
  { key: 'screener', label: 'Screener' },
];
const PRIMARY = '#7C3AED';

const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <View style={styles.section}>
    <Text style={styles.sectionTitle}>{title}</Text>
    {children}
  </View>
);

const Toggle = ({ on, onPress, label, testID }: { on: boolean; onPress: () => void; label: string; testID?: string }) => (
  <TouchableOpacity testID={testID} style={styles.toggleRow} onPress={onPress} activeOpacity={0.7}>
    <Ionicons name={on ? 'checkbox' : 'square-outline'} size={20} color={on ? PRIMARY : '#94A3B8'} />
    <Text style={styles.toggleLabel}>{label}</Text>
  </TouchableOpacity>
);

const Seg = ({ options, value, onChange, testIDPrefix }: { options: { k: string; l: string }[]; value: string; onChange: (k: string) => void; testIDPrefix?: string }) => (
  <View style={styles.seg}>
    {options.map(o => (
      <TouchableOpacity key={o.k} testID={testIDPrefix ? `${testIDPrefix}-${o.k}` : undefined} style={[styles.segBtn, value === o.k && styles.segBtnOn]} onPress={() => onChange(o.k)}>
        <Text style={[styles.segText, value === o.k && styles.segTextOn]}>{o.l}</Text>
      </TouchableOpacity>
    ))}
  </View>
);

const Field = ({ label, value, onChange, keyboardType, placeholder, testID }: any) => (
  <View style={styles.field}>
    <Text style={styles.fieldLabel}>{label}</Text>
    <TextInput testID={testID} style={styles.input} value={String(value ?? '')} onChangeText={onChange}
      keyboardType={keyboardType} placeholder={placeholder} placeholderTextColor="#9CA3AF" autoCapitalize="none" />
  </View>
);

export default function AdminEmbedPartnersScreen() {
  const router = useRouter();
  const [partners, setPartners] = useState<any[]>([]);
  const [slug, setSlug] = useState<string | null>(null);
  const [cfg, setCfg] = useState<any | null>(null);
  const [analytics, setAnalytics] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const loadPartners = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const r = await api.get('/embed/partners');
      const list = r.data?.partners || [];
      setPartners(list);
      if (!slug && list.length) selectPartner(list[0].slug);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Failed to load partners';
      setLoadError(msg);
      // Keep the page usable — admin can still open the embed script docs even
      // when /embed/partners fails (e.g. network blip, RBAC restriction).
    } finally { setLoading(false); }
  }, []);

  const selectPartner = async (s: string) => {
    setSlug(s); setCfg(null); setAnalytics(null);
    try {
      const [c, a] = await Promise.all([
        api.get(`/embed/config/${s}`),
        api.get(`/embed/analytics/${s}`).catch(() => ({ data: null })),
      ]);
      setCfg(c.data); setAnalytics(a.data);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load config');
    }
  };

  useEffect(() => { loadPartners(); }, [loadPartners]);

  const patch = (p: any) => setCfg((c: any) => ({ ...c, ...p }));
  const patchTheme = (p: any) => setCfg((c: any) => ({ ...c, theme: { ...(c.theme || {}), ...p } }));
  const patchPricing = (p: any) => setCfg((c: any) => ({ ...c, screener_pricing: { ...(c.screener_pricing || {}), ...p } }));
  const patchIngest = (p: any) => setCfg((c: any) => ({ ...c, ingestion: { ...(c.ingestion || {}), ...p } }));
  const toggleFlow = (f: string) => setCfg((c: any) => {
    const cur = new Set(c.enabled_flows || []);
    if (cur.has(f)) cur.delete(f); else cur.add(f);
    return { ...c, enabled_flows: Array.from(cur) };
  });

  const save = async () => {
    if (!cfg || !slug) return;
    setSaving(true);
    try {
      const body = {
        allowed_origins: Array.isArray(cfg.allowed_origins) ? cfg.allowed_origins
          : String(cfg.allowed_origins || '').split(',').map((x: string) => x.trim()).filter(Boolean),
        branding_mode: cfg.branding_mode || 'white_label',
        render_mode: cfg.render_mode || 'rn_web',
        enabled_flows: cfg.enabled_flows || [],
        theme: {
          primary_color: cfg.theme?.primary_color || '#7C3AED',
          accent_color: cfg.theme?.accent_color || null,
          logo_uri: cfg.theme?.logo_uri || null,
          font_family: cfg.theme?.font_family || null,
          hide_powered_by: !!cfg.theme?.hide_powered_by,
        },
        auth_mode: cfg.otp_required ? 'otp' : 'frictionless',
        otp_required: !!cfg.otp_required,
        expose_dev_code: !!cfg.expose_dev_code,
        screener_pricing: {
          base_credits: parseFloat(cfg.screener_pricing?.base_credits) || 0,
          per_candidate: parseFloat(cfg.screener_pricing?.per_candidate) || 0,
          per_finalist: parseFloat(cfg.screener_pricing?.per_finalist) || 0,
          per_factor: parseFloat(cfg.screener_pricing?.per_factor) || 0,
          billing_mode: cfg.screener_pricing?.billing_mode || 'end_user',
        },
        ingestion: {
          api_enabled: !!cfg.ingestion?.api_enabled,
          api_endpoint: cfg.ingestion?.api_endpoint || null,
          api_auth_header: cfg.ingestion?.api_auth_header || null,
          csv_sheet_enabled: cfg.ingestion?.csv_sheet_enabled !== false,
          scrape_enabled: !!cfg.ingestion?.scrape_enabled,
          scrape_legal_ack: !!cfg.ingestion?.scrape_legal_ack,
          scrape_terms_ack: !!cfg.ingestion?.scrape_terms_ack,
          url_min_tier: cfg.ingestion?.url_min_tier || null,
        },
      };
      await api.put(`/embed/config/${slug}`, body);
      showAlert('Saved', 'Embed configuration updated.');
      selectPartner(slug);
      loadPartners();
    } catch (e: any) {
      showAlert('Could not save', e?.response?.data?.detail || 'Validation failed');
    } finally { setSaving(false); }
  };

  const snippet = slug
    ? `<script src="${API_URL}/api/embed/decision/${slug}/loader.js" data-flow="${(cfg?.enabled_flows || ['mydezider'])[0]}"></script>\n<button data-dezider-open>Help me Decide</button>`
    : '';
  const copySnippet = async () => {
    try {
      if (Platform.OS === 'web' && navigator?.clipboard) { await navigator.clipboard.writeText(snippet); showAlert('Copied', 'Embed snippet copied to clipboard.'); }
      else showAlert('Embed snippet', snippet);
    } catch { showAlert('Embed snippet', snippet); }
  };
  const openPreview = () => {
    const url = `${API_URL}/api/embed/demo-host/${slug}`;
    if (Platform.OS === 'web') window.open(url, '_blank');
    else showAlert('Preview URL', url);
  };

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color={PRIMARY} /></View>;

  return (
    <ScrollView style={styles.wrap} contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
      <View style={styles.headerRow}>
        <View style={{ flex: 1 }}>
          <Text style={styles.h1}>Partner Embed Console</Text>
          <Text style={styles.sub}>White-label embed config, pricing, snippet & analytics per partner.</Text>
        </View>
        {/* Quick link to the crawler embed scripts + Admin/Partner docs.
            Always visible so admins can hand the snippet to a partner even
            before that partner exists in the system. */}
        <TouchableOpacity
          testID="embed-open-crawler-docs-btn"
          style={styles.docsBtn}
          activeOpacity={0.85}
          onPress={() => router.push('/admin/crawler-embed-docs' as any)}>
          <Ionicons name="code-slash" size={15} color="#FFF" />
          <Text style={styles.docsBtnText}>Crawler scripts & guidelines</Text>
        </TouchableOpacity>
      </View>

      {!!loadError && (
        <View style={styles.errBox} testID="embed-load-error">
          <Ionicons name="alert-circle" size={16} color="#B91C1C" />
          <Text style={styles.errText}>Couldn't load partners — {loadError}</Text>
          <TouchableOpacity onPress={loadPartners} style={styles.retryBtn} activeOpacity={0.85}>
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Empty-state — no partners yet. Don't dead-end the admin with a forever spinner. */}
      {!loadError && partners.length === 0 && (
        <View style={styles.emptyState} testID="embed-empty-state">
          <Ionicons name="people-outline" size={36} color="#94A3B8" />
          <Text style={styles.emptyTitle}>No embed partners yet</Text>
          <Text style={styles.emptyBody}>
            Partners are created from <Text style={{ fontWeight: '700' }}>Admin → Org Members</Text> (or via
            the partner-org API). Once a partner exists, return here to configure their white-label embed,
            pricing, and ingestion settings.
          </Text>
          <View style={styles.emptyActions}>
            <TouchableOpacity
              testID="embed-empty-goto-org-members"
              style={styles.emptyPrimary}
              activeOpacity={0.85}
              onPress={() => router.push('/admin/org-members' as any)}>
              <Ionicons name="people" size={14} color="#FFF" />
              <Text style={styles.emptyPrimaryText}>Open Org Members</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="embed-empty-goto-docs"
              style={styles.emptySecondary}
              activeOpacity={0.85}
              onPress={() => router.push('/admin/crawler-embed-docs' as any)}>
              <Ionicons name="code-slash" size={14} color={PRIMARY} />
              <Text style={styles.emptySecondaryText}>View crawler scripts</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* partner picker */}
      {partners.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 14 }}>
          {partners.map(p => (
            <TouchableOpacity key={p.slug} testID={`embed-partner-tab-${p.slug}`} onPress={() => selectPartner(p.slug)}
              style={[styles.pTab, slug === p.slug && styles.pTabOn]}>
              <Text style={[styles.pTabText, slug === p.slug && { color: '#fff' }]}>{p.name}</Text>
              {p.configured && <View style={styles.dot} />}
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {partners.length > 0 && !cfg ? (
        <View style={styles.center}>
          <ActivityIndicator color={PRIMARY} />
          <Text style={{ fontSize: 12, color: '#94A3B8', marginTop: 8 }}>Loading partner config…</Text>
        </View>
      ) : null}

      {cfg ? (
        <>
          <Section title="Branding">
            <Text style={styles.fieldLabel}>Branding mode</Text>
            <Seg options={[{ k: 'white_label', l: 'White-label' }, { k: 'co_brand', l: 'Co-brand' }]}
              testIDPrefix="embed-branding-mode"
              value={cfg.branding_mode || 'white_label'} onChange={(k) => patch({ branding_mode: k })} />
            <Text style={[styles.fieldLabel, { marginTop: 12 }]}>Render mode</Text>
            <Seg options={[{ k: 'rn_web', l: 'Real app (rn_web)' }, { k: 'html_widget', l: 'HTML widget' }]}
              testIDPrefix="embed-render-mode"
              value={cfg.render_mode || 'rn_web'} onChange={(k) => patch({ render_mode: k })} />
            <View style={styles.row2}>
              <Field label="Primary color" value={cfg.theme?.primary_color} onChange={(t: string) => patchTheme({ primary_color: t })} placeholder="#7B1E3B" />
              <Field label="Accent color" value={cfg.theme?.accent_color} onChange={(t: string) => patchTheme({ accent_color: t })} placeholder="#C9A24B" />
            </View>
            <Field label="Logo URL (optional)" value={cfg.theme?.logo_uri} onChange={(t: string) => patchTheme({ logo_uri: t })} placeholder="https://…" />
            <Toggle testID="embed-hide-powered-by" on={!!cfg.theme?.hide_powered_by} onPress={() => patchTheme({ hide_powered_by: !cfg.theme?.hide_powered_by })} label="Hide “Powered by View Dezider”" />
          </Section>

          <Section title="Enabled flows">
            <View style={styles.chipRow}>
              {FLOWS.map(f => {
                const on = (cfg.enabled_flows || []).includes(f.key);
                return (
                  <TouchableOpacity key={f.key} testID={`embed-flow-chip-${f.key}`} onPress={() => toggleFlow(f.key)}
                    style={[styles.flowChip, on && { backgroundColor: PRIMARY, borderColor: PRIMARY }]}>
                    <Text style={[styles.flowChipText, on && { color: '#fff' }]}>{f.label}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </Section>

          <Section title="Authentication & origins">
            <Toggle testID="embed-otp-required" on={!!cfg.otp_required} onPress={() => patch({ otp_required: !cfg.otp_required })} label="Require WhatsApp OTP (else frictionless)" />
            <Toggle testID="embed-expose-dev-code" on={!!cfg.expose_dev_code} onPress={() => patch({ expose_dev_code: !cfg.expose_dev_code })} label="Expose dev OTP code (non-prod testing)" />
            <Field label="Allowed origins (comma-separated)"
              value={Array.isArray(cfg.allowed_origins) ? cfg.allowed_origins.join(', ') : cfg.allowed_origins}
              onChange={(t: string) => patch({ allowed_origins: t })} placeholder="pmsbazaar.com, www.pmsbazaar.com" />
          </Section>

          <Section title="Screener pricing & billing">
            <View style={styles.row2}>
              <Field label="Base credits" keyboardType="decimal-pad" value={cfg.screener_pricing?.base_credits} onChange={(t: string) => patchPricing({ base_credits: t })} />
              <Field label="Per candidate" keyboardType="decimal-pad" value={cfg.screener_pricing?.per_candidate} onChange={(t: string) => patchPricing({ per_candidate: t })} />
            </View>
            <View style={styles.row2}>
              <Field label="Per finalist" keyboardType="decimal-pad" value={cfg.screener_pricing?.per_finalist} onChange={(t: string) => patchPricing({ per_finalist: t })} />
              <Field label="Per factor" keyboardType="decimal-pad" value={cfg.screener_pricing?.per_factor} onChange={(t: string) => patchPricing({ per_factor: t })} />
            </View>
            <Text style={[styles.fieldLabel, { marginTop: 6 }]}>Billing mode</Text>
            <Seg options={[{ k: 'end_user', l: 'End user' }, { k: 'partner', l: 'Partner' }, { k: 'both', l: 'Both' }]}
              testIDPrefix="embed-billing-mode"
              value={cfg.screener_pricing?.billing_mode || 'end_user'} onChange={(k) => patchPricing({ billing_mode: k })} />
          </Section>

          <Section title="Catalogue ingestion">
            <Toggle testID="embed-ingest-csv-sheet" on={cfg.ingestion?.csv_sheet_enabled !== false} onPress={() => patchIngest({ csv_sheet_enabled: !(cfg.ingestion?.csv_sheet_enabled !== false) })} label="CSV / Google-Sheet upload" />
            <Toggle testID="embed-ingest-api" on={!!cfg.ingestion?.api_enabled} onPress={() => patchIngest({ api_enabled: !cfg.ingestion?.api_enabled })} label="Partner data API" />
            {cfg.ingestion?.api_enabled && (
              <Field label="API endpoint" value={cfg.ingestion?.api_endpoint} onChange={(t: string) => patchIngest({ api_endpoint: t })} placeholder="https://partner.com/api/catalogue" />
            )}
            <Toggle testID="embed-ingest-scrape" on={!!cfg.ingestion?.scrape_enabled} onPress={() => patchIngest({ scrape_enabled: !cfg.ingestion?.scrape_enabled })} label="Premium “paste URL” / server-side fetch" />
            {cfg.ingestion?.scrape_enabled && (
              <View style={styles.gate}>
                <Text style={styles.gateNote}>⚠️ Legal gate — both must be confirmed to save with scraping enabled:</Text>
                <Toggle testID="embed-ingest-scrape-legal-ack" on={!!cfg.ingestion?.scrape_legal_ack} onPress={() => patchIngest({ scrape_legal_ack: !cfg.ingestion?.scrape_legal_ack })} label="We have legal authority / permission to fetch this data" />
                <Toggle testID="embed-ingest-scrape-terms-ack" on={!!cfg.ingestion?.scrape_terms_ack} onPress={() => patchIngest({ scrape_terms_ack: !cfg.ingestion?.scrape_terms_ack })} label="The partner's Terms of Service permit automated access" />
              </View>
            )}
          </Section>

          <TouchableOpacity testID="embed-save-config-btn" style={[styles.saveBtn, saving && { opacity: 0.6 }]} onPress={save} disabled={saving}>
            {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveText}>Save configuration</Text>}
          </TouchableOpacity>

          <Section title="Embed snippet">
            <View style={styles.codeBox}><Text style={styles.code}>{snippet}</Text></View>
            <View style={styles.actionRow}>
              <TouchableOpacity testID="embed-copy-snippet-btn" style={styles.outlineBtn} onPress={copySnippet}>
                <Ionicons name="copy-outline" size={15} color={PRIMARY} /><Text style={styles.outlineText}>Copy snippet</Text>
              </TouchableOpacity>
              <TouchableOpacity testID="embed-preview-btn" style={styles.outlineBtn} onPress={openPreview}>
                <Ionicons name="open-outline" size={15} color={PRIMARY} /><Text style={styles.outlineText}>Preview partner page</Text>
              </TouchableOpacity>
            </View>
          </Section>

          {analytics && (
            <Section title="Analytics">
              <View style={styles.statRow}>
                <Stat label="Runs" value={analytics.totals?.runs ?? 0} />
                <Stat label="Candidates" value={analytics.totals?.candidates_ranked ?? 0} />
                <Stat label="End-user cr." value={analytics.totals?.end_user_credits ?? 0} />
                <Stat label="Partner cr." value={analytics.totals?.partner_credits ?? 0} />
              </View>
              {(analytics.recent_runs || []).slice(0, 8).map((r: any) => (
                <View key={r.id} style={styles.runRow}>
                  <Text style={styles.runTop} numberOfLines={1}>{r.top_match || '—'}</Text>
                  <Text style={styles.runMeta}>{r.candidate_count}→{r.finalists_count} · {r.cost_credits}cr · {r.billing_mode}{r.used_ai ? ' · AI' : ''}</Text>
                </View>
              ))}
              {(!analytics.recent_runs || analytics.recent_runs.length === 0) && (
                <Text style={styles.empty}>No screener runs yet for this partner.</Text>
              )}
            </Section>
          )}
        </>
      ) : null}
    </ScrollView>
  );
}

const Stat = ({ label, value }: { label: string; value: any }) => (
  <View testID={`embed-stat-${String(label).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+$/,'')}`} style={styles.stat}>
    <Text style={styles.statValue}>{value}</Text>
    <Text style={styles.statLabel}>{label}</Text>
  </View>
);

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#F8FAFC' },
  center: { padding: 40, alignItems: 'center', justifyContent: 'center' },
  h1: { fontSize: 22, fontWeight: '800', color: '#0F172A' },
  sub: { fontSize: 13, color: '#64748B', marginTop: 4 },
  pTab: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, marginRight: 8, backgroundColor: '#fff' },
  pTabOn: { backgroundColor: PRIMARY, borderColor: PRIMARY },
  pTabText: { fontSize: 13, fontWeight: '700', color: '#334155' },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: '#22C55E' },
  section: { backgroundColor: '#fff', borderRadius: 14, borderWidth: 1, borderColor: '#E5E7EB', padding: 16, marginTop: 14 },
  sectionTitle: { fontSize: 14, fontWeight: '800', color: '#0F172A', marginBottom: 12 },
  field: { flex: 1, marginBottom: 10 },
  fieldLabel: { fontSize: 12, fontWeight: '700', color: '#475569', marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 9, paddingHorizontal: 11, paddingVertical: 10, fontSize: 13.5, color: '#0F172A', backgroundColor: '#fff' },
  row2: { flexDirection: 'row', gap: 12 },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 9, paddingVertical: 7 },
  toggleLabel: { fontSize: 13.5, color: '#334155', flex: 1 },
  seg: { flexDirection: 'row', backgroundColor: '#F1F5F9', borderRadius: 10, padding: 3 },
  segBtn: { flex: 1, paddingVertical: 9, borderRadius: 8, alignItems: 'center' },
  segBtnOn: { backgroundColor: '#fff', shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 3, shadowOffset: { width: 0, height: 1 } },
  segText: { fontSize: 12.5, fontWeight: '700', color: '#64748B' },
  segTextOn: { color: PRIMARY },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  flowChip: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 18, paddingHorizontal: 16, paddingVertical: 9, backgroundColor: '#fff' },
  flowChipText: { fontSize: 13, fontWeight: '700', color: '#475569' },
  gate: { backgroundColor: '#FEF2F2', borderRadius: 10, padding: 10, marginTop: 4 },
  gateNote: { fontSize: 12, color: '#B91C1C', fontWeight: '600', marginBottom: 4 },
  saveBtn: { backgroundColor: PRIMARY, borderRadius: 12, paddingVertical: 15, alignItems: 'center', marginTop: 16 },
  saveText: { color: '#fff', fontSize: 15, fontWeight: '800' },
  codeBox: { backgroundColor: '#0F172A', borderRadius: 10, padding: 12 },
  code: { color: '#E2E8F0', fontSize: 11.5, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  actionRow: { flexDirection: 'row', gap: 10, marginTop: 12, flexWrap: 'wrap' },
  outlineBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: PRIMARY, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 9 },
  outlineText: { color: PRIMARY, fontSize: 13, fontWeight: '700' },
  statRow: { flexDirection: 'row', gap: 10, marginBottom: 8 },
  stat: { flex: 1, backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, alignItems: 'center' },
  statValue: { fontSize: 18, fontWeight: '800', color: PRIMARY },
  statLabel: { fontSize: 10.5, color: '#64748B', marginTop: 3, textAlign: 'center' },
  runRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8, borderTopWidth: 1, borderTopColor: '#F1F5F9' },
  runTop: { fontSize: 13, fontWeight: '700', color: '#1F2937', flex: 1, marginRight: 8 },
  runMeta: { fontSize: 11.5, color: '#64748B' },
  empty: { fontSize: 12.5, color: '#94A3B8', fontStyle: 'italic', marginTop: 4 },

  headerRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' },
  docsBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: PRIMARY, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10 },
  docsBtnText: { color: '#FFF', fontSize: 12.5, fontWeight: '800' },

  errBox: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FEF2F2', borderColor: '#FECACA', borderWidth: 1, borderRadius: 10, padding: 12, marginTop: 14 },
  errText: { flex: 1, fontSize: 12.5, color: '#991B1B', fontWeight: '600' },
  retryBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: '#DC2626' },
  retryText: { color: '#FFF', fontSize: 12, fontWeight: '800' },

  emptyState: { alignItems: 'center', backgroundColor: '#FFF', borderColor: '#E2E8F0', borderWidth: 1, borderRadius: 12, padding: 24, marginTop: 16 },
  emptyTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A', marginTop: 10 },
  emptyBody: { fontSize: 12.5, color: '#475569', textAlign: 'center', lineHeight: 18, marginTop: 6, maxWidth: 520 },
  emptyActions: { flexDirection: 'row', gap: 10, marginTop: 14, flexWrap: 'wrap', justifyContent: 'center' },
  emptyPrimary: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: PRIMARY, paddingHorizontal: 14, paddingVertical: 9, borderRadius: 10 },
  emptyPrimaryText: { color: '#FFF', fontSize: 12.5, fontWeight: '800' },
  emptySecondary: { flexDirection: 'row', alignItems: 'center', gap: 6, borderColor: PRIMARY, borderWidth: 1, paddingHorizontal: 14, paddingVertical: 9, borderRadius: 10, backgroundColor: '#FFF' },
  emptySecondaryText: { color: PRIMARY, fontSize: 12.5, fontWeight: '800' },
});
