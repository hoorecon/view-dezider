import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../../src/constants/colors';
import api from '../../../../src/utils/api';
import { showAlert } from '../../../../src/utils/alert';

type OrgType = { code: string; label: string; icon: string };

export default function OrgApplyScreen() {
  const router = useRouter();
  const [types, setTypes] = useState<OrgType[]>([]);
  const [orgType, setOrgType] = useState('ngo');
  const [displayName, setDisplayName] = useState('');
  const [legalName, setLegalName] = useState('');
  const [about, setAbout] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [state, setState] = useState('');
  const [district, setDistrict] = useState('');
  const [categoriesInput, setCategoriesInput] = useState('');
  const [eligible, setEligible] = useState<boolean | null>(null);
  const [blockers, setBlockers] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get('/public-pulse/orgs/types').then((r) => setTypes(r.data.types || [])).catch(() => {});
  }, []);

  useEffect(() => {
    api.get(`/public-pulse/orgs/eligibility/${orgType}`).then((r) => {
      setEligible(r.data.eligible);
      setBlockers(r.data.blockers || []);
    }).catch(() => setEligible(null));
  }, [orgType]);

  const submit = async () => {
    if (!displayName.trim() || !email.trim()) {
      showAlert('Required', 'Display name and email are required');
      return;
    }
    setSubmitting(true);
    try {
      const categories = categoriesInput.split(',').map((c) => c.trim()).filter(Boolean);
      await api.post('/public-pulse/orgs/apply', {
        org_type: orgType,
        display_name: displayName,
        legal_name: legalName || undefined,
        about: about || undefined,
        website: website || undefined,
        email,
        phone: phone || undefined,
        state: state || undefined,
        district: district || undefined,
        categories,
      });
      showAlert('Submitted', 'Your application is in the admin queue. You will be notified when reviewed.');
      router.replace('/tools/public-pulse/org' as any);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (typeof detail === 'object' && detail?.blockers) {
        showAlert('Not eligible', detail.blockers.join('\n'));
      } else {
        showAlert('Error', typeof detail === 'string' ? detail : 'Failed to submit');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={28} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Apply to Register Org</Text>
          <View style={{ width: 28 }} />
        </View>

        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          <Text style={styles.label}>Organization type</Text>
          <View style={styles.typeGrid}>
            {types.map((t) => {
              const sel = orgType === t.code;
              return (
                <TouchableOpacity
                  key={t.code}
                  style={[styles.typeBtn, sel && styles.typeBtnSel]}
                  onPress={() => setOrgType(t.code)}
                >
                  <Ionicons name={t.icon as any} size={20} color={sel ? '#FFF' : COLORS.primary} />
                  <Text style={[styles.typeTxt, sel && { color: '#FFF' }]}>{t.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {eligible === false && blockers.length > 0 && (
            <View style={styles.blockerBanner}>
              <Ionicons name="warning" size={20} color="#DC2626" />
              <View style={{ flex: 1, marginLeft: 8 }}>
                <Text style={styles.blockerTitle}>Not eligible for this org type</Text>
                {blockers.map((b, i) => (
                  <Text key={i} style={styles.blockerItem}>• {b}</Text>
                ))}
              </View>
            </View>
          )}

          <Text style={styles.label}>Display name *</Text>
          <TextInput style={styles.input} value={displayName} onChangeText={setDisplayName} placeholder="E.g., Coimbatore Skills Foundation" placeholderTextColor="#9CA3AF" />

          <Text style={styles.label}>Legal name</Text>
          <TextInput style={styles.input} value={legalName} onChangeText={setLegalName} placeholder="Registered legal name (optional)" placeholderTextColor="#9CA3AF" />

          <Text style={styles.label}>Short pitch / what you do</Text>
          <TextInput style={[styles.input, { minHeight: 80, textAlignVertical: 'top' }]} value={about} onChangeText={setAbout} placeholder="2-3 sentences on your mission" placeholderTextColor="#9CA3AF" multiline />

          <Text style={styles.label}>Official email *</Text>
          <TextInput style={styles.input} value={email} onChangeText={setEmail} placeholder="info@yourorg.org" placeholderTextColor="#9CA3AF" keyboardType="email-address" autoCapitalize="none" />

          <Text style={styles.label}>Phone</Text>
          <TextInput style={styles.input} value={phone} onChangeText={setPhone} placeholder="+91 ..." placeholderTextColor="#9CA3AF" keyboardType="phone-pad" />

          <Text style={styles.label}>Website</Text>
          <TextInput style={styles.input} value={website} onChangeText={setWebsite} placeholder="https://..." placeholderTextColor="#9CA3AF" autoCapitalize="none" />

          <View style={styles.row}>
            <View style={{ flex: 1, marginRight: 8 }}>
              <Text style={styles.label}>State</Text>
              <TextInput style={styles.input} value={state} onChangeText={setState} placeholder="Tamil Nadu" placeholderTextColor="#9CA3AF" />
            </View>
            <View style={{ flex: 1, marginLeft: 8 }}>
              <Text style={styles.label}>District</Text>
              <TextInput style={styles.input} value={district} onChangeText={setDistrict} placeholder="Coimbatore" placeholderTextColor="#9CA3AF" />
            </View>
          </View>

          <Text style={styles.label}>Categories (comma-separated)</Text>
          <TextInput
            style={styles.input}
            value={categoriesInput}
            onChangeText={setCategoriesInput}
            placeholder="education, skills, employment"
            placeholderTextColor="#9CA3AF"
          />
          <Text style={styles.hint}>Used for auto-routing feedback + filtering on org dashboard</Text>

          <View style={styles.noticeCard}>
            <Ionicons name="information-circle" size={18} color="#3B82F6" />
            <Text style={styles.noticeTxt}>
              An admin will review your application (typically within 2-3 business days). You'll be notified by in-app notification.
            </Text>
          </View>

          <TouchableOpacity
            style={[styles.submitBtn, (!eligible || submitting) && { opacity: 0.5 }]}
            onPress={submit}
            disabled={!eligible || submitting}
          >
            {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={styles.submitTxt}>Submit Application</Text>}
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  label: { fontSize: 13, fontWeight: '600', color: COLORS.text, marginTop: 16, marginBottom: 8 },
  input: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, padding: 12, fontSize: 14, color: COLORS.text },
  hint: { fontSize: 11, color: '#6B7280', marginTop: 4 },
  typeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  typeBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 16, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#D1D5DB' },
  typeBtnSel: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  typeTxt: { fontSize: 12, color: COLORS.text, fontWeight: '600' },
  blockerBanner: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#FEE2E2', padding: 14, borderRadius: 12, marginTop: 16, borderWidth: 1, borderColor: '#FCA5A5' },
  blockerTitle: { fontSize: 13, fontWeight: '700', color: '#991B1B' },
  blockerItem: { fontSize: 12, color: '#991B1B', marginTop: 4 },
  noticeCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#EFF6FF', padding: 12, borderRadius: 10, marginTop: 16, gap: 10, borderWidth: 1, borderColor: '#BFDBFE' },
  noticeTxt: { flex: 1, fontSize: 12, color: '#1E40AF', lineHeight: 16 },
  row: { flexDirection: 'row' },
  submitBtn: { backgroundColor: COLORS.primary, padding: 16, borderRadius: 12, alignItems: 'center', marginTop: 20 },
  submitTxt: { color: '#FFF', fontSize: 15, fontWeight: '700' },
});
