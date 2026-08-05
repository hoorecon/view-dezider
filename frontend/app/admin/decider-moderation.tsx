/**
 * /admin/decider-moderation — Approve / Disapprove user-published items.
 *
 * Reads the pending queue via GET /api/admin/moderation/store and offers
 * inline actions for each item:
 *   • jAI-Verify   → POST /api/admin/moderation/{id}/approve
 *   • Disapprove   → POST /api/admin/moderation/{id}/disapprove {reason}
 *   • Reset        → POST /api/admin/moderation/{id}/reset
 *
 * Also exposes the storefront-visibility toggles (show unverified /
 * show jAI-verified) via GET|PATCH /api/admin/moderation/config.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, StyleSheet,
  ActivityIndicator, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';

interface Item {
  template_id: string;
  title: string;
  subtitle?: string;
  kind: string;
  moderation_status?: 'unverified' | 'jai_verified' | 'disapproved';
  moderation_remark?: string;
  moderation_publisher_remark?: string;
  creator_name?: string;
  publisher_type?: string;
  factor_count?: number;
  option_count?: number;
  is_public?: boolean;
}

const STATUS_META: Record<string, { label: string; color: string; bg: string }> = {
  unverified:   { label: 'Unverified',    color: '#B45309', bg: '#FEF3C7' },
  jai_verified: { label: 'jAI Verified',  color: '#059669', bg: '#D1FAE5' },
  disapproved:  { label: 'Disapproved',   color: '#DC2626', bg: '#FEE2E2' },
};
const FILTERS = ['all', 'unverified', 'jai_verified', 'disapproved'] as const;

export default function AdminDeciderModeration() {
  const router = useRouter();
  const [items, setItems] = useState<Item[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [filter, setFilter] = useState<typeof FILTERS[number]>('unverified');
  const [loading, setLoading] = useState(true);
  const [cfg, setCfg] = useState<{ show_unverified_in_store: boolean; show_jai_verified_in_store: boolean } | null>(null);

  const [disapproveTarget, setDisapproveTarget] = useState<Item | null>(null);
  const [disapproveReason, setDisapproveReason] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (filter !== 'all') params.status = filter;
      const [q, c] = await Promise.all([
        api.get('/admin/moderation/store', { params }),
        api.get('/admin/moderation/config'),
      ]);
      setItems(q.data?.items || []);
      setCounts(q.data?.counts || {});
      setCfg(c.data);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not load moderation queue');
    } finally { setLoading(false); }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const approve = async (item: Item) => {
    setBusy(item.template_id);
    try {
      await api.post(`/admin/moderation/${item.template_id}/approve`);
      await load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to approve');
    } finally { setBusy(null); }
  };

  const submitDisapprove = async () => {
    if (!disapproveTarget || !disapproveReason.trim()) {
      showAlert('Reason required', 'Please explain to the publisher what needs to change.');
      return;
    }
    setBusy(disapproveTarget.template_id);
    try {
      await api.post(`/admin/moderation/${disapproveTarget.template_id}/disapprove`, { reason: disapproveReason.trim() });
      setDisapproveTarget(null);
      setDisapproveReason('');
      await load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to disapprove');
    } finally { setBusy(null); }
  };

  const reset = async (item: Item) => {
    setBusy(item.template_id);
    try {
      await api.post(`/admin/moderation/${item.template_id}/reset`);
      await load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to reset');
    } finally { setBusy(null); }
  };

  const toggleCfg = async (key: 'show_unverified_in_store' | 'show_jai_verified_in_store') => {
    if (!cfg) return;
    const next = !cfg[key];
    try {
      const r = await api.patch('/admin/moderation/config', { [key]: next });
      setCfg(r.data);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to update config');
    }
  };

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.headerTitle}>Decider Store Moderation</Text>
      </View>

      {/* Store visibility toggles */}
      {cfg && (
        <View style={s.cfgBar}>
          <Text style={s.cfgLabel}>Show in Decider Store:</Text>
          <TouchableOpacity onPress={() => toggleCfg('show_jai_verified_in_store')} style={[s.cfgChip, cfg.show_jai_verified_in_store && s.cfgChipOn]}>
            <Ionicons name={cfg.show_jai_verified_in_store ? 'checkmark-circle' : 'ellipse-outline'} size={14} color={cfg.show_jai_verified_in_store ? '#059669' : '#64748B'} />
            <Text style={[s.cfgChipText, cfg.show_jai_verified_in_store && { color: '#059669' }]}>jAI Verified</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => toggleCfg('show_unverified_in_store')} style={[s.cfgChip, cfg.show_unverified_in_store && s.cfgChipOn]}>
            <Ionicons name={cfg.show_unverified_in_store ? 'checkmark-circle' : 'ellipse-outline'} size={14} color={cfg.show_unverified_in_store ? '#B45309' : '#64748B'} />
            <Text style={[s.cfgChipText, cfg.show_unverified_in_store && { color: '#B45309' }]}>Unverified</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Filter chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.filterBar} contentContainerStyle={{ gap: 6, paddingHorizontal: 12, alignItems: 'center' }}>
        {FILTERS.map((f) => (
          <TouchableOpacity key={f} style={[s.filterChip, filter === f && s.filterChipOn]} onPress={() => setFilter(f)} testID={`mod-filter-${f}`}>
            <Text style={[s.filterChipText, filter === f && s.filterChipTextOn]}>
              {f === 'all' ? 'All' : (STATUS_META[f]?.label || f)}
              {counts[f] !== undefined ? `  ${counts[f]}` : ''}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 12, gap: 10 }}>
        {loading && <ActivityIndicator color={COLORS.primary} />}
        {!loading && items.length === 0 && (
          <Text style={s.empty}>No items in this queue.</Text>
        )}
        {items.map((it) => {
          const st = it.moderation_status || 'unverified';
          const meta = STATUS_META[st] || STATUS_META.unverified;
          return (
            <View key={it.template_id} style={s.card}>
              <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
                <View style={{ flex: 1 }}>
                  <Text style={s.cardTitle}>{it.title}</Text>
                  <Text style={s.cardMeta}>
                    {it.kind === 'app' ? '🧩 App' : '📄 Template'} · {it.factor_count || 0} factors · {it.option_count || 0} options
                    {it.creator_name ? ` · by ${it.creator_name}` : ''} {it.publisher_type ? `(${it.publisher_type})` : ''}
                  </Text>
                </View>
                <View style={[s.badge, { backgroundColor: meta.bg }]}>
                  <Text style={[s.badgeText, { color: meta.color }]}>{meta.label}</Text>
                </View>
              </View>
              {!!it.moderation_remark && st === 'disapproved' && (
                <View style={s.remarkBox}><Text style={s.remarkLabel}>Admin remark:</Text><Text style={s.remarkText}>{it.moderation_remark}</Text></View>
              )}
              {!!it.moderation_publisher_remark && (
                <View style={[s.remarkBox, { backgroundColor: '#EFF6FF', borderColor: '#BFDBFE' }]}>
                  <Text style={[s.remarkLabel, { color: '#1D4ED8' }]}>Publisher resubmission note:</Text>
                  <Text style={[s.remarkText, { color: '#1E40AF' }]}>{it.moderation_publisher_remark}</Text>
                </View>
              )}
              <View style={s.actions}>
                {st !== 'jai_verified' && (
                  <TouchableOpacity style={[s.actBtn, s.actApprove]} onPress={() => approve(it)} disabled={busy === it.template_id} testID={`mod-approve-${it.template_id}`}>
                    <Ionicons name="checkmark-circle" size={15} color="#FFF" />
                    <Text style={s.actBtnText}>jAI-Verify</Text>
                  </TouchableOpacity>
                )}
                {st !== 'disapproved' && (
                  <TouchableOpacity style={[s.actBtn, s.actDisapprove]} onPress={() => { setDisapproveTarget(it); setDisapproveReason(''); }} disabled={busy === it.template_id}>
                    <Ionicons name="close-circle" size={15} color="#FFF" />
                    <Text style={s.actBtnText}>Disapprove</Text>
                  </TouchableOpacity>
                )}
                {st !== 'unverified' && (
                  <TouchableOpacity style={[s.actBtn, s.actReset]} onPress={() => reset(it)} disabled={busy === it.template_id}>
                    <Ionicons name="refresh" size={15} color="#FFF" />
                    <Text style={s.actBtnText}>Reset</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          );
        })}
      </ScrollView>

      {/* Disapprove modal */}
      <Modal visible={!!disapproveTarget} transparent animationType="fade" onRequestClose={() => setDisapproveTarget(null)}>
        <View style={s.modalOverlay}>
          <View style={s.modalBox}>
            <Text style={s.modalTitle}>Disapprove — reason for publisher</Text>
            <Text style={s.modalSubtitle}>This note will be shown to the publisher on their Mine tab so they can revise and resubmit.</Text>
            <TextInput
              style={s.modalInput}
              value={disapproveReason}
              onChangeText={setDisapproveReason}
              multiline
              placeholder="e.g. Add clearer expected values on the top-3 factors and re-submit."
              placeholderTextColor={COLORS.textMuted}
              testID="disapprove-reason"
            />
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <TouchableOpacity style={[s.actBtn, s.actReset, { flex: 1 }]} onPress={() => setDisapproveTarget(null)}>
                <Text style={s.actBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.actBtn, s.actDisapprove, { flex: 2 }]} onPress={submitDisapprove}>
                <Ionicons name="close-circle" size={15} color="#FFF" />
                <Text style={s.actBtnText}>Confirm disapprove</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F1F5F9' },
  header: { flexDirection: 'row', gap: 10, padding: 14, backgroundColor: COLORS.primary, alignItems: 'center' },
  headerTitle: { color: '#FFF', fontSize: 16, fontWeight: '800' },
  cfgBar: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0', flexWrap: 'wrap' },
  cfgLabel: { fontSize: 12.5, fontWeight: '700', color: '#0F172A' },
  cfgChip: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC' },
  cfgChipOn: { borderColor: 'transparent', backgroundColor: '#FFFFFF' },
  cfgChipText: { fontSize: 12, fontWeight: '700', color: '#64748B' },
  filterBar: { maxHeight: 44, borderBottomWidth: 1, borderBottomColor: '#E2E8F0', backgroundColor: '#FFF' },
  filterChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: '#F1F5F9', height: 28, justifyContent: 'center', alignSelf: 'center' },
  filterChipOn: { backgroundColor: COLORS.primary },
  filterChipText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  filterChipTextOn: { color: '#FFF' },
  empty: { textAlign: 'center', color: '#64748B', paddingVertical: 40 },
  card: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, gap: 8, borderWidth: 1, borderColor: '#E2E8F0' },
  cardTitle: { fontSize: 14.5, fontWeight: '800', color: '#0F172A' },
  cardMeta: { fontSize: 11.5, color: '#64748B', marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999 },
  badgeText: { fontSize: 10.5, fontWeight: '800' },
  remarkBox: { padding: 8, borderRadius: 8, backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA' },
  remarkLabel: { fontSize: 11, fontWeight: '800', color: '#B91C1C', marginBottom: 2 },
  remarkText: { fontSize: 12.5, color: '#7F1D1D', lineHeight: 17 },
  actions: { flexDirection: 'row', gap: 6, flexWrap: 'wrap', marginTop: 4 },
  actBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8 },
  actApprove: { backgroundColor: '#059669' },
  actDisapprove: { backgroundColor: '#DC2626' },
  actReset: { backgroundColor: '#6B7280' },
  actBtnText: { color: '#FFF', fontWeight: '800', fontSize: 12 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 20 },
  modalBox: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, gap: 10 },
  modalTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A' },
  modalSubtitle: { fontSize: 12, color: '#64748B' },
  modalInput: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, fontSize: 13.5, minHeight: 80, textAlignVertical: 'top', borderWidth: 1, borderColor: '#E2E8F0' },
});
