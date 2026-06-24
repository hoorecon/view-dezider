import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, Alert, RefreshControl, Platform,
  Modal, TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { safeBack } from '../../src/utils/navigation';

const API = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL
  || process.env.EXPO_PUBLIC_BACKEND_URL
  || '';

const COLORS = {
  // Google Workspace blue-white palette
  bg: '#F8F9FA',           // page bg (Google grey-50)
  card: '#FFFFFF',         // surface
  cardAlt: '#F1F3F4',      // alt surface (Google grey-100)
  accent: '#1A73E8',       // Google blue
  accentLight: '#4285F4',
  border: '#DADCE0',       // Google grey-300
  textPrimary: '#202124',  // Google grey-900
  textSecondary: '#5F6368',// Google grey-700
  textMuted: '#80868B',    // Google grey-500
  full: '#1E8E3E',         // Google green
  read: '#1A73E8',         // Google blue
  locked: '#F29900',       // Google yellow
  hidden: '#9AA0A6',
  quotaExceeded: '#D93025',// Google red
  success: '#1E8E3E',
  error: '#D93025',
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
  // NEW (v3.19.7) — section grouping support
  is_section?: boolean;
  section_order?: number;
  parent_feature_id?: string;
  tile_overrides?: Record<string, boolean>;
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

  // Cell editor modal state
  const [editing, setEditing] = useState<{
    feature: Feature; audienceKey: string;
  } | null>(null);
  const [editLevel, setEditLevel] = useState<'full' | 'read' | 'locked' | 'hidden'>('full');
  const [editQuota, setEditQuota] = useState<string>('-1');
  const [applyAll, setApplyAll] = useState(false);
  const [saving, setSaving] = useState(false);

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

  // ─── Cell editor handlers ──────────────────────────────────────
  const openEditor = (feature: Feature, audienceKey: string) => {
    const cur = feature.access[audienceKey] || { level: 'hidden', quota: 0 };
    setEditing({ feature, audienceKey });
    setEditLevel((cur.level as any) || 'full');
    setEditQuota(String(cur.quota ?? -1));
    setApplyAll(false);
  };

  const closeEditor = () => {
    setEditing(null);
    setSaving(false);
  };

  const saveEditor = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const headers = await getHeaders();
      // Merge the existing access map with the single-cell change, so the
      // backend PUT (which replaces `access` wholesale) doesn't drop the
      // other 9 columns.
      const nextAccess: Record<string, { level: string; quota: number }> = {};
      for (const k of accessKeys) {
        nextAccess[k] = editing.feature.access[k] || { level: 'hidden', quota: 0 };
      }
      const qNum = parseInt(editQuota, 10);
      const cell = {
        level: editLevel,
        quota: Number.isFinite(qNum) ? qNum : (editLevel === 'hidden' ? 0 : -1),
      };
      if (applyAll) {
        // Mass-apply this level+quota to every audience/tier column.
        for (const k of accessKeys) nextAccess[k] = { ...cell };
      } else {
        nextAccess[editing.audienceKey] = cell;
      }
      const resp = await fetch(
        `${API}/api/acm/feature/${editing.feature.feature_id}`,
        {
          method: 'PUT',
          headers,
          body: JSON.stringify({ access: nextAccess }),
        },
      );
      if (resp.ok) {
        await fetchMatrix();
        // keep the detail panel open with refreshed data
        const fresh = matrix?.modules
          .flatMap((m) => m.features)
          .find((f) => f.feature_id === editing.feature.feature_id);
        if (fresh) setSelectedFeature(fresh);
        closeEditor();
      } else {
        const err = await resp.json().catch(() => ({}));
        Alert.alert('Save failed', err.detail || `HTTP ${resp.status}`);
        setSaving(false);
      }
    } catch (e: any) {
      Alert.alert('Save failed', e.message || 'Network error');
      setSaving(false);
    }
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
              <TouchableOpacity
                key={key}
                style={styles.detailCell}
                onPress={() => openEditor(feature, key)}
                activeOpacity={0.7}>
                <View style={[styles.typeBadge, { backgroundColor: label.color + '20', borderColor: label.color + '60' }]}>
                  <Text style={[styles.typeBadgeText, { color: label.color }]}>{label.short}</Text>
                </View>
                <Ionicons name={cfg.icon as any} size={14} color={cfg.color} />
                <Text style={[styles.detailLevel, { color: cfg.color }]}>{cfg.label}</Text>
                <Text style={styles.detailQuota}>
                  {rule.quota === -1 ? '∞' : rule.quota === 0 ? '—' : rule.quota}
                </Text>
                <Ionicons name="pencil" size={10} color={COLORS.textMuted} style={{ marginLeft: 'auto' }} />
              </TouchableOpacity>
            );
          })}
        </View>
        <Text style={styles.detailHint}>Tap any cell above to edit its access level and quota.</Text>
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
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
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
                {mod.module_id === 'dashboard_tiles' && (
                  <TouchableOpacity
                    style={styles.layoutLinkBtn}
                    activeOpacity={0.8}
                    onPress={() => router.push('/admin/dashboard-layout' as any)}>
                    <Ionicons name="swap-vertical" size={16} color={COLORS.accent} />
                    <View style={{ flex: 1, marginLeft: 8 }}>
                      <Text style={styles.layoutLinkTitle}>Rename · Reorder · Move modules</Text>
                      <Text style={styles.layoutLinkHint}>Drag to reorder sections &amp; move tiles between them (cells here control visibility)</Text>
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={COLORS.accent} />
                  </TouchableOpacity>
                )}
                {(() => {
                  // ─── SECTION GROUPING (dashboard_tiles only) ───────────
                  // If this module declares sections (rows with is_section)
                  // render them as parent rows with children indented below.
                  // Other modules render the flat list as before.
                  const sectionRows = mod.features.filter(f => f.is_section)
                    .sort((a, b) => (a.section_order || 0) - (b.section_order || 0));
                  const childByParent: Record<string, Feature[]> = {};
                  for (const f of mod.features) {
                    if (f.parent_feature_id) {
                      (childByParent[f.parent_feature_id] = childByParent[f.parent_feature_id] || []).push(f);
                    }
                  }
                  const orphans = mod.features.filter(f => !f.is_section && !f.parent_feature_id);

                  if (sectionRows.length === 0) {
                    return mod.features.map((feat) => (
                      <View key={feat.feature_id}>
                        {renderFeatureRow(feat)}
                        {renderFeatureDetail(feat)}
                      </View>
                    ));
                  }

                  return (
                    <>
                      {sectionRows.map((section) => (
                        <View key={section.feature_id}>
                          <View style={styles.sectionRowBg}>
                            {renderFeatureRow(section)}
                          </View>
                          {renderFeatureDetail(section)}
                          {(childByParent[section.feature_id] || []).map((child) => (
                            <View key={child.feature_id} style={styles.tileRowIndent}>
                              {renderFeatureRow(child)}
                              {renderFeatureDetail(child)}
                            </View>
                          ))}
                        </View>
                      ))}
                      {orphans.length > 0 && (
                        <View style={{ marginTop: 12 }}>
                          <Text style={styles.orphanLabel}>Other / un-sectioned</Text>
                          {orphans.map((feat) => (
                            <View key={feat.feature_id}>
                              {renderFeatureRow(feat)}
                              {renderFeatureDetail(feat)}
                            </View>
                          ))}
                        </View>
                      )}
                    </>
                  );
                })()}
              </View>
            )}
          </View>
        ))}

        <View style={{ height: 100 }} />
      </ScrollView>

      {/* ─── Cell Editor Modal ─────────────────────────────────────── */}
      <Modal
        visible={!!editing}
        transparent
        animationType="slide"
        onRequestClose={closeEditor}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeaderRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.modalTitle}>
                  {editing?.feature.feature_name}
                </Text>
                <Text style={styles.modalSubtitle}>
                  Audience:{' '}
                  <Text style={{ color: USER_TYPE_LABELS[editing?.audienceKey || '']?.color || COLORS.accent, fontWeight: '700' }}>
                    {USER_TYPE_LABELS[editing?.audienceKey || '']?.short || editing?.audienceKey}
                  </Text>
                  {'  ·  '}
                  <Text style={{ color: COLORS.textMuted }}>
                    {editing?.feature.quota_unit} ({editing?.feature.quota_resets})
                  </Text>
                </Text>
              </View>
              <TouchableOpacity onPress={closeEditor} disabled={saving}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalLabel}>Access level</Text>
            <View style={styles.levelRow}>
              {(['full', 'read', 'locked', 'hidden'] as const).map((lvl) => {
                const cfg = ACCESS_ICONS[lvl];
                const active = editLevel === lvl;
                return (
                  <TouchableOpacity
                    key={lvl}
                    style={[
                      styles.levelBtn,
                      { borderColor: cfg.color },
                      active && styles.levelBtnActive,
                      active && { backgroundColor: cfg.color, borderColor: cfg.color },
                    ]}
                    onPress={() => {
                      setEditLevel(lvl);
                      // Auto-set sensible quota defaults when switching level
                      if (lvl === 'hidden' || lvl === 'locked') setEditQuota('0');
                      else if (parseInt(editQuota, 10) === 0) setEditQuota('-1');
                    }}
                    activeOpacity={0.75}>
                    {active && (
                      <View style={styles.levelBtnCheck}>
                        <Ionicons name="checkmark-circle" size={14} color="#FFF" />
                      </View>
                    )}
                    <Ionicons name={cfg.icon as any} size={18} color={active ? '#FFF' : cfg.color} />
                    <Text style={[styles.levelBtnText, { color: active ? '#FFF' : cfg.color }]}>{cfg.label}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <Text style={styles.modalLabel}>Quota</Text>
            <Text style={styles.modalHint}>
              -1 = unlimited (∞){'  ·  '}0 = no allowance (use for Hidden/Locked){'  ·  '}any positive number = cap per {editing?.feature.quota_resets}
            </Text>
            <TextInput
              style={styles.quotaInput}
              value={editQuota}
              onChangeText={setEditQuota}
              keyboardType="numbers-and-punctuation"
              placeholder="-1"
              placeholderTextColor={COLORS.textMuted}
            />

            <TouchableOpacity
              style={styles.applyAllRow}
              activeOpacity={0.75}
              onPress={() => setApplyAll((v) => !v)}>
              <Ionicons
                name={applyAll ? 'checkbox' : 'square-outline'}
                size={22}
                color={applyAll ? COLORS.accent : COLORS.textMuted}
              />
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={styles.applyAllTitle}>Apply to all user types</Text>
                <Text style={styles.applyAllHint}>
                  Sets this level &amp; quota for every audience/tier column at once.
                </Text>
              </View>
            </TouchableOpacity>

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnCancel]}
                onPress={closeEditor}
                disabled={saving}>
                <Text style={styles.modalBtnCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnSave, saving && { opacity: 0.6 }]}
                onPress={saveEditor}
                disabled={saving}>
                {saving
                  ? <ActivityIndicator size="small" color="#FFF" />
                  : <Text style={styles.modalBtnSaveText}>Save</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
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
  detailHint: {
    fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic',
    marginTop: 8, paddingHorizontal: 4,
  },
  // ─── Section grouping (dashboard_tiles) ───
  sectionRowBg: {
    backgroundColor: COLORS.cardAlt,
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: COLORS.accent,
    marginTop: 10,
  },
  tileRowIndent: {
    marginLeft: 24,
    borderLeftWidth: 2,
    borderLeftColor: COLORS.border,
    paddingLeft: 8,
  },
  orphanLabel: {
    fontSize: 11, fontWeight: '700', color: COLORS.textMuted,
    textTransform: 'uppercase', letterSpacing: 0.5,
    marginBottom: 4, marginLeft: 4,
  },
  // ─── Editor modal ───
  modalBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.65)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: COLORS.card,
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    padding: 20,
    borderTopWidth: 2, borderColor: COLORS.accent,
    width: '100%', maxWidth: 560, alignSelf: 'center',
  },
  modalHeaderRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 12,
    marginBottom: 16,
  },
  modalTitle: {
    color: COLORS.textPrimary, fontSize: 16, fontWeight: '800',
  },
  modalSubtitle: {
    color: COLORS.textSecondary, fontSize: 12, marginTop: 4,
  },
  modalLabel: {
    color: COLORS.textSecondary, fontSize: 12, fontWeight: '700',
    marginTop: 8, marginBottom: 8, textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  modalHint: {
    color: COLORS.textMuted, fontSize: 11,
    marginBottom: 8, lineHeight: 16,
  },
  levelRow: {
    flexDirection: 'row', gap: 8, marginBottom: 6,
  },
  levelBtn: {
    flex: 1, paddingVertical: 10, paddingHorizontal: 6,
    borderRadius: 10, borderWidth: 1.5,
    backgroundColor: COLORS.bg,
    alignItems: 'center', gap: 4,
  },
  // Stronger visual cue when a level chip is selected — fixes the
  // "Hidden chip looks identical whether selected or not" complaint.
  levelBtnActive: {
    borderWidth: 2.5,
    shadowColor: '#000', shadowOpacity: 0.12,
    shadowRadius: 4, shadowOffset: { width: 0, height: 2 },
  },
  levelBtnCheck: {
    position: 'absolute', top: 4, right: 4,
  },
  levelBtnText: { fontSize: 11, fontWeight: '700' },
  layoutLinkBtn: {
    flexDirection: 'row', alignItems: 'center',
    padding: 12, borderRadius: 10, marginBottom: 10,
    backgroundColor: COLORS.accent + '12',
    borderWidth: 1, borderColor: COLORS.accent + '33',
  },
  layoutLinkTitle: { fontSize: 13, fontWeight: '700', color: COLORS.accent },
  layoutLinkHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  applyAllRow: {
    flexDirection: 'row', alignItems: 'center',
    marginTop: 16, padding: 12, borderRadius: 10,
    backgroundColor: COLORS.accent + '0F',
    borderWidth: 1, borderColor: COLORS.accent + '33',
  },
  applyAllTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  applyAllHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  quotaInput: {
    backgroundColor: COLORS.bg,
    borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    color: COLORS.textPrimary, fontSize: 16, fontWeight: '700',
    paddingHorizontal: 14, paddingVertical: 12,
    marginBottom: 18,
  },
  modalActions: {
    flexDirection: 'row', gap: 10, marginTop: 4,
  },
  modalBtn: {
    flex: 1, paddingVertical: 12, borderRadius: 10,
    alignItems: 'center', justifyContent: 'center',
  },
  modalBtnCancel: {
    backgroundColor: 'transparent',
    borderWidth: 1.5, borderColor: COLORS.border,
  },
  modalBtnCancelText: {
    color: COLORS.textSecondary, fontWeight: '700', fontSize: 14,
  },
  modalBtnSave: { backgroundColor: COLORS.accent },
  modalBtnSaveText: {
    color: '#FFF', fontWeight: '800', fontSize: 14,
  },
});
