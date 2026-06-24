/**
 * MilestoneEditor — list of recursive SMART milestones under a Goal.
 *
 * Each milestone is itself a mini-SMART grid: S/M/A/R/T + metrics + target date.
 * The same MetricsEditor / SkillsetPicker / ResourcePicker are reused for
 * consistency with the parent Goal.
 *
 * Backend wire-up:
 *  - POST    /goal-setter/goals/{goal_id}/milestones
 *  - PUT     /goal-setter/goals/{goal_id}/milestones/{milestone_id}
 *  - DELETE  /goal-setter/goals/{goal_id}/milestones/{milestone_id}
 *  - PUT     /goal-setter/goals/{goal_id}/milestones/{milestone_id}/status
 *
 * Props:
 *  - goalId         (required when persisting; if null the editor runs in
 *                    "draft" mode and only updates local state via onChange)
 *  - milestones     current list
 *  - onChange       fired after any server-confirmed mutation
 *  - readOnly       if true, only status / progress is editable (used in GEM)
 */
import React, { useState } from 'react';
import {
  View, Text, TextInput, StyleSheet, TouchableOpacity,
  ActivityIndicator, Modal, ScrollView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import api from '../utils/api';
import MetricsEditor, { type GoalMetric } from './MetricsEditor';
import SkillsetPicker from './SkillsetPicker';
import ResourcePicker, { type PickedResource } from './ResourcePicker';
import { DecisionContinuePanel } from './DecisionContinuePanel';

export interface SmartMilestone {
  milestone_id: string;
  title: string;
  specific?: string;
  measurable?: string;
  metrics?: GoalMetric[];
  achievable?: string;
  achievable_skills?: string[];
  realistic?: string;
  realistic_resources?: PickedResource[];
  timebound?: string;
  target_date?: string;
  order?: number;
  status: 'pending' | 'in_progress' | 'done' | 'blocked';
  progress_pct: number;
  notes?: string;
}

interface Props {
  goalId: string | null;
  milestones: SmartMilestone[];
  onChange: (m: SmartMilestone[]) => void;
  readOnly?: boolean;
}

const STATUS_META: Record<SmartMilestone['status'], { label: string; color: string; bg: string }> = {
  pending: { label: 'Pending', color: '#6B7280', bg: '#F3F4F6' },
  in_progress: { label: 'In Progress', color: '#2563EB', bg: '#DBEAFE' },
  done: { label: 'Done', color: '#059669', bg: '#D1FAE5' },
  blocked: { label: 'Blocked', color: '#DC2626', bg: '#FEE2E2' },
};

const newDraft = (idx: number): SmartMilestone => ({
  milestone_id: `draft_${Date.now().toString(36)}_${idx}`,
  title: '',
  specific: '',
  measurable: '',
  metrics: [],
  achievable: '',
  achievable_skills: [],
  realistic: '',
  realistic_resources: [],
  timebound: '',
  target_date: '',
  order: idx,
  status: 'pending',
  progress_pct: 0,
  notes: '',
});

export default function MilestoneEditor({ goalId, milestones, onChange, readOnly }: Props) {
  const list = Array.isArray(milestones) ? milestones : [];
  const [editing, setEditing] = useState<SmartMilestone | null>(null);
  const [saving, setSaving] = useState(false);
  const [exploreId, setExploreId] = useState<string | null>(null);

  const persistAdd = async (m: SmartMilestone) => {
    if (!goalId) {
      onChange([...list, { ...m, order: list.length }]);
      return;
    }
    const res = await api.post(`/goal-setter/goals/${goalId}/milestones`, m);
    onChange([...list, res.data]);
  };

  const persistUpdate = async (m: SmartMilestone) => {
    if (!goalId || m.milestone_id.startsWith('draft_')) {
      onChange(list.map(x => (x.milestone_id === m.milestone_id ? m : x)));
      return;
    }
    const res = await api.put(`/goal-setter/goals/${goalId}/milestones/${m.milestone_id}`, m);
    onChange(list.map(x => (x.milestone_id === m.milestone_id ? res.data : x)));
  };

  const persistDelete = async (id: string) => {
    if (!goalId || id.startsWith('draft_')) {
      onChange(list.filter(x => x.milestone_id !== id));
      return;
    }
    await api.delete(`/goal-setter/goals/${goalId}/milestones/${id}`);
    onChange(list.filter(x => x.milestone_id !== id));
  };

  const updateStatus = async (m: SmartMilestone, status: SmartMilestone['status']) => {
    if (!goalId || m.milestone_id.startsWith('draft_')) {
      onChange(list.map(x => x.milestone_id === m.milestone_id ? { ...x, status, progress_pct: status === 'done' ? 100 : x.progress_pct } : x));
      return;
    }
    const res = await api.put(`/goal-setter/goals/${goalId}/milestones/${m.milestone_id}/status`, { status });
    onChange(list.map(x => (x.milestone_id === m.milestone_id ? res.data : x)));
  };

  const openAdd = () => setEditing(newDraft(list.length));
  const openEdit = (m: SmartMilestone) => setEditing({ ...m });

  const save = async () => {
    if (!editing) return;
    if (!editing.title.trim()) return;
    setSaving(true);
    try {
      const exists = list.some(x => x.milestone_id === editing.milestone_id);
      if (exists) await persistUpdate(editing);
      else await persistAdd(editing);
      setEditing(null);
    } catch (e) {
      // Surface a minimal alert via console; modal stays open
      console.warn('Milestone save failed', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <View>
      {list.length === 0 ? (
        <View style={st.empty}>
          <Ionicons name="flag-outline" size={20} color={COLORS.textMuted} />
          <Text style={st.emptyText}>
            No milestones yet. Break this Goal into recursive SMART sub-goals to track gradual progress.
          </Text>
        </View>
      ) : (
        list.map((m, idx) => {
          const meta = STATUS_META[m.status] || STATUS_META.pending;
          return (
            <View key={m.milestone_id} style={st.row}>
              <View style={st.rowHead}>
                <View style={st.idxBadge}><Text style={st.idxText}>#{idx + 1}</Text></View>
                <Text style={st.rowTitle} numberOfLines={1}>{m.title || '(untitled)'}</Text>
                <View style={[st.statusPill, { backgroundColor: meta.bg }]}>
                  <Text style={[st.statusText, { color: meta.color }]}>{meta.label}</Text>
                </View>
              </View>
              <View style={st.metaRow}>
                {!!m.target_date && <Text style={st.metaTxt}>📅 {m.target_date}</Text>}
                {!!m.metrics?.length && <Text style={st.metaTxt}>📊 {m.metrics.length} metrics</Text>}
                <Text style={st.metaTxt}>· {m.progress_pct}%</Text>
              </View>

              <View style={st.actionRow}>
                {(['pending', 'in_progress', 'done', 'blocked'] as const).map(s => {
                  const sm = STATUS_META[s];
                  const active = m.status === s;
                  return (
                    <TouchableOpacity
                      key={s}
                      style={[st.statusBtn, active && { backgroundColor: sm.color, borderColor: sm.color }]}
                      onPress={() => updateStatus(m, s)}
                    >
                      <Text style={[st.statusBtnText, active && { color: '#FFF' }]}>{sm.label}</Text>
                    </TouchableOpacity>
                  );
                })}
                {!readOnly && (
                  <>
                    <TouchableOpacity style={st.iconBtn} onPress={() => openEdit(m)}>
                      <Ionicons name="create-outline" size={14} color={COLORS.primary} />
                    </TouchableOpacity>
                    <TouchableOpacity style={st.iconBtn} onPress={() => persistDelete(m.milestone_id)}>
                      <Ionicons name="trash-outline" size={14} color={COLORS.error} />
                    </TouchableOpacity>
                  </>
                )}
                <TouchableOpacity
                  style={st.exploreBtn}
                  onPress={() => setExploreId(exploreId === m.milestone_id ? null : m.milestone_id)}
                >
                  <Ionicons name="rocket-outline" size={13} color="#3B82F6" />
                  <Text style={st.exploreBtnTxt}>Go deeper</Text>
                  <Ionicons name={exploreId === m.milestone_id ? 'chevron-up' : 'chevron-down'} size={12} color="#3B82F6" />
                </TouchableOpacity>
              </View>
              {exploreId === m.milestone_id && (
                <DecisionContinuePanel
                  sourceModule="goal-setter"
                  sourceDecisionId={goalId || m.milestone_id}
                  title={m.title}
                  contextSummary={`Milestone from your SMART goal${m.title ? `: ${m.title}` : ''}.`}
                />
              )}
            </View>
          );
        })
      )}

      {!readOnly && (
        <TouchableOpacity style={st.addBtn} onPress={openAdd}>
          <Ionicons name="add" size={14} color="#059669" />
          <Text style={st.addBtnTxt}>Add Milestone</Text>
        </TouchableOpacity>
      )}

      {/* Edit modal — recursive mini-SMART grid */}
      <Modal visible={!!editing} transparent animationType="fade" onRequestClose={() => setEditing(null)}>
        <View style={st.modalBg}>
          <View style={st.modalCard}>
            <View style={st.modalHead}>
              <Text style={st.modalTitle}>{editing && list.some(x => x.milestone_id === editing.milestone_id) ? 'Edit' : 'Add'} Milestone</Text>
              <TouchableOpacity onPress={() => setEditing(null)}>
                <Ionicons name="close" size={20} color={COLORS.textMuted} />
              </TouchableOpacity>
            </View>
            {editing && (
              <ScrollView style={{ maxHeight: 500 }} contentContainerStyle={{ paddingBottom: 12 }}>
                <Text style={st.fieldLabel}>Title *</Text>
                <TextInput
                  style={st.input}
                  value={editing.title}
                  onChangeText={t => setEditing({ ...editing, title: t })}
                  placeholder="e.g., MVP Beta to 10 testers"
                  placeholderTextColor={COLORS.textMuted}
                />

                <Text style={st.fieldLabel}>S — Specific</Text>
                <TextInput style={[st.input, st.ta]} multiline value={editing.specific || ''} onChangeText={t => setEditing({ ...editing, specific: t })} />

                <Text style={st.fieldLabel}>M — Measurable</Text>
                <TextInput style={[st.input, st.ta]} multiline value={editing.measurable || ''} onChangeText={t => setEditing({ ...editing, measurable: t })} />

                <View style={st.subBox}>
                  <Text style={st.subBoxLabel}>Structured Metrics</Text>
                  <MetricsEditor
                    value={editing.metrics || []}
                    onChange={(metrics) => setEditing({ ...editing, metrics })}
                  />
                </View>

                <Text style={st.fieldLabel}>A — Achievable</Text>
                <TextInput style={[st.input, st.ta]} multiline value={editing.achievable || ''} onChangeText={t => setEditing({ ...editing, achievable: t })} />

                <View style={st.subBox}>
                  <SkillsetPicker
                    value={editing.achievable_skills || []}
                    onChange={(achievable_skills) => setEditing({ ...editing, achievable_skills })}
                  />
                </View>

                <Text style={st.fieldLabel}>R — Realistic</Text>
                <TextInput style={[st.input, st.ta]} multiline value={editing.realistic || ''} onChangeText={t => setEditing({ ...editing, realistic: t })} />

                <View style={st.subBox}>
                  <ResourcePicker
                    value={editing.realistic_resources || []}
                    onChange={(realistic_resources) => setEditing({ ...editing, realistic_resources })}
                  />
                </View>

                <Text style={st.fieldLabel}>T — Time-bound</Text>
                <TextInput style={[st.input, st.ta]} multiline value={editing.timebound || ''} onChangeText={t => setEditing({ ...editing, timebound: t })} />

                <Text style={st.fieldLabel}>Target Date</Text>
                <TextInput style={st.input} value={editing.target_date || ''} onChangeText={t => setEditing({ ...editing, target_date: t })} placeholder="YYYY-MM-DD" placeholderTextColor={COLORS.textMuted} />

                <Text style={st.fieldLabel}>Progress %</Text>
                <TextInput style={st.input} keyboardType="numeric" value={String(editing.progress_pct ?? 0)} onChangeText={t => setEditing({ ...editing, progress_pct: Math.max(0, Math.min(100, parseInt(t) || 0)) })} />
              </ScrollView>
            )}
            <View style={st.modalFoot}>
              <TouchableOpacity style={st.cancelBtn} onPress={() => setEditing(null)}>
                <Text style={st.cancelBtnTxt}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[st.saveBtn, (!editing?.title.trim() || saving) && { opacity: 0.5 }]}
                disabled={!editing?.title.trim() || saving}
                onPress={save}
              >
                {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={st.saveBtnTxt}>Save Milestone</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const st = StyleSheet.create({
  empty: { padding: 14, alignItems: 'center', backgroundColor: '#F0FDF4', borderRadius: 10, gap: 6 },
  emptyText: { fontSize: 11, color: '#065F46', textAlign: 'center' },
  row: { backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#D1FAE5', borderRadius: 10, padding: 10, marginBottom: 8 },
  rowHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  idxBadge: { backgroundColor: '#D1FAE5', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  idxText: { fontSize: 10, fontWeight: '700', color: '#059669' },
  rowTitle: { flex: 1, fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  statusPill: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: 8 },
  statusText: { fontSize: 10, fontWeight: '700' },
  metaRow: { flexDirection: 'row', gap: 8, marginTop: 4, marginBottom: 6, flexWrap: 'wrap' },
  metaTxt: { fontSize: 11, color: COLORS.textMuted },
  actionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, alignItems: 'center' },
  statusBtn: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, borderWidth: 1, borderColor: '#E5E7EB' },
  statusBtnText: { fontSize: 10, fontWeight: '600', color: COLORS.textSecondary },
  iconBtn: { padding: 6 },
  exploreBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, borderWidth: 1, borderColor: '#BFDBFE', backgroundColor: '#EFF6FF' },
  exploreBtnTxt: { fontSize: 11, fontWeight: '700', color: '#3B82F6' },
  addBtn: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 4, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#059669', borderStyle: 'dashed', marginTop: 4 },
  addBtnTxt: { fontSize: 12, fontWeight: '700', color: '#059669' },

  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  modalCard: { backgroundColor: '#FFFFFF', borderRadius: 14, padding: 14, width: '100%', maxWidth: 600 },
  modalHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  modalTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  fieldLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textSecondary, marginTop: 8, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 8, paddingHorizontal: 10, paddingVertical: Platform.OS === 'web' ? 8 : 6, fontSize: 12, color: COLORS.textPrimary, backgroundColor: '#FFFFFF' },
  ta: { minHeight: 50, textAlignVertical: 'top' },
  subBox: { backgroundColor: '#F8FAFC', borderRadius: 8, padding: 8, marginTop: 4, borderWidth: 1, borderColor: '#E5E7EB' },
  subBoxLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textSecondary, marginBottom: 4 },
  modalFoot: { flexDirection: 'row', gap: 8, marginTop: 10 },
  cancelBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center', backgroundColor: '#F1F5F9' },
  cancelBtnTxt: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  saveBtn: { flex: 2, paddingVertical: 10, borderRadius: 8, alignItems: 'center', backgroundColor: '#059669' },
  saveBtnTxt: { fontSize: 12, fontWeight: '700', color: '#FFFFFF' },
});
