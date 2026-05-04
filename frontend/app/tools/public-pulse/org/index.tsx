import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../../src/constants/colors';
import api from '../../../../src/utils/api';

const STATUS_COLOR: Record<string, string> = {
  pending: '#F59E0B',
  approved: '#10B981',
  rejected: '#EF4444',
  suspended: '#6B7280',
};

export default function OrgHome() {
  const router = useRouter();
  const [myOrgs, setMyOrgs] = useState<any[]>([]);
  const [myApps, setMyApps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const [orgsRes, appsRes] = await Promise.all([
        api.get('/public-pulse/orgs/my-orgs'),
        api.get('/public-pulse/orgs/my-applications'),
      ]);
      setMyOrgs(orgsRes.data.orgs || []);
      setMyApps(appsRes.data.applications || []);
    } catch (e) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { setLoading(true); load(); }, []));

  if (loading) {
    return <SafeAreaView style={styles.container}><ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 64 }} /></SafeAreaView>;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={28} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Org / Gov Portal</Text>
          <View style={{ width: 28 }} />
        </View>

        {/* My verified orgs */}
        {myOrgs.length > 0 ? (
          <>
            <Text style={styles.section}>My Organizations</Text>
            {myOrgs.map((o) => (
              <TouchableOpacity
                key={o.org_id}
                style={styles.orgCard}
                onPress={() => router.push(`/tools/public-pulse/org/dashboard?orgId=${o.org_id}` as any)}
              >
                <View style={styles.orgIcon}><Ionicons name="business" size={22} color={COLORS.primary} /></View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.orgName}>{o.display_name}</Text>
                  <Text style={styles.orgMeta}>{o.org_type.replace('_', ' ').toUpperCase()} · {o.my_role}</Text>
                  {o.district && <Text style={styles.orgMeta}>{o.district}</Text>}
                </View>
                <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
              </TouchableOpacity>
            ))}
          </>
        ) : (
          <View style={styles.emptyCard}>
            <Ionicons name="business-outline" size={32} color="#9CA3AF" />
            <Text style={styles.emptyTitle}>No verified organization yet</Text>
            <Text style={styles.emptyTxt}>Apply to register your NGO / MSME / Govt dept / other</Text>
          </View>
        )}

        {/* Apply button */}
        <TouchableOpacity
          style={styles.applyBtn}
          onPress={() => router.push('/tools/public-pulse/org/apply' as any)}
        >
          <Ionicons name="add-circle" size={22} color="#FFF" />
          <Text style={styles.applyBtnTxt}>Apply to register a new Org</Text>
        </TouchableOpacity>

        {/* My applications */}
        {myApps.length > 0 && (
          <>
            <Text style={styles.section}>My Applications</Text>
            {myApps.map((a) => (
              <View key={a.application_id} style={styles.appCard}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.appName}>{a.display_name}</Text>
                  <Text style={styles.appMeta}>{a.org_type.replace('_', ' ')} · Submitted {new Date(a.submitted_at).toLocaleDateString()}</Text>
                  {a.rejection_reason && <Text style={styles.rejectTxt}>Reason: {a.rejection_reason}</Text>}
                </View>
                <View style={[styles.statusPill, { backgroundColor: `${STATUS_COLOR[a.status]}20` }]}>
                  <Text style={[styles.statusTxt, { color: STATUS_COLOR[a.status] }]}>{a.status.toUpperCase()}</Text>
                </View>
              </View>
            ))}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  section: { fontSize: 14, fontWeight: '700', color: COLORS.text, marginVertical: 12, marginTop: 20 },
  orgCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 10 },
  orgIcon: { width: 44, height: 44, borderRadius: 22, backgroundColor: '#EEF2FF', alignItems: 'center', justifyContent: 'center', marginRight: 12 },
  orgName: { fontSize: 15, fontWeight: '700', color: COLORS.text },
  orgMeta: { fontSize: 12, color: '#6B7280', marginTop: 2 },
  emptyCard: { alignItems: 'center', backgroundColor: '#FFF', padding: 24, borderRadius: 12, marginVertical: 12 },
  emptyTitle: { fontSize: 15, fontWeight: '700', color: COLORS.text, marginTop: 12 },
  emptyTxt: { fontSize: 13, color: '#6B7280', marginTop: 4, textAlign: 'center' },
  applyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.primary, padding: 14, borderRadius: 12, gap: 8, marginTop: 8 },
  applyBtnTxt: { color: '#FFF', fontSize: 14, fontWeight: '700' },
  appCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 8 },
  appName: { fontSize: 14, fontWeight: '700', color: COLORS.text },
  appMeta: { fontSize: 11, color: '#6B7280', marginTop: 2 },
  rejectTxt: { fontSize: 11, color: '#EF4444', marginTop: 4 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  statusTxt: { fontSize: 10, fontWeight: '700' },
});
