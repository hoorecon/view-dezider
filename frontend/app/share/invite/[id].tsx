import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator, TextInput } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../src/utils/api';
import { VoiceTextInput } from '../../../src/components/VoiceTextInput';
import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * Invitee landing page for `/share/invite/[id]`.
 *
 * Flow:
 *   1. If not logged in → redirect to /auth/login?next=/share/invite/[id]
 *      (login page will return here after auth; new users go through normal
 *      signup with WhatsApp OTP verification then come back).
 *   2. Fetch invite, verify ownership / linkage.
 *   3. Render a per-field input (text + voice) for each field listed in the invite.
 *   4. Submit → status becomes `submitted` (or `submitted late`).
 */
export default function ShareInvitePage() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [invite, setInvite] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [responses, setResponses] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const fetchInvite = useCallback(async () => {
    setErr(null); setLoading(true);
    try {
      const token = await AsyncStorage.getItem('token');
      if (!token) { router.replace(`/auth/login?next=${encodeURIComponent('/share/invite/' + id)}` as any); return; }
      const { data } = await api.get(`/collab/invite/${id}`);
      setInvite(data.invite);
      const seed: Record<string, string> = {};
      (data.invite.fields || []).forEach((f: string) => { seed[f] = ''; });
      setResponses(seed);
    } catch (e: any) {
      if (e?.response?.status === 401) {
        router.replace(`/auth/login?next=${encodeURIComponent('/share/invite/' + id)}` as any); return;
      }
      setErr(e?.response?.data?.detail || 'Failed to load invite');
    } finally { setLoading(false); }
  }, [id, router]);

  useEffect(() => { if (id) fetchInvite(); }, [id, fetchInvite]);

  const submit = async () => {
    setSubmitting(true); setErr(null);
    try {
      await api.post(`/collab/invite/${id}/submit`, { submission: responses });
      setDone(true);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Submit failed');
    } finally { setSubmitting(false); }
  };

  if (loading) return <SafeAreaView style={s.center}><ActivityIndicator /></SafeAreaView>;
  if (err) return <SafeAreaView style={s.center}><Text style={s.err}>{err}</Text><TouchableOpacity onPress={fetchInvite} style={s.btn}><Text style={s.btnText}>Retry</Text></TouchableOpacity></SafeAreaView>;
  if (!invite) return null;

  const expired = invite.status === 'expired';
  const submitted = invite.status === 'submitted' || invite.status === 'merged' || done;

  return (
    <SafeAreaView style={s.wrap}>
      <ScrollView contentContainerStyle={{ padding: 20 }}>
        <View style={s.header}>
          <Ionicons name="share-social" size={22} color="#0EA5E9" />
          <Text style={s.title}>You’ve been invited</Text>
        </View>
        <Text style={s.subtitle}>
          <Text style={{ fontWeight: '700' }}>{invite.owner_name}</Text> invited you to contribute to:
        </Text>
        <Text style={s.stepLabel}>{invite.step_label}</Text>
        <Text style={s.moduleLabel}>in {invite.module_label}{invite.party_label ? ` — as ${invite.party_label}` : ''}</Text>
        {invite.message ? <View style={s.msgBox}><Text style={s.msg}>“{invite.message}”</Text></View> : null}
        <Text style={s.expiry}>Expires: {new Date(invite.expires_at).toLocaleString()}</Text>

        {expired && (
          <View style={s.warnBox}>
            <Ionicons name="warning" size={16} color="#B45309" />
            <Text style={s.warnText}>This invite has expired. Your input is still welcome as a late note — but won’t be auto-merged.</Text>
          </View>
        )}
        {submitted && (
          <View style={s.successBox}>
            <Ionicons name="checkmark-circle" size={20} color="#10B981" />
            <Text style={s.successText}>Submitted. The owner has been notified.</Text>
          </View>
        )}

        {!submitted && (
          <View style={{ marginTop: 20 }}>
            {(invite.fields || []).length === 0 && (
              <Text style={s.help}>The owner did not pin specific fields. Type any input you’d like to contribute below.</Text>
            )}
            {(invite.fields && invite.fields.length > 0 ? invite.fields : ['contribution']).map((f: string) => (
              <View key={f} style={{ marginBottom: 14 }}>
                <Text style={s.fieldLabel}>{f.replace(/_/g, ' ')}</Text>
                <VoiceTextInput
                  inputStyle={s.input}
                  multiline
                  placeholder="Type or speak your input..."
                  placeholderTextColor="#94A3B8"
                  value={responses[f] || ''}
                  onChangeText={(t) => setResponses(r => ({ ...r, [f]: t }))}
                  sessionId="" field={f} color="#0EA5E9" module="eg-generic"
                />
              </View>
            ))}
            <TouchableOpacity style={s.btn} onPress={submit} disabled={submitting}>
              {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={s.btnText}>Submit{expired ? ' (late note)' : ''}</Text>}
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#FFFFFF' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { fontSize: 22, fontWeight: '800', color: '#0F172A' },
  subtitle: { fontSize: 14, color: '#475569', marginTop: 14 },
  stepLabel: { fontSize: 18, fontWeight: '700', color: '#0F172A', marginTop: 8 },
  moduleLabel: { fontSize: 13, color: '#64748B', marginTop: 4 },
  msgBox: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, marginTop: 14, borderWidth: 1, borderColor: '#E2E8F0' },
  msg: { fontSize: 13, color: '#475569', fontStyle: 'italic' },
  expiry: { fontSize: 12, color: '#64748B', marginTop: 8 },
  warnBox: { flexDirection: 'row', gap: 8, alignItems: 'center', backgroundColor: '#FFFBEB', borderRadius: 10, padding: 10, marginTop: 14, borderWidth: 1, borderColor: '#FCD34D' },
  warnText: { flex: 1, fontSize: 12, color: '#92400E' },
  successBox: { flexDirection: 'row', gap: 8, alignItems: 'center', backgroundColor: '#F0FDF4', borderRadius: 10, padding: 12, marginTop: 16, borderWidth: 1, borderColor: '#86EFAC' },
  successText: { fontSize: 13, color: '#065F46', fontWeight: '600' },
  fieldLabel: { fontSize: 13, fontWeight: '700', color: '#0F172A', marginBottom: 6, textTransform: 'capitalize' },
  input: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A', minHeight: 80, textAlignVertical: 'top' },
  help: { fontSize: 12, color: '#64748B', marginBottom: 10 },
  err: { fontSize: 14, color: '#DC2626', marginBottom: 14, textAlign: 'center' },
  btn: { backgroundColor: '#003087', borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 6 },
  btnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
});
