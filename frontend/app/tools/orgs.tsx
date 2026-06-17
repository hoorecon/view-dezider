/**
 * Custom Orgs — Interim layer between Life Area and GEM.
 * List, create, delete user-created Orgs of any OrgType under any Life Area/Sub-Area.
 * From an Org, jump into the 7×7 assessment and 6 LeGs hierarchy.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, Alert, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../src/utils/api';

const LIFE_AREAS = ['Career','Business','Finance','Family','Health','Relationships','Personal','Social','Spiritual','Recreation'];
const ORG_TYPES = ['BUSINESS','NGO','GOVT','EDUCATION','FAMILY','COMMUNITY','SPIRITUAL','HEALTHCARE','OTHER'];

export default function OrgsScreen() {
  const router = useRouter();
  const [orgs, setOrgs] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<any>(null);

  const load = async () => {
    setBusy(true);
    try { const { data } = await api.get('/seven-seven/orgs'); setOrgs(data?.orgs || []); }
    finally { setBusy(false); }
  };
  useFocusEffect(useCallback(() => { load(); }, []));

  const create = () => setEditing({ name: '', org_type: 'BUSINESS', life_area: LIFE_AREAS[0], sub_area: '', description: '', icon: 'business', color: '#4338CA' });

  const save = async () => {
    if (!editing.name?.trim()) { Alert.alert('Name required'); return; }
    try { await api.post('/seven-seven/orgs', editing); setEditing(null); await load(); }
    catch(e:any){ Alert.alert('Save failed', e?.response?.data?.detail || e.message); }
  };

  const remove = async (org: any) => {
    if (!confirm(`Archive '${org.name}'?`)) return;
    try { await api.delete(`/seven-seven/orgs/${org.id}`); await load(); }
    catch(e:any){ Alert.alert('Delete failed', e?.response?.data?.detail || e.message); }
  };

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.title}>My Organizations</Text>
        <Text style={s.subtitle}>Custom orgs across life areas · 7×7 matrix · 6 LeGs goals</Text>
      </View>
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        <TouchableOpacity style={s.addBtn} onPress={create}><Ionicons name="add-circle" size={20} color="#FFF" /><Text style={s.addBtnText}>Create Organization</Text></TouchableOpacity>
        {busy ? <ActivityIndicator /> : orgs.length === 0 ? (
          <View style={s.empty}>
            <Ionicons name="business-outline" size={48} color="#CBD5E1" />
            <Text style={s.emptyText}>No orgs yet. Create your first interim structure under any life area.</Text>
            <Text style={s.emptyHint}>Orgs unlock the 7×7 assessment matrix and the 6 Level Goal Setting hierarchy.</Text>
          </View>
        ) : orgs.map((o) => (
          <TouchableOpacity key={o.id} style={s.orgCard} onPress={() => router.push({ pathname: '/tools/org-detail', params: { id: o.id } } as any)}>
            <View style={[s.orgIcon, { backgroundColor: o.color || '#4338CA' }]}><Ionicons name={(o.icon || 'business') as any} size={22} color="#FFF" /></View>
            <View style={{ flex: 1 }}>
              <Text style={s.orgName}>{o.name}</Text>
              <Text style={s.orgMeta}>{o.org_type} · {o.life_area}{o.sub_area ? ` / ${o.sub_area}` : ''}</Text>
              {o.description ? <Text style={s.orgDesc} numberOfLines={2}>{o.description}</Text> : null}
            </View>
            <TouchableOpacity onPress={(e) => { e.stopPropagation(); remove(o); }} hitSlop={{ top: 10, right: 10, bottom: 10, left: 10 }}><Ionicons name="trash" size={16} color="#EF4444" /></TouchableOpacity>
          </TouchableOpacity>
        ))}

        {editing && (
          <View style={s.editorOverlay}>
            <View style={s.editor}>
              <Text style={s.editorTitle}>New Organization</Text>
              <ScrollView style={{ maxHeight: 420 }}>
                <Text style={s.lbl}>Name</Text>
                <TextInput style={s.inp} value={editing.name} onChangeText={(v) => setEditing((p:any)=>({...p, name: v}))} placeholder="e.g. JELCOS AI Pvt Ltd" placeholderTextColor="#94A3B8" />
                <Text style={s.lbl}>Org Type</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  {ORG_TYPES.map(t => <TouchableOpacity key={t} style={[s.chip, editing.org_type===t && s.chipOn]} onPress={() => setEditing((p:any)=>({...p, org_type: t}))}><Text style={[s.chipText, editing.org_type===t && { color: '#FFF' }]}>{t}</Text></TouchableOpacity>)}
                </ScrollView>
                <Text style={s.lbl}>Life Area</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  {LIFE_AREAS.map(la => <TouchableOpacity key={la} style={[s.chip, editing.life_area===la && s.chipOn]} onPress={() => setEditing((p:any)=>({...p, life_area: la}))}><Text style={[s.chipText, editing.life_area===la && { color: '#FFF' }]}>{la}</Text></TouchableOpacity>)}
                </ScrollView>
                <Text style={s.lbl}>Sub-Area (optional)</Text>
                <TextInput style={s.inp} value={editing.sub_area} onChangeText={(v) => setEditing((p:any)=>({...p, sub_area: v}))} placeholder="e.g. SaaS, Property, etc." placeholderTextColor="#94A3B8" />
                <Text style={s.lbl}>Description</Text>
                <TextInput style={[s.inp, { minHeight: 64, textAlignVertical: 'top' }]} multiline value={editing.description} onChangeText={(v) => setEditing((p:any)=>({...p, description: v}))} placeholder="What this Org delivers" placeholderTextColor="#94A3B8" />
              </ScrollView>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 12 }}>
                <TouchableOpacity style={s.cancelBtn} onPress={() => setEditing(null)}><Text style={s.cancelText}>Cancel</Text></TouchableOpacity>
                <TouchableOpacity style={s.saveBtn} onPress={save}><Text style={s.saveText}>Create</Text></TouchableOpacity>
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
  addBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#10B981', borderRadius: 10, padding: 12, marginBottom: 12 },
  addBtnText: { color: '#FFF', fontWeight: '800' },
  empty: { alignItems: 'center', padding: 24 },
  emptyText: { fontSize: 13, color: '#64748B', marginTop: 12, textAlign: 'center' },
  emptyHint: { fontSize: 11, color: '#94A3B8', marginTop: 6, textAlign: 'center', fontStyle: 'italic' },
  orgCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8, borderWidth: 1, borderColor: '#E2E8F0' },
  orgIcon: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  orgName: { fontSize: 14, fontWeight: '800', color: '#0F172A' },
  orgMeta: { fontSize: 11, color: '#64748B', marginTop: 2 },
  orgDesc: { fontSize: 12, color: '#334155', marginTop: 4 },
  editorOverlay: { position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 20 },
  editor: { backgroundColor: '#FFF', borderRadius: 12, padding: 16, maxHeight: '85%' },
  editorTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A', marginBottom: 8 },
  lbl: { fontSize: 12, fontWeight: '700', color: '#475569', marginTop: 8, marginBottom: 4 },
  inp: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 10, fontSize: 13, color: '#0F172A' },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC', marginRight: 6 },
  chipOn: { backgroundColor: '#003087', borderColor: '#003087' },
  chipText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  cancelBtn: { flex: 1, padding: 12, borderRadius: 8, backgroundColor: '#E2E8F0', alignItems: 'center' },
  cancelText: { color: '#475569', fontWeight: '700' },
  saveBtn: { flex: 2, padding: 12, borderRadius: 8, backgroundColor: '#003087', alignItems: 'center' },
  saveText: { color: '#FFF', fontWeight: '700' },
});
