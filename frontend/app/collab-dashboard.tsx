import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator, Alert,
} from 'react-native';
import { useLocalSearchParams, useRouter, Stack } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { COLORS } from '../src/constants/colors';
import api from '../src/utils/api';
import ReviewMergeModal from '../src/components/ReviewMergeModal';

interface FlowShare {
  id: string; step_number: number; session_mode: string; status: string;
  call_room_url?: string; merge_history?: any[]; merge_mode?: string;
  total: number; contributed: number;
  recipients: { name: string; status: string; sme?: boolean }[];
  pending: string[];
  activeCount?: number;
}

const STATUS_COLOR: Record<string, string> = {
  pending: COLORS.textMuted, opened: '#D97706', contributed: '#16A34A', merged: '#7C3AED',
};

export default function CollabDashboard() {
  const { module = 'decision', id = '', title = '' } = useLocalSearchParams<{ module?: string; id?: string; title?: string }>();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [shares, setShares] = useState<FlowShare[]>([]);
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [reviewAi, setReviewAi] = useState(false);

  const load = useCallback(async () => {
    if (!id) { setLoading(false); return; }
    try {
      const { data } = await api.get(`/shared-steps-by-flow?module=${module}&module_id=${id}`);
      const list: FlowShare[] = data.shares || [];
      // pull live presence counts in parallel (best-effort)
      await Promise.all(list.filter(s => s.session_mode === 'live_sync').map(async (s) => {
        try { const p = await api.get(`/shared-steps/${s.id}/presence`); s.activeCount = p.data?.count || 0; } catch { /* */ }
      }));
      setShares(list);
    } catch { /* */ } finally { setLoading(false); }
  }, [module, id]);

  useEffect(() => { load(); }, [load]);

  return (
    <View style={s.container}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.hTitle}>Collaboration</Text>
          <Text style={s.hSub} numberOfLines={1}>{title || 'All shared steps'}</Text>
        </View>
        <TouchableOpacity onPress={load} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="refresh" size={20} color={COLORS.textSecondary} />
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : shares.length === 0 ? (
        <View style={s.center}>
          <Ionicons name="people-outline" size={44} color={COLORS.textMuted} />
          <Text style={s.empty}>No shared steps for this flow yet.{'\n'}Share a step to invite contributors.</Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40, gap: 12 }}>
          {shares.map((sh) => (
            <View key={sh.id} style={s.card}>
              <View style={s.cardTop}>
                <View style={s.stepBadge}><Text style={s.stepBadgeTxt}>Step {sh.step_number}</Text></View>
                <View style={[s.modePill, sh.session_mode === 'live_sync' && { backgroundColor: '#ECFDF5' }]}>
                  <Ionicons name={sh.session_mode === 'live_sync' ? 'videocam' : 'time-outline'} size={12}
                    color={sh.session_mode === 'live_sync' ? '#059669' : '#64748B'} />
                  <Text style={[s.modePillTxt, sh.session_mode === 'live_sync' && { color: '#059669' }]}>
                    {sh.session_mode === 'live_sync' ? 'Live' : 'Async'}
                  </Text>
                </View>
                {sh.status === 'merged' && (
                  <View style={s.mergedPill}><Ionicons name="git-merge" size={11} color="#7C3AED" /><Text style={s.mergedTxt}>Merged</Text></View>
                )}
                <View style={{ flex: 1 }} />
                <Text style={s.respCount}>{sh.contributed}/{sh.total} responded</Text>
              </View>

              {/* recipients status chips */}
              <View style={s.chipsRow}>
                {sh.recipients.map((r, i) => (
                  <View key={i} style={[s.statusChip, { borderColor: (STATUS_COLOR[r.status] || COLORS.textMuted) + '66' }]}>
                    <View style={[s.dot, { backgroundColor: STATUS_COLOR[r.status] || COLORS.textMuted }]} />
                    <Text style={s.chipName} numberOfLines={1}>{r.name}{r.sme ? ' · SME' : ''}</Text>
                  </View>
                ))}
                {sh.pending.map((p, i) => (
                  <View key={`p${i}`} style={[s.statusChip, { borderColor: '#E5E7EB' }]}>
                    <Ionicons name="mail-outline" size={11} color={COLORS.textMuted} />
                    <Text style={s.chipName} numberOfLines={1}>{p}</Text>
                  </View>
                ))}
              </View>

              {/* live link */}
              {sh.session_mode === 'live_sync' && sh.call_room_url && (
                <View style={s.liveRow}>
                  <View style={s.activeDot} />
                  <Text style={s.activeTxt}>{sh.activeCount || 0} active now</Text>
                  <TouchableOpacity style={s.copyBtn} onPress={async () => { await Clipboard.setStringAsync(sh.call_room_url!); Alert.alert('Copied', 'Meeting link copied.'); }}>
                    <Ionicons name="copy-outline" size={13} color="#059669" />
                    <Text style={s.copyTxt}>Copy link</Text>
                  </TouchableOpacity>
                </View>
              )}

              {/* merge history */}
              {(sh.merge_history?.length || 0) > 0 && (
                <Text style={s.histLine}>
                  <Ionicons name="time-outline" size={11} color={COLORS.textMuted} />
                  {`  ${sh.merge_history!.length} merge(s) · last: ${sh.merge_history![sh.merge_history!.length - 1]?.method || 'merge'}`}
                </Text>
              )}

              {/* actions */}
              {sh.total > 0 && (
                <View style={s.actions}>
                  <TouchableOpacity style={[s.actBtn, { backgroundColor: COLORS.primary }]}
                    onPress={() => { setReviewAi(false); setReviewId(sh.id); }}>
                    <Ionicons name="git-compare-outline" size={14} color="#FFF" />
                    <Text style={s.actTxt}>Review &amp; Merge</Text>
                  </TouchableOpacity>
                  {sh.contributed > 0 && (
                    <TouchableOpacity style={[s.actBtn, { backgroundColor: '#7C3AED' }]}
                      onPress={() => { setReviewAi(true); setReviewId(sh.id); }}>
                      <Ionicons name="sparkles" size={14} color="#FFF" />
                      <Text style={s.actTxt}>AI Auto-Merge</Text>
                    </TouchableOpacity>
                  )}
                </View>
              )}
            </View>
          ))}
        </ScrollView>
      )}

      <ReviewMergeModal
        visible={!!reviewId}
        shareId={reviewId}
        autoAi={reviewAi}
        onClose={() => { setReviewId(null); setReviewAi(false); }}
        onMerged={load}
      />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingTop: 56, paddingBottom: 14, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  hTitle: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary },
  hSub: { fontSize: 12.5, color: COLORS.textSecondary, marginTop: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 30 },
  empty: { fontSize: 14, color: COLORS.textMuted, textAlign: 'center', marginTop: 12, lineHeight: 20 },
  card: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: COLORS.border, gap: 10 },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  stepBadge: { backgroundColor: '#EEF2FF', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 4 },
  stepBadgeTxt: { fontSize: 12, fontWeight: '800', color: '#4338CA' },
  modePill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#F1F5F9', borderRadius: 10, paddingHorizontal: 8, paddingVertical: 3 },
  modePillTxt: { fontSize: 11, fontWeight: '700', color: '#64748B' },
  mergedPill: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#EDE9FE', borderRadius: 10, paddingHorizontal: 7, paddingVertical: 3 },
  mergedTxt: { fontSize: 10.5, fontWeight: '700', color: '#7C3AED' },
  respCount: { fontSize: 12, fontWeight: '700', color: COLORS.textSecondary },
  chipsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  statusChip: { flexDirection: 'row', alignItems: 'center', gap: 5, borderWidth: 1, borderRadius: 14, paddingHorizontal: 9, paddingVertical: 5, maxWidth: 180 },
  dot: { width: 7, height: 7, borderRadius: 4 },
  chipName: { fontSize: 11.5, color: COLORS.textPrimary, fontWeight: '600' },
  liveRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#ECFDF5', borderRadius: 10, padding: 8 },
  activeDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#16A34A' },
  activeTxt: { fontSize: 12, fontWeight: '700', color: '#065F46', flex: 1 },
  copyBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, borderColor: '#6EE7B7', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 5, backgroundColor: '#FFF' },
  copyTxt: { fontSize: 11.5, fontWeight: '700', color: '#059669' },
  histLine: { fontSize: 11.5, color: COLORS.textMuted },
  actions: { flexDirection: 'row', gap: 8 },
  actBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 10, paddingVertical: 10 },
  actTxt: { fontSize: 13, fontWeight: '700', color: '#FFF' },
});
