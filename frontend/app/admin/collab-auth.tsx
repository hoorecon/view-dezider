/**
 * Admin · Collaboration Verification
 * Toggle whether the advanced participant-verification methods
 * (DigiLocker / Biometric / Authenticator) are available in the
 * Group-Decisions create wizard. When OFF (default), session initiators
 * only see the simple WhatsApp-OTP / Email-OTP options.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

export default function AdminCollabAuthScreen() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [advancedEnabled, setAdvancedEnabled] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get('/collaboration/admin/auth-config');
      setAdvancedEnabled(!!r.data?.advanced_methods_enabled);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = async (next: boolean) => {
    setSaving(true);
    setAdvancedEnabled(next);
    try {
      await api.put('/collaboration/admin/auth-config', { advanced_methods_enabled: next });
    } catch (e: any) {
      setAdvancedEnabled(!next);
      showAlert('Error', e?.response?.data?.detail || 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#7C3AED', '#A855F7']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.header}>
        <TouchableOpacity onPress={() => safeBack('/admin')} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Collaboration Verification</Text>
          <Text style={s.headerSub}>Participant identity options</Text>
        </View>
        <Ionicons name="shield-checkmark" size={22} color="#FFF" />
      </LinearGradient>

      {loading ? (
        <View style={s.centered}><ActivityIndicator size="large" color="#7C3AED" /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16 }} showsVerticalScrollIndicator>
          <View style={s.card}>
            <View style={s.rowBetween}>
              <View style={{ flex: 1, paddingRight: 12 }}>
                <Text style={s.cardTitle}>Advanced verification methods</Text>
                <Text style={s.cardDesc}>
                  DigiLocker (Aadhaar / Country ID), Biometric and Authenticator (TOTP).
                  Enable only when these are fully configured on the backend.
                </Text>
              </View>
              <Switch
                value={advancedEnabled}
                onValueChange={toggle}
                disabled={saving}
                trackColor={{ true: '#7C3AED', false: '#D1D5DB' }}
                thumbColor="#FFF"
              />
            </View>
          </View>

          <View style={[s.banner, advancedEnabled ? s.bannerInfo : s.bannerOk]}>
            <Ionicons name={advancedEnabled ? 'information-circle' : 'checkmark-circle'} size={18} color={advancedEnabled ? '#1D4ED8' : '#059669'} />
            <Text style={[s.bannerTxt, { color: advancedEnabled ? '#1D4ED8' : '#065F46' }]}>
              {advancedEnabled
                ? 'Advanced methods are ON. Session initiators will see DigiLocker / Biometric / Authenticator in Step 5.'
                : 'Advanced methods are OFF (recommended). Initiators see WhatsApp OTP and/or Email OTP — and may skip verification entirely.'}
            </Text>
          </View>

          <View style={s.card}>
            <Text style={s.cardTitle}>Default: One-Time Passcode (OTP)</Text>
            <Text style={s.cardDesc}>
              When advanced methods are off, participants verify with a 6-digit code (valid 10 min)
              sent over WhatsApp or Email — using the contact details from your Contacts. The session
              initiator chooses which channel(s) to offer in Step 5; if none is selected, verification
              is skipped for that session.
            </Text>
            <View style={s.otpRow}>
              <View style={s.otpChip}><Ionicons name="logo-whatsapp" size={14} color="#059669" /><Text style={s.otpChipTxt}>WhatsApp OTP</Text></View>
              <View style={s.otpChip}><Ionicons name="mail" size={14} color="#3B82F6" /><Text style={s.otpChipTxt}>Email OTP</Text></View>
            </View>
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingTop: 12, paddingBottom: 18, gap: 12 },
  backBtn: { padding: 4 },
  headerTitle: { color: '#FFF', fontSize: 18, fontWeight: '800' },
  headerSub: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  card: { backgroundColor: '#FFF', borderRadius: 14, borderWidth: 1, borderColor: '#E5E7EB', padding: 16, marginBottom: 12 },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  cardTitle: { fontSize: 15, fontWeight: '700', color: '#111827', marginBottom: 6 },
  cardDesc: { fontSize: 13, color: '#6B7280', lineHeight: 19 },
  banner: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', padding: 12, borderRadius: 12, marginBottom: 12 },
  bannerOk: { backgroundColor: '#ECFDF5' },
  bannerInfo: { backgroundColor: '#EFF6FF' },
  bannerTxt: { flex: 1, fontSize: 12, lineHeight: 18, fontWeight: '600' },
  otpRow: { flexDirection: 'row', gap: 10, marginTop: 12 },
  otpChip: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#F3F4F6', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  otpChipTxt: { fontSize: 13, fontWeight: '600', color: '#374151' },
});
