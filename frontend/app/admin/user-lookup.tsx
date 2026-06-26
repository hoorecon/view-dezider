/**
 * /admin/user-lookup — read-only PII "User View".
 *
 * Access: Super Admin, or Admin with can_view_pii. A lookup needs BOTH email +
 * WhatsApp to match the same account, a purpose, and an NDA acknowledgement.
 * Every access is logged immutably. Admins see their own log; Super Admin can
 * manage permissions and view everyone's access log.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TextInput, TouchableOpacity, ActivityIndicator, Modal, Switch, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack } from '../../src/utils/navigation';

const PURPOSES = ['Support service', 'Data Analytics', 'Training Support', 'Other'];

// Tester / early-access tiers a permitted admin can assign to a user. The exact
// features each tier unlocks are controlled in Admin → ACM (granular matrix).
const ASSIGNABLE_TYPES: { id: string; label: string }[] = [
  { id: 'free', label: 'Free' },
  { id: 'trial', label: 'Trial' },
  { id: 'unit_tester', label: 'Unit Tester' },
  { id: 'integration_tester', label: 'Integration Tester' },
  { id: 'alpha', label: 'Alpha' },
  { id: 'beta', label: 'Beta' },
];

function fmtDate(d: any) {
  if (!d) return '—';
  try { return new Date(d).toLocaleString(); } catch { return String(d); }
}

export default function UserLookup() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const isSuper = user?.role === 'super_admin';
  const hasAccess = isSuper || !!user?.can_view_pii;

  // Lookup form
  const [email, setEmail] = useState('');
  const [whatsapp, setWhatsapp] = useState('');
  const [purpose, setPurpose] = useState('Support service');
  const [note, setNote] = useState('');
  const [ndaAck, setNdaAck] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [savingType, setSavingType] = useState(false);
  const [pendingType, setPendingType] = useState<string | null>(null);

  // NDA modal
  const [nda, setNda] = useState<any>(null);
  const [ndaOpen, setNdaOpen] = useState(false);

  // Logs + permissions
  const [myLog, setMyLog] = useState<any[]>([]);
  const [allLog, setAllLog] = useState<any[]>([]);
  const [grants, setGrants] = useState<any[]>([]);
  const [tab, setTab] = useState<'lookup' | 'mylog' | 'manage'>('lookup');

  const loadNda = useCallback(async () => {
    try { const r = await api.get('/admin/pii/nda'); setNda(r.data); } catch { /* ignore */ }
  }, []);
  const loadMyLog = useCallback(async () => {
    try { const r = await api.get('/admin/pii/my-access-log'); setMyLog(r.data?.entries || []); } catch { /* ignore */ }
  }, []);
  const loadManage = useCallback(async () => {
    try {
      const [g, a] = await Promise.all([api.get('/admin/pii/grants'), api.get('/admin/pii/access-log')]);
      setGrants(g.data?.admins || []);
      setAllLog(a.data?.entries || []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { if (hasAccess) { loadNda(); loadMyLog(); if (isSuper) loadManage(); } }, [hasAccess, isSuper, loadNda, loadMyLog, loadManage]);

  const openNda = useCallback(() => {
    if (Platform.OS === 'web') {
      // Aesthetic popup window on web; falls back to in-app modal.
      try {
        const w = window.open('', '_blank', 'width=560,height=640');
        if (w && nda) {
          w.document.write(`<title>${nda.title}</title><div style="font-family:Inter,system-ui,sans-serif;padding:24px;max-width:520px;color:#0f172a"><h2 style="color:#7c3aed">${nda.title}</h2>${(nda.body || []).map((p: string) => `<p style="line-height:1.6;color:#334155">${p}</p>`).join('')}<p style="margin-top:20px;font-weight:700">${nda.acknowledgement}</p></div>`);
          w.document.close();
          return;
        }
      } catch { /* fall through to modal */ }
    }
    setNdaOpen(true);
  }, [nda]);

  const submit = useCallback(async () => {
    if (!email.trim() || !whatsapp.trim()) { showAlert('Missing details', 'Enter both email and WhatsApp number.'); return; }
    if (!ndaAck) { showAlert('NDA required', 'Please acknowledge the NDA to proceed.'); return; }
    setSubmitting(true);
    setResult(null);
    try {
      const r = await api.post('/admin/pii/lookup', {
        email: email.trim(), whatsapp_number: whatsapp.trim(), purpose,
        purpose_note: note.trim() || null, nda_ack: ndaAck,
      });
      setResult(r.data);
      setPendingType(null);
      loadMyLog();
    } catch (e: any) {
      showAlert('Lookup failed', e?.response?.data?.detail || 'No matching account.');
      loadMyLog();
    } finally { setSubmitting(false); }
  }, [email, whatsapp, purpose, note, ndaAck, loadMyLog]);

  const toggleGrant = useCallback(async (targetEmail: string, grant: boolean) => {
    try {
      await api.post('/admin/pii/grant', { email: targetEmail, grant });
      loadManage();
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Could not update permission');
    }
  }, [loadManage]);

  const saveUserType = useCallback(async (uid: string, newType: string) => {
    setSavingType(true);
    try {
      const r = await api.put(`/acm/user/${uid}/type`, { user_type: newType });
      const applied = r.data?.user_type || newType;
      setResult((prev: any) => (prev ? { ...prev, profile: { ...prev.profile, user_type: applied } } : prev));
      setPendingType(null);
      showAlert('User type updated', `Set to "${applied.replace(/_/g, ' ')}". Their feature access now follows the ACM matrix for this tier.`);
    } catch (e: any) {
      showAlert('Update failed', e?.response?.data?.detail || 'Could not change the user type.');
    } finally {
      setSavingType(false);
    }
  }, []);

  if (!hasAccess) {
    return (
      <SafeAreaView style={s.root} edges={['top']}>
        <Header title="User Lookup" onBack={() => safeBack(router)} />
        <View style={s.center}>
          <Ionicons name="lock-closed" size={40} color={COLORS.textMuted} />
          <Text style={s.noAccess}>You don't have PII-access permission.</Text>
          <Text style={s.noAccessSub}>Ask a Super Admin to grant you access.</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <Header title="User Lookup (PII)" onBack={() => safeBack(router)} />

      {/* Tabs */}
      <View style={s.tabs}>
        <Tab label="Lookup" active={tab === 'lookup'} onPress={() => setTab('lookup')} />
        <Tab label="My Access Log" active={tab === 'mylog'} onPress={() => setTab('mylog')} />
        {isSuper && <Tab label="Manage" active={tab === 'manage'} onPress={() => setTab('manage')} />}
      </View>

      <ScrollView contentContainerStyle={s.body} keyboardShouldPersistTaps="handled">
        {tab === 'lookup' && (
          <>
            <View style={s.card}>
              <Text style={s.label}>Email</Text>
              <TextInput style={s.input} value={email} onChangeText={setEmail} placeholder="user@example.com" placeholderTextColor="#94A3B8" autoCapitalize="none" keyboardType="email-address" />
              <Text style={s.label}>WhatsApp number</Text>
              <TextInput style={s.input} value={whatsapp} onChangeText={setWhatsapp} placeholder="+9198xxxxxxxx" placeholderTextColor="#94A3B8" keyboardType="phone-pad" />

              <Text style={s.label}>Purpose</Text>
              <View style={s.chips}>
                {PURPOSES.map((p) => (
                  <TouchableOpacity key={p} style={[s.chip, purpose === p && s.chipOn]} onPress={() => setPurpose(p)}>
                    <Text style={[s.chipText, purpose === p && s.chipTextOn]}>{p}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              {purpose === 'Other' && (
                <TextInput style={s.input} value={note} onChangeText={setNote} placeholder="Describe the purpose" placeholderTextColor="#94A3B8" />
              )}

              {/* NDA */}
              <TouchableOpacity style={s.ndaRow} onPress={() => setNdaAck((v) => !v)} activeOpacity={0.8}>
                <Ionicons name={ndaAck ? 'checkbox' : 'square-outline'} size={22} color={ndaAck ? COLORS.primary : COLORS.textMuted} />
                <Text style={s.ndaText}>
                  I acknowledge the{' '}
                  <Text style={s.ndaLink} onPress={openNda}>PII Access NDA & terms</Text>.
                </Text>
              </TouchableOpacity>
              <Text style={s.warn}>You must have signed an NDA to access this PII.</Text>

              <TouchableOpacity style={[s.primaryBtn, submitting && { opacity: 0.6 }]} onPress={submit} disabled={submitting}>
                {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryText}>View user details</Text>}
              </TouchableOpacity>
            </View>

            {result?.profile && (
              <View style={s.resultCard}>
                <Text style={s.resultName}>{result.profile.name}</Text>
                <Row k="Email" v={result.profile.email} />
                <Row k="WhatsApp" v={`${result.profile.whatsapp_number || '—'}${result.profile.whatsapp_verified ? '  ✓ verified' : ''}`} />
                <Row k="Role" v={result.profile.role} />
                <Row k="Org" v={result.profile.org_id || '—'} />
                <Row k="Auth" v={result.profile.auth_method} />
                <Row k="Joined" v={fmtDate(result.profile.created_at)} />

                <Text style={s.subHead}>Entitlements</Text>
                {result.entitlements?.length ? result.entitlements.map((e: any) => (
                  <View key={e.sku_code} style={s.entRow}>
                    <Text style={s.entSku}>{e.sku_code}</Text>
                    <Text style={s.entMetric}>Bought {e.bought}</Text>
                    <Text style={[s.entMetric, { color: '#D97706' }]}>Used {e.used}</Text>
                    <Text style={[s.entMetric, { color: '#059669' }]}>Left {e.left}</Text>
                  </View>
                )) : <Text style={s.muted}>No purchases.</Text>}

                <Text style={s.subHead}>Decisions ({result.decisions_count})</Text>
                {result.recent_decisions?.slice(0, 10).map((d: any, i: number) => (
                  <Text key={i} style={s.decItem}>• {d.title}</Text>
                ))}
                {!result.recent_decisions?.length && <Text style={s.muted}>No decisions.</Text>}
                <Text style={s.auditNote}>Access logged · ref {String(result.audit_id).slice(0, 8)}</Text>
              </View>
            )}

            {result?.profile && (
              <View style={s.card} testID="assign-type-card">
                <Text style={s.sectionTitle}>User Type & Access</Text>
                <Text style={s.muted}>
                  Current: <Text style={{ fontWeight: '800', color: COLORS.textPrimary }}>{(result.profile.user_type || 'free').replace(/_/g, ' ')}</Text>
                  {result.profile.role && result.profile.role !== 'user' ? `   ·   role: ${result.profile.role}` : ''}
                </Text>
                <Text style={s.typeHint}>
                  Assign a tester / early-access tier so this user sees pre-release features. Exactly which
                  features each tier unlocks is controlled in Admin → ACM.
                </Text>
                <View style={s.chips}>
                  {ASSIGNABLE_TYPES.map((t) => {
                    const current = pendingType ?? (result.profile.user_type || 'free');
                    const on = current === t.id;
                    return (
                      <TouchableOpacity
                        key={t.id}
                        testID={`assign-type-${t.id}`}
                        style={[s.chip, on && s.chipOn]}
                        onPress={() => setPendingType(t.id)}
                      >
                        <Text style={[s.chipText, on && s.chipTextOn]}>{t.label}</Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
                {(() => {
                  const dirty = !!pendingType && pendingType !== (result.profile.user_type || 'free');
                  return (
                    <TouchableOpacity
                      testID="assign-type-save"
                      style={[s.primaryBtn, (!dirty || savingType) && { opacity: 0.5 }]}
                      onPress={() => saveUserType(result.profile.user_id, pendingType as string)}
                      disabled={!dirty || savingType}
                    >
                      {savingType ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryText}>Save user type</Text>}
                    </TouchableOpacity>
                  );
                })()}
              </View>
            )}
          </>
        )}

        {tab === 'mylog' && (
          <View style={s.card}>
            <Text style={s.sectionTitle}>My PII access history</Text>
            {myLog.length === 0 ? <Text style={s.muted}>No access yet.</Text> : myLog.map((r) => (
              <LogRow key={r.id} r={r} />
            ))}
          </View>
        )}

        {tab === 'manage' && isSuper && (
          <>
            <View style={s.card}>
              <Text style={s.sectionTitle}>PII access permissions</Text>
              <Text style={s.muted}>Grant admins permission to look up user PII.</Text>
              {grants.map((a) => (
                <View key={a.user_id} style={s.grantRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={s.grantName}>{a.name || a.email}</Text>
                    <Text style={s.grantEmail}>{a.email}</Text>
                  </View>
                  <Switch value={!!a.can_view_pii} onValueChange={(v) => toggleGrant(a.email, v)} />
                </View>
              ))}
              {grants.length === 0 && <Text style={s.muted}>No admins found.</Text>}
            </View>

            <View style={s.card}>
              <Text style={s.sectionTitle}>All PII access log</Text>
              {allLog.length === 0 ? <Text style={s.muted}>No access yet.</Text> : allLog.map((r) => (
                <LogRow key={r.id} r={r} showViewer />
              ))}
            </View>
          </>
        )}
      </ScrollView>

      {/* NDA modal (native / fallback) */}
      <Modal visible={ndaOpen} transparent animationType="fade" onRequestClose={() => setNdaOpen(false)}>
        <View style={s.modalOverlay}>
          <View style={s.modalCard}>
            <Text style={s.modalTitle}>{nda?.title || 'PII Access NDA'}</Text>
            <ScrollView style={{ maxHeight: 360 }}>
              {(nda?.body || []).map((p: string, i: number) => <Text key={i} style={s.ndaPara}>{p}</Text>)}
              <Text style={s.ndaAckLine}>{nda?.acknowledgement}</Text>
            </ScrollView>
            <TouchableOpacity style={s.primaryBtn} onPress={() => { setNdaAck(true); setNdaOpen(false); }}>
              <Text style={s.primaryText}>I acknowledge</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setNdaOpen(false)}><Text style={s.closeLink}>Close</Text></TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

function Header({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <View style={s.header}>
      <TouchableOpacity onPress={onBack} hitSlop={8} style={{ width: 24 }}><Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
      <Text style={s.headerTitle}>{title}</Text>
      <View style={{ width: 24 }} />
    </View>
  );
}
function Tab({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity style={[s.tab, active && s.tabOn]} onPress={onPress}>
      <Text style={[s.tabText, active && s.tabTextOn]}>{label}</Text>
    </TouchableOpacity>
  );
}
function Row({ k, v }: { k: string; v: any }) {
  return <View style={s.kv}><Text style={s.kvK}>{k}</Text><Text style={s.kvV}>{String(v ?? '—')}</Text></View>;
}
function LogRow({ r, showViewer }: { r: any; showViewer?: boolean }) {
  return (
    <View style={s.logRow}>
      <Ionicons name={r.matched ? 'eye' : 'close-circle'} size={16} color={r.matched ? '#059669' : '#DC2626'} />
      <View style={{ flex: 1 }}>
        {showViewer && <Text style={s.logViewer}>{r.viewer_email}</Text>}
        <Text style={s.logTarget}>{r.lookup_email}</Text>
        <Text style={s.logMeta}>{r.purpose}{r.purpose_note ? ` · ${r.purpose_note}` : ''} · {fmtDate(r.created_at)}</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: COLORS.border, backgroundColor: COLORS.white },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 8, padding: 24 },
  noAccess: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 8 },
  noAccessSub: { fontSize: 13, color: COLORS.textMuted },
  tabs: { flexDirection: 'row', backgroundColor: COLORS.white, paddingHorizontal: 12, gap: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  tab: { paddingVertical: 12, paddingHorizontal: 6, borderBottomWidth: 2, borderBottomColor: 'transparent' },
  tabOn: { borderBottomColor: COLORS.primary },
  tabText: { fontSize: 13, fontWeight: '600', color: COLORS.textMuted },
  tabTextOn: { color: COLORS.primary },
  body: { padding: 16, paddingBottom: 48 },
  card: { backgroundColor: COLORS.white, borderRadius: 14, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: COLORS.border },
  label: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6, marginTop: 10 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11, fontSize: 14, color: COLORS.textPrimary, backgroundColor: '#F8FAFC' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F8FAFC' },
  chipOn: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  chipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  chipTextOn: { color: '#FFFFFF' },
  ndaRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, marginTop: 16 },
  ndaText: { flex: 1, fontSize: 13, color: COLORS.textSecondary, lineHeight: 19 },
  ndaLink: { color: COLORS.primary, fontWeight: '700', textDecorationLine: 'underline' },
  warn: { fontSize: 12, color: '#B45309', backgroundColor: '#FEF3C7', borderRadius: 8, padding: 8, marginTop: 10 },
  primaryBtn: { marginTop: 16, backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 13, alignItems: 'center' },
  primaryText: { color: '#FFFFFF', fontWeight: '800', fontSize: 15 },
  resultCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 16, borderWidth: 1.5, borderColor: COLORS.primary },
  resultName: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 10 },
  kv: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5, borderTopWidth: 1, borderTopColor: COLORS.divider },
  kvK: { fontSize: 13, color: COLORS.textMuted },
  kvV: { fontSize: 13, color: COLORS.textPrimary, fontWeight: '600', flexShrink: 1, textAlign: 'right', marginLeft: 12 },
  subHead: { fontSize: 14, fontWeight: '800', color: COLORS.textPrimary, marginTop: 16, marginBottom: 8 },
  entRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 4 },
  entSku: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, width: 44 },
  entMetric: { fontSize: 12, color: COLORS.textSecondary },
  decItem: { fontSize: 13, color: COLORS.textSecondary, paddingVertical: 2 },
  muted: { fontSize: 13, color: COLORS.textMuted, paddingVertical: 4 },
  auditNote: { fontSize: 11, color: COLORS.textMuted, marginTop: 14, fontStyle: 'italic' },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 8 },
  typeHint: { fontSize: 12.5, color: COLORS.textSecondary, lineHeight: 18, marginTop: 8, marginBottom: 12 },
  logRow: { flexDirection: 'row', gap: 10, paddingVertical: 8, borderTopWidth: 1, borderTopColor: COLORS.divider, alignItems: 'flex-start' },
  logViewer: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  logTarget: { fontSize: 13, color: COLORS.textSecondary },
  logMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  grantRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderTopWidth: 1, borderTopColor: COLORS.divider },
  grantName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  grantEmail: { fontSize: 12, color: COLORS.textMuted },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', justifyContent: 'center', padding: 20 },
  modalCard: { backgroundColor: '#FFFFFF', borderRadius: 16, padding: 20 },
  modalTitle: { fontSize: 17, fontWeight: '800', color: COLORS.primary, marginBottom: 12 },
  ndaPara: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 20, marginBottom: 10 },
  ndaAckLine: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginTop: 6 },
  closeLink: { textAlign: 'center', color: COLORS.textMuted, marginTop: 12, fontSize: 13 },
});
