/**
 * ProfessionalRolesPanel
 * Multi-organization role list editor for Contacts page (Iter 129).
 * Add / edit / delete / set primary (★) role.
 */
import React, { useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, TextInput, Modal, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export interface ProfessionalRole {
  role_id?: string;
  organization: string;
  designation?: string;
  org_type?: string;
  org_subtype?: string;
  department?: string;
  reporting_to?: string;
  start_date?: string;
  end_date?: string;
  is_current?: boolean;
  is_primary?: boolean;
  notes?: string;
}

interface Props {
  roles: ProfessionalRole[];
  onChange: (next: ProfessionalRole[]) => void;
}

const ORG_TYPES = ['individual', 'business', 'ngo', 'association', 'govt'];

export default function ProfessionalRolesPanel({ roles = [], onChange }: Props) {
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<ProfessionalRole>({ organization: '', is_current: true, is_primary: roles.length === 0 });

  const startNew = () => { setDraft({ organization: '', is_current: true, is_primary: roles.length === 0 }); setEditing(-1); };
  const startEdit = (i: number) => { setDraft({ ...roles[i] }); setEditing(i); };
  const cancel = () => { setEditing(null); };

  const setPrimary = (i: number) => {
    const next = roles.map((r, j) => ({ ...r, is_primary: j === i }));
    onChange(next);
  };
  const remove = (i: number) => {
    if (!confirm('Remove this role?')) return;
    let next = roles.filter((_, j) => j !== i);
    if (next.length && !next.some(r => r.is_primary)) next = next.map((r, j) => ({ ...r, is_primary: j === 0 }));
    onChange(next);
  };
  const save = () => {
    if (!draft.organization.trim()) { Alert.alert('Org required', 'Enter an organization name.'); return; }
    let next = [...roles];
    if (editing === -1) {
      next.push({ ...draft });
    } else if (editing !== null) {
      next[editing] = { ...draft };
    }
    // Enforce single primary
    if (draft.is_primary) next = next.map((r, j) => j === (editing === -1 ? next.length - 1 : editing) ? r : ({ ...r, is_primary: false }));
    if (!next.some(r => r.is_primary) && next.length) next[0].is_primary = true;
    onChange(next);
    setEditing(null);
  };

  return (
    <View style={s.wrap}>
      <View style={s.headerRow}>
        <Ionicons name="briefcase" size={14} color="#003087" />
        <Text style={s.title}>Roles &amp; Organizations</Text>
        <Text style={s.count}>{roles.length}</Text>
        <TouchableOpacity style={s.addBtn} onPress={startNew}><Ionicons name="add" size={14} color="#FFF" /><Text style={s.addBtnText}>Add</Text></TouchableOpacity>
      </View>
      {roles.length === 0 ? (
        <Text style={s.empty}>No roles yet. Add multiple organizations / designations the contact holds.</Text>
      ) : roles.map((r, i) => (
        <View key={r.role_id || i} style={s.row}>
          <TouchableOpacity onPress={() => setPrimary(i)} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }}>
            <Ionicons name={r.is_primary ? 'star' : 'star-outline'} size={18} color={r.is_primary ? '#F59E0B' : '#94A3B8'} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.rowOrg}>{r.organization}</Text>
            {r.designation ? <Text style={s.rowDes}>{r.designation}{r.department ? ` · ${r.department}` : ''}</Text> : null}
            {(r.start_date || r.end_date) && <Text style={s.rowDates}>{r.start_date || '?'} → {r.is_current ? 'present' : (r.end_date || '?')}</Text>}
          </View>
          <TouchableOpacity onPress={() => startEdit(i)} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }}><Ionicons name="create" size={14} color="#3B82F6" /></TouchableOpacity>
          <TouchableOpacity onPress={() => remove(i)} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }}><Ionicons name="trash" size={14} color="#EF4444" /></TouchableOpacity>
        </View>
      ))}

      <Modal visible={editing !== null} transparent animationType="fade" onRequestClose={cancel}>
        <View style={s.overlay}>
          <View style={s.modal}>
            <Text style={s.modalTitle}>{editing === -1 ? 'Add Role' : 'Edit Role'}</Text>
            <ScrollView style={{ maxHeight: 400 }}>
              <Text style={s.lbl}>Organization *</Text>
              <TextInput style={s.inp} value={draft.organization} onChangeText={(v) => setDraft(d => ({ ...d, organization: v }))} placeholder="e.g. JELCOS AI Pvt Ltd" placeholderTextColor="#94A3B8" />
              <Text style={s.lbl}>Designation</Text>
              <TextInput style={s.inp} value={draft.designation || ''} onChangeText={(v) => setDraft(d => ({ ...d, designation: v }))} placeholder="e.g. Founder & CEO" placeholderTextColor="#94A3B8" />
              <Text style={s.lbl}>Org Type</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {ORG_TYPES.map(t => (
                  <TouchableOpacity key={t} style={[s.chip, draft.org_type === t && s.chipOn]} onPress={() => setDraft(d => ({ ...d, org_type: t }))}><Text style={[s.chipText, draft.org_type === t && { color: '#FFF' }]}>{t}</Text></TouchableOpacity>
                ))}
              </ScrollView>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <View style={{ flex: 1 }}><Text style={s.lbl}>Department</Text><TextInput style={s.inp} value={draft.department || ''} onChangeText={(v) => setDraft(d => ({ ...d, department: v }))} placeholder="Engineering" placeholderTextColor="#94A3B8" /></View>
                <View style={{ flex: 1 }}><Text style={s.lbl}>Reports to</Text><TextInput style={s.inp} value={draft.reporting_to || ''} onChangeText={(v) => setDraft(d => ({ ...d, reporting_to: v }))} placeholder="Manager name" placeholderTextColor="#94A3B8" /></View>
              </View>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <View style={{ flex: 1 }}><Text style={s.lbl}>Start date</Text><TextInput style={s.inp} value={draft.start_date || ''} onChangeText={(v) => setDraft(d => ({ ...d, start_date: v }))} placeholder="YYYY-MM" placeholderTextColor="#94A3B8" /></View>
                <View style={{ flex: 1 }}><Text style={s.lbl}>End date</Text><TextInput style={s.inp} value={draft.end_date || ''} onChangeText={(v) => setDraft(d => ({ ...d, end_date: v, is_current: false }))} placeholder="YYYY-MM (blank = current)" placeholderTextColor="#94A3B8" editable={!draft.is_current} /></View>
              </View>
              <View style={{ flexDirection: 'row', gap: 12, marginTop: 6, marginBottom: 6 }}>
                <TouchableOpacity style={s.toggleRow} onPress={() => setDraft(d => ({ ...d, is_current: !d.is_current, end_date: d.is_current ? d.end_date : '' }))}>
                  <Ionicons name={draft.is_current ? 'checkbox' : 'square-outline'} size={16} color={draft.is_current ? '#10B981' : '#94A3B8'} />
                  <Text style={s.toggleText}>Currently active</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.toggleRow} onPress={() => setDraft(d => ({ ...d, is_primary: !d.is_primary }))}>
                  <Ionicons name={draft.is_primary ? 'star' : 'star-outline'} size={16} color={draft.is_primary ? '#F59E0B' : '#94A3B8'} />
                  <Text style={s.toggleText}>Primary (★)</Text>
                </TouchableOpacity>
              </View>
              <Text style={s.lbl}>Notes</Text>
              <TextInput style={[s.inp, { minHeight: 40, textAlignVertical: 'top' }]} multiline value={draft.notes || ''} onChangeText={(v) => setDraft(d => ({ ...d, notes: v }))} placeholder="Anything else worth noting" placeholderTextColor="#94A3B8" />
            </ScrollView>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
              <TouchableOpacity style={s.cancelBtn} onPress={cancel}><Text style={s.cancelText}>Cancel</Text></TouchableOpacity>
              <TouchableOpacity style={s.saveBtn} onPress={save}><Text style={s.saveText}>Save Role</Text></TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#E2E8F0' },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  title: { fontSize: 13, fontWeight: '800', color: '#003087', flex: 1 },
  count: { fontSize: 11, color: '#64748B', fontWeight: '700' },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#10B981', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4 },
  addBtnText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
  empty: { fontSize: 11, color: '#64748B', fontStyle: 'italic' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderTopWidth: 1, borderColor: '#F1F5F9' },
  rowOrg: { fontSize: 12, fontWeight: '700', color: '#0F172A' },
  rowDes: { fontSize: 11, color: '#64748B', marginTop: 1 },
  rowDates: { fontSize: 10, color: '#94A3B8', marginTop: 1 },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 16 },
  modal: { backgroundColor: '#FFF', borderRadius: 12, padding: 16, maxHeight: '90%' },
  modalTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', marginBottom: 8 },
  lbl: { fontSize: 11, fontWeight: '700', color: '#475569', marginTop: 6, marginBottom: 3 },
  inp: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 8, fontSize: 12, color: '#0F172A' },
  chip: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC', marginRight: 5 },
  chipOn: { backgroundColor: '#003087', borderColor: '#003087' },
  chipText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  toggleText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  cancelBtn: { flex: 1, padding: 10, borderRadius: 8, backgroundColor: '#E2E8F0', alignItems: 'center' },
  cancelText: { color: '#475569', fontWeight: '700' },
  saveBtn: { flex: 2, padding: 10, borderRadius: 8, backgroundColor: '#003087', alignItems: 'center' },
  saveText: { color: '#FFF', fontWeight: '700' },
});
