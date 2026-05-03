import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, RefreshControl, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';

const API = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL
  || process.env.EXPO_PUBLIC_BACKEND_URL
  || '';

const COLORS = {
  bg: '#0F172A',
  card: '#1E293B',
  cardAlt: '#1A2332',
  accent: '#8B5CF6',
  accentLight: '#A78BFA',
  border: '#334155',
  textPrimary: '#F1F5F9',
  textSecondary: '#94A3B8',
  textMuted: '#64748B',
  full: '#22C55E',
  read: '#3B82F6',
  locked: '#F59E0B',
  hidden: '#6B7280',
  quotaExceeded: '#EF4444',
  success: '#10B981',
  error: '#EF4444',
};

const ACCESS_ICONS: Record<string, { icon: string; color: string; label: string }> = {
  full: { icon: 'checkmark-circle', color: COLORS.full, label: 'Full' },
  read: { icon: 'eye', color: COLORS.read, label: 'Read' },
  locked: { icon: 'lock-closed', color: COLORS.locked, label: 'Locked' },
  hidden: { icon: 'eye-off', color: COLORS.hidden, label: 'Hidden' },
};

const USER_TYPE_LABELS: Record<string, { short: string; color: string }> = {
  unit_tester: { short: 'UT', color: '#EF4444' },
  integration_tester: { short: 'IT', color: '#F97316' },
  alpha: { short: 'α', color: '#8B5CF6' },
  beta: { short: 'β', color: '#06B6D4' },
  free: { short: 'FREE', color: '#6B7280' },
  trial: { short: 'TRIAL', color: '#F59E0B' },
  paid_starter: { short: 'S', color: '#10B981' },
  paid_pro: { short: 'PRO', color: '#3B82F6' },
  paid_enterprise: { short: 'ENT', color: '#8B5CF6' },
  paid_api: { short: 'API', color: '#EC4899' },
};

interface Feature {
  feature_id: string;
  feature_name: string;
  release_stage: string;
  quota_unit: string;
  quota_resets: string;
  access: Record<string, { level: string; quota: number }>;
}

interface Module {
  module_id: string;
  module_name: string;
  module_icon: string;
  module_description: string;
  order: number;
  features: Feature[];
}

interface MatrixData {
  modules: Module[];
  user_types: { id: string; name: string; description: string }[];
  subscription_plans: { id: string; name: string }[];
  release_stages: string[];
  total_modules: number;
  total_features: number;
}

export default function ACMAdminScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [matrix, setMatrix] = useState<MatrixData | null>(null);
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null);
  const [error, setError] = useState('');

  const accessKeys = [
    'unit_tester', 'integration_tester', 'alpha', 'beta',
    'free', 'trial', 'paid_starter', 'paid_pro', 'paid_enterprise', 'paid_api',
  ];

  const getHeaders = async () => {
    const token = await AsyncStorage.getItem('session_token');
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  };

  const fetchMatrix = useCallback(async () => {
    try {
      const headers = await getHeaders();
      const resp = await fetch(`${API}/api/acm/matrix`, { headers });
      if (resp.ok) {
        const data = await resp.json();
        setMatrix(data);
        setError('');
      } else {
        const err = await resp.json().catch(() => ({}));
        setError(err.detail || 'Failed to load ACM matrix');
      }
    } catch (e: any) {
      setError(e.message || 'Network error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const seedACM = async (force = false) => {
    try {
      setLoading(true);
      const headers = await getHeaders();
      const resp = await fetch(`${API}/api/acm/seed?force=${force}`, {
        method: 'POST', headers,
      });
      const data = await resp.json();
      if (resp.ok) {
        Alert.alert('Success', `ACM seeded: ${data.modules} modules, ${data.features} features`);
        await fetchMatrix();
      } else {
        Alert.alert('Error', data.detail || 'Seed failed');
      }
    } catch (e: any) {
      Alert.alert('Error', e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMatrix();
  }, []);

  const toggleModule = (moduleId: string) => {
    setExpandedModules((prev) => {
      const next = new Set(prev);
      if (next.has(moduleId)) next.delete(moduleId);
      else next.add(moduleId);
      return next;
    });
  };

  const renderAccessCell = (access: { level: string; quota: number } | undefined) => {
    const rule = access || { level: 'hidden', quota: 0 };
    const config = ACCESS_ICONS[rule.level] || ACCESS_ICONS.hidden;

    return (
      <View style={[styles.accessCell, { borderColor: config.color + '40' }]}>
        <Ionicons name={config.icon as any} size={12} color={config.color} />
        {rule.quota > 0 && rule.level === 'full' && (
          <Text style={[styles.quotaText, { color: config.color }]}>{rule.quota}</Text>
        )}
        {rule.quota === -1 && rule.level === 'full' && (
          <Text style={[styles.quotaText, { color: config.color }]}>∞</Text>
        )}
      </View>
    );
  };

  const renderFeatureRow = (feature: Feature) => {
    return (
      <TouchableOpacity
        key={feature.feature_id}
        style={styles.featureRow}
        onPress={() => setSelectedFeature(selectedFeature?.feature_id === feature.feature_id ? null : feature)}
        activeOpacity={0.7}
      >
        <View style={styles.featureNameCol}>
          <Text style={styles.featureName} numberOfLines={2}>{feature.feature_name}</Text>
          <Text style={styles.featureQuotaUnit}>{feature.quota_unit}</Text>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.accessCells}>
          {accessKeys.map((key) => (
            <View key={key} style={styles.cellWrapper}>
              {renderAccessCell(feature.access[key])}
            </View>
          ))}
        </ScrollView>
      </TouchableOpacity>
    );
  };

  const renderFeatureDetail = (feature: Feature) => {
    if (selectedFeature?.feature_id !== feature.feature_id) return null;

    return (
      <View style={styles.detailPanel}>
        <View style={styles.detailHeader}>
          <Ionicons name="information-circle" size={16} color={COLORS.accentLight} />
          <Text style={styles.detailTitle}>{feature.feature_name}</Text>
        </View>
        <View style={styles.detailMeta}>
          <View style={styles.metaPill}>
            <Text style={styles.metaLabel}>Stage</Text>
            <Text style={styles.metaValue}>{feature.release_stage}</Text>
          </View>
          <View style={styles.metaPill}>
            <Text style={styles.metaLabel}>Quota</Text>
            <Text style={styles.metaValue}>{feature.quota_unit}</Text>
          </View>
          <View style={styles.metaPill}>
            <Text style={styles.metaLabel}>Resets</Text>
            <Text style={styles.metaValue}>{feature.quota_resets}</Text>
          </View>
        </View>
        <View style={styles.detailGrid}>
          {accessKeys.map((key) => {
            const rule = feature.access[key] || { level: 'hidden', quota: 0 };
            const cfg = ACCESS_ICONS[rule.level] || ACCESS_ICONS.hidden;
            const label = USER_TYPE_LABELS[key] || { short: key, color: '#999' };
            return (
              <View key={key} style={styles.detailCell}>
                <View style={[styles.typeBadge, { backgroundColor: label.color + '20', borderColor: label.color + '60' }]}>
                  <Text style={[styles.typeBadgeText, { color: label.color }]}>{label.short}</Text>
                </View>
                <Ionicons name={cfg.icon as any} size={14} color={cfg.color} />
                <Text style={[styles.detailLevel, { color: cfg.color }]}>{cfg.label}</Text>
                <Text style={styles.detailQuota}>
                  {rule.quota === -1 ? '∞' : rule.quota === 0 ? '—' : rule.quota}
                </Text>
              </View>
            );
          })}
        </View>
      </View>
    );
  };

  if (loading && !matrix) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.accent} style={{ marginTop: 100 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>WOWO — Access Control Matrix</Text>
          <Text style={styles.headerSub}>
            {matrix ? `${matrix.total_modules} Modules · ${matrix.total_features} Features` : 'Loading...'}
          </Text>
        </View>
        <TouchableOpacity
          onPress={() => Alert.alert(
            'Seed ACM',
            'Seed default ACM data?',
            [
              { text: 'Cancel', style: 'cancel' },
              { text: 'Seed (Keep)', onPress: () => seedACM(false) },
              { text: 'Force Re-seed', onPress: () => seedACM(true), style: 'destructive' },
            ]
          )}
          style={styles.seedBtn}
        >
          <Ionicons name="cloud-download" size={20} color={COLORS.accent} />
        </TouchableOpacity>
      </View>

      {error ? (
        <View style={styles.errorBanner}>
          <Ionicons name="alert-circle" size={16} color={COLORS.error} />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity onPress={() => seedACM(false)}>
            <Text style={styles.errorAction}>Seed Now</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {/* Legend */}
      <View style={styles.legend}>
        {Object.entries(ACCESS_ICONS).map(([key, val]) => (
          <View key={key} style={styles.legendItem}>
            <Ionicons name={val.icon as any} size={12} color={val.color} />
            <Text style={[styles.legendLabel, { color: val.color }]}>{val.label}</Text>
          </View>
        ))}
      </View>

      {/* Column Headers */}
      <View style={styles.colHeaders}>
        <View style={styles.featureNameCol}>
          <Text style={styles.colHeaderText}>Feature</Text>
        </View>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.accessCells}>
          {accessKeys.map((key) => {
            const label = USER_TYPE_LABELS[key] || { short: key, color: '#999' };
            return (
              <View key={key} style={styles.cellWrapper}>
                <View style={[styles.colHeaderBadge, { backgroundColor: label.color + '20' }]}>
                  <Text style={[styles.colHeaderBadgeText, { color: label.color }]}>{label.short}</Text>
                </View>
              </View>
            );
          })}
        </ScrollView>
      </View>

      {/* Matrix */}
      <ScrollView
        style={{ flex: 1 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); fetchMatrix(); }}
            tintColor={COLORS.accent}
          />
        }
      >
        {matrix?.modules.map((mod) => (
          <View key={mod.module_id} style={styles.moduleCard}>
            <TouchableOpacity
              style={styles.moduleHeader}
              onPress={() => toggleModule(mod.module_id)}
              activeOpacity={0.7}
            >
              <Ionicons name={(mod.module_icon || 'apps') as any} size={18} color={COLORS.accentLight} />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={styles.moduleName}>{mod.module_name}</Text>
                <Text style={styles.moduleFeatureCount}>{mod.features.length} features</Text>
              </View>
              <Ionicons
                name={expandedModules.has(mod.module_id) ? 'chevron-up' : 'chevron-down'}
                size={18}
                color={COLORS.textMuted}
              />
            </TouchableOpacity>

            {expandedModules.has(mod.module_id) && (
              <View style={styles.featuresContainer}>
                {mod.features.map((feat) => (
                  <View key={feat.feature_id}>
                    {renderFeatureRow(feat)}
                    {renderFeatureDetail(feat)}
                  </View>
                ))}
              </View>
            )}
          </View>
        ))}

        <View style={{ height: 100 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  backBtn: { marginRight: 12, padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  headerSub: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  seedBtn: {
    padding: 8, borderRadius: 8,
    backgroundColor: COLORS.accent + '20',
  },
  errorBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 16, paddingVertical: 10,
    backgroundColor: COLORS.error + '15',
    borderBottomWidth: 1, borderBottomColor: COLORS.error + '30',
  },
  errorText: { flex: 1, fontSize: 13, color: COLORS.error },
  errorAction: { fontSize: 13, fontWeight: '700', color: COLORS.accent },
  legend: {
    flexDirection: 'row', gap: 16,
    paddingHorizontal: 16, paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendLabel: { fontSize: 11, fontWeight: '600' },
  colHeaders: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 6,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
    backgroundColor: COLORS.cardAlt,
  },
  colHeaderText: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted, textTransform: 'uppercase' },
  colHeaderBadge: {
    paddingHorizontal: 4, paddingVertical: 2,
    borderRadius: 4, alignItems: 'center',
  },
  colHeaderBadgeText: { fontSize: 9, fontWeight: '800' },
  featureNameCol: { width: 130, paddingRight: 8 },
  accessCells: { flexDirection: 'row' },
  cellWrapper: { width: 36, alignItems: 'center', justifyContent: 'center' },
  accessCell: {
    width: 30, height: 30, borderRadius: 6,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 1,
    backgroundColor: COLORS.bg + '80',
  },
  quotaText: { fontSize: 8, fontWeight: '800', marginTop: 1 },
  moduleCard: {
    marginHorizontal: 8, marginTop: 8,
    borderRadius: 10, borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.card,
    overflow: 'hidden',
  },
  moduleHeader: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 14, paddingVertical: 12,
  },
  moduleName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  moduleFeatureCount: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  featuresContainer: {
    borderTopWidth: 1, borderTopColor: COLORS.border,
    paddingBottom: 4,
  },
  featureRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 14, paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: COLORS.border + '60',
  },
  featureName: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  featureQuotaUnit: { fontSize: 10, color: COLORS.textMuted, marginTop: 1, fontStyle: 'italic' },
  detailPanel: {
    marginHorizontal: 14, marginBottom: 8,
    paddingHorizontal: 12, paddingVertical: 10,
    backgroundColor: COLORS.accent + '10',
    borderRadius: 8, borderWidth: 1,
    borderColor: COLORS.accent + '30',
  },
  detailHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginBottom: 8,
  },
  detailTitle: { fontSize: 13, fontWeight: '700', color: COLORS.accentLight },
  detailMeta: { flexDirection: 'row', gap: 8, marginBottom: 10, flexWrap: 'wrap' },
  metaPill: {
    flexDirection: 'row', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 12, backgroundColor: COLORS.bg,
  },
  metaLabel: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600' },
  metaValue: { fontSize: 10, color: COLORS.textPrimary, fontWeight: '700' },
  detailGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 6,
  },
  detailCell: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 6, paddingVertical: 4,
    borderRadius: 6, backgroundColor: COLORS.bg,
    borderWidth: 1, borderColor: COLORS.border,
  },
  typeBadge: {
    paddingHorizontal: 4, paddingVertical: 1,
    borderRadius: 4, borderWidth: 1,
  },
  typeBadgeText: { fontSize: 8, fontWeight: '800' },
  detailLevel: { fontSize: 10, fontWeight: '600' },
  detailQuota: { fontSize: 10, color: COLORS.textMuted, fontWeight: '700' },
});
