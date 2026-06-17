/**
 * Admin · Values Tracker CRUD
 * Manage 8 platform-default + custom org principles.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, Alert, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';

interface P { id: string; code: string; name: string; short?: string; body: string; bullets?: string[]; order: number; platform_default?: boolean; org_id?: string|null; active?: boolean; }

export default function AdminValues() {
  const router = useRouter();
  const [items, setItems] = useState<P[]>([]);
  const [editing, setEditing] = useState<P|null>(null);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState<any>({});

  const load = async () => {
    setBusy(true);
    try {
      const { data } = await api.get('/values/principles');
      setItems(data?.principles || []);
      const { data: s } = await api.get('/values/settings').catch(() => ({ data: {} }));
      setSettings(s || {});
    } finally { setBusy(false); }
  };
  useEffect(() => { load(); }, []);

  const startNew = () => setEditing({ id: '', code: '', name: '', short: '', body: '', bullets: [''], order: 100, platform_default: false, org_id: null, active: true });

  const save = async () => {
    if (!editing) return;
    if (!editing.code || !editing.name || !editing.body) { Alert.alert('Missing fields', 'code, name and body are required'); return; }
    try {
      if (editing.id) { await api.put(`/values/principles/${editing.id}`, editing); }
      else { await api.post('/values/principles', editing); }
      setEditing(null); await load();
    } catch (e: any) { Alert.alert('Save failed', e?.response?.data?.detail || e.message); }
  };

  const remove = async (p: P) => {
    if (p.platform_default) { Alert.alert('Protected', 'Platform-default principles cannot be deleted.'); return; }
    if (!confirm(`Delete '${p.name}'?`)) return;
    try { await api.delete(`/values/principles/${p.id}`); await load(); } catch(e:any){ Alert.alert('Delete failed', e?.response?.data?.detail || e.message); }
  };

  const saveSettings = async () => {
    try { await api.put('/values/settings', settings); Alert.alert('Saved', 'Threshold updated.'); }
    catch(e:any){ Alert.alert('Save failed', e?.response?.data?.detail || e.message); }
  };

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.title}>Values Tracker · Admin</Text>
        <Text style={s.subtitle}>{items.length} principles · 8 platform defaults are mandatory</Text>
      </View>
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        <View style={s.settingsCard}>
          <Text style={s.settingsLabel}>AI Alignment Block Threshold (public)</Text>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <TextInput style={s.numInput} keyboardType="numeric" placeholder="None = warn+log" value={String(settings?.public_block_threshold ?? '')} onChangeText={(v) => setSettings((p:any) => ({ ...p, public_block_threshold: v ? Number(v) : null }))} />
            <TouchableOpacity style={s.saveSmall} onPress={saveSettings}><Text style={s.saveSmallText}>Save</Text></TouchableOpacity>
          </View>
          <Text style={s.hint}>Block actions when alignment score &lt; threshold (0–10). Leave blank for warn+log only.</Text>
        </View>

        <TouchableOpacity style={s.addBtn} onPress={startNew}><Ionicons name="add" size={18} color="#FFF" /><Text style={s.addBtnText}>Add Custom Principle</Text></TouchableOpacity>

        {busy ? <ActivityIndicator /> : items.map((p) => (
          <View key={p.id} style={s.row}>
            <View style={s.rowHeader}>
              <View style={{ flex: 1 }}>
                <Text style={s.rowName}>{p.order}. {p.name}</Text>
                {p.short ? <Text style={s.rowShort}>{p.short}</Text> : null}
              </View>
              {p.platform_default && <View style={s.lockBadge}><Ionicons name="lock-closed" size={10} color="#FFF" /><Text style={s.lockBadgeText}>Default</Text></View>}
              <TouchableOpacity onPress={() => setEditing(p)} style={s.iconBtn}><Ionicons name="create" size={16} color="#3B82F6" /></TouchableOpacity>
              {!p.platform_default && <TouchableOpacity onPress={() => remove(p)} style={s.iconBtn}><Ionicons name="trash" size={16} color="#EF4444" /></TouchableOpacity>}
            </View>
          </View>
        ))}

        {editing !== null && (
          <View style={s.editorOverlay}>
            <View style={s.editor}>
              <Text style={s.editorTitle}>{editing.id ? 'Edit Principle' : 'New Principle'}</Text>
              <ScrollView style={{ maxHeight: 400 }}>
                <Text style={s.lbl}>Code (slug)</Text>
                <TextInput style={s.inp} value={editing.code} onChangeText={(v) => setEditing(p => p ? ({ ...p, code: v }) : null)} editable={!editing.platform_default} />
                <Text style={s.lbl}>Name</Text>
                <TextInput style={s.inp} value={editing.name} onChangeText={(v) => setEditing(p => p ? ({ ...p, name: v }) : null)} />
                <Text style={s.lbl}>Short summary</Text>
                <TextInput style={s.inp} value={editing.short || ''} onChangeText={(v) => setEditing(p => p ? ({ ...p, short: v }) : null)} />
                <Text style={s.lbl}>Body</Text>
                <TextInput style={[s.inp, { minHeight: 80, textAlignVertical: 'top' }]} multiline value={editing.body} onChangeText={(v) => setEditing(p => p ? ({ ...p, body: v }) : null)} />
                <Text style={s.lbl}>Bullets (one per line)</Text>
                <TextInput style={[s.inp, { minHeight: 80, textAlignVertical: 'top' }]} multiline value={(editing.bullets||[]).join('\n')} onChangeText={(v) => setEditing(p => p ? ({ ...p, bullets: v.split('\n') }) : null)} />
                <Text style={s.lbl}>Order</Text>
                <TextInput style={s.inp} keyboardType="numeric" value={String(editing.order)} onChangeText={(v) => setEditing(p => p ? ({ ...p, order: Number(v) || 100 }) : null)} />
              </ScrollView>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 12 }}>
                <TouchableOpacity style={s.cancelBtn} onPress={() => setEditing(null)}><Text style={s.cancelText}>Cancel</Text></TouchableOpacity>
                <TouchableOpacity style={s.saveBtn} onPress={save}><Text style={s.saveText}>Save</Text></TouchableOpacity>
              </View>
            </View>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { backgroundColor: '#003087', padding: 16 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  title: { color: '#FFF', fontSize: 20, fontWeight: '800' },
  subtitle: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  settingsCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 12 },
  settingsLabel: { fontSize: 13, fontWeight: '700', color: '#0F172A', marginBottom: 6 },
  numInput: { flex: 1, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 8, fontSize: 13, color: '#0F172A' },
  saveSmall: { backgroundColor: '#003087', paddingHorizontal: 14, justifyContent: 'center', borderRadius: 8 },
  saveSmallText: { color: '#FFF', fontWeight: '700' },
  hint: { fontSize: 11, color: '#64748B', marginTop: 6 },
  addBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#10B981', borderRadius: 10, padding: 10, marginBottom: 10 },
  addBtnText: { color: '#FFF', fontWeight: '700' },
  row: { backgroundColor: '#FFF', padding: 12, borderRadius: 10, marginBottom: 8, borderWidth: 1, borderColor: '#E2E8F0' },
  rowHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowName: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  rowShort: { fontSize: 11, color: '#64748B', marginTop: 2 },
  lockBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#475569', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  lockBadgeText: { color: '#FFF', fontSize: 10, fontWeight: '700' },
  iconBtn: { padding: 6 },
  editorOverlay: { position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 20 },
  editor: { backgroundColor: '#FFF', borderRadius: 12, padding: 16, maxHeight: '80%' },
  editorTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A', marginBottom: 10 },
  lbl: { fontSize: 12, fontWeight: '700', color: '#475569', marginBottom: 4, marginTop: 8 },
  inp: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 10, fontSize: 13, color: '#0F172A' },
  cancelBtn: { flex: 1, padding: 12, borderRadius: 8, backgroundColor: '#E2E8F0', alignItems: 'center' },
  cancelText: { color: '#475569', fontWeight: '700' },
  saveBtn: { flex: 2, padding: 12, borderRadius: 8, backgroundColor: '#003087', alignItems: 'center' },
  saveText: { color: '#FFF', fontWeight: '700' },
});
