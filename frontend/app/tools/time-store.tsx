/**
 * Time Store — buy back time.
 *
 * Tabs:
 *   - Audit: time-save opportunities surfaced from user's CTT + Lifestyle + Matrix
 *   - Services: org-curated solutions (from Solutions Store) priced to save N min/day
 *   - Purchases: my order history
 *   - Delegations: internal delegation inbox
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Modal, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

const TABS = [
  { id: 'audit', label: 'Audit', icon: 'analytics' },
  { id: 'services', label: 'Services', icon: 'cart' },
  { id: 'purchases', label: 'Purchases', icon: 'receipt' },
  { id: 'delegations', label: 'Delegations', icon: 'paper-plane' },
];

export default function TimeStoreScreen() {
  const router = useRouter();
  const [tab, setTab] = useState('audit');
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>(null);
  const [savePerDay, setSavePerDay] = useState(30);
  const [delegateOpen, setDelegateOpen] = useState<any>(null);
  const [delegateBody, setDelegateBody] = useState({ description: '', note: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === 'audit') {
        const r = await api.get('/time-store/time-audit');
        setData(r.data);
      } else if (tab === 'services') {
        const r = await api.get(`/time-store/services?save_minutes_per_day=${savePerDay}`);
        setData(r.data);
      } else if (tab === 'purchases') {
        const r = await api.get('/time-store/purchases');
        setData(r.data);
      } else if (tab === 'delegations') {
        const r = await api.get('/time-store/delegations');
        setData(r.data);
      }
    } catch { setData(null); }
    finally { setLoading(false); }
  }, [tab, savePerDay]);

  useEffect(() => { load(); }, [load]);

  const purchase = async (sol: any) => {
    try {
      const r = await api.post('/time-store/purchase', {
        solution_id: sol.solution_id,
        save_minutes_per_day: savePerDay,
      });
      showAlert('Order placed', `Order ${r.data.order_id}\nStatus: ${r.data.status}\n${r.data.note || ''}`);
    } catch { showAlert('Error', 'Purchase failed'); }
  };

  const submitDelegation = async () => {
    if (!delegateBody.description.trim()) { showAlert('Required', 'Describe the work'); return; }
    try {
      await api.post('/time-store/delegate', {
        source_type: delegateOpen.source_type,
        source_id: delegateOpen.source_id,
        description: delegateBody.description,
        estimated_minutes_saved: delegateOpen.minutes_saved_per_event * (delegateOpen.events_per_week || 1),
        note: delegateBody.note,
      });
      setDelegateOpen(null);
      setDelegateBody({ description: '', note: '' });
      showAlert('Delegated', 'Added to your delegation inbox.');
      setTab('delegations');
    } catch { showAlert('Error', 'Delegation failed'); }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#0891B2', '#10B981']} style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)}>
          <Ionicons name="chevron-back" size={26} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1, marginLeft: 8 }}>
          <Text style={styles.h1}>Time Store</Text>
          <Text style={styles.sub}>Buy back time · delegate · outsource</Text>
        </View>
      </LinearGradient>

      <View style={styles.tabRow}>
        {TABS.map(t => {
          const sel = t.id === tab;
          return (
            <TouchableOpacity key={t.id} onPress={() => setTab(t.id)}
              style={[styles.tab, sel && styles.tabActive]}>
              <Ionicons name={t.icon as any} size={14} color={sel ? '#FFF' : COLORS.textMuted} />
              <Text style={[styles.tabText, sel && { color: '#FFF' }]}>{t.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {loading ? (
        <ActivityIndicator size="large" color="#0891B2" style={{ marginTop: 40 }} />
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          {tab === 'audit' && (
            <View>
              <View style={styles.bigTile}>
                <Text style={styles.bigTileLabel}>Total saveable per week</Text>
                <Text style={styles.bigTileValue}>
                  {data?.total_hours_saveable_per_week ?? 0}h
                </Text>
                <Text style={styles.bigTileSub}>
                  {data?.total_minutes_saveable_per_week ?? 0} minutes across {data?.opportunities?.length || 0} opportunities
                </Text>
              </View>
              {(data?.opportunities || []).length === 0 ? (
                <Text style={styles.emptyText}>No opportunities yet. Add CTT tasks, a Lifestyle Designer plan, or flag cells in your Solution Matrix as “mundane” to unlock suggestions.</Text>
              ) : (
                (data?.opportunities || []).map((o: any) => (
                  <View key={o.opp_id} style={styles.oppCard}>
                    <View style={styles.leverChip}>
                      <Text style={styles.leverChipText}>{o.tepfi_lever}</Text>
                    </View>
                    <Text style={styles.oppTitle}>{o.title}</Text>
                    <Text style={styles.oppWhy}>{o.why}</Text>
                    <Text style={styles.oppMinutes}>
                      Save ~{o.minutes_saved_per_event * (o.events_per_week || 1)} min/week
                    </Text>
                    <View style={styles.oppActions}>
                      <TouchableOpacity style={styles.delegateBtn}
                        onPress={() => { setDelegateOpen(o); setDelegateBody({ description: o.title, note: '' }); }}>
                        <Ionicons name="paper-plane" size={14} color="#FFF" />
                        <Text style={styles.delegateBtnText}>Delegate</Text>
                      </TouchableOpacity>
                      <TouchableOpacity style={[styles.delegateBtn, { backgroundColor: '#0891B2' }]}
                        onPress={() => setTab('services')}>
                        <Ionicons name="cart" size={14} color="#FFF" />
                        <Text style={styles.delegateBtnText}>Find Service</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))
              )}
            </View>
          )}

          {tab === 'services' && (
            <View>
              <Text style={styles.sectionTitle}>How much time do you want to save per day?</Text>
              <View style={styles.bucketRow}>
                {[30, 60, 120].map(b => (
                  <TouchableOpacity key={b} onPress={() => setSavePerDay(b)}
                    style={[styles.bucket, savePerDay === b && styles.bucketActive]}>
                    <Text style={[styles.bucketText, savePerDay === b && { color: '#FFF' }]}>
                      {b < 60 ? `${b}m` : `${b / 60}h`}/day
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              {(data?.services || []).length === 0 ? (
                <Text style={styles.emptyText}>
                  No registered org services matching this save target yet.
                  Orgs can list their time-saving solutions in the Solutions Store; they'll appear here automatically.
                </Text>
              ) : (
                (data?.services || []).map((s: any) => (
                  <View key={s.solution_id} style={styles.serviceCard}>
                    <View style={styles.serviceHead}>
                      <Text style={styles.serviceTitle}>{s.title}</Text>
                      {s.price_inr != null && (
                        <Text style={styles.servicePrice}>₹ {s.price_inr}</Text>
                      )}
                    </View>
                    {s.org && (
                      <Text style={styles.serviceOrg}>by {s.org.display_name}</Text>
                    )}
                    <Text style={styles.serviceDesc} numberOfLines={3}>{s.description}</Text>
                    <View style={styles.savesRow}>
                      {s.time_save_per_day_min && (
                        <View style={styles.saveBadge}>
                          <Text style={styles.saveBadgeText}>
                            Saves ~{s.time_save_per_day_min} min/day
                          </Text>
                        </View>
                      )}
                    </View>
                    <TouchableOpacity testID={`ts-buy-${s.solution_id}`} style={styles.buyBtn} onPress={() => purchase(s)}>
                      <Ionicons name="cart" size={14} color="#FFF" />
                      <Text style={styles.buyBtnText}>Buy back time</Text>
                    </TouchableOpacity>
                  </View>
                ))
              )}
            </View>
          )}

          {tab === 'purchases' && (
            <View>
              {(data?.items || []).length === 0 ? (
                <Text style={styles.emptyText}>No purchases yet.</Text>
              ) : (
                (data?.items || []).map((p: any) => (
                  <View key={p.order_id} style={styles.serviceCard}>
                    <Text style={styles.serviceTitle}>{p.solution_title}</Text>
                    <Text style={styles.serviceOrg}>Order {p.order_id}</Text>
                    <View style={[styles.savesRow, { marginTop: 6 }]}>
                      <View style={[styles.statusBadge, {
                        backgroundColor: p.status === 'paid' ? '#ECFDF5' : '#FEF3C7',
                      }]}>
                        <Text style={[styles.statusBadgeText, {
                          color: p.status === 'paid' ? '#065F46' : '#92400E',
                        }]}>{String(p.status).toUpperCase()}</Text>
                      </View>
                      {p.payment_provider === 'mock' && (
                        <Text style={styles.mockedText}>MOCKED payment — flips to real once Razorpay keys are live</Text>
                      )}
                    </View>
                  </View>
                ))
              )}
            </View>
          )}

          {tab === 'delegations' && (
            <View>
              {(data?.items || []).length === 0 ? (
                <Text style={styles.emptyText}>No delegations yet. Use the Audit tab to delegate an opportunity.</Text>
              ) : (
                (data?.items || []).map((d: any) => (
                  <View key={d.delegation_id} style={styles.serviceCard}>
                    <Text style={styles.serviceTitle}>{d.description}</Text>
                    <Text style={styles.serviceOrg}>ID {d.delegation_id}</Text>
                    <View style={[styles.savesRow, { marginTop: 6 }]}>
                      <View style={[styles.statusBadge, { backgroundColor: '#EDE9FE' }]}>
                        <Text style={[styles.statusBadgeText, { color: '#5B21B6' }]}>{String(d.status).toUpperCase()}</Text>
                      </View>
                      <Text style={styles.mockedText}>≈ {d.estimated_minutes_saved} min saved</Text>
                    </View>
                  </View>
                ))
              )}
            </View>
          )}
        </ScrollView>
      )}

      <Modal visible={delegateOpen !== null} animationType="slide" transparent onRequestClose={() => setDelegateOpen(null)}>
        <View style={styles.modalOverlay}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>Delegate</Text>
            <Text style={styles.fieldLabel}>Description</Text>
            <TextInput style={[styles.input, { minHeight: 60 }]}
              multiline value={delegateBody.description}
              onChangeText={v => setDelegateBody({ ...delegateBody, description: v })} />
            <Text style={styles.fieldLabel}>Note (optional)</Text>
            <TextInput style={styles.input} value={delegateBody.note}
              onChangeText={v => setDelegateBody({ ...delegateBody, note: v })} />
            <View style={styles.rowEnd}>
              <TouchableOpacity onPress={() => setDelegateOpen(null)} style={styles.cancelBtn}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={submitDelegation} style={styles.saveBtn}>
                <Text style={styles.saveBtnText}>Send</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16 },
  h1: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  sub: { fontSize: 11, color: 'rgba(255,255,255,0.85)' },
  tabRow: { flexDirection: 'row', padding: 8, gap: 4, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 7, borderRadius: 8, backgroundColor: COLORS.divider },
  tabActive: { backgroundColor: '#0891B2' },
  tabText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },
  bigTile: { padding: 16, backgroundColor: '#CFFAFE', borderRadius: 14, marginBottom: 14 },
  bigTileLabel: { fontSize: 12, color: '#155E75', fontWeight: '600', textTransform: 'uppercase' },
  bigTileValue: { fontSize: 34, color: '#0E7490', fontWeight: '700', marginTop: 4 },
  bigTileSub: { fontSize: 12, color: '#155E75', marginTop: 2 },
  emptyText: { color: COLORS.textMuted, fontSize: 12, marginVertical: 20, textAlign: 'center', lineHeight: 18 },
  oppCard: { padding: 12, backgroundColor: COLORS.white, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 10 },
  leverChip: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8, backgroundColor: '#FEF3C7' },
  leverChipText: { fontSize: 10, color: '#92400E', fontWeight: '700' },
  oppTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginTop: 6 },
  oppWhy: { fontSize: 12, color: COLORS.textMuted, marginTop: 4, lineHeight: 16 },
  oppMinutes: { fontSize: 11, color: '#0E7490', fontWeight: '700', marginTop: 4 },
  oppActions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  delegateBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#10B981', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  delegateBtnText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
  sectionTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  bucketRow: { flexDirection: 'row', gap: 6, marginBottom: 14 },
  bucket: { flex: 1, paddingVertical: 10, backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  bucketActive: { backgroundColor: '#0891B2', borderColor: '#0891B2' },
  bucketText: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary },
  serviceCard: { padding: 12, backgroundColor: COLORS.white, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 10 },
  serviceHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  serviceTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, flex: 1 },
  servicePrice: { fontSize: 14, fontWeight: '700', color: '#0891B2' },
  serviceOrg: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  serviceDesc: { fontSize: 12, color: COLORS.textPrimary, marginTop: 6, lineHeight: 16 },
  savesRow: { flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap', alignItems: 'center' },
  saveBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, backgroundColor: '#DCFCE7' },
  saveBadgeText: { fontSize: 10, color: '#15803D', fontWeight: '700' },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  statusBadgeText: { fontSize: 10, fontWeight: '700' },
  mockedText: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600' },
  buyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#0891B2', paddingVertical: 10, borderRadius: 8, marginTop: 10 },
  buyBtnText: { color: '#FFF', fontWeight: '700', fontSize: 13 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.background, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16 },
  sheetTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  fieldLabel: { fontSize: 12, color: COLORS.textMuted, marginTop: 10, marginBottom: 4, fontWeight: '600' },
  input: { backgroundColor: COLORS.white, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary },
  rowEnd: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 14 },
  cancelBtn: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border },
  cancelBtnText: { color: COLORS.textPrimary, fontWeight: '600' },
  saveBtn: { backgroundColor: '#0891B2', paddingHorizontal: 18, paddingVertical: 10, borderRadius: 8 },
  saveBtnText: { color: '#FFF', fontWeight: '700' },
});
