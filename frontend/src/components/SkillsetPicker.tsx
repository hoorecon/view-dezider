/**
 * SkillsetPicker — multi-select chips that aggregate skills across the user's
 * contacts (incl. Self). Used inside the Goal Setter "Achievable" section.
 *
 * New skill creation:
 *  - By default a new skill is added to the Self contact (per product spec).
 *  - User can toggle a small "Add to: Self ▾" picker to assign it to a
 *    different existing contact instead.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, FlatList, Modal, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import api from '../utils/api';

interface SkillRow {
  skill: string;
  contact_ids: string[];
  contact_names: string[];
}

interface Props {
  value: string[];                // selected skills
  onChange: (v: string[]) => void;
}

export default function SkillsetPicker({ value, onChange }: Props) {
  const selected = Array.isArray(value) ? value : [];
  const [skills, setSkills] = useState<SkillRow[]>([]);
  const [contacts, setContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [newSkill, setNewSkill] = useState('');
  const [target, setTarget] = useState<{ id: string; name: string; is_self?: boolean } | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [adding, setAdding] = useState(false);

  const refresh = async () => {
    try {
      const [agg, list] = await Promise.all([
        api.get('/contacts/skills/aggregate'),
        api.get('/contacts', { params: { limit: 200 } }),
      ]);
      setSkills(agg.data?.skills || []);
      const cs = list.data?.contacts || [];
      setContacts(cs);
      // Ensure target defaults to Self
      const self = cs.find((c: any) => c.is_self);
      if (self && !target) setTarget({ id: self.id, name: 'Self', is_self: true });
      else if (!self && cs.length > 0 && !target) setTarget({ id: cs[0].id, name: cs[0].name });
    } catch (e) {
      // Self may not exist yet — ensure it
      try {
        const s = await api.post('/contacts/ensure-self', {});
        setTarget({ id: s.data.id, name: 'Self', is_self: true });
        const list = await api.get('/contacts', { params: { limit: 200 } });
        setContacts(list.data?.contacts || []);
      } catch (e2) { /* ignore */ }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  const toggleSkill = (skill: string) => {
    if (selected.includes(skill)) onChange(selected.filter(s => s !== skill));
    else onChange([...selected, skill]);
  };

  const addNewSkill = async () => {
    const s = newSkill.trim();
    if (!s) return;
    if (!target) return;
    setAdding(true);
    try {
      await api.post(`/contacts/${target.id}/skills/add`, { skill: s });
      // Auto-select the newly added skill
      if (!selected.includes(s)) onChange([...selected, s]);
      setNewSkill('');
      await refresh();
    } catch (e: any) {
      // Soft fail: still surface as selected so user isn't blocked
      if (!selected.includes(s)) onChange([...selected, s]);
      setNewSkill('');
    } finally {
      setAdding(false);
    }
  };

  const allKnown = useMemo(() => skills.map(s => s.skill), [skills]);
  const unknownSelected = selected.filter(s => !allKnown.includes(s));

  if (loading) {
    return (
      <View style={st.loadWrap}>
        <ActivityIndicator size="small" color={COLORS.primary} />
        <Text style={st.loadText}>Loading skills from your contacts…</Text>
      </View>
    );
  }

  return (
    <View>
      <View style={st.headerRow}>
        <Ionicons name="construct" size={14} color="#D97706" />
        <Text style={st.headerText}>Skillset ({selected.length} selected)</Text>
      </View>
      <Text style={st.hint}>
        Pick skills available to you across Self & Contacts.
      </Text>

      {/* Existing skills as chips */}
      <View style={st.chipWrap}>
        {skills.length === 0 ? (
          <Text style={st.emptyHint}>No skills logged yet — add one below.</Text>
        ) : (
          skills.map(s => {
            const isOn = selected.includes(s.skill);
            return (
              <TouchableOpacity
                key={s.skill}
                style={[st.chip, isOn && st.chipOn]}
                onPress={() => toggleSkill(s.skill)}
              >
                <Text style={[st.chipTxt, isOn && st.chipTxtOn]}>{s.skill}</Text>
                <Text style={[st.chipMeta, isOn && { color: '#FED7AA' }]}>· {s.contact_ids.length}</Text>
              </TouchableOpacity>
            );
          })
        )}
        {unknownSelected.map(s => (
          <TouchableOpacity key={'u_' + s} style={[st.chip, st.chipOn]} onPress={() => toggleSkill(s)}>
            <Text style={[st.chipTxt, st.chipTxtOn]}>{s}</Text>
            <Text style={[st.chipMeta, { color: '#FED7AA' }]}>· new</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Add new skill row */}
      <View style={st.addRow}>
        <TextInput
          style={st.input}
          placeholder="+ Add a new skill"
          placeholderTextColor={COLORS.textMuted}
          value={newSkill}
          onChangeText={setNewSkill}
          onSubmitEditing={addNewSkill}
        />
        <TouchableOpacity style={st.targetBtn} onPress={() => setPickerOpen(true)}>
          <Ionicons name="person" size={12} color={COLORS.primary} />
          <Text style={st.targetTxt} numberOfLines={1}>
            {target ? (target.is_self ? 'Self' : target.name) : 'Self'}
          </Text>
          <Ionicons name="chevron-down" size={12} color={COLORS.primary} />
        </TouchableOpacity>
        <TouchableOpacity
          style={[st.addBtn, (!newSkill.trim() || adding) && { opacity: 0.5 }]}
          disabled={!newSkill.trim() || adding}
          onPress={addNewSkill}
        >
          {adding ? <ActivityIndicator size="small" color="#FFF" /> : <Ionicons name="add" size={16} color="#FFF" />}
        </TouchableOpacity>
      </View>

      {/* Target contact picker */}
      <Modal visible={pickerOpen} transparent animationType="fade" onRequestClose={() => setPickerOpen(false)}>
        <View style={st.modalBg}>
          <View style={st.modalCard}>
            <Text style={st.modalTitle}>Add new skill to…</Text>
            <FlatList
              data={contacts}
              keyExtractor={c => c.id}
              style={{ maxHeight: 320 }}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[st.row, target?.id === item.id && st.rowActive]}
                  onPress={() => { setTarget({ id: item.id, name: item.name, is_self: !!item.is_self }); setPickerOpen(false); }}
                >
                  <Ionicons
                    name={item.is_self ? 'person-circle' : 'person-outline'}
                    size={18}
                    color={item.is_self ? '#F59E0B' : COLORS.primary}
                  />
                  <Text style={st.rowName}>{item.is_self ? `${item.name} (You)` : item.name}</Text>
                </TouchableOpacity>
              )}
              ListEmptyComponent={<Text style={st.emptyHint}>No contacts yet.</Text>}
            />
            <TouchableOpacity style={st.closeBtn} onPress={() => setPickerOpen(false)}>
              <Text style={st.closeBtnTxt}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const st = StyleSheet.create({
  loadWrap: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 10 },
  loadText: { fontSize: 11, color: COLORS.textMuted },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  headerText: { fontSize: 12, fontWeight: '700', color: '#D97706' },
  hint: { fontSize: 11, color: '#92400E', marginBottom: 8 },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 14, borderWidth: 1, borderColor: '#FCD34D', backgroundColor: '#FFFBEB',
  },
  chipOn: { backgroundColor: '#F59E0B', borderColor: '#F59E0B' },
  chipTxt: { fontSize: 11, fontWeight: '600', color: '#92400E' },
  chipTxtOn: { color: '#FFFFFF' },
  chipMeta: { fontSize: 10, color: '#A16207' },
  emptyHint: { fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic' },
  addRow: { flexDirection: 'row', gap: 6, alignItems: 'center' },
  input: {
    flex: 1, borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: Platform.OS === 'web' ? 8 : 6,
    backgroundColor: '#FFFFFF', fontSize: 12, color: COLORS.textPrimary,
  },
  targetBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 8, paddingVertical: 6,
    borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#F9FAFB',
    maxWidth: 110,
  },
  targetTxt: { fontSize: 11, color: COLORS.primary, fontWeight: '600', flexShrink: 1 },
  addBtn: { width: 32, height: 32, borderRadius: 8, backgroundColor: '#D97706', justifyContent: 'center', alignItems: 'center' },

  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalCard: { backgroundColor: '#FFFFFF', borderRadius: 14, padding: 14, width: '100%', maxWidth: 380 },
  modalTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 8, paddingVertical: 10, borderRadius: 8, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  rowActive: { backgroundColor: '#FEF3C7' },
  rowName: { fontSize: 13, color: COLORS.textPrimary },
  closeBtn: { marginTop: 10, padding: 10, borderRadius: 8, backgroundColor: '#F1F5F9', alignItems: 'center' },
  closeBtnTxt: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
});
