import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Switch, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../src/constants/colors';
import api from '../../../src/utils/api';
import { showAlert } from '../../../src/utils/alert';

type Purpose = { code: string; label: string; description: string; default: boolean };

export default function ConsentScreen() {
  const router = useRouter();
  const [purposes, setPurposes] = useState<Purpose[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [version, setVersion] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const [optsRes, mineRes] = await Promise.all([
          api.get('/public-pulse/consent/options'),
          api.get('/public-pulse/consent/me').catch(() => ({ data: { active: false } })),
        ]);
        setPurposes(optsRes.data.purposes || []);
        setVersion(optsRes.data.version || '');
        const initial: Record<string, boolean> = {};
        for (const p of optsRes.data.purposes) {
          initial[p.code] = mineRes.data?.purposes?.[p.code] ?? p.default;
        }
        setSelected(initial);
      } catch (e) {
        showAlert('Error', 'Failed to load consent options');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const submit = async () => {
    setSaving(true);
    try {
      await api.post('/public-pulse/consent', {
        purposes: selected,
        data_categories_allowed: ['demographics', 'tool_answers', 'feedback'],
      });
      router.replace('/tools/public-pulse' as any);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to save consent');
    } finally {
      setSaving(false);
    }
  };

  const withdraw = async () => {
    setSaving(true);
    try {
      await api.post('/public-pulse/consent/withdraw');
      showAlert('Done', 'Your consent has been withdrawn. You will no longer be included in research.');
      router.back();
    } catch (e) {
      showAlert('Error', 'Failed to withdraw');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <SafeAreaView style={styles.container}><ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 64 }} /></SafeAreaView>;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={28} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Your Data Preferences</Text>
          <View style={{ width: 28 }} />
        </View>

        <View style={styles.intro}>
          <Ionicons name="shield-checkmark" size={28} color="#10B981" />
          <Text style={styles.introTitle}>You're always in control</Text>
          <Text style={styles.introText}>
            We ask only what improves YOUR decision clarity. You can change or withdraw consent
            anytime, and your individual responses are never shared — only anonymized aggregates.
          </Text>
        </View>

        {purposes.map((p) => (
          <View key={p.code} style={styles.purposeCard}>
            <View style={{ flex: 1, marginRight: 12 }}>
              <Text style={styles.purposeLabel}>{p.label}</Text>
              <Text style={styles.purposeDesc}>{p.description}</Text>
            </View>
            <Switch
              value={selected[p.code] || false}
              onValueChange={(v) => setSelected({ ...selected, [p.code]: v })}
              thumbColor={selected[p.code] ? '#FFF' : '#FFF'}
              trackColor={{ false: '#D1D5DB', true: '#10B981' }}
            />
          </View>
        ))}

        <Text style={styles.versionTxt}>Consent version: {version}</Text>

        <TouchableOpacity style={styles.primaryBtn} onPress={submit} disabled={saving}>
          {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.primaryBtnTxt}>Save Preferences</Text>}
        </TouchableOpacity>

        <TouchableOpacity style={styles.withdrawBtn} onPress={withdraw} disabled={saving}>
          <Text style={styles.withdrawTxt}>Withdraw all consent</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  intro: { backgroundColor: '#ECFDF5', padding: 16, borderRadius: 14, marginBottom: 20, borderWidth: 1, borderColor: '#A7F3D0' },
  introTitle: { fontSize: 16, fontWeight: '700', color: '#065F46', marginTop: 8 },
  introText: { fontSize: 13, color: '#065F46', marginTop: 6, lineHeight: 19 },
  purposeCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF',
    borderRadius: 12, padding: 16, marginBottom: 10,
  },
  purposeLabel: { fontSize: 14, fontWeight: '700', color: COLORS.text },
  purposeDesc: { fontSize: 12, color: '#6B7280', marginTop: 4, lineHeight: 17 },
  versionTxt: { fontSize: 11, color: '#9CA3AF', textAlign: 'center', marginTop: 16 },
  primaryBtn: { backgroundColor: COLORS.primary, borderRadius: 12, padding: 16, alignItems: 'center', marginTop: 16 },
  primaryBtnTxt: { color: '#FFF', fontSize: 15, fontWeight: '700' },
  withdrawBtn: { padding: 16, alignItems: 'center', marginTop: 8 },
  withdrawTxt: { color: '#EF4444', fontSize: 13, fontWeight: '600' },
});
