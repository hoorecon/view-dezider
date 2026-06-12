/**
 * Admin → Masters management.
 * CRUD for religion, caste, language, occupation, skill, drive, trait.
 * Admins can add / edit / delete any row (including bundled seed rows).
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { OrgTypesManager } from '../../src/components/admin/OrgTypesManager';

const TYPES = [
  { key: 'org_type', label: 'Org Types' },
  { key: 'religion', label: 'Religions' },
  { key: 'caste', label: 'Castes' },
  { key: 'language', label: 'Languages' },
  { key: 'occupation', label: 'Occupations' },
  { key: 'skill', label: 'Skills' },
  { key: 'drive', label: 'Drives' },
  { key: 'trait', label: 'Traits' },
];

export default function AdminMastersScreen() {
  const router = useRouter();
  const [type, setType] = useState('org_type');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [editor, setEditor] = useState<{ open: boolean; id: string | null; value: string; parent: string }>(
    { open: false, id: null, value: '', parent: '' }
  );
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (type === 'org_type') return; // handled by OrgTypesManager
    setLoading(true);
    try {
      const res = await api.get(`/masters/${type}?include_inactive=true&limit=2000`);
      setItems(res.data.items || []);
    } catch (e) {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [type]);

  useEffect(() => { load(); }, [load]);

  const filtered = search.trim()
    ? items.filter(i => (i.value || '').toLowerCase().includes(search.trim().toLowerCase()))
    : items;

  const openAdd = () => setEditor({ open: true, id: null, value: '', parent: '' });
  const openEdit = (it: any) => setEditor({ open: true, id: it.master_id, value: it.value, parent: it.parent || '' });

  const save = async () => {
    const val = editor.value.trim();
    if (!val) { showAlert('Required', 'Value cannot be empty'); return; }
    setSaving(true);
    try {
      if (editor.id) {
        await api.put(`/masters/${editor.id}`, { value: val, parent: type === 'caste' ? (editor.parent || null) : undefined });
      } else {
        await api.post('/masters', { type, value: val, parent: type === 'caste' ? (editor.parent || null) : null });
      }
      setEditor({ open: false, id: null, value: '', parent: '' });
      load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  const remove = (it: any) => {
    showAlert('Delete', `Delete “${it.value}”?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/masters/${it.master_id}`); load(); }
        catch (e) { showAlert('Error', 'Delete failed'); }
      } },
    ]);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#6366F1', '#4338CA']} style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Masters</Text>
        {type !== 'org_type' && (
          <TouchableOpacity style={styles.addHdrBtn} onPress={openAdd}>
            <Ionicons name="add" size={22} color="#FFF" />
          </TouchableOpacity>
        )}
      </LinearGradient>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.typeBar} contentContainerStyle={{ paddingHorizontal: 12, gap: 8 }}>
        {TYPES.map(t => (
          <TouchableOpacity key={t.key} style={[styles.typeChip, type === t.key && styles.typeChipActive]} onPress={() => { setType(t.key); setSearch(''); }}>
            <Text style={[styles.typeChipText, type === t.key && { color: '#FFF' }]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {type === 'org_type' ? (
        <OrgTypesManager />
      ) : (
        <>
          <View style={styles.searchRow}>
            <Ionicons name="search" size={16} color="#94A3B8" />
            <TextInput style={styles.searchInput} placeholder={`Search ${type}…`} value={search} onChangeText={setSearch} />
            <Text style={styles.countText}>{filtered.length}</Text>
          </View>

          {loading ? (
            <ActivityIndicator style={{ marginTop: 40 }} color="#6366F1" />
          ) : (
            <FlatList
              data={filtered}
              keyExtractor={(i) => i.master_id}
              contentContainerStyle={{ padding: 12, paddingBottom: 40 }}
              renderItem={({ item }) => (
                <View style={styles.row}>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.rowText, !item.active && { color: '#94A3B8', textDecorationLine: 'line-through' }]}>{item.value}</Text>
                    {!!item.parent && <Text style={styles.rowSub}>{item.parent}{item.is_seed ? ' · seed' : ''}</Text>}
                    {!item.parent && item.is_seed && <Text style={styles.rowSub}>seed</Text>}
                  </View>
                  <TouchableOpacity style={styles.iconBtn} onPress={() => openEdit(item)}>
                    <Ionicons name="pencil" size={18} color="#6366F1" />
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.iconBtn} onPress={() => remove(item)}>
                    <Ionicons name="trash" size={18} color="#EF4444" />
                  </TouchableOpacity>
                </View>
              )}
              ListEmptyComponent={<Text style={styles.empty}>No items</Text>}
            />
          )}
        </>
      )}

      <Modal visible={editor.open} transparent animationType="fade" onRequestClose={() => setEditor({ ...editor, open: false })}>
        <View style={styles.modalBg}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>{editor.id ? 'Edit' : 'Add'} {type}</Text>
            <TextInput style={styles.modalInput} placeholder="Value" value={editor.value} onChangeText={(v) => setEditor({ ...editor, value: v })} autoFocus />
            {type === 'caste' && (
              <TextInput style={styles.modalInput} placeholder="Parent religion (e.g., Hindu)" value={editor.parent} onChangeText={(v) => setEditor({ ...editor, parent: v })} />
            )}
            <View style={styles.modalActions}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setEditor({ open: false, id: null, value: '', parent: '' })}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.saveBtn} onPress={save} disabled={saving}>
                {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.saveBtnText}>Save</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 14, gap: 10 },
  backBtn: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: '#FFF' },
  addHdrBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#ffffff33', alignItems: 'center', justifyContent: 'center' },
  typeBar: { maxHeight: 52, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  typeChip: { paddingHorizontal: 14, height: 34, borderRadius: 17, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center', marginVertical: 9 },
  typeChipActive: { backgroundColor: '#6366F1' },
  typeChipText: { fontSize: 13, fontWeight: '600', color: '#475569' },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8, margin: 12, paddingHorizontal: 12, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  searchInput: { flex: 1, paddingVertical: 10, fontSize: 14, color: '#0F172A' },
  countText: { fontSize: 12, color: '#94A3B8', fontWeight: '600' },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#EEF2F7' },
  rowText: { fontSize: 14, color: '#0F172A', fontWeight: '500' },
  rowSub: { fontSize: 11, color: '#94A3B8', marginTop: 2 },
  iconBtn: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  empty: { textAlign: 'center', color: '#94A3B8', marginTop: 40 },
  modalBg: { flex: 1, backgroundColor: '#00000066', alignItems: 'center', justifyContent: 'center', padding: 24 },
  modalCard: { width: '100%', maxWidth: 420, backgroundColor: '#FFF', borderRadius: 16, padding: 20 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A', marginBottom: 12, textTransform: 'capitalize' },
  modalInput: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, marginBottom: 10, color: '#0F172A' },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: 6 },
  cancelBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#F1F5F9', alignItems: 'center' },
  cancelBtnText: { fontSize: 14, fontWeight: '700', color: '#475569' },
  saveBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#6366F1', alignItems: 'center' },
  saveBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
});
