/**
 * Time Dezider — Raja Guru screen.
 *
 * Tabs: Morning · Midday · Evening · Next Action.
 * Each pulls its own endpoint. User taps Accept / Defer / Skip on any pick;
 * feedback is POSTed to tune future ranking. Key timings + nudge cadence
 * editable under a settings icon.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

const SLOTS = [
  { id: 'day-plan', label: 'Morning', icon: 'sunny', endpoint: '/raja-guru/day-plan' },
  { id: 'midday', label: 'Midday', icon: 'time', endpoint: '/raja-guru/midday-check' },
  { id: 'evening', label: 'Evening', icon: 'moon', endpoint: '/raja-guru/evening-retro' },
  { id: 'next', label: 'Now', icon: 'flash', endpoint: '/raja-guru/next-action' },
];

export default function TimeDeziderScreen() {
  const router = useRouter();
  const [slot, setSlot] = useState('day-plan');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [prefs, setPrefs] = useState<any>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [kt, setKt] = useState({ wake_up: '06:30', bed_time: '22:30', business_start: '09:30', business_end: '18:30' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const s = SLOTS.find(x => x.id === slot)!;
      const [r, pr] = await Promise.all([
        api.get(s.endpoint),
        api.get('/raja-guru/preferences'),
      ]);
      setData(r.data);
      setPrefs(pr.data);
      setKt({
        wake_up: pr.data.wake_up, bed_time: pr.data.bed_time,
        business_start: pr.data.business_start, business_end: pr.data.business_end,
      });
    } catch {
      setData(null);
    } finally { setLoading(false); }
  }, [slot]);

  useEffect(() => { load(); }, [load]);

  const decide = async (pick: any, decision: 'accept' | 'defer' | 'skip') => {
    try {
      await api.post('/raja-guru/feedback', {
        nudge_id: `${slot}_${pick.ref_id}`,
        action_ref_id: pick.ref_id,
        action_ref_type: pick.kind,
        decision,
      });
      showAlert('Got it', `Recorded: ${decision}`);
    } catch {}
  };

  const saveSettings = async () => {
    try {
      await api.post('/daily-time-log/preferences', kt);
      await api.post('/raja-guru/preferences', {
        nudge_morning: prefs.nudge_morning,
        nudge_midday: prefs.nudge_midday,
        nudge_evening: prefs.nudge_evening,
        nudge_hourly: prefs.nudge_hourly,
        nudge_event_driven: prefs.nudge_event_driven,
      });
      setSettingsOpen(false);
      load();
    } catch {
      showAlert('Error', 'Failed to save settings');
    }
  };

  const picks = data?.picks || (data?.pick ? [data.pick] : []);
  const wins = data?.wins || [];
  const gaps = data?.gaps || [];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#6D28D9', '#EC4899']} style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={26} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1, marginLeft: 8 }}>
          <Text style={styles.h1}>Time Dezider</Text>
          <Text style={styles.sub}>Raja Guru for a Raja</Text>
        </View>
        <TouchableOpacity onPress={() => setSettingsOpen(true)}>
          <Ionicons name="settings" size={22} color="#FFF" />
        </TouchableOpacity>
      </LinearGradient>

      <View style={styles.tabRow}>
        {SLOTS.map(s => {
          const sel = s.id === slot;
          return (
            <TouchableOpacity key={s.id} onPress={() => setSlot(s.id)}
              style={[styles.tab, sel && styles.tabActive]}>
              <Ionicons name={s.icon as any} size={16} color={sel ? '#FFF' : COLORS.textMuted} />
              <Text style={[styles.tabText, sel && { color: '#FFF' }]}>{s.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          <View style={styles.introCard}>
            <Ionicons name="sparkles" size={18} color="#6D28D9" />
            <Text style={styles.introText}>{data?.intro}</Text>
          </View>

          {data?.key_timings && (
            <View style={styles.ktStrip}>
              {['wake_up', 'business_start', 'business_end', 'bed_time'].map(k => (
                <View key={k} style={styles.ktItem}>
                  <Text style={styles.ktLabel}>
                    {k.replace('_', ' ').replace('up', 'Up').replace('start', 'Start').replace('end', 'End').replace('bed time', 'Bed')}
                  </Text>
                  <Text style={styles.ktValue}>{data.key_timings[k]}</Text>
                </View>
              ))}
            </View>
          )}

          {wins.length > 0 && (
            <View>
              <Text style={styles.sectionTitle}>Wins today</Text>
              {wins.map((w: string, i: number) => (
                <View key={i} style={[styles.noteRow, { backgroundColor: '#ECFDF5' }]}>
                  <Ionicons name="checkmark-circle" size={16} color="#10B981" />
                  <Text style={styles.noteText}>{w}</Text>
                </View>
              ))}
            </View>
          )}
          {gaps.length > 0 && (
            <View>
              <Text style={styles.sectionTitle}>Gaps to close</Text>
              {gaps.map((g: string, i: number) => (
                <View key={i} style={[styles.noteRow, { backgroundColor: '#FEF2F2' }]}>
                  <Ionicons name="alert-circle" size={16} color="#EF4444" />
                  <Text style={styles.noteText}>{g}</Text>
                </View>
              ))}
            </View>
          )}

          {picks.length > 0 && (
            <View>
              <Text style={styles.sectionTitle}>Picks ({picks.length})</Text>
              {picks.map((p: any, i: number) => (
                <View key={i} style={styles.pickCard}>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <View style={[styles.kindChip, { backgroundColor: p.kind === 'ctt_task' ? '#DBEAFE' : '#DCFCE7' }]}>
                        <Text style={[styles.kindChipText, { color: p.kind === 'ctt_task' ? '#1D4ED8' : '#15803D' }]}>
                          {p.kind === 'ctt_task' ? 'TASK' : 'LIFESTYLE'}
                        </Text>
                      </View>
                      <Text style={styles.pickScore}>score {p.score}</Text>
                    </View>
                    <Text style={styles.pickTitle}>{p.title}</Text>
                    <Text style={styles.pickReason}>{p.reason}</Text>
                    <Text style={styles.pickEstimate}>≈ {p.estimated_minutes} min</Text>
                  </View>
                  <View style={styles.pickActions}>
                    <TouchableOpacity style={[styles.actBtn, styles.actAccept]} onPress={() => decide(p, 'accept')}>
                      <Ionicons name="checkmark" size={14} color="#FFF" />
                    </TouchableOpacity>
                    <TouchableOpacity style={[styles.actBtn, styles.actDefer]} onPress={() => decide(p, 'defer')}>
                      <Ionicons name="time" size={14} color="#FFF" />
                    </TouchableOpacity>
                    <TouchableOpacity style={[styles.actBtn, styles.actSkip]} onPress={() => decide(p, 'skip')}>
                      <Ionicons name="close" size={14} color="#FFF" />
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
            </View>
          )}

          {data?.raja_note && (
            <View style={styles.rajaNote}>
              <Ionicons name="flower" size={16} color="#6D28D9" />
              <Text style={styles.rajaNoteText}>{data.raja_note}</Text>
            </View>
          )}
        </ScrollView>
      )}

      <Modal visible={settingsOpen} animationType="slide" transparent onRequestClose={() => setSettingsOpen(false)}>
        <View style={styles.modalOverlay}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>Key timings & Nudges</Text>
            {['wake_up', 'bed_time', 'business_start', 'business_end'].map((k) => (
              <View key={k} style={{ marginBottom: 8 }}>
                <Text style={styles.fieldLabel}>{k.replace('_', ' ')} (HH:MM)</Text>
                <TextInput style={styles.input}
                  value={(kt as any)[k]}
                  onChangeText={v => setKt({ ...kt, [k]: v })} />
              </View>
            ))}
            <Text style={[styles.fieldLabel, { marginTop: 10 }]}>Nudge cadence</Text>
            {[
              { key: 'nudge_morning', label: 'Morning intent-setter' },
              { key: 'nudge_midday', label: 'Midday check-in' },
              { key: 'nudge_evening', label: 'Evening retrospective' },
              { key: 'nudge_hourly', label: 'Hourly nudges' },
              { key: 'nudge_event_driven', label: 'Event-driven (after each task)' },
            ].map((c) => (
              <TouchableOpacity key={c.key} style={styles.toggleRow}
                onPress={() => setPrefs({ ...prefs, [c.key]: !(prefs?.[c.key]) })}>
                <Ionicons name={prefs?.[c.key] ? 'checkbox' : 'square-outline'}
                  size={20} color={prefs?.[c.key] ? COLORS.primary : COLORS.textMuted} />
                <Text style={styles.toggleText}>{c.label}</Text>
              </TouchableOpacity>
            ))}
            <View style={styles.rowEnd}>
              <TouchableOpacity onPress={() => setSettingsOpen(false)} style={styles.cancelBtn}>
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={saveSettings} style={styles.saveBtn}>
                <Text style={styles.saveBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16 },
  h1: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  sub: { fontSize: 11, color: 'rgba(255,255,255,0.85)' },
  tabRow: { flexDirection: 'row', padding: 10, gap: 6, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8, borderRadius: 10, backgroundColor: COLORS.divider },
  tabActive: { backgroundColor: '#6D28D9' },
  tabText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },
  introCard: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 12, backgroundColor: '#F5F3FF', borderWidth: 1, borderColor: '#DDD6FE', marginBottom: 12 },
  introText: { flex: 1, fontSize: 13, color: '#5B21B6', fontWeight: '500', lineHeight: 19 },
  ktStrip: { flexDirection: 'row', gap: 6, marginBottom: 12 },
  ktItem: { flex: 1, padding: 8, backgroundColor: COLORS.white, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  ktLabel: { fontSize: 9, color: COLORS.textMuted, fontWeight: '700', textTransform: 'uppercase' },
  ktValue: { fontSize: 13, color: COLORS.textPrimary, fontWeight: '700', marginTop: 2 },
  sectionTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginTop: 10, marginBottom: 6 },
  noteRow: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 8, marginBottom: 6 },
  noteText: { flex: 1, fontSize: 12, color: COLORS.textPrimary, lineHeight: 17 },
  pickCard: { flexDirection: 'row', padding: 12, backgroundColor: COLORS.white, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 8, gap: 10 },
  kindChip: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  kindChipText: { fontSize: 10, fontWeight: '700' },
  pickScore: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600' },
  pickTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginTop: 4 },
  pickReason: { fontSize: 11, color: COLORS.textMuted, marginTop: 2, lineHeight: 15 },
  pickEstimate: { fontSize: 10, color: COLORS.textMuted, marginTop: 4 },
  pickActions: { flexDirection: 'column', gap: 4, justifyContent: 'center' },
  actBtn: { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  actAccept: { backgroundColor: '#10B981' },
  actDefer: { backgroundColor: '#F59E0B' },
  actSkip: { backgroundColor: '#EF4444' },
  rajaNote: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, borderRadius: 10, backgroundColor: '#FDF2F8', marginTop: 10 },
  rajaNoteText: { flex: 1, fontSize: 12, color: '#9D174D', fontStyle: 'italic', lineHeight: 17 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.background, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, maxHeight: '85%' },
  sheetTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  fieldLabel: { fontSize: 12, color: COLORS.textMuted, marginBottom: 4, fontWeight: '600', textTransform: 'capitalize' },
  input: { backgroundColor: COLORS.white, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8 },
  toggleText: { fontSize: 13, color: COLORS.textPrimary },
  rowEnd: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 14 },
  cancelBtn: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border },
  cancelBtnText: { color: COLORS.textPrimary, fontWeight: '600' },
  saveBtn: { backgroundColor: '#6D28D9', paddingHorizontal: 18, paddingVertical: 10, borderRadius: 8 },
  saveBtnText: { color: '#FFF', fontWeight: '700' },
});
