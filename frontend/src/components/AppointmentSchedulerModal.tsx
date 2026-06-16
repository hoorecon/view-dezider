import React, { useState } from 'react';
import { Modal, View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, ScrollView, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../utils/api';

interface AppointmentSchedulerModalProps {
  visible: boolean;
  onClose: () => void;
  module: 'conflict-breaker' | 'pros-cons' | 'swot' | 'solution-finder' | 'goal-setter' | 'my-dezider';
  decisionId: string;
  stepId?: string;
  defaultTitle?: string;
  defaultParticipants?: { name?: string; phone?: string; email?: string }[];
  onScheduled?: (apptId: string) => void;
}

/**
 * Generic A/V appointment scheduler. Stores in UTC, displays in viewer's local
 * TZ. Reminders default to 60min + 15min before; both configurable here.
 * Real call uses the existing Jitsi room module.
 */
export const AppointmentSchedulerModal: React.FC<AppointmentSchedulerModalProps> = ({
  visible, onClose, module, decisionId, stepId, defaultTitle = 'Discussion call', defaultParticipants = [], onScheduled,
}) => {
  const now = new Date();
  const inOneHour = new Date(now.getTime() + 60 * 60 * 1000);
  const localIsoLike = (d: Date) => {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const [title, setTitle] = useState(defaultTitle);
  const [localDt, setLocalDt] = useState(localIsoLike(inOneHour));
  const [duration, setDuration] = useState('30');
  const [participants, setParticipants] = useState(defaultParticipants.length ? defaultParticipants : [{ name: '', phone: '', email: '' }]);
  const [reminders, setReminders] = useState<number[]>([60, 15]);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const updateParticipant = (i: number, key: 'name' | 'phone' | 'email', value: string) => {
    const next = [...participants]; (next[i] as any)[key] = value; setParticipants(next);
  };
  const addParticipant = () => setParticipants([...participants, { name: '', phone: '', email: '' }]);
  const removeParticipant = (i: number) => setParticipants(participants.filter((_, ix) => ix !== i));
  const toggleReminder = (mins: number) => {
    setReminders(r => r.includes(mins) ? r.filter(x => x !== mins) : [...r, mins].sort((a, b) => b - a));
  };

  const submit = async () => {
    setErr(null);
    if (!title.trim()) { setErr('Title required'); return; }
    if (!localDt) { setErr('Date/time required'); return; }
    const scheduledLocal = new Date(localDt);
    if (isNaN(scheduledLocal.getTime())) { setErr('Invalid date/time'); return; }
    if (scheduledLocal.getTime() < Date.now() + 2 * 60 * 1000) { setErr('Time must be at least 2 minutes in the future'); return; }
    setSubmitting(true);
    try {
      const { data } = await api.post('/collab/appointment', {
        module, decision_id: decisionId, step_id: stepId,
        title: title.trim(),
        scheduled_at: scheduledLocal.toISOString(),
        duration_minutes: parseInt(duration, 10) || 30,
        participants: participants.filter(p => (p.phone || p.email) && (p.phone || '').trim()),
        reminder_offsets_minutes: reminders,
      });
      if (data?.appointment?.appointment_id && onScheduled) onScheduled(data.appointment.appointment_id);
      onClose();
    } catch (e: any) {
      setErr(e?.response?.data?.detail || e?.message || 'Failed to schedule');
    } finally { setSubmitting(false); }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.card}>
          <ScrollView keyboardShouldPersistTaps="handled">
            <View style={s.headerRow}>
              <Text style={s.title}>Schedule A/V call</Text>
              <TouchableOpacity onPress={onClose} hitSlop={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                <Ionicons name="close" size={22} color="#475569" />
              </TouchableOpacity>
            </View>

            <Text style={s.label}>Title</Text>
            <TextInput value={title} onChangeText={setTitle} style={s.input} />

            <Text style={s.label}>When (your local time)</Text>
            {Platform.OS === 'web' ? (
              <input type="datetime-local" value={localDt} onChange={(e: any) => setLocalDt(e.target.value)} style={{ ...(s.input as any), padding: '10px 12px', border: '1px solid #CBD5E1', borderRadius: 10 }} />
            ) : (
              <TextInput value={localDt} onChangeText={setLocalDt} placeholder="YYYY-MM-DDTHH:MM" placeholderTextColor="#94A3B8" style={s.input} />
            )}
            <Text style={s.help}>Stored in UTC; each participant sees their local time in reminders.</Text>

            <Text style={s.label}>Duration (minutes)</Text>
            <TextInput value={duration} onChangeText={setDuration} keyboardType="numeric" style={s.input} />

            <Text style={s.label}>Reminders before call</Text>
            <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
              {[1440, 60, 30, 15, 5].map(m => {
                const active = reminders.includes(m);
                const label = m >= 60 ? `${Math.floor(m / 60)}h${m % 60 ? ` ${m % 60}m` : ''}` : `${m}m`;
                return (
                  <TouchableOpacity key={m} onPress={() => toggleReminder(m)} style={[s.chip, active && s.chipActive]}>
                    <Text style={[s.chipText, active && { color: '#FFF' }]}>{label}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <Text style={s.label}>Participants</Text>
            {participants.map((p, i) => (
              <View key={i} style={s.participantBox}>
                <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <Text style={{ fontSize: 12, fontWeight: '700', color: '#475569' }}>Participant {i + 1}</Text>
                  {participants.length > 1 && (
                    <TouchableOpacity onPress={() => removeParticipant(i)}>
                      <Ionicons name="trash-outline" size={16} color="#EF4444" />
                    </TouchableOpacity>
                  )}
                </View>
                <TextInput value={p.name} onChangeText={v => updateParticipant(i, 'name', v)} placeholder="Name" placeholderTextColor="#94A3B8" style={[s.input, { marginBottom: 6 }]} />
                <TextInput value={p.phone} onChangeText={v => updateParticipant(i, 'phone', v)} placeholder="WhatsApp +91..." placeholderTextColor="#94A3B8" style={[s.input, { marginBottom: 6 }]} />
                <TextInput value={p.email} onChangeText={v => updateParticipant(i, 'email', v)} placeholder="Email" placeholderTextColor="#94A3B8" autoCapitalize="none" style={s.input} />
              </View>
            ))}
            <TouchableOpacity onPress={addParticipant} style={s.addBtn}>
              <Ionicons name="add-circle-outline" size={16} color="#3B82F6" />
              <Text style={{ color: '#3B82F6', fontWeight: '700', fontSize: 13 }}>Add participant</Text>
            </TouchableOpacity>

            {err && <Text style={s.err}>{err}</Text>}

            <TouchableOpacity style={s.submitBtn} onPress={submit} disabled={submitting}>
              {submitting ? <ActivityIndicator color="#FFF" /> : (
                <><Ionicons name="videocam" size={16} color="#FFF" /><Text style={s.submitText}>Schedule call</Text></>
              )}
            </TouchableOpacity>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
};

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  card: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '92%' },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  title: { fontSize: 18, fontWeight: '800', color: '#0F172A' },
  label: { fontSize: 13, fontWeight: '700', color: '#0F172A', marginTop: 10, marginBottom: 4 },
  input: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A' },
  help: { fontSize: 11, color: '#64748B', marginTop: 4 },
  chip: { borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 16, paddingHorizontal: 12, paddingVertical: 6, backgroundColor: '#FFF' },
  chipActive: { backgroundColor: '#3B82F6', borderColor: '#3B82F6' },
  chipText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  participantBox: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 10, marginBottom: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingVertical: 6 },
  submitBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#003087', borderRadius: 12, paddingVertical: 14, marginTop: 18 },
  submitText: { fontSize: 15, fontWeight: '800', color: '#FFF' },
  err: { fontSize: 13, color: '#DC2626', marginTop: 10, fontWeight: '600' },
});

export default AppointmentSchedulerModal;
