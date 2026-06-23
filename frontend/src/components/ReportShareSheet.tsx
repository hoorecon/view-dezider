/**
 * <ReportShareSheet> — ONE reusable share sheet for the whole app.
 *
 * Sends a secure link via the existing backend share system:
 *   • WhatsApp → UltraMsg
 *   • Email    → Resend
 * The recipient sees it under "Shared with me" and can download a server-side
 * (reportlab) PDF. Works for any module the backend `/api/shares` supports
 * (dezider, pros_cons, swot, solution_finder, assessment, …).
 *
 * Also exports `downloadReportPdf(url, filename)` — an authenticated PDF
 * download helper (web = blob download, native = open) reused anywhere.
 */
import React, { useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, ScrollView, Platform, Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../utils/api';
import { showAlert } from '../utils/alert';

export async function downloadReportPdf(path: string, filename: string) {
  const base = (process.env.EXPO_PUBLIC_BACKEND_URL || '') + path;
  const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
  const token = await AsyncStorage.getItem('session_token');
  const resp = await fetch(base, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!resp.ok) throw new Error((await resp.text()) || 'Download failed');
  const blob = await resp.blob();
  if (Platform.OS === 'web') {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  } else {
    const reader = new FileReader();
    reader.onloadend = () => Linking.openURL(reader.result as string);
    reader.readAsDataURL(blob);
  }
}

interface Props {
  visible: boolean;
  onClose: () => void;
  module: string;          // 'assessment' | 'dezider' | 'pros_cons' | 'swot' | 'solution_finder'
  decisionId: string;
  title?: string;
  /** Pre-fill a WhatsApp number (e.g. the assessed person's). */
  defaultPhone?: string;
}

export default function ReportShareSheet({ visible, onClose, module, decisionId, title, defaultPhone }: Props) {
  const [channel, setChannel] = useState<'whatsapp' | 'email'>('whatsapp');
  const [phone, setPhone] = useState(defaultPhone || '');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);

  React.useEffect(() => { if (visible) setPhone(defaultPhone || ''); }, [visible, defaultPhone]);

  const send = async () => {
    if (channel === 'whatsapp' && phone.replace(/\D/g, '').length < 8) {
      showAlert('Number needed', 'Enter a valid WhatsApp number with country code.'); return;
    }
    if (channel === 'email' && !email.trim()) { showAlert('Email needed', 'Enter the recipient email.'); return; }
    setBusy(true);
    try {
      const res = await api.post('/shares', {
        module, decision_id: decisionId, channel,
        recipient_phone: channel === 'whatsapp' ? phone.trim() : undefined,
        recipient_email: channel === 'email' ? email.trim() : undefined,
        recipient_name: name.trim() || undefined,
      });
      onClose();
      if (res.data?.sent) {
        showAlert('Shared ✅', `Link sent via ${channel === 'whatsapp' ? 'WhatsApp' : 'email'}. They'll find it under "Shared with me" after logging in.`);
      } else {
        showAlert('Saved — delivery pending', res.data?.error ? `Could not deliver: ${res.data.error}` : 'Share created but delivery failed.');
      }
    } catch (e: any) {
      showAlert('Share failed', e?.response?.data?.detail || 'Try again later.');
    } finally { setBusy(false); }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.card}>
          <ScrollView keyboardShouldPersistTaps="handled">
            <View style={s.headerRow}>
              <Text style={s.title}>Share report</Text>
              <TouchableOpacity onPress={onClose} hitSlop={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                <Ionicons name="close" size={22} color="#475569" />
              </TouchableOpacity>
            </View>
            {!!title && <Text style={s.subtitle} numberOfLines={2}>{title}</Text>}

            <View style={s.channelRow}>
              <TouchableOpacity style={[s.chan, channel === 'whatsapp' && s.chanActive]} onPress={() => setChannel('whatsapp')}>
                <Ionicons name="logo-whatsapp" size={18} color={channel === 'whatsapp' ? '#FFF' : '#25D366'} />
                <Text style={[s.chanTxt, channel === 'whatsapp' && s.chanTxtActive]}>WhatsApp</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.chan, channel === 'email' && s.chanActive]} onPress={() => setChannel('email')}>
                <Ionicons name="mail" size={18} color={channel === 'email' ? '#FFF' : '#2563EB'} />
                <Text style={[s.chanTxt, channel === 'email' && s.chanTxtActive]}>Email</Text>
              </TouchableOpacity>
            </View>

            {channel === 'whatsapp' ? (
              <>
                <Text style={s.label}>WhatsApp number (with country code)</Text>
                <TextInput value={phone} onChangeText={setPhone} placeholder="+91 9XXXXXXXXX" placeholderTextColor="#94A3B8" keyboardType={Platform.OS === 'web' ? 'default' : 'phone-pad'} style={s.input} />
              </>
            ) : (
              <>
                <Text style={s.label}>Recipient email</Text>
                <TextInput value={email} onChangeText={setEmail} placeholder="name@example.com" placeholderTextColor="#94A3B8" autoCapitalize="none" keyboardType="email-address" style={s.input} />
              </>
            )}
            <Text style={s.label}>Their name (optional)</Text>
            <TextInput value={name} onChangeText={setName} placeholder="Recipient name" placeholderTextColor="#94A3B8" style={s.input} />
            <Text style={s.help}>A secure JELCOS AI link is sent. They log in / sign up free and the report appears under “Shared with me” with a downloadable PDF.</Text>

            <TouchableOpacity style={s.btn} onPress={send} disabled={busy}>
              {busy ? <ActivityIndicator color="#FFF" /> : (<><Ionicons name="paper-plane" size={16} color="#FFF" /><Text style={s.btnText}>Send</Text></>)}
            </TouchableOpacity>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  card: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '90%' },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { fontSize: 18, fontWeight: '800', color: '#0F172A' },
  subtitle: { fontSize: 13, color: '#475569', marginTop: 4 },
  channelRow: { flexDirection: 'row', gap: 10, marginTop: 16 },
  chan: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 12, borderRadius: 10, borderWidth: 1.5, borderColor: '#CBD5E1', backgroundColor: '#FFF' },
  chanActive: { backgroundColor: '#6366F1', borderColor: '#6366F1' },
  chanTxt: { fontSize: 14, fontWeight: '700', color: '#334155' },
  chanTxtActive: { color: '#FFF' },
  label: { fontSize: 13, fontWeight: '700', color: '#0F172A', marginTop: 14, marginBottom: 4 },
  input: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A' },
  help: { fontSize: 11, color: '#64748B', marginTop: 8, lineHeight: 16 },
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#6366F1', borderRadius: 12, paddingVertical: 14, marginTop: 18 },
  btnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
});
