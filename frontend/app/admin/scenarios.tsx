/**
 * Admin → Intake Scenarios (hos_decision_templates) manager.
 * CRUD + ORG-TYPE TAGGING for the scenario/template suggestions shown on the
 * decision intake (Step-4 dropdown of My Dezider / SWOT). Templates tagged
 * with org types (e.g. FAMILY) appear ONLY when the user picks that
 * "This decision is for…" card; untagged templates are generic (everyone).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput, FlatList,
  ActivityIndicator, Modal, ScrollView, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { useOrgTypes } from '../../src/hooks/useOrgTypes';
import { safeBack } from '../../src/utils/navigation';

interface Tpl {
  id: string; title: string; description?: string;
  life_area_id?: string; ask_type_id?: string;
  tags?: string[]; org_types?: string[]; applies_to_modules?: string[];
  decision_types?: string[]; popularity?: number; order?: number; status?: string;
}

const MODULES = ['dezider', 'swot'];
const EMPTY: Tpl = {
  id: '', title: '', description: '', life_area_id: '', ask_type_id: 'at_need',
  tags: [], org_types: [], applies_to_modules: ['dezider'], decision_types: [],
  popularity: 50, order: 99, status: 'active',
};

export default function AdminScenarios() {
  const router = useRouter();
  const { orgTypes } = useOrgTypes();
  const [items, setItems] = useState<Tpl[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [orgFilter, setOrgFilter] = useState<string>('');     // '' = all, 'GENERIC' = untagged
  const [lifeAreas, setLifeAreas] = useState<{ id: string; name: string }[]>([]);
  const [askTypes, setAskTypes] = useState<{ id: string; name: string }[]>([]);
  const [editor, setEditor] = useState<{ open: boolean; isNew: boolean; data: Tpl }>(
    { open: false, isNew: true, data: EMPTY });
  const [tagsText, setTagsText] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      if (orgFilter) p.append('org_type', orgFilter);
      const r = await api.get(`/hos/admin/templates?${p}`);
      setItems(r.data?.items || []);
    } catch (_e) { setItems([]); }
    finally { setLoading(false); }
  }, [orgFilter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    api.get('/hos/life-areas').then(r => setLifeAreas(r.data || [])).catch(() => {});
    api.get('/hos/ask-types').then(r => setAskTypes(r.data || [])).catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(t => t.title.toLowerCase().includes(q)
      || (t.tags || []).some(x => x.toLowerCase().includes(q)));
  }, [items, search]);

  const laName = (id?: string) => lifeAreas.find(l => l.id === id)?.name || id || '—';

  const openAdd = () => { setTagsText(''); setEditor({ open: true, isNew: true, data: { ...EMPTY } }); };
  const openEdit = (t: Tpl) => { setTagsText((t.tags || []).join(', ')); setEditor({ open: true, isNew: false, data: { ...t } }); };
  const setField = (patch: Partial<Tpl>) => setEditor(e => ({ ...e, data: { ...e.data, ...patch } }));

  const toggleOrgType = (key: string) => {
    const cur = editor.data.org_types || [];
    setField({ org_types: cur.includes(key) ? cur.filter(k => k !== key) : [...cur, key] });
  };
  const toggleModule = (m: string) => {
    const cur = editor.data.applies_to_modules || [];
    setField({ applies_to_modules: cur.includes(m) ? cur.filter(k => k !== m) : [...cur, m] });
  };

  const save = async () => {
    const d = editor.data;
    if (!d.title.trim()) { showAlert('Required', 'Title cannot be empty'); return; }
    setSaving(true);
    try {
      const payload = {
        title: d.title.trim(), description: (d.description || '').trim(),
        life_area_id: d.life_area_id || null, ask_type_id: d.ask_type_id || null,
        tags: tagsText.split(',').map(s => s.trim()).filter(Boolean),
        org_types: d.org_types || [],
        applies_to_modules: (d.applies_to_modules || []).length ? d.applies_to_modules : ['dezider'],
        popularity: Number(d.popularity) || 50, order: Number(d.order) || 99,
        status: d.status === 'active' ? 'active' : 'inactive',
      };
      if (editor.isNew) await api.post('/hos/admin/templates', payload);
      else await api.put(`/hos/admin/templates/${d.id}`, payload);
      setEditor({ open: false, isNew: true, data: EMPTY });
      load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const remove = (t: Tpl) => {
    showAlert('Delete scenario', `Delete “${t.title}”? This cannot be undone.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/hos/templates/${t.id}`); load(); }
        catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Delete failed'); }
      } },
    ]);
  };

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.header}>
        <TouchableOpacity testID="scenarios-back-btn" style={s.backBtn} onPress={() => safeBack(router)}>
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Intake Scenarios</Text>
        <TouchableOpacity testID="scenario-add-btn" style={s.addHdrBtn} onPress={openAdd}>
          <Ionicons name="add" size={22} color="#FFF" />
        </TouchableOpacity>
      </View>
      <Text style={s.subHint}>
        Scenario suggestions on the decision intake. Tag with Org Types to show them ONLY for
        that “This decision is for…” card — untagged scenarios are shown to everyone.
      </Text>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabBar} contentContainerStyle={{ paddingHorizontal: 12, gap: 8 }}>
        {[{ key: '', label: 'All' }, { key: 'GENERIC', label: 'Generic (untagged)' },
          ...orgTypes.map(o => ({ key: o.key, label: o.label }))].map(t => (
          <TouchableOpacity
            key={t.key || 'all'} testID={`scenario-filter-${t.key || 'ALL'}`}
            style={[s.tab, orgFilter === t.key && s.tabActive]}
            onPress={() => setOrgFilter(t.key)}>
            <Text style={[s.tabText, orgFilter === t.key && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <View style={s.searchRow}>
        <Ionicons name="search" size={16} color="#94A3B8" />
        <TextInput testID="scenario-search" style={s.searchInput} placeholder="Search scenarios…"
          value={search} onChangeText={setSearch} />
        <Text style={s.countText}>{filtered.length}</Text>
      </View>

      {loading ? (
        <ActivityIndicator style={{ marginTop: 40 }} color="#6366F1" />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(i) => i.id}
          contentContainerStyle={{ padding: 12, paddingBottom: 40 }}
          renderItem={({ item }) => (
            <View style={s.row} testID={`scenario-row-${item.id}`}>
              <View style={{ flex: 1 }}>
                <Text style={[s.rowTitle, item.status !== 'active' && s.rowOff]}>{item.title}</Text>
                <Text style={s.rowSub}>{laName(item.life_area_id)}</Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 5 }}>
                  {(item.org_types || []).length === 0
                    ? <View style={s.pillGeneric}><Text style={s.pillGenericText}>All org types</Text></View>
                    : (item.org_types || []).map(k => {
                      const ot = orgTypes.find(o => o.key === k);
                      return (
                        <View key={k} style={[s.pill, { backgroundColor: (ot?.color || '#6366F1') + '1A' }]}>
                          <Text style={[s.pillText, { color: ot?.color || '#6366F1' }]}>{ot?.label || k}</Text>
                        </View>
                      );
                    })}
                  {item.status !== 'active' && (
                    <View style={[s.pill, { backgroundColor: '#FEE2E2' }]}>
                      <Text style={[s.pillText, { color: '#991B1B' }]}>inactive</Text>
                    </View>
                  )}
                </View>
              </View>
              <TouchableOpacity testID={`scenario-edit-${item.id}`} style={s.iconBtn} onPress={() => openEdit(item)}>
                <Ionicons name="pencil" size={18} color="#6366F1" />
              </TouchableOpacity>
              <TouchableOpacity testID={`scenario-delete-${item.id}`} style={s.iconBtn} onPress={() => remove(item)}>
                <Ionicons name="trash" size={18} color="#EF4444" />
              </TouchableOpacity>
            </View>
          )}
          ListEmptyComponent={<Text style={s.empty}>No scenarios</Text>}
        />
      )}

      {/* ── Editor modal ── */}
      <Modal visible={editor.open} transparent animationType="fade" onRequestClose={() => setEditor(e => ({ ...e, open: false }))}>
        <View style={s.modalBg}>
          <View style={s.modalCard}>
            <ScrollView style={{ maxHeight: 540 }} showsVerticalScrollIndicator={false}>
              <Text style={s.modalTitle}>{editor.isNew ? 'Add Scenario' : 'Edit Scenario'}</Text>

              <Text style={s.fieldLabel}>Title *</Text>
              <TextInput testID="scenario-title-input" style={s.input}
                placeholder="e.g. Where should we go for our family vacation?"
                value={editor.data.title} onChangeText={v => setField({ title: v })} />

              <Text style={s.fieldLabel}>Description</Text>
              <TextInput testID="scenario-desc-input" style={[s.input, { minHeight: 60 }]} multiline
                value={editor.data.description || ''} onChangeText={v => setField({ description: v })} />

              <Text style={s.fieldLabel}>Org Types (empty = shown to everyone)</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 7 }}>
                {orgTypes.map(o => {
                  const active = (editor.data.org_types || []).includes(o.key);
                  return (
                    <TouchableOpacity key={o.key} testID={`scenario-org-${o.key}`}
                      style={[s.chip, active && { backgroundColor: o.color + '1A', borderColor: o.color }]}
                      onPress={() => toggleOrgType(o.key)}>
                      <Text style={[s.chipText, active && { color: o.color, fontWeight: '700' }]}>{o.label}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              <Text style={s.fieldLabel}>Life Area</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 7 }}>
                {lifeAreas.map(la => (
                  <TouchableOpacity key={la.id} testID={`scenario-la-${la.id}`}
                    style={[s.chip, editor.data.life_area_id === la.id && s.chipActive]}
                    onPress={() => setField({ life_area_id: la.id })}>
                    <Text style={[s.chipText, editor.data.life_area_id === la.id && s.chipTextActive]} numberOfLines={1}>
                      {la.name}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={s.fieldLabel}>Ask Type</Text>
              <View style={{ flexDirection: 'row', gap: 7 }}>
                {askTypes.map(at => (
                  <TouchableOpacity key={at.id} testID={`scenario-at-${at.id}`}
                    style={[s.chip, editor.data.ask_type_id === at.id && s.chipActive]}
                    onPress={() => setField({ ask_type_id: at.id })}>
                    <Text style={[s.chipText, editor.data.ask_type_id === at.id && s.chipTextActive]}>{at.name}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={s.fieldLabel}>Modules</Text>
              <View style={{ flexDirection: 'row', gap: 7 }}>
                {MODULES.map(m => {
                  const active = (editor.data.applies_to_modules || []).includes(m);
                  return (
                    <TouchableOpacity key={m} testID={`scenario-module-${m}`}
                      style={[s.chip, active && s.chipActive]} onPress={() => toggleModule(m)}>
                      <Text style={[s.chipText, active && s.chipTextActive]}>{m}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              <Text style={s.fieldLabel}>Tags (comma-separated, used by free-text matching)</Text>
              <TextInput testID="scenario-tags-input" style={s.input}
                placeholder="vacation, holiday, travel" value={tagsText} onChangeText={setTagsText} />

              <View style={s.switchRow}>
                <Text style={s.fieldLabel}>Active (visible on intake)</Text>
                <Switch testID="scenario-active-switch" value={editor.data.status === 'active'}
                  onValueChange={(v) => setField({ status: v ? 'active' : 'inactive' })}
                  trackColor={{ false: '#CBD5E1', true: '#10B981' }} />
              </View>
            </ScrollView>

            <View style={s.modalActions}>
              <TouchableOpacity testID="scenario-cancel-btn" style={s.cancelBtn}
                onPress={() => setEditor({ open: false, isNew: true, data: EMPTY })}>
                <Text style={s.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity testID="scenario-save-btn" style={s.saveBtn} onPress={save} disabled={saving}>
                {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.saveBtnText}>Save</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#EEF2F7' },
  backBtn: { width: 40, height: 40, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 17, fontWeight: '800', color: '#0F172A' },
  addHdrBtn: { width: 38, height: 38, borderRadius: 10, backgroundColor: '#6366F1', alignItems: 'center', justifyContent: 'center' },
  subHint: { fontSize: 11.5, color: '#64748B', paddingHorizontal: 14, paddingTop: 8, lineHeight: 16 },
  tabBar: { maxHeight: 46, marginTop: 8 },
  tab: { paddingHorizontal: 13, paddingVertical: 8, borderRadius: 18, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E2E8F0' },
  tabActive: { backgroundColor: '#6366F1', borderColor: '#6366F1' },
  tabText: { fontSize: 12.5, color: '#475569', fontWeight: '600' },
  tabTextActive: { color: '#FFF' },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 12, marginTop: 10, paddingHorizontal: 12, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  searchInput: { flex: 1, paddingVertical: 9, fontSize: 14, color: '#0F172A' },
  countText: { fontSize: 12, color: '#94A3B8', fontWeight: '700' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#EEF2F7' },
  rowTitle: { fontSize: 14, color: '#0F172A', fontWeight: '600' },
  rowOff: { color: '#94A3B8' },
  rowSub: { fontSize: 11, color: '#94A3B8', marginTop: 2 },
  pill: { borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2 },
  pillText: { fontSize: 10, fontWeight: '700' },
  pillGeneric: { borderRadius: 8, paddingHorizontal: 7, paddingVertical: 2, backgroundColor: '#F1F5F9' },
  pillGenericText: { fontSize: 10, fontWeight: '700', color: '#64748B' },
  iconBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  empty: { textAlign: 'center', color: '#94A3B8', marginTop: 30 },
  modalBg: { flex: 1, backgroundColor: '#00000066', alignItems: 'center', justifyContent: 'center', padding: 24 },
  modalCard: { width: '100%', maxWidth: 520, backgroundColor: '#FFF', borderRadius: 16, padding: 20 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A', marginBottom: 8 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: '#334155', marginTop: 12, marginBottom: 5, flex: 1 },
  input: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A' },
  chip: { paddingHorizontal: 11, paddingVertical: 7, borderRadius: 16, borderWidth: 1, borderColor: '#E2E8F0', backgroundColor: '#FFF', maxWidth: 220 },
  chipActive: { backgroundColor: '#EEF2FF', borderColor: '#6366F1' },
  chipText: { fontSize: 12, color: '#475569' },
  chipTextActive: { color: '#4338CA', fontWeight: '700' },
  switchRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: 14 },
  cancelBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#F1F5F9', alignItems: 'center' },
  cancelBtnText: { fontSize: 14, fontWeight: '700', color: '#475569' },
  saveBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#6366F1', alignItems: 'center' },
  saveBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
});
