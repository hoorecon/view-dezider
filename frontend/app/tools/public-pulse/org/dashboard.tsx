import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../../src/constants/colors';
import api from '../../../../src/utils/api';
import { safeBack } from '../../../../src/utils/navigation';

export default function OrgDashboard() {
  const router = useRouter();
  const { orgId } = useLocalSearchParams<{ orgId: string }>();
  const [org, setOrg] = useState<any>(null);
  const [dash, setDash] = useState<any>(null);
  const [feedbackCount, setFeedbackCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    if (!orgId) return;
    try {
      const [orgRes, dashRes, queueRes] = await Promise.all([
        api.get(`/public-pulse/orgs/${orgId}`),
        api.get(`/public-pulse/orgs/${orgId}/dashboard`),
        api.get(`/public-pulse/orgs/${orgId}/feedback/queue`),
      ]);
      setOrg(orgRes.data);
      setDash(dashRes.data);
      setFeedbackCount(queueRes.data.count || 0);
    } catch (e) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { setLoading(true); load(); }, [orgId]));

  if (loading || !org) {
    return <SafeAreaView style={styles.container}><ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 64 }} /></SafeAreaView>;
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={{ paddingBottom: 40 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => safeBack(router)}>
            <Ionicons name="chevron-back" size={28} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle} numberOfLines={1}>{org.display_name}</Text>
          <View style={{ width: 28 }} />
        </View>

        <View style={styles.orgBanner}>
          <Ionicons name="business" size={28} color={COLORS.primary} />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={styles.orgType}>{org.org_type?.replace('_', ' ').toUpperCase()}</Text>
            {org.district && <Text style={styles.orgLoc}>{org.district}</Text>}
            <Text style={styles.orgRole}>Your role: {org.my_role || 'member'}</Text>
          </View>
        </View>

        {/* Action cards */}
        <View style={styles.cardsRow}>
          <TouchableOpacity
            style={styles.actionCard}
            onPress={() => router.push(`/tools/public-pulse/org/feedback-queue?orgId=${orgId}` as any)}
          >
            <Ionicons name="mail-unread" size={22} color="#F59E0B" />
            <Text style={styles.actionCount}>{feedbackCount}</Text>
            <Text style={styles.actionLabel}>Feedback Queue</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.actionCard}
            onPress={() => router.push(`/tools/public-pulse/org/members?orgId=${orgId}` as any)}
          >
            <Ionicons name="people" size={22} color={COLORS.primary} />
            <Text style={styles.actionCount}>{org.active_member_count || 1}</Text>
            <Text style={styles.actionLabel}>Members</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.actionCard}
            onPress={() => {}}
          >
            <Ionicons name="checkmark-done" size={22} color="#10B981" />
            <Text style={styles.actionCount}>{org.total_feedback_handled || 0}</Text>
            <Text style={styles.actionLabel}>Resolved</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.section}>Aggregate Insights (anonymized)</Text>
        {dash?.blocked ? (
          <View style={styles.blockedCard}>
            <Ionicons name="lock-closed" size={24} color="#9CA3AF" />
            <Text style={styles.blockedTxt}>{dash.reason || 'Insufficient sample size'}</Text>
            <Text style={styles.blockedHint}>k-threshold: {dash.k_threshold}</Text>
          </View>
        ) : dash?.aggregates ? (
          <View>
            <Text style={styles.aggMeta}>
              Based on {dash.total_in_aggregate} responses
              {dash.filter?.district ? ` from ${dash.filter.district}` : ''}
              {dash.filter?.age_group ? ` (age ${dash.filter.age_group})` : ''}
            </Text>
            {Object.entries(dash.aggregates).map(([key, rows]: any) =>
              rows && rows.length > 0 ? (
                <View key={key} style={styles.aggBlock}>
                  <Text style={styles.aggTitle}>{titleize(key)}</Text>
                  {rows.slice(0, 6).map((r: any, i: number) => {
                    const pct = dash.total_in_aggregate ? Math.round((r.count / dash.total_in_aggregate) * 100) : 0;
                    return (
                      <View key={i} style={styles.row}>
                        <Text style={styles.rowLabel}>{labelize(r.label)}</Text>
                        <View style={styles.barWrap}>
                          <View style={[styles.barFill, { width: `${pct}%` }]} />
                        </View>
                        <Text style={styles.rowCount}>{pct}%</Text>
                      </View>
                    );
                  })}
                </View>
              ) : null,
            )}
          </View>
        ) : null}

        <View style={styles.privacyCard}>
          <Ionicons name="shield-checkmark" size={16} color="#10B981" />
          <Text style={styles.privacyTxt}>
            Only aggregates above k-threshold shown. Individual responses are never shared.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const titleize = (s: string) => s.replace('by_', '').split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
const labelize = (s: string) => typeof s === 'string' ? s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : s;

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: COLORS.text, marginHorizontal: 12, textAlign: 'center' },
  orgBanner: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#EEF2FF', padding: 16, margin: 16, borderRadius: 14 },
  orgType: { fontSize: 11, color: COLORS.primary, fontWeight: '700', letterSpacing: 1 },
  orgLoc: { fontSize: 13, color: COLORS.text, marginTop: 2 },
  orgRole: { fontSize: 11, color: '#6B7280', marginTop: 4 },
  cardsRow: { flexDirection: 'row', gap: 10, paddingHorizontal: 16, marginBottom: 16 },
  actionCard: { flex: 1, backgroundColor: '#FFF', borderRadius: 12, padding: 14, alignItems: 'center' },
  actionCount: { fontSize: 22, fontWeight: '800', color: COLORS.text, marginTop: 6 },
  actionLabel: { fontSize: 11, color: '#6B7280', marginTop: 2, textAlign: 'center' },
  section: { fontSize: 15, fontWeight: '700', color: COLORS.text, paddingHorizontal: 16, marginTop: 8, marginBottom: 12 },
  aggMeta: { fontSize: 11, color: '#6B7280', paddingHorizontal: 16, marginBottom: 12, fontStyle: 'italic' },
  aggBlock: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginHorizontal: 16, marginBottom: 10 },
  aggTitle: { fontSize: 13, fontWeight: '700', color: COLORS.text, marginBottom: 10 },
  row: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  rowLabel: { fontSize: 12, color: COLORS.text, width: 90 },
  barWrap: { flex: 1, height: 8, backgroundColor: '#E5E7EB', borderRadius: 4, marginHorizontal: 8, overflow: 'hidden' },
  barFill: { height: '100%', backgroundColor: COLORS.primary, borderRadius: 4 },
  rowCount: { fontSize: 11, color: '#6B7280', width: 36, textAlign: 'right' },
  blockedCard: { alignItems: 'center', backgroundColor: '#FFF', padding: 24, marginHorizontal: 16, borderRadius: 12 },
  blockedTxt: { fontSize: 13, color: '#6B7280', marginTop: 8 },
  blockedHint: { fontSize: 11, color: '#9CA3AF', marginTop: 4 },
  privacyCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#ECFDF5', padding: 10, margin: 16, borderRadius: 8, gap: 8 },
  privacyTxt: { flex: 1, fontSize: 11, color: '#065F46' },
});
