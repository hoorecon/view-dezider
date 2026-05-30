/**
 * LinkedGoalMilestonesView
 * Renders a SMART Goal (from goal_setter) inside a GEM Goal context.
 * - S·M·A·R·T grid + structured metrics are STRUCTURALLY READ-ONLY
 * - Milestone STATUS and PROGRESS remain editable (executed in GEM)
 * - Uses lightweight endpoint: PUT /api/goal-setter/goals/{id}/milestones/{mid}/status
 */
import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Slider from '@react-native-community/slider';
import { COLORS } from '../constants/colors';
import api from '../utils/api';

const SMART_DEFS = [
  { id: 'specific',  letter: 'S', name: 'Specific',  color: '#3B82F6' },
  { id: 'measurable',letter: 'M', name: 'Measurable',color: '#10B981' },
  { id: 'achievable',letter: 'A', name: 'Achievable',color: '#F59E0B' },
  { id: 'realistic', letter: 'R', name: 'Realistic', color: '#8B5CF6' },
  { id: 'timebound', letter: 'T', name: 'Time-bound',color: '#EF4444' },
];

const STATUS_OPTIONS: Array<{ id: string; label: string; color: string; icon: any }> = [
  { id: 'pending',     label: 'Pending',     color: '#94A3B8', icon: 'time-outline' },
  { id: 'in_progress', label: 'In Progress', color: '#3B82F6', icon: 'play-circle-outline' },
  { id: 'done',        label: 'Done',        color: '#10B981', icon: 'checkmark-circle' },
  { id: 'blocked',     label: 'Blocked',     color: '#EF4444', icon: 'alert-circle-outline' },
];

interface Props {
  smartGoalId: string;
  onUnlink?: () => void;
}

export default function LinkedGoalMilestonesView({ smartGoalId, onUnlink }: Props) {
  const [loading, setLoading] = useState(true);
  const [goal, setGoal] = useState<any>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => { load(); }, [smartGoalId]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/goal-setter/goals/${smartGoalId}`);
      setGoal(res.data);
    } catch (e) {
      console.error('Linked goal load', e);
    } finally { setLoading(false); }
  };

  const updateMilestone = async (mid: string, patch: { status?: string; progress_pct?: number }) => {
    setSavingId(mid);
    // Optimistic update
    setGoal((g: any) => {
      if (!g) return g;
      const ms = [...(g.milestones || [])];
      const i = ms.findIndex((m: any) => m.milestone_id === mid);
      if (i >= 0) ms[i] = { ...ms[i], ...patch };
      return { ...g, milestones: ms };
    });
    try {
      await api.put(`/goal-setter/goals/${smartGoalId}/milestones/${mid}/status`, patch);
    } catch (e) {
      console.error('Status update failed', e);
      // Reload to revert
      load();
    } finally { setSavingId(null); }
  };

  if (loading) {
    return (
      <View style={s.box}>
        <ActivityIndicator color={COLORS.primary} />
      </View>
    );
  }

  if (!goal) {
    return (
      <View style={s.box}>
        <View style={s.warnRow}>
          <Ionicons name="warning" size={14} color="#B91C1C" />
          <Text style={s.warnText}>Linked SMART Goal not found.</Text>
          {onUnlink && (
            <TouchableOpacity onPress={onUnlink}><Text style={s.unlinkText}>Unlink</Text></TouchableOpacity>
          )}
        </View>
      </View>
    );
  }

  const milestones = goal.milestones || [];
  const totalMs = milestones.length;
  const doneMs = milestones.filter((m: any) => m.status === 'done').length;
  const avgProgress = totalMs ? Math.round(milestones.reduce((s: number, m: any) => s + (m.progress_pct || 0), 0) / totalMs) : 0;

  return (
    <View style={s.box}>
      {/* Header */}
      <View style={s.head}>
        <Ionicons name="link" size={16} color="#059669" />
        <View style={{ flex: 1 }}>
          <Text style={s.headTitle} numberOfLines={1}>{goal.title}</Text>
          <Text style={s.headSub}>SMART Goal · {doneMs}/{totalMs} milestones · {avgProgress}% avg</Text>
        </View>
        {onUnlink && (
          <TouchableOpacity onPress={onUnlink} style={s.unlinkBtn}>
            <Ionicons name="unlink" size={14} color="#B91C1C" />
            <Text style={s.unlinkText}>Unlink</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Read-only SMART grid */}
      <View style={s.lockRow}>
        <Ionicons name="lock-closed" size={11} color={COLORS.textMuted} />
        <Text style={s.lockText}>Structure read-only · planned in Goal Setter</Text>
      </View>
      <View style={s.smartGrid}>
        {SMART_DEFS.map(d => {
          const val = (goal as any)[d.id] || '';
          if (!val) return null;
          return (
            <View key={d.id} style={s.smartRow}>
              <View style={[s.smartBadge, { backgroundColor: d.color }]}>
                <Text style={s.smartBadgeText}>{d.letter}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.smartName}>{d.name}</Text>
                <Text style={s.smartVal} numberOfLines={3}>{val}</Text>
              </View>
            </View>
          );
        })}
      </View>

      {/* Metrics (read-only) */}
      {(goal.metrics || []).length > 0 && (
        <View style={s.metricsBox}>
          <View style={s.metricsHead}>
            <Ionicons name="stats-chart" size={12} color="#059669" />
            <Text style={s.metricsHeadText}>Target Metrics ({goal.metrics.length})</Text>
          </View>
          {goal.metrics.map((m: any, i: number) => (
            <View key={i} style={s.metricRow}>
              <Text style={s.metricName} numberOfLines={1}>{m.name || 'Metric'}</Text>
              <Text style={s.metricVal}>
                {m.operator || '='} {m.target_value ?? '—'} {m.unit || ''}
              </Text>
            </View>
          ))}
        </View>
      )}

      {/* Milestones — interactive status/progress */}
      <View style={s.msSection}>
        <View style={s.msHead}>
          <Ionicons name="flag" size={14} color="#059669" />
          <Text style={s.msHeadTitle}>Milestones ({totalMs})</Text>
        </View>
        {totalMs === 0 && (
          <Text style={s.empty}>No milestones planned. Add them in Goal Setter.</Text>
        )}
        {milestones.map((m: any) => (
          <View key={m.milestone_id} style={s.msCard}>
            <View style={s.msTitleRow}>
              <Text style={s.msTitle} numberOfLines={2}>{m.title || 'Untitled milestone'}</Text>
              {savingId === m.milestone_id && <ActivityIndicator size="small" color={COLORS.primary} />}
            </View>
            {m.target_date ? (
              <Text style={s.msMeta}>Target: {m.target_date}</Text>
            ) : null}

            {/* SMART pill row for milestone (read-only) */}
            <View style={s.msSmartBar}>
              {SMART_DEFS.map(d => (
                <View key={d.id} style={[s.smartPill, { backgroundColor: (m as any)[d.id] ? d.color : '#E5E7EB' }]}>
                  <Text style={[s.smartPillText, { color: (m as any)[d.id] ? '#FFF' : COLORS.textMuted }]}>{d.letter}</Text>
                </View>
              ))}
              {(m.metrics || []).length > 0 && (
                <View style={s.smartPillMetric}>
                  <Ionicons name="stats-chart" size={10} color="#059669" />
                  <Text style={s.smartPillMetricText}>{m.metrics.length}</Text>
                </View>
              )}
            </View>

            {/* Status chips */}
            <View style={s.statusRow}>
              {STATUS_OPTIONS.map(opt => {
                const active = m.status === opt.id;
                return (
                  <TouchableOpacity key={opt.id}
                    style={[s.statusChip, active && { backgroundColor: opt.color, borderColor: opt.color }]}
                    onPress={() => updateMilestone(m.milestone_id, { status: opt.id })}
                  >
                    <Ionicons name={opt.icon} size={11} color={active ? '#FFF' : opt.color} />
                    <Text style={[s.statusText, active && { color: '#FFF' }]}>{opt.label}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Progress slider */}
            <View style={s.progRow}>
              <Text style={s.progLabel}>Progress: {m.progress_pct || 0}%</Text>
              <Slider
                style={{ flex: 1, height: 30 }}
                minimumValue={0} maximumValue={100} step={5}
                value={m.progress_pct || 0}
                onSlidingComplete={(v) => updateMilestone(m.milestone_id, { progress_pct: Math.round(v) })}
                minimumTrackTintColor="#10B981"
                maximumTrackTintColor="#E5E7EB"
                thumbTintColor="#059669"
              />
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  box: {
    marginTop: 16, padding: 14, borderRadius: 14,
    backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0',
  },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  headTitle: { fontSize: 14, fontWeight: '700', color: '#065F46' },
  headSub: { fontSize: 11, color: '#047857', marginTop: 1 },
  unlinkBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA' },
  unlinkText: { fontSize: 11, fontWeight: '600', color: '#B91C1C' },
  warnRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  warnText: { flex: 1, fontSize: 12, color: '#B91C1C' },
  lockRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6, marginBottom: 6 },
  lockText: { fontSize: 10, color: COLORS.textMuted, fontStyle: 'italic' },

  smartGrid: { backgroundColor: '#FFFFFF', borderRadius: 10, padding: 10, gap: 8 },
  smartRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  smartBadge: { width: 24, height: 24, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  smartBadgeText: { fontSize: 11, fontWeight: '800', color: '#FFFFFF' },
  smartName: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary },
  smartVal: { fontSize: 12, color: COLORS.textSecondary, marginTop: 1, lineHeight: 16 },

  metricsBox: { backgroundColor: '#F0FDF4', borderRadius: 10, padding: 10, marginTop: 8, borderWidth: 1, borderColor: '#A7F3D0' },
  metricsHead: { flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 6 },
  metricsHeadText: { fontSize: 11, fontWeight: '700', color: '#059669' },
  metricRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 3 },
  metricName: { flex: 1, fontSize: 12, color: '#065F46', fontWeight: '600' },
  metricVal: { fontSize: 11, color: '#047857', fontWeight: '700' },

  msSection: { marginTop: 10 },
  msHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  msHeadTitle: { fontSize: 13, fontWeight: '700', color: '#065F46' },
  empty: { fontSize: 12, color: COLORS.textMuted, fontStyle: 'italic', padding: 8 },

  msCard: { backgroundColor: '#FFFFFF', borderRadius: 10, padding: 10, marginBottom: 8, borderWidth: 1, borderColor: '#D1FAE5' },
  msTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  msTitle: { flex: 1, fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  msMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  msSmartBar: { flexDirection: 'row', gap: 4, marginTop: 6, alignItems: 'center' },
  smartPill: { width: 20, height: 20, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  smartPillText: { fontSize: 9, fontWeight: '800' },
  smartPillMetric: { flexDirection: 'row', alignItems: 'center', gap: 2, paddingHorizontal: 5, paddingVertical: 1, borderRadius: 10, backgroundColor: '#F0FDF4', borderWidth: 1, borderColor: '#A7F3D0' },
  smartPillMetricText: { fontSize: 9, fontWeight: '700', color: '#059669' },

  statusRow: { flexDirection: 'row', gap: 4, marginTop: 8, flexWrap: 'wrap' },
  statusChip: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E5E7EB' },
  statusText: { fontSize: 10, fontWeight: '600', color: COLORS.textSecondary },

  progRow: { marginTop: 6 },
  progLabel: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '600' },
});
