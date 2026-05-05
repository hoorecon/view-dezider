/**
 * Daily Time Log — main screen.
 *
 * Shows a 24-hour timeline for a date (default = today). Auto-rollup blocks
 * appear pre-filled (tagged auto). User adds manual blocks via a sheet.
 * Week strip + streak chip + link to Weekly Review.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Platform, KeyboardAvoidingView, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

const CATEGORIES = [
  { key: 'lifestyle', label: 'Lifestyle', color: '#10B981', icon: 'leaf' },
  { key: 'ctt', label: 'CTT', color: '#2563EB', icon: 'checkbox' },
  { key: 'meditation', label: 'Meditate', color: '#8B5CF6', icon: 'sparkles' },
  { key: 'journal', label: 'Journal', color: '#EC4899', icon: 'book' },
  { key: 'sleep', label: 'Sleep', color: '#475569', icon: 'moon' },
  { key: 'break', label: 'Break', color: '#F59E0B', icon: 'cafe' },
  { key: 'learning', label: 'Learn', color: '#06B6D4', icon: 'school' },
  { key: 'other', label: 'Other', color: '#6B7280', icon: 'ellipsis-horizontal' },
];

function isoToday(offset = 0) {
  const d = new Date(); d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

function hhmm(v?: string) {
  if (!v) return '';
  return v.length >= 5 ? v.slice(0, 5) : v;
}

export default function DailyTimeLogScreen() {
  const router = useRouter();
  const [date, setDate] = useState(isoToday());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [log, setLog] = useState<any>(null);
  const [streak, setStreak] = useState<any>({ current: 0, longest: 0 });
  const [editing, setEditing] = useState<any>(null);
  const [newBlock, setNewBlock] = useState({
    start: '09:00', end: '10:00', category: 'ctt', label: '', note: '',
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r1, r2] = await Promise.all([
        api.get(`/daily-time-log/${date}`),
        api.get(`/daily-time-log/streaks`),
      ]);
      setLog(r1.data);
      setStreak(r2.data || { current: 0, longest: 0 });
    } catch {
      showAlert('Error', 'Failed to load day log');
    } finally { setLoading(false); }
  }, [date]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const saveBlock = async () => {
    if (!newBlock.start || !newBlock.end) {
      showAlert('Required', 'Set start and end time');
      return;
    }
    setSaving(true);
    try {
      const existing = (log?.blocks || []).filter((b: any) => !b.auto_sourced);
      const blocks = [...existing, { ...newBlock }];
      if (editing) {
        const idx = blocks.findIndex((b: any) => b.block_id === editing.block_id);
        if (idx >= 0) blocks[idx] = { ...editing, ...newBlock };
      }
      await api.post('/daily-time-log', {
        log_date: date, blocks,
        run_auto_rollup: true,
      });
      setEditing(null);
      setNewBlock({ start: '09:00', end: '10:00', category: 'ctt', label: '', note: '' });
      await load();
    } catch {
      showAlert('Error', 'Could not save block');
    } finally { setSaving(false); }
  };

  const deleteBlock = async (b: any) => {
    if (b.auto_sourced) {
      showAlert('Auto block', 'Auto-imported blocks cannot be deleted. Edit the source record instead.');
      return;
    }
    setSaving(true);
    try {
      const blocks = (log?.blocks || []).filter((x: any) => x.block_id !== b.block_id && !x.auto_sourced);
      await api.post('/daily-time-log', { log_date: date, blocks, run_auto_rollup: true });
      await load();
    } finally { setSaving(false); }
  };

  const perCategory = useMemo(() => {
    return (log?.planned_vs_actual?.per_category_minutes) || {};
  }, [log]);

  const totalMin = log?.total_logged_minutes || 0;
  const totalHr = Math.floor(totalMin / 60);
  const totalRemMin = totalMin % 60;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={28} color={COLORS.textPrimary} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={styles.h1}>Daily Time Log</Text>
            <Text style={styles.sub}>Track actual time · streak {streak.current}🔥 (best {streak.longest})</Text>
          </View>
          <TouchableOpacity onPress={() => router.push('/tools/weekly-review' as any)}>
            <Ionicons name="calendar" size={24} color={COLORS.primary} />
          </TouchableOpacity>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.dayStrip}>
          {[-6, -5, -4, -3, -2, -1, 0].map(off => {
            const d = isoToday(off);
            const sel = d === date;
            const dt = new Date(d);
            return (
              <TouchableOpacity
                key={d}
                onPress={() => setDate(d)}
                style={[styles.dayChip, sel && styles.dayChipActive]}
              >
                <Text style={[styles.dayChipDay, sel && { color: '#FFF' }]}>
                  {dt.toLocaleString('en', { weekday: 'short' })}
                </Text>
                <Text style={[styles.dayChipDate, sel && { color: '#FFF' }]}>
                  {dt.getDate()}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        {loading ? (
          <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
        ) : (
          <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
            <View style={styles.summaryCard}>
              <View style={styles.sumTile}>
                <Text style={styles.sumLabel}>Total logged</Text>
                <Text style={styles.sumValue}>{totalHr}h {totalRemMin}m</Text>
              </View>
              {CATEGORIES.slice(0, 4).map(c => (
                <View key={c.key} style={styles.sumTile}>
                  <View style={[styles.sumDot, { backgroundColor: c.color }]} />
                  <Text style={styles.sumLabel}>{c.label}</Text>
                  <Text style={[styles.sumValue, { fontSize: 14 }]}>
                    {Math.round((perCategory[c.key] || 0) / 60 * 10) / 10}h
                  </Text>
                </View>
              ))}
            </View>

            <Text style={styles.sectionTitle}>Timeline blocks</Text>
            {(log?.blocks || []).length === 0 ? (
              <Text style={styles.emptyText}>No blocks yet. Tap “Add block” or let auto-rollup pick up CTT / Lifestyle / Meditation.</Text>
            ) : (
              (log.blocks || []).map((b: any) => {
                const cat = CATEGORIES.find(c => c.key === b.category) || CATEGORIES[7];
                return (
                  <View key={b.block_id} style={[styles.block, { borderLeftColor: cat.color }]}>
                    <View style={{ flex: 1 }}>
                      <View style={styles.blockHeadRow}>
                        <Ionicons name={cat.icon as any} size={14} color={cat.color} />
                        <Text style={[styles.blockLabel, { color: cat.color }]}>{cat.label.toUpperCase()}</Text>
                        {b.auto_sourced && (
                          <View style={styles.autoTag}><Text style={styles.autoTagText}>AUTO</Text></View>
                        )}
                      </View>
                      <Text style={styles.blockTitle}>
                        {hhmm(b.start)}{b.start && b.end ? ` – ${hhmm(b.end)}` : ''} · {b.minutes} min
                      </Text>
                      <Text style={styles.blockText}>{b.label || b.note || '—'}</Text>
                    </View>
                    {!b.auto_sourced && (
                      <View style={styles.blockActions}>
                        <TouchableOpacity onPress={() => {
                          setEditing(b);
                          setNewBlock({
                            start: b.start || '09:00', end: b.end || '10:00',
                            category: b.category || 'ctt',
                            label: b.label || '', note: b.note || '',
                          });
                        }}>
                          <Ionicons name="create" size={18} color={COLORS.primary} />
                        </TouchableOpacity>
                        <TouchableOpacity onPress={() => deleteBlock(b)}>
                          <Ionicons name="trash" size={18} color={COLORS.error} />
                        </TouchableOpacity>
                      </View>
                    )}
                  </View>
                );
              })
            )}

            <TouchableOpacity testID="dtl-add-block" style={styles.addBtn} onPress={() => setEditing({})}>
              <Ionicons name="add" size={20} color="#FFF" />
              <Text style={styles.addBtnText}>Add block</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.refreshBtn}
              onPress={async () => {
                try { await api.post(`/daily-time-log/${date}/refresh-rollup`, {}); await load(); }
                catch { showAlert('Error', 'Failed to refresh rollup'); }
              }}
            >
              <Ionicons name="refresh" size={16} color={COLORS.primary} />
              <Text style={styles.refreshBtnText}>Re-scan CTT / Lifestyle / Meditation</Text>
            </TouchableOpacity>
          </ScrollView>
        )}

        <Modal visible={editing !== null} animationType="slide" transparent onRequestClose={() => setEditing(null)}>
          <View style={styles.modalOverlay}>
            <View style={styles.sheet}>
              <Text style={styles.sheetTitle}>{editing?.block_id ? 'Edit block' : 'Add block'}</Text>
              <Text style={styles.fieldLabel}>Category</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
                {CATEGORIES.map(c => {
                  const sel = newBlock.category === c.key;
                  return (
                    <TouchableOpacity key={c.key} onPress={() => setNewBlock({ ...newBlock, category: c.key })}
                      style={[styles.catChip, sel && { backgroundColor: c.color, borderColor: c.color }]}>
                      <Ionicons name={c.icon as any} size={14} color={sel ? '#FFF' : c.color} />
                      <Text style={[styles.catChipText, sel && { color: '#FFF' }]}>{c.label}</Text>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>
              <View style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Start (HH:MM)</Text>
                  <TextInput testID="dtl-block-start" style={styles.input} value={newBlock.start}
                    onChangeText={v => setNewBlock({ ...newBlock, start: v })} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>End (HH:MM)</Text>
                  <TextInput testID="dtl-block-end" style={styles.input} value={newBlock.end}
                    onChangeText={v => setNewBlock({ ...newBlock, end: v })} />
                </View>
              </View>
              <Text style={styles.fieldLabel}>Label</Text>
              <TextInput testID="dtl-block-label" style={styles.input} value={newBlock.label} placeholder="e.g. Morning run"
                placeholderTextColor={COLORS.textMuted}
                onChangeText={v => setNewBlock({ ...newBlock, label: v })} />
              <Text style={styles.fieldLabel}>Note</Text>
              <TextInput style={[styles.input, { minHeight: 60 }]} value={newBlock.note} multiline
                placeholderTextColor={COLORS.textMuted} placeholder="Optional"
                onChangeText={v => setNewBlock({ ...newBlock, note: v })} />
              <View style={styles.rowEnd}>
                <TouchableOpacity onPress={() => setEditing(null)} style={styles.cancelBtn}>
                  <Text style={styles.cancelBtnText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity testID="dtl-block-save" onPress={saveBlock} disabled={saving}
                  style={[styles.saveBtn, saving && { opacity: 0.6 }]}>
                  {saving ? <ActivityIndicator size="small" color="#FFF" /> :
                    <Text style={styles.saveBtnText}>Save</Text>}
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 },
  h1: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  sub: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  dayStrip: { paddingHorizontal: 12, gap: 8, paddingVertical: 6 },
  dayChip: {
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12,
    backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border,
    alignItems: 'center', minWidth: 48, marginRight: 6,
  },
  dayChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  dayChipDay: { fontSize: 11, color: COLORS.textMuted, fontWeight: '600' },
  dayChipDate: { fontSize: 16, color: COLORS.textPrimary, fontWeight: '700' },
  summaryCard: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14,
    padding: 10, backgroundColor: COLORS.white, borderRadius: 12,
    borderWidth: 1, borderColor: COLORS.border,
  },
  sumTile: { minWidth: '23%', alignItems: 'center', padding: 6 },
  sumDot: { width: 10, height: 10, borderRadius: 5, marginBottom: 4 },
  sumLabel: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600' },
  sumValue: { fontSize: 16, color: COLORS.textPrimary, fontWeight: '700', marginTop: 2 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  emptyText: { color: COLORS.textMuted, fontSize: 12, marginBottom: 12 },
  block: {
    flexDirection: 'row', gap: 10, alignItems: 'center',
    backgroundColor: COLORS.white, borderRadius: 10, padding: 12, marginBottom: 8,
    borderWidth: 1, borderColor: COLORS.border, borderLeftWidth: 4,
  },
  blockHeadRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  blockLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.5 },
  blockTitle: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginTop: 2 },
  blockText: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  blockActions: { flexDirection: 'row', gap: 10 },
  autoTag: {
    backgroundColor: COLORS.divider, paddingHorizontal: 6, paddingVertical: 1,
    borderRadius: 3, marginLeft: 4,
  },
  autoTagText: { fontSize: 8, color: COLORS.textMuted, fontWeight: '700' },
  addBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: COLORS.primary, paddingVertical: 12, borderRadius: 10,
    marginTop: 8,
  },
  addBtnText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
  refreshBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    marginTop: 10, paddingVertical: 10,
  },
  refreshBtnText: { color: COLORS.primary, fontWeight: '600', fontSize: 12 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.background, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16 },
  sheetTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  fieldLabel: { fontSize: 12, color: COLORS.textMuted, marginTop: 10, marginBottom: 4, fontWeight: '600' },
  input: {
    backgroundColor: COLORS.white, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary,
  },
  row: { flexDirection: 'row', gap: 8 },
  rowEnd: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 14 },
  cancelBtn: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border },
  cancelBtnText: { color: COLORS.textPrimary, fontWeight: '600', fontSize: 13 },
  saveBtn: { backgroundColor: COLORS.primary, paddingHorizontal: 18, paddingVertical: 10, borderRadius: 8 },
  saveBtnText: { color: '#FFF', fontWeight: '700', fontSize: 13 },
  catChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14,
    borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white,
    marginRight: 4,
  },
  catChipText: { fontSize: 11, fontWeight: '600', color: COLORS.textPrimary },
});
