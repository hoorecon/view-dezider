import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert, Modal, TextInput,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const HOUR_HEIGHT = 60;
const SOURCE_COLORS: Record<string, string> = {
  ctt: '#3B82F6',
  lifestyle: '#10B981',
  unplanned: '#F59E0B',
};
const PRIORITY_COLORS: Record<string, string> = {
  high: '#EF4444',
  medium: '#F59E0B',
  low: '#94A3B8',
};

function parseTimeToMins(t: string | null): number | null {
  if (!t) return null;
  const parts = t.split(':');
  if (parts.length < 2) return null;
  return parseInt(parts[0]) * 60 + parseInt(parts[1]);
}

function minsToTime(m: number): string {
  const h = Math.floor(m / 60);
  const min = m % 60;
  return `${h.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}`;
}

function formatTime12(t: string): string {
  const mins = parseTimeToMins(t);
  if (mins === null) return t;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${m.toString().padStart(2, '0')} ${ampm}`;
}

export default function TimeDeziderScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [blocks, setBlocks] = useState<any[]>([]);
  const [stats, setStats] = useState<any>({});
  const [dayStart, setDayStart] = useState('06:00');
  const [dayEnd, setDayEnd] = useState('23:00');

  // Add unplanned task modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDuration, setNewDuration] = useState('60');
  const [newPriority, setNewPriority] = useState('high');
  const [newStartTime, setNewStartTime] = useState('');

  // Reschedule
  const [rescheduling, setRescheduling] = useState(false);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Preferences
  const [showPrefs, setShowPrefs] = useState(false);
  const [prefDayStart, setPrefDayStart] = useState('06:00');
  const [prefDayEnd, setPrefDayEnd] = useState('23:00');

  const fetchSchedule = async () => {
    try {
      const res = await api.get(`/time-dezider/daily?date=${date}`);
      setBlocks(res.data.blocks || []);
      setStats(res.data.stats || {});
      setDayStart(res.data.day_start || '06:00');
      setDayEnd(res.data.day_end || '23:00');
    } catch (err) {
      console.error('Schedule fetch error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchSchedule(); }, [date]));

  const changeDate = (delta: number) => {
    const d = new Date(date);
    d.setDate(d.getDate() + delta);
    setDate(d.toISOString().split('T')[0]);
    setLoading(true);
    setSuggestions([]);
  };

  const addUnplannedTask = async () => {
    if (!newTitle.trim()) {
      Alert.alert('Required', 'Please enter a task title');
      return;
    }
    try {
      await api.post('/time-dezider/unplanned-task', {
        date,
        title: newTitle,
        duration_minutes: parseInt(newDuration) || 60,
        priority: newPriority,
        start_time: newStartTime || undefined,
      });
      setShowAddModal(false);
      setNewTitle('');
      setNewDuration('60');
      setNewStartTime('');
      fetchSchedule();
    } catch {
      Alert.alert('Error', 'Failed to add task');
    }
  };

  const requestReschedule = async () => {
    const unplanned = blocks.filter(b => b.source_type === 'unplanned');
    if (unplanned.length === 0) {
      Alert.alert('No Unplanned Tasks', 'Add an unplanned task first to get rescheduling suggestions.');
      return;
    }
    setRescheduling(true);
    try {
      const latest = unplanned[unplanned.length - 1];
      const res = await api.post('/time-dezider/reschedule', {
        date,
        unplanned_title: latest.title,
        unplanned_duration: latest.duration_minutes,
        unplanned_priority: latest.priority,
      });
      setSuggestions(res.data.suggestions || []);
      setShowSuggestions(true);
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || 'Rescheduling failed');
    } finally {
      setRescheduling(false);
    }
  };

  const approveSuggestions = async (selected: any[]) => {
    try {
      await api.post('/time-dezider/approve', { suggestions: selected });
      setShowSuggestions(false);
      setSuggestions([]);
      fetchSchedule();
      Alert.alert('Applied', `${selected.length} changes applied to your schedule.`);
    } catch {
      Alert.alert('Error', 'Failed to apply changes');
    }
  };

  const removeUnplanned = async (blockId: string) => {
    try {
      await api.delete(`/time-dezider/unplanned-task/${blockId.replace('unplanned_', '')}`);
      fetchSchedule();
    } catch {
      Alert.alert('Error', 'Failed to remove task');
    }
  };

  const savePreferences = async () => {
    try {
      await api.put('/time-dezider/preferences', {
        day_start: prefDayStart,
        day_end: prefDayEnd,
      });
      setShowPrefs(false);
      fetchSchedule();
    } catch {
      Alert.alert('Error', 'Failed to save preferences');
    }
  };

  // Render timeline blocks
  const dayStartMins = parseTimeToMins(dayStart) || 360;
  const dayEndMins = parseTimeToMins(dayEnd) || 1380;
  const totalHours = Math.ceil((dayEndMins - dayStartMins) / 60);
  const scheduledBlocks = blocks.filter(b => b.start_time);
  const unscheduledBlocks = blocks.filter(b => !b.start_time);

  if (loading) {
    return (
      <SafeAreaView style={s.container}>
        <View style={s.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container}>
      {/* Header */}
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>Time Dezider</Text>
          <Text style={s.subtitle}>Daily Schedule Manager</Text>
        </View>
        <TouchableOpacity onPress={() => { setPrefDayStart(dayStart); setPrefDayEnd(dayEnd); setShowPrefs(true); }} style={s.settingsBtn}>
          <Ionicons name="settings-outline" size={20} color={COLORS.textMuted} />
        </TouchableOpacity>
      </View>

      {/* Date Nav */}
      <View style={s.dateNav}>
        <TouchableOpacity onPress={() => changeDate(-1)} style={s.dateNavBtn}>
          <Ionicons name="chevron-back" size={20} color={COLORS.primary} />
        </TouchableOpacity>
        <TouchableOpacity onPress={() => { setDate(new Date().toISOString().split('T')[0]); setLoading(true); }}>
          <Text style={s.dateText}>
            {new Date(date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
          </Text>
          {date === new Date().toISOString().split('T')[0] && (
            <View style={s.todayBadge}><Text style={s.todayBadgeText}>Today</Text></View>
          )}
        </TouchableOpacity>
        <TouchableOpacity onPress={() => changeDate(1)} style={s.dateNavBtn}>
          <Ionicons name="chevron-forward" size={20} color={COLORS.primary} />
        </TouchableOpacity>
      </View>

      {/* Stats Bar */}
      <View style={s.statsBar}>
        <View style={s.statItem}>
          <Text style={s.statNum}>{Math.round((stats.scheduled_minutes || 0) / 60 * 10) / 10}h</Text>
          <Text style={s.statLabel}>Scheduled</Text>
        </View>
        <View style={s.statItem}>
          <Text style={[s.statNum, { color: '#16A34A' }]}>{Math.round((stats.free_minutes || 0) / 60 * 10) / 10}h</Text>
          <Text style={s.statLabel}>Free</Text>
        </View>
        <View style={s.statItem}>
          <Text style={s.statNum}>{stats.total_blocks || 0}</Text>
          <Text style={s.statLabel}>Tasks</Text>
        </View>
        <View style={[s.statItem, { borderRightWidth: 0 }]}>
          <Text style={[s.statNum, { color: (stats.utilization_percent || 0) > 80 ? '#EF4444' : COLORS.primary }]}>
            {stats.utilization_percent || 0}%
          </Text>
          <Text style={s.statLabel}>Utilized</Text>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={s.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchSchedule(); }} colors={[COLORS.primary]} />}
      >
        {/* Timeline */}
        <View style={s.timelineContainer}>
          {Array.from({ length: totalHours + 1 }, (_, i) => {
            const hour = Math.floor(dayStartMins / 60) + i;
            return (
              <View key={hour} style={[s.hourRow, { top: i * HOUR_HEIGHT }]}>
                <Text style={s.hourLabel}>{hour > 12 ? hour - 12 : hour === 0 ? 12 : hour}{hour >= 12 ? 'p' : 'a'}</Text>
                <View style={s.hourLine} />
              </View>
            );
          })}

          {/* Blocks on timeline */}
          {scheduledBlocks.map((block) => {
            const startMins = parseTimeToMins(block.start_time) || dayStartMins;
            const endMins = parseTimeToMins(block.end_time) || (startMins + block.duration_minutes);
            const top = ((startMins - dayStartMins) / 60) * HOUR_HEIGHT;
            const height = Math.max(28, ((endMins - startMins) / 60) * HOUR_HEIGHT);
            const color = SOURCE_COLORS[block.source_type] || '#94A3B8';

            return (
              <TouchableOpacity
                key={block.id}
                style={[s.timeBlock, {
                  top: top + 16,
                  height,
                  borderLeftColor: color,
                  backgroundColor: block.status === 'completed' ? '#F0FDF4' : '#FFF',
                }]}
                onPress={() => {
                  if (block.source_type === 'unplanned') {
                    Alert.alert(block.title, `Duration: ${block.duration_minutes}m\nPriority: ${block.priority}`, [
                      { text: 'Remove', style: 'destructive', onPress: () => removeUnplanned(block.source_id) },
                      { text: 'OK' },
                    ]);
                  }
                }}
              >
                <View style={s.blockHeader}>
                  <View style={[s.blockSourceDot, { backgroundColor: color }]} />
                  <Text style={s.blockTitle} numberOfLines={1}>{block.title}</Text>
                  <View style={[s.priorityDot, { backgroundColor: PRIORITY_COLORS[block.priority] || '#94A3B8' }]} />
                </View>
                {height > 36 && (
                  <Text style={s.blockTime}>
                    {formatTime12(block.start_time)} – {formatTime12(block.end_time)} · {block.duration_minutes}m
                  </Text>
                )}
                {block.status === 'completed' && (
                  <Ionicons name="checkmark-circle" size={14} color="#16A34A" style={{ position: 'absolute', right: 6, top: 6 }} />
                )}
              </TouchableOpacity>
            );
          })}

          {/* Empty timeline height */}
          <View style={{ height: (totalHours + 1) * HOUR_HEIGHT + 20 }} />
        </View>

        {/* Unscheduled tasks */}
        {unscheduledBlocks.length > 0 && (
          <View style={s.unscheduledSection}>
            <Text style={s.sectionTitle}>Unscheduled ({unscheduledBlocks.length})</Text>
            {unscheduledBlocks.map(block => (
              <View key={block.id} style={s.unscheduledCard}>
                <View style={[s.blockSourceDot, { backgroundColor: SOURCE_COLORS[block.source_type] || '#94A3B8' }]} />
                <View style={{ flex: 1 }}>
                  <Text style={s.unscheduledTitle}>{block.title}</Text>
                  <Text style={s.unscheduledMeta}>{block.duration_minutes}m · {block.priority} · {block.life_area || 'General'}</Text>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* AI Reschedule Button */}
        <TouchableOpacity style={s.rescheduleBtn} onPress={requestReschedule} disabled={rescheduling}>
          {rescheduling ? (
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <>
              <Ionicons name="flash" size={18} color="#FFF" />
              <Text style={s.rescheduleBtnText}>AI Reschedule</Text>
            </>
          )}
        </TouchableOpacity>

        {/* Legend */}
        <View style={s.legendRow}>
          {Object.entries(SOURCE_COLORS).map(([key, color]) => (
            <View key={key} style={s.legendItem}>
              <View style={[s.legendDot, { backgroundColor: color }]} />
              <Text style={s.legendLabel}>{key === 'ctt' ? 'CTT Task' : key === 'lifestyle' ? 'Routine' : 'Unplanned'}</Text>
            </View>
          ))}
        </View>
      </ScrollView>

      {/* FAB - Add Unplanned Task */}
      <TouchableOpacity style={s.fab} onPress={() => setShowAddModal(true)}>
        <Ionicons name="add" size={26} color="#FFF" />
      </TouchableOpacity>

      {/* Add Unplanned Task Modal */}
      <Modal visible={showAddModal} transparent animationType="slide">
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>Add Unplanned Task</Text>
              <TouchableOpacity onPress={() => setShowAddModal(false)}>
                <Ionicons name="close" size={22} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={s.modalBody}>
              <Text style={s.modalLabel}>Task Title</Text>
              <TextInput style={s.input} value={newTitle} onChangeText={setNewTitle} placeholder="e.g., Urgent client call" placeholderTextColor={COLORS.textMuted} />

              <Text style={s.modalLabel}>Duration (minutes)</Text>
              <TextInput style={s.input} value={newDuration} onChangeText={setNewDuration} keyboardType="numeric" placeholder="60" placeholderTextColor={COLORS.textMuted} />

              <Text style={s.modalLabel}>Preferred Start Time (optional)</Text>
              <TextInput style={s.input} value={newStartTime} onChangeText={setNewStartTime} placeholder="HH:MM (e.g. 14:00)" placeholderTextColor={COLORS.textMuted} />

              <Text style={s.modalLabel}>Priority</Text>
              <View style={s.priorityRow}>
                {['high', 'medium', 'low'].map(p => (
                  <TouchableOpacity
                    key={p}
                    style={[s.priorityBtn, newPriority === p && { backgroundColor: PRIORITY_COLORS[p], borderColor: PRIORITY_COLORS[p] }]}
                    onPress={() => setNewPriority(p)}
                  >
                    <Text style={[s.priorityBtnText, newPriority === p && { color: '#FFF' }]}>{p}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <TouchableOpacity style={s.submitBtn} onPress={addUnplannedTask}>
                <Ionicons name="add-circle" size={18} color="#FFF" />
                <Text style={s.submitBtnText}>Add & Find Slot</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* AI Suggestions Modal */}
      <Modal visible={showSuggestions} transparent animationType="slide">
        <View style={s.modalOverlay}>
          <View style={[s.modalContent, { maxHeight: '85%' }]}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>AI Rescheduling Suggestions</Text>
              <TouchableOpacity onPress={() => setShowSuggestions(false)}>
                <Ionicons name="close" size={22} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={s.modalBody}>
              {suggestions.length === 0 ? (
                <Text style={s.emptyText}>No rescheduling needed - your schedule looks good!</Text>
              ) : (
                <>
                  {suggestions.map((sug: any, idx: number) => (
                    <View key={idx} style={s.suggestionCard}>
                      <View style={s.sugHeader}>
                        <View style={[s.sugActionBadge, {
                          backgroundColor: sug.action === 'delegate' ? '#DBEAFE' : sug.action === 'move' ? '#FEF3C7' :
                            sug.action === 'compress' ? '#D1FAE5' : sug.action === 'eliminate' ? '#FEE2E2' : '#F3E8FF',
                        }]}>
                          <Text style={[s.sugActionText, {
                            color: sug.action === 'delegate' ? '#3B82F6' : sug.action === 'move' ? '#D97706' :
                              sug.action === 'compress' ? '#16A34A' : sug.action === 'eliminate' ? '#DC2626' : '#7C3AED',
                          }]}>{(sug.action || '').toUpperCase()}</Text>
                        </View>
                        {sug.tepfi_lever && (
                          <View style={s.tepfiBadge}>
                            <Text style={s.tepfiText}>{sug.tepfi_lever}/{sug.tepfi_layer}</Text>
                          </View>
                        )}
                      </View>
                      <Text style={s.sugTitle}>{sug.target_title || sug.description}</Text>
                      <Text style={s.sugDesc}>{sug.description || sug.reasoning}</Text>
                      {sug.new_start_time && (
                        <Text style={s.sugTime}>→ {formatTime12(sug.new_start_time)} – {formatTime12(sug.new_end_time || '')}</Text>
                      )}
                      {sug.delegate_to && (
                        <View style={s.delegateRow}>
                          <Ionicons name="person" size={12} color="#3B82F6" />
                          <Text style={s.delegateText}>Delegate to: {sug.delegate_to}</Text>
                        </View>
                      )}
                      {sug.time_saved_minutes > 0 && (
                        <Text style={s.timeSaved}>⏱ Saves {sug.time_saved_minutes}m</Text>
                      )}
                    </View>
                  ))}
                  <TouchableOpacity style={s.approveBtn} onPress={() => approveSuggestions(suggestions)}>
                    <Ionicons name="checkmark-circle" size={18} color="#FFF" />
                    <Text style={s.approveBtnText}>Approve All ({suggestions.length})</Text>
                  </TouchableOpacity>
                </>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Preferences Modal */}
      <Modal visible={showPrefs} transparent animationType="slide">
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={s.modalOverlay}>
          <View style={s.modalContent}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>Day Settings</Text>
              <TouchableOpacity onPress={() => setShowPrefs(false)}>
                <Ionicons name="close" size={22} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>
            <View style={s.modalBody}>
              <Text style={s.modalLabel}>Day Start (HH:MM)</Text>
              <TextInput style={s.input} value={prefDayStart} onChangeText={setPrefDayStart} placeholder="06:00" placeholderTextColor={COLORS.textMuted} />
              <Text style={s.modalLabel}>Day End (HH:MM)</Text>
              <TextInput style={s.input} value={prefDayEnd} onChangeText={setPrefDayEnd} placeholder="23:00" placeholderTextColor={COLORS.textMuted} />
              <TouchableOpacity style={s.submitBtn} onPress={savePreferences}>
                <Text style={s.submitBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted },
  settingsBtn: { padding: 6 },

  // Date Nav
  dateNav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 8, gap: 16 },
  dateNavBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center' },
  dateText: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center' },
  todayBadge: { backgroundColor: COLORS.primary, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 2, alignSelf: 'center', marginTop: 2 },
  todayBadgeText: { fontSize: 10, fontWeight: '700', color: '#FFF' },

  // Stats
  statsBar: { flexDirection: 'row', marginHorizontal: 16, backgroundColor: '#FFF', borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 8 },
  statItem: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRightWidth: 1, borderRightColor: COLORS.border },
  statNum: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  statLabel: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },

  scrollContent: { paddingHorizontal: 16, paddingBottom: 100 },

  // Timeline
  timelineContainer: { position: 'relative', marginTop: 8 },
  hourRow: { position: 'absolute', left: 0, right: 0, flexDirection: 'row', alignItems: 'center' },
  hourLabel: { width: 28, fontSize: 10, color: COLORS.textMuted, textAlign: 'right' },
  hourLine: { flex: 1, height: 1, backgroundColor: '#F1F5F9', marginLeft: 6 },

  // Time Block
  timeBlock: { position: 'absolute', left: 40, right: 4, borderLeftWidth: 3, borderRadius: 8, backgroundColor: '#FFF', paddingHorizontal: 8, paddingVertical: 5, elevation: 2, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.08, shadowRadius: 3 },
  blockHeader: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  blockSourceDot: { width: 8, height: 8, borderRadius: 4 },
  blockTitle: { flex: 1, fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  priorityDot: { width: 6, height: 6, borderRadius: 3 },
  blockTime: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },

  // Unscheduled
  unscheduledSection: { marginTop: 16, gap: 6 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  unscheduledCard: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FFF', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: COLORS.border },
  unscheduledTitle: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  unscheduledMeta: { fontSize: 11, color: COLORS.textMuted },

  // Reschedule
  rescheduleBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#7C3AED', borderRadius: 12, paddingVertical: 14, marginTop: 16 },
  rescheduleBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },

  // Legend
  legendRow: { flexDirection: 'row', justifyContent: 'center', gap: 16, marginTop: 12 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendLabel: { fontSize: 10, color: COLORS.textMuted },

  // FAB
  fab: { position: 'absolute', right: 20, bottom: 24, width: 56, height: 56, borderRadius: 28, backgroundColor: '#F59E0B', alignItems: 'center', justifyContent: 'center', elevation: 6, shadowColor: '#000', shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.15, shadowRadius: 5 },

  // Modals
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '80%' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  modalTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  modalBody: { padding: 16 },
  modalLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, padding: 12, fontSize: 14, color: COLORS.textPrimary },
  priorityRow: { flexDirection: 'row', gap: 8 },
  priorityBtn: { flex: 1, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  priorityBtnText: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary, textTransform: 'capitalize' },
  submitBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 14, marginTop: 16, marginBottom: 12 },
  submitBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },

  // Suggestions
  emptyText: { fontSize: 14, color: COLORS.textMuted, textAlign: 'center', paddingVertical: 20 },
  suggestionCard: { backgroundColor: '#F8FAFC', borderRadius: 12, padding: 14, marginBottom: 10 },
  sugHeader: { flexDirection: 'row', gap: 6, marginBottom: 6 },
  sugActionBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  sugActionText: { fontSize: 10, fontWeight: '700' },
  tepfiBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: '#F3E8FF' },
  tepfiText: { fontSize: 10, fontWeight: '600', color: '#7C3AED' },
  sugTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  sugDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2, lineHeight: 17 },
  sugTime: { fontSize: 12, fontWeight: '600', color: COLORS.primary, marginTop: 4 },
  delegateRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  delegateText: { fontSize: 12, fontWeight: '600', color: '#3B82F6' },
  timeSaved: { fontSize: 11, fontWeight: '600', color: '#16A34A', marginTop: 4 },
  approveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#16A34A', borderRadius: 12, paddingVertical: 14, marginTop: 8, marginBottom: 12 },
  approveBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
});
