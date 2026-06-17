/**
 * ConvertToActionButton
 * Drop-in CTA for end of any Decision Kickstarter (MyDezider, P&C, SWOT, SF, Instant Dezider, GEM).
 * Wraps POST /api/action-items with the universal source_module / source_id schema.
 */
import React, { useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, Alert, Modal, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../utils/api';

export type DecisionSource = 'MYDEZIDER_MPPS' | 'PROS_CONS' | 'SWOT' | 'PNA' | 'CONFLICT_BREAKER' | 'CLD' | 'GEM' | 'SOLUTION_FINDER' | 'INSTANT_DEZIDER' | 'GOAL_SETTER' | 'AALA' | 'ATEX';

interface Props {
  source_module: DecisionSource;
  source_id: string;
  source_label?: string;
  default_title?: string;
  default_description?: string;
  default_who?: string;
  default_by_when?: string;
  default_priority?: 'low' | 'medium' | 'high' | 'urgent';
  life_area?: string;
  compact?: boolean;
  onCreated?: (action: any) => void;
}

export default function ConvertToActionButton({
  source_module, source_id, source_label,
  default_title = '', default_description = '', default_who = '', default_by_when = '',
  default_priority = 'medium', life_area, compact = false, onCreated,
}: Props) {
  const router = useRouter();
  const [modalOpen, setModalOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [recType, setRecType] = useState<'one_time' | 'recurring'>('one_time');
  const [freq, setFreq] = useState<'daily' | 'weekly' | 'monthly'>('daily');
  const [title, setTitle] = useState(default_title);
  const [desc, setDesc] = useState(default_description);
  const [who, setWho] = useState(default_who);
  const [byWhen, setByWhen] = useState(default_by_when);
  const [priority, setPriority] = useState(default_priority);
  const [createdId, setCreatedId] = useState<string | null>(null);

  const open = () => {
    setTitle(default_title); setDesc(default_description); setWho(default_who);
    setByWhen(default_by_when); setPriority(default_priority);
    setRecType('one_time'); setFreq('daily'); setCreatedId(null);
    setModalOpen(true);
  };

  const create = async () => {
    if (!title.trim()) { Alert.alert('Title required'); return; }
    setBusy(true);
    try {
      const body: any = {
        source_module,
        source_id,
        source_label: source_label || `${source_module} · ${title.slice(0, 60)}`,
        title: title.trim(),
        description: desc.trim(),
        who: who.trim(),
        by_when: byWhen.trim() || null,
        priority,
        recurrence_type: recType,
        life_area: life_area || null,
      };
      if (recType === 'recurring') body.recurrence_frequency = freq;
      const { data } = await api.post('/action-items', body);
      const newId = data?.action_id || data?.id;
      setCreatedId(newId);
      onCreated?.(data);
    } catch (e: any) {
      Alert.alert('Failed', e?.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  };

  const portTo = async (target: 'CTT' | 'LIFESTYLE') => {
    if (!createdId) return;
    try {
      await api.post(`/action-items/${createdId}/port`, { target });
      Alert.alert('Ported', `Action sent to ${target === 'CTT' ? 'CTT' : 'Lifestyle Dezider'}.`);
      setModalOpen(false);
      router.push(target === 'CTT' ? '/tools/ctt' as any : '/tools/lifestyle' as any);
    } catch (e: any) { Alert.alert('Port failed', e?.response?.data?.detail || e.message); }
  };

  return (
    <>
      <TouchableOpacity style={[s.btn, compact && s.btnCompact]} onPress={open}>
        <Ionicons name="checkmark-circle" size={compact ? 14 : 18} color="#FFF" />
        <Text style={[s.btnText, compact && { fontSize: 11 }]}>{compact ? 'To Action' : 'Convert to Action'}</Text>
      </TouchableOpacity>

      <Modal visible={modalOpen} transparent animationType="fade" onRequestClose={() => setModalOpen(false)}>
        <View style={s.overlay}>
          <View style={s.modal}>
            <View style={s.modalHead}>
              <Text style={s.modalTitle}>Convert to Action Tracker</Text>
              <TouchableOpacity onPress={() => setModalOpen(false)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            {!createdId ? (
              <View>
                <Text style={s.lbl}>Title *</Text>
                <TextInput style={s.inp} value={title} onChangeText={setTitle} placeholder="e.g. Talk to mentor about next steps" placeholderTextColor="#94A3B8" />
                <Text style={s.lbl}>Description</Text>
                <TextInput style={[s.inp, { minHeight: 50, textAlignVertical: 'top' }]} multiline value={desc} onChangeText={setDesc} placeholder="Optional details..." placeholderTextColor="#94A3B8" />
                <View style={{ flexDirection: 'row', gap: 6 }}>
                  <View style={{ flex: 1 }}><Text style={s.lbl}>Who</Text><TextInput style={s.inp} value={who} onChangeText={setWho} placeholder="Me" placeholderTextColor="#94A3B8" /></View>
                  <View style={{ flex: 1 }}><Text style={s.lbl}>By when</Text><TextInput style={s.inp} value={byWhen} onChangeText={setByWhen} placeholder="YYYY-MM-DD" placeholderTextColor="#94A3B8" /></View>
                </View>
                <Text style={s.lbl}>Priority</Text>
                <View style={{ flexDirection: 'row', gap: 6 }}>
                  {(['low', 'medium', 'high', 'urgent'] as const).map(p => (
                    <TouchableOpacity key={p} style={[s.pchip, priority === p && s.pchipOn]} onPress={() => setPriority(p)}><Text style={[s.pchipText, priority === p && { color: '#FFF' }]}>{p}</Text></TouchableOpacity>
                  ))}
                </View>
                <Text style={s.lbl}>Type</Text>
                <View style={{ flexDirection: 'row', gap: 6 }}>
                  <TouchableOpacity style={[s.tchip, recType === 'one_time' && s.tchipOn]} onPress={() => setRecType('one_time')}><Text style={[s.tchipText, recType === 'one_time' && { color: '#FFF' }]}>One-time</Text></TouchableOpacity>
                  <TouchableOpacity style={[s.tchip, recType === 'recurring' && s.tchipOn]} onPress={() => setRecType('recurring')}><Text style={[s.tchipText, recType === 'recurring' && { color: '#FFF' }]}>Recurring</Text></TouchableOpacity>
                </View>
                {recType === 'recurring' && (
                  <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
                    {(['daily', 'weekly', 'monthly'] as const).map(f => (
                      <TouchableOpacity key={f} style={[s.pchip, freq === f && s.pchipOn]} onPress={() => setFreq(f)}><Text style={[s.pchipText, freq === f && { color: '#FFF' }]}>{f}</Text></TouchableOpacity>
                    ))}
                  </View>
                )}
                <TouchableOpacity style={[s.create, busy && { opacity: 0.6 }]} onPress={create} disabled={busy}>
                  {busy ? <ActivityIndicator color="#FFF" /> : <><Ionicons name="add-circle" size={16} color="#FFF" /><Text style={s.createText}>  Create Action</Text></>}
                </TouchableOpacity>
              </View>
            ) : (
              <View>
                <View style={s.successPill}><Ionicons name="checkmark-circle" size={16} color="#16A34A" /><Text style={s.successText}>Action created · {title.slice(0, 50)}</Text></View>
                <Text style={[s.lbl, { marginTop: 12 }]}>Where should it execute?</Text>
                <TouchableOpacity style={[s.portBtn, { backgroundColor: '#0EA5E9' }]} onPress={() => portTo('CTT')}><Ionicons name="flash" size={14} color="#FFF" /><Text style={s.portText}> Run as CTT (on-demand)</Text></TouchableOpacity>
                <TouchableOpacity style={[s.portBtn, { backgroundColor: '#059669' }]} onPress={() => portTo('LIFESTYLE')}><Ionicons name="repeat" size={14} color="#FFF" /><Text style={s.portText}> Run as Lifestyle Dezider (recurring)</Text></TouchableOpacity>
                <TouchableOpacity style={s.portBtnGhost} onPress={() => { setModalOpen(false); router.push('/tools/action-center' as any); }}><Text style={s.portTextGhost}>Just keep in Action Tracker</Text></TouchableOpacity>
              </View>
            )}
          </View>
        </View>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#10B981', borderRadius: 10, paddingVertical: 12, paddingHorizontal: 16 },
  btnCompact: { paddingVertical: 6, paddingHorizontal: 10, borderRadius: 6 },
  btnText: { color: '#FFF', fontWeight: '800', fontSize: 13 },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 20 },
  modal: { backgroundColor: '#FFF', borderRadius: 12, padding: 16, maxHeight: '90%' },
  modalHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A' },
  lbl: { fontSize: 11, fontWeight: '700', color: '#475569', marginTop: 8, marginBottom: 4 },
  inp: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 10, fontSize: 13, color: '#0F172A' },
  pchip: { flex: 1, paddingVertical: 6, borderRadius: 6, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC', alignItems: 'center' },
  pchipOn: { backgroundColor: '#003087', borderColor: '#003087' },
  pchipText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  tchip: { flex: 1, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC', alignItems: 'center' },
  tchipOn: { backgroundColor: '#10B981', borderColor: '#10B981' },
  tchipText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  create: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#003087', borderRadius: 10, padding: 12, marginTop: 12 },
  createText: { color: '#FFF', fontWeight: '800' },
  successPill: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#DCFCE7', padding: 10, borderRadius: 8 },
  successText: { color: '#166534', fontSize: 12, fontWeight: '700', flex: 1 },
  portBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', borderRadius: 10, padding: 12, marginTop: 8 },
  portText: { color: '#FFF', fontWeight: '700', fontSize: 13 },
  portBtnGhost: { padding: 12, marginTop: 4, alignItems: 'center' },
  portTextGhost: { color: '#475569', fontWeight: '700', fontSize: 12 },
});
