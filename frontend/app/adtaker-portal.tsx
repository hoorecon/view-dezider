/**
 * /adtaker-portal — publisher portal (AdTaker Program), Org-login rail.
 *
 * Organizations linked to a publisher record (admin sets `org_id` on the
 * publisher) see their tracker ID, widget snippets and performance here.
 * Publishers WITHOUT a login use the API Key + Secret rail instead
 * (GET /api/adtaker/self/* with X-Adtaker-Key / X-Adtaker-Secret headers).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { safeBack } from '../src/utils/navigation';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const rup = (paise: number) => `₹${((paise || 0) / 100).toFixed(2)}`;

export default function AdTakerPortal() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const [pubs, setPubs] = useState<any[]>([]);
  const [apps, setApps] = useState<any[]>([]);
  const [snipApp, setSnipApp] = useState('');

  const load = useCallback(async () => {
    try {
      const [p, store] = await Promise.all([
        api.get('/adtaker/portal/me'),
        api.get('/decider-store').catch(() => ({ data: {} })),
      ]);
      setPubs(p.data.publishers || []);
      const all = (store.data.templates || []).slice()
        .sort((a: any, b: any) => (a.kind === 'app' ? -1 : 0) - (b.kind === 'app' ? -1 : 0));
      setApps(all);
      if (all.length && !snipApp) setSnipApp(all[0].template_id);
      setErrMsg(null);
    } catch (e: any) {
      setErrMsg(e?.response?.data?.detail || 'Could not load the publisher portal.');
    } finally { setLoading(false); setRefreshing(false); }
  }, [snipApp]);
  useEffect(() => { load(); }, [load]);

  const copy = async (text: string, label: string) => {
    await Clipboard.setStringAsync(text);
    showAlert('Copied', label);
  };

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity style={s.backBtn} onPress={() => safeBack(router, '/')}>
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>Publisher Portal · AdTaker</Text>
          <Text style={s.sub}>Widgets, tracker IDs & earnings</Text>
        </View>
      </View>

      {loading ? <ActivityIndicator color="#0369A1" style={{ marginTop: 48 }} /> : errMsg ? (
        <View style={s.lockWrap}>
          <Ionicons name="globe-outline" size={40} color="#0369A1" />
          <Text style={s.lockTitle}>No publisher linked</Text>
          <Text style={s.lockMsg}>{errMsg}</Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={s.body}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
          {pubs.map((p) => (
            <View key={p.publisher_id} style={s.card}>
              <View style={s.rowHead}>
                <Text style={s.rowTitle}>{p.name}</Text>
                <View style={[s.badge, { backgroundColor: p.status === 'active' ? '#DCFCE7' : '#FEF3C7' }]}>
                  <Text style={[s.badgeText, { color: p.status === 'active' ? '#166534' : '#B45309' }]}>{String(p.status).toUpperCase()}</Text>
                </View>
              </View>
              {!!p.site_url && <Text style={s.rowSub}>{p.site_url}</Text>}

              <Text style={s.secLabel}>Tracker ID</Text>
              <TouchableOpacity style={s.trackerRow} onPress={() => copy(p.tracker_id, 'Tracker ID copied')}>
                <Text style={s.tracker}>{p.tracker_id}</Text>
                <Ionicons name="copy-outline" size={14} color="#0369A1" />
              </TouchableOpacity>
              {!!p.api_key && (
                <>
                  <Text style={s.secLabel}>API Key (secret was shown once at creation — ask admin to rotate if lost)</Text>
                  <TouchableOpacity style={s.trackerRow} onPress={() => copy(p.api_key, 'API key copied')}>
                    <Text style={s.tracker}>{p.api_key}</Text>
                    <Ionicons name="copy-outline" size={14} color="#0369A1" />
                  </TouchableOpacity>
                </>
              )}

              <Text style={s.secLabel}>Performance (last 30 days)</Text>
              <View style={s.metaRow}>
                <Text style={s.meta}>👁 {p.stats?.totals?.impressions || 0}</Text>
                <Text style={s.meta}>👆 {p.stats?.totals?.clicks || 0} ({p.stats?.ctr_pct || 0}% CTR)</Text>
                <Text style={s.meta}>✅ {p.stats?.totals?.conversions || 0} installs</Text>
                <Text style={[s.meta, { color: '#16A34A', fontWeight: '800' }]}>≈ {rup(p.stats?.earnings_estimate_paise || 0)} earned ({p.revenue_share_pct}% share)</Text>
              </View>

              <Text style={s.secLabel}>Embed a Decider App on your site</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
                {apps.map(a => (
                  <TouchableOpacity key={a.template_id} style={[s.chip, snipApp === a.template_id && s.chipOn]} onPress={() => setSnipApp(a.template_id)}>
                    <Text style={[s.chipText, snipApp === a.template_id && { color: '#FFF' }]} numberOfLines={1}>
                      {a.kind === 'app' ? '🔍 ' : ''}{a.title}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
              {!!snipApp && (
                <>
                  <View style={s.snippetBox}>
                    <Text style={s.snippet}>{`<script src="${API_URL}/api/adtaker/widget.js?tracker=${p.tracker_id}&app=${snipApp}"></script>`}</Text>
                  </View>
                  <TouchableOpacity style={s.copyBtn}
                    onPress={() => copy(`<script src="${API_URL}/api/adtaker/widget.js?tracker=${p.tracker_id}&app=${snipApp}"></script>`, 'Embed snippet copied')}>
                    <Ionicons name="copy" size={14} color="#FFF" /><Text style={s.copyText}>Copy snippet</Text>
                  </TouchableOpacity>
                </>
              )}
            </View>
          ))}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  backBtn: { padding: 4 },
  title: { fontSize: 18, fontWeight: '800', color: '#0F172A' },
  sub: { fontSize: 12, color: '#64748B', marginTop: 1 },
  body: { padding: 16, maxWidth: 760, width: '100%', alignSelf: 'center' },
  lockWrap: { alignItems: 'center', padding: 32, marginTop: 40 },
  lockTitle: { fontSize: 17, fontWeight: '800', color: '#0F172A', marginTop: 14 },
  lockMsg: { fontSize: 13, color: '#64748B', marginTop: 8, textAlign: 'center', lineHeight: 19 },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 12 },
  rowHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowTitle: { flex: 1, fontSize: 15.5, fontWeight: '800', color: '#0F172A' },
  rowSub: { fontSize: 12, color: '#64748B', marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999 },
  badgeText: { fontSize: 10, fontWeight: '900', letterSpacing: 0.4 },
  secLabel: { fontSize: 11.5, fontWeight: '800', color: '#475569', marginTop: 14, marginBottom: 5, textTransform: 'uppercase', letterSpacing: 0.3 },
  trackerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F0F9FF', borderWidth: 1, borderColor: '#BAE6FD', borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8, alignSelf: 'flex-start' },
  tracker: { fontSize: 13, fontWeight: '800', color: '#0369A1', letterSpacing: 0.4 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  meta: { fontSize: 11.5, color: '#475569', fontWeight: '600' },
  chip: { paddingVertical: 7, paddingHorizontal: 12, borderRadius: 999, backgroundColor: '#F1F5F9', marginRight: 6, maxWidth: 220 },
  chipOn: { backgroundColor: '#0369A1' },
  chipText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  snippetBox: { backgroundColor: '#0F172A', borderRadius: 10, padding: 12 },
  snippet: { color: '#7DD3FC', fontSize: 11.5, fontFamily: 'monospace' as any },
  copyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#0369A1', borderRadius: 10, paddingVertical: 10, marginTop: 8 },
  copyText: { color: '#FFF', fontSize: 13, fontWeight: '800' },
});
