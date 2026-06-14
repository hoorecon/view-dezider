/**
 * Action Center — central tracker for all Action Items captured across modules.
 * Filter by status / source module / ported_to. Tap to view & port to CTT or LifeStyle.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import TimestampLine from '../../src/components/TimestampLine';
import { formatDMY } from '../../src/utils/datetime';

type ActionItem = {
  action_id: string; title: string; who: string; by_when?: string|null;
  recurrence_type: string; recurrence_frequency?: string|null;
  priority: 'low'|'medium'|'high'|'urgent';
  status: string; progress_pct: number;
  source_module: string; source_label?: string|null;
  ported_to?: 'CTT'|'LIFESTYLE'|null;
};

const STATUS_FILTERS = ['all','pending','in_progress','done','blocked'];
const SOURCE_FILTERS = ['all','MYDEZIDER_MPPS','PROS_CONS','SWOT','PNA','CONFLICT_BREAKER','AIM','MANUAL'];
const PORTED_FILTERS = ['all','not_ported','CTT','LIFESTYLE'];

const PRIORITY_COLOR: Record<string,string> = { low:'#94A3B8', medium:'#3B82F6', high:'#F59E0B', urgent:'#EF4444' };
const STATUS_COLOR:   Record<string,string> = { pending:'#94A3B8', in_progress:'#3B82F6', done:'#10B981', blocked:'#EF4444', cancelled:'#A1A1AA' };
const SOURCE_LABEL:   Record<string,string> = {
  MYDEZIDER_MPPS:'My Dezider · MPPS', PROS_CONS:'Pros & Cons', SWOT:'SWOT',
  PNA:'PNA', CONFLICT_BREAKER:'Conflict Breaker', CLD:'CLD', GEM:'GEM',
  GOAL_SETTER:'Goal Setter', AALA:'AALA', AIM:'AIM · Emotional Gatekeeper', MANUAL:'Manual',
};

export default function ActionCenter() {
  const router = useRouter();
  const params = useLocalSearchParams<{ source?: string; session_id?: string }>();
  const [items, setItems] = useState<ActionItem[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string|null>(null);
  const [fStatus, setFStatus] = useState('all');
  const [fSource, setFSource] = useState('all');
  const [fPorted, setFPorted] = useState('all');

  // Auto-import banner shown after seeding from an upstream source
  // (e.g. AIM session → Action Items Planner deep-link).
  const [importBanner, setImportBanner] = useState<
    { msg: string; ctt: number; life: number } | null
  >(null);
  const importedRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q: any = {};
      if (fStatus !== 'all') q.status = fStatus;
      if (fSource !== 'all') q.source_module = fSource;
      if (fPorted === 'not_ported') q.not_ported = '1';
      else if (fPorted !== 'all') q.ported_to = fPorted;
      const qs = new URLSearchParams(q).toString();
      const [r, s] = await Promise.all([
        api.get(`/action-items${qs ? '?' + qs : ''}`),
        api.get('/action-items/stats/summary'),
      ]);
      setItems(r.data || []);
      setSummary(s.data || null);
    } catch (e) { console.warn('Action center load', e); }
    finally { setLoading(false); }
  }, [fStatus, fSource, fPorted]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  // Auto-import on deep-link from upstream sources (currently AIM).
  // Idempotent on the backend — safe to call multiple times.
  useEffect(() => {
    const src = String(params?.source || '');
    const sid = String(params?.session_id || '');
    if (src !== 'aim_session' || !sid) return;
    const key = `aim:${sid}`;
    if (importedRef.current === key) return;
    importedRef.current = key;
    (async () => {
      try {
        const r = await api.post(`/action-items/import-from-aim/${sid}`);
        const n = Number(r.data?.imported_count || 0);
        const c = Number(r.data?.ctt_count || 0);
        const l = Number(r.data?.lifestyle_count || 0);
        if (n > 0) {
          setImportBanner({
            msg: `Imported ${n} new items from your AIM session.`,
            ctt: c, life: l,
          });
        } else {
          setImportBanner({
            msg: 'AIM items are already in your planner (nothing new to import).',
            ctt: 0, life: 0,
          });
        }
        // Pre-filter to AIM so the user immediately sees what was seeded.
        setFSource('AIM');
        load();
      } catch (e: any) {
        showAlert('Import failed', e?.response?.data?.detail || 'Could not import from AIM');
      }
    })();
  }, [params?.source, params?.session_id, load]);

  const port = async (it: ActionItem, target: 'CTT'|'LIFESTYLE') => {
    if (it.ported_to) return showAlert('Already ported', `In ${it.ported_to}`);
    setSavingId(it.action_id);
    try {
      const path = target === 'CTT' ? 'port-to-ctt' : 'port-to-lifestyle';
      await api.post(`/action-items/${it.action_id}/${path}`);
      load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed');
    } finally { setSavingId(null); }
  };

  return (
    <SafeAreaView style={s.root}>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
        <View style={s.headerRow}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
            <Ionicons name="chevron-back" size={22} color="#0F172A" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.title}>Action Center</Text>
            <Text style={s.sub}>Central tracker for all Who · What · By-when items</Text>
          </View>
        </View>

        {summary && (
          <View style={s.statsRow}>
            <View style={s.statCard}><Text style={s.statN}>{summary.total || 0}</Text><Text style={s.statL}>Total</Text></View>
            <View style={s.statCard}><Text style={[s.statN,{color:'#3B82F6'}]}>{summary.by_status?.in_progress || 0}</Text><Text style={s.statL}>In Progress</Text></View>
            <View style={s.statCard}><Text style={[s.statN,{color:'#10B981'}]}>{summary.by_status?.done || 0}</Text><Text style={s.statL}>Done</Text></View>
            <View style={s.statCard}><Text style={[s.statN,{color:'#1D4ED8'}]}>{summary.by_ported?.CTT || 0}</Text><Text style={s.statL}>In CTT</Text></View>
            <View style={s.statCard}><Text style={[s.statN,{color:'#B45309'}]}>{summary.by_ported?.LIFESTYLE || 0}</Text><Text style={s.statL}>LifeStyle</Text></View>
          </View>
        )}

        {/* AIM import banner — shown after deep-linking from an AIM session. */}
        {importBanner && (
          <View style={s.banner} testID="aim-import-banner">
            <View style={s.bannerIconWrap}>
              <Ionicons name="sparkles" size={18} color="#7C3AED" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.bannerTitle}>{importBanner.msg}</Text>
              {(importBanner.ctt + importBanner.life) > 0 && (
                <Text style={s.bannerSub}>
                  Grouped: {importBanner.ctt} one-time → CTT · {importBanner.life} recurring → LifeStyle.
                  Tap → CTT / → LifeStyle on each row to confirm.
                </Text>
              )}
            </View>
            <TouchableOpacity onPress={() => setImportBanner(null)} testID="aim-import-banner-close">
              <Ionicons name="close" size={18} color="#7C3AED" />
            </TouchableOpacity>
          </View>
        )}

        {/* Filters */}
        <Text style={s.filterLabel}>Status</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipsRow}>
          {STATUS_FILTERS.map(f => (
            <TouchableOpacity key={f} style={[s.chip, fStatus === f && s.chipActive]} onPress={() => setFStatus(f)}>
              <Text style={[s.chipText, fStatus === f && { color: '#FFF' }]}>{f === 'all' ? 'All' : f.replace('_',' ')}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        <Text style={s.filterLabel}>Source</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipsRow}>
          {SOURCE_FILTERS.map(f => (
            <TouchableOpacity key={f} style={[s.chip, fSource === f && s.chipActive]} onPress={() => setFSource(f)}>
              <Text style={[s.chipText, fSource === f && { color: '#FFF' }]}>{f === 'all' ? 'All' : (SOURCE_LABEL[f] || f)}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        <Text style={s.filterLabel}>Tracking</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipsRow}>
          {PORTED_FILTERS.map(f => (
            <TouchableOpacity key={f} style={[s.chip, fPorted === f && s.chipActive]} onPress={() => setFPorted(f)}>
              <Text style={[s.chipText, fPorted === f && { color: '#FFF' }]}>
                {f === 'all' ? 'All' : f === 'not_ported' ? 'Not ported' : f === 'CTT' ? 'In CTT' : 'In LifeStyle'}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {loading ? (
          <ActivityIndicator color="#0D9488" style={{ marginVertical: 24 }} />
        ) : items.length === 0 ? (
          <View style={s.emptyBox}>
            <Ionicons name="checkmark-done-circle-outline" size={42} color="#CBD5E1" />
            <Text style={s.emptyText}>No action items match these filters.</Text>
          </View>
        ) : (
          <View style={{ marginTop: 12 }}>
            {items.map(it => (
              <View key={it.action_id} style={s.row}>
                <View style={[s.priDot, { backgroundColor: PRIORITY_COLOR[it.priority] || '#94A3B8' }]} />
                <View style={{ flex: 1 }}>
                  <Text style={s.rowTitle} numberOfLines={2}>{it.title}</Text>
                  <Text style={s.rowSource}>{SOURCE_LABEL[it.source_module] || it.source_module}{it.source_label ? ` · ${it.source_label}` : ''}</Text>
                  <TimestampLine entity={it} compact />
                  <View style={s.metaRow}>
                    {!!it.who && <Text style={s.metaText}>👤 {it.who}</Text>}
                    {!!it.by_when && <Text style={s.metaText}>📅 {formatDMY(it.by_when)}</Text>}
                    <Text style={s.metaText}>{it.recurrence_type === 'recurring' ? `🔁 ${it.recurrence_frequency}` : '⚡ one-time'}</Text>
                  </View>
                  <View style={s.tagRow}>
                    <View style={[s.tag, { backgroundColor: (STATUS_COLOR[it.status]||'#94A3B8') + '22' }]}>
                      <Text style={[s.tagText, { color: STATUS_COLOR[it.status] || '#94A3B8' }]}>{it.status}</Text>
                    </View>
                    {it.ported_to ? (
                      <View style={[s.tag, { backgroundColor: it.ported_to === 'CTT' ? '#DBEAFE' : '#FEF3C7' }]}>
                        <Ionicons name="link" size={11} color={it.ported_to === 'CTT' ? '#1D4ED8' : '#B45309'} />
                        <Text style={[s.tagText, { color: it.ported_to === 'CTT' ? '#1D4ED8' : '#B45309' }]}>
                          {it.ported_to === 'CTT' ? 'In CTT' : 'In LifeStyle'}
                        </Text>
                      </View>
                    ) : (
                      <>
                        <TouchableOpacity style={[s.smallBtn, { backgroundColor: '#DBEAFE' }]} onPress={() => port(it, 'CTT')} disabled={savingId === it.action_id}>
                          <Ionicons name="calendar" size={11} color="#1D4ED8" />
                          <Text style={[s.smallBtnText, { color: '#1D4ED8' }]}>→ CTT</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={[s.smallBtn, { backgroundColor: '#FEF3C7' }]} onPress={() => port(it, 'LIFESTYLE')} disabled={savingId === it.action_id}>
                          <Ionicons name="repeat" size={11} color="#B45309" />
                          <Text style={[s.smallBtnText, { color: '#B45309' }]}>→ LifeStyle</Text>
                        </TouchableOpacity>
                      </>
                    )}
                  </View>
                </View>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  backBtn: { padding: 6 },
  title: { fontSize: 22, fontWeight: '800', color: '#0F172A' },
  sub: { fontSize: 12, color: '#64748B', marginTop: 2 },

  statsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  statCard: { flex: 1, minWidth: 70, padding: 10, borderRadius: 10, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E2E8F0', alignItems: 'center' },
  statN: { fontSize: 18, fontWeight: '800', color: '#0F172A' },
  statL: { fontSize: 10, color: '#64748B', marginTop: 2 },

  filterLabel: { fontSize: 11, fontWeight: '700', color: '#64748B', marginTop: 10, marginBottom: 6, textTransform: 'uppercase' },
  chipsRow: { flexDirection: 'row', gap: 6, paddingRight: 16 },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#FFFFFF' },
  chipActive: { backgroundColor: '#0D9488', borderColor: '#0D9488' },
  chipText: { fontSize: 11, fontWeight: '600', color: '#0F172A' },

  emptyBox: { alignItems: 'center', padding: 30, gap: 10 },
  emptyText: { fontSize: 13, color: '#64748B' },

  row: { flexDirection: 'row', gap: 10, padding: 12, marginBottom: 8, backgroundColor: '#FFFFFF', borderRadius: 12, borderWidth: 1, borderColor: '#E2E8F0' },
  priDot: { width: 10, height: 10, borderRadius: 5, marginTop: 6 },
  rowTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  rowSource: { fontSize: 11, color: '#0D9488', fontWeight: '700', marginTop: 2 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 4 },
  metaText: { fontSize: 11, color: '#475569' },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8, alignItems: 'center' },
  tag: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  tagText: { fontSize: 10, fontWeight: '700' },
  smallBtn: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  smallBtnText: { fontSize: 10, fontWeight: '700' },
  banner: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#F5F3FF', borderRadius: 12, padding: 12, marginBottom: 12,
    borderWidth: 1, borderColor: '#DDD6FE',
  },
  bannerIconWrap: { width: 30, height: 30, borderRadius: 15, backgroundColor: '#EDE9FE', alignItems: 'center', justifyContent: 'center' },
  bannerTitle: { fontSize: 13, fontWeight: '700', color: '#5B21B6' },
  bannerSub: { fontSize: 11, color: '#6D28D9', marginTop: 2, lineHeight: 15 },
});
