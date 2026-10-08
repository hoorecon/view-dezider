import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl, Platform, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';
import { getLifeArea } from '../../src/constants/lifeAreas';
import ListFilterBar, { DateRangeKey, withinDateRange, decisionTypeLabel } from '../../src/components/ListFilterBar';

interface ShareItem {
  token: string;
  module: string;
  module_label: string;
  decision_id: string;
  title: string;
  owner_name: string;
  channel: string;
  life_area?: string | null;
  decision_type?: string | null;
  created_at: string;
}

interface SharedStepItem {
  id: string;
  decision_id: string;
  owner_id: string;
  owner_name: string;
  step_number: number;
  decision_title: string;
  decision_context: string;
  merge_mode: string;
  message: string;
  recipients: any[];
  status: string;
  created_at: string;
  module?: string;
  step_access?: string;
}

const MODULE_ICON: Record<string, string> = {
  dezider: 'git-branch',
  pros_cons: 'swap-horizontal',
  swot: 'grid',
  solution_finder: 'compass',
  decision: 'git-branch',
};

const STEP_NAMES: Record<number, string> = {
  1: 'Context & Options', 2: 'Define Factors & Criteria', 3: 'Classify Factors',
  4: 'Prioritize Factors', 5: 'Calculate Ratings', 6: 'Define Options',
  7: 'Assess & Calculate', 8: 'Results Summary', 9: 'Reflection', 10: 'Final Notes',
};

export default function SharedWithMeTab() {
  const router = useRouter();
  const [section, setSection] = useState<'steps' | 'reports'>('steps');
  const [items, setItems] = useState<ShareItem[]>([]);
  const [stepItems, setStepItems] = useState<SharedStepItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);

  // filters
  const [search, setSearch] = useState('');
  const [dateRange, setDateRange] = useState<DateRangeKey>('all');
  const [lifeArea, setLifeArea] = useState<string | null>(null);
  const [decisionType, setDecisionType] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const pending = await AsyncStorage.getItem('pending_share_token');
      if (pending) {
        try { await api.post(`/shares/${pending}/accept`); } catch { /* ignore */ }
        await AsyncStorage.removeItem('pending_share_token');
      }
      const [repRes, stepRes] = await Promise.allSettled([
        api.get('/shares/shared-with-me'),
        api.get('/shared-steps/received'),
      ]);

      if (repRes.status === 'fulfilled') {
        setItems(repRes.value.data?.items || []);
      }
      if (stepRes.status === 'fulfilled') {
        setStepItems(Array.isArray(stepRes.value.data) ? stepRes.value.data : []);
      }
    } catch {
      showAlert('Error', 'Could not load shared items.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));
  useEffect(() => { load(); }, [load]);

  const availableLifeAreas = useMemo(
    () => Array.from(new Set(items.map((i) => i.life_area).filter(Boolean))) as string[],
    [items],
  );
  const availableDecisionTypes = useMemo(
    () => Array.from(new Set(items.map((i) => i.decision_type).filter(Boolean))) as string[],
    [items],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((it) => {
      if (q && !(`${it.title} ${it.owner_name}`.toLowerCase().includes(q))) return false;
      if (lifeArea && it.life_area !== lifeArea) return false;
      if (decisionType && it.decision_type !== decisionType) return false;
      if (!withinDateRange(it.created_at, dateRange)) return false;
      return true;
    });
  }, [items, search, lifeArea, decisionType, dateRange]);

  const filteredStepItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return stepItems;
    return stepItems.filter(
      (st) =>
        st.decision_title?.toLowerCase().includes(q) ||
        st.owner_name?.toLowerCase().includes(q) ||
        (STEP_NAMES[st.step_number] || '').toLowerCase().includes(q)
    );
  }, [stepItems, search]);

  const download = useCallback(async (item: ShareItem) => {
    setDownloading(item.token);
    try {
      const base = (process.env.EXPO_PUBLIC_BACKEND_URL || '') + `/api/shares/${item.token}/report.pdf`;
      const token = await AsyncStorage.getItem('session_token');
      const resp = await fetch(base, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!resp.ok) { const t = await resp.text(); throw new Error(t || 'Download failed'); }
      const blob = await resp.blob();
      if (Platform.OS === 'web') {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `jelcos_${item.module}_${item.decision_id.slice(0, 8)}.pdf`;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1500);
      } else {
        const reader = new FileReader();
        reader.onloadend = () => Linking.openURL(reader.result as string);
        reader.readAsDataURL(blob);
      }
    } catch (e: any) {
      showAlert('Download failed', e?.message || 'Try again later.');
    } finally {
      setDownloading(null);
    }
  }, []);

  const openSharedStep = (stepItem: SharedStepItem) => {
    const access = stepItem.step_access || 'readonly';
    const mod = stepItem.module || 'decision';
    const qs = `contribShareId=${stepItem.id}&contribStep=${stepItem.step_number}&access=${access}`;
    if (mod === 'decision') {
      router.push(`/prr/${stepItem.decision_id}?${qs}` as any);
      return;
    }
    if (mod === 'pros_cons') {
      router.push(`/tools/pros-cons-wizard?id=${stepItem.decision_id}&${qs}` as any);
    } else if (mod === 'solution_finder') {
      router.push(`/tools/solution-finder?id=${stepItem.decision_id}&${qs}` as any);
    }
  };

  const renderStepItem = ({ item }: { item: SharedStepItem }) => {
    const isContributed = item.recipients?.some((r: any) => r.status === 'contributed');
    const isReadOnly = item.step_access === 'readonly';

    return (
      <TouchableOpacity
        style={s.card}
        activeOpacity={0.7}
        onPress={() => openSharedStep(item)}
      >
        <View style={s.iconWrap}>
          <Ionicons name="git-branch" size={20} color={COLORS.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.title} numberOfLines={2}>
            {item.decision_title || 'Untitled Decision'}
          </Text>
          <Text style={s.meta} numberOfLines={1}>
            Step {item.step_number}: {STEP_NAMES[item.step_number] || 'Step ' + item.step_number} · Shared by {item.owner_name}
          </Text>
          <View style={s.tagRow}>
            <View style={[s.tag, { backgroundColor: isContributed ? '#10B98118' : '#F59E0B18' }]}>
              <Ionicons
                name={isContributed ? 'checkmark-circle' : 'time-outline'}
                size={11}
                color={isContributed ? '#10B981' : '#F59E0B'}
              />
              <Text style={[s.tagTxt, { color: isContributed ? '#10B981' : '#D97706' }]}>
                {isContributed ? 'Contributed' : 'Pending Review'}
              </Text>
            </View>
            <View style={[s.tag, { backgroundColor: COLORS.primary + '12' }]}>
              <Ionicons name={isReadOnly ? 'eye-outline' : 'create-outline'} size={11} color={COLORS.primary} />
              <Text style={[s.tagTxt, { color: COLORS.primary }]}>
                {isReadOnly ? 'Read-only' : 'Editable'}
              </Text>
            </View>
          </View>
        </View>
        <TouchableOpacity style={s.openBtn} onPress={() => openSharedStep(item)}>
          <Ionicons name="open-outline" size={15} color="#fff" />
          <Text style={s.dlTxt}>Open</Text>
        </TouchableOpacity>
      </TouchableOpacity>
    );
  };

  const renderReportItem = ({ item }: { item: ShareItem }) => {
    const la = getLifeArea(item.life_area);
    return (
      <View style={s.card}>
        <View style={s.iconWrap}>
          <Ionicons name={(MODULE_ICON[item.module] || 'document-text') as any} size={20} color={COLORS.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.title} numberOfLines={2}>{item.title}</Text>
          <Text style={s.meta} numberOfLines={1}>{item.module_label} · Shared by {item.owner_name}</Text>
          <View style={s.tagRow}>
            {la && (
              <View style={[s.tag, { backgroundColor: la.color + '15' }]}>
                <Ionicons name={la.icon as any} size={10} color={la.color} />
                <Text style={[s.tagTxt, { color: la.color }]}>{la.short}</Text>
              </View>
            )}
            {!!item.decision_type && (
              <View style={[s.tag, { backgroundColor: COLORS.primary + '12' }]}>
                <Text style={[s.tagTxt, { color: COLORS.primary }]}>{decisionTypeLabel(item.decision_type)}</Text>
              </View>
            )}
          </View>
        </View>
        <TouchableOpacity style={s.dlBtn} onPress={() => download(item)} disabled={downloading === item.token}>
          {downloading === item.token
            ? <ActivityIndicator size="small" color="#fff" />
            : <><Ionicons name="download" size={15} color="#fff" /><Text style={s.dlTxt}>Open</Text></>}
        </TouchableOpacity>
      </View>
    );
  };

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      <View style={s.header}>
        <Text style={s.hTitle}>Shared with me</Text>
        <Text style={s.hSub}>Collaboration steps and reports shared with you</Text>

        {/* Section Tabs */}
        <View style={s.tabBar}>
          <TouchableOpacity
            style={[s.tabBtn, section === 'steps' && s.tabBtnActive]}
            onPress={() => setSection('steps')}
          >
            <Ionicons
              name="git-network-outline"
              size={15}
              color={section === 'steps' ? '#fff' : COLORS.textSecondary}
            />
            <Text style={[s.tabBtnText, section === 'steps' && s.tabBtnTextActive]}>
              Shared Steps ({stepItems.length})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[s.tabBtn, section === 'reports' && s.tabBtnActive]}
            onPress={() => setSection('reports')}
          >
            <Ionicons
              name="document-text-outline"
              size={15}
              color={section === 'reports' ? '#fff' : COLORS.textSecondary}
            />
            <Text style={[s.tabBtnText, section === 'reports' && s.tabBtnTextActive]}>
              Decision Reports ({items.length})
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : section === 'steps' ? (
        <FlatList
          data={filteredStepItems}
          keyExtractor={(i) => i.id}
          renderItem={renderStepItem}
          ListEmptyComponent={
            <View style={s.center}>
              <Ionicons name="git-network-outline" size={48} color={COLORS.textMuted} />
              <Text style={s.emptyTitle}>
                {stepItems.length === 0 ? 'No shared steps yet' : 'No matching steps'}
              </Text>
              <Text style={s.emptySub}>
                {stepItems.length === 0
                  ? 'When someone shares a decision step with you to review or collaborate, it will appear here.'
                  : 'Try adjusting your search filter.'}
              </Text>
            </View>
          }
          contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: 100, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(i) => i.token}
          renderItem={renderReportItem}
          ListHeaderComponent={
            items.length > 0 ? (
              <View style={{ marginBottom: 6 }}>
                <ListFilterBar
                  search={search} onSearch={setSearch}
                  dateRange={dateRange} onDateRange={setDateRange}
                  lifeArea={lifeArea} onLifeArea={setLifeArea}
                  decisionType={decisionType} onDecisionType={setDecisionType}
                  availableLifeAreas={availableLifeAreas}
                  availableDecisionTypes={availableDecisionTypes}
                  searchPlaceholder="Search shared reports…"
                />
                <Text style={s.count}>{filtered.length} of {items.length}</Text>
              </View>
            ) : null
          }
          ListEmptyComponent={
            <View style={s.center}>
              <Ionicons name="share-social-outline" size={48} color={COLORS.textMuted} />
              <Text style={s.emptyTitle}>{items.length === 0 ? 'No shared reports yet' : 'No matches'}</Text>
              <Text style={s.emptySub}>
                {items.length === 0
                  ? 'When someone shares a decision report with you, it appears here to view and download.'
                  : 'Try adjusting your search or filters.'}
              </Text>
            </View>
          }
          contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: 100, flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        />
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.background },
  header: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 8 },
  hTitle: { fontSize: 26, fontWeight: '700', color: COLORS.textPrimary },
  hSub: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2, marginBottom: 12 },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    padding: 4,
    gap: 6,
  },
  tabBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 9,
    borderRadius: 9,
  },
  tabBtnActive: {
    backgroundColor: COLORS.primary,
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.15,
    shadowRadius: 4,
    elevation: 2,
  },
  tabBtnText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  tabBtnTextActive: {
    color: '#fff',
    fontWeight: '700',
  },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 10 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 6 },
  emptySub: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', lineHeight: 19 },
  count: { fontSize: 11, color: COLORS.textMuted, marginTop: 4, marginLeft: 2 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#fff', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: COLORS.border },
  iconWrap: { width: 40, height: 40, borderRadius: 10, backgroundColor: COLORS.primary + '15', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 14.5, fontWeight: '700', color: COLORS.textPrimary },
  meta: { fontSize: 12, color: COLORS.textMuted, marginTop: 3 },
  tagRow: { flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' },
  tag: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 8 },
  tagTxt: { fontSize: 9.5, fontWeight: '700' },
  dlBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 9, borderRadius: 9 },
  openBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 9, borderRadius: 9 },
  dlTxt: { color: '#fff', fontSize: 13, fontWeight: '700' },
});
