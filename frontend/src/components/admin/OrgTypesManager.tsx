/**
 * OrgTypesManager — Admin → Masters → "Org Types" tab.
 * Full CRUD on the Org-Type master (db.org_types_master) that powers the
 * Initial-Info "This decision is for…" cards (My Dezider / SWOT / Pros & Cons),
 * the Solution targeting picker and coupon org-type filters.
 * Backed by /api/admin/org-types (key-based PUT/DELETE).
 */
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, FlatList, Switch, ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../utils/api';
import { showAlert } from '../../utils/alert';

interface OrgTypeRow {
  key: string; label: string; icon?: string; color?: string;
  description?: string; is_org?: boolean; active?: boolean;
  sort_order?: number; is_system?: boolean;
}

const COLOR_PRESETS = [
  '#6366F1', '#EC4899', '#0EA5E9', '#F59E0B', '#10B981', '#F43F5E',
  '#8B5CF6', '#14B8A6', '#EF4444', '#A855F7', '#64748B', '#0F172A',
];

// All Ionicons names (≈900 after dropping the -sharp variants) for the
// searchable picker. Computed once at module load.
const ALL_ICONS: string[] = Object.keys((Ionicons as any).glyphMap || {})
  .filter(n => !n.endsWith('-sharp'));

const EMPTY: OrgTypeRow = {
  key: '', label: '', icon: 'ellipse', color: '#6366F1',
  description: '', is_org: true, active: true, sort_order: 99,
};

export const OrgTypesManager = () => {
  const [items, setItems] = useState<OrgTypeRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [editor, setEditor] = useState<{ open: boolean; isNew: boolean; data: OrgTypeRow }>(
    { open: false, isNew: true, data: EMPTY });
  const [saving, setSaving] = useState(false);
  const [iconPickerOpen, setIconPickerOpen] = useState(false);
  const [iconSearch, setIconSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/org-types');
      setItems(r.data || []);
    } catch (_e) { setItems([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filteredIcons = useMemo(() => {
    const q = iconSearch.trim().toLowerCase();
    if (!q) return ALL_ICONS.slice(0, 120);
    return ALL_ICONS.filter(n => n.includes(q)).slice(0, 120);
  }, [iconSearch]);

  const openAdd = () => setEditor({ open: true, isNew: true, data: { ...EMPTY, sort_order: items.length + 1 } });
  const openEdit = (it: OrgTypeRow) => setEditor({ open: true, isNew: false, data: { ...it } });
  const setField = (patch: Partial<OrgTypeRow>) => setEditor(e => ({ ...e, data: { ...e.data, ...patch } }));

  const save = async () => {
    const d = editor.data;
    if (!d.label.trim()) { showAlert('Required', 'Label cannot be empty'); return; }
    const key = (d.key || d.label).trim().toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    if (!key) { showAlert('Required', 'Key cannot be empty'); return; }
    setSaving(true);
    try {
      const payload = {
        key, label: d.label.trim(), icon: d.icon || 'ellipse', color: d.color || '#6366F1',
        description: (d.description || '').trim(), is_org: !!d.is_org,
        active: !!d.active, sort_order: Number(d.sort_order) || 99,
      };
      if (editor.isNew) await api.post('/admin/org-types', payload);
      else await api.put(`/admin/org-types/${editor.data.key}`, payload);
      setEditor({ open: false, isNew: true, data: EMPTY });
      load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const remove = (it: OrgTypeRow) => {
    const inUseDecisions = !!it.is_system;
    showAlert(
      'Delete org type',
      inUseDecisions
        ? `“${it.label}” is a system type — it will be DISABLED (hidden from pickers) instead of deleted.`
        : `Delete “${it.label}”? Decisions already using it keep their value.`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: inUseDecisions ? 'Disable' : 'Delete', style: 'destructive', onPress: async () => {
          try { await api.delete(`/admin/org-types/${it.key}`); load(); }
          catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Delete failed'); }
        } },
      ]);
  };

  if (loading) return <ActivityIndicator style={{ marginTop: 40 }} color="#6366F1" />;

  return (
    <View style={{ flex: 1 }}>
      <View style={s.headRow}>
        <Text style={s.headHint}>
          These cards appear on the Initial-Info step of My Dezider, SWOT &amp; Pros-Cons, and in Solution targeting.
        </Text>
        <TouchableOpacity testID="org-type-add-btn" style={s.addBtn} onPress={openAdd}>
          <Ionicons name="add" size={16} color="#FFF" />
          <Text style={s.addBtnText}>Add</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={items}
        keyExtractor={(i) => i.key}
        contentContainerStyle={{ padding: 12, paddingBottom: 40 }}
        renderItem={({ item }) => (
          <View style={s.row} testID={`org-type-row-${item.key}`}>
            <View style={[s.iconBubble, { backgroundColor: (item.color || '#6366F1') + '22' }]}>
              <Ionicons name={(item.icon || 'ellipse') as any} size={20} color={item.color || '#6366F1'} />
            </View>
            <View style={{ flex: 1 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <Text style={[s.rowLabel, !item.active && s.rowOff]}>{item.label}</Text>
                {item.is_system && <View style={s.pill}><Text style={s.pillText}>system</Text></View>}
                {!item.active && <View style={[s.pill, s.pillRed]}><Text style={[s.pillText, { color: '#991B1B' }]}>disabled</Text></View>}
              </View>
              <Text style={s.rowSub}>{item.key}{item.description ? ` · ${item.description}` : ''}</Text>
            </View>
            <TouchableOpacity testID={`org-type-edit-${item.key}`} style={s.iconBtn} onPress={() => openEdit(item)}>
              <Ionicons name="pencil" size={18} color="#6366F1" />
            </TouchableOpacity>
            <TouchableOpacity testID={`org-type-delete-${item.key}`} style={s.iconBtn} onPress={() => remove(item)}>
              <Ionicons name="trash" size={18} color="#EF4444" />
            </TouchableOpacity>
          </View>
        )}
        ListEmptyComponent={<Text style={s.empty}>No org types</Text>}
      />

      {/* ── Editor modal ── */}
      <Modal visible={editor.open} transparent animationType="fade" onRequestClose={() => setEditor(e => ({ ...e, open: false }))}>
        <View style={s.modalBg}>
          <View style={s.modalCard}>
            <ScrollView style={{ maxHeight: 520 }} showsVerticalScrollIndicator={false}>
              <Text style={s.modalTitle}>{editor.isNew ? 'Add Org Type' : `Edit ${editor.data.label}`}</Text>

              <Text style={s.fieldLabel}>Label *</Text>
              <TextInput testID="org-type-label-input" style={s.input} placeholder="e.g. Family"
                value={editor.data.label} onChangeText={(v) => setField({ label: v })} />

              <Text style={s.fieldLabel}>Key {editor.isNew ? '(auto from label, editable)' : '(locked)'}</Text>
              <TextInput
                testID="org-type-key-input"
                style={[s.input, !editor.isNew && s.inputDisabled]}
                placeholder="FAMILY" autoCapitalize="characters"
                editable={editor.isNew}
                value={editor.isNew
                  ? (editor.data.key || editor.data.label.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, ''))
                  : editor.data.key}
                onChangeText={(v) => setField({ key: v.toUpperCase() })}
              />

              <Text style={s.fieldLabel}>Description (shown under the card)</Text>
              <TextInput testID="org-type-desc-input" style={s.input} placeholder="e.g. Family / household"
                value={editor.data.description || ''} onChangeText={(v) => setField({ description: v })} />

              <Text style={s.fieldLabel}>Icon</Text>
              <TouchableOpacity testID="org-type-icon-btn" style={s.iconSelectBtn} onPress={() => { setIconSearch(''); setIconPickerOpen(true); }}>
                <Ionicons name={(editor.data.icon || 'ellipse') as any} size={20} color={editor.data.color || '#6366F1'} />
                <Text style={s.iconSelectText}>{editor.data.icon || 'ellipse'}</Text>
                <Ionicons name="chevron-down" size={16} color="#94A3B8" />
              </TouchableOpacity>

              <Text style={s.fieldLabel}>Color</Text>
              <View style={s.colorRow}>
                {COLOR_PRESETS.map(c => (
                  <TouchableOpacity
                    key={c} testID={`org-type-color-${c.replace('#', '')}`}
                    style={[s.swatch, { backgroundColor: c }, editor.data.color === c && s.swatchActive]}
                    onPress={() => setField({ color: c })}
                  >
                    {editor.data.color === c && <Ionicons name="checkmark" size={14} color="#FFF" />}
                  </TouchableOpacity>
                ))}
              </View>
              <TextInput testID="org-type-color-input" style={s.input} placeholder="#6366F1"
                value={editor.data.color || ''} onChangeText={(v) => setField({ color: v })} autoCapitalize="none" />

              <View style={s.switchRow}>
                <Text style={s.fieldLabel}>Is an Organisation (vs Individual)</Text>
                <Switch testID="org-type-is-org-switch" value={!!editor.data.is_org}
                  onValueChange={(v) => setField({ is_org: v })} trackColor={{ false: '#CBD5E1', true: '#0EA5E9' }} />
              </View>
              <View style={s.switchRow}>
                <Text style={s.fieldLabel}>Active (visible in pickers)</Text>
                <Switch testID="org-type-active-switch" value={!!editor.data.active}
                  onValueChange={(v) => setField({ active: v })} trackColor={{ false: '#CBD5E1', true: '#10B981' }} />
              </View>

              <Text style={s.fieldLabel}>Sort order</Text>
              <TextInput testID="org-type-sort-input" style={s.input} keyboardType="number-pad"
                value={String(editor.data.sort_order ?? '')} onChangeText={(v) => setField({ sort_order: Number(v) || 0 })} />
            </ScrollView>

            <View style={s.modalActions}>
              <TouchableOpacity testID="org-type-cancel-btn" style={s.cancelBtn} onPress={() => setEditor({ open: false, isNew: true, data: EMPTY })}>
                <Text style={s.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity testID="org-type-save-btn" style={s.saveBtn} onPress={save} disabled={saving}>
                {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.saveBtnText}>Save</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ── Searchable Ionicons picker ── */}
      <Modal visible={iconPickerOpen} transparent animationType="fade" onRequestClose={() => setIconPickerOpen(false)}>
        <View style={s.modalBg}>
          <View style={[s.modalCard, { maxHeight: 540 }]}>
            <Text style={s.modalTitle}>Pick an icon</Text>
            <View style={s.searchRow}>
              <Ionicons name="search" size={16} color="#94A3B8" />
              <TextInput
                testID="org-type-icon-search"
                style={s.searchInput} placeholder="Search icons… (e.g. home, people, leaf)"
                value={iconSearch} onChangeText={setIconSearch} autoFocus
              />
            </View>
            <FlatList
              data={filteredIcons}
              keyExtractor={(n) => n}
              numColumns={5}
              style={{ maxHeight: 360 }}
              initialNumToRender={40}
              renderItem={({ item: name }) => (
                <TouchableOpacity
                  testID={`org-type-icon-opt-${name}`}
                  style={[s.iconCell, editor.data.icon === name && s.iconCellActive]}
                  onPress={() => { setField({ icon: name }); setIconPickerOpen(false); }}
                >
                  <Ionicons name={name as any} size={22} color={editor.data.icon === name ? '#6366F1' : '#475569'} />
                  <Text style={s.iconCellText} numberOfLines={1}>{name}</Text>
                </TouchableOpacity>
              )}
              ListEmptyComponent={<Text style={s.empty}>No icons match “{iconSearch}”</Text>}
            />
            <TouchableOpacity testID="org-type-icon-close" style={[s.cancelBtn, { marginTop: 10 }]} onPress={() => setIconPickerOpen(false)}>
              <Text style={s.cancelBtnText}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
};

const s = StyleSheet.create({
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingTop: 12 },
  headHint: { flex: 1, fontSize: 12, color: '#64748B', lineHeight: 17 },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#6366F1', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 9 },
  addBtnText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#EEF2F7' },
  iconBubble: { width: 38, height: 38, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  rowLabel: { fontSize: 14, color: '#0F172A', fontWeight: '600' },
  rowOff: { color: '#94A3B8', textDecorationLine: 'line-through' },
  rowSub: { fontSize: 11, color: '#94A3B8', marginTop: 2 },
  pill: { backgroundColor: '#F1F5F9', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2 },
  pillRed: { backgroundColor: '#FEE2E2' },
  pillText: { fontSize: 10, fontWeight: '700', color: '#475569' },
  iconBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  empty: { textAlign: 'center', color: '#94A3B8', marginTop: 30 },
  modalBg: { flex: 1, backgroundColor: '#00000066', alignItems: 'center', justifyContent: 'center', padding: 24 },
  modalCard: { width: '100%', maxWidth: 460, backgroundColor: '#FFF', borderRadius: 16, padding: 20 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A', marginBottom: 10 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: '#334155', marginTop: 10, marginBottom: 4, flex: 1 },
  input: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A' },
  inputDisabled: { backgroundColor: '#F8FAFC', color: '#94A3B8' },
  iconSelectBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10 },
  iconSelectText: { flex: 1, fontSize: 14, color: '#0F172A' },
  colorRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  swatch: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  swatchActive: { borderWidth: 2, borderColor: '#0F172A' },
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, backgroundColor: '#F8FAFC', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 10 },
  searchInput: { flex: 1, paddingVertical: 9, fontSize: 14, color: '#0F172A' },
  iconCell: { flex: 1, alignItems: 'center', paddingVertical: 10, gap: 4, borderRadius: 8 },
  iconCellActive: { backgroundColor: '#EEF2FF' },
  iconCellText: { fontSize: 9, color: '#64748B', maxWidth: 70 },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: 14 },
  cancelBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#F1F5F9', alignItems: 'center' },
  cancelBtnText: { fontSize: 14, fontWeight: '700', color: '#475569' },
  saveBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#6366F1', alignItems: 'center' },
  saveBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
});
