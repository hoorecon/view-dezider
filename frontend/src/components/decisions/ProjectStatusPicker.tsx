/**
 * ProjectStatusPicker — chip + modal-picker for the 11 GEM project statuses.
 *
 * Calls PUT /api/gem/goals/{goal_id}/project-status which cascades to linked
 * CTT tasks and LifeDezider routines server-side. Shows a toast with the
 * cascade summary.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Modal, ScrollView, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import api from '../../utils/api';
import { showAlert } from '../../utils/alert';

export interface ProjectStatusEntry {
  key: string; label: string; color: string; icon: string;
}

let _statusCache: ProjectStatusEntry[] | null = null;
let _cascadeRules: { deactivates: string[]; reactivates: string[] } | null = null;

async function loadStatuses(): Promise<{ statuses: ProjectStatusEntry[]; rules: any }> {
  if (_statusCache && _cascadeRules) return { statuses: _statusCache, rules: _cascadeRules };
  try {
    const r = await api.get('/gem/project-statuses');
    _statusCache = r.data.statuses || [];
    _cascadeRules = {
      deactivates: r.data.cascade_deactivates_routines || [],
      reactivates: r.data.cascade_reactivates_routines || [],
    };
    return { statuses: _statusCache, rules: _cascadeRules };
  } catch {
    return { statuses: [], rules: { deactivates: [], reactivates: [] } };
  }
}

interface Props {
  goalId: string;
  currentStatus?: string;
  onChange?: (newStatus: string, cascade: any) => void;
  compact?: boolean;
}

export default function ProjectStatusPicker({ goalId, currentStatus = 'open', onChange, compact = false }: Props) {
  const [statuses, setStatuses] = useState<ProjectStatusEntry[]>([]);
  const [rules, setRules] = useState<any>({ deactivates: [], reactivates: [] });
  const [pickerOpen, setPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [localStatus, setLocalStatus] = useState(currentStatus);

  useEffect(() => { setLocalStatus(currentStatus); }, [currentStatus]);
  useEffect(() => { loadStatuses().then(({ statuses, rules }) => { setStatuses(statuses); setRules(rules); }); }, []);

  const current = statuses.find(s => s.key === localStatus) ||
                  { key: localStatus, label: localStatus, color: COLORS.textMuted, icon: 'ellipse-outline' };

  const choose = useCallback(async (key: string) => {
    if (key === localStatus) { setPickerOpen(false); return; }
    const willCascade = rules.deactivates.includes(key) || rules.reactivates.includes(key) || ['on_hold','cancelled','completed'].includes(key);
    if (willCascade) {
      const ok = (typeof window !== 'undefined' && (window as any).confirm)
        ? (window as any).confirm(`Set status to "${statuses.find(s=>s.key===key)?.label || key}"?\n\nThis will cascade to all linked CTT tasks and LifeDezider routines.`)
        : true;
      if (!ok) return;
    }
    try {
      setSaving(true);
      const r = await api.put(`/gem/goals/${goalId}/project-status`, { project_status: key });
      const cascade = r.data?.cascade || {};
      setLocalStatus(key);
      setPickerOpen(false);
      onChange?.(key, cascade);
      const taskMsg = cascade.tasks_changed ? `${cascade.tasks_changed} task${cascade.tasks_changed===1?'':'s'}` : '';
      const routMsg = cascade.routines_changed ? `${cascade.routines_changed} routine${cascade.routines_changed===1?'':'s'}` : '';
      const join = taskMsg && routMsg ? ' · ' : '';
      if (taskMsg || routMsg) {
        showAlert('Status updated', `Cascaded to ${taskMsg}${join}${routMsg}.`);
      }
    } catch (e: any) {
      showAlert('Update failed', e?.response?.data?.detail || e.message);
    } finally { setSaving(false); }
  }, [goalId, localStatus, statuses, rules, onChange]);

  return (
    <>
      <TouchableOpacity
        onPress={(e: any) => { e?.stopPropagation?.(); setPickerOpen(true); }}
        style={[s.chip, { backgroundColor: current.color + '18', borderColor: current.color + '55' }, compact && s.chipCompact]}
        testID={`project-status-chip-${goalId}`}
      >
        <Ionicons name={current.icon as any} size={11} color={current.color} />
        <Text style={[s.chipText, { color: current.color }, compact && s.chipTextCompact]} numberOfLines={1}>
          {current.label}
        </Text>
        {!compact && <Ionicons name="chevron-down" size={10} color={current.color} />}
      </TouchableOpacity>

      <Modal visible={pickerOpen} transparent animationType="slide" onRequestClose={() => setPickerOpen(false)}>
        <Pressable style={s.overlay} onPress={() => setPickerOpen(false)}>
          <Pressable style={s.sheet} onPress={(e) => e.stopPropagation()}>
            <View style={s.sheetHead}>
              <View>
                <Text style={s.sheetTitle}>Project Status</Text>
                <Text style={s.sheetSub}>Statuses marked ⚡ cascade to linked CTT tasks & routines</Text>
              </View>
              <TouchableOpacity onPress={() => setPickerOpen(false)} hitSlop={8}>
                <Ionicons name="close" size={22} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 480 }}>
              {statuses.map(st => {
                const cascades = rules.deactivates.includes(st.key) || rules.reactivates.includes(st.key) || ['on_hold','cancelled','completed'].includes(st.key);
                const isActive = st.key === localStatus;
                return (
                  <TouchableOpacity
                    key={st.key}
                    style={[s.option, isActive && { backgroundColor: st.color + '12' }]}
                    onPress={() => choose(st.key)}
                    disabled={saving}
                    testID={`project-status-option-${st.key}`}
                  >
                    <View style={[s.optIcon, { backgroundColor: st.color + '22' }]}>
                      <Ionicons name={st.icon as any} size={14} color={st.color} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={[s.optLabel, isActive && { color: st.color, fontWeight: '700' }]}>{st.label}</Text>
                      {cascades && <Text style={s.optHint}>⚡ Cascades to tasks & routines</Text>}
                    </View>
                    {isActive && <Ionicons name="checkmark-circle" size={16} color={st.color} />}
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
            {saving && (
              <View style={s.savingOverlay}>
                <ActivityIndicator color={COLORS.primary} />
                <Text style={s.savingText}>Cascading status…</Text>
              </View>
            )}
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, borderWidth: 1, alignSelf: 'flex-start' },
  chipCompact: { paddingHorizontal: 6, paddingVertical: 2 },
  chipText: { fontSize: 10, fontWeight: '700' },
  chipTextCompact: { fontSize: 9 },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 16, paddingBottom: 24 },
  sheetHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  sheetSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  option: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 11, paddingHorizontal: 10, borderRadius: 8, marginBottom: 2 },
  optIcon: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  optLabel: { fontSize: 13, color: COLORS.textPrimary, fontWeight: '500' },
  optHint: { fontSize: 10, color: COLORS.textMuted, marginTop: 1 },
  savingOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(255,255,255,0.85)', alignItems: 'center', justifyContent: 'center', gap: 6 },
  savingText: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '600' },
});
