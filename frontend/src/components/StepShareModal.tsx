import React, { useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, ScrollView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../utils/api';
import { COLORS } from '../constants/colors';

interface StepShareModalProps {
  visible: boolean;
  onClose: () => void;
  module: 'conflict-breaker' | 'pros-cons' | 'swot' | 'solution-finder' | 'goal-setter' | 'my-dezider';
  decisionId: string;
  stepId: string;
  stepLabel: string;
  /** For multi-party modules only (Conflict Breaker). */
  partyId?: string;
  partyLabel?: string;
  /** Which fields the invitee should fill. */
  fields?: string[];
  /** Optional default TTL hours (defaults to 72). */
  defaultTtlHours?: number;
  onInvited?: (inviteId: string) => void;
}

/**
 * Generic step-share modal used by all 6 collaborative modules. In-app only —
 * the link routes to `/share/invite/[id]` where the invitee logs in or does an
 * instant signup with mandatory WhatsApp verification before submitting.
 */
export const StepShareModal: React.FC<StepShareModalProps> = ({
  visible, onClose, module, decisionId, stepId, stepLabel, partyId, partyLabel,
  fields = [], defaultTtlHours = 72, onInvited,
}) => {
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [message, setMessage] = useState('');
  const [ttlHours, setTtlHours] = useState(String(defaultTtlHours));
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ link?: string; whatsapp?: boolean; email?: boolean } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const reset = () => { setPhone(''); setEmail(''); setName(''); setMessage(''); setResult(null); setErr(null); };
  const close = () => { reset(); onClose(); };

  const submit = async () => {
    setErr(null);
    const digits = phone.replace(/\D/g, '');
    if (digits.length < 8) { setErr('Please enter a valid WhatsApp number (with country code).'); return; }
    setSending(true);
    try {
      const expiry = new Date();
      expiry.setHours(expiry.getHours() + (parseInt(ttlHours, 10) || defaultTtlHours));
      const { data } = await api.post('/collab/invite', {
        module, decision_id: decisionId, step_id: stepId, step_label: stepLabel,
        party_id: partyId, party_label: partyLabel, fields,
        invitee_phone: phone, invitee_email: email || undefined,
        invitee_display_name: name || partyLabel || undefined,
        expires_at: expiry.toISOString(),
        message: message || undefined,
      });
      setResult({
        link: data?.link,
        whatsapp: !!data?.notify?.whatsapp,
        email: !!data?.notify?.email,
      });
      if (data?.invite?.invite_id && onInvited) onInvited(data.invite.invite_id);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || 'Failed to send invite');
    } finally { setSending(false); }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={close}>
      <View style={s.overlay}>
        <View style={s.card}>
          <ScrollView keyboardShouldPersistTaps="handled">
            <View style={s.headerRow}>
              <View style={{ flex: 1 }}>
                <Text style={s.title}>Share &amp; invite</Text>
                <Text style={s.subtitle}>
                  Step: <Text style={{ fontWeight: '700' }}>{stepLabel}</Text>
                  {partyLabel && <Text> — as <Text style={{ color: '#6366F1' }}>{partyLabel}</Text></Text>}
                </Text>
              </View>
              <TouchableOpacity onPress={close} hitSlop={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                <Ionicons name="close" size={22} color="#475569" />
              </TouchableOpacity>
            </View>

            {!result && (
              <>
                <Text style={s.label}>WhatsApp number (with country code)</Text>
                <TextInput
                  value={phone} onChangeText={setPhone}
                  placeholder="+91 9XXXXXXXXX"
                  placeholderTextColor="#94A3B8"
                  keyboardType={Platform.OS === 'web' ? 'default' : 'phone-pad'}
                  style={s.input}
                />
                <Text style={s.help}>If they’re a new user, they’ll do an instant signup with WhatsApp verification before submitting.</Text>

                <Text style={s.label}>Email (optional)</Text>
                <TextInput value={email} onChangeText={setEmail} placeholder="name@example.com" placeholderTextColor="#94A3B8" autoCapitalize="none" keyboardType="email-address" style={s.input} />

                <Text style={s.label}>Their display name (optional)</Text>
                <TextInput value={name} onChangeText={setName} placeholder={partyLabel || 'Contributor name'} placeholderTextColor="#94A3B8" style={s.input} />

                <Text style={s.label}>Expires in (hours)</Text>
                <TextInput value={ttlHours} onChangeText={setTtlHours} keyboardType="numeric" style={s.input} />
                <Text style={s.help}>Late submissions are saved as reference but not auto-merged.</Text>

                <Text style={s.label}>Personal note (optional)</Text>
                <TextInput value={message} onChangeText={setMessage} multiline placeholder="Hey, please share your perspective on this step..." placeholderTextColor="#94A3B8" style={[s.input, { minHeight: 70, textAlignVertical: 'top' }]} />

                {err && <Text style={s.err}>{err}</Text>}

                <TouchableOpacity style={s.btn} onPress={submit} disabled={sending}>
                  {sending ? <ActivityIndicator color="#FFF" /> : (
                    <>
                      <Ionicons name="paper-plane" size={16} color="#FFF" />
                      <Text style={s.btnText}>Send invite</Text>
                    </>
                  )}
                </TouchableOpacity>
              </>
            )}

            {result && (
              <View>
                <View style={s.successBox}>
                  <Ionicons name="checkmark-circle" size={28} color="#10B981" />
                  <Text style={s.successTitle}>Invite sent!</Text>
                  <Text style={s.successHelp}>
                    {result.whatsapp ? 'WhatsApp delivered. ' : 'WhatsApp will retry. '}
                    {result.email ? 'Email delivered. ' : ''}
                    Track status from “Invites” on this decision.
                  </Text>
                  {result.link && (
                    <View style={s.linkBox}>
                      <Text style={s.linkText} selectable>{result.link}</Text>
                    </View>
                  )}
                </View>
                <TouchableOpacity style={[s.btn, { backgroundColor: '#64748B', marginTop: 14 }]} onPress={close}>
                  <Text style={s.btnText}>Done</Text>
                </TouchableOpacity>
              </View>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  card: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '90%' },
  headerRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 14 },
  title: { fontSize: 18, fontWeight: '800', color: '#0F172A' },
  subtitle: { fontSize: 13, color: '#475569', marginTop: 2 },
  label: { fontSize: 13, fontWeight: '700', color: '#0F172A', marginTop: 10, marginBottom: 4 },
  input: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A' },
  help: { fontSize: 11, color: '#64748B', marginTop: 4 },
  err: { fontSize: 13, color: '#DC2626', marginTop: 10, fontWeight: '600' },
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS?.primary || '#003087', borderRadius: 12, paddingVertical: 14, marginTop: 18 },
  btnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  successBox: { backgroundColor: '#F0FDF4', borderRadius: 12, padding: 16, alignItems: 'center', borderWidth: 1, borderColor: '#86EFAC' },
  successTitle: { fontSize: 16, fontWeight: '800', color: '#065F46', marginTop: 8 },
  successHelp: { fontSize: 12, color: '#065F46', textAlign: 'center', marginTop: 6, lineHeight: 18 },
  linkBox: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#D1FAE5', borderRadius: 8, padding: 10, marginTop: 10, width: '100%' },
  linkText: { fontSize: 11, color: '#065F46' },
});

export default StepShareModal;
