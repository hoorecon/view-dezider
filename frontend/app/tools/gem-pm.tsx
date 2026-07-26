/**
 * GEM PM Workspace — full project-management layer on a GEM Goal.
 * Tabs: WBS tree · Gantt · Kanban board · Calendar · Registers (Risks/Issues/Changes)
 * WBS: Goal → Milestones → Deliverables → Work Packages → Task (CTT/Routine) → Subtask (recursive)
 */
import React, { useState, useCallback, useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, Platform, KeyboardAvoidingView,
} from 'react-native';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';
import { ACTION_STATUS_OPTS, statusColor, statusLabel } from '../../src/constants/actionStatus';

type PMNode = {
  node_id: string; parent_id: string | null; node_type: string;
  title: string; description: string; status: string; kanban_col: string;
  progress_pct: number; task_kind?: string | null; linked_action_id?: string | null;
  assignments: { owner: string; co_owner: string; reviewer: string; approver: string; watchers: string[] };
  est_start?: string | null; est_finish?: string | null; est_hours: number;
  actual_start?: string | null; actual_finish?: string | null; actual_hours: number;
  computed: { rollup_progress: number; delayed: boolean; critical: boolean; es: number; ef: number; duration: number; slack: number; variance_hours: number };
};
type PMDep = { dep_id: string; predecessor_id: string; successor_id: string; dep_type: string; lag_days: number };

const TYPE_META: Record<string, { label: string; icon: any; color: string }> = {
  milestone:    { label: 'Milestone',    icon: 'flag',       color: '#8B5CF6' },
  deliverable:  { label: 'Deliverable',  icon: 'cube',       color: '#0EA5E9' },
  work_package: { label: 'Work Package', icon: 'briefcase',  color: '#F59E0B' },
  task:         { label: 'Task',         icon: 'construct',  color: '#10B981' },
  subtask:      { label: 'Subtask',      icon: 'git-branch', color: '#64748B' },
};
const ALLOWED_CHILDREN: Record<string, string[]> = {
  root: ['milestone', 'task'], milestone: ['deliverable', 'task'],
  deliverable: ['work_package', 'task'], work_package: ['task'],
  task: ['subtask'], subtask: ['subtask'],
};
const KANBAN_COLS = [
  { id: 'backlog', label: 'Backlog', color: '#94A3B8' },
  { id: 'todo', label: 'To Do', color: '#3B82F6' },
  { id: 'in_progress', label: 'In Progress', color: '#F59E0B' },
  { id: 'review', label: 'Review', color: '#8B5CF6' },
  { id: 'done', label: 'Done', color: '#10B981' },
];
const DEP_TYPES = ['FS', 'SS', 'FF', 'SF'];
const TABS = [
  { id: 'wbs', label: 'WBS', icon: 'git-network' },
  { id: 'gantt', label: 'Gantt', icon: 'stats-chart' },
  { id: 'board', label: 'Board', icon: 'grid' },
  { id: 'calendar', label: 'Calendar', icon: 'calendar' },
  { id: 'registers', label: 'Registers', icon: 'warning' },
];
const REG_KINDS = [
  { id: 'risk', label: 'Risks', icon: 'alert-circle', color: '#F59E0B' },
  { id: 'issue', label: 'Issues', icon: 'flame', color: '#EF4444' },
  { id: 'change', label: 'Change Log', icon: 'swap-vertical', color: '#3B82F6' },
];
const LEVELS = ['low', 'medium', 'high'];

const addDays = (iso: string, n: number) => {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + n);
  return d;
};
const fmtShort = (d: Date) => `${d.getUTCDate()}/${d.getUTCMonth() + 1}`;

export default function GemPMScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ goalId?: string }>();
  const [goalId, setGoalId] = useState<string>(String(params?.goalId || ''));
  const [gemGoals, setGemGoals] = useState<any[]>([]);
  const [ws, setWs] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('wbs');
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  // node add/edit modal
  const [modal, setModal] = useState<null | { mode: 'add' | 'edit'; parent?: PMNode | null; node?: PMNode }>(null);
  const [saving, setSaving] = useState(false);
  const [f, setF] = useState<any>({});
  // dependency add state (inside edit modal)
  const [depPredId, setDepPredId] = useState('');
  const [depType, setDepType] = useState('FS');
  const [depLag, setDepLag] = useState('0');
  const [depPickerOpen, setDepPickerOpen] = useState(false);
  // registers
  const [regKind, setRegKind] = useState('risk');
  const [regs, setRegs] = useState<any[]>([]);
  const [regModal, setRegModal] = useState<null | { mode: 'add' | 'edit'; reg?: any }>(null);
  const [rf, setRf] = useState<any>({});
  // calendar
  const [calMonth, setCalMonth] = useState(() => { const d = new Date(); return { y: d.getFullYear(), m: d.getMonth() }; });
  const [calSelected, setCalSelected] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (!goalId) {
        const r = await api.get('/gem/goals');
        setGemGoals(r.data || []);
      } else {
        const r = await api.get(`/gem-pm/${goalId}/workspace`);
        setWs(r.data);
      }
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load PM workspace');
    } finally { setLoading(false); }
  }, [goalId]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const loadRegs = useCallback(async (kind: string) => {
    try {
      const r = await api.get(`/gem-pm/${goalId}/registers?kind=${kind}`);
      setRegs(r.data || []);
    } catch { /* noop */ }
  }, [goalId]);

  const nodes: PMNode[] = ws?.nodes || [];
  const deps: PMDep[] = ws?.deps || [];
  const byId = useMemo(() => Object.fromEntries(nodes.map(n => [n.node_id, n])), [nodes]);
  const childrenMap = useMemo(() => {
    const m: Record<string, PMNode[]> = {};
    nodes.forEach(n => { const k = n.parent_id || 'root'; (m[k] = m[k] || []).push(n); });
    return m;
  }, [nodes]);

  // ── node modal helpers ──
  const openAdd = (parent: PMNode | null) => {
    const pType = parent ? parent.node_type : 'root';
    const types = ALLOWED_CHILDREN[pType] || [];
    setF({
      node_type: types[0], title: '', description: '', status: 'pending',
      est_start: '', est_finish: '', est_hours: '', actual_start: '', actual_finish: '', actual_hours: '',
      owner: '', co_owner: '', reviewer: '', approver: '', watchers: '',
    });
    setModal({ mode: 'add', parent });
  };
  const openEdit = (n: PMNode) => {
    setF({
      node_type: n.node_type, title: n.title, description: n.description || '', status: n.status,
      est_start: n.est_start || '', est_finish: n.est_finish || '', est_hours: n.est_hours ? String(n.est_hours) : '',
      actual_start: n.actual_start || '', actual_finish: n.actual_finish || '', actual_hours: n.actual_hours ? String(n.actual_hours) : '',
      owner: n.assignments?.owner || '', co_owner: n.assignments?.co_owner || '',
      reviewer: n.assignments?.reviewer || '', approver: n.assignments?.approver || '',
      watchers: (n.assignments?.watchers || []).join(', '),
    });
    setDepPredId(''); setDepType('FS'); setDepLag('0'); setDepPickerOpen(false);
    setModal({ mode: 'edit', node: n });
  };

  const saveNode = async () => {
    if (!f.title?.trim()) { showAlert('Required', 'Title is required'); return; }
    setSaving(true);
    const payload = {
      title: f.title.trim(), description: f.description, status: f.status,
      node_type: f.node_type,
      est_start: f.est_start || null, est_finish: f.est_finish || null,
      est_hours: parseFloat(f.est_hours) || 0,
      actual_start: f.actual_start || null, actual_finish: f.actual_finish || null,
      actual_hours: parseFloat(f.actual_hours) || 0,
      assignments: {
        owner: f.owner, co_owner: f.co_owner, reviewer: f.reviewer, approver: f.approver,
        watchers: String(f.watchers || '').split(',').map((x: string) => x.trim()).filter(Boolean),
      },
    };
    try {
      if (modal?.mode === 'add') {
        await api.post(`/gem-pm/${goalId}/nodes`, { ...payload, parent_id: modal.parent?.node_id || null });
      } else if (modal?.node) {
        await api.put(`/gem-pm/nodes/${modal.node.node_id}`, payload);
      }
      setModal(null); load();
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed to save'); }
    finally { setSaving(false); }
  };

  const deleteNode = (n: PMNode) => {
    showAlert('Delete node?', 'This removes the node and its entire subtree (plus its dependencies).', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/gem-pm/nodes/${n.node_id}`); setModal(null); load(); }
        catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
      } },
    ]);
  };

  const portNode = async (n: PMNode, target: 'CTT' | 'LIFESTYLE') => {
    try {
      await api.post(`/gem-pm/nodes/${n.node_id}/port`, { target });
      showAlert('Ported', `Task added to ${target === 'CTT' ? 'CTT' : 'LifeStyle'} & tracked in Action Center.`);
      setModal(null); load();
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  const addDep = async () => {
    if (!depPredId || !modal?.node) { showAlert('Required', 'Pick a predecessor node'); return; }
    try {
      await api.post(`/gem-pm/${goalId}/deps`, {
        predecessor_id: depPredId, successor_id: modal.node.node_id,
        dep_type: depType, lag_days: parseInt(depLag) || 0,
      });
      setDepPredId(''); load();
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };
  const removeDep = async (depId: string) => {
    try { await api.delete(`/gem-pm/deps/${depId}`); load(); }
    catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  const moveKanban = async (n: PMNode, dir: -1 | 1) => {
    const idx = KANBAN_COLS.findIndex(c => c.id === (n.kanban_col || 'todo'));
    const next = KANBAN_COLS[idx + dir];
    if (!next) return;
    try { await api.put(`/gem-pm/nodes/${n.node_id}/kanban`, { col: next.id }); load(); }
    catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  // ── register helpers ──
  const openRegAdd = () => { setRf({ title: '', description: '', owner: '', status: 'open', probability: 'medium', impact: 'medium', mitigation: '', severity: 'medium', resolution: '', change_type: 'scope', decision: '' }); setRegModal({ mode: 'add' }); };
  const openRegEdit = (r: any) => { setRf({ ...r }); setRegModal({ mode: 'edit', reg: r }); };
  const saveReg = async () => {
    if (!rf.title?.trim()) { showAlert('Required', 'Title is required'); return; }
    setSaving(true);
    try {
      if (regModal?.mode === 'add') await api.post(`/gem-pm/${goalId}/registers`, { ...rf, kind: regKind });
      else await api.put(`/gem-pm/registers/${regModal?.reg?.reg_id}`, rf);
      setRegModal(null); loadRegs(regKind); load();
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };
  const deleteReg = (r: any) => {
    showAlert('Delete entry?', 'Remove this register entry?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/gem-pm/registers/${r.reg_id}`); loadRegs(regKind); load(); } catch { /* noop */ }
      } },
    ]);
  };

  // ═══════════ RENDER: project picker ═══════════
  if (!goalId) {
    return (
      <SafeAreaView style={s.root} edges={['top']}>
        <LinearGradient colors={['#4F46E5', '#6366F1']} style={s.hdr}>
          <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.hdrT}>GEM Projects</Text>
            <Text style={s.hdrS}>Pick a GEM goal to open its PM workspace</Text>
          </View>
        </LinearGradient>
        <ScrollView contentContainerStyle={{ padding: 16 }}>
          {loading ? <ActivityIndicator size="large" color="#4F46E5" style={{ marginTop: 40 }} /> :
            gemGoals.length === 0 ? (
              <View style={s.emptyBox}>
                <Ionicons name="diamond-outline" size={48} color="#CBD5E1" />
                <Text style={s.emptyText}>No GEM goals yet. Create one in GEM first.</Text>
              </View>
            ) : gemGoals.map(g => (
              <TouchableOpacity key={g.goal_id} style={s.pickCard} onPress={() => setGoalId(g.goal_id)}>
                <Ionicons name="git-network" size={20} color="#4F46E5" />
                <View style={{ flex: 1 }}>
                  <Text style={s.pickTitle} numberOfLines={1}>{g.title || 'Untitled'}</Text>
                  <Text style={s.pickSub}>{g.status || 'active'} · {g.progress_percent || 0}%</Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color="#94A3B8" />
              </TouchableOpacity>
            ))}
        </ScrollView>
      </SafeAreaView>
    );
  }

  // ═══════════ WBS tree ═══════════
  const renderTree = (parentKey: string, depth: number): React.ReactNode =>
    (childrenMap[parentKey] || []).map(n => {
      const meta = TYPE_META[n.node_type] || TYPE_META.task;
      const kids = childrenMap[n.node_id] || [];
      const isCollapsed = collapsed[n.node_id];
      const canAdd = (ALLOWED_CHILDREN[n.node_type] || []).length > 0;
      return (
        <View key={n.node_id}>
          <View style={[s.wbsRow, { marginLeft: depth * 14 }, n.computed.critical && s.wbsCritical]}>
            <TouchableOpacity
              onPress={() => setCollapsed(c => ({ ...c, [n.node_id]: !c[n.node_id] }))}
              style={{ width: 20, alignItems: 'center' }} disabled={kids.length === 0}>
              {kids.length > 0
                ? <Ionicons name={isCollapsed ? 'chevron-forward' : 'chevron-down'} size={13} color="#64748B" />
                : <View style={{ width: 4, height: 4, borderRadius: 2, backgroundColor: '#CBD5E1' }} />}
            </TouchableOpacity>
            <Ionicons name={meta.icon} size={14} color={meta.color} />
            <TouchableOpacity style={{ flex: 1 }} onPress={() => openEdit(n)}>
              <Text style={s.wbsTitle} numberOfLines={1}>{n.title}</Text>
              <View style={s.wbsMetaRow}>
                <Text style={[s.wbsType, { color: meta.color }]}>{meta.label}</Text>
                {!!n.assignments?.owner && <Text style={s.wbsMeta}>👤 {n.assignments.owner}</Text>}
                {!!n.est_finish && <Text style={s.wbsMeta}>📅 {n.est_finish}</Text>}
                {n.computed.critical && <Text style={s.critBadge}>⚡ critical</Text>}
                {n.computed.delayed && <Text style={s.delayBadge}>⏰ delayed</Text>}
                {!!n.linked_action_id && <Text style={s.portBadge}>🔗 {n.task_kind === 'routine' ? 'LifeStyle' : 'CTT'}</Text>}
              </View>
            </TouchableOpacity>
            <View style={s.wbsProg}>
              <Text style={s.wbsProgText}>{Math.round(n.computed.rollup_progress)}%</Text>
              <View style={s.wbsProgBar}><View style={[s.wbsProgFill, { width: `${n.computed.rollup_progress}%` }]} /></View>
            </View>
            <View style={[s.stChip, { backgroundColor: statusColor(n.status) + '22' }]}>
              <Text style={[s.stChipT, { color: statusColor(n.status) }]}>{statusLabel(n.status)}</Text>
            </View>
            {canAdd && (
              <TouchableOpacity onPress={() => openAdd(n)} style={s.addChildBtn}>
                <Ionicons name="add" size={14} color="#4F46E5" />
              </TouchableOpacity>
            )}
          </View>
          {!isCollapsed && renderTree(n.node_id, depth + 1)}
        </View>
      );
    });

  // ═══════════ Gantt ═══════════
  const renderGantt = () => {
    if (nodes.length === 0) return <Text style={s.emptyText}>Add WBS nodes with estimated dates to see the Gantt chart.</Text>;
    const anchor = ws?.project?.anchor || new Date().toISOString().slice(0, 10);
    const total = Math.max(ws?.project?.duration_days || 1, 7);
    const dayW = 22;
    const flat: PMNode[] = [];
    const walk = (k: string) => (childrenMap[k] || []).forEach(n => { flat.push(n); walk(n.node_id); });
    walk('root');
    const todayOff = Math.round((Date.now() - new Date(anchor + 'T00:00:00Z').getTime()) / 86400000);
    const ticks = [];
    for (let i = 0; i <= total; i += 7) ticks.push(i);
    return (
      <View>
        <ScrollView horizontal showsHorizontalScrollIndicator>
          <View>
            {/* header ticks */}
            <View style={{ flexDirection: 'row', height: 24, marginLeft: 150 }}>
              {ticks.map(t => (
                <View key={t} style={{ position: 'absolute', left: t * dayW }}>
                  <Text style={s.ganttTick}>{fmtShort(addDays(anchor, t))}</Text>
                </View>
              ))}
            </View>
            {flat.map(n => {
              const c = n.computed;
              const barColor = c.critical ? '#EF4444' : c.delayed ? '#F59E0B' : (TYPE_META[n.node_type]?.color || '#10B981');
              return (
                <View key={n.node_id} style={s.ganttRow}>
                  <TouchableOpacity style={{ width: 150 }} onPress={() => openEdit(n)}>
                    <Text style={s.ganttLabel} numberOfLines={1}>{n.title}</Text>
                  </TouchableOpacity>
                  <View style={{ width: total * dayW + 20, height: 22, justifyContent: 'center' }}>
                    {todayOff >= 0 && todayOff <= total && (
                      <View style={[s.todayLine, { left: todayOff * dayW }]} />
                    )}
                    {n.node_type === 'milestone' ? (
                      <View style={[s.ganttDiamond, { left: c.ef * dayW - 6, borderBottomColor: barColor }]} />
                    ) : (
                      <View style={[s.ganttBar, { left: c.es * dayW, width: Math.max(c.duration * dayW, 8), backgroundColor: barColor }]}>
                        <View style={[s.ganttBarFill, { width: `${c.rollup_progress}%` }]} />
                      </View>
                    )}
                  </View>
                </View>
              );
            })}
          </View>
        </ScrollView>
        <View style={s.legendRow}>
          <View style={[s.legendDot, { backgroundColor: '#EF4444' }]} /><Text style={s.legendT}>Critical path</Text>
          <View style={[s.legendDot, { backgroundColor: '#F59E0B' }]} /><Text style={s.legendT}>Delayed</Text>
          <View style={[s.legendDot, { backgroundColor: '#DC2626', width: 2, height: 12, borderRadius: 0 }]} /><Text style={s.legendT}>Today</Text>
        </View>
        {deps.length > 0 && (
          <View style={{ marginTop: 10 }}>
            <Text style={s.secTitle}>Dependencies ({deps.length})</Text>
            {deps.map(d => (
              <View key={d.dep_id} style={s.depRow}>
                <Text style={s.depText} numberOfLines={1}>
                  {byId[d.predecessor_id]?.title || '?'} <Text style={{ fontWeight: '800', color: '#4F46E5' }}> —{d.dep_type}{d.lag_days ? `+${d.lag_days}d` : ''}→ </Text>{byId[d.successor_id]?.title || '?'}
                </Text>
                <TouchableOpacity onPress={() => removeDep(d.dep_id)}>
                  <Ionicons name="trash-outline" size={14} color="#EF4444" />
                </TouchableOpacity>
              </View>
            ))}
          </View>
        )}
      </View>
    );
  };

  // ═══════════ Kanban board ═══════════
  const renderBoard = () => {
    const cards = nodes.filter(n => n.node_type === 'task' || n.node_type === 'subtask');
    if (cards.length === 0) return <Text style={s.emptyText}>No tasks yet — add Task nodes in the WBS tab.</Text>;
    return (
      <ScrollView horizontal showsHorizontalScrollIndicator contentContainerStyle={{ gap: 10, paddingBottom: 20 }}>
        {KANBAN_COLS.map((col, ci) => {
          const colCards = cards.filter(c => (c.kanban_col || 'todo') === col.id);
          return (
            <View key={col.id} style={s.kanbanCol}>
              <View style={[s.kanbanHead, { borderTopColor: col.color }]}>
                <Text style={[s.kanbanHeadT, { color: col.color }]}>{col.label}</Text>
                <View style={[s.kanbanCount, { backgroundColor: col.color + '22' }]}>
                  <Text style={{ fontSize: 10, fontWeight: '800', color: col.color }}>{colCards.length}</Text>
                </View>
              </View>
              {colCards.map(c => (
                <View key={c.node_id} style={[s.kanbanCard, c.computed.critical && { borderColor: '#FECACA' }]}>
                  <TouchableOpacity onPress={() => openEdit(c)}>
                    <Text style={s.kanbanCardT} numberOfLines={2}>{c.title}</Text>
                    <View style={s.wbsMetaRow}>
                      {!!c.assignments?.owner && <Text style={s.wbsMeta}>👤 {c.assignments.owner}</Text>}
                      {!!c.est_finish && <Text style={s.wbsMeta}>📅 {c.est_finish}</Text>}
                      {c.computed.critical && <Text style={s.critBadge}>⚡</Text>}
                      {c.computed.delayed && <Text style={s.delayBadge}>⏰</Text>}
                    </View>
                  </TouchableOpacity>
                  <View style={s.kanbanMoveRow}>
                    <TouchableOpacity disabled={ci === 0} onPress={() => moveKanban(c, -1)} style={[s.moveBtn, ci === 0 && { opacity: 0.3 }]}>
                      <Ionicons name="chevron-back" size={14} color="#4F46E5" />
                    </TouchableOpacity>
                    <TouchableOpacity disabled={ci === KANBAN_COLS.length - 1} onPress={() => moveKanban(c, 1)} style={[s.moveBtn, ci === KANBAN_COLS.length - 1 && { opacity: 0.3 }]}>
                      <Ionicons name="chevron-forward" size={14} color="#4F46E5" />
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
            </View>
          );
        })}
      </ScrollView>
    );
  };

  // ═══════════ Calendar ═══════════
  const renderCalendar = () => {
    const { y, m } = calMonth;
    const first = new Date(Date.UTC(y, m, 1));
    const startDow = first.getUTCDay();
    const daysIn = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    const cells: (number | null)[] = [...Array(startDow).fill(null), ...Array.from({ length: daysIn }, (_, i) => i + 1)];
    while (cells.length % 7 !== 0) cells.push(null);
    const dstr = (d: number) => `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
    const eventsOn = (d: number) => nodes.filter(n => n.est_finish === dstr(d));
    const selEvents = calSelected ? nodes.filter(n => n.est_finish === calSelected) : [];
    return (
      <View>
        <View style={s.calHead}>
          <TouchableOpacity onPress={() => setCalMonth(({ y: yy, m: mm }) => mm === 0 ? { y: yy - 1, m: 11 } : { y: yy, m: mm - 1 })}>
            <Ionicons name="chevron-back" size={20} color="#4F46E5" />
          </TouchableOpacity>
          <Text style={s.calMonthT}>{first.toLocaleString('en', { month: 'long', timeZone: 'UTC' })} {y}</Text>
          <TouchableOpacity onPress={() => setCalMonth(({ y: yy, m: mm }) => mm === 11 ? { y: yy + 1, m: 0 } : { y: yy, m: mm + 1 })}>
            <Ionicons name="chevron-forward" size={20} color="#4F46E5" />
          </TouchableOpacity>
        </View>
        <View style={s.calGrid}>
          {['S', 'M', 'T', 'W', 'T', 'F', 'S'].map((d, i) => (
            <View key={i} style={s.calCell}><Text style={s.calDow}>{d}</Text></View>
          ))}
          {cells.map((d, i) => {
            const evs = d ? eventsOn(d) : [];
            const isSel = d && calSelected === dstr(d);
            return (
              <TouchableOpacity key={i} style={[s.calCell, isSel && s.calCellSel]} disabled={!d}
                onPress={() => d && setCalSelected(dstr(d))}>
                {d ? (
                  <>
                    <Text style={[s.calDay, isSel && { color: '#FFF' }]}>{d}</Text>
                    <View style={{ flexDirection: 'row', gap: 2 }}>
                      {evs.slice(0, 3).map(e => (
                        <View key={e.node_id} style={[s.calDot, { backgroundColor: TYPE_META[e.node_type]?.color || '#10B981' }]} />
                      ))}
                    </View>
                  </>
                ) : null}
              </TouchableOpacity>
            );
          })}
        </View>
        {calSelected && (
          <View style={{ marginTop: 10 }}>
            <Text style={s.secTitle}>Due on {calSelected} ({selEvents.length})</Text>
            {selEvents.length === 0 && <Text style={s.emptyText}>Nothing due this day.</Text>}
            {selEvents.map(n => (
              <TouchableOpacity key={n.node_id} style={s.depRow} onPress={() => openEdit(n)}>
                <Ionicons name={TYPE_META[n.node_type]?.icon || 'construct'} size={14} color={TYPE_META[n.node_type]?.color} />
                <Text style={[s.depText, { flex: 1 }]} numberOfLines={1}>{n.title}</Text>
                <Text style={[s.stChipT, { color: statusColor(n.status) }]}>{statusLabel(n.status)}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>
    );
  };

  // ═══════════ Registers ═══════════
  const renderRegisters = () => (
    <View>
      <View style={{ flexDirection: 'row', gap: 6, marginBottom: 10 }}>
        {REG_KINDS.map(k => (
          <TouchableOpacity key={k.id}
            style={[s.regKindChip, regKind === k.id && { backgroundColor: k.color, borderColor: k.color }]}
            onPress={() => { setRegKind(k.id); loadRegs(k.id); }}>
            <Ionicons name={k.icon as any} size={13} color={regKind === k.id ? '#FFF' : k.color} />
            <Text style={[s.regKindT, regKind === k.id && { color: '#FFF' }]}>{k.label} ({ws?.register_counts?.[k.id] || 0})</Text>
          </TouchableOpacity>
        ))}
      </View>
      <TouchableOpacity style={s.regAddBtn} onPress={openRegAdd}>
        <Ionicons name="add-circle" size={16} color="#4F46E5" />
        <Text style={s.regAddT}>Add {regKind === 'change' ? 'change entry' : regKind}</Text>
      </TouchableOpacity>
      {regs.length === 0 ? <Text style={s.emptyText}>No {regKind} entries yet.</Text> :
        regs.map(r => (
          <TouchableOpacity key={r.reg_id} style={s.regCard} onPress={() => openRegEdit(r)}>
            <View style={{ flex: 1 }}>
              <Text style={s.regTitle} numberOfLines={1}>{r.title}</Text>
              <View style={s.wbsMetaRow}>
                {!!r.owner && <Text style={s.wbsMeta}>👤 {r.owner}</Text>}
                <Text style={s.wbsMeta}>· {r.status}</Text>
                {regKind === 'risk' && <Text style={s.wbsMeta}>P:{r.probability} I:{r.impact}</Text>}
                {regKind === 'issue' && !!r.severity && <Text style={s.delayBadge}>{r.severity}</Text>}
                {regKind === 'change' && !!r.change_type && <Text style={s.wbsMeta}>{r.change_type}</Text>}
              </View>
            </View>
            <TouchableOpacity onPress={() => deleteReg(r)}>
              <Ionicons name="trash-outline" size={15} color="#EF4444" />
            </TouchableOpacity>
          </TouchableOpacity>
        ))}
    </View>
  );

  // ═══════════ MAIN RENDER ═══════════
  const project = ws?.project || {};
  const modalNode = modal?.node;
  const nodeDeps = modalNode ? deps.filter(d => d.successor_id === modalNode.node_id) : [];
  const allowedAddTypes = modal?.mode === 'add' ? (ALLOWED_CHILDREN[modal?.parent?.node_type || 'root'] || []) : [];
  const variance = (parseFloat(f.actual_hours) || 0) - (parseFloat(f.est_hours) || 0);

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <LinearGradient colors={['#4F46E5', '#6366F1']} style={s.hdr}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.hdrT} numberOfLines={1}>{ws?.goal?.title || 'PM Workspace'}</Text>
          <Text style={s.hdrS}>
            {project.total_nodes || 0} nodes · {Math.round(project.progress || 0)}% · {ws?.critical_path?.length || 0} critical · {project.delayed_count || 0} delayed
          </Text>
        </View>
      </LinearGradient>

      {/* Tabs */}
      <View style={s.tabsRow}>
        {TABS.map(t => (
          <TouchableOpacity key={t.id} style={[s.tabBtn, tab === t.id && s.tabBtnA]}
            onPress={() => { setTab(t.id); if (t.id === 'registers') loadRegs(regKind); }}>
            <Ionicons name={t.icon as any} size={14} color={tab === t.id ? '#4F46E5' : '#94A3B8'} />
            <Text style={[s.tabT, tab === t.id && { color: '#4F46E5' }]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? <ActivityIndicator size="large" color="#4F46E5" style={{ marginTop: 40 }} /> : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 14, paddingBottom: 60 }}>
          {tab === 'wbs' && (
            <View>
              <View style={{ flexDirection: 'row', gap: 8, marginBottom: 10 }}>
                <TouchableOpacity style={s.topAddBtn} onPress={() => openAdd(null)}>
                  <Ionicons name="add-circle" size={16} color="#FFF" />
                  <Text style={s.topAddT}>Add Milestone / Task</Text>
                </TouchableOpacity>
              </View>
              {nodes.length === 0
                ? <View style={s.emptyBox}>
                    <Ionicons name="git-network-outline" size={44} color="#CBD5E1" />
                    <Text style={s.emptyText}>Build your WBS: Goal → Milestones → Deliverables → Work Packages → Tasks → Subtasks</Text>
                  </View>
                : renderTree('root', 0)}
            </View>
          )}
          {tab === 'gantt' && renderGantt()}
          {tab === 'board' && renderBoard()}
          {tab === 'calendar' && renderCalendar()}
          {tab === 'registers' && renderRegisters()}
        </ScrollView>
      )}

      {/* ── Node add/edit modal ── */}
      <Modal visible={!!modal} transparent animationType="slide" onRequestClose={() => setModal(null)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={s.mOverlay}>
          <View style={s.mSheet}>
            <View style={s.mHead}>
              <Text style={s.mTitle}>{modal?.mode === 'add' ? `Add under ${modal?.parent?.title || 'Goal'}` : 'Edit node'}</Text>
              <TouchableOpacity onPress={() => setModal(null)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 520 }}>
              {modal?.mode === 'add' && (
                <>
                  <Text style={s.mLabel}>Type</Text>
                  <View style={s.mChips}>
                    {allowedAddTypes.map(t => (
                      <TouchableOpacity key={t} style={[s.mChip, f.node_type === t && { backgroundColor: TYPE_META[t].color, borderColor: TYPE_META[t].color }]}
                        onPress={() => setF((x: any) => ({ ...x, node_type: t }))}>
                        <Text style={[s.mChipT, f.node_type === t && { color: '#FFF' }]}>{TYPE_META[t].label}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </>
              )}
              <Text style={s.mLabel}>Title *</Text>
              <TextInput style={s.mInput} value={f.title} onChangeText={v => setF((x: any) => ({ ...x, title: v }))} placeholder="What needs to be done?" />
              <Text style={s.mLabel}>Description</Text>
              <TextInput style={[s.mInput, { minHeight: 50 }]} value={f.description} onChangeText={v => setF((x: any) => ({ ...x, description: v }))} multiline />

              {modal?.mode === 'edit' && (
                <>
                  <Text style={s.mLabel}>Status</Text>
                  <View style={s.mChips}>
                    {ACTION_STATUS_OPTS.map(o => (
                      <TouchableOpacity key={o.id} style={[s.mChip, f.status === o.id && { backgroundColor: o.color, borderColor: o.color }]}
                        onPress={() => setF((x: any) => ({ ...x, status: o.id }))}>
                        <Text style={[s.mChipT, f.status === o.id && { color: '#FFF' }]}>{o.label}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </>
              )}

              <Text style={s.mSec}>📅 Estimated vs Actual</Text>
              <View style={s.mRow2}>
                <View style={{ flex: 1 }}>
                  <Text style={s.mLabel}>Est. start</Text>
                  <TextInput style={s.mInput} value={f.est_start} onChangeText={v => setF((x: any) => ({ ...x, est_start: v }))} placeholder="YYYY-MM-DD" autoCapitalize="none" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.mLabel}>Est. finish</Text>
                  <TextInput style={s.mInput} value={f.est_finish} onChangeText={v => setF((x: any) => ({ ...x, est_finish: v }))} placeholder="YYYY-MM-DD" autoCapitalize="none" />
                </View>
                <View style={{ width: 80 }}>
                  <Text style={s.mLabel}>Est. hrs</Text>
                  <TextInput style={s.mInput} value={f.est_hours} onChangeText={v => setF((x: any) => ({ ...x, est_hours: v }))} keyboardType="numeric" placeholder="0" />
                </View>
              </View>
              <View style={s.mRow2}>
                <View style={{ flex: 1 }}>
                  <Text style={s.mLabel}>Actual start</Text>
                  <TextInput style={s.mInput} value={f.actual_start} onChangeText={v => setF((x: any) => ({ ...x, actual_start: v }))} placeholder="YYYY-MM-DD" autoCapitalize="none" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.mLabel}>Actual finish</Text>
                  <TextInput style={s.mInput} value={f.actual_finish} onChangeText={v => setF((x: any) => ({ ...x, actual_finish: v }))} placeholder="YYYY-MM-DD" autoCapitalize="none" />
                </View>
                <View style={{ width: 80 }}>
                  <Text style={s.mLabel}>Act. hrs</Text>
                  <TextInput style={s.mInput} value={f.actual_hours} onChangeText={v => setF((x: any) => ({ ...x, actual_hours: v }))} keyboardType="numeric" placeholder="0" />
                </View>
              </View>
              {(parseFloat(f.actual_hours) || 0) > 0 && (
                <Text style={[s.wbsMeta, { marginTop: 4, color: variance > 0 ? '#EF4444' : '#10B981' }]}>
                  Variance: {variance > 0 ? '+' : ''}{variance.toFixed(1)} hrs
                </Text>
              )}

              <Text style={s.mSec}>👥 Team</Text>
              <View style={s.mRow2}>
                <View style={{ flex: 1 }}>
                  <Text style={s.mLabel}>Owner</Text>
                  <TextInput style={s.mInput} value={f.owner} onChangeText={v => setF((x: any) => ({ ...x, owner: v }))} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.mLabel}>Co-owner</Text>
                  <TextInput style={s.mInput} value={f.co_owner} onChangeText={v => setF((x: any) => ({ ...x, co_owner: v }))} />
                </View>
              </View>
              <View style={s.mRow2}>
                <View style={{ flex: 1 }}>
                  <Text style={s.mLabel}>Reviewer</Text>
                  <TextInput style={s.mInput} value={f.reviewer} onChangeText={v => setF((x: any) => ({ ...x, reviewer: v }))} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.mLabel}>Approver</Text>
                  <TextInput style={s.mInput} value={f.approver} onChangeText={v => setF((x: any) => ({ ...x, approver: v }))} />
                </View>
              </View>
              <Text style={s.mLabel}>Watchers (comma-separated)</Text>
              <TextInput style={s.mInput} value={f.watchers} onChangeText={v => setF((x: any) => ({ ...x, watchers: v }))} placeholder="Ravi, Priya" />

              {modal?.mode === 'edit' && modalNode && (
                <>
                  <Text style={s.mSec}>🔗 Dependencies (this starts after…)</Text>
                  {nodeDeps.map(d => (
                    <View key={d.dep_id} style={s.depRow}>
                      <Text style={s.depText} numberOfLines={1}>
                        {byId[d.predecessor_id]?.title || '?'} <Text style={{ fontWeight: '800', color: '#4F46E5' }}>{d.dep_type}{d.lag_days ? `+${d.lag_days}d` : ''}</Text>
                      </Text>
                      <TouchableOpacity onPress={() => removeDep(d.dep_id)}>
                        <Ionicons name="trash-outline" size={14} color="#EF4444" />
                      </TouchableOpacity>
                    </View>
                  ))}
                  <TouchableOpacity style={s.mInput} onPress={() => setDepPickerOpen(o => !o)}>
                    <Text style={{ fontSize: 13, color: depPredId ? '#0F172A' : '#94A3B8' }}>
                      {depPredId ? (byId[depPredId]?.title || depPredId) : 'Pick predecessor node…'}
                    </Text>
                  </TouchableOpacity>
                  {depPickerOpen && (
                    <View style={s.depPicker}>
                      {nodes.filter(n => n.node_id !== modalNode.node_id).map(n => (
                        <TouchableOpacity key={n.node_id} style={s.depPickRow} onPress={() => { setDepPredId(n.node_id); setDepPickerOpen(false); }}>
                          <Ionicons name={TYPE_META[n.node_type]?.icon || 'construct'} size={12} color={TYPE_META[n.node_type]?.color} />
                          <Text style={s.depText} numberOfLines={1}>{n.title}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}
                  <View style={[s.mRow2, { alignItems: 'center' }]}>
                    <View style={s.mChips}>
                      {DEP_TYPES.map(t => (
                        <TouchableOpacity key={t} style={[s.mChip, depType === t && { backgroundColor: '#4F46E5', borderColor: '#4F46E5' }]} onPress={() => setDepType(t)}>
                          <Text style={[s.mChipT, depType === t && { color: '#FFF' }]}>{t}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                    <TextInput style={[s.mInput, { width: 60 }]} value={depLag} onChangeText={setDepLag} keyboardType="numeric" placeholder="lag" />
                    <TouchableOpacity style={s.depAddBtn} onPress={addDep}>
                      <Ionicons name="add" size={16} color="#FFF" />
                    </TouchableOpacity>
                  </View>

                  {(modalNode.node_type === 'task' || modalNode.node_type === 'subtask') && !modalNode.linked_action_id && (
                    <>
                      <Text style={s.mSec}>⚡ Execute</Text>
                      <View style={{ flexDirection: 'row', gap: 8 }}>
                        <TouchableOpacity style={[s.portBtn, { backgroundColor: '#DBEAFE' }]} onPress={() => portNode(modalNode, 'CTT')}>
                          <Ionicons name="calendar" size={14} color="#1D4ED8" />
                          <Text style={[s.portBtnT, { color: '#1D4ED8' }]}>→ CTT (one-time)</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={[s.portBtn, { backgroundColor: '#FEF3C7' }]} onPress={() => portNode(modalNode, 'LIFESTYLE')}>
                          <Ionicons name="repeat" size={14} color="#B45309" />
                          <Text style={[s.portBtnT, { color: '#B45309' }]}>→ LifeStyle (routine)</Text>
                        </TouchableOpacity>
                      </View>
                    </>
                  )}
                  {!!modalNode.linked_action_id && (
                    <Text style={[s.wbsMeta, { marginTop: 10 }]}>🔗 Ported to {modalNode.task_kind === 'routine' ? 'LifeStyle' : 'CTT'} — manage from the Action Center.</Text>
                  )}
                  <TouchableOpacity style={s.delNodeBtn} onPress={() => deleteNode(modalNode)}>
                    <Ionicons name="trash" size={14} color="#EF4444" />
                    <Text style={{ fontSize: 12, fontWeight: '700', color: '#EF4444' }}>Delete node & subtree</Text>
                  </TouchableOpacity>
                </>
              )}
            </ScrollView>
            <TouchableOpacity style={s.mSave} onPress={saveNode} disabled={saving}>
              {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.mSaveT}>{modal?.mode === 'add' ? 'Add node' : 'Save changes'}</Text>}
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* ── Register add/edit modal ── */}
      <Modal visible={!!regModal} transparent animationType="slide" onRequestClose={() => setRegModal(null)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={s.mOverlay}>
          <View style={s.mSheet}>
            <View style={s.mHead}>
              <Text style={s.mTitle}>{regModal?.mode === 'add' ? `New ${regKind}` : `Edit ${regKind}`}</Text>
              <TouchableOpacity onPress={() => setRegModal(null)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 460 }}>
              <Text style={s.mLabel}>Title *</Text>
              <TextInput style={s.mInput} value={rf.title} onChangeText={v => setRf((x: any) => ({ ...x, title: v }))} />
              <Text style={s.mLabel}>Description</Text>
              <TextInput style={[s.mInput, { minHeight: 50 }]} value={rf.description} onChangeText={v => setRf((x: any) => ({ ...x, description: v }))} multiline />
              <Text style={s.mLabel}>Owner</Text>
              <TextInput style={s.mInput} value={rf.owner} onChangeText={v => setRf((x: any) => ({ ...x, owner: v }))} />
              <Text style={s.mLabel}>Status</Text>
              <View style={s.mChips}>
                {['open', 'mitigating', 'resolved', 'closed'].map(st => (
                  <TouchableOpacity key={st} style={[s.mChip, rf.status === st && { backgroundColor: '#4F46E5', borderColor: '#4F46E5' }]} onPress={() => setRf((x: any) => ({ ...x, status: st }))}>
                    <Text style={[s.mChipT, rf.status === st && { color: '#FFF' }]}>{st}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              {regKind === 'risk' && (
                <>
                  <Text style={s.mLabel}>Probability</Text>
                  <View style={s.mChips}>{LEVELS.map(l => (
                    <TouchableOpacity key={l} style={[s.mChip, rf.probability === l && { backgroundColor: '#F59E0B', borderColor: '#F59E0B' }]} onPress={() => setRf((x: any) => ({ ...x, probability: l }))}>
                      <Text style={[s.mChipT, rf.probability === l && { color: '#FFF' }]}>{l}</Text>
                    </TouchableOpacity>))}
                  </View>
                  <Text style={s.mLabel}>Impact</Text>
                  <View style={s.mChips}>{LEVELS.map(l => (
                    <TouchableOpacity key={l} style={[s.mChip, rf.impact === l && { backgroundColor: '#EF4444', borderColor: '#EF4444' }]} onPress={() => setRf((x: any) => ({ ...x, impact: l }))}>
                      <Text style={[s.mChipT, rf.impact === l && { color: '#FFF' }]}>{l}</Text>
                    </TouchableOpacity>))}
                  </View>
                  <Text style={s.mLabel}>Mitigation plan</Text>
                  <TextInput style={[s.mInput, { minHeight: 50 }]} value={rf.mitigation} onChangeText={v => setRf((x: any) => ({ ...x, mitigation: v }))} multiline />
                </>
              )}
              {regKind === 'issue' && (
                <>
                  <Text style={s.mLabel}>Severity</Text>
                  <View style={s.mChips}>{[...LEVELS, 'critical'].map(l => (
                    <TouchableOpacity key={l} style={[s.mChip, rf.severity === l && { backgroundColor: '#EF4444', borderColor: '#EF4444' }]} onPress={() => setRf((x: any) => ({ ...x, severity: l }))}>
                      <Text style={[s.mChipT, rf.severity === l && { color: '#FFF' }]}>{l}</Text>
                    </TouchableOpacity>))}
                  </View>
                  <Text style={s.mLabel}>Resolution</Text>
                  <TextInput style={[s.mInput, { minHeight: 50 }]} value={rf.resolution} onChangeText={v => setRf((x: any) => ({ ...x, resolution: v }))} multiline />
                </>
              )}
              {regKind === 'change' && (
                <>
                  <Text style={s.mLabel}>Change type</Text>
                  <View style={s.mChips}>{['scope', 'budget', 'timeline', 'decision'].map(l => (
                    <TouchableOpacity key={l} style={[s.mChip, rf.change_type === l && { backgroundColor: '#3B82F6', borderColor: '#3B82F6' }]} onPress={() => setRf((x: any) => ({ ...x, change_type: l }))}>
                      <Text style={[s.mChipT, rf.change_type === l && { color: '#FFF' }]}>{l}</Text>
                    </TouchableOpacity>))}
                  </View>
                  <Text style={s.mLabel}>Decision / outcome</Text>
                  <TextInput style={[s.mInput, { minHeight: 50 }]} value={rf.decision} onChangeText={v => setRf((x: any) => ({ ...x, decision: v }))} multiline />
                </>
              )}
            </ScrollView>
            <TouchableOpacity style={s.mSave} onPress={saveReg} disabled={saving}>
              {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.mSaveT}>Save</Text>}
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  hdr: { flexDirection: 'row', alignItems: 'center', padding: 14, gap: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },
  hdrT: { fontSize: 16, fontWeight: '800', color: '#FFF' },
  hdrS: { fontSize: 11, color: 'rgba(255,255,255,0.85)', marginTop: 2 },

  tabsRow: { flexDirection: 'row', backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  tabBtn: { flex: 1, alignItems: 'center', paddingVertical: 9, gap: 2, borderBottomWidth: 2, borderBottomColor: 'transparent' },
  tabBtnA: { borderBottomColor: '#4F46E5' },
  tabT: { fontSize: 10, fontWeight: '700', color: '#94A3B8' },

  emptyBox: { alignItems: 'center', padding: 30, gap: 10 },
  emptyText: { fontSize: 12, color: '#64748B', textAlign: 'center', lineHeight: 18 },
  secTitle: { fontSize: 12, fontWeight: '800', color: '#334155', marginBottom: 6, textTransform: 'uppercase' },

  pickCard: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, backgroundColor: '#FFF', borderRadius: 12, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 8 },
  pickTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  pickSub: { fontSize: 11, color: '#64748B', marginTop: 2 },

  topAddBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#4F46E5', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  topAddT: { fontSize: 12, fontWeight: '700', color: '#FFF' },

  wbsRow: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', padding: 8, marginBottom: 5 },
  wbsCritical: { borderColor: '#FECACA', backgroundColor: '#FEF2F2' },
  wbsTitle: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  wbsMetaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 2, alignItems: 'center' },
  wbsType: { fontSize: 9, fontWeight: '800', textTransform: 'uppercase' },
  wbsMeta: { fontSize: 10, color: '#64748B' },
  critBadge: { fontSize: 9, fontWeight: '800', color: '#EF4444' },
  delayBadge: { fontSize: 9, fontWeight: '800', color: '#B45309' },
  portBadge: { fontSize: 9, fontWeight: '800', color: '#1D4ED8' },
  wbsProg: { width: 46, alignItems: 'flex-end' },
  wbsProgText: { fontSize: 10, fontWeight: '800', color: '#334155' },
  wbsProgBar: { width: 42, height: 4, borderRadius: 2, backgroundColor: '#E2E8F0', marginTop: 2 },
  wbsProgFill: { height: 4, borderRadius: 2, backgroundColor: '#4F46E5' },
  stChip: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  stChipT: { fontSize: 9, fontWeight: '800' },
  addChildBtn: { width: 24, height: 24, borderRadius: 12, backgroundColor: '#EEF2FF', justifyContent: 'center', alignItems: 'center' },

  ganttTick: { fontSize: 9, color: '#94A3B8', fontWeight: '700' },
  ganttRow: { flexDirection: 'row', alignItems: 'center', height: 26 },
  ganttLabel: { fontSize: 11, fontWeight: '600', color: '#334155', paddingRight: 8 },
  ganttBar: { position: 'absolute', height: 14, borderRadius: 7, overflow: 'hidden' },
  ganttBarFill: { height: 14, backgroundColor: 'rgba(255,255,255,0.35)' },
  ganttDiamond: { position: 'absolute', width: 0, height: 0, borderLeftWidth: 6, borderRightWidth: 6, borderBottomWidth: 12, borderLeftColor: 'transparent', borderRightColor: 'transparent' },
  todayLine: { position: 'absolute', top: 0, bottom: 0, width: 2, backgroundColor: '#DC2626', opacity: 0.5 },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, flexWrap: 'wrap' },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendT: { fontSize: 10, color: '#64748B', marginRight: 8 },

  depRow: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8, backgroundColor: '#FFF', borderRadius: 8, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 4 },
  depText: { flex: 1, fontSize: 11, color: '#334155' },
  depPicker: { maxHeight: 160, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8, marginTop: 4, backgroundColor: '#F8FAFC' },
  depPickRow: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 8, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  depAddBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: '#4F46E5', justifyContent: 'center', alignItems: 'center' },

  kanbanCol: { width: 230, backgroundColor: '#F1F5F9', borderRadius: 12, padding: 8 },
  kanbanHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingBottom: 6, borderTopWidth: 3, paddingTop: 6, paddingHorizontal: 4, borderRadius: 4 },
  kanbanHeadT: { fontSize: 12, fontWeight: '800' },
  kanbanCount: { paddingHorizontal: 7, paddingVertical: 2, borderRadius: 10 },
  kanbanCard: { backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', padding: 10, marginBottom: 6 },
  kanbanCardT: { fontSize: 12, fontWeight: '700', color: '#0F172A' },
  kanbanMoveRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  moveBtn: { width: 28, height: 24, borderRadius: 8, backgroundColor: '#EEF2FF', justifyContent: 'center', alignItems: 'center' },

  calHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, paddingHorizontal: 10 },
  calMonthT: { fontSize: 14, fontWeight: '800', color: '#0F172A' },
  calGrid: { flexDirection: 'row', flexWrap: 'wrap', backgroundColor: '#FFF', borderRadius: 12, borderWidth: 1, borderColor: '#E2E8F0', overflow: 'hidden' },
  calCell: { width: '14.28%', minHeight: 44, alignItems: 'center', paddingTop: 6, borderWidth: 0.5, borderColor: '#F1F5F9' },
  calCellSel: { backgroundColor: '#4F46E5' },
  calDow: { fontSize: 10, fontWeight: '800', color: '#94A3B8' },
  calDay: { fontSize: 12, fontWeight: '600', color: '#334155' },
  calDot: { width: 5, height: 5, borderRadius: 3, marginTop: 2 },

  regKindChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#FFF' },
  regKindT: { fontSize: 11, fontWeight: '700', color: '#334155' },
  regAddBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 10 },
  regAddT: { fontSize: 12, fontWeight: '700', color: '#4F46E5' },
  regCard: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 6 },
  regTitle: { fontSize: 13, fontWeight: '700', color: '#0F172A' },

  mOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  mSheet: { backgroundColor: '#FFF', borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 16, maxWidth: 680, width: '100%', alignSelf: 'center' },
  mHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  mTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A' },
  mLabel: { fontSize: 10, fontWeight: '800', color: '#64748B', marginTop: 10, marginBottom: 4, textTransform: 'uppercase' },
  mSec: { fontSize: 13, fontWeight: '800', color: '#4F46E5', marginTop: 16 },
  mInput: { borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: '#0F172A', backgroundColor: '#FFF' },
  mRow2: { flexDirection: 'row', gap: 8 },
  mChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, flex: 1 },
  mChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#FFF' },
  mChipT: { fontSize: 11, fontWeight: '700', color: '#334155' },
  mSave: { backgroundColor: '#4F46E5', borderRadius: 12, paddingVertical: 13, alignItems: 'center', marginTop: 12 },
  mSaveT: { color: '#FFF', fontSize: 14, fontWeight: '800' },
  portBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5, paddingVertical: 10, borderRadius: 10 },
  portBtnT: { fontSize: 11, fontWeight: '800' },
  delNodeBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 16, alignSelf: 'flex-start' },
});
