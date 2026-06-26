/**
 * Admin → Payouts (Collaboration Epic Phase E).
 * Configure marketplace payout policy (min threshold, weekly schedule, platform
 * commission, RazorpayX account number), trigger a manual run, and review payouts.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Switch, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

// Save a base64 xlsx — browser download on web, share sheet on native.
async function saveBase64Xlsx(filename: string, b64: string) {
  const mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  if (Platform.OS === 'web') {
    const byteChars = atob(b64);
    const bytes = new Uint8Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) bytes[i] = byteChars.charCodeAt(i);
    const blob = new Blob([bytes], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    return;
  }
  const uri = `${FileSystem.cacheDirectory}${filename}`;
  await FileSystem.writeAsStringAsync(uri, b64, { encoding: 'base64' as any });
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(uri, { mimeType: mime, dialogTitle: filename });
  }
}

export default function AdminPayoutsScreen() {
  const router = useRouter();
  const [cfg, setCfg] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [channel, setChannel] = useState<'razorpayx' | 'manual_idfc'>('manual_idfc');
  const [payouts, setPayouts] = useState<any[]>([]);
  const [pending, setPending] = useState<any[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);

  const load = useCallback(async () => {
    try {
      const [c, p, a] = await Promise.all([
        api.get('/admin/payouts/config'),
        api.get('/admin/payouts'),
        api.get('/admin/payouts/audit-log'),
      ]);
      setCfg(c.data); setPayouts(p.data?.payouts || []); setPending(p.data?.pending_balances || []);
      setAuditLog(a.data?.items || []);
    } catch { /* noop */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const update = (patch: any) => setCfg({ ...cfg, ...patch });

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put('/admin/payouts/config', {
        min_payout_inr: parseInt(String(cfg.min_payout_inr) || '0', 10),
        payout_weekday: cfg.payout_weekday,
        payout_hour_utc: parseInt(String(cfg.payout_hour_utc) || '0', 10),
        platform_commission_percent: parseInt(String(cfg.platform_commission_percent) || '0', 10),
        enabled: cfg.enabled,
        razorpayx_account_number: cfg.razorpayx_account_number || '',
        idfc_debit_account_number: cfg.idfc_debit_account_number || '',
      });
      setCfg(r.data); showAlert('Saved', 'Payout configuration updated.');
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Save failed'); }
    finally { setSaving(false); }
  };

  const runBatch = async () => {
    setRunning(true);
    let summary: any = {};
    try {
      const s = await api.get('/admin/payouts/eligible-summary');
      summary = s.data || {};
    } catch { /* show generic copy if summary fails */ }
    setRunning(false);

    const isRzx = channel === 'razorpayx';
    const who = summary.eligible != null
      ? `${summary.eligible} eligible seller(s) · ₹${summary.total_inr ?? 0} total`
      : 'all eligible sellers above the threshold';
    const title = isRzx ? 'Run a RazorpayX batch?' : 'Create a Manual-IDFC batch?';
    const msg = isRzx
      ? `This sends REAL payouts via RazorpayX to ${who}. This cannot be undone.${summary.razorpayx_active === false ? '\n\n⚠️ RazorpayX is NOT active — this will abort.' : ''}`
      : `This only QUEUES rows (pending_manual) for ${who}. No money moves until you pay via IDFC net-banking and mark them paid.`;

    showAlert(title, msg, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: isRzx ? 'Send RazorpayX' : 'Queue Manual',
        style: isRzx ? 'destructive' : 'default',
        onPress: async () => {
          setRunning(true);
          try {
            const r = await api.post('/admin/payouts/run', { channel });
            if (isRzx) {
              showAlert('RazorpayX batch complete', `Processed ${r.data.processed ?? 0}, queued ${r.data.queued_pending ?? 0}, skipped ${r.data.skipped ?? 0}.`);
            } else {
              showAlert('Manual batch created', `Queued ${r.data.created ?? 0} payout(s): ${r.data.bank ?? 0} bank, ${r.data.upi ?? 0} UPI. Skipped ${r.data.skipped ?? 0}.`);
            }
            load();
          } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Run failed'); }
          finally { setRunning(false); }
        },
      },
    ]);
  };

  const downloadExport = async (kind: 'bank' | 'upi') => {
    setBusy(kind);
    try {
      const r = await api.get(`/admin/payouts/export/${kind}`);
      if (!r.data?.count) { showAlert('Nothing to export', `No pending ${kind === 'bank' ? 'bank' : 'UPI'} payouts. Create a batch first.`); return; }
      if (kind === 'bank' && !r.data.debit_account_set) {
        showAlert('Tip', 'Set your IDFC debit account number in Configuration so the file is ready to upload.');
      }
      await saveBase64Xlsx(r.data.filename, r.data.content_base64);
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Export failed'); }
    finally { setBusy(null); }
  };

  const markAllPaid = async () => {
    showAlert('Mark all as paid?', `This marks all ${pendingManual.length} pending manual payout(s) as PROCESSED. Do this only after you have actually transferred the money via IDFC.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Mark paid', onPress: async () => {
        setBusy('markpaid');
        try {
          const r = await api.post('/admin/payouts/mark-paid', {});
          showAlert('Done', `${r.data.marked_paid} payout(s) marked as paid.`);
          load();
        } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
        finally { setBusy(null); }
      } },
    ]);
  };

  if (loading || !cfg) return (
    <SafeAreaView style={styles.container} edges={['top']}><ActivityIndicator style={{ marginTop: 60 }} color="#16A34A" /></SafeAreaView>
  );

  const pendingManual = payouts.filter((p) => p.status === 'pending_manual');

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#16A34A', '#15803D']} style={styles.header}>
        <TouchableOpacity style={styles.iconHdr} onPress={() => safeBack(router)}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={styles.headerTitle}>Payouts</Text>
        <View style={{ width: 38 }} />
      </LinearGradient>

      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 50 }}>
        {/* RazorpayX status */}
        <View style={[styles.statusCard, { backgroundColor: cfg.razorpayx_active ? '#F0FDF4' : '#FFF7ED', borderColor: cfg.razorpayx_active ? '#BBF7D0' : '#FED7AA' }]}>
          <Ionicons name={cfg.razorpayx_active ? 'checkmark-circle' : 'alert-circle'} size={20} color={cfg.razorpayx_active ? '#16A34A' : '#EA580C'} />
          <Text style={[styles.statusText, { color: cfg.razorpayx_active ? '#166534' : '#9A3412' }]}>
            {cfg.razorpayx_active
              ? 'RazorpayX is active — payouts will be sent automatically.'
              : 'RazorpayX not activated. Payouts will be QUEUED (pending_manual) until you activate RazorpayX and set the account number below.'}
          </Text>
        </View>

        <Text style={styles.sectionTitle}>Configuration</Text>
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.label}>Payouts enabled</Text>
            <Switch value={!!cfg.enabled} onValueChange={(v) => update({ enabled: v })} trackColor={{ true: '#16A34A' }} />
          </View>

          <Text style={styles.label}>Minimum payout threshold (₹)</Text>
          <TextInput style={styles.input} value={String(cfg.min_payout_inr)} onChangeText={(t) => update({ min_payout_inr: t.replace(/[^0-9]/g, '') })} keyboardType="numeric" />

          <Text style={styles.label}>Platform commission (%)</Text>
          <TextInput style={styles.input} value={String(cfg.platform_commission_percent)} onChangeText={(t) => update({ platform_commission_percent: t.replace(/[^0-9]/g, '') })} keyboardType="numeric" />

          <Text style={styles.label}>Payout day</Text>
          <View style={styles.weekdayWrap}>
            {WEEKDAYS.map((w, i) => (
              <TouchableOpacity key={w} style={[styles.weekChip, cfg.payout_weekday === i && styles.weekChipActive]} onPress={() => update({ payout_weekday: i })}>
                <Text style={[styles.weekChipText, cfg.payout_weekday === i && { color: '#FFF' }]}>{w.slice(0, 3)}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.label}>Payout hour (UTC, 0-23)</Text>
          <TextInput style={styles.input} value={String(cfg.payout_hour_utc)} onChangeText={(t) => { const n = parseInt(t.replace(/[^0-9]/g, '') || '0', 10); update({ payout_hour_utc: Math.min(23, n) }); }} keyboardType="numeric" />

          <Text style={styles.label}>RazorpayX account number</Text>
          <TextInput style={styles.input} value={cfg.razorpayx_account_number || ''} onChangeText={(t) => update({ razorpayx_account_number: t })} placeholder="RazorpayX virtual account no." autoCapitalize="none" />

          <Text style={styles.label}>IDFC debit account number (for manual bulk transfer)</Text>
          <TextInput style={styles.input} value={cfg.idfc_debit_account_number || ''} onChangeText={(t) => update({ idfc_debit_account_number: t.replace(/[^0-9]/g, '') })} placeholder="Your IDFC current a/c no." keyboardType="numeric" />

          <TouchableOpacity style={styles.saveBtn} onPress={save} disabled={saving}>
            {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>Save configuration</Text>}
          </TouchableOpacity>
        </View>

        {/* Run a batch — explicit channel choice prevents accidental double-pay */}
        <Text style={styles.sectionTitle}>Run a payout batch</Text>
        <View style={styles.card}>
          <Text style={styles.label}>Channel</Text>
          <View style={styles.channelWrap}>
            <TouchableOpacity
              style={[styles.channelChip, channel === 'manual_idfc' && styles.channelChipActiveManual]}
              onPress={() => setChannel('manual_idfc')}
              testID="channel-manual-idfc"
            >
              <Ionicons name="albums" size={16} color={channel === 'manual_idfc' ? '#FFF' : '#7C3AED'} />
              <Text style={[styles.channelChipText, channel === 'manual_idfc' && { color: '#FFF' }]}>Manual-IDFC</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.channelChip, channel === 'razorpayx' && styles.channelChipActiveRzx]}
              onPress={() => setChannel('razorpayx')}
              testID="channel-razorpayx"
            >
              <Ionicons name="flash" size={16} color={channel === 'razorpayx' ? '#FFF' : '#0EA5E9'} />
              <Text style={[styles.channelChipText, channel === 'razorpayx' && { color: '#FFF' }]}>RazorpayX</Text>
            </TouchableOpacity>
          </View>
          <Text style={styles.channelHint}>
            {channel === 'manual_idfc'
              ? 'Manual-IDFC only QUEUES rows (pending_manual). No money moves until you transfer via IDFC net-banking and mark them paid.'
              : `RazorpayX sends REAL payouts immediately. ${cfg.razorpayx_active ? 'RazorpayX is active.' : '⚠️ RazorpayX is NOT active — this run will abort.'}`}
          </Text>

          <TouchableOpacity
            style={[styles.runBtn, channel === 'razorpayx' ? { backgroundColor: '#DC2626' } : { backgroundColor: '#7C3AED' }, { marginTop: 4 }]}
            onPress={runBatch}
            disabled={running}
            testID="run-batch"
          >
            {running ? <ActivityIndicator color="#FFF" /> : <><Ionicons name="play" size={18} color="#FFF" /><Text style={styles.runBtnText}>{channel === 'razorpayx' ? 'Send RazorpayX batch' : 'Queue Manual-IDFC batch'}</Text></>}
          </TouchableOpacity>
        </View>

        {/* Manual payouts via IDFC bank file / on-screen UPI */}
        <Text style={styles.sectionTitle}>Manual payouts (IDFC)</Text>
        <View style={styles.card}>
          <Text style={styles.helpText}>
            Pay sellers directly from your IDFC current account — no aggregator needed.
            {'\n'}1. Queue a Manual-IDFC batch above (locks eligible balances).{'\n'}2. Download the file(s).{'\n'}3. Upload Bank file to IDFC Bulk Transfer; enter UPI IDs in IDFC {'"'}Bulk Pay On-Screen{'"'}.{'\n'}4. After transferring, tap {'"'}Mark all as paid{'"'}.
          </Text>

          <View style={styles.exportRow}>
            <TouchableOpacity style={[styles.exportBtn, { borderColor: '#16A34A' }]} onPress={() => downloadExport('bank')} disabled={busy === 'bank'} testID="export-bank">
              {busy === 'bank' ? <ActivityIndicator color="#16A34A" /> : <><Ionicons name="download" size={15} color="#16A34A" /><Text style={[styles.exportBtnText, { color: '#16A34A' }]}>Bank file (IDFC)</Text></>}
            </TouchableOpacity>
            <TouchableOpacity style={[styles.exportBtn, { borderColor: '#0EA5E9' }]} onPress={() => downloadExport('upi')} disabled={busy === 'upi'} testID="export-upi">
              {busy === 'upi' ? <ActivityIndicator color="#0EA5E9" /> : <><Ionicons name="download" size={15} color="#0EA5E9" /><Text style={[styles.exportBtnText, { color: '#0EA5E9' }]}>UPI list</Text></>}
            </TouchableOpacity>
          </View>

          <TouchableOpacity style={[styles.actBtn, { backgroundColor: pendingManual.length ? '#16A34A' : '#CBD5E1' }]} onPress={markAllPaid} disabled={busy === 'markpaid' || !pendingManual.length} testID="mark-all-paid">
            {busy === 'markpaid' ? <ActivityIndicator color="#FFF" /> : <><Ionicons name="checkmark-done" size={16} color="#FFF" /><Text style={styles.actBtnText}>Mark all as paid ({pendingManual.length})</Text></>}
          </TouchableOpacity>
        </View>

        {/* pending balances */}
        <Text style={styles.sectionTitle}>Pending balances ({pending.length})</Text>
        {pending.length === 0 ? <Text style={styles.empty}>No sellers with available balances.</Text> :
          pending.map((p) => (
            <View key={p.user_id} style={styles.row}>
              <Text style={styles.rowSub} numberOfLines={1}>{p.user_id}</Text>
              <Text style={styles.rowAmount}>₹{p.available_inr}</Text>
            </View>
          ))}

        {/* payouts */}
        <Text style={styles.sectionTitle}>Recent payouts ({payouts.length})</Text>
        {payouts.length === 0 ? <Text style={styles.empty}>No payouts yet.</Text> :
          payouts.map((p) => (
            <View key={p.payout_id} style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={styles.rowTitle}>₹{p.amount_inr} · {p.method?.toUpperCase()}</Text>
                <Text style={styles.rowSub}>{new Date(p.created_at).toLocaleString()}</Text>
              </View>
              <Text style={[styles.statusTag, p.status === 'processing' && { color: '#0EA5E9' }, p.status === 'pending_manual' && { color: '#F59E0B' }, p.status === 'failed' && { color: '#EF4444' }]}>{p.status}</Text>
            </View>
          ))}

        {/* audit trail */}
        <Text style={styles.sectionTitle}>Payout run audit trail ({auditLog.length})</Text>
        {auditLog.length === 0 ? <Text style={styles.empty}>No batch runs recorded yet.</Text> :
          auditLog.map((a) => {
            const oc = a.outcome === 'success' ? '#16A34A' : a.outcome === 'aborted' ? '#F59E0B' : '#EF4444';
            const paid = a.result?.created ?? a.result?.processed ?? 0;
            return (
              <View key={a.audit_id} style={styles.auditRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.auditTitle}>
                    {(a.channel === 'razorpayx' ? 'RazorpayX' : 'Manual-IDFC')} · <Text style={{ color: oc }}>{a.outcome}</Text>
                  </Text>
                  <Text style={styles.auditSub}>{a.actor_email || a.actor_user_id || 'admin'} · {new Date(a.created_at).toLocaleString()}</Text>
                  <Text style={styles.auditSub}>Eligible {a.eligible_before ?? '—'} · ₹{a.total_inr_before ?? 0} · paid/queued {paid}</Text>
                </View>
                <View style={[styles.auditDot, { backgroundColor: oc }]} />
              </View>
            );
          })}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 14 },
  iconHdr: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: '#FFF', textAlign: 'center' },
  statusCard: { flexDirection: 'row', gap: 10, borderRadius: 12, padding: 12, borderWidth: 1, marginBottom: 16 },
  statusText: { flex: 1, fontSize: 12.5, lineHeight: 18 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', marginBottom: 8, marginTop: 8 },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: '#E2E8F0' },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  label: { fontSize: 12.5, fontWeight: '700', color: '#475569', marginBottom: 6, marginTop: 12 },
  input: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A', backgroundColor: '#FAFAFA' },
  weekdayWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  weekChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, backgroundColor: '#F1F5F9' },
  weekChipActive: { backgroundColor: '#16A34A' },
  weekChipText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  saveBtn: { backgroundColor: '#16A34A', paddingVertical: 13, borderRadius: 10, alignItems: 'center', marginTop: 18 },
  saveBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  runBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 13, borderRadius: 12, marginTop: 14 },
  runBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  channelWrap: { flexDirection: 'row', gap: 10, marginTop: 4 },
  channelChip: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, borderRadius: 10, borderWidth: 1.5, borderColor: '#E2E8F0', backgroundColor: '#FFF' },
  channelChipActiveManual: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  channelChipActiveRzx: { backgroundColor: '#0EA5E9', borderColor: '#0EA5E9' },
  channelChipText: { fontSize: 13, fontWeight: '800', color: '#475569' },
  channelHint: { fontSize: 12, color: '#64748B', lineHeight: 18, marginTop: 10 },
  helpText: { fontSize: 12.5, color: '#475569', lineHeight: 19, marginBottom: 12 },
  actBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 12, borderRadius: 10, marginTop: 10 },
  actBtnText: { color: '#FFF', fontWeight: '800', fontSize: 13.5 },
  exportRow: { flexDirection: 'row', gap: 10, marginTop: 10 },
  exportBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, borderRadius: 10, borderWidth: 1.5, backgroundColor: '#FFF' },
  exportBtnText: { fontWeight: '800', fontSize: 12.5 },
  empty: { fontSize: 13, color: '#94A3B8', marginBottom: 10 },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: '#EEF2F7' },
  rowTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  rowSub: { fontSize: 11.5, color: '#64748B', flex: 1 },
  rowAmount: { fontSize: 14, fontWeight: '800', color: '#16A34A' },
  statusTag: { fontSize: 11.5, fontWeight: '700', color: '#64748B', textTransform: 'capitalize' },
  auditRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: '#EEF2F7' },
  auditTitle: { fontSize: 13.5, fontWeight: '800', color: '#0F172A' },
  auditSub: { fontSize: 11, color: '#64748B', marginTop: 2 },
  auditDot: { width: 10, height: 10, borderRadius: 5, marginLeft: 8 },
});
