import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert, ActivityIndicator, Platform, KeyboardAvoidingView, Switch,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const LIFE_AREAS = [
  { id: 'career', name: 'Career', icon: 'briefcase' },
  { id: 'finance', name: 'Finance', icon: 'cash' },
  { id: 'relationships', name: 'Relationships', icon: 'heart' },
  { id: 'holistic_health', name: 'Holistic Health', icon: 'fitness' },
  { id: 'assets', name: 'Assets', icon: 'home' },
  { id: 'knowledge_skills', name: 'Knowledge & Skills', icon: 'school' },
  { id: 'social_image', name: 'Social Image', icon: 'people' },
  { id: 'social_contributions', name: 'Social Contributions', icon: 'hand-left' },
  { id: 'hobbies_entertainment', name: 'Hobbies', icon: 'game-controller' },
  { id: 'spirituality_religion', name: 'Spirituality', icon: 'leaf' },
];

const PRIORITIES = [
  { id: 'critical', label: 'Critical', color: '#EF4444', icon: 'alert-circle' },
  { id: 'high', label: 'High', color: '#F59E0B', icon: 'warning' },
  { id: 'medium', label: 'Medium', color: '#3B82F6', icon: 'remove-circle' },
  { id: 'low', label: 'Low', color: '#6B7280', icon: 'arrow-down-circle' },
];

const STATUSES = [
  { id: 'open', label: 'Open', color: '#6B7280', icon: 'radio-button-off' },
  { id: 'in_progress', label: 'In Progress', color: '#3B82F6', icon: 'time' },
  { id: 'done', label: 'Done', color: '#10B981', icon: 'checkmark-circle' },
  { id: 'blocked', label: 'Blocked', color: '#EF4444', icon: 'close-circle' },
  { id: 'cancelled', label: 'Cancelled', color: '#9CA3AF', icon: 'ban' },
];

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
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const editId = id as string | undefined;
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [expandedSection, setExpandedSection] = useState<string>('basic');

  // Form state
  const [task, setTask] = useState('');
  const [subTask, setSubTask] = useState('');
  const [status, setStatus] = useState('open');
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

  useEffect(() => {
    if (editId) loadTask();
  }, [editId]);

  const loadTask = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/ctt/tasks/${editId}`);
      const d = res.data;
      setTask(d.task || '');
      setSubTask(d.sub_task || '');
      setStatus(d.current_status || 'open');
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
    } catch (e) {
      Alert.alert('Error', 'Failed to load task');
      router.back();
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!task.trim()) {
      Alert.alert('Required', 'Task name is required');
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
      };
      if (editId) {
        await api.put(`/ctt/tasks/${editId}`, payload);
      } else {
        await api.post('/ctt/tasks', payload);
      }
      router.back();
    } catch (e) {
      Alert.alert('Error', 'Failed to save task');
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
        <LinearGradient colors={['#1E3A5F', '#2D5F8B']} style={st.header}>
          <TouchableOpacity onPress={() => router.back()} style={st.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
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
              onPress={() => Alert.alert('Delete', 'Delete this task?', [
                { text: 'Cancel', style: 'cancel' },
                { text: 'Delete', style: 'destructive', onPress: async () => {
                  try { await api.delete(`/ctt/tasks/${editId}`); router.back(); }
                  catch (e) { Alert.alert('Error', 'Failed to delete'); }
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
            </View>
          )}
        </ScrollView>

        {/* Sticky Save Button */}
        <View style={st.bottom}>
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
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, paddingBottom: 18 },
  backBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2, textTransform: 'capitalize' },
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
  freqActive: { backgroundColor: '#1E3A5F', borderColor: '#1E3A5F' },

  // Bottom
  bottom: { padding: 16, paddingBottom: Platform.OS === 'ios' ? 20 : 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1E3A5F', borderRadius: 14, paddingVertical: 16 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
