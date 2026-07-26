import React, { useState, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import { useLifeAreas } from '../../src/utils/useLifeAreas';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert, ActivityIndicator, Platform, KeyboardAvoidingView, Switch, Modal,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as Linking from 'expo-linking';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';
import { LinkedFreedomsPicker } from '../../src/components/LinkedFreedomsPicker';
import ATEXEstimateButton from '../../src/components/ATEXEstimateButton';
import { safeBack } from '../../src/utils/navigation';
import { ACTION_STATUS_OPTS, normStatus } from '../../src/constants/actionStatus';

// LIFE_AREAS array moved into the component (catalog-driven).
const PRIORITIES = [
  { id: 'critical', label: 'Critical', color: '#EF4444', icon: 'alert-circle' },
  { id: 'high', label: 'High', color: '#F59E0B', icon: 'warning' },
  { id: 'medium', label: 'Medium', color: '#3B82F6', icon: 'remove-circle' },
  { id: 'low', label: 'Low', color: '#6B7280', icon: 'arrow-down-circle' },
];

const STATUS_ICONS: Record<string,string> = {
  pending: 'radio-button-off', wip_25: 'time-outline', wip_50: 'time',
  wip_75: 'time', done: 'checkmark-circle', deferred: 'pause-circle',
  blocked: 'close-circle', cancelled: 'ban',
};
const STATUSES = ACTION_STATUS_OPTS.map(o => ({
  id: o.id, label: o.label, color: o.color, icon: STATUS_ICONS[o.id] || 'ellipse',
}));

const FREQUENCIES = [
  { id: 'hourly', label: 'Hourly', icon: 'time-outline' },
  { id: 'daily', label: 'Daily', icon: 'today' },
  { id: 'weekly', label: 'Weekly', icon: 'calendar' },
  { id: 'fortnightly', label: 'Fortnightly', icon: 'calendar-outline' },
  { id: 'monthly', label: 'Monthly', icon: 'calendar-number' },
];

const DECISION_TYPES = [
  { id: 'problem', label: 'Problem', icon: 'alert-circle', color: '#EF4444', bg: '#FEE2E2' },
  { id: 'need', label: 'Need', icon: 'bulb', color: '#D97706', bg: '#FEF3C7' },
  { id: 'aspiration', label: 'Aspiration', icon: 'rocket', color: '#059669', bg: '#D1FAE5' },
];

export default function CTTTaskScreen() {
  // LIFE_AREAS now flows from the Admin Central Catalog via the
  // useLifeAreas() hook (single source of truth across the app).
  // Adapter preserves both old (`c`, `name`) and new (`color`,
  // `label`, `slug`, `node_id`) field names so the rest of this file
  // continues to compile without ripple-effect edits.
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
  const { id } = useLocalSearchParams();
  const spawnParams = useLocalSearchParams<{ parent_task_id?: string; parent_title?: string }>();
  const { session } = useAuthStore();
  const editId = id as string | undefined;
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [expandedSection, setExpandedSection] = useState<string>('basic');

  // Form state
  const [task, setTask] = useState('');
  const [subTask, setSubTask] = useState('');
  const [status, setStatus] = useState('pending');
  const [priority, setPriority] = useState('medium');
  const [remarks, setRemarks] = useState('');
  const [deadline, setDeadline] = useState('');
  const [taskOwners, setTaskOwners] = useState('');
  const [lifeArea, setLifeArea] = useState('');
  const [decisionType, setDecisionType] = useState('');
  const [company, setCompany] = useState('');
  const [division, setDivision] = useState('');
  const [team, setTeam] = useState('');
  const [project, setProject] = useState('');
  const [internalDep, setInternalDep] = useState('');
  const [externalDep, setExternalDep] = useState('');
  const [internalHelp, setInternalHelp] = useState('');
  const [externalHelp, setExternalHelp] = useState('');
  const [duration, setDuration] = useState('');
  const [fromTime, setFromTime] = useState('');
  const [toTime, setToTime] = useState('');
  const [isRoutine, setIsRoutine] = useState(false);
  const [frequency, setFrequency] = useState('');
  const [sourceType, setSourceType] = useState('manual');
  const [sourceId, setSourceId] = useState('');
  const [linkedFreedoms, setLinkedFreedoms] = useState<string[]>([]);
  // ── Classification ref: link this task under a pre-existing module item ──
  const [classificationRef, setClassificationRef] = useState<{ type: string; ref_id: string; label: string } | null>(null);
  const [clsPickerOpen, setClsPickerOpen] = useState(false);
  const [clsOptions, setClsOptions] = useState<{ type: string; ref_id: string; label: string }[]>([]);
  const [clsLoading, setClsLoading] = useState(false);

  useEffect(() => {
    if (editId) loadTask();
  }, [editId]);

  // Spawned as a SUB-TASK from another CTT task ("Trigger from this task")
  useEffect(() => {
    if (!editId && spawnParams?.parent_task_id) {
      setClassificationRef({
        type: 'parent_task',
        ref_id: String(spawnParams.parent_task_id),
        label: String(spawnParams.parent_title || 'Parent task'),
      });
    }
  }, [editId, spawnParams?.parent_task_id]);

  const CLS_TYPE_LABELS: Record<string, string> = {
    goal: 'Goal', milestone: 'Milestone', deliverable: 'Deliverable',
    work_package: 'Work Package', parent_task: 'Parent CTT Task',
  };

  const openClsPicker = async () => {
    setClsPickerOpen(true);
    setClsLoading(true);
    try {
      const [goalsR, nodesR, tasksR] = await Promise.all([
        api.get('/goal-setter/goals').catch(() => ({ data: [] })),
        api.get('/gem-pm/nodes/all?types=deliverable,work_package').catch(() => ({ data: [] })),
        api.get('/ctt/tasks').catch(() => ({ data: [] })),
      ]);
      const opts: { type: string; ref_id: string; label: string }[] = [];
      (goalsR.data || []).forEach((g: any) => {
        opts.push({ type: 'goal', ref_id: g.goal_id, label: g.title || 'Goal' });
        (g.milestones || []).forEach((m: any) => {
          opts.push({ type: 'milestone', ref_id: m.milestone_id, label: `${m.title || 'Milestone'} · ${g.title || ''}` });
        });
      });
      (nodesR.data || []).forEach((n: any) => {
        opts.push({ type: n.node_type, ref_id: n.node_id, label: n.title || 'PM node' });
      });
      (tasksR.data || []).forEach((t: any) => {
        if (t.task_id !== editId) opts.push({ type: 'parent_task', ref_id: t.task_id, label: t.task || 'CTT task' });
      });
      setClsOptions(opts);
    } finally { setClsLoading(false); }
  };

  // ── "Trigger from this task" launchers (Dependencies & Help) ──
  const TRIGGERS = [
    { id: 'sf', label: 'Solution Finder', icon: 'bulb', color: '#4F46E5', go: () => router.push({ pathname: '/tools/solution-finder', params: { seed: task } } as any) },
    { id: 'dez', label: 'MyDezider', icon: 'git-compare', color: '#8E24AA', go: () => router.push({ pathname: '/tools/new-decision', params: { module: 'dezider' } } as any) },
    { id: 'pc', label: 'Pros & Cons', icon: 'swap-vertical', color: '#0D9488', go: () => router.push('/tools/pros-cons' as any) },
    { id: 'sub', label: 'Sub Task', icon: 'git-branch', color: '#F59E0B', go: () => router.push({ pathname: '/tools/ctt-task', params: { parent_task_id: editId || '', parent_title: task } } as any) },
    { id: 'life', label: 'LifeStyle Routine', icon: 'repeat', color: '#B45309', go: () => router.push('/tools/lifestyle' as any) },
    { id: 'goal', label: 'Goal', icon: 'flag', color: '#059669', go: () => router.push('/tools/goal-setter' as any) },
  ];

  const loadTask = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/ctt/tasks/${editId}`);
      const d = res.data;
      setTask(d.task || '');
      setSubTask(d.sub_task || '');
      setStatus(normStatus(d.current_status));
      setPriority(d.priority || 'medium');
      setRemarks(d.remarks || '');
      setDeadline(d.deadline || '');
      setTaskOwners((d.task_owners || []).join(', '));
      setLifeArea(d.life_area || '');
      setDecisionType(d.decision_type || '');
      setCompany(d.company || '');
      setDivision(d.division || '');
      setTeam(d.team || '');
      setProject(d.project || '');
      setInternalDep(d.internal_dependency || '');
      setExternalDep(d.external_dependency || '');
      setInternalHelp(d.internal_help || '');
      setExternalHelp(d.external_help || '');
      setDuration(d.task_duration || '');
      setFromTime(d.from_time || '');
      setToTime(d.to_time || '');
      setIsRoutine(d.is_routine || false);
      setFrequency(d.frequency || '');
      setSourceType(d.source_type || 'manual');
      setSourceId(d.source_id || '');
      setLinkedFreedoms(d.linked_freedoms || []);
      setClassificationRef(d.classification_ref || null);
    } catch (e) {
      showAlert('Error', 'Failed to load task');
      safeBack(router);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!task.trim()) {
      showAlert('Required', 'Task name is required');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        task: task.trim(),
        sub_task: subTask.trim(),
        current_status: status,
        priority,
        remarks: remarks.trim(),
        deadline: deadline || null,
        task_owners: taskOwners.split(',').map(s => s.trim()).filter(Boolean),
        life_area: lifeArea,
        decision_type: decisionType,
        company: company.trim(),
        division: division.trim(),
        team: team.trim(),
        project: project.trim(),
        internal_dependency: internalDep.trim(),
        external_dependency: externalDep.trim(),
        internal_help: internalHelp.trim(),
        external_help: externalHelp.trim(),
        task_duration: duration.trim(),
        from_time: fromTime || null,
        to_time: toTime || null,
        is_routine: isRoutine,
        frequency: isRoutine ? frequency : null,
        linked_freedoms: linkedFreedoms,
        classification_ref: classificationRef,
      };
      if (editId) {
        await api.put(`/ctt/tasks/${editId}`, payload);
      } else {
        await api.post('/ctt/tasks', payload);
      }
      safeBack(router);
    } catch (e) {
      showAlert('Error', 'Failed to save task');
    } finally {
      setSaving(false);
    }
  };

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? '' : section);
  };

  const SectionHeader = ({ title, section, icon, count }: { title: string; section: string; icon: string; count?: number }) => (
    <TouchableOpacity style={st.sectionHeader} onPress={() => toggleSection(section)}>
      <View style={st.sectionLeft}>
        <Ionicons name={icon as any} size={18} color={COLORS.primary} />
        <Text style={st.sectionTitle}>{title}</Text>
        {count !== undefined && count > 0 && (
          <View style={st.sectionBadge}>
            <Text style={st.sectionBadgeText}>{count}</Text>
          </View>
        )}
      </View>
      <Ionicons
        name={expandedSection === section ? 'chevron-up' : 'chevron-down'}
        size={18}
        color={COLORS.textMuted}
      />
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <SafeAreaView style={st.container}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={{ fontSize: 14, color: COLORS.textMuted, marginTop: 12 }}>Loading task...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {/* Header */}
        <LinearGradient colors={['#2D5F8B', '#1E3A5F']} style={st.header}>
          <TouchableOpacity onPress={() => safeBack(router)} style={st.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFFFFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={st.headerTitle}>{editId ? 'Edit Task' : 'New Task'}</Text>
            {editId && sourceType !== 'manual' && (
              <Text style={st.headerSub}>Source: {sourceType.replace('_', ' ')}</Text>
            )}
          </View>
          {editId && (
            <TouchableOpacity
              style={st.deleteBtn}
              onPress={() => showAlert('Delete', 'Delete this task?', [
                { text: 'Cancel', style: 'cancel' },
                { text: 'Delete', style: 'destructive', onPress: async () => {
                  try { await api.delete(`/ctt/tasks/${editId}`); safeBack(router); }
                  catch (e) { showAlert('Error', 'Failed to delete'); }
                }},
              ])}
            >
              <Ionicons name="trash-outline" size={18} color="#FF6B6B" />
            </TouchableOpacity>
          )}
        </LinearGradient>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 100 }} showsVerticalScrollIndicator={false}>
          {/* === BASIC INFO (always visible) === */}
          <View style={st.section}>
            <Text style={st.label}>Task *</Text>
            <TextInput
              style={st.input}
              value={task}
              onChangeText={setTask}
              placeholder="What needs to be done?"
              placeholderTextColor={COLORS.textMuted}
              multiline
            />

            <Text style={st.label}>Sub-Task</Text>
            <TextInput
              style={st.input}
              value={subTask}
              onChangeText={setSubTask}
              placeholder="Break it down further..."
              placeholderTextColor={COLORS.textMuted}
            />

            {/* Iter 129 — ATEX Effort Estimation invocation */}
            <View style={{ marginTop: 8, marginBottom: 4 }}>
              <ATEXEstimateButton source="ctt" title={task} ref_id={editId} />
            </View>

            {/* Priority */}
            <Text style={st.label}>Priority</Text>
            <View style={st.chipRow}>
              {PRIORITIES.map(p => (
                <TouchableOpacity
                  key={p.id}
                  style={[st.priorityChip, priority === p.id && { backgroundColor: p.color, borderColor: p.color }]}
                  onPress={() => setPriority(p.id)}
                >
                  <Ionicons name={p.icon as any} size={14} color={priority === p.id ? '#FFF' : p.color} />
                  <Text style={[st.chipText, priority === p.id && { color: '#FFF' }]}>{p.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Status */}
            <Text style={st.label}>Status</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={st.chipRow}>
                {STATUSES.map(s => (
                  <TouchableOpacity
                    key={s.id}
                    style={[st.statusChip, status === s.id && { backgroundColor: s.color, borderColor: s.color }]}
                    onPress={() => setStatus(s.id)}
                  >
                    <Ionicons name={s.icon as any} size={14} color={status === s.id ? '#FFF' : s.color} />
                    <Text style={[st.chipText, status === s.id && { color: '#FFF' }]}>{s.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
          </View>

          {/* === CLASSIFICATION === */}
          <SectionHeader title="Classification" section="classification" icon="pricetags" count={(lifeArea ? 1 : 0) + (decisionType ? 1 : 0)} />
          {expandedSection === 'classification' && (
            <View style={st.section}>
              <Text style={st.label}>Life Area</Text>
              <View style={st.lifeAreaGrid}>
                {LIFE_AREAS.map(a => (
                  <TouchableOpacity
                    key={a.id}
                    style={[st.lifeAreaChip, lifeArea === a.id && st.lifeAreaActive]}
                    onPress={() => setLifeArea(lifeArea === a.id ? '' : a.id)}
                  >
                    <Ionicons name={a.icon as any} size={16} color={lifeArea === a.id ? '#FFF' : COLORS.primary} />
                    <Text style={[st.lifeAreaText, lifeArea === a.id && { color: '#FFF' }]}>{a.name}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={st.label}>Decision Type</Text>
              <View style={st.chipRow}>
                {DECISION_TYPES.map(dt => (
                  <TouchableOpacity
                    key={dt.id}
                    style={[st.decisionChip, {
                      backgroundColor: decisionType === dt.id ? dt.color : dt.bg,
                      borderColor: decisionType === dt.id ? dt.color : dt.bg,
                    }]}
                    onPress={() => setDecisionType(decisionType === dt.id ? '' : dt.id)}
                  >
                    <Ionicons name={dt.icon as any} size={16} color={decisionType === dt.id ? '#FFF' : dt.color} />
                    <Text style={[st.decisionText, { color: decisionType === dt.id ? '#FFF' : dt.color }]}>{dt.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={st.label}>Link to pre-existing item</Text>
              <Text style={{ fontSize: 11, color: COLORS.textMuted, marginBottom: 6 }}>
                Classify this task under a Goal, Milestone, Deliverable, Work Package or a Parent CTT Task.
              </Text>
              {classificationRef ? (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#EEF2FF', borderRadius: 10, padding: 10 }}>
                  <Ionicons name="link" size={14} color="#4F46E5" />
                  <Text style={{ flex: 1, fontSize: 12, fontWeight: '600', color: '#3730A3' }} numberOfLines={1}>
                    {CLS_TYPE_LABELS[classificationRef.type] || classificationRef.type}: {classificationRef.label}
                  </Text>
                  <TouchableOpacity onPress={() => setClassificationRef(null)} hitSlop={8}>
                    <Ionicons name="close-circle" size={16} color="#6366F1" />
                  </TouchableOpacity>
                </View>
              ) : (
                <TouchableOpacity
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: '#C7D2FE', borderStyle: 'dashed', borderRadius: 10, padding: 10 }}
                  onPress={openClsPicker}
                >
                  <Ionicons name="add-circle-outline" size={16} color="#4F46E5" />
                  <Text style={{ fontSize: 12, fontWeight: '600', color: '#4F46E5' }}>Choose item to link…</Text>
                </TouchableOpacity>
              )}
            </View>
          )}

          {/* === SCHEDULING === */}
          <SectionHeader title="Scheduling" section="scheduling" icon="time" count={deadline ? 1 : 0} />
          {expandedSection === 'scheduling' && (
            <View style={st.section}>
              <Text style={st.label}>Deadline</Text>
              <TextInput
                style={st.input}
                value={deadline}
                onChangeText={setDeadline}
                placeholder="e.g. 2026-03-30 or 30/03/26"
                placeholderTextColor={COLORS.textMuted}
              />

              <View style={st.row}>
                <View style={{ flex: 1 }}>
                  <Text style={st.label}>From Time</Text>
                  <TextInput
                    style={st.input}
                    value={fromTime}
                    onChangeText={setFromTime}
                    placeholder="YYYY-MM-DD HH:MM"
                    placeholderTextColor={COLORS.textMuted}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={st.label}>To Time</Text>
                  <TextInput
                    style={st.input}
                    value={toTime}
                    onChangeText={setToTime}
                    placeholder="YYYY-MM-DD HH:MM"
                    placeholderTextColor={COLORS.textMuted}
                  />
                </View>
              </View>

              <Text style={st.label}>Duration</Text>
              <TextInput
                style={st.input}
                value={duration}
                onChangeText={setDuration}
                placeholder="e.g. 2h 30m"
                placeholderTextColor={COLORS.textMuted}
              />

              <Text style={st.label}>Task Owner(s)</Text>
              <TextInput
                style={st.input}
                value={taskOwners}
                onChangeText={setTaskOwners}
                placeholder="Comma-separated: Self, John, Expert"
                placeholderTextColor={COLORS.textMuted}
              />
            </View>
          )}

          {/* === ROUTINE === */}
          <SectionHeader title="Routine Settings" section="routine" icon="repeat" count={isRoutine ? 1 : 0} />
          {expandedSection === 'routine' && (
            <View style={st.section}>
              <View style={st.routineRow}>
                <View style={{ flex: 1 }}>
                  <Text style={st.routineLabel}>Make this a Routine Task</Text>
                  <Text style={st.routineHint}>Routine tasks repeat on a schedule</Text>
                </View>
                <Switch
                  value={isRoutine}
                  onValueChange={setIsRoutine}
                  trackColor={{ false: '#D1D5DB', true: COLORS.primary + '80' }}
                  thumbColor={isRoutine ? COLORS.primary : '#9CA3AF'}
                />
              </View>

              {isRoutine && (
                <>
                  <Text style={st.label}>Frequency</Text>
                  <View style={st.chipRow}>
                    {FREQUENCIES.map(f => (
                      <TouchableOpacity
                        key={f.id}
                        style={[st.freqChip, frequency === f.id && st.freqActive]}
                        onPress={() => setFrequency(f.id)}
                      >
                        <Ionicons name={f.icon as any} size={14} color={frequency === f.id ? '#FFF' : COLORS.textMuted} />
                        <Text style={[st.chipText, frequency === f.id && { color: '#FFF' }]}>{f.label}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </>
              )}
            </View>
          )}

          {/* === ORGANIZATION === */}
          <SectionHeader title="Organization" section="org" icon="business" count={(company ? 1 : 0) + (project ? 1 : 0)} />
          {expandedSection === 'org' && (
            <View style={st.section}>
              <View style={st.row}>
                <View style={{ flex: 1 }}>
                  <Text style={st.label}>Company</Text>
                  <TextInput style={st.input} value={company} onChangeText={setCompany} placeholder="Company" placeholderTextColor={COLORS.textMuted} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={st.label}>Project</Text>
                  <TextInput style={st.input} value={project} onChangeText={setProject} placeholder="Project" placeholderTextColor={COLORS.textMuted} />
                </View>
              </View>
              <View style={st.row}>
                <View style={{ flex: 1 }}>
                  <Text style={st.label}>Division</Text>
                  <TextInput style={st.input} value={division} onChangeText={setDivision} placeholder="Division" placeholderTextColor={COLORS.textMuted} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={st.label}>Team</Text>
                  <TextInput style={st.input} value={team} onChangeText={setTeam} placeholder="Team" placeholderTextColor={COLORS.textMuted} />
                </View>
              </View>
            </View>
          )}

          {/* === DEPENDENCIES === */}
          <SectionHeader title="Dependencies & Help" section="deps" icon="git-branch" count={(internalDep ? 1 : 0) + (externalDep ? 1 : 0)} />
          {expandedSection === 'deps' && (
            <View style={st.section}>
              <Text style={st.label}>Internal Dependency (ID)</Text>
              <TextInput style={st.input} value={internalDep} onChangeText={setInternalDep} placeholder="What internal resources are needed?" placeholderTextColor={COLORS.textMuted} />

              <Text style={st.label}>External Dependency (ED)</Text>
              <TextInput style={st.input} value={externalDep} onChangeText={setExternalDep} placeholder="What external factors are needed?" placeholderTextColor={COLORS.textMuted} />

              <Text style={st.label}>Internal Help (IH)</Text>
              <TextInput style={st.input} value={internalHelp} onChangeText={setInternalHelp} placeholder="Help needed from within org" placeholderTextColor={COLORS.textMuted} />

              <Text style={st.label}>External Help (EH)</Text>
              <TextInput style={st.input} value={externalHelp} onChangeText={setExternalHelp} placeholder="Help needed from outside" placeholderTextColor={COLORS.textMuted} />

              <Text style={st.label}>Remarks</Text>
              <TextInput
                style={[st.input, { minHeight: 80, textAlignVertical: 'top' }]}
                value={remarks}
                onChangeText={setRemarks}
                placeholder="Additional notes..."
                placeholderTextColor={COLORS.textMuted}
                multiline
                numberOfLines={4}
              />

              <LinkedFreedomsPicker value={linkedFreedoms} onChange={setLinkedFreedoms} />

              <Text style={st.label}>Trigger from this task</Text>
              <Text style={{ fontSize: 11, color: COLORS.textMuted, marginBottom: 6 }}>
                A task can involve a problem to be solved or a decision to be made — launch the right tool with this task&apos;s context.
              </Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                {TRIGGERS.map(t => (
                  <TouchableOpacity
                    key={t.id}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: t.color + '15', borderWidth: 1, borderColor: t.color + '40', paddingHorizontal: 10, paddingVertical: 7, borderRadius: 10 }}
                    onPress={t.go}
                  >
                    <Ionicons name={t.icon as any} size={13} color={t.color} />
                    <Text style={{ fontSize: 11, fontWeight: '700', color: t.color }}>{t.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}
        </ScrollView>

        {/* Sticky Save Button + Calendar Sync */}
        <View style={st.bottom}>
          {editId && deadline && (
            <TouchableOpacity
              style={st.calendarSyncBtn}
              onPress={async () => {
                try {
                  const statusRes = await api.get('/oauth/calendar/status', {
                    headers: { Authorization: `Bearer ${session}` },
                  });
                  if (!statusRes.data?.connected) {
                    showAlert('Connect Calendar', 'Please connect your Google Calendar first.', [
                      { text: 'Cancel', style: 'cancel' },
                      { text: 'Connect', onPress: () => router.push('/tools/google-calendar' as any) },
                    ]);
                    return;
                  }
                  const res = await api.post('/google-calendar/sync-ctt-task', {
                    task_id: editId,
                    timezone: 'Asia/Kolkata',
                  }, { headers: { Authorization: `Bearer ${session}` } });
                  showAlert('Synced!', 'Task added to your Google Calendar', [
                    { text: 'OK' },
                    { text: 'Open Link', onPress: () => {
                      if (res.data?.html_link) Linking.openURL(res.data.html_link);
                    }},
                  ]);
                } catch (e: any) {
                  showAlert('Error', e?.response?.data?.detail || 'Failed to sync to calendar');
                }
              }}
            >
              <Ionicons name="calendar" size={16} color="#4285F4" />
              <Text style={st.calendarSyncText}>Sync to Google Calendar</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity
            style={[st.saveBtn, saving && { opacity: 0.7 }]}
            onPress={handleSave}
            disabled={saving}
          >
            {saving ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <>
                <Ionicons name="checkmark-circle" size={20} color="#FFF" />
                <Text style={st.saveBtnText}>{editId ? 'Update Task' : 'Create Task'}</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>

      {/* Classification "link to pre-existing item" picker */}
      <Modal visible={clsPickerOpen} transparent animationType="slide" onRequestClose={() => setClsPickerOpen(false)}>
        <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: '#FFF', borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center' }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <Text style={{ fontSize: 15, fontWeight: '800', color: COLORS.textPrimary }}>Link to pre-existing item</Text>
              <TouchableOpacity onPress={() => setClsPickerOpen(false)}><Ionicons name="close" size={22} color={COLORS.textSecondary} /></TouchableOpacity>
            </View>
            {clsLoading ? <ActivityIndicator color={COLORS.primary} style={{ marginVertical: 24 }} /> : (
              <ScrollView style={{ maxHeight: 420 }}>
                {['goal', 'milestone', 'deliverable', 'work_package', 'parent_task'].map(tp => {
                  const list = clsOptions.filter(o => o.type === tp);
                  if (list.length === 0) return null;
                  return (
                    <View key={tp}>
                      <Text style={{ fontSize: 10, fontWeight: '800', color: COLORS.textMuted, textTransform: 'uppercase', marginTop: 12, marginBottom: 4 }}>
                        {CLS_TYPE_LABELS[tp]} ({list.length})
                      </Text>
                      {list.map(o => (
                        <TouchableOpacity
                          key={`${o.type}-${o.ref_id}`}
                          style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' }}
                          onPress={() => { setClassificationRef(o); setClsPickerOpen(false); }}
                        >
                          <Ionicons
                            name={tp === 'goal' ? 'flag' : tp === 'milestone' ? 'flag-outline' : tp === 'deliverable' ? 'cube' : tp === 'work_package' ? 'briefcase' : 'git-branch'}
                            size={14} color="#4F46E5"
                          />
                          <Text style={{ flex: 1, fontSize: 13, color: COLORS.textPrimary }} numberOfLines={1}>{o.label}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  );
                })}
                {clsOptions.length === 0 && (
                  <Text style={{ fontSize: 12, color: COLORS.textMuted, textAlign: 'center', marginVertical: 24 }}>
                    Nothing to link yet — create Goals (Goal Setter), PM nodes (GEM PM) or other CTT tasks first.
                  </Text>
                )}
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, paddingBottom: 18 },
  backBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(15,23,42,0.06)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFFFFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.85)', marginTop: 2, textTransform: 'capitalize' },
  deleteBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center' },

  section: { paddingHorizontal: 16, paddingVertical: 12 },

  // Section header (accordion)
  sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 14, backgroundColor: COLORS.white, borderTopWidth: 1, borderTopColor: COLORS.divider, marginTop: 4 },
  sectionLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  sectionBadge: { backgroundColor: COLORS.primary + '20', paddingHorizontal: 8, paddingVertical: 1, borderRadius: 10 },
  sectionBadgeText: { fontSize: 11, fontWeight: '700', color: COLORS.primary },

  label: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12, marginBottom: 6 },
  input: { backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 14, paddingVertical: 12, fontSize: 14, color: COLORS.textPrimary },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chipText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },

  priorityChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: COLORS.white },
  statusChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: COLORS.white },

  // Life area grid
  lifeAreaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  lifeAreaChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 12, borderWidth: 1.5, borderColor: COLORS.primary + '30', backgroundColor: COLORS.primary + '08', minWidth: '45%' },
  lifeAreaActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  lifeAreaText: { fontSize: 12, fontWeight: '600', color: COLORS.primary },

  // Decision type
  decisionChip: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 10, borderRadius: 12, borderWidth: 1.5, flex: 1, justifyContent: 'center' },
  decisionText: { fontSize: 13, fontWeight: '700' },

  // Row
  row: { flexDirection: 'row', gap: 10 },

  // Routine
  routineRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 4 },
  routineLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  routineHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  freqChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: COLORS.white },
  freqActive: { backgroundColor: '#F1F5F9', borderColor: '#F1F5F9' },

  // Bottom
  bottom: { padding: 16, paddingBottom: Platform.OS === 'ios' ? 20 : 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white },
  calendarSyncBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#E8F0FE', borderRadius: 10, paddingVertical: 10, marginBottom: 8, borderWidth: 1, borderColor: '#4285F430' },
  calendarSyncText: { fontSize: 13, fontWeight: '600', color: '#4285F4' },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#F1F5F9', borderRadius: 14, paddingVertical: 16 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: '#0F172A' },
});
