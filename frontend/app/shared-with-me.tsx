import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, ActivityIndicator, RefreshControl, Platform, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { COLORS } from '../src/constants/colors';

interface ShareItem {
  token: string;
  module: string;
  module_label: string;
  decision_id: string;
  title: string;
  owner_name: string;
  channel: string;
  created_at: string;
}

const MODULE_ICON: Record<string, string> = {
  dezider: 'git-branch',
  pros_cons: 'swap-horizontal',
  swot: 'grid',
  solution_finder: 'compass',
};

export default function SharedWithMe() {
  const router = useRouter();
  const [items, setItems] = useState<ShareItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      // Process any share captured before the user logged in / signed up.
      const pending = await AsyncStorage.getItem('pending_share_token');
      if (pending) {
        try { await api.post(`/shares/${pending}/accept`); } catch { /* ignore */ }
        await AsyncStorage.removeItem('pending_share_token');
      }
      const res = await api.get('/shares/shared-with-me');
      setItems(res.data?.items || []);
    } catch (e: any) {
      showAlert('Error', 'Could not load shared reports.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

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

  const renderItem = ({ item }: { item: ShareItem }) => (
    <View style={s.card}>
      <View style={s.iconWrap}>
        <Ionicons name={(MODULE_ICON[item.module] || 'document-text') as any} size={20} color={COLORS.primary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={s.title} numberOfLines={2}>{item.title}</Text>
        <Text style={s.meta} numberOfLines={1}>{item.module_label} · Shared by {item.owner_name}</Text>
      </View>
      <TouchableOpacity style={s.dlBtn} onPress={() => download(item)} disabled={downloading === item.token}>
        {downloading === item.token
          ? <ActivityIndicator size="small" color="#fff" />
          : <><Ionicons name="download" size={15} color="#fff" /><Text style={s.dlTxt}>Open</Text></>}
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={s.safe} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.back}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={s.hTitle}>Shared with me</Text>
        <View style={{ width: 22 }} />
      </View>
      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : items.length === 0 ? (
        <View style={s.center}>
          <Ionicons name="share-social-outline" size={48} color={COLORS.textMuted} />
          <Text style={s.emptyTitle}>No shared reports yet</Text>
          <Text style={s.emptySub}>When someone shares a decision report with you, it appears here to view and download.</Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => i.token}
          renderItem={renderItem}
          contentContainerStyle={{ padding: 16, gap: 12 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        />
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: COLORS.border },
  back: { padding: 2 },
  hTitle: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 10 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 6 },
  emptySub: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', lineHeight: 19 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#fff', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: COLORS.border },
  iconWrap: { width: 40, height: 40, borderRadius: 10, backgroundColor: COLORS.primary + '15', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 14.5, fontWeight: '700', color: COLORS.textPrimary },
  meta: { fontSize: 12, color: COLORS.textMuted, marginTop: 3 },
  dlBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 9, borderRadius: 9 },
  dlTxt: { color: '#fff', fontSize: 13, fontWeight: '700' },
});
