/**
 * <ModuleStoreActions> — drop-in action bar for decision detail/summary views.
 *
 * Three contextual CTAs that work across MyDezider, Pros & Cons, and SWOT:
 *  • Download Report (L1)  — calls /reports/{module}/{id}.pdf; if no entitlement
 *                            yet, deep-links to /store?highlight=L1.
 *  • Book Expert (L3)      — checks for L3 balance; if none → /store?highlight=L3
 *                            (purchase first); else deep-links to /tools/expert-net
 *                            filtered by the decision's life_area_id.
 *  • Order Expert Review (L4) — purchase + admin queues delivery; manual
 *                               fulfillment for Phase 2.
 *
 * Renders as a soft-coloured horizontal row of pills, safe in narrow viewports.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, ActivityIndicator, Linking, Modal, TextInput, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../utils/api';
import { showAlert, confirmDialog } from '../utils/alert';
import type { DecisionModule } from './PaywallGate';

interface Props {
  module: DecisionModule;
  decisionId: string;
  lifeAreaId?: string | null;
  subAreaId?: string | null;
}

interface ReportInfo { unlocked: boolean; unlocked_via?: string | null; l1_balance: number; l2_balance: number; }

export default function ModuleStoreActions({ module, decisionId, lifeAreaId, subAreaId }: Props) {
  const router = useRouter();
  const [info, setInfo] = useState<ReportInfo | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [shareChannel, setShareChannel] = useState<'email' | 'whatsapp'>('email');
  const [shareEmail, setShareEmail] = useState('');
  const [sharePhone, setSharePhone] = useState('');
  const [shareName, setShareName] = useState('');
  const [shareBusy, setShareBusy] = useState(false);
  // In-app Contacts picker
  const [pickerOpen, setPickerOpen] = useState(false);
  const [contacts, setContacts] = useState<any[]>([]);
  const [contactSearch, setContactSearch] = useState('');
  const [contactsLoading, setContactsLoading] = useState(false);

  const loadInfo = useCallback(async () => {
    try {
      const res = await api.get(`/reports/${module}/${decisionId}/info`);
      setInfo(res.data);
    } catch {
      setInfo({ unlocked: false, l1_balance: 0, l2_balance: 0 });
    }
  }, [module, decisionId]);
  useEffect(() => { loadInfo(); }, [loadInfo]);

  const downloadPdf = useCallback(async () => {
    setBusy('L1');
    try {
      const base = (process.env.EXPO_PUBLIC_BACKEND_URL || '') + `/api/reports/${module}/${decisionId}.pdf`;
      // Use a fetch+blob so we can pass the auth header (axios does not stream PDFs nicely on web)
      const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
      const token = await AsyncStorage.getItem('session_token');
      const resp = await fetch(base, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (resp.status === 402) {
        // No entitlement — kick to store
        const want = await confirmDialog('Unlock report', 'You need a DIY Decision Report (₹199) or any plan to download the PDF. Open the store now?', { confirmText: 'Open store' });
        if (want) router.push({ pathname: '/store', params: { highlight: 'L1', module, decision_id: decisionId } } as any);
        return;
      }
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || 'Download failed');
      }
      const blob = await resp.blob();
      if (Platform.OS === 'web') {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dezider_${module}_${decisionId.slice(0, 8)}.pdf`;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1500);
      } else {
        // Native: open in browser (good enough for Phase A; native FS save can be added later)
        const reader = new FileReader();
        reader.onloadend = () => Linking.openURL(reader.result as string);
        reader.readAsDataURL(blob);
      }
      await loadInfo();
      showAlert('Report ready', 'Your PDF has been downloaded.');
    } catch (e: any) {
      showAlert('Download failed', e?.message || 'Try again later.');
    } finally { setBusy(null); }
  }, [module, decisionId, router, loadInfo]);

  const bookExpert = useCallback(async () => {
    setBusy('L3');
    try {
      // Check L3 balance up front
      const res = await api.get('/store/my-entitlements');
      const l3 = (res.data?.entitlements || []).find((x: any) => x.sku_code === 'L3');
      const hasL3 = (l3?.balance || 0) > 0;
      if (!hasL3) {
        const want = await confirmDialog('Book a Professional Session', 'A Professional Guided Session (₹1,999) lets you screen-share your decision with an expert. Buy now?', { confirmText: 'Open store' });
        if (want) router.push({ pathname: '/store', params: { highlight: 'L3', module, decision_id: decisionId } } as any);
        return;
      }
      // Deep-link into expert-net filtered by life area
      router.push({ pathname: '/tools/expert-net' as any, params: { from_module: module, decision_id: decisionId, life_area_id: lifeAreaId || '', sub_area_id: subAreaId || '' } } as any);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not check entitlements.');
    } finally { setBusy(null); }
  }, [module, decisionId, router, lifeAreaId, subAreaId]);

  const orderReview = useCallback(async () => {
    const ok = await confirmDialog('Order Expert Review', 'A domain expert will review this decision and send written recommendations within 48 hrs (₹2,800). Continue to store?', { confirmText: 'Buy L4' });
    if (!ok) return;
    router.push({ pathname: '/store', params: { highlight: 'L4', module, decision_id: decisionId } } as any);
  }, [router, module, decisionId]);

  const submitShare = useCallback(async () => {
    if (shareChannel === 'email' && !shareEmail.trim()) { showAlert('Email needed', 'Enter the recipient email.'); return; }
    if (shareChannel === 'whatsapp' && !sharePhone.trim()) { showAlert('Phone needed', 'Enter the WhatsApp number with country code.'); return; }
    setShareBusy(true);
    try {
      const res = await api.post('/shares', {
        module, decision_id: decisionId, channel: shareChannel,
        recipient_email: shareChannel === 'email' ? shareEmail.trim() : undefined,
        recipient_phone: shareChannel === 'whatsapp' ? sharePhone.trim() : undefined,
        recipient_name: shareName.trim() || undefined,
      });
      setShareOpen(false); setShareEmail(''); setSharePhone(''); setShareName('');
      if (res.data?.sent) {
        showAlert('Shared', `Link sent via ${shareChannel === 'email' ? 'email' : 'WhatsApp'}. They'll find it under "Shared with me" after logging in.`);
      } else {
        showAlert('Saved — delivery pending', res.data?.error ? `Could not deliver: ${res.data.error}` : 'Share created but delivery failed.');
      }
    } catch (e: any) {
      showAlert('Share failed', e?.response?.data?.detail || 'Try again later.');
    } finally { setShareBusy(false); }
  }, [module, decisionId, shareChannel, shareEmail, sharePhone, shareName]);

  const openContactPicker = useCallback(async () => {
    setPickerOpen(true);
    setContactSearch('');
    setContactsLoading(true);
    try {
      const res = await api.get('/contacts', { params: { limit: 200 } });
      setContacts(res.data?.contacts || []);
    } catch {
      showAlert('Contacts', 'Could not load your contacts. You can still type the details manually.');
      setContacts([]);
    } finally {
      setContactsLoading(false);
    }
  }, []);

  const chooseContact = useCallback((c: any) => {
    if (shareChannel === 'email') {
      const email = (c.email || '').trim();
      if (!email) { showAlert('No email saved', `${c.name || 'This contact'} has no email. Add one in Contacts or type it manually.`); return; }
      setShareEmail(email);
    } else {
      const wa = String(c.whatsapp || c.phone || '').replace(/[^\d+]/g, '');
      if (!wa) { showAlert('No number saved', `${c.name || 'This contact'} has no WhatsApp/phone number. Add one in Contacts or type it manually.`); return; }
      setSharePhone(wa);
    }
    if (c.name && !shareName.trim()) setShareName(c.name);
    setPickerOpen(false);
  }, [shareChannel, shareName]);

  const filteredContacts = useMemo(() => {
    const q = contactSearch.trim().toLowerCase();
    if (!q) return contacts;
    return contacts.filter((c) =>
      `${c.name || ''} ${c.email || ''} ${c.phone || ''} ${c.whatsapp || ''} ${c.organization || ''}`.toLowerCase().includes(q));
  }, [contacts, contactSearch]);

  return (
    <View style={s.row}>
      <Pill icon="download" label={info?.unlocked ? 'Download PDF' : 'Unlock PDF'} tone="#3B82F6" busy={busy === 'L1'} onPress={downloadPdf} hint={info?.unlocked ? null : info?.l1_balance ? `${info.l1_balance} L1 left` : null} />
      <Pill icon="videocam" label="Book Expert" tone="#059669" busy={busy === 'L3'} onPress={bookExpert} />
      <Pill icon="ribbon" label="Expert Review" tone="#DC2626" busy={busy === 'L4'} onPress={orderReview} />
      <Pill icon="share-social" label="Share" tone="#7C3AED" onPress={() => setShareOpen(true)} />

      <Modal visible={shareOpen} transparent animationType="fade" onRequestClose={() => setShareOpen(false)}>
        <View style={s.backdrop}>
          <View style={s.sheet}>
            <Text style={s.sheetTitle}>Share this report</Text>
            <Text style={s.sheetSub}>They'll get a secure link. After logging in (or signing up free), it appears in their “Shared with me”.</Text>
            <View style={s.segRow}>
              <SegBtn label="Email" active={shareChannel === 'email'} onPress={() => setShareChannel('email')} />
              <SegBtn label="WhatsApp" active={shareChannel === 'whatsapp'} onPress={() => setShareChannel('whatsapp')} />
            </View>
            {shareChannel === 'email' ? (
              <TextInput style={s.input} placeholder="Recipient email" placeholderTextColor="#9CA3AF" autoCapitalize="none" keyboardType="email-address" value={shareEmail} onChangeText={setShareEmail} />
            ) : (
              <TextInput style={s.input} placeholder="WhatsApp number (with country code)" placeholderTextColor="#9CA3AF" keyboardType="phone-pad" value={sharePhone} onChangeText={setSharePhone} />
            )}
            <TouchableOpacity style={s.pickBtn} onPress={openContactPicker}>
              <Ionicons name="people" size={16} color="#7C3AED" />
              <Text style={s.pickTxt}>Pick from Contacts</Text>
            </TouchableOpacity>
            <TextInput style={s.input} placeholder="Recipient name (optional)" placeholderTextColor="#9CA3AF" value={shareName} onChangeText={setShareName} />
            <View style={s.sheetBtns}>
              <TouchableOpacity style={[s.sheetBtn, s.cancelBtn]} onPress={() => setShareOpen(false)} disabled={shareBusy}><Text style={s.cancelTxt}>Cancel</Text></TouchableOpacity>
              <TouchableOpacity style={[s.sheetBtn, s.sendBtn]} onPress={submitShare} disabled={shareBusy}>
                {shareBusy ? <ActivityIndicator size="small" color="#fff" /> : <Text style={s.sendTxt}>Send</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* In-app Contacts picker */}
      <Modal visible={pickerOpen} transparent animationType="slide" onRequestClose={() => setPickerOpen(false)}>
        <View style={s.backdrop}>
          <View style={[s.sheet, { maxHeight: '82%', paddingBottom: 12 }]}>
            <View style={s.pickerHead}>
              <Text style={s.sheetTitle}>Pick from Contacts</Text>
              <TouchableOpacity onPress={() => setPickerOpen(false)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                <Ionicons name="close" size={22} color="#6B7280" />
              </TouchableOpacity>
            </View>
            <Text style={s.sheetSub}>Choose a contact to fill their {shareChannel === 'email' ? 'email' : 'WhatsApp number'} automatically.</Text>
            <View style={s.searchBox}>
              <Ionicons name="search" size={16} color="#9CA3AF" />
              <TextInput style={s.searchInput} placeholder="Search name, email, phone…" placeholderTextColor="#9CA3AF" value={contactSearch} onChangeText={setContactSearch} autoCapitalize="none" />
            </View>
            {contactsLoading ? (
              <ActivityIndicator color="#7C3AED" style={{ marginVertical: 24 }} />
            ) : (
              <ScrollView style={{ maxHeight: 380 }} keyboardShouldPersistTaps="handled">
                {filteredContacts.length === 0 ? (
                  <Text style={s.emptyTxt}>No contacts found. Add people in the Contacts module, or close this and type the {shareChannel === 'email' ? 'email' : 'number'} manually.</Text>
                ) : filteredContacts.map((c, i) => {
                  const detail = shareChannel === 'email' ? (c.email || 'No email saved') : (c.whatsapp || c.phone || 'No number saved');
                  const disabled = shareChannel === 'email' ? !c.email : !(c.whatsapp || c.phone);
                  return (
                    <TouchableOpacity
                      key={c.contact_id || c.id || `${c.name}-${i}`}
                      style={[s.contactRow, disabled && { opacity: 0.45 }]}
                      onPress={() => chooseContact(c)}
                      disabled={disabled}
                    >
                      <View style={s.avatar}><Text style={s.avatarTxt}>{(c.name || '?').slice(0, 1).toUpperCase()}</Text></View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.contactName} numberOfLines={1}>{c.name || 'Unnamed'}</Text>
                        <Text style={s.contactDetail} numberOfLines={1}>{detail}</Text>
                      </View>
                      {!disabled && <Ionicons name="chevron-forward" size={18} color="#9CA3AF" />}
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
}

function SegBtn({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <TouchableOpacity onPress={onPress} style={[s.seg, active && s.segActive]}>
      <Text style={[s.segTxt, active && s.segTxtActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

function Pill({ icon, label, tone, onPress, busy, hint }: { icon: any; label: string; tone: string; onPress: () => void; busy?: boolean; hint?: string | null }) {
  return (
    <TouchableOpacity onPress={onPress} style={[s.pill, { borderColor: tone + '55', backgroundColor: tone + '12' }]} disabled={!!busy} accessibilityLabel={label}>
      {busy ? <ActivityIndicator size="small" color={tone} /> : <Ionicons name={icon} size={16} color={tone} />}
      <Text style={[s.pillText, { color: tone }]}>{label}</Text>
      {hint && <Text style={[s.pillHint, { color: tone }]}>· {hint}</Text>}
    </TouchableOpacity>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginVertical: 10, paddingHorizontal: 4 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, borderWidth: 1 },
  pillText: { fontSize: 13, fontWeight: '700' },
  pillHint: { fontSize: 11, fontWeight: '600', opacity: 0.85 },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  sheet: { backgroundColor: '#fff', borderRadius: 16, padding: 20, width: '100%', maxWidth: 440, alignSelf: 'center' },
  sheetTitle: { fontSize: 18, fontWeight: '800', color: '#111827' },
  sheetSub: { fontSize: 12.5, color: '#6B7280', marginTop: 6, marginBottom: 14, lineHeight: 18 },
  segRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  seg: { flex: 1, paddingVertical: 10, borderRadius: 10, borderWidth: 1.5, borderColor: '#E5E7EB', alignItems: 'center' },
  segActive: { borderColor: '#7C3AED', backgroundColor: '#7C3AED15' },
  segTxt: { fontSize: 14, fontWeight: '700', color: '#6B7280' },
  segTxtActive: { color: '#7C3AED' },
  input: { borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11, fontSize: 15, color: '#111827', marginBottom: 10 },
  pickBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, borderWidth: 1.5, borderColor: '#7C3AED', backgroundColor: '#7C3AED10', marginBottom: 10 },
  pickTxt: { fontSize: 14, fontWeight: '700', color: '#7C3AED' },
  pickerHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  searchBox: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, paddingHorizontal: 12, paddingVertical: Platform.OS === 'ios' ? 10 : 6, marginBottom: 8 },
  searchInput: { flex: 1, fontSize: 14, color: '#111827', padding: 0 },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: '#F1F1F4' },
  avatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#7C3AED', alignItems: 'center', justifyContent: 'center' },
  avatarTxt: { color: '#fff', fontSize: 16, fontWeight: '800' },
  contactName: { fontSize: 14.5, fontWeight: '700', color: '#111827' },
  contactDetail: { fontSize: 12.5, color: '#6B7280', marginTop: 2 },
  emptyTxt: { fontSize: 13, color: '#9CA3AF', textAlign: 'center', paddingVertical: 28, lineHeight: 19, paddingHorizontal: 8 },
  sheetBtns: { flexDirection: 'row', gap: 10, marginTop: 4 },
  sheetBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  cancelBtn: { backgroundColor: '#F3F4F6' },
  cancelTxt: { fontSize: 15, fontWeight: '700', color: '#374151' },
  sendBtn: { backgroundColor: '#7C3AED' },
  sendTxt: { fontSize: 15, fontWeight: '700', color: '#fff' },
});
