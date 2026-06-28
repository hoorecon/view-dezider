/**
 * Org Detail - 7×7 Assessment Matrix + 6 LeGs Goal Tree
 * Fortnightly cadence assessment + tree-like drill-down for goals.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

const LEVEL_ORDER = ['L1','L2','L3','L4','L5','L6'] as const;
const LEVEL_INFO: Record<string, { label: string; hint: string; color: string }> = {
  L1: { label: 'L1 · Financial',          hint: 'Revenue, GP, OP, PBT, PAT, Reserves',          color: '#DC2626' },
  L2: { label: 'L2 · Customer / Solution',hint: 'Segments, ARPU, Conversion, Channel partners', color: '#EA580C' },
  L3: { label: 'L3 · 7 Divisions',        hint: 'Strategic objective per division',             color: '#CA8A04' },
  L4: { label: 'L4 · Team',               hint: 'Per-team performance goals',                   color: '#16A34A' },
  L5: { label: 'L5 · Individual',         hint: 'Per-person delivery goals',                    color: '#0EA5E9' },
  L6: { label: 'L6 · Learning & Dev',     hint: 'Attitude / Knowledge / Skill plans',           color: '#8B5CF6' },
};

export default function OrgDetail() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const orgId = params.id as string;
  const [org, setOrg] = useState<any>(null);
  const [tab, setTab] = useState<'matrix'|'goals'>('matrix');
  const [divisions, setDivisions] = useState<any[]>([]);
  const [drivers, setDrivers] = useState<any[]>([]);
  const [scale, setScale] = useState<any[]>([]);
  const [matrix, setMatrix] = useState<Record<string, any>>({});
  const [due, setDue] = useState<any>(null);
  const [tree, setTree] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [scoring, setScoring] = useState<{division: string; driver: string} | null>(null);
  const [scoreRemarks, setScoreRemarks] = useState('');
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState<{ level: string; parent_goal_id: string | null } | null>(null);
  const [newGoal, setNewGoal] = useState<any>({});
  const [editingGoalId, setEditingGoalId] = useState<string | null>(null);
  const [smartGoals, setSmartGoals] = useState<any[]>([]);

  // Date helpers — UI uses DD-MM-YYYY, backend stores YYYY-MM-DD (ISO).
  const ddmmToIso = (s: string): string | null => {
    if (!s) return null;
    const m = s.match(/^(\d{2})-(\d{2})-(\d{4})$/);
    if (!m) return null;
    return `${m[3]}-${m[2]}-${m[1]}`;
  };
  const isoToDdmm = (s: string | null | undefined): string => {
    if (!s) return '';
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[3]}-${m[2]}-${m[1]}` : s;
  };

  // Load SMART goals once when modal opens (lazy)
  useEffect(() => {
    if (!adding) return;
    (async () => {
      try {
        const { data } = await api.get('/goal-setter/goals');
        setSmartGoals(data?.goals || data || []);
      } catch { setSmartGoals([]); }
    })();
  }, [adding]);

  const reload = async () => {
    setBusy(true);
    try {
      const [o, d1, d2, sc, m, dd, t] = await Promise.all([
        api.get(`/seven-seven/orgs/${orgId}`),
        api.get('/seven-seven/divisions'),
        api.get('/seven-seven/drivers'),
        api.get('/seven-seven/scale'),
        api.get(`/seven-seven/assess/${orgId}`),
        api.get(`/seven-seven/assess/${orgId}/due`),
        api.get(`/six-legs/goals/tree/${orgId}`),
      ]);
      setOrg(o.data);
      setDivisions(d1.data?.divisions || []);
      setDrivers(d2.data?.drivers || []);
      setScale(sc.data?.scale || []);
      const m2: Record<string, any> = {};
      (m.data?.matrix || []).forEach((c: any) => { m2[`${c.division_code}|${c.driver_code}`] = c; });
      setMatrix(m2);
      setDue(dd.data);
      setTree(t.data?.tree || []);
    } finally { setBusy(false); }
  };
  useFocusEffect(useCallback(() => { if (orgId) reload(); }, [orgId]));

  const submitScore = async (scaleCode: string) => {
    if (!scoring) return;
    try {
      await api.post('/seven-seven/assess', {
        user_org_id: orgId,
        division_code: scoring.division,
        driver_code: scoring.driver,
        scale_code: scaleCode,
        remarks: scoreRemarks,
      });
      setScoring(null); setScoreRemarks('');
      await reload();
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
  };

  const createGoal = async () => {
    if (!adding) return;
    if (!newGoal.title?.trim()) { showAlert('Title required'); return; }
    if (adding.level === 'L3' && !newGoal.division_code) { showAlert('Division required', 'L3 goals must be linked to one of the 7 Divisions.'); return; }
    const payload = {
      user_org_id: orgId,
      level: adding.level,
      parent_goal_id: adding.parent_goal_id,
      title: newGoal.title,
      description: newGoal.description || '',
      metric_label: newGoal.metric_label || '',
      metric_target: newGoal.metric_target || '',
      metric_unit: newGoal.metric_unit || '',
      target_date: ddmmToIso(newGoal.target_date) || newGoal.target_date || null,
      owner_name: newGoal.owner_name || '',
      division_code: newGoal.division_code || null,
      goal_setter_id: newGoal.goal_setter_id || null,
      status: newGoal.status || 'pending',
    };
    try {
      if (editingGoalId) {
        await api.put(`/six-legs/goals/${editingGoalId}`, payload);
      } else {
        await api.post('/six-legs/goals', payload);
      }
      setAdding(null); setNewGoal({}); setEditingGoalId(null);
      await reload();
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
  };

  const deleteGoal = async (gid: string) => {
    if (!confirm('Delete this goal and all its children?')) return;
    try { await api.delete(`/six-legs/goals/${gid}`); await reload(); }
    catch(e:any){ showAlert('Delete failed', e?.response?.data?.detail || e.message); }
  };

  const convertToAction = async (gid: string, recurring: boolean) => {
    try {
      await api.post(`/six-legs/goals/${gid}/convert-to-action`, { recurrence_type: recurring ? 'recurring' : 'one_time', recurrence_frequency: recurring ? 'weekly' : null, priority: 'medium' });
      showAlert('Converted', `Goal pushed to Action Tracker as ${recurring ? 'a recurring routine' : 'a one-time task'}.`);
    } catch(e:any){ showAlert('Convert failed', e?.response?.data?.detail || e.message); }
  };

  const findScale = (sc?: string) => scale.find(x => x.code === sc);

  const renderNode = (node: any, depth: number) => {
    const lvl = node.level || 'L1';
    const isOpen = expanded[node.id] !== false;
    const childCount = node.children?.length || 0;
    return (
      <View key={node.id} style={[s.goalNode, { marginLeft: depth * 14 }]}>
        <View style={s.goalRow}>
          <TouchableOpacity onPress={() => setExpanded(e => ({ ...e, [node.id]: !isOpen }))} disabled={childCount === 0}>
            <Ionicons name={isOpen ? 'chevron-down' : 'chevron-forward'} size={14} color={childCount ? '#475569' : '#CBD5E1'} />
          </TouchableOpacity>
          <View style={[s.levelPip, { backgroundColor: LEVEL_INFO[lvl]?.color || '#64748B' }]}><Text style={s.levelPipText}>{lvl}</Text></View>
          <View style={{ flex: 1 }}>
            <Text style={s.goalTitle}>{node.title}</Text>
            {node.metric_label ? <Text style={s.goalMeta}>{node.metric_label}: {node.metric_target} {node.metric_unit}</Text> : null}
            {node.owner_name ? <Text style={s.goalMeta}>Owner: {node.owner_name}{node.target_date ? ` · by ${isoToDdmm(node.target_date)}` : ''}</Text> : null}
          </View>
          {lvl === 'L1' && (
            <TouchableOpacity style={s.goalAct} onPress={() => router.push(`/tools/financial-model?org=${orgId}&goal=${node.id}` as any)} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }} accessibilityLabel="Open Financial Model" testID={`fm-open-${node.id}`} {...({ title: 'Open Financial Model (forecasts, ratios, DCF)' } as any)}><Ionicons name="calculator" size={16} color="#003087" /></TouchableOpacity>
          )}
          <TouchableOpacity style={s.goalAct} onPress={() => convertToAction(node.id, false)} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }} accessibilityLabel="Mark as done (one-time)" {...({ title: 'Mark as done — convert to one-time Action Tracker task' } as any)}><Ionicons name="checkmark-circle" size={16} color="#10B981" /></TouchableOpacity>
          <TouchableOpacity style={s.goalAct} onPress={() => convertToAction(node.id, true)} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }} accessibilityLabel="Convert to recurring routine" {...({ title: 'Convert to recurring routine in Action Tracker' } as any)}><Ionicons name="repeat" size={16} color="#8B5CF6" /></TouchableOpacity>
          <TouchableOpacity style={s.goalAct} onPress={() => { setEditingGoalId(node.id); setAdding({ level: lvl as any, parent_goal_id: node.parent_goal_id || null }); setNewGoal({ ...node, target_date: node.target_date ? isoToDdmm(node.target_date) : '' }); }} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }} accessibilityLabel="Edit goal" {...({ title: 'Edit this goal' } as any)}><Ionicons name="create" size={16} color="#F59E0B" /></TouchableOpacity>
          {lvl !== 'L6' && (
            <TouchableOpacity style={s.goalAct} onPress={() => { const nextLvl = LEVEL_ORDER[LEVEL_ORDER.indexOf(lvl as any) + 1] || 'L6'; setEditingGoalId(null); setAdding({ level: nextLvl, parent_goal_id: node.id }); setNewGoal({}); }} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }} accessibilityLabel="Add sub-goal" {...({ title: `Add a sub-goal under ${lvl}` } as any)}><Ionicons name="add-circle" size={16} color="#003087" /></TouchableOpacity>
          )}
          <TouchableOpacity style={s.goalAct} onPress={() => deleteGoal(node.id)} hitSlop={{ top: 8, right: 8, bottom: 8, left: 8 }} accessibilityLabel="Delete goal" {...({ title: 'Delete this goal and all its children' } as any)}><Ionicons name="trash" size={14} color="#EF4444" /></TouchableOpacity>
        </View>
        {isOpen && (node.children || []).map((c: any) => renderNode(c, depth + 1))}
      </View>
    );
  };

  if (busy && !org) return <SafeAreaView style={s.wrap}><ActivityIndicator style={{ marginTop: 80 }} /></SafeAreaView>;
  if (!org) return <SafeAreaView style={s.wrap}><Text style={{ padding: 20 }}>Org not found</Text></SafeAreaView>;

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={[s.header, { backgroundColor: org.color || '#003087' }]}>
        <TouchableOpacity onPress={() => { try { safeBack(router); } catch {} router.replace('/(tabs)' as any); }} style={s.backBtn} accessibilityLabel="Back to dashboard" {...({ title: 'Back to dashboard' } as any)}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.title}>{org.name}</Text>
        <Text style={s.subtitle}>{org.org_type} · {org.life_area}{org.sub_area ? ` / ${org.sub_area}` : ''}</Text>
      </View>
      <View style={s.tabs}>
        <TouchableOpacity style={[s.tab, tab==='matrix' && s.tabActive]} onPress={() => setTab('matrix')}><Text style={[s.tabText, tab==='matrix' && s.tabTextActive]}>7×7 MATRIX</Text></TouchableOpacity>
        <TouchableOpacity style={[s.tab, tab==='goals' && s.tabActive]} onPress={() => setTab('goals')}><Text style={[s.tabText, tab==='goals' && s.tabTextActive]}>6 LeGs GOALS</Text></TouchableOpacity>
      </View>

      {tab === 'matrix' && (
        <ScrollView contentContainerStyle={{ padding: 12 }}>
          {due?.due_now && (
            <View style={s.dueBanner}>
              <Ionicons name="alert-circle" size={16} color="#F59E0B" />
              <Text style={s.dueText}>Fortnightly re-assessment is DUE{due.days_since_last ? ` (last: ${due.days_since_last}d ago)` : ''}.</Text>
            </View>
          )}
          {divisions.map((d) => (
            <View key={d.code} style={s.divCard}>
              <View style={[s.divHead, { backgroundColor: d.color }]}>
                <Ionicons name={(d.icon || 'folder') as any} size={16} color="#FFF" />
                <Text style={s.divName}>{d.order}. {d.name}</Text>
                <Text style={s.divDept}>{d.department}</Text>
              </View>
              <View style={s.driversWrap}>
                {drivers.map((dr) => {
                  const cell = matrix[`${d.code}|${dr.code}`];
                  const sc = cell ? findScale(cell.scale_code) : null;
                  return (
                    <TouchableOpacity key={dr.code} style={[s.cell, { borderColor: sc?.color || '#CBD5E1', backgroundColor: sc ? `${sc.color}15` : '#FFF' }]} onPress={() => { setScoring({ division: d.code, driver: dr.code }); setScoreRemarks(cell?.remarks || ''); }}>
                      <Text style={s.cellCat}>{dr.category?.toUpperCase()}</Text>
                      <Text style={s.cellName}>{dr.name}</Text>
                      {sc ? <View style={[s.cellPill, { backgroundColor: sc.color }]}><Text style={s.cellPillText}>{sc.name}</Text></View> : <Text style={s.cellEmpty}>tap to score</Text>}
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>
          ))}
        </ScrollView>
      )}

      {tab === 'goals' && (
        <ScrollView contentContainerStyle={{ padding: 12 }}>
          <Text style={s.gateBanner}>6 LeGs is gated to this Org — all goals belong to {org.name}.</Text>
          {/* New L1 root button */}
          <TouchableOpacity style={s.addRootBtn} onPress={() => { setAdding({ level: 'L1', parent_goal_id: null }); setNewGoal({}); }}>
            <Ionicons name="add-circle" size={18} color="#FFF" /><Text style={s.addRootText}>  New L1 Financial Goal</Text>
          </TouchableOpacity>
          <TouchableOpacity style={s.fmBtn} onPress={() => router.push(`/tools/financial-model?org=${orgId}` as any)} testID="open-financial-model">
            <Ionicons name="calculator" size={18} color="#003087" /><Text style={s.fmBtnText}>  Financial Model — forecasts · ratios · DCF valuation</Text>
          </TouchableOpacity>
          {tree.length === 0 && <Text style={s.emptyTree}>No goals yet. Start with an L1 Financial goal, then drill down through the 6 levels.</Text>}
          {tree.map((node: any) => renderNode(node, 0))}
          <View style={s.legendCard}>
            <Text style={s.legendTitle}>Level Guide</Text>
            {LEVEL_ORDER.map(l => (
              <View key={l} style={s.legendRow}>
                <View style={[s.legendPip, { backgroundColor: LEVEL_INFO[l].color }]} />
                <View style={{ flex: 1 }}>
                  <Text style={s.legendName}>{LEVEL_INFO[l].label}</Text>
                  <Text style={s.legendHint}>{LEVEL_INFO[l].hint}</Text>
                </View>
              </View>
            ))}
          </View>
        </ScrollView>
      )}

      {scoring && (
        <View style={s.overlay}>
          <View style={s.modal}>
            <Text style={s.modalTitle}>Score · {divisions.find(d => d.code === scoring.division)?.name}</Text>
            <Text style={s.modalSub}>Driver: {drivers.find(d => d.code === scoring.driver)?.name}</Text>
            {scale.map(sc => (
              <TouchableOpacity key={sc.code} style={[s.scaleBtn, { backgroundColor: sc.color }]} onPress={() => submitScore(sc.code)}>
                <Text style={s.scaleBtnText}>{sc.name}</Text>
              </TouchableOpacity>
            ))}
            <Text style={s.lbl}>Remarks (optional)</Text>
            <TextInput style={[s.inp, { minHeight: 60, textAlignVertical: 'top' }]} multiline value={scoreRemarks} onChangeText={setScoreRemarks} placeholder="e.g. Need 2 more senior devs..." placeholderTextColor="#94A3B8" />
            <TouchableOpacity style={s.cancelBtn} onPress={() => { setScoring(null); setScoreRemarks(''); }}><Text style={s.cancelText}>Close</Text></TouchableOpacity>
          </View>
        </View>
      )}

      {adding && (
        <View style={s.overlay}>
          <View style={s.modal}>
            <Text style={s.modalTitle}>New {LEVEL_INFO[adding.level].label}</Text>
            <ScrollView style={{ maxHeight: 400 }}>
              <Text style={s.lbl}>Title *</Text>
              <TextInput style={s.inp} value={newGoal.title||''} onChangeText={(v) => setNewGoal((p:any)=>({...p,title:v}))} placeholder="Goal title" placeholderTextColor="#94A3B8" />
              <Text style={s.lbl}>Description</Text>
              <TextInput style={[s.inp, { minHeight: 60, textAlignVertical: 'top' }]} multiline value={newGoal.description||''} onChangeText={(v) => setNewGoal((p:any)=>({...p,description:v}))} placeholder="..." placeholderTextColor="#94A3B8" />
              {adding.level === 'L3' && (<>
                <Text style={s.lbl}>Division (required for L3)</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  {divisions.map(d => <TouchableOpacity key={d.code} style={[s.chip, newGoal.division_code===d.code && { backgroundColor: d.color, borderColor: d.color }]} onPress={() => setNewGoal((p:any)=>({...p, division_code: d.code}))}><Text style={[s.chipText, newGoal.division_code===d.code && { color: '#FFF' }]}>{d.name}</Text></TouchableOpacity>)}
                </ScrollView>
              </>)}
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <View style={{ flex: 1 }}><Text style={s.lbl}>Metric</Text><TextInput style={s.inp} value={newGoal.metric_label||''} onChangeText={(v) => setNewGoal((p:any)=>({...p, metric_label: v}))} placeholder="Revenue" placeholderTextColor="#94A3B8" /></View>
                <View style={{ flex: 1 }}><Text style={s.lbl}>Target</Text><TextInput style={s.inp} value={newGoal.metric_target||''} onChangeText={(v) => setNewGoal((p:any)=>({...p, metric_target: v}))} placeholder="10" placeholderTextColor="#94A3B8" /></View>
                <View style={{ flex: 1 }}><Text style={s.lbl}>Unit</Text><TextInput style={s.inp} value={newGoal.metric_unit||''} onChangeText={(v) => setNewGoal((p:any)=>({...p, metric_unit: v}))} placeholder="Cr" placeholderTextColor="#94A3B8" /></View>
              </View>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <View style={{ flex: 1 }}><Text style={s.lbl}>Owner</Text><TextInput style={s.inp} value={newGoal.owner_name||''} onChangeText={(v) => setNewGoal((p:any)=>({...p, owner_name: v}))} placeholder="e.g. Chelz" placeholderTextColor="#94A3B8" /></View>
                <View style={{ flex: 1 }}><Text style={s.lbl}>Target Date</Text><TextInput style={s.inp} value={newGoal.target_date||''} onChangeText={(v) => setNewGoal((p:any)=>({...p, target_date: v}))} placeholder="DD-MM-YYYY" placeholderTextColor="#94A3B8" /></View>
              </View>
              {/* Linked Goal Setter — visible at all times so user can attach/detach */}
              <Text style={s.lbl}>Linked Goal Setter (optional)</Text>
              {(() => {
                const linked = smartGoals.find((g: any) => (g.goal_id || g.id) === newGoal.goal_setter_id);
                if (linked) return (
                  <View style={[s.linkRow, s.linkRowOn]}>
                    <Ionicons name="link" size={14} color="#003087" />
                    <View style={{ flex: 1 }}>
                      <Text style={s.linkText} numberOfLines={1}>{linked.title}</Text>
                      <Text style={s.linkMeta}>{linked.life_area || '—'}{linked.goal_type ? ` · ${linked.goal_type}` : ''}</Text>
                    </View>
                    <TouchableOpacity onPress={() => setNewGoal((p:any) => ({ ...p, goal_setter_id: null }))} accessibilityLabel="Unlink Goal Setter entry" {...({ title: 'Detach SMART goal' } as any)}>
                      <Ionicons name="close-circle" size={16} color="#EF4444" />
                    </TouchableOpacity>
                  </View>
                );
                return (
                  <ScrollView style={{ maxHeight: 120 }} nestedScrollEnabled>
                    {smartGoals.length === 0 ? <Text style={s.linkEmpty}>No SMART goals available — create one in Goal Setter first.</Text>
                    : smartGoals.map((g: any) => {
                      const gid = g.goal_id || g.id;
                      return (
                        <TouchableOpacity key={gid} style={s.linkRow} onPress={() => setNewGoal((p:any) => ({ ...p, goal_setter_id: gid }))}>
                          <Ionicons name="radio-button-off" size={14} color="#94A3B8" />
                          <Text style={s.linkText} numberOfLines={1}>{g.title}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </ScrollView>
                );
              })()}
            </ScrollView>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
              <TouchableOpacity style={s.cancelBtn} onPress={() => { setAdding(null); setNewGoal({}); setEditingGoalId(null); }}><Text style={s.cancelText}>Cancel</Text></TouchableOpacity>
              <TouchableOpacity style={s.saveBtn} onPress={createGoal}><Text style={s.saveText}>{editingGoalId ? 'Save' : 'Create'}</Text></TouchableOpacity>
            </View>
          </View>
        </View>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { padding: 16, backgroundColor: '#003087' },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  title: { color: '#FFF', fontSize: 20, fontWeight: '800' },
  subtitle: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  tabs: { flexDirection: 'row', backgroundColor: '#FFF', borderBottomWidth: 1, borderColor: '#E2E8F0' },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderColor: '#003087' },
  tabText: { fontSize: 12, fontWeight: '700', color: '#64748B' },
  tabTextActive: { color: '#003087', fontWeight: '800' },
  dueBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FEF3C7', padding: 10, borderRadius: 8, marginBottom: 10 },
  dueText: { color: '#92400E', fontSize: 12, fontWeight: '700' },
  divCard: { backgroundColor: '#FFF', borderRadius: 10, marginBottom: 10, borderWidth: 1, borderColor: '#E2E8F0', overflow: 'hidden' },
  divHead: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 10 },
  divName: { color: '#FFF', fontWeight: '800', fontSize: 13, flex: 1 },
  divDept: { color: 'rgba(255,255,255,0.85)', fontSize: 10 },
  driversWrap: { flexDirection: 'row', flexWrap: 'wrap', padding: 6, gap: 6 },
  cell: { flexBasis: '23.5%', flexGrow: 1, minWidth: 110, padding: 8, borderRadius: 8, borderWidth: 1.5, backgroundColor: '#FFF' },
  cellCat: { fontSize: 9, fontWeight: '800', color: '#94A3B8' },
  cellName: { fontSize: 12, fontWeight: '700', color: '#0F172A', marginTop: 2 },
  cellPill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, alignSelf: 'flex-start', marginTop: 6 },
  cellPillText: { color: '#FFF', fontSize: 9, fontWeight: '800' },
  cellEmpty: { fontSize: 10, color: '#94A3B8', marginTop: 6, fontStyle: 'italic' },
  linkRow: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8, borderRadius: 6, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 4, backgroundColor: '#FFF' },
  linkRowOn: { borderColor: '#003087', backgroundColor: '#EEF2FF' },
  linkText: { fontSize: 12, color: '#0F172A', fontWeight: '600' },
  linkMeta: { fontSize: 10, color: '#64748B', marginTop: 1 },
  linkEmpty: { fontSize: 11, color: '#94A3B8', fontStyle: 'italic', padding: 8 },
  gateBanner: { backgroundColor: '#EEF2FF', color: '#4338CA', padding: 10, borderRadius: 8, fontSize: 11, marginBottom: 10 },
  addRootBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#DC2626', borderRadius: 10, padding: 10, marginBottom: 10 },
  addRootText: { color: '#FFF', fontWeight: '800', fontSize: 13 },
  fmBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#003087', borderRadius: 10, padding: 10, marginBottom: 10 },
  fmBtnText: { color: '#003087', fontWeight: '800', fontSize: 12 },
  emptyTree: { textAlign: 'center', color: '#64748B', fontSize: 12, padding: 20, fontStyle: 'italic' },
  goalNode: { marginBottom: 4 },
  goalRow: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#FFF', padding: 8, borderRadius: 8, borderWidth: 1, borderColor: '#E2E8F0' },
  levelPip: { paddingHorizontal: 5, paddingVertical: 2, borderRadius: 5 },
  levelPipText: { color: '#FFF', fontSize: 9, fontWeight: '800' },
  goalTitle: { fontSize: 12, fontWeight: '700', color: '#0F172A' },
  goalMeta: { fontSize: 10, color: '#64748B', marginTop: 1 },
  goalAct: { padding: 4 },
  legendCard: { backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginTop: 16, borderWidth: 1, borderColor: '#E2E8F0' },
  legendTitle: { fontSize: 12, fontWeight: '800', color: '#003087', marginBottom: 6 },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 },
  legendPip: { width: 12, height: 12, borderRadius: 6 },
  legendName: { fontSize: 11, fontWeight: '700', color: '#0F172A' },
  legendHint: { fontSize: 10, color: '#64748B' },
  overlay: { position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 20 },
  modal: { backgroundColor: '#FFF', borderRadius: 12, padding: 16, maxHeight: '85%' },
  modalTitle: { fontSize: 14, fontWeight: '800', color: '#0F172A' },
  modalSub: { fontSize: 12, color: '#64748B', marginTop: 2, marginBottom: 12 },
  scaleBtn: { padding: 12, borderRadius: 8, marginBottom: 6 },
  scaleBtnText: { color: '#FFF', fontWeight: '800', textAlign: 'center' },
  lbl: { fontSize: 11, fontWeight: '700', color: '#475569', marginTop: 8, marginBottom: 4 },
  inp: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 10, fontSize: 13, color: '#0F172A' },
  chip: { paddingHorizontal: 8, paddingVertical: 5, borderRadius: 6, borderWidth: 1, borderColor: '#CBD5E1', marginRight: 5, backgroundColor: '#F8FAFC' },
  chipText: { fontSize: 10, fontWeight: '700', color: '#475569' },
  cancelBtn: { flex: 1, padding: 12, borderRadius: 8, backgroundColor: '#E2E8F0', alignItems: 'center' },
  cancelText: { color: '#475569', fontWeight: '700' },
  saveBtn: { flex: 2, padding: 12, borderRadius: 8, backgroundColor: '#003087', alignItems: 'center' },
  saveText: { color: '#FFF', fontWeight: '700' },
});
