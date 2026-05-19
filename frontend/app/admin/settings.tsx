/**
 * /admin/settings — Admin Settings hub.
 *
 * Currently focused on 3rd-party integration credentials (Razorpay,
 * Exotel, DigiLocker, UltraMsg WhatsApp, Google Calendar, Emergent LLM).
 *
 * Architecture:
 *   • Credentials stored in MongoDB `integrations` collection (NOT in .env)
 *     so updates take effect immediately without container restart.
 *   • Secret fields are masked on the wire — server never returns the raw
 *     value once stored.
 *   • Each provider has a "Test" button (currently checks required fields;
 *     real provider pings ship in Phase 2).
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
  Modal,
  Alert,
  Platform,
  Switch,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

type FieldSpec = {
  key: string;
  label: string;
  type: 'text' | 'password';
  required: boolean;
  secret: boolean;
  placeholder?: string;
};

type IntegrationItem = {
  provider: string;
  title: string;
  category: string;
  icon: string;
  description: string;
  docs_url: string;
  fields: FieldSpec[];
  enabled: boolean;
  configured: boolean;
  config_masked: Record<string, any>;
  updated_at?: string;
  updated_by?: string;
  last_tested_at?: string;
  last_test_result?: any;
};

export default function AdminSettings() {
  const [items, setItems] = useState<IntegrationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<IntegrationItem | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [enabled, setEnabled] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/integrations');
      setItems(res.data || []);
    } catch (e: any) {
      console.error('Load integrations failed:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openEdit = (item: IntegrationItem) => {
    setEditing(item);
    setEnabled(item.enabled);
    // pre-fill with masked values; user only types over fields they want to change
    const initial: Record<string, string> = {};
    item.fields.forEach(f => {
      initial[f.key] = (item.config_masked?.[f.key] ?? '') as string;
    });
    setForm(initial);
  };

  const closeEdit = () => {
    setEditing(null);
    setForm({});
  };

  const save = async () => {
    if (!editing) return;
    // Validate required fields
    const missing = editing.fields
      .filter(f => f.required && !form[f.key])
      .map(f => f.label);
    if (missing.length) {
      const msg = `Required: ${missing.join(', ')}`;
      if (Platform.OS === 'web') window.alert(msg); else Alert.alert('Missing fields', msg);
      return;
    }
    setSaving(true);
    try {
      // Only send fields user actually edited (skip those equal to mask)
      const config: Record<string, string> = {};
      Object.entries(form).forEach(([k, v]) => {
        if (v !== '••••••••') config[k] = v;
      });
      await api.put(`/admin/integrations/${editing.provider}`, { enabled, config });
      await load();
      closeEdit();
      const msg = `${editing.title} updated.`;
      if (Platform.OS === 'web') window.alert(msg); else Alert.alert('Saved', msg);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Save failed';
      if (Platform.OS === 'web') window.alert(msg); else Alert.alert('Error', msg);
    } finally {
      setSaving(false);
    }
  };

  const runTest = async (provider: string) => {
    setTesting(provider);
    try {
      const res = await api.post(`/admin/integrations/${provider}/test`);
      const r = res.data;
      const msg = r.ok
        ? '✅ All required fields are configured.'
        : `❌ Missing: ${(r.missing_fields || []).join(', ')}`;
      if (Platform.OS === 'web') window.alert(msg); else Alert.alert('Test result', msg);
      await load();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Test failed';
      if (Platform.OS === 'web') window.alert(msg); else Alert.alert('Error', msg);
    } finally {
      setTesting(null);
    }
  };

  // Group items by category for nicer display
  const grouped: Record<string, IntegrationItem[]> = {};
  items.forEach(it => {
    if (!grouped[it.category]) grouped[it.category] = [];
    grouped[it.category].push(it);
  });

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={{ padding: 20, paddingBottom: 60 }}
        showsVerticalScrollIndicator={true}
      >
        {/* Page header */}
        <View style={styles.pageHeader}>
          <Text style={styles.pageTitle}>Admin Settings</Text>
          <Text style={styles.pageSubtitle}>
            Manage 3rd-party integration credentials. Changes take effect immediately — no restart required.
          </Text>
        </View>

        {/* Security notice */}
        <View style={styles.noticeBox}>
          <Ionicons name="lock-closed" size={16} color={COLORS.primary} />
          <Text style={styles.noticeText}>
            Secrets are masked on display (•••). Submit a new value only when rotating credentials.
          </Text>
        </View>

        {loading ? (
          <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
        ) : items.length === 0 ? (
          <Text style={styles.empty}>No integrations available.</Text>
        ) : (
          Object.entries(grouped).map(([category, list]) => (
            <View key={category} style={styles.categorySection}>
              <Text style={styles.categoryHeader}>{category.toUpperCase()}</Text>
              {list.map(item => (
                <View key={item.provider} style={styles.card}>
                  <View style={styles.cardHeader}>
                    <View style={[styles.iconBubble, { backgroundColor: COLORS.primary + '15' }]}>
                      <Ionicons name={item.icon as any} size={22} color={COLORS.primary} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <View style={styles.titleRow}>
                        <Text style={styles.cardTitle}>{item.title}</Text>
                        <View style={[styles.statusPill, item.configured ? styles.pillOk : styles.pillWarn]}>
                          <Ionicons
                            name={item.configured ? 'checkmark-circle' : 'alert-circle'}
                            size={11}
                            color="#fff"
                          />
                          <Text style={styles.pillText}>
                            {item.configured ? (item.enabled ? 'Active' : 'Configured') : 'Not configured'}
                          </Text>
                        </View>
                      </View>
                      <Text style={styles.cardDesc}>{item.description}</Text>
                      {item.updated_at && (
                        <Text style={styles.metaText}>
                          Updated {new Date(item.updated_at).toLocaleString()}
                          {item.updated_by ? ` by ${item.updated_by}` : ''}
                        </Text>
                      )}
                    </View>
                  </View>

                  <View style={styles.actionRow}>
                    <TouchableOpacity
                      style={[styles.btn, styles.btnPrimary]}
                      onPress={() => openEdit(item)}
                    >
                      <Ionicons name="create-outline" size={14} color="#fff" />
                      <Text style={styles.btnPrimaryText}>Configure</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.btn, styles.btnGhost]}
                      onPress={() => runTest(item.provider)}
                      disabled={testing === item.provider}
                    >
                      {testing === item.provider ? (
                        <ActivityIndicator size="small" color={COLORS.primary} />
                      ) : (
                        <>
                          <Ionicons name="pulse-outline" size={14} color={COLORS.primary} />
                          <Text style={styles.btnGhostText}>Test</Text>
                        </>
                      )}
                    </TouchableOpacity>
                    {item.docs_url && (
                      <TouchableOpacity
                        style={[styles.btn, styles.btnGhost]}
                        onPress={() => {
                          if (Platform.OS === 'web' && typeof window !== 'undefined') {
                            window.open(item.docs_url, '_blank');
                          }
                        }}
                      >
                        <Ionicons name="document-text-outline" size={14} color={COLORS.primary} />
                        <Text style={styles.btnGhostText}>Docs</Text>
                      </TouchableOpacity>
                    )}
                  </View>
                </View>
              ))}
            </View>
          ))
        )}
      </ScrollView>

      {/* Edit modal */}
      <Modal visible={!!editing} animationType="slide" transparent onRequestClose={closeEdit}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <ScrollView>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>{editing?.title}</Text>
                <TouchableOpacity onPress={closeEdit} hitSlop={10}>
                  <Ionicons name="close" size={22} color={COLORS.textPrimary} />
                </TouchableOpacity>
              </View>

              <Text style={styles.modalDesc}>{editing?.description}</Text>

              {/* Enable toggle */}
              <View style={styles.toggleRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.toggleLabel}>Enable this integration</Text>
                  <Text style={styles.toggleHint}>
                    When OFF, calls to this provider return graceful 503.
                  </Text>
                </View>
                <Switch value={enabled} onValueChange={setEnabled} />
              </View>

              {/* Dynamic fields */}
              {editing?.fields.map(f => (
                <View key={f.key} style={styles.fieldGroup}>
                  <Text style={styles.fieldLabel}>
                    {f.label}
                    {f.required && <Text style={{ color: '#EF4444' }}> *</Text>}
                  </Text>
                  <TextInput
                    value={form[f.key] || ''}
                    onChangeText={(v) => setForm(prev => ({ ...prev, [f.key]: v }))}
                    secureTextEntry={f.type === 'password'}
                    autoCapitalize="none"
                    autoCorrect={false}
                    placeholder={f.placeholder || `Enter ${f.label.toLowerCase()}`}
                    placeholderTextColor={COLORS.textMuted}
                    style={styles.input}
                  />
                  {f.secret && form[f.key] === '••••••••' && (
                    <Text style={styles.fieldHint}>
                      Tap to replace. Leave as-is to keep the existing secret.
                    </Text>
                  )}
                </View>
              ))}

              <View style={styles.modalFooter}>
                <TouchableOpacity onPress={closeEdit} style={[styles.btn, styles.btnGhost]}>
                  <Text style={styles.btnGhostText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={save}
                  disabled={saving}
                  style={[styles.btn, styles.btnPrimary, { flex: 1 }]}
                >
                  {saving ? (
                    <ActivityIndicator color="#fff" size="small" />
                  ) : (
                    <>
                      <Ionicons name="save" size={14} color="#fff" />
                      <Text style={styles.btnPrimaryText}>Save credentials</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, minHeight: 600, backgroundColor: COLORS.background },
  pageHeader: { marginBottom: 16 },
  pageTitle: { fontSize: 24, fontWeight: '800', color: COLORS.textPrimary },
  pageSubtitle: { fontSize: 13, color: COLORS.textMuted, marginTop: 4 },
  noticeBox: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: COLORS.primary + '10', padding: 12, borderRadius: 8,
    marginBottom: 16,
  },
  noticeText: { flex: 1, fontSize: 12, color: COLORS.textPrimary },
  empty: { textAlign: 'center', color: COLORS.textMuted, marginTop: 60 },
  categorySection: { marginTop: 20 },
  categoryHeader: {
    fontSize: 11, fontWeight: '700', color: COLORS.textMuted, letterSpacing: 0.8,
    marginBottom: 10,
  },
  card: {
    backgroundColor: COLORS.cardBg, borderRadius: 12, padding: 16,
    marginBottom: 10, borderWidth: 1, borderColor: COLORS.border,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  iconBubble: {
    width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center',
  },
  titleRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  cardDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 4, lineHeight: 17 },
  metaText: { fontSize: 11, color: COLORS.textMuted, marginTop: 4 },
  statusPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12,
  },
  pillOk: { backgroundColor: '#10B981' },
  pillWarn: { backgroundColor: '#F59E0B' },
  pillText: { fontSize: 10, color: '#fff', fontWeight: '700' },
  actionRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  btn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8,
  },
  btnPrimary: { backgroundColor: COLORS.primary },
  btnPrimaryText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  btnGhost: { backgroundColor: COLORS.primary + '12' },
  btnGhostText: { color: COLORS.primary, fontSize: 13, fontWeight: '600' },
  // Modal
  modalBackdrop: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'center', alignItems: 'center', padding: 20,
  },
  modalCard: {
    width: '100%', maxWidth: 560, maxHeight: '85%',
    backgroundColor: COLORS.cardBg, borderRadius: 14, padding: 20,
  },
  modalHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 8,
  },
  modalTitle: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary },
  modalDesc: { fontSize: 12, color: COLORS.textMuted, marginBottom: 14 },
  toggleRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingVertical: 10, borderTopWidth: 1, borderBottomWidth: 1,
    borderColor: COLORS.border, marginBottom: 14,
  },
  toggleLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  toggleHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  fieldGroup: { marginBottom: 14 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },
  fieldHint: { fontSize: 10, color: COLORS.textMuted, marginTop: 4, fontStyle: 'italic' },
  input: {
    borderWidth: 1, borderColor: COLORS.border, borderRadius: 8,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 14,
    color: COLORS.textPrimary, backgroundColor: COLORS.background,
  },
  modalFooter: { flexDirection: 'row', gap: 10, marginTop: 8 },
});
