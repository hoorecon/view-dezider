/**
 * Central Catalog Manager — Explorer (Windows-Explorer style, lazy-loaded)
 *
 * /admin/catalog
 *
 * Tree backbone:
 *   LifeArea (L0) ─ SubArea / catalog node (L1+) ─ OrgType ─ PNRAG ─ Scenario
 *      └─ Decision Templates · Solution Templates (ASM) · Solution Store items ★ ReviewNet
 *
 * - Children are fetched lazily on expand (/catalog-explorer/children).
 * - Inline CRUD gated by role capabilities (/catalog-explorer/meta):
 *     • Super Admin  → full CRUD on Scenarios + Decision/Solution Templates.
 *     • Admin/Co-Admin → Solution Store items + ReviewNet (auto-approved) only.
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
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../src/utils/api';
import { COLORS } from '../../../src/constants/colors';
import { showAlert } from '../../../src/utils/alert';

interface ExplorerNode {
  id: string;
  node_type: string;
  label: string;
  sublabel?: string | null;
  icon?: string | null;
  color?: string | null;
  expandable: boolean;
  editable: boolean;
  deletable: boolean;
  badge?: string | null;
  ctx: Record<string, any>;
  meta: Record<string, any>;
}

interface Caps {
  role: string;
  is_admin: boolean;
  is_super_admin: boolean;
  can_full_crud: boolean;
  can_store_crud: boolean;
}

const ROOT_KEY = 'ROOT';

// group key -> leaf entity
const GROUP_ENTITY: Record<string, string> = {
  decision_templates: 'decision_template',
  solution_templates: 'solution_template',
  solution_items: 'solution_item',
};

interface FieldDef { key: string; label: string; multiline?: boolean; picker?: boolean; }
const ENTITY_FORM: Record<string, { title: string; fields: FieldDef[] }> = {
  scenario: {
    title: 'Scenario',
    fields: [
      { key: 'title', label: 'Title *' },
      { key: 'description', label: 'Description', multiline: true },
    ],
  },
  decision_template: {
    title: 'Decision Template',
    fields: [
      { key: 'title', label: 'Title *' },
      { key: 'decision_type', label: 'Decision type (optional)' },
      { key: 'description', label: 'Description', multiline: true },
    ],
  },
  solution_template: {
    title: 'ASM Solution Template',
    fields: [
      { key: 'title', label: 'Title *' },
      { key: 'asm_stage', label: 'ASM stage (optional)' },
      { key: 'description', label: 'Description', multiline: true },
    ],
  },
  solution_item: {
    title: 'Solution Store Item',
    fields: [
      { key: 'name', label: 'Name *' },
      { key: 'type', label: 'Type', picker: true },
      { key: 'provider', label: 'Provider (optional)' },
      { key: 'url', label: 'URL (optional)' },
      { key: 'description', label: 'Description', multiline: true },
    ],
  },
};

const ENTITY_ENDPOINT: Record<string, string> = {
  scenario: '/catalog-explorer/scenarios',
  decision_template: '/catalog-explorer/decision-templates',
  solution_template: '/catalog-explorer/solution-templates',
  solution_item: '/catalog-explorer/solution-items',
};

export default function AdminCatalogExplorerScreen() {
  const router = useRouter();
  const [caps, setCaps] = useState<Caps | null>(null);
  const [solutionTypes, setSolutionTypes] = useState<string[]>(['PRODUCT', 'SERVICE', 'EVENT', 'PROJECT', 'PERSON_CONTACT']);
  const [bootLoading, setBootLoading] = useState(true);
  const [seedBusy, setSeedBusy] = useState(false);

  const [cache, setCache] = useState<Record<string, ExplorerNode[]>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loadingKeys, setLoadingKeys] = useState<Record<string, boolean>>({});

  // editor modal
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState<'create' | 'edit'>('create');
  const [editorEntity, setEditorEntity] = useState<string>('scenario');
  const [editorParent, setEditorParent] = useState<ExplorerNode | null>(null);  // node under which to add (create)
  const [editorReloadNode, setEditorReloadNode] = useState<ExplorerNode | null>(null); // node to refetch after op (null = ROOT)
  const [editorTarget, setEditorTarget] = useState<ExplorerNode | null>(null);  // node being edited
  const [form, setForm] = useState<Record<string, string>>({});
  const [submitBusy, setSubmitBusy] = useState(false);

  // ── params builder for /children ──
  const buildParams = (node: ExplorerNode | null): Record<string, any> => {
    if (!node || node.node_type === '__root__') return { node_type: 'catalog_node' };
    const c = node.ctx || {};
    switch (node.node_type) {
      case 'catalog_node':
        return { node_type: 'catalog_node', node_id: c.node_id };
      case 'org_type':
        return { node_type: 'org_type', node_id: c.node_id, org_type: c.org_type, life_area_id: c.life_area_id };
      case 'pnrag':
        return { node_type: 'pnrag', node_id: c.node_id, org_type: c.org_type, pnrag: c.pnrag, life_area_id: c.life_area_id };
      case 'scenario':
        return { node_type: 'scenario', scenario_id: c.scenario_id };
      case 'group':
        return { node_type: 'group', scenario_id: c.scenario_id, group: c.group };
      default:
        return { node_type: 'catalog_node' };
    }
  };

  const fetchChildren = useCallback(async (node: ExplorerNode | null): Promise<ExplorerNode[]> => {
    const res = await api.get('/catalog-explorer/children', { params: buildParams(node) });
    return res.data?.children || [];
  }, []);

  const keyFor = (node: ExplorerNode | null) => (node ? node.id : ROOT_KEY);

  const loadInto = useCallback(async (node: ExplorerNode | null) => {
    const key = keyFor(node);
    setLoadingKeys(prev => ({ ...prev, [key]: true }));
    try {
      const children = await fetchChildren(node);
      setCache(prev => ({ ...prev, [key]: children }));
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Failed to load';
      showAlert('Catalog error', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoadingKeys(prev => ({ ...prev, [key]: false }));
    }
  }, [fetchChildren]);

  const boot = useCallback(async () => {
    setBootLoading(true);
    try {
      const metaRes = await api.get('/catalog-explorer/meta');
      setCaps(metaRes.data?.capabilities || null);
      if (Array.isArray(metaRes.data?.solution_types)) setSolutionTypes(metaRes.data.solution_types);
      await loadInto(null);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Failed to initialise';
      showAlert('Catalog error', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setBootLoading(false);
    }
  }, [loadInto]);

  useEffect(() => { boot(); }, [boot]);

  const toggle = (node: ExplorerNode) => {
    const key = node.id;
    const willExpand = !expanded[key];
    setExpanded(prev => ({ ...prev, [key]: willExpand }));
    if (willExpand && !cache[key]) loadInto(node);
  };

  // ── CRUD helpers ──
  const openCreate = (parentNode: ExplorerNode) => {
    let entity = '';
    if (parentNode.node_type === 'pnrag') entity = 'scenario';
    else if (parentNode.node_type === 'group') entity = GROUP_ENTITY[parentNode.ctx?.group] || '';
    if (!entity) return;
    setEditorMode('create');
    setEditorEntity(entity);
    setEditorParent(parentNode);
    setEditorReloadNode(parentNode);
    setEditorTarget(null);
    setForm(entity === 'solution_item' ? { type: solutionTypes[0] || 'PRODUCT' } : {});
    setEditorOpen(true);
  };

  const openEdit = (node: ExplorerNode, parentNode: ExplorerNode | null) => {
    const entity = node.node_type;
    const m = node.meta || {};
    let initial: Record<string, string> = {};
    if (entity === 'scenario') {
      initial = { title: m.title || node.label || '', description: m.description || '' };
    } else if (entity === 'decision_template') {
      initial = { title: m.title || node.label || '', decision_type: m.decision_type || '', description: m.description || '' };
    } else if (entity === 'solution_template') {
      initial = { title: m.title || node.label || '', asm_stage: m.asm_stage || '', description: m.description || '' };
    } else if (entity === 'solution_item') {
      initial = { name: node.label || '', type: m.type || solutionTypes[0] || 'PRODUCT', provider: m.provider || '', url: m.url || '', description: m.description || '' };
    } else {
      return;
    }
    setEditorMode('edit');
    setEditorEntity(entity);
    setEditorParent(null);
    setEditorReloadNode(parentNode);
    setEditorTarget(node);
    setForm(initial);
    setEditorOpen(true);
  };

  const submitEditor = async () => {
    const entity = editorEntity;
    const base = ENTITY_ENDPOINT[entity];
    // basic required validation
    const primary = entity === 'solution_item' ? 'name' : 'title';
    if (!(form[primary] || '').trim()) {
      showAlert('Required', `Please enter a ${primary === 'name' ? 'name' : 'title'}.`);
      return;
    }
    setSubmitBusy(true);
    try {
      if (editorMode === 'create') {
        const pc = editorParent?.ctx || {};
        let body: Record<string, any> = {};
        if (entity === 'scenario') {
          body = { catalog_node_id: pc.node_id, org_type: pc.org_type, pnrag: pc.pnrag, title: form.title?.trim(), description: form.description?.trim() || null };
        } else if (entity === 'decision_template') {
          body = { scenario_id: pc.scenario_id, title: form.title?.trim(), decision_type: form.decision_type?.trim() || null, description: form.description?.trim() || null };
        } else if (entity === 'solution_template') {
          body = { scenario_id: pc.scenario_id, title: form.title?.trim(), asm_stage: form.asm_stage?.trim() || null, description: form.description?.trim() || null };
        } else if (entity === 'solution_item') {
          body = { scenario_id: pc.scenario_id, name: form.name?.trim(), type: form.type || 'PRODUCT', provider: form.provider?.trim() || '', url: form.url?.trim() || '', description: form.description?.trim() || '' };
        }
        await api.post(base, body);
      } else {
        const id = editorTarget?.id;
        let body: Record<string, any> = {};
        if (entity === 'scenario') {
          body = { title: form.title?.trim(), description: form.description?.trim() || null };
        } else if (entity === 'decision_template') {
          body = { title: form.title?.trim(), decision_type: form.decision_type?.trim() || null, description: form.description?.trim() || null };
        } else if (entity === 'solution_template') {
          body = { title: form.title?.trim(), asm_stage: form.asm_stage?.trim() || null, description: form.description?.trim() || null };
        } else if (entity === 'solution_item') {
          body = { name: form.name?.trim(), type: form.type || 'PRODUCT', provider: form.provider?.trim() || '', url: form.url?.trim() || '', description: form.description?.trim() || '' };
        }
        await api.put(`${base}/${id}`, body);
      }
      setEditorOpen(false);
      await loadInto(editorReloadNode);
      // make sure parent stays expanded
      if (editorReloadNode) setExpanded(prev => ({ ...prev, [editorReloadNode.id]: true }));
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Save failed';
      showAlert('Save failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSubmitBusy(false);
    }
  };

  const doDelete = async (node: ExplorerNode, parentNode: ExplorerNode | null, cascade = false) => {
    const base = ENTITY_ENDPOINT[node.node_type];
    if (!base) return;
    try {
      await api.delete(`${base}/${node.id}`, { params: cascade ? { cascade: true } : {} });
      await loadInto(parentNode);
      if (parentNode) setExpanded(prev => ({ ...prev, [parentNode.id]: true }));
    } catch (e: any) {
      const status = e?.response?.status;
      const msg = e?.response?.data?.detail || e.message || 'Delete failed';
      if (status === 409 && node.node_type === 'scenario' && !cascade) {
        showAlert('Scenario not empty', typeof msg === 'string' ? msg : 'It still has child items.', [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Delete all', style: 'destructive', onPress: () => doDelete(node, parentNode, true) },
        ]);
        return;
      }
      showAlert('Delete failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  const confirmDelete = (node: ExplorerNode, parentNode: ExplorerNode | null) => {
    showAlert('Delete?', `Remove "${node.label}"?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => doDelete(node, parentNode) },
    ]);
  };

  const viewRatings = async (node: ExplorerNode) => {
    try {
      const res = await api.get(`/catalog-explorer/solution-items/${node.id}/ratings`);
      const d = res.data || {};
      const lines = (d.factors || []).map((f: any) => `• ${f.factor}: ${f.avg} (${f.count})`).join('\n');
      showAlert(
        `ReviewNet · ${node.label}`,
        `Overall: ${d.overall ?? 'no ratings'} · ${d.review_count || 0} review(s)${lines ? `\n\n${lines}` : ''}`,
      );
    } catch (e: any) {
      showAlert('Ratings', 'Could not load ratings.');
    }
  };

  // ── add-affordance check ──
  const canAdd = (node: ExplorerNode): boolean => {
    if (!caps) return false;
    if (node.node_type === 'pnrag') return caps.can_full_crud;
    if (node.node_type === 'group') {
      const g = node.ctx?.group;
      if (g === 'solution_items') return caps.can_store_crud;
      return caps.can_full_crud; // decision / solution templates
    }
    return false;
  };

  // ── render ──
  const renderChildren = (parentNode: ExplorerNode | null, depth: number): React.ReactNode => {
    const key = keyFor(parentNode);
    const kids = cache[key];
    const isLoading = loadingKeys[key];
    if (isLoading && !kids) {
      return (
        <View style={[styles.inlineLoad, { paddingLeft: 14 + depth * 16 }]}>
          <ActivityIndicator size="small" color={COLORS.primary} />
        </View>
      );
    }
    if (kids && kids.length === 0) {
      return (
        <Text style={[styles.emptyChild, { paddingLeft: 18 + depth * 16 }]}>— empty —</Text>
      );
    }
    return (kids || []).map(k => renderNode(k, depth, parentNode));
  };

  const renderNode = (node: ExplorerNode, depth: number, parentNode: ExplorerNode | null): React.ReactNode => {
    const isOpen = expanded[node.id];
    const tint = node.color || COLORS.textSecondary;
    const addable = canAdd(node);
    return (
      <View key={node.id}>
        <View style={[styles.row, { paddingLeft: 6 + depth * 16 }]}>
          {node.expandable ? (
            <TouchableOpacity onPress={() => toggle(node)} style={styles.caretBtn} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name={isOpen ? 'chevron-down' : 'chevron-forward'} size={16} color={COLORS.textSecondary} />
            </TouchableOpacity>
          ) : (
            <View style={styles.caretBtn} />
          )}

          <View style={[styles.iconDot, { backgroundColor: (tint as string) + '22' }]}>
            <Ionicons name={(node.icon as any) || 'ellipse'} size={15} color={tint as string} />
          </View>

          <TouchableOpacity
            style={{ flex: 1, marginLeft: 8 }}
            activeOpacity={node.expandable ? 0.6 : 1}
            onPress={() => node.expandable && toggle(node)}
          >
            <View style={styles.titleRow}>
              <Text style={styles.nodeName} numberOfLines={1}>{node.label}</Text>
              {!!node.badge && (
                <View style={styles.badge}><Text style={styles.badgeText}>{node.badge}</Text></View>
              )}
            </View>
            {!!node.sublabel && <Text style={styles.nodeMeta} numberOfLines={1}>{node.sublabel}</Text>}
          </TouchableOpacity>

          <View style={styles.actions}>
            {node.node_type === 'solution_item' && (
              <TouchableOpacity onPress={() => viewRatings(node)} style={styles.iconBtn} accessibilityLabel="View ratings">
                <Ionicons name="star-outline" size={17} color="#F59E0B" />
              </TouchableOpacity>
            )}
            {addable && (
              <TouchableOpacity onPress={() => openCreate(node)} style={styles.iconBtn} accessibilityLabel="Add">
                <Ionicons name="add-circle" size={20} color={COLORS.primary} />
              </TouchableOpacity>
            )}
            {node.editable && (
              <TouchableOpacity onPress={() => openEdit(node, parentNode)} style={styles.iconBtn} accessibilityLabel="Edit">
                <Ionicons name="pencil" size={16} color={COLORS.textSecondary} />
              </TouchableOpacity>
            )}
            {node.deletable && (
              <TouchableOpacity onPress={() => confirmDelete(node, parentNode)} style={styles.iconBtn} accessibilityLabel="Delete">
                <Ionicons name="trash" size={16} color={COLORS.error} />
              </TouchableOpacity>
            )}
          </View>
        </View>

        {isOpen && renderChildren(node, depth + 1)}
      </View>
    );
  };

  // ── seed / migrate ──
  const migrateScenarios = async () => {
    setSeedBusy(true);
    try {
      const res = await api.post('/catalog-explorer/seed-scenarios-from-templates', {});
      showAlert('Scenarios migrated',
        `Created ${res.data.scenarios_created}, skipped ${res.data.skipped_existing}, unmatched ${res.data.templates_unmatched}.`);
      // reset caches so new scenarios appear on re-expand
      setCache({}); setExpanded({});
      await loadInto(null);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Migration failed';
      showAlert('Migration failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSeedBusy(false);
    }
  };

  const seedBackbone = async () => {
    setSeedBusy(true);
    try {
      await api.post('/catalog/seed?force=false', {});
      setCache({}); setExpanded({});
      await loadInto(null);
      showAlert('Backbone ready', 'Life areas & sub-areas verified.');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Seed failed';
      showAlert('Seed failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSeedBusy(false);
    }
  };

  const formDef = ENTITY_FORM[editorEntity];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Central Catalog</Text>
        <TouchableOpacity onPress={() => { setCache({}); setExpanded({}); loadInto(null); }} style={styles.iconBtn}>
          <Ionicons name="refresh" size={20} color={COLORS.textPrimary} />
        </TouchableOpacity>
      </View>

      {/* Capability banner */}
      {caps && (
        <View style={styles.capBar}>
          <Ionicons name="shield-checkmark" size={13} color={COLORS.primary} />
          <Text style={styles.capText}>
            {caps.is_super_admin
              ? 'Super Admin · full structure CRUD'
              : 'Admin · Solution Store & ReviewNet (auto-approved); structure read-only'}
          </Text>
        </View>
      )}

      {/* Super-admin tools */}
      {caps?.can_full_crud && (
        <View style={styles.seedRow}>
          <TouchableOpacity disabled={seedBusy} style={styles.seedBtn} onPress={seedBackbone}>
            {seedBusy ? <ActivityIndicator color="#FFF" size="small" /> : (
              <><Ionicons name="leaf" size={13} color="#FFF" /><Text style={styles.seedBtnText}>Verify backbone</Text></>
            )}
          </TouchableOpacity>
          <TouchableOpacity disabled={seedBusy} style={[styles.seedBtn, { backgroundColor: '#7C3AED' }]} onPress={migrateScenarios}>
            {seedBusy ? <ActivityIndicator color="#FFF" size="small" /> : (
              <><Ionicons name="git-merge" size={13} color="#FFF" /><Text style={styles.seedBtnText}>Migrate scenarios</Text></>
            )}
          </TouchableOpacity>
        </View>
      )}

      {/* Tree */}
      {bootLoading ? (
        <View style={styles.center}><ActivityIndicator color={COLORS.primary} /></View>
      ) : (
        <ScrollView contentContainerStyle={{ paddingBottom: 80, paddingTop: 4 }}>
          {renderChildren(null, 0)}
        </ScrollView>
      )}

      {/* Editor modal */}
      <Modal visible={editorOpen} transparent animationType="slide" onRequestClose={() => setEditorOpen(false)}>
        <KeyboardAvoidingView style={styles.modalOverlay} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <View style={styles.sheet}>
            <ScrollView keyboardShouldPersistTaps="handled">
              <Text style={styles.sheetTitle}>
                {editorMode === 'create' ? `New ${formDef?.title}` : `Edit ${formDef?.title}`}
              </Text>
              {editorMode === 'create' && editorParent && (
                <Text style={styles.sheetSub}>under “{editorParent.label}”</Text>
              )}

              {formDef?.fields.map(f => (
                <View key={f.key}>
                  <Text style={styles.fieldLabel}>{f.label}</Text>
                  {f.picker ? (
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingVertical: 4 }}>
                      {solutionTypes.map(t => (
                        <TouchableOpacity
                          key={t}
                          style={[styles.typeChip, form[f.key] === t && styles.typeChipActive]}
                          onPress={() => setForm(prev => ({ ...prev, [f.key]: t }))}
                        >
                          <Text style={[styles.typeChipText, form[f.key] === t && styles.typeChipTextActive]}>{t}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  ) : (
                    <TextInput
                      style={[styles.input, f.multiline && styles.inputMultiline]}
                      value={form[f.key] || ''}
                      onChangeText={v => setForm(prev => ({ ...prev, [f.key]: v }))}
                      placeholder={f.label.replace(' *', '')}
                      placeholderTextColor={COLORS.textMuted}
                      multiline={!!f.multiline}
                      autoCapitalize={f.key === 'url' ? 'none' : 'sentences'}
                    />
                  )}
                </View>
              ))}

              <View style={{ flexDirection: 'row', gap: 8, marginTop: 16 }}>
                <TouchableOpacity style={styles.cancelBtn} onPress={() => setEditorOpen(false)}>
                  <Text style={styles.cancelBtnText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.saveBtn, submitBusy && { opacity: 0.6 }]} disabled={submitBusy} onPress={submitEditor}>
                  {submitBusy ? <ActivityIndicator color="#FFF" /> : (
                    <Text style={styles.saveBtnText}>{editorMode === 'create' ? 'Create' : 'Save'}</Text>
                  )}
                </TouchableOpacity>
              </View>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 14, paddingVertical: 12, backgroundColor: COLORS.white,
    borderBottomWidth: 1, borderBottomColor: COLORS.divider,
  },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },

  capBar: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 8, backgroundColor: '#EEF2FF',
    borderBottomWidth: 1, borderBottomColor: '#E0E7FF',
  },
  capText: { fontSize: 11, color: COLORS.textSecondary, flex: 1 },

  seedRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 14, paddingVertical: 8, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  seedBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: COLORS.primary, paddingVertical: 9, borderRadius: 8 },
  seedBtnText: { color: '#FFF', fontSize: 12, fontWeight: '600' },

  row: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 9, paddingRight: 8,
    borderBottomWidth: 1, borderBottomColor: '#F1F5F9', backgroundColor: COLORS.white,
  },
  caretBtn: { width: 22, alignItems: 'center', justifyContent: 'center' },
  iconDot: { width: 26, height: 26, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  nodeName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, flexShrink: 1 },
  nodeMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  badge: { backgroundColor: '#E2E8F0', borderRadius: 9, paddingHorizontal: 7, paddingVertical: 1 },
  badgeText: { fontSize: 10, color: COLORS.textSecondary, fontWeight: '700' },
  actions: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  iconBtn: { padding: 6 },

  inlineLoad: { paddingVertical: 10, backgroundColor: COLORS.white },
  emptyChild: { paddingVertical: 8, fontSize: 11, color: COLORS.textMuted, backgroundColor: COLORS.white, fontStyle: 'italic' },

  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },

  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '85%' },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  sheetSub: { fontSize: 12, color: COLORS.textMuted, marginTop: 2, marginBottom: 4 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 12 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },
  inputMultiline: { minHeight: 70, textAlignVertical: 'top' },
  typeChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F9FAFB' },
  typeChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  typeChipText: { fontSize: 12, color: COLORS.textPrimary, fontWeight: '500' },
  typeChipTextActive: { color: '#FFF' },
  cancelBtn: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 12, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border },
  cancelBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  saveBtn: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 12, borderRadius: 8, backgroundColor: COLORS.primary },
  saveBtnText: { color: '#FFF', fontSize: 14, fontWeight: '600' },
});
