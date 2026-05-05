/**
 * Central Catalog Management — Admin Tree Editor
 *
 * /admin/catalog
 *
 * - Loads the full catalog tree (or filtered by life area)
 * - Collapsible nodes with breadcrumb path indication via depth indent
 * - Admin can:
 *     • Add child to an L1 or L2 node (creates L2 / L3 respectively)
 *     • Edit name / icon / sort_order / active flag on L2/L3 nodes
 *     • Delete an L2/L3 node (only if leaf and no solutions mapped)
 * - Backbone (L0/L1) is read-only — shown but with a 🔒 indicator
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
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

interface CatalogNode {
  node_id: string;
  name: string;
  slug: string;
  level: number;
  parent_id: string | null;
  life_area_id: string;
  sub_area_id: string | null;
  description?: string | null;
  icon?: string | null;
  color?: string | null;
  sort_order?: number;
  is_active?: boolean;
  is_immutable?: boolean;
  children?: CatalogNode[];
}

const LEVEL_TINT: Record<number, string> = {
  0: '#1E3A8A',  // life area
  1: '#0E7490',  // sub area
  2: '#0F766E',  // category
  3: '#15803D',  // subcategory
};

export default function AdminCatalogScreen() {
  const router = useRouter();
  const [tree, setTree] = useState<CatalogNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [editingNode, setEditingNode] = useState<CatalogNode | null>(null);
  const [addingUnder, setAddingUnder] = useState<CatalogNode | null>(null);
  const [draftName, setDraftName] = useState('');
  const [draftSlug, setDraftSlug] = useState('');
  const [draftIcon, setDraftIcon] = useState('');
  const [draftSortOrder, setDraftSortOrder] = useState('0');
  const [busy, setBusy] = useState(false);
  const [filterLifeArea, setFilterLifeArea] = useState<string | null>(null);
  const [seedBusy, setSeedBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const params = filterLifeArea ? { life_area_id: filterLifeArea } : {};
      const res = await api.get('/catalog/tree', { params });
      setTree(res.data?.roots || []);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Failed to load tree';
      showAlert('Catalog error', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filterLifeArea]);

  useEffect(() => { load(); }, [load]);

  const lifeAreas: { id: string; name: string }[] = useMemo(() => {
    return tree
      .filter(n => n.level === 0)
      .map(n => ({ id: n.life_area_id, name: n.name }));
  }, [tree]);

  const toggle = (node_id: string) => {
    setCollapsed(prev => ({ ...prev, [node_id]: !prev[node_id] }));
  };

  // -------- mutators --------
  const submitAdd = async () => {
    if (!addingUnder) return;
    if (!draftName.trim()) {
      showAlert('Required', 'Enter a name');
      return;
    }
    try {
      setBusy(true);
      await api.post('/catalog/nodes', {
        name: draftName.trim(),
        slug: draftSlug.trim() || undefined,
        parent_id: addingUnder.node_id,
        icon: draftIcon.trim() || undefined,
        sort_order: parseInt(draftSortOrder, 10) || 0,
      });
      showAlert('Created', `Added "${draftName}" under ${addingUnder.name}`);
      setAddingUnder(null);
      setDraftName(''); setDraftSlug(''); setDraftIcon(''); setDraftSortOrder('0');
      load();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Create failed';
      showAlert('Create failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setBusy(false);
    }
  };

  const submitEdit = async () => {
    if (!editingNode) return;
    if (!draftName.trim()) {
      showAlert('Required', 'Name required');
      return;
    }
    try {
      setBusy(true);
      await api.put(`/catalog/nodes/${editingNode.node_id}`, {
        name: draftName.trim(),
        icon: draftIcon.trim() || undefined,
        sort_order: parseInt(draftSortOrder, 10) || 0,
      });
      showAlert('Updated', `"${draftName}" saved`);
      setEditingNode(null);
      setDraftName(''); setDraftSlug(''); setDraftIcon(''); setDraftSortOrder('0');
      load();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Update failed';
      showAlert('Update failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setBusy(false);
    }
  };

  const submitDelete = async (node: CatalogNode) => {
    showAlert(
      'Delete node?',
      `Permanently delete "${node.name}"? This cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/catalog/nodes/${node.node_id}`);
              showAlert('Deleted', `"${node.name}" removed`);
              load();
            } catch (e: any) {
              const msg = e?.response?.data?.detail || e.message || 'Delete failed';
              showAlert('Delete failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
            }
          },
        },
      ]
    );
  };

  const reseed = async (force: boolean) => {
    setSeedBusy(true);
    try {
      const res = await api.post(`/catalog/seed?force=${force}`, {});
      showAlert('Seed complete',
        `Backbone +${res.data.backbone_inserted} inserted / ${res.data.backbone_updated} updated.\nL2+L3 +${res.data.l2_l3_inserted} inserted (skipped ${res.data.l2_l3_skipped_existing}).\nTotal nodes: ${res.data.total_nodes}.${res.data.wiped_l2_l3_nodes ? `\nWiped ${res.data.wiped_l2_l3_nodes} prior nodes.` : ''}`);
      load();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Seed failed';
      showAlert('Seed failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSeedBusy(false);
    }
  };

  // -------- render --------
  const renderNode = (node: CatalogNode, depth = 0): React.ReactNode => {
    const tint = LEVEL_TINT[node.level] || COLORS.textSecondary;
    const isCollapsed = collapsed[node.node_id];
    const hasChildren = (node.children?.length || 0) > 0;
    const showAddBtn = node.level === 1 || node.level === 2;     // can add L2 / L3
    const isMutable = !node.is_immutable;

    return (
      <View key={node.node_id}>
        <View style={[styles.row, { paddingLeft: 8 + depth * 14 }]}>
          {/* expand toggle */}
          {hasChildren ? (
            <TouchableOpacity onPress={() => toggle(node.node_id)} style={styles.caretBtn}>
              <Ionicons name={isCollapsed ? 'chevron-forward' : 'chevron-down'} size={16} color={COLORS.textSecondary} />
            </TouchableOpacity>
          ) : (
            <View style={styles.caretBtn} />
          )}

          {/* level pill */}
          <View style={[styles.levelPill, { backgroundColor: tint + '22', borderColor: tint }]}>
            <Text style={[styles.levelPillText, { color: tint }]}>L{node.level}</Text>
          </View>

          <View style={{ flex: 1, marginLeft: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <Text style={styles.nodeName} numberOfLines={1}>{node.name}</Text>
              {!isMutable && <Ionicons name="lock-closed" size={11} color={COLORS.textMuted} />}
              {node.is_active === false && <Text style={styles.inactiveTag}>inactive</Text>}
            </View>
            <Text style={styles.nodeMeta} numberOfLines={1}>
              {node.slug}{node.icon ? ` · ${node.icon}` : ''}
            </Text>
          </View>

          {/* actions */}
          <View style={styles.actions}>
            {showAddBtn && (
              <TouchableOpacity
                onPress={() => {
                  setAddingUnder(node);
                  setDraftName(''); setDraftSlug(''); setDraftIcon('');
                  setDraftSortOrder('0');
                }}
                style={styles.iconBtn}
                accessibilityLabel="Add child"
              >
                <Ionicons name="add-circle" size={20} color={COLORS.primary} />
              </TouchableOpacity>
            )}
            {isMutable && (
              <>
                <TouchableOpacity
                  onPress={() => {
                    setEditingNode(node);
                    setDraftName(node.name);
                    setDraftSlug(node.slug);
                    setDraftIcon(node.icon || '');
                    setDraftSortOrder(String(node.sort_order ?? 0));
                  }}
                  style={styles.iconBtn}
                  accessibilityLabel="Edit"
                >
                  <Ionicons name="pencil" size={18} color={COLORS.textSecondary} />
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={() => submitDelete(node)}
                  style={styles.iconBtn}
                  accessibilityLabel="Delete"
                >
                  <Ionicons name="trash" size={18} color={COLORS.error} />
                </TouchableOpacity>
              </>
            )}
          </View>
        </View>

        {!isCollapsed && hasChildren && (
          <View>{node.children!.map(c => renderNode(c, depth + 1))}</View>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Central Catalog</Text>
        <TouchableOpacity onPress={() => { setRefreshing(true); load(); }} style={styles.iconBtn}>
          <Ionicons name="refresh" size={20} color={COLORS.textPrimary} />
        </TouchableOpacity>
      </View>

      {/* Filter bar */}
      <View style={styles.filterBar}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingHorizontal: 4 }}>
          <TouchableOpacity
            style={[styles.chip, !filterLifeArea && styles.chipActive]}
            onPress={() => setFilterLifeArea(null)}
          >
            <Text style={[styles.chipText, !filterLifeArea && styles.chipTextActive]}>All</Text>
          </TouchableOpacity>
          {lifeAreas.map(la => (
            <TouchableOpacity
              key={la.id}
              style={[styles.chip, filterLifeArea === la.id && styles.chipActive]}
              onPress={() => setFilterLifeArea(la.id)}
            >
              <Text style={[styles.chipText, filterLifeArea === la.id && styles.chipTextActive]}>{la.name}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Seed actions */}
      <View style={styles.seedRow}>
        <TouchableOpacity disabled={seedBusy} style={styles.seedBtn} onPress={() => reseed(false)}>
          {seedBusy ? <ActivityIndicator color="#FFF" size="small" /> : (
            <>
              <Ionicons name="leaf" size={14} color="#FFF" />
              <Text style={styles.seedBtnText}>Seed (idempotent)</Text>
            </>
          )}
        </TouchableOpacity>
        <TouchableOpacity disabled={seedBusy} style={[styles.seedBtn, { backgroundColor: COLORS.error }]} onPress={() => reseed(true)}>
          {seedBusy ? <ActivityIndicator color="#FFF" size="small" /> : (
            <>
              <Ionicons name="refresh-circle" size={14} color="#FFF" />
              <Text style={styles.seedBtnText}>Force re-seed</Text>
            </>
          )}
        </TouchableOpacity>
      </View>

      {/* Body */}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={COLORS.primary} />
        </View>
      ) : tree.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="folder-open" size={32} color={COLORS.textMuted} />
          <Text style={{ color: COLORS.textMuted, marginTop: 8 }}>No catalog data — tap Seed.</Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ paddingBottom: 80 }}>
          {tree.map(root => renderNode(root))}
        </ScrollView>
      )}

      {/* Edit / Add modal */}
      <Modal
        visible={!!(editingNode || addingUnder)}
        transparent
        animationType="slide"
        onRequestClose={() => { setEditingNode(null); setAddingUnder(null); }}
      >
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>
              {editingNode ? `Edit "${editingNode.name}"`
                : addingUnder ? `Add child under "${addingUnder.name}" (Level ${(addingUnder?.level ?? 0) + 1})`
                : ''}
            </Text>

            <Text style={styles.fieldLabel}>Name *</Text>
            <TextInput style={styles.input} value={draftName} onChangeText={setDraftName} placeholder="e.g. Senior Citizen FD" placeholderTextColor={COLORS.textMuted} />

            {addingUnder && (
              <>
                <Text style={styles.fieldLabel}>Slug (auto if blank)</Text>
                <TextInput style={styles.input} value={draftSlug} onChangeText={setDraftSlug} placeholder="senior_citizen" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" />
              </>
            )}

            <Text style={styles.fieldLabel}>Icon (Ionicons name, optional)</Text>
            <TextInput style={styles.input} value={draftIcon} onChangeText={setDraftIcon} placeholder="wallet" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" />

            <Text style={styles.fieldLabel}>Sort order</Text>
            <TextInput style={styles.input} value={draftSortOrder} onChangeText={setDraftSortOrder} placeholder="0" placeholderTextColor={COLORS.textMuted} keyboardType="numeric" />

            <View style={{ flexDirection: 'row', gap: 8, marginTop: 12 }}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => { setEditingNode(null); setAddingUnder(null); }}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.saveBtn, busy && { opacity: 0.6 }]}
                disabled={busy}
                onPress={editingNode ? submitEdit : submitAdd}
              >
                {busy ? <ActivityIndicator color="#FFF" /> : (
                  <Text style={styles.saveBtnText}>{editingNode ? 'Save' : 'Add'}</Text>
                )}
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 12,
    backgroundColor: COLORS.white,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.divider,
  },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },

  filterBar: { paddingVertical: 8, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F9FAFB' },
  chipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  chipText: { fontSize: 12, color: COLORS.textPrimary, fontWeight: '500' },
  chipTextActive: { color: '#FFF' },

  seedRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 14, paddingVertical: 8 },
  seedBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: COLORS.primary, paddingVertical: 10, borderRadius: 8 },
  seedBtnText: { color: '#FFF', fontSize: 12, fontWeight: '600' },

  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingRight: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
    backgroundColor: COLORS.white,
  },
  caretBtn: { width: 20, alignItems: 'center', justifyContent: 'center' },
  levelPill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, borderWidth: 1, marginLeft: 4 },
  levelPillText: { fontSize: 10, fontWeight: '700' },
  nodeName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  nodeMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  actions: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  iconBtn: { padding: 6 },
  inactiveTag: { fontSize: 10, color: COLORS.error, fontWeight: '600' },

  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },

  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, gap: 6 },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 6 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },
  cancelBtn: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 12, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border },
  cancelBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  saveBtn: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 12, borderRadius: 8, backgroundColor: COLORS.primary },
  saveBtnText: { color: '#FFF', fontSize: 14, fontWeight: '600' },
});
