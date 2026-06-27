/**
 * Central Catalog — Payout & Karma Config (L0–L3 governance)
 * /admin/catalog-payout
 *
 * Admins set monetization config per catalog node (or globally). Resolution
 * inherits L3 -> L2 -> L1 -> L0 -> global -> system default (nearest wins).
 *
 * Equations (read-only reference, computed server-side in core.payout_engine):
 *   Cash (Solution Store PAID use):
 *     payment_min + (payment_max - payment_min) * (avg_rating/5) * (num_ratings/3000)
 *   Karma (free use / ReviewNet):
 *     karma_per_use * (1 + star_rating/5)
 *   Cash is ONLY for Solution Store paid usage; free use + ReviewNet => Karma.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  TextInput,
  Modal,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

const STEP_LABELS: Record<string, string> = {
  factors: 'Factors',
  classification: 'Classification',
  prioritization: 'Prioritization',
  options: 'Options',
  assessment: 'Assessment',
};
const STEPS = ['factors', 'classification', 'prioritization', 'options', 'assessment'];

type Cfg = {
  free_usage_solution_store?: number;
  free_usage_template_by_step?: Record<string, number>;
  payment_min?: number;
  payment_max?: number;
  karma_solution_store?: number;
  karma_reviewnet?: number;
  karma_template_by_step?: Record<string, number>;
};

type NodeOverride = Cfg & {
  node_id: string;
  node_name?: string;
  level?: number;
  life_area_id?: string;
};

const numOr = (v: any): string => (v === undefined || v === null ? '' : String(v));

function buildPayload(
  form: Record<string, string>,
  karmaSteps: Record<string, string>,
  freeSteps: Record<string, string>,
) {
  const out: any = {};
  const setNum = (k: string) => {
    if (form[k] !== undefined && form[k] !== '') out[k] = Number(form[k]);
  };
  setNum('free_usage_solution_store');
  setNum('payment_min');
  setNum('payment_max');
  setNum('karma_solution_store');
  setNum('karma_reviewnet');
  const collect = (src: Record<string, string>) => {
    const o: Record<string, number> = {};
    STEPS.forEach((s) => {
      if (src[s] !== undefined && src[s] !== '') o[s] = Number(src[s]);
    });
    return o;
  };
  const k = collect(karmaSteps);
  if (Object.keys(k).length) out.karma_template_by_step = k;
  const f = collect(freeSteps);
  if (Object.keys(f).length) out.free_usage_template_by_step = f;
  return out;
}

export default function CatalogPayoutScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [nodes, setNodes] = useState<NodeOverride[]>([]);

  // global form state
  const [gForm, setGForm] = useState<Record<string, string>>({});
  const [gSteps, setGSteps] = useState<Record<string, string>>({});         // karma by step
  const [gFreeSteps, setGFreeSteps] = useState<Record<string, string>>({});  // free-usage quota by step

  // node override modal
  const [modalOpen, setModalOpen] = useState(false);
  const [editNode, setEditNode] = useState<NodeOverride | null>(null);
  const [nForm, setNForm] = useState<Record<string, string>>({});
  const [nSteps, setNSteps] = useState<Record<string, string>>({});         // karma by step
  const [nFreeSteps, setNFreeSteps] = useState<Record<string, string>>({});  // free-usage quota by step

  // node picker (for add)
  const [lifeAreas, setLifeAreas] = useState<any[]>([]);
  const [pickArea, setPickArea] = useState<string>('');
  const [areaNodes, setAreaNodes] = useState<any[]>([]);
  const [pickNodeId, setPickNodeId] = useState<string>('');
  const [pickNodeName, setPickNodeName] = useState<string>('');

  const hydrateGlobal = (cfg: Cfg) => {
    setGForm({
      free_usage_solution_store: numOr(cfg.free_usage_solution_store),
      payment_min: numOr(cfg.payment_min),
      payment_max: numOr(cfg.payment_max),
      karma_solution_store: numOr(cfg.karma_solution_store),
      karma_reviewnet: numOr(cfg.karma_reviewnet),
    });
    const by = cfg.karma_template_by_step || {};
    const fb = cfg.free_usage_template_by_step || {};
    const s: Record<string, string> = {};
    const fs: Record<string, string> = {};
    STEPS.forEach((k) => { s[k] = numOr(by[k]); fs[k] = numOr(fb[k]); });
    setGSteps(s);
    setGFreeSteps(fs);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/catalog/payout/config');
      hydrateGlobal(data.global || {});
      setNodes(data.nodes || []);
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to load payout config');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    api.get('/catalog/life-areas').then(({ data }) => setLifeAreas(data.items || [])).catch(() => {});
  }, [load]);

  const saveGlobal = async () => {
    setSaving(true);
    try {
      const payload = buildPayload(gForm, gSteps, gFreeSteps);
      const { data } = await api.put('/catalog/payout/config/global', payload);
      hydrateGlobal(data);
      showAlert('Saved', 'Global payout config updated.');
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  // ---- node override modal helpers ----
  const openAddNode = () => {
    setEditNode(null);
    setNForm({});
    const s: Record<string, string> = {};
    STEPS.forEach((k) => (s[k] = ''));
    setNSteps(s);
    setNFreeSteps({ ...s });
    setPickArea('');
    setAreaNodes([]);
    setPickNodeId('');
    setPickNodeName('');
    setModalOpen(true);
  };

  const openEditNode = (n: NodeOverride) => {
    setEditNode(n);
    setNForm({
      free_usage_solution_store: numOr(n.free_usage_solution_store),
      payment_min: numOr(n.payment_min),
      payment_max: numOr(n.payment_max),
      karma_solution_store: numOr(n.karma_solution_store),
      karma_reviewnet: numOr(n.karma_reviewnet),
    });
    const by = n.karma_template_by_step || {};
    const fb = n.free_usage_template_by_step || {};
    const s: Record<string, string> = {};
    const fs: Record<string, string> = {};
    STEPS.forEach((k) => { s[k] = numOr(by[k]); fs[k] = numOr(fb[k]); });
    setNSteps(s);
    setNFreeSteps(fs);
    setPickNodeId(n.node_id);
    setPickNodeName(n.node_name || n.node_id);
    setModalOpen(true);
  };

  const selectArea = async (areaId: string) => {
    setPickArea(areaId);
    setPickNodeId('');
    setPickNodeName('');
    try {
      const { data } = await api.get(`/catalog/nodes?life_area_id=${encodeURIComponent(areaId)}`);
      const items = (data.items || []).slice().sort(
        (a: any, b: any) => (a.level || 0) - (b.level || 0) || String(a.name || '').localeCompare(String(b.name || '')),
      );
      setAreaNodes(items);
    } catch {
      setAreaNodes([]);
    }
  };

  const saveNode = async () => {
    if (!pickNodeId) {
      showAlert('Select a node', 'Choose a catalog node to configure.');
      return;
    }
    setSaving(true);
    try {
      const payload = buildPayload(nForm, nSteps, nFreeSteps);
      await api.put(`/catalog/payout/config/node/${encodeURIComponent(pickNodeId)}`, payload);
      setModalOpen(false);
      await load();
      showAlert('Saved', 'Node override saved.');
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const deleteNode = (n: NodeOverride) => {
    showAlert('Remove override?', `"${n.node_name || n.node_id}" will fall back to inherited values.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/catalog/payout/config/node/${encodeURIComponent(n.node_id)}`);
            await load();
          } catch (e: any) {
            showAlert('Error', e.response?.data?.detail || 'Delete failed');
          }
        },
      },
    ]);
  };

  const areaName = (a: any) => a.name || a.label || a.title || a.id;

  const renderNumRow = (
    label: string,
    key: string,
    form: Record<string, string>,
    setForm: (f: Record<string, string>) => void,
    hint?: string,
  ) => (
    <View style={styles.fieldRow} key={key}>
      <View style={{ flex: 1 }}>
        <Text style={styles.fieldLabel}>{label}</Text>
        {!!hint && <Text style={styles.fieldHint}>{hint}</Text>}
      </View>
      <TextInput
        style={styles.numInput}
        value={form[key] ?? ''}
        onChangeText={(t) => setForm({ ...form, [key]: t.replace(/[^0-9.]/g, '') })}
        keyboardType="decimal-pad"
        placeholder="—"
        placeholderTextColor={COLORS.textMuted}
        testID={`payout-input-${key}`}
      />
    </View>
  );

  const renderStepRows = (
    title: string,
    steps: Record<string, string>,
    setSteps: (s: Record<string, string>) => void,
    idPrefix: string,
  ) => (
    <View style={styles.stepBox}>
      <Text style={styles.subLabel}>{title}</Text>
      {STEPS.map((s) => (
        <View style={styles.fieldRow} key={s}>
          <Text style={[styles.fieldLabel, { flex: 1 }]}>{STEP_LABELS[s]}</Text>
          <TextInput
            style={styles.numInput}
            value={steps[s] ?? ''}
            onChangeText={(t) => setSteps({ ...steps, [s]: t.replace(/[^0-9.]/g, '') })}
            keyboardType="decimal-pad"
            placeholder="—"
            placeholderTextColor={COLORS.textMuted}
            testID={`${idPrefix}-${s}`}
          />
        </View>
      ))}
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Catalog Payouts</Text>
        <View style={{ width: 38 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.inner}>
          {/* Equation reference */}
          <View style={styles.infoCard}>
            <View style={styles.infoRow}>
              <Ionicons name="cash-outline" size={16} color={COLORS.success} />
              <Text style={styles.infoText}>
                Cash (Store paid use) = min + (max − min) × (avg★/5) × (#ratings/3000), capped to [min, max].
              </Text>
            </View>
            <View style={styles.infoRow}>
              <Ionicons name="sparkles-outline" size={16} color={COLORS.primary} />
              <Text style={styles.infoText}>
                Karma (free use & ReviewNet) = karma × (1 + ★/5). Cash is only for Store paid use.
              </Text>
            </View>
            <View style={styles.infoRow}>
              <Ionicons name="git-branch-outline" size={16} color={COLORS.info} />
              <Text style={styles.infoText}>Inherits L3 → L2 → L1 → L0 → Global (nearest override wins).</Text>
            </View>
          </View>

          {/* GLOBAL */}
          <Text style={styles.sectionTitle}>Global defaults</Text>
          <View style={styles.card}>
            {renderNumRow('Free uses · Store', 'free_usage_solution_store', gForm, setGForm, 'Free uses before paid (Solution Store)')}
            {renderNumRow('Payment min (₹)', 'payment_min', gForm, setGForm)}
            {renderNumRow('Payment max (₹)', 'payment_max', gForm, setGForm)}
            {renderNumRow('Karma · Store free use', 'karma_solution_store', gForm, setGForm)}
            {renderNumRow('Karma · ReviewNet rating', 'karma_reviewnet', gForm, setGForm)}
            {renderStepRows('Decision Template free-use Karma (by copy-depth · higher = more)', gSteps, setGSteps, 'payout-step')}
            {renderStepRows('Decision Template free-usage quota (by copy-depth · before paid)', gFreeSteps, setGFreeSteps, 'payout-free-step')}
            <TouchableOpacity
              style={[styles.saveBtn, saving && { opacity: 0.6 }]}
              onPress={saveGlobal}
              disabled={saving}
              testID="payout-save-global"
            >
              {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>Save Global Config</Text>}
            </TouchableOpacity>
          </View>

          {/* NODE OVERRIDES */}
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Per-node overrides</Text>
            <TouchableOpacity style={styles.addBtn} onPress={openAddNode} testID="payout-add-node">
              <Ionicons name="add" size={16} color="#FFF" />
              <Text style={styles.addBtnText}>Add</Text>
            </TouchableOpacity>
          </View>

          {nodes.length === 0 ? (
            <View style={styles.emptyBox}>
              <Text style={styles.emptyText}>No overrides yet. All nodes use the global defaults above.</Text>
            </View>
          ) : (
            nodes.map((n) => (
              <View style={styles.nodeRow} key={n.node_id}>
                <View style={styles.levelBadge}>
                  <Text style={styles.levelBadgeText}>L{n.level ?? '?'}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.nodeName} numberOfLines={1}>{n.node_name || n.node_id}</Text>
                  <Text style={styles.nodeMeta} numberOfLines={1}>
                    {[
                      n.payment_min != null ? `₹${n.payment_min}–${n.payment_max ?? '?'}` : null,
                      n.karma_solution_store != null ? `K:${n.karma_solution_store}` : null,
                      n.free_usage_solution_store != null ? `free:${n.free_usage_solution_store}` : null,
                    ].filter(Boolean).join('  ·  ') || 'partial override'}
                  </Text>
                </View>
                <TouchableOpacity style={styles.iconBtn} onPress={() => openEditNode(n)} testID={`payout-edit-${n.node_id}`}>
                  <Ionicons name="create-outline" size={18} color={COLORS.primary} />
                </TouchableOpacity>
                <TouchableOpacity style={styles.iconBtn} onPress={() => deleteNode(n)} testID={`payout-delete-${n.node_id}`}>
                  <Ionicons name="trash-outline" size={18} color={COLORS.error} />
                </TouchableOpacity>
              </View>
            ))
          )}
          <View style={{ height: 40 }} />
        </View>
      </ScrollView>

      {/* Add / Edit node override modal */}
      <Modal visible={modalOpen} transparent animationType="slide" onRequestClose={() => setModalOpen(false)}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.modalWrap}
        >
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{editNode ? 'Edit override' : 'Add node override'}</Text>
              <TouchableOpacity onPress={() => setModalOpen(false)}>
                <Ionicons name="close" size={22} color={COLORS.textSecondary} />
              </TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ padding: 16 }}>
              {!editNode && (
                <>
                  <Text style={styles.subLabel}>1. Pick life area (L0)</Text>
                  <View style={styles.chipWrap}>
                    {lifeAreas.map((a) => (
                      <TouchableOpacity
                        key={a.id}
                        style={[styles.chip, pickArea === a.id && styles.chipActive]}
                        onPress={() => selectArea(a.id)}
                      >
                        <Text style={[styles.chipText, pickArea === a.id && { color: '#FFF' }]}>{areaName(a)}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                  {areaNodes.length > 0 && (
                    <>
                      <Text style={styles.subLabel}>2. Pick node</Text>
                      <View style={styles.nodePickList}>
                        {areaNodes.map((nd) => (
                          <TouchableOpacity
                            key={nd.node_id}
                            style={[styles.pickItem, pickNodeId === nd.node_id && styles.pickItemActive]}
                            onPress={() => { setPickNodeId(nd.node_id); setPickNodeName(nd.name || nd.node_id); }}
                          >
                            <View style={styles.levelBadgeSm}><Text style={styles.levelBadgeText}>L{nd.level ?? '?'}</Text></View>
                            <Text style={[styles.pickItemText, pickNodeId === nd.node_id && { color: COLORS.primary, fontWeight: '700' }]} numberOfLines={1}>
                              {nd.name || nd.node_id}
                            </Text>
                            {pickNodeId === nd.node_id && <Ionicons name="checkmark-circle" size={16} color={COLORS.primary} />}
                          </TouchableOpacity>
                        ))}
                      </View>
                    </>
                  )}
                </>
              )}

              {!!pickNodeId && (
                <>
                  <Text style={[styles.subLabel, { marginTop: 8 }]}>Config for: {pickNodeName}</Text>
                  <Text style={styles.fieldHint}>Leave blank to inherit that value from the parent / global.</Text>
                  {renderNumRow('Free uses · Store', 'free_usage_solution_store', nForm, setNForm)}
                  {renderNumRow('Payment min (₹)', 'payment_min', nForm, setNForm)}
                  {renderNumRow('Payment max (₹)', 'payment_max', nForm, setNForm)}
                  {renderNumRow('Karma · Store free use', 'karma_solution_store', nForm, setNForm)}
                  {renderNumRow('Karma · ReviewNet rating', 'karma_reviewnet', nForm, setNForm)}
                  {renderStepRows('Template free-use Karma (by copy-depth)', nSteps, setNSteps, 'payout-nkarma-step')}
                  {renderStepRows('Template free-usage quota (by copy-depth)', nFreeSteps, setNFreeSteps, 'payout-nfree-step')}
                </>
              )}
            </ScrollView>
            <View style={styles.modalFooter}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setModalOpen(false)}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.saveBtn, { flex: 1 }, (saving || !pickNodeId) && { opacity: 0.5 }]}
                onPress={saveNode}
                disabled={saving || !pickNodeId}
                testID="payout-save-node"
              >
                {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>Save Override</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 12,
    backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  backBtn: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 17, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center' },
  scroll: { alignItems: 'center', paddingVertical: 16 },
  inner: { width: '100%', maxWidth: 520, paddingHorizontal: 16 },

  infoCard: { backgroundColor: '#F8F5FC', borderRadius: 12, padding: 12, gap: 8, marginBottom: 18, borderWidth: 1, borderColor: '#EADDF5' },
  infoRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  infoText: { flex: 1, fontSize: 12, color: COLORS.textSecondary, lineHeight: 17 },

  sectionTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10 },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 24, marginBottom: 10 },

  card: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: COLORS.border },
  fieldRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, gap: 12 },
  fieldLabel: { fontSize: 14, color: COLORS.textPrimary, fontWeight: '500' },
  fieldHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  subLabel: { fontSize: 13, fontWeight: '700', color: COLORS.textSecondary, marginTop: 6, marginBottom: 4 },
  numInput: {
    width: 96, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 8, fontSize: 14, color: COLORS.textPrimary,
    textAlign: 'right', backgroundColor: COLORS.surface,
  },
  stepBox: { marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: COLORS.divider },

  saveBtn: {
    marginTop: 16, backgroundColor: COLORS.primary, borderRadius: 10,
    paddingVertical: 13, alignItems: 'center', justifyContent: 'center',
  },
  saveBtnText: { color: '#FFF', fontWeight: '700', fontSize: 14 },

  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8 },
  addBtnText: { color: '#FFF', fontWeight: '700', fontSize: 13 },

  emptyBox: { backgroundColor: COLORS.white, borderRadius: 12, padding: 18, borderWidth: 1, borderColor: COLORS.border, borderStyle: 'dashed' },
  emptyText: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center' },

  nodeRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: COLORS.white, borderRadius: 10, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  levelBadge: { backgroundColor: COLORS.primaryLight, borderRadius: 6, paddingHorizontal: 7, paddingVertical: 3 },
  levelBadgeSm: { backgroundColor: COLORS.primaryLight, borderRadius: 5, paddingHorizontal: 6, paddingVertical: 2 },
  levelBadgeText: { color: '#FFF', fontWeight: '800', fontSize: 11 },
  nodeName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  nodeMeta: { fontSize: 11, color: COLORS.textSecondary, marginTop: 2 },
  iconBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },

  modalWrap: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  modalCard: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, maxHeight: '90%', width: '100%', maxWidth: 560, alignSelf: 'center' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  modalTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  modalFooter: { flexDirection: 'row', gap: 10, padding: 16, borderTopWidth: 1, borderTopColor: COLORS.divider },
  cancelBtn: { paddingHorizontal: 18, paddingVertical: 13, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center', justifyContent: 'center' },
  cancelBtnText: { color: COLORS.textSecondary, fontWeight: '600' },

  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 16, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.surface },
  chipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  chipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  nodePickList: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, overflow: 'hidden' },
  pickItem: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  pickItemActive: { backgroundColor: '#F8F5FC' },
  pickItemText: { flex: 1, fontSize: 13, color: COLORS.textPrimary },
});
