import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl, Platform, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect } from 'expo-router';
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

const MODULE_ICON: Record<string, string> = {
  dezider: 'git-branch',
  pros_cons: 'swap-horizontal',
  swot: 'grid',
  solution_finder: 'compass',
};

export default function SharedWithMeTab() {
  const [items, setItems] = useState<ShareItem[]>([]);
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
      const res = await api.get('/shares/shared-with-me');
      setItems(res.data?.items || []);
    } catch {
      showAlert('Error', 'Could not load shared reports.');
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

  const renderItem = ({ item }: { item: ShareItem }) => {
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
        <Text style={s.hSub}>Reports others shared with you</Text>
      </View>
      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(i) => i.token}
          renderItem={renderItem}
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
  hSub: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
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
  dlTxt: { color: '#fff', fontSize: 13, fontWeight: '700' },
});
