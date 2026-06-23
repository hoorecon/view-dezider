/**
 * My Earnings & Payouts (Collaboration Epic Phase E).
 * Shows marketplace earnings, lets the seller link a UPI/bank payout account,
 * and lists earnings ledger + past payouts. Weekly auto-payout above the admin
 * minimum threshold.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { safeBack } from '../src/utils/navigation';

export default function EarningsScreen() {
  const router = useRouter();
  const [summary, setSummary] = useState<any>(null);
  const [ledger, setLedger] = useState<any[]>([]);
  const [payouts, setPayouts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [showAccount, setShowAccount] = useState(false);
  const [method, setMethod] = useState<'upi' | 'bank'>('upi');
  const [vpa, setVpa] = useState('');
  const [acctNo, setAcctNo] = useState('');
  const [ifsc, setIfsc] = useState('');
  const [benName, setBenName] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, l, p] = await Promise.all([
        api.get('/earnings/summary'),
        api.get('/earnings/ledger'),
        api.get('/earnings/payouts'),
      ]);
      setSummary(s.data); setLedger(l.data?.items || []); setPayouts(p.data?.items || []);
      const acct = s.data?.payout_account;
      if (acct) {
        setMethod(acct.method || 'upi'); setVpa(acct.vpa || '');
        setAcctNo(acct.account_number || ''); setIfsc(acct.ifsc || ''); setBenName(acct.beneficiary_name || '');
      }
    } catch { /* noop */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const saveAccount = async () => {
    if (method === 'upi' && !vpa.trim()) { showAlert('UPI required', 'Enter your UPI ID (VPA).'); return; }
    if (method === 'bank' && (!acctNo.trim() || !ifsc.trim() || !benName.trim())) { showAlert('Details required', 'Enter account number, IFSC and beneficiary name.'); return; }
    setSaving(true);
    try {
      await api.post('/earnings/payout-account', {
        method, vpa: vpa.trim(), account_number: acctNo.trim(), ifsc: ifsc.trim(), beneficiary_name: benName.trim(),
      });
      setShowAccount(false); load(); showAlert('Saved', 'Payout account linked.');
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const payoutStatusMeta = (s: string) => ({
    processing: { c: '#0EA5E9', t: 'Processing' }, processed: { c: '#16A34A', t: 'Paid' },
    pending_manual: { c: '#F59E0B', t: 'Queued' }, failed: { c: '#EF4444', t: 'Failed' },
  } as any)[s] || { c: '#64748B', t: s };

  if (loading) return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ActivityIndicator style={{ marginTop: 60 }} color="#16A34A" />
    </SafeAreaView>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#16A34A', '#15803D']} style={styles.header}>
        <TouchableOpacity style={styles.iconHdr} onPress={() => safeBack(router)}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Earnings & Payouts</Text>
        <View style={{ width: 38 }} />
      </LinearGradient>

      <ScrollView
        contentContainerStyle={{ padding: 16, paddingBottom: 50 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        {/* balance card */}
        <LinearGradient colors={['#16A34A', '#22C55E']} style={styles.balanceCard}>
          <Text style={styles.balanceLabel}>Available for payout</Text>
          <Text style={styles.balanceAmount}>₹{summary?.available_inr ?? 0}</Text>
          <View style={styles.balanceRow}>
            <Text style={styles.balanceSub}>Lifetime ₹{summary?.lifetime_inr ?? 0}</Text>
            <Text style={styles.balanceSub}>Paid out ₹{summary?.paid_out_inr ?? 0}</Text>
          </View>
        </LinearGradient>

        {/* payout schedule */}
        <View style={styles.infoCard}>
          <Ionicons name="calendar-outline" size={18} color="#16A34A" />
          <Text style={styles.infoText}>
            Auto-payout every <Text style={styles.bold}>{summary?.payout_weekday}</Text> when your balance reaches <Text style={styles.bold}>₹{summary?.min_payout_inr}</Text>.
            {summary?.eligible_for_payout ? ' You\'re eligible for the next run.' : ` Earn ₹${Math.max(0, (summary?.min_payout_inr ?? 0) - (summary?.available_inr ?? 0))} more to qualify.`}
          </Text>
        </View>

        {/* payout account */}
        <TouchableOpacity style={styles.acctCard} onPress={() => setShowAccount(true)} testID="link-payout-account">
          <View style={styles.acctIcon}><Ionicons name={summary?.has_payout_account ? 'checkmark-circle' : 'add-circle-outline'} size={22} color={summary?.has_payout_account ? '#16A34A' : '#94A3B8'} /></View>
          <View style={{ flex: 1 }}>
            <Text style={styles.acctTitle}>{summary?.has_payout_account ? 'Payout account linked' : 'Link a payout account'}</Text>
            <Text style={styles.acctSub}>
              {summary?.has_payout_account
                ? (summary.payout_account?.method === 'upi' ? `UPI · ${summary.payout_account?.vpa}` : `Bank · ****${(summary.payout_account?.account_number || '').slice(-4)}`)
                : 'Add UPI or bank to receive payouts'}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
        </TouchableOpacity>

        {/* ledger */}
        <Text style={styles.sectionTitle}>Earnings ({ledger.length})</Text>
        {ledger.length === 0 ? (
          <Text style={styles.empty}>No earnings yet. Publish paid decisions on the Marketplace to start earning.</Text>
        ) : ledger.map((e) => (
          <View key={e.entry_id} style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle} numberOfLines={1}>{e.listing_title || 'Marketplace clone'}</Text>
              <Text style={styles.rowSub}>{new Date(e.created_at).toLocaleDateString()}{e.commission_inr ? ` · −₹${e.commission_inr} fee` : ''}</Text>
            </View>
            <View style={{ alignItems: 'flex-end' }}>
              <Text style={styles.rowAmount}>+₹{e.net_inr}</Text>
              <Text style={[styles.rowStatus, e.status === 'paid_out' && { color: '#16A34A' }]}>{e.status === 'paid_out' ? 'Paid out' : 'Available'}</Text>
            </View>
          </View>
        ))}

        {/* payouts */}
        {payouts.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Payouts ({payouts.length})</Text>
            {payouts.map((p) => {
              const m = payoutStatusMeta(p.status);
              return (
                <View key={p.payout_id} style={styles.row}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.rowTitle}>₹{p.amount_inr} · {p.method?.toUpperCase()}</Text>
                    <Text style={styles.rowSub}>{new Date(p.created_at).toLocaleDateString()}{p.destination ? ` · ${p.destination}` : ''}</Text>
                  </View>
                  <View style={[styles.statusPill, { backgroundColor: m.c + '22' }]}><Text style={[styles.statusPillText, { color: m.c }]}>{m.t}</Text></View>
                </View>
              );
            })}
          </>
        )}
      </ScrollView>

      {/* link account modal */}
      <Modal visible={showAccount} transparent animationType="slide" onRequestClose={() => setShowAccount(false)}>
        <View style={styles.modalBg}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Payout account</Text>
              <TouchableOpacity onPress={() => setShowAccount(false)}><Ionicons name="close" size={24} color="#0F172A" /></TouchableOpacity>
            </View>
            <View style={styles.methodRow}>
              {(['upi', 'bank'] as const).map(m => (
                <TouchableOpacity key={m} style={[styles.methodBtn, method === m && styles.methodBtnActive]} onPress={() => setMethod(m)}>
                  <Ionicons name={m === 'upi' ? 'phone-portrait-outline' : 'business-outline'} size={18} color={method === m ? '#FFF' : '#16A34A'} />
                  <Text style={[styles.methodText, method === m && { color: '#FFF' }]}>{m === 'upi' ? 'UPI' : 'Bank'}</Text>
                </TouchableOpacity>
              ))}
            </View>
            {method === 'upi' ? (
              <>
                <Text style={styles.fieldLabel}>UPI ID (VPA)</Text>
                <TextInput style={styles.input} value={vpa} onChangeText={setVpa} placeholder="name@bank" autoCapitalize="none" />
              </>
            ) : (
              <>
                <Text style={styles.fieldLabel}>Beneficiary name</Text>
                <TextInput style={styles.input} value={benName} onChangeText={setBenName} placeholder="As per bank records" />
                <Text style={styles.fieldLabel}>Account number</Text>
                <TextInput style={styles.input} value={acctNo} onChangeText={setAcctNo} placeholder="Account number" keyboardType="numeric" />
                <Text style={styles.fieldLabel}>IFSC</Text>
                <TextInput style={styles.input} value={ifsc} onChangeText={(t) => setIfsc(t.toUpperCase())} placeholder="e.g. HDFC0001234" autoCapitalize="characters" />
              </>
            )}
            <TouchableOpacity style={styles.saveBtn} onPress={saveAccount} disabled={saving}>
              {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>Save account</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 14 },
  iconHdr: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: '#FFF', textAlign: 'center' },
  balanceCard: { borderRadius: 18, padding: 20, marginBottom: 14 },
  balanceLabel: { fontSize: 13, color: '#DCFCE7', fontWeight: '600' },
  balanceAmount: { fontSize: 38, fontWeight: '900', color: '#FFF', marginTop: 4 },
  balanceRow: { flexDirection: 'row', gap: 18, marginTop: 8 },
  balanceSub: { fontSize: 12.5, color: '#DCFCE7', fontWeight: '600' },
  infoCard: { flexDirection: 'row', gap: 10, backgroundColor: '#F0FDF4', borderRadius: 12, padding: 12, marginBottom: 12, borderWidth: 1, borderColor: '#BBF7D0' },
  infoText: { flex: 1, fontSize: 12.5, color: '#166534', lineHeight: 18 },
  bold: { fontWeight: '800' },
  acctCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: '#E2E8F0' },
  acctIcon: { width: 34, alignItems: 'center' },
  acctTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  acctSub: { fontSize: 12, color: '#64748B', marginTop: 2 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', marginBottom: 8, marginTop: 6 },
  empty: { fontSize: 13, color: '#94A3B8', marginBottom: 12, lineHeight: 18 },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#EEF2F7' },
  rowTitle: { fontSize: 14, fontWeight: '600', color: '#0F172A' },
  rowSub: { fontSize: 11.5, color: '#64748B', marginTop: 2 },
  rowAmount: { fontSize: 15, fontWeight: '800', color: '#16A34A' },
  rowStatus: { fontSize: 11, color: '#94A3B8', marginTop: 2, fontWeight: '600' },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  statusPillText: { fontSize: 11, fontWeight: '800' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 18, maxHeight: '90%' },
  sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  sheetTitle: { fontSize: 17, fontWeight: '800', color: '#0F172A' },
  methodRow: { flexDirection: 'row', gap: 10, marginBottom: 8 },
  methodBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 10, borderWidth: 1.5, borderColor: '#16A34A' },
  methodBtnActive: { backgroundColor: '#16A34A' },
  methodText: { fontSize: 14, fontWeight: '700', color: '#16A34A' },
  fieldLabel: { fontSize: 12, fontWeight: '700', color: '#475569', marginBottom: 6, marginTop: 12 },
  input: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11, fontSize: 14, color: '#0F172A', backgroundColor: '#FAFAFA' },
  saveBtn: { backgroundColor: '#16A34A', paddingVertical: 14, borderRadius: 12, alignItems: 'center', marginTop: 18 },
  saveBtnText: { color: '#FFF', fontWeight: '800', fontSize: 15 },
});
