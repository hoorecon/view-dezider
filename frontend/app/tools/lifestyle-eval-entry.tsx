import React, { useState, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import { useLifeAreas } from '../../src/utils/useLifeAreas';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Platform, KeyboardAvoidingView, Modal,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

interface Activity {
  activity_id: string;
  from_time: string;
  to_time: string;
  activity: string;
  area_of_life: string;
  category: string;
  duration_minutes: number;
  remarks: string;
}

// LIFE_AREAS array moved into the component (catalog-driven).
const CATEGORIES = [
  { id: 'problem', name: 'Problem', color: '#EF4444', icon: 'alert-circle' },
  { id: 'need', name: 'Need', color: '#F59E0B', icon: 'ellipse' },
  { id: 'aspiration', name: 'Aspiration', color: '#10B981', icon: 'star' },
];

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
const MIN_OPTIONS = ['00', '15', '30', '45'];

function calcDuration(from: string, to: string): number {
  if (!from || !to) return 0;
  const [fh, fm] = from.split(':').map(Number);
  const [th, tm] = to.split(':').map(Number);
  let fMin = fh * 60 + fm;
  let tMin = th * 60 + tm;
  if (tMin < fMin) tMin += 24 * 60;
  return tMin - fMin;
}

function formatMins(m: number) {
  const h = Math.floor(m / 60);
  const min = m % 60;
  return h > 0 ? `${h}h ${min}m` : `${min}m`;
}

export default function LifestyleEvalEntryScreen() {
  // LIFE_AREAS flows from the Admin Central Catalog via the useLifeAreas()
  // hook (single source of truth across the app). Adapter preserves both
  // old (`c`, `name`) and new (`color`, `label`, `slug`, `node_id`) field
  // names so the rest of this file continues to compile without
  // ripple-effect edits.
  const { items: _laItems } = useLifeAreas();
  const LIFE_AREAS = _laItems.map(a => ({
    id: a.id,
    node_id: a.node_id,
    slug: a.slug,
    name: a.name,
    label: a.name,
    short: a.name,
    icon: a.icon,
    color: a.color,
    c: a.color,
  }));

  const router = useRouter();
  const params = useLocalSearchParams();
  const dateParam = (params.date as string) || new Date().toISOString().split('T')[0];

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [remarks, setRemarks] = useState('');
  const [dayType, setDayType] = useState('');
  const [comparison, setComparison] = useState<any>(null);
  const [showComparison, setShowComparison] = useState(params.tab === 'comparison');

  // Time picker state
  const [timeModal, setTimeModal] = useState(false);
  const [timeTarget, setTimeTarget] = useState<{ idx: number; field: 'from_time' | 'to_time' } | null>(null);
  const [pickHour, setPickHour] = useState('06');
  const [pickMin, setPickMin] = useState('00');

  useEffect(() => { loadLog(); }, [dateParam]);

  const loadLog = async () => {
    setLoading(true);
    try {
      const [logRes, compRes] = await Promise.all([
        api.get(`/lifestyle-eval/logs/${dateParam}`),
        api.get(`/lifestyle-eval/planned-vs-actual?date=${dateParam}`),
      ]);
      const log = logRes.data;
      if (log.exists && log.activities?.length) {
        setActivities(log.activities);
        setRemarks(log.remarks || '');
        setDayType(log.day_type || '');
      } else {
        // Start with one empty row
        setActivities([emptyActivity()]);
        detectDayType();
      }
      setComparison(compRes.data);
    } catch (e) {
      console.error('Load error:', e);
      setActivities([emptyActivity()]);
      detectDayType();
    } finally { setLoading(false); }
  };

  const detectDayType = () => {
    const d = new Date(dateParam);
    const wd = d.getDay();
    setDayType(wd === 6 ? 'saturday' : wd === 0 ? 'sunday' : 'weekday');
  };

  const emptyActivity = (): Activity => ({
    activity_id: `ACT-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    from_time: '', to_time: '',
    activity: '', area_of_life: '', category: 'need',
    duration_minutes: 0, remarks: '',
  });

  const addActivity = () => {
    const last = activities[activities.length - 1];
    const newAct = emptyActivity();
    if (last?.to_time) newAct.from_time = last.to_time;
    setActivities([...activities, newAct]);
  };

  const removeActivity = (idx: number) => {
    if (activities.length <= 1) return;
    setActivities(activities.filter((_, i) => i !== idx));
  };

  const updateActivity = (idx: number, field: keyof Activity, value: string) => {
    setActivities(prev => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], [field]: value };
      if (field === 'from_time' || field === 'to_time') {
        copy[idx].duration_minutes = calcDuration(copy[idx].from_time, copy[idx].to_time);
      }
      return copy;
    });
  };

  const openTimePicker = (idx: number, field: 'from_time' | 'to_time') => {
    const current = activities[idx][field];
    if (current) {
      const [h, m] = current.split(':');
      setPickHour(h || '06');
      setPickMin(m || '00');
    } else {
      setPickHour('06');
      setPickMin('00');
    }
    setTimeTarget({ idx, field });
    setTimeModal(true);
  };

  const confirmTime = () => {
    if (timeTarget) {
      updateActivity(timeTarget.idx, timeTarget.field, `${pickHour}:${pickMin}`);
    }
    setTimeModal(false);
  };

  const handleSave = async () => {
    const valid = activities.filter(a => a.activity.trim() || a.from_time);
    if (valid.length === 0) { showAlert('Empty', 'Add at least one activity'); return; }
    setSaving(true);
    try {
      await api.post('/lifestyle-eval/logs', {
        date: dateParam,
        day_type: dayType,
        activities: valid,
        remarks,
      });
      showAlert('Saved', 'Activities logged!', [{ text: 'OK', onPress: () => safeBack(router) }]);
    } catch (e) {
      showAlert('Error', 'Failed to save');
    } finally { setSaving(false); }
  };

  const totalMinutes = activities.reduce((s, a) => s + a.duration_minutes, 0);

  if (loading) {
    return (
      <SafeAreaView style={st.container}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#7C3AED" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <LinearGradient colors={['#7C3AED', '#A855F7']} style={st.header}>
          <TouchableOpacity onPress={() => safeBack(router)} style={st.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={st.headerTitle}>{dateParam}</Text>
            <Text style={st.headerSub}>
              {dayType.charAt(0).toUpperCase() + dayType.slice(1)} · {activities.length} activities · {formatMins(totalMinutes)}
            </Text>
          </View>
        </LinearGradient>

        {/* Tab: Activities vs Comparison */}
        <View style={st.tabRow}>
          <TouchableOpacity style={[st.tab, !showComparison && st.tabActive]} onPress={() => setShowComparison(false)}>
            <Ionicons name="list" size={14} color={!showComparison ? '#FFF' : COLORS.textMuted} />
            <Text style={[st.tabText, !showComparison && { color: '#FFF' }]}>Activities</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[st.tab, showComparison && st.tabActive]} onPress={() => setShowComparison(true)}>
            <Ionicons name="git-compare" size={14} color={showComparison ? '#FFF' : COLORS.textMuted} />
            <Text style={[st.tabText, showComparison && { color: '#FFF' }]}>Planned vs Actual</Text>
          </TouchableOpacity>
        </View>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 100 }} showsVerticalScrollIndicator={false}>
          {showComparison ? renderComparison() : renderActivities()}
        </ScrollView>

        {!showComparison && (
          <View style={st.bottom}>
            <TouchableOpacity style={st.addRow} onPress={addActivity}>
              <Ionicons name="add-circle" size={18} color="#7C3AED" />
              <Text style={st.addText}>Add Activity</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[st.saveBtn, saving && { opacity: 0.7 }]} onPress={handleSave} disabled={saving}>
              {saving ? <ActivityIndicator size="small" color="#FFF" /> : (
                <>
                  <Ionicons name="checkmark-circle" size={18} color="#FFF" />
                  <Text style={st.saveBtnText}>Save</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        )}
      </KeyboardAvoidingView>

      {/* Time Picker Modal */}
      <Modal visible={timeModal} transparent animationType="slide">
        <View style={st.modalOverlay}>
          <View style={st.modalContent}>
            <Text style={st.modalTitle}>Select Time</Text>
            <View style={st.pickerRow}>
              <ScrollView style={st.pickerCol} showsVerticalScrollIndicator={false}>
                {HOUR_OPTIONS.map(h => (
                  <TouchableOpacity key={h} style={[st.pickerItem, pickHour === h && st.pickerActive]}
                    onPress={() => setPickHour(h)}>
                    <Text style={[st.pickerItemText, pickHour === h && { color: '#FFF', fontWeight: '700' }]}>{h}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
              <Text style={st.pickerSep}>:</Text>
              <ScrollView style={st.pickerCol} showsVerticalScrollIndicator={false}>
                {MIN_OPTIONS.map(m => (
                  <TouchableOpacity key={m} style={[st.pickerItem, pickMin === m && st.pickerActive]}
                    onPress={() => setPickMin(m)}>
                    <Text style={[st.pickerItemText, pickMin === m && { color: '#FFF', fontWeight: '700' }]}>{m}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
            <View style={st.modalActions}>
              <TouchableOpacity style={st.modalCancel} onPress={() => setTimeModal(false)}>
                <Text style={st.modalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={st.modalConfirm} onPress={confirmTime}>
                <Text style={st.modalConfirmText}>Confirm</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );

  function renderActivities() {
    return (
      <View style={{ padding: 16 }}>
        {activities.map((act, idx) => {
          const areaInfo = LIFE_AREAS.find(a => a.id === act.area_of_life);
          return (
            <View key={act.activity_id} style={st.actCard}>
              <View style={st.actHeader}>
                <Text style={st.actNum}>#{idx + 1}</Text>
                {act.duration_minutes > 0 && (
                  <Text style={st.actDur}>{formatMins(act.duration_minutes)}</Text>
                )}
                {activities.length > 1 && (
                  <TouchableOpacity onPress={() => removeActivity(idx)}>
                    <Ionicons name="close-circle" size={18} color={COLORS.error} />
                  </TouchableOpacity>
                )}
              </View>

              {/* Time row */}
              <View style={st.timeRow}>
                <TouchableOpacity style={st.timeBtn} onPress={() => openTimePicker(idx, 'from_time')}>
                  <Ionicons name="time-outline" size={14} color="#7C3AED" />
                  <Text style={st.timeBtnText}>{act.from_time || 'From'}</Text>
                </TouchableOpacity>
                <Ionicons name="arrow-forward" size={14} color={COLORS.textMuted} />
                <TouchableOpacity style={st.timeBtn} onPress={() => openTimePicker(idx, 'to_time')}>
                  <Ionicons name="time-outline" size={14} color="#7C3AED" />
                  <Text style={st.timeBtnText}>{act.to_time || 'To'}</Text>
                </TouchableOpacity>
              </View>

              {/* Activity description */}
              <TextInput style={st.actInput} placeholder="Significant Activity..."
                placeholderTextColor={COLORS.textMuted}
                value={act.activity} onChangeText={v => updateActivity(idx, 'activity', v)} />

              {/* Area of Life chips */}
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 6 }}>
                <View style={st.chipRow}>
                  {LIFE_AREAS.map(area => (
                    <TouchableOpacity key={area.id}
                      style={[st.areaChip, act.area_of_life === area.id && { backgroundColor: area.color, borderColor: area.color }]}
                      onPress={() => updateActivity(idx, 'area_of_life', area.id)}>
                      <Ionicons name={area.icon as any} size={10}
                        color={act.area_of_life === area.id ? '#FFF' : area.color} />
                      <Text style={[st.areaChipText, act.area_of_life === area.id && { color: '#FFF' }]}
                        numberOfLines={1}>{area.name}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>

              {/* Category: Problem / Need / Aspiration */}
              <View style={st.catRow}>
                {CATEGORIES.map(cat => (
                  <TouchableOpacity key={cat.id}
                    style={[st.catChip, act.category === cat.id && { backgroundColor: cat.color, borderColor: cat.color }]}
                    onPress={() => updateActivity(idx, 'category', cat.id)}>
                    <Ionicons name={cat.icon as any} size={10}
                      color={act.category === cat.id ? '#FFF' : cat.color} />
                    <Text style={[st.catChipText, act.category === cat.id && { color: '#FFF' }]}>{cat.name}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Remarks */}
              <TextInput style={[st.actInput, { minHeight: 32, fontSize: 12 }]} placeholder="Remarks..."
                placeholderTextColor={COLORS.textMuted}
                value={act.remarks} onChangeText={v => updateActivity(idx, 'remarks', v)} />
            </View>
          );
        })}

        {/* Daily remarks */}
        <View style={{ marginTop: 12 }}>
          <Text style={st.label}>Daily Remarks</Text>
          <TextInput style={[st.actInput, { minHeight: 48 }]} placeholder="Overall day notes..."
            placeholderTextColor={COLORS.textMuted}
            value={remarks} onChangeText={setRemarks} multiline />
        </View>
      </View>
    );
  }

  function renderComparison() {
    if (!comparison?.comparison) {
      return (
        <View style={{ padding: 20, alignItems: 'center' }}>
          <Text style={{ color: COLORS.textMuted }}>No comparison data available</Text>
        </View>
      );
    }
    return (
      <View style={{ padding: 16 }}>
        <View style={st.compHeader}>
          <Text style={st.compTitle}>Planned vs Actual — {dateParam}</Text>
          <Text style={st.compSub}>
            {comparison.actual_areas} actual areas · {comparison.planned_areas} planned areas · {formatMins(comparison.total_actual_minutes)}
          </Text>
        </View>

        {comparison.comparison.map((item: any) => (
          <View key={item.area_id} style={[st.compCard, {
            borderLeftColor: item.gap === 'covered' ? '#10B981' :
              item.gap === 'missed' ? '#EF4444' :
              item.gap === 'unplanned' ? '#F59E0B' : COLORS.border,
          }]}>
            <View style={st.compCardHeader}>
              <Text style={st.compAreaName}>{item.area_name}</Text>
              <View style={[st.gapBadge, {
                backgroundColor: item.gap === 'covered' ? '#10B98120' :
                  item.gap === 'missed' ? '#EF444420' :
                  item.gap === 'unplanned' ? '#F59E0B20' : COLORS.divider,
              }]}>
                <Text style={[st.gapText, {
                  color: item.gap === 'covered' ? '#10B981' :
                    item.gap === 'missed' ? '#EF4444' :
                    item.gap === 'unplanned' ? '#F59E0B' : COLORS.textMuted,
                }]}>{item.gap.toUpperCase()}</Text>
              </View>
            </View>

            {item.has_actual && (
              <Text style={st.compDetail}>
                Actual: {formatMins(item.actual_minutes)} ({item.actual_activities?.length || 0} activities)
              </Text>
            )}
            {item.planned_tasks?.length > 0 && (
              <Text style={st.compDetail}>
                CTT Tasks: {item.planned_tasks.join(', ')}
              </Text>
            )}
            {item.planned_routines?.length > 0 && (
              <Text style={st.compDetail}>
                Routines: {item.planned_routines.join(', ')}
              </Text>
            )}
            {item.planned_goals?.length > 0 && (
              <Text style={st.compDetail}>
                Goals: {item.planned_goals.join(', ')}
              </Text>
            )}
          </View>
        ))}
      </View>
    );
  }
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, paddingBottom: 18 },
  backBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },

  tabRow: { flexDirection: 'row', paddingHorizontal: 16, paddingTop: 10, gap: 6, paddingBottom: 6 },
  tab: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 7, borderRadius: 16, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  tabActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  tabText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },

  actCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  actHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  actNum: { fontSize: 12, fontWeight: '700', color: '#7C3AED' },
  actDur: { flex: 1, fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  timeRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  timeBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, borderWidth: 1, borderColor: '#7C3AED30', backgroundColor: '#7C3AED08' },
  timeBtnText: { fontSize: 13, fontWeight: '600', color: '#7C3AED' },

  actInput: { backgroundColor: COLORS.background, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary, marginTop: 4 },

  chipRow: { flexDirection: 'row', gap: 4 },
  areaChip: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 5, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  areaChipText: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted },

  catRow: { flexDirection: 'row', gap: 6, marginTop: 8 },
  catChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  catChipText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  label: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },

  // Comparison
  compHeader: { marginBottom: 12 },
  compTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  compSub: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  compCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border, borderLeftWidth: 4 },
  compCardHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  compAreaName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  gapBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  gapText: { fontSize: 9, fontWeight: '700' },
  compDetail: { fontSize: 12, color: COLORS.textSecondary, marginTop: 3 },

  // Bottom
  bottom: { flexDirection: 'row', alignItems: 'center', padding: 12, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white, gap: 10 },
  addRow: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: '#7C3AED', },
  addText: { fontSize: 13, fontWeight: '600', color: '#7C3AED' },
  saveBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#7C3AED', borderRadius: 12, paddingVertical: 14 },
  saveBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },

  // Time picker modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: COLORS.white, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, paddingBottom: Platform.OS === 'ios' ? 40 : 20 },
  modalTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center', marginBottom: 16 },
  pickerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', height: 160 },
  pickerCol: { width: 80, maxHeight: 160 },
  pickerSep: { fontSize: 24, fontWeight: '700', color: COLORS.textPrimary, marginHorizontal: 8 },
  pickerItem: { paddingVertical: 8, alignItems: 'center', borderRadius: 8, marginVertical: 2 },
  pickerActive: { backgroundColor: '#7C3AED' },
  pickerItemText: { fontSize: 18, color: COLORS.textPrimary },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: 16 },
  modalCancel: { flex: 1, paddingVertical: 12, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  modalCancelText: { fontSize: 14, fontWeight: '600', color: COLORS.textMuted },
  modalConfirm: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#7C3AED', alignItems: 'center' },
  modalConfirmText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
});
