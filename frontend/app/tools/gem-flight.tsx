import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, Alert, ActivityIndicator, TextInput, Modal,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const LIFE_AREAS = [
  { id: 'career', label: 'Career', icon: 'briefcase', color: '#3B82F6' },
  { id: 'finance', label: 'Finance', icon: 'cash', color: '#10B981' },
  { id: 'relationships', label: 'Relationships', icon: 'heart', color: '#EF4444' },
  { id: 'holistic_health', label: 'Health', icon: 'fitness', color: '#F59E0B' },
  { id: 'assets', label: 'Assets', icon: 'home', color: '#8B5CF6' },
  { id: 'knowledge_skills', label: 'Knowledge', icon: 'school', color: '#06B6D4' },
  { id: 'social_image', label: 'Social', icon: 'people', color: '#EC4899' },
  { id: 'spirituality', label: 'Spirituality', icon: 'leaf', color: '#84CC16' },
];

const STATUS_COLORS: Record<string, string> = {
  active: '#10B981',
  paused: '#F59E0B',
  completed: '#3B82F6',
  abandoned: '#EF4444',
};

const PHASE_ICONS: Record<string, string> = {
  pre_flight: 'settings-outline',
  takeoff: 'arrow-up-circle',
  climbing: 'trending-up',
  cruise: 'airplane',
  descent: 'trending-down',
  landed: 'flag',
  taxiing: 'walk',
};

interface FlightProject {
  project_id: string;
  title: string;
  vision: string;
  goal: string;
  life_area: string;
  current_step: number;
  progress_percent: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export default function GemFlightScreen() {
  const router = useRouter();
  const [projects, setProjects] = useState<FlightProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    title: '',
    vision: '',
    goal: '',
    point_a: '',
    point_b: '',
    life_area: '',
    specific: '',
    measurable: '',
    achievable: '',
    realistic: '',
    time_bound: '',
  });

  const fetchProjects = async () => {
    try {
      const res = await api.get('/gem-flight/projects');
      setProjects(res.data.projects || []);
    } catch (e) {
      console.error('Error fetching flight projects:', e);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchProjects(); }, []));
  const onRefresh = async () => { setRefreshing(true); await fetchProjects(); setRefreshing(false); };

  const createProject = async () => {
    if (!form.title.trim()) {
      Alert.alert('Required', 'Please enter a project title');
      return;
    }
    setCreating(true);
    try {
      const res = await api.post('/gem-flight/projects', form);
      setShowCreate(false);
      setForm({ title: '', vision: '', goal: '', point_a: '', point_b: '', life_area: '', specific: '', measurable: '', achievable: '', realistic: '', time_bound: '' });
      router.push(`/tools/gem-flight-detail?id=${res.data.project_id}` as any);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail || 'Failed to create project');
    } finally {
      setCreating(false);
    }
  };

  const deleteProject = (id: string) => {
    Alert.alert('Delete Flight', 'Are you sure you want to delete this flight project?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try {
            await api.delete(`/gem-flight/projects/${id}`);
            fetchProjects();
          } catch { Alert.alert('Error', 'Failed to delete'); }
        }
      },
    ]);
  };

  const getPhaseForStep = (step: number, status: string) => {
    if (status === 'completed') return 'landed';
    if (step <= 2) return 'pre_flight';
    if (step <= 4) return 'takeoff';
    if (step === 5) return 'climbing';
    if (step === 6) return 'cruise';
    if (step === 7) return 'descent';
    return 'taxiing';
  };

  if (loading) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.loadingWrap}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <LinearGradient colors={['#0C1445', '#1A237E', '#283593']} style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>GEM Flight Model</Text>
          <Text style={s.headerSub}>Navigate your goals like a pilot</Text>
        </View>
        <TouchableOpacity onPress={() => setShowCreate(true)} style={s.addBtn}>
          <Ionicons name="add" size={24} color="#FFF" />
        </TouchableOpacity>
      </LinearGradient>

      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {projects.length === 0 ? (
          <View style={s.emptyState}>
            <Ionicons name="airplane-outline" size={64} color={COLORS.textMuted} />
            <Text style={s.emptyTitle}>No Flight Projects Yet</Text>
            <Text style={s.emptyDesc}>
              Create your first flight project to navigate from where you are (Point A) to where you want to be (Point B).
            </Text>
            <TouchableOpacity style={s.createBtn} onPress={() => setShowCreate(true)}>
              <LinearGradient colors={['#1A237E', '#3949AB']} style={s.createGradient}>
                <Ionicons name="airplane" size={20} color="#FFF" />
                <Text style={s.createBtnText}>Launch Your First Flight</Text>
              </LinearGradient>
            </TouchableOpacity>
          </View>
        ) : (
          projects.map((proj) => {
            const phase = getPhaseForStep(proj.current_step, proj.status);
            const areaInfo = LIFE_AREAS.find(a => a.id === proj.life_area);
            return (
              <TouchableOpacity
                key={proj.project_id}
                style={s.projectCard}
                onPress={() => router.push(`/tools/gem-flight-detail?id=${proj.project_id}` as any)}
                onLongPress={() => deleteProject(proj.project_id)}
                activeOpacity={0.7}
              >
                <LinearGradient
                  colors={proj.status === 'completed' ? ['#059669', '#10B981'] : ['#1E293B', '#334155']}
                  style={s.projectGradient}
                >
                  {/* Top Row: Icon + Title + Status */}
                  <View style={s.projectTop}>
                    <View style={[s.phaseIcon, { backgroundColor: STATUS_COLORS[proj.status] + '30' }]}>
                      <Ionicons
                        name={(PHASE_ICONS[phase] || 'airplane') as any}
                        size={24}
                        color={STATUS_COLORS[proj.status]}
                      />
                    </View>
                    <View style={{ flex: 1, marginLeft: 12 }}>
                      <Text style={s.projectTitle} numberOfLines={1}>{proj.title}</Text>
                      <View style={s.metaRow}>
                        {areaInfo && (
                          <View style={[s.badge, { backgroundColor: areaInfo.color + '30' }]}>
                            <Ionicons name={areaInfo.icon as any} size={12} color={areaInfo.color} />
                            <Text style={[s.badgeText, { color: areaInfo.color }]}>{areaInfo.label}</Text>
                          </View>
                        )}
                        <View style={[s.badge, { backgroundColor: STATUS_COLORS[proj.status] + '30' }]}>
                          <Text style={[s.badgeText, { color: STATUS_COLORS[proj.status] }]}>
                            {proj.status.toUpperCase()}
                          </Text>
                        </View>
                      </View>
                    </View>
                    <Ionicons name="chevron-forward" size={20} color="rgba(255,255,255,0.5)" />
                  </View>

                  {/* Flight Progress Bar */}
                  <View style={s.progressSection}>
                    <View style={s.progressTrack}>
                      <View style={[s.progressFill, { width: `${proj.progress_percent}%` }]} />
                      <View style={[s.planeMarker, { left: `${Math.max(5, proj.progress_percent - 3)}%` }]}>
                        <Text style={s.planeEmoji}>✈️</Text>
                      </View>
                    </View>
                    <View style={s.progressLabels}>
                      <Text style={s.progressLabel}>Step {proj.current_step}/7</Text>
                      <Text style={s.progressLabel}>{proj.progress_percent}%</Text>
                    </View>
                  </View>

                  {/* Goal preview */}
                  {proj.goal ? (
                    <Text style={s.goalPreview} numberOfLines={1}>
                      🎯 {proj.goal}
                    </Text>
                  ) : null}
                </LinearGradient>
              </TouchableOpacity>
            );
          })
        )}
      </ScrollView>

      {/* Create Modal */}
      <Modal visible={showCreate} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer} edges={['top']}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
            <View style={s.modalHeader}>
              <TouchableOpacity onPress={() => setShowCreate(false)}>
                <Ionicons name="close" size={28} color={COLORS.textPrimary} />
              </TouchableOpacity>
              <Text style={s.modalTitle}>Launch New Flight</Text>
              <TouchableOpacity onPress={createProject} disabled={creating}>
                {creating ? <ActivityIndicator size="small" color={COLORS.primary} /> :
                  <Text style={s.modalSave}>Launch</Text>}
              </TouchableOpacity>
            </View>

            <ScrollView style={s.modalScroll} contentContainerStyle={{ padding: 20, paddingBottom: 40 }}>
              <Text style={s.fieldLabel}>Project Title *</Text>
              <TextInput
                style={s.input}
                placeholder="e.g., Career Transition 2026"
                value={form.title}
                onChangeText={(t) => setForm({ ...form, title: t })}
                placeholderTextColor={COLORS.textMuted}
              />

              <Text style={s.fieldLabel}>Life Area</Text>
              <View style={s.areaGrid}>
                {LIFE_AREAS.map(a => (
                  <TouchableOpacity
                    key={a.id}
                    style={[s.areaChip, form.life_area === a.id && { backgroundColor: a.color + '20', borderColor: a.color }]}
                    onPress={() => setForm({ ...form, life_area: a.id })}
                  >
                    <Ionicons name={a.icon as any} size={16} color={form.life_area === a.id ? a.color : COLORS.textSecondary} />
                    <Text style={[s.areaChipText, form.life_area === a.id && { color: a.color }]}>{a.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={s.fieldLabel}>Vision</Text>
              <TextInput
                style={[s.input, { height: 60 }]}
                placeholder="Your big-picture vision for this goal..."
                value={form.vision}
                onChangeText={(t) => setForm({ ...form, vision: t })}
                multiline
                placeholderTextColor={COLORS.textMuted}
              />

              <Text style={s.fieldLabel}>Goal</Text>
              <TextInput
                style={s.input}
                placeholder="What exactly do you want to achieve?"
                value={form.goal}
                onChangeText={(t) => setForm({ ...form, goal: t })}
                placeholderTextColor={COLORS.textMuted}
              />

              <Text style={s.fieldLabel}>Point A (Where I Am Now)</Text>
              <TextInput
                style={s.input}
                placeholder="Describe your current situation..."
                value={form.point_a}
                onChangeText={(t) => setForm({ ...form, point_a: t })}
                placeholderTextColor={COLORS.textMuted}
              />

              <Text style={s.fieldLabel}>Point B (Where I Want to Be)</Text>
              <TextInput
                style={s.input}
                placeholder="Describe your desired destination..."
                value={form.point_b}
                onChangeText={(t) => setForm({ ...form, point_b: t })}
                placeholderTextColor={COLORS.textMuted}
              />

              {/* SMART Goal Section */}
              <View style={s.smartSection}>
                <Text style={s.sectionHeader}>SMART Goal Breakdown</Text>

                <Text style={s.fieldLabel}>Specific</Text>
                <TextInput style={s.input} placeholder="What exactly?" value={form.specific}
                  onChangeText={(t) => setForm({ ...form, specific: t })} placeholderTextColor={COLORS.textMuted} />

                <Text style={s.fieldLabel}>Measurable</Text>
                <TextInput style={s.input} placeholder="How will you measure success?" value={form.measurable}
                  onChangeText={(t) => setForm({ ...form, measurable: t })} placeholderTextColor={COLORS.textMuted} />

                <Text style={s.fieldLabel}>Achievable</Text>
                <TextInput style={s.input} placeholder="Is it realistically attainable?" value={form.achievable}
                  onChangeText={(t) => setForm({ ...form, achievable: t })} placeholderTextColor={COLORS.textMuted} />

                <Text style={s.fieldLabel}>Realistic</Text>
                <TextInput style={s.input} placeholder="Does it align with resources?" value={form.realistic}
                  onChangeText={(t) => setForm({ ...form, realistic: t })} placeholderTextColor={COLORS.textMuted} />

                <Text style={s.fieldLabel}>Time Bound (Deadline)</Text>
                <TextInput style={s.input} placeholder="YYYY-MM-DD" value={form.time_bound}
                  onChangeText={(t) => setForm({ ...form, time_bound: t })} placeholderTextColor={COLORS.textMuted} />
              </View>
            </ScrollView>
          </KeyboardAvoidingView>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0F172A' },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { paddingHorizontal: 16, paddingVertical: 16, flexDirection: 'row', alignItems: 'center' },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center', marginRight: 8 },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  addBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center' },
  scroll: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 40 },
  emptyState: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 32 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: '#FFF', marginTop: 16 },
  emptyDesc: { fontSize: 14, color: 'rgba(255,255,255,0.6)', textAlign: 'center', lineHeight: 22, marginTop: 8 },
  createBtn: { marginTop: 24, borderRadius: 14, overflow: 'hidden' },
  createGradient: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 24, paddingVertical: 14, gap: 8 },
  createBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  projectCard: { marginBottom: 16, borderRadius: 16, overflow: 'hidden' },
  projectGradient: { padding: 16 },
  projectTop: { flexDirection: 'row', alignItems: 'center' },
  phaseIcon: { width: 48, height: 48, borderRadius: 24, justifyContent: 'center', alignItems: 'center' },
  projectTitle: { fontSize: 17, fontWeight: '700', color: '#FFF' },
  metaRow: { flexDirection: 'row', gap: 8, marginTop: 4, flexWrap: 'wrap' },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  badgeText: { fontSize: 10, fontWeight: '700' },
  progressSection: { marginTop: 16 },
  progressTrack: { height: 6, backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 3, overflow: 'visible', position: 'relative' },
  progressFill: { height: '100%', backgroundColor: '#818CF8', borderRadius: 3 },
  planeMarker: { position: 'absolute', top: -10, zIndex: 1 },
  planeEmoji: { fontSize: 16 },
  progressLabels: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 },
  progressLabel: { fontSize: 12, color: 'rgba(255,255,255,0.6)', fontWeight: '600' },
  goalPreview: { fontSize: 12, color: 'rgba(255,255,255,0.5)', marginTop: 10 },
  // Modal
  modalContainer: { flex: 1, backgroundColor: COLORS.background },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  modalSave: { fontSize: 16, fontWeight: '700', color: COLORS.primary },
  modalScroll: { flex: 1 },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 6, marginTop: 14 },
  input: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, fontSize: 15, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border },
  areaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  areaChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: COLORS.white },
  areaChipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  smartSection: { marginTop: 16, paddingTop: 16, borderTopWidth: 1, borderTopColor: COLORS.border },
  sectionHeader: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
});
