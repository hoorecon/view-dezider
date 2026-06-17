/**
 * Admin · 7×7 Org Matrix Masters
 * Manage 7 Divisions + 7 Drivers (grouped under Team/Systems/Strategy) + Scoring Scale.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';

export default function AdminSevenSeven() {
  const router = useRouter();
  const [tab, setTab] = useState<'divisions'|'drivers'|'scale'>('divisions');
  const [divisions, setDivisions] = useState<any[]>([]);
  const [drivers, setDrivers] = useState<any[]>([]);
  const [scale, setScale] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<any>(null);

  const load = async () => {
    setBusy(true);
    try {
      const [d1, d2, d3] = await Promise.all([
        api.get('/seven-seven/divisions'),
        api.get('/seven-seven/drivers'),
        api.get('/seven-seven/scale'),
      ]);
      setDivisions(d1.data?.divisions || []);
      setDrivers(d2.data?.drivers || []);
      setScale(d3.data?.scale || []);
    } finally { setBusy(false); }
  };
  useEffect(() => { load(); }, []);

  const startNew = () => {
    if (tab === 'divisions') setEditing({ kind: 'division', code: '', name: '', department: '', icon: 'folder', color: '#64748B', order: 100, sub_teams: [], active: true });
    else if (tab === 'drivers') setEditing({ kind: 'driver', code: '', name: '', category: 'team', hint: '', order: 100, active: true });
  };

  const save = async () => {
    if (!editing) return;
    try {
      if (editing.kind === 'division') {
        await api.post('/seven-seven/divisions', editing);
      } else if (editing.kind === 'driver') {
        await api.post('/seven-seven/drivers', editing);
      }
      setEditing(null); await load();
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
  };

  const remove = async (kind: 'division'|'driver', code: string, isDefault: boolean) => {
    if (isDefault) { showAlert('Protected', 'Platform-default items cannot be deleted.'); return; }
    if (!confirm('Delete?')) return;
    try { await api.delete(`/seven-seven/${kind}s/${code}`); await load(); }
    catch(e:any){ showAlert('Delete failed', e?.response?.data?.detail || e.message); }
  };

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.title}>7×7 Org Matrix · Masters</Text>
        <Text style={s.subtitle}>Divisions × Drivers × Scoring Scale</Text>
      </View>
      <View style={s.tabs}>
        {(['divisions','drivers','scale'] as const).map(t => (
          <TouchableOpacity key={t} style={[s.tab, tab===t && s.tabActive]} onPress={() => setTab(t)}>
            <Text style={[s.tabText, tab===t && s.tabTextActive]}>{t.toUpperCase()}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        {tab !== 'scale' && (
          <TouchableOpacity style={s.addBtn} onPress={startNew}><Ionicons name="add" size={18} color="#FFF" /><Text style={s.addBtnText}>Add {tab === 'divisions' ? 'Division' : 'Driver'}</Text></TouchableOpacity>
        )}
        {busy ? <ActivityIndicator /> : (
          tab === 'divisions' ? (
            divisions.map((d) => (
              <View key={d.code} style={s.row}>
                <View style={[s.colorPip, { backgroundColor: d.color }]} />
                <View style={{ flex: 1 }}>
                  <Text style={s.rowName}>{d.order}. {d.name}</Text>
                  <Text style={s.rowShort}>{d.department} · {d.sub_teams?.length || 0} teams</Text>
                </View>
                {d.platform_default && <View style={s.lockBadge}><Ionicons name="lock-closed" size={10} color="#FFF" /></View>}
                <TouchableOpacity onPress={() => setEditing({ ...d, kind: 'division' })} style={s.iconBtn}><Ionicons name="create" size={16} color="#3B82F6" /></TouchableOpacity>
                {!d.platform_default && <TouchableOpacity onPress={() => remove('division', d.code, false)} style={s.iconBtn}><Ionicons name="trash" size={16} color="#EF4444" /></TouchableOpacity>}
              </View>
            ))
          ) : tab === 'drivers' ? (
            drivers.map((dr) => (
              <View key={dr.code} style={s.row}>
                <View style={[s.catBadge, dr.category==='team' && { backgroundColor: '#DBEAFE' }, dr.category==='systems' && { backgroundColor: '#FEF3C7' }, dr.category==='strategy' && { backgroundColor: '#DCFCE7' }]}>
                  <Text style={[s.catBadgeText, dr.category==='team' && { color: '#1E40AF' }, dr.category==='systems' && { color: '#92400E' }, dr.category==='strategy' && { color: '#166534' }]}>{(dr.category||'').toUpperCase()}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.rowName}>{dr.order}. {dr.name}</Text>
                  <Text style={s.rowShort}>{dr.hint}</Text>
                </View>
                {dr.platform_default && <View style={s.lockBadge}><Ionicons name="lock-closed" size={10} color="#FFF" /></View>}
                <TouchableOpacity onPress={() => setEditing({ ...dr, kind: 'driver' })} style={s.iconBtn}><Ionicons name="create" size={16} color="#3B82F6" /></TouchableOpacity>
                {!dr.platform_default && <TouchableOpacity onPress={() => remove('driver', dr.code, false)} style={s.iconBtn}><Ionicons name="trash" size={16} color="#EF4444" /></TouchableOpacity>}
              </View>
            ))
          ) : (
            scale.map((sc) => (
              <View key={sc.code} style={s.row}>
                <View style={[s.colorPip, { backgroundColor: sc.color }]} />
                <Text style={s.rowName}>{sc.name}</Text>
                <View style={s.lockBadge}><Ionicons name="lock-closed" size={10} color="#FFF" /></View>
              </View>
            ))
          )
        )}

        {editing !== null && (
          <View style={s.editorOverlay}>
            <View style={s.editor}>
              <Text style={s.editorTitle}>{editing.kind === 'division' ? 'Division' : 'Driver'}</Text>
              <ScrollView style={{ maxHeight: 360 }}>
                <Text style={s.lbl}>Code</Text>
                <TextInput style={s.inp} value={editing.code} onChangeText={(v) => setEditing((p:any) => ({ ...p, code: v }))} />
                <Text style={s.lbl}>Name</Text>
                <TextInput style={s.inp} value={editing.name} onChangeText={(v) => setEditing((p:any) => ({ ...p, name: v }))} />
                {editing.kind === 'division' && (<>
                  <Text style={s.lbl}>Department</Text>
                  <TextInput style={s.inp} value={editing.department||''} onChangeText={(v) => setEditing((p:any) => ({ ...p, department: v }))} />
                  <Text style={s.lbl}>Color</Text>
                  <TextInput style={s.inp} value={editing.color||''} onChangeText={(v) => setEditing((p:any) => ({ ...p, color: v }))} />
                </>)}
                {editing.kind === 'driver' && (<>
                  <Text style={s.lbl}>Category</Text>
                  <View style={{ flexDirection: 'row', gap: 6 }}>
                    {['team','systems','strategy'].map(c => (
                      <TouchableOpacity key={c} style={[s.catPick, editing.category===c && s.catPickActive]} onPress={() => setEditing((p:any) => ({ ...p, category: c }))}>
                        <Text style={[s.catPickText, editing.category===c && { color: '#FFF' }]}>{c}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                  <Text style={s.lbl}>Hint</Text>
                  <TextInput style={s.inp} value={editing.hint||''} onChangeText={(v) => setEditing((p:any) => ({ ...p, hint: v }))} />
                </>)}
                <Text style={s.lbl}>Order</Text>
                <TextInput style={s.inp} keyboardType="numeric" value={String(editing.order)} onChangeText={(v) => setEditing((p:any) => ({ ...p, order: Number(v) || 100 }))} />
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
  tabs: { flexDirection: 'row', backgroundColor: '#FFF', borderBottomWidth: 1, borderColor: '#E2E8F0' },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderColor: '#003087' },
  tabText: { fontSize: 11, fontWeight: '700', color: '#64748B' },
  tabTextActive: { color: '#003087', fontWeight: '800' },
  addBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#10B981', borderRadius: 10, padding: 10, marginBottom: 10 },
  addBtnText: { color: '#FFF', fontWeight: '700' },
  row: { backgroundColor: '#FFF', padding: 10, borderRadius: 10, marginBottom: 8, borderWidth: 1, borderColor: '#E2E8F0', flexDirection: 'row', alignItems: 'center', gap: 8 },
  colorPip: { width: 18, height: 18, borderRadius: 4 },
  rowName: { fontSize: 13, fontWeight: '700', color: '#0F172A', flexShrink: 1 },
  rowShort: { fontSize: 11, color: '#64748B', marginTop: 2 },
  catBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, backgroundColor: '#F1F5F9' },
  catBadgeText: { fontSize: 9, fontWeight: '800' },
  lockBadge: { width: 22, height: 22, borderRadius: 11, backgroundColor: '#475569', alignItems: 'center', justifyContent: 'center' },
  iconBtn: { padding: 6 },
  editorOverlay: { position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 20 },
  editor: { backgroundColor: '#FFF', borderRadius: 12, padding: 16, maxHeight: '80%' },
  editorTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A', marginBottom: 10 },
  lbl: { fontSize: 12, fontWeight: '700', color: '#475569', marginBottom: 4, marginTop: 8 },
  inp: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 10, fontSize: 13, color: '#0F172A' },
  catPick: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC' },
  catPickActive: { backgroundColor: '#003087', borderColor: '#003087' },
  catPickText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  cancelBtn: { flex: 1, padding: 12, borderRadius: 8, backgroundColor: '#E2E8F0', alignItems: 'center' },
  cancelText: { color: '#475569', fontWeight: '700' },
  saveBtn: { flex: 2, padding: 12, borderRadius: 8, backgroundColor: '#003087', alignItems: 'center' },
  saveText: { color: '#FFF', fontWeight: '700' },
});
