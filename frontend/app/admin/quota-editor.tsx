/**
 * Admin · Edit User Report Allocation  (/admin/quota-editor)
 *
 * Locate a user by email + mobile, then correct their remaining (LEFT) report
 * quota per SKU. Authorized by a WhatsApp OTP sent to the Super Admin. The
 * target user is notified (WhatsApp + email) with the stated reason.
 *
 * Permission: Super Admin, or an Admin granted `can_edit_quota`.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';
import { showAlert } from '../../src/utils/alert';

interface SkuRow { sku_code: string; name: string; granted: number; consumed: number; balance: number; }
interface FoundUser { user_id: string; name?: string; email?: string; mobile_masked?: string; whatsapp_verified?: boolean; }
interface AdminGrant { user_id: string; email: string; name?: string; can_edit_quota: boolean; }

export default function AdminQuotaEditorScreen() {
  const router = useRouter();
  const [perm, setPerm] = useState<{ can_edit_quota: boolean; role: string } | null>(null);
  const [boot, setBoot] = useState(true);

  // lookup
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [lookupBusy, setLookupBusy] = useState(false);
  const [found, setFound] = useState<FoundUser | null>(null);
  const [skus, setSkus] = useState<SkuRow[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  // otp / apply
  const [otpInfo, setOtpInfo] = useState<{ sent_to_masked: string } | null>(null);
  const [otp, setOtp] = useState('');
  const [reason, setReason] = useState('');
  const [activeSku, setActiveSku] = useState<string | null>(null);
  const [applyBusy, setApplyBusy] = useState(false);

  // super-admin grants
  const [grants, setGrants] = useState<AdminGrant[]>([]);
  const [grantEmail, setGrantEmail] = useState('');

  const loadPerm = useCallback(async () => {
    setBoot(true);
    try {
      const r = await api.get('/admin/quota/permission');
      setPerm(r.data);
      if (r.data?.role === 'super_admin') {
        const g = await api.get('/admin/quota/grants').catch(() => ({ data: { admins: [] } }));
        setGrants(g.data?.admins || []);
      }
    } catch {
      setPerm({ can_edit_quota: false, role: '' });
    } finally {
      setBoot(false);
    }
  }, []);

  useEffect(() => { loadPerm(); }, [loadPerm]);

  const errMsg = (e: any, fb: string) => {
    const m = e?.response?.data?.detail || e?.message || fb;
    return typeof m === 'string' ? m : JSON.stringify(m);
  };

  const doLookup = async () => {
    if (!email.trim() || !mobile.trim()) { showAlert('Required', 'Enter both email and mobile.'); return; }
    setLookupBusy(true);
    setFound(null); setSkus([]); setOtpInfo(null); setOtp(''); setActiveSku(null);
    try {
      const r = await api.post('/admin/quota/lookup', { email: email.trim(), mobile: mobile.trim() });
      setFound(r.data.user);
      setSkus(r.data.skus || []);
      const d: Record<string, string> = {};
      (r.data.skus || []).forEach((s: SkuRow) => { d[s.sku_code] = String(s.balance); });
      setDrafts(d);
    } catch (e: any) {
      showAlert('Lookup failed', errMsg(e, 'Could not find user'));
    } finally {
      setLookupBusy(false);
    }
  };

  const sendOtp = async () => {
    if (!found) return;
    try {
      const r = await api.post('/admin/quota/request-otp', { target_user_id: found.user_id });
      setOtpInfo({ sent_to_masked: r.data?.sent_to_masked || '' });
      showAlert('Authorization code sent', `An OTP was sent to the Super Admin's WhatsApp (${r.data?.sent_to_masked}). Enter it below to apply the change.`);
    } catch (e: any) {
      showAlert('Could not send code', errMsg(e, 'OTP request failed'));
    }
  };

  const applyChange = async (sku: SkuRow) => {
    const raw = drafts[sku.sku_code];
    const newLeft = parseInt(raw, 10);
    if (isNaN(newLeft) || newLeft < 0) { showAlert('Invalid', 'Enter a valid non-negative number for LEFT.'); return; }
    if (!reason.trim() || reason.trim().length < 3) { showAlert('Reason required', 'Please enter a reason (min 3 chars) for the change.'); return; }
    if (!otp.trim()) { showAlert('OTP required', 'Enter the authorization code sent to the Super Admin.'); return; }
    setApplyBusy(true);
    try {
      const r = await api.post('/admin/quota/apply', {
        target_user_id: found!.user_id, sku_code: sku.sku_code,
        new_left: newLeft, reason: reason.trim(), otp: otp.trim(),
      });
      setSkus(r.data.skus || []);
      const d: Record<string, string> = {};
      (r.data.skus || []).forEach((s: SkuRow) => { d[s.sku_code] = String(s.balance); });
      setDrafts(d);
      setOtp(''); setOtpInfo(null); setActiveSku(null); setReason('');
      const n = r.data?.notified || {};
      showAlert('Updated ✓', `${sku.name}: LEFT set to ${r.data.new_left}.\nUser notified — WhatsApp: ${n.whatsapp ? 'sent' : 'no'}, Email: ${n.email ? 'sent' : 'no'}.`);
    } catch (e: any) {
      showAlert('Update failed', errMsg(e, 'Apply failed'));
    } finally {
      setApplyBusy(false);
    }
  };

  const toggleGrant = async (g: AdminGrant) => {
    try {
      await api.post('/admin/quota/grant', { email: g.email, grant: !g.can_edit_quota });
      setGrants(prev => prev.map(x => x.user_id === g.user_id ? { ...x, can_edit_quota: !x.can_edit_quota } : x));
    } catch (e: any) {
      showAlert('Failed', errMsg(e, 'Could not update permission'));
    }
  };

  const addGrant = async () => {
    if (!grantEmail.trim()) return;
    try {
      await api.post('/admin/quota/grant', { email: grantEmail.trim(), grant: true });
      setGrantEmail('');
      const g = await api.get('/admin/quota/grants');
      setGrants(g.data?.admins || []);
      showAlert('Granted', 'Permission granted (if the email matches an admin).');
    } catch (e: any) {
      showAlert('Failed', errMsg(e, 'Could not grant'));
    }
  };

  if (boot) {
    return <SafeAreaView style={styles.container}><View style={styles.center}><ActivityIndicator color={COLORS.primary} /></View></SafeAreaView>;
  }

  if (!perm?.can_edit_quota) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <Header onBack={() => router.back()} />
        <View style={styles.center}>
          <Ionicons name="lock-closed" size={40} color={COLORS.textMuted} />
          <Text style={styles.deniedText}>You don't have permission to edit report allocations.</Text>
          <Text style={styles.deniedSub}>Ask a Super Admin to grant you the "Edit report counts" permission.</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <Header onBack={() => router.back()} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }} keyboardShouldPersistTaps="handled">
          {/* Lookup */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Locate user</Text>
            <Text style={styles.cardSub}>Both email and mobile must match the same account.</Text>
            <Text style={styles.label}>Email</Text>
            <TextInput style={styles.input} value={email} onChangeText={setEmail} placeholder="user@example.com"
              placeholderTextColor={COLORS.textMuted} autoCapitalize="none" keyboardType="email-address" />
            <Text style={styles.label}>Mobile (WhatsApp)</Text>
            <TextInput style={styles.input} value={mobile} onChangeText={setMobile} placeholder="+91XXXXXXXXXX"
              placeholderTextColor={COLORS.textMuted} keyboardType="phone-pad" />
            <TouchableOpacity style={[styles.primaryBtn, lookupBusy && { opacity: 0.6 }]} disabled={lookupBusy} onPress={doLookup}>
              {lookupBusy ? <ActivityIndicator color="#FFF" /> : <Text style={styles.primaryBtnText}>Find user</Text>}
            </TouchableOpacity>
          </View>

          {/* Result */}
          {found && (
            <View style={styles.card}>
              <View style={styles.userRow}>
                <View style={styles.avatar}><Text style={styles.avatarText}>{(found.name || found.email || '?').charAt(0).toUpperCase()}</Text></View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.userName}>{found.name || '—'}</Text>
                  <Text style={styles.userMeta}>{found.email} · {found.mobile_masked}</Text>
                </View>
                {found.whatsapp_verified && <Ionicons name="checkmark-circle" size={18} color="#059669" />}
              </View>

              <View style={styles.otpBox}>
                <Text style={styles.otpHint}>Editing requires Super-Admin authorization.</Text>
                <TouchableOpacity style={styles.otpBtn} onPress={sendOtp}>
                  <Ionicons name="key" size={14} color="#FFF" />
                  <Text style={styles.otpBtnText}>{otpInfo ? 'Resend code' : 'Send authorization code'}</Text>
                </TouchableOpacity>
                {otpInfo && (
                  <>
                    <Text style={[styles.otpHint, { marginTop: 8 }]}>Sent to Super Admin WhatsApp: {otpInfo.sent_to_masked}</Text>
                    <View style={styles.otpInline}>
                      <TextInput style={[styles.input, { flex: 1, marginTop: 0 }]} value={otp} onChangeText={setOtp}
                        placeholder="6-digit code" placeholderTextColor={COLORS.textMuted} keyboardType="number-pad" maxLength={6} />
                    </View>
                    <Text style={styles.label}>Reason (sent to user)</Text>
                    <TextInput style={[styles.input, styles.multiline]} value={reason} onChangeText={setReason} multiline
                      placeholder="e.g. Corrected an accidental over-allocation." placeholderTextColor={COLORS.textMuted} />
                  </>
                )}
              </View>

              <Text style={[styles.cardTitle, { marginTop: 8 }]}>Report allocation</Text>
              {skus.map(s => (
                <View key={s.sku_code} style={styles.skuRow}>
                  <View style={styles.skuLeft}>
                    <View style={styles.skuBadge}><Text style={styles.skuBadgeText}>{s.sku_code}</Text></View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.skuName} numberOfLines={1}>{s.name}</Text>
                      <Text style={styles.skuMeta}>Bought {s.granted} · Used {s.consumed}</Text>
                    </View>
                  </View>
                  <View style={styles.skuRight}>
                    <Text style={styles.leftLabel}>LEFT</Text>
                    <TextInput
                      style={styles.leftInput}
                      value={drafts[s.sku_code] ?? String(s.balance)}
                      onChangeText={(v) => { setDrafts(prev => ({ ...prev, [s.sku_code]: v.replace(/[^0-9]/g, '') })); setActiveSku(s.sku_code); }}
                      keyboardType="number-pad"
                    />
                    <TouchableOpacity
                      style={[styles.saveSku, (applyBusy || !otpInfo) && { opacity: 0.5 }]}
                      disabled={applyBusy || !otpInfo}
                      onPress={() => applyChange(s)}
                    >
                      {applyBusy && activeSku === s.sku_code ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.saveSkuText}>Save</Text>}
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
              {!otpInfo && <Text style={styles.tip}>Send the authorization code to enable Save.</Text>}
            </View>
          )}

          {/* Super-admin permission manager */}
          {perm?.role === 'super_admin' && (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Who can edit report counts</Text>
              <Text style={styles.cardSub}>Grant this permission to selected admins.</Text>
              <View style={styles.otpInline}>
                <TextInput style={[styles.input, { flex: 1, marginTop: 0 }]} value={grantEmail} onChangeText={setGrantEmail}
                  placeholder="admin@email.com" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" keyboardType="email-address" />
                <TouchableOpacity style={styles.grantAdd} onPress={addGrant}><Text style={styles.grantAddText}>Grant</Text></TouchableOpacity>
              </View>
              {grants.length === 0 ? (
                <Text style={styles.tip}>No admins found.</Text>
              ) : grants.map(g => (
                <TouchableOpacity key={g.user_id} style={styles.grantRow} onPress={() => toggleGrant(g)}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.grantName}>{g.name || g.email}</Text>
                    <Text style={styles.grantEmail}>{g.email}</Text>
                  </View>
                  <Ionicons name={g.can_edit_quota ? 'toggle' : 'toggle-outline'} size={30} color={g.can_edit_quota ? '#059669' : COLORS.textMuted} />
                </TouchableOpacity>
              ))}
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Header({ onBack }: { onBack: () => void }) {
  return (
    <View style={styles.header}>
      <TouchableOpacity onPress={onBack} style={{ padding: 4 }}><Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
      <Text style={styles.headerTitle}>Edit Report Allocation</Text>
      <View style={{ width: 30 }} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 8 },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 14, paddingVertical: 12, backgroundColor: COLORS.white,
    borderBottomWidth: 1, borderBottomColor: COLORS.divider,
  },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  deniedText: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, textAlign: 'center' },
  deniedSub: { fontSize: 12, color: COLORS.textMuted, textAlign: 'center' },

  card: { backgroundColor: COLORS.white, borderRadius: 14, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: COLORS.divider },
  cardTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  cardSub: { fontSize: 12, color: COLORS.textMuted, marginTop: 2, marginBottom: 6 },
  label: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, marginTop: 4, backgroundColor: COLORS.white },
  multiline: { minHeight: 60, textAlignVertical: 'top' },
  primaryBtn: { backgroundColor: COLORS.primary, borderRadius: 8, paddingVertical: 12, alignItems: 'center', marginTop: 14 },
  primaryBtnText: { color: '#FFF', fontSize: 14, fontWeight: '700' },

  userRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  avatar: { width: 40, height: 40, borderRadius: 20, backgroundColor: COLORS.primary, alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: '#FFF', fontSize: 18, fontWeight: '700' },
  userName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  userMeta: { fontSize: 12, color: COLORS.textMuted, marginTop: 1 },

  otpBox: { backgroundColor: '#FFFBEB', borderRadius: 10, padding: 12, marginTop: 12, borderWidth: 1, borderColor: '#FDE68A' },
  otpHint: { fontSize: 11, color: '#92400E' },
  otpBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#D97706', borderRadius: 8, paddingVertical: 9, marginTop: 8 },
  otpBtnText: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  otpInline: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },

  skuRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  skuLeft: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1, paddingRight: 8 },
  skuBadge: { backgroundColor: '#EDE9FE', borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3 },
  skuBadgeText: { fontSize: 11, fontWeight: '800', color: '#7C3AED' },
  skuName: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  skuMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  skuRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  leftLabel: { fontSize: 10, color: '#059669', fontWeight: '700' },
  leftInput: { width: 78, borderWidth: 1, borderColor: '#059669', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 7, fontSize: 14, color: COLORS.textPrimary, textAlign: 'center' },
  saveSku: { backgroundColor: COLORS.primary, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8 },
  saveSkuText: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  tip: { fontSize: 11, color: COLORS.textMuted, marginTop: 8, fontStyle: 'italic' },

  grantRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  grantName: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  grantEmail: { fontSize: 11, color: COLORS.textMuted },
  grantAdd: { backgroundColor: COLORS.primary, borderRadius: 8, paddingHorizontal: 14, paddingVertical: 11 },
  grantAddText: { color: '#FFF', fontSize: 12, fontWeight: '700' },
});
