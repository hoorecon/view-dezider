import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Modal, TextInput,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import TimestampLine from '../../src/components/TimestampLine';

const LIFE_AREAS = [
  { id: 'holistic_health', name: 'Holistic Health', icon: 'fitness', color: '#10B981' },
  { id: 'knowledge_skills', name: 'Knowledge & Skills', icon: 'school', color: '#3B82F6' },
  { id: 'relationships', name: 'Relationships', icon: 'heart', color: '#EC4899' },
  { id: 'finance', name: 'Finance', icon: 'cash', color: '#F59E0B' },
  { id: 'assets', name: 'Assets', icon: 'home', color: '#8B5CF6' },
  { id: 'career', name: 'Career', icon: 'briefcase', color: '#0EA5E9' },
  { id: 'personal_dreams', name: 'Personal Dreams', icon: 'star', color: '#F97316' },
  { id: 'social_image', name: 'Social Image', icon: 'people', color: '#6366F1' },
  { id: 'social_contributions', name: 'Social Contributions', icon: 'hand-left', color: '#14B8A6' },
  { id: 'spirituality', name: 'Spirituality', icon: 'leaf', color: '#A855F7' },
];

const DAY_TYPES = [
  { id: 'weekday', label: 'Weekday', icon: 'briefcase' },
  { id: 'saturday', label: 'Saturday', icon: 'sunny' },
  { id: 'sunday', label: 'Sunday', icon: 'moon' },
];

type Allocation = { hours: number; priority: string; notes: string };
type Allocations = Record<string, Record<string, Allocation>>;

const emptyAllocations = (): Allocations => {
  const allocs: Allocations = {};
  DAY_TYPES.forEach(dt => {
    allocs[dt.id] = {};
    LIFE_AREAS.forEach(la => {
      allocs[dt.id][la.id] = { hours: 0, priority: 'medium', notes: '' };
    });
  });
  return allocs;
};

export default function LifestyleDesignerScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [plans, setPlans] = useState<any[]>([]);
  const [activePlan, setActivePlan] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [compLoading, setCompLoading] = useState(false);

  // Tabs
  const [tab, setTab] = useState<'plans' | 'comparison'>('plans');

  // Plan modal
  const [showPlanModal, setShowPlanModal] = useState(false);
  const [editPlan, setEditPlan] = useState<any>(null);
  const [planForm, setPlanForm] = useState({ name: '', description: '' });
  const [allocations, setAllocations] = useState<Allocations>(emptyAllocations());
  const [activeDayType, setActiveDayType] = useState('weekday');
  const [saving, setSaving] = useState(false);

  const fetchData = async () => {
    try {
      const [plansRes, activeRes] = await Promise.all([
        api.get('/lifestyle-designer/plans'),
        api.get('/lifestyle-designer/active-plan'),
      ]);
      setPlans(plansRes.data || []);
      setActivePlan(activeRes.data?.active_plan || null);
    } catch (e) { console.error('LD fetch error:', e); }
    finally { setLoading(false); }
  };

  const fetchComparison = async () => {
    setCompLoading(true);
    try {
      const res = await api.get('/lifestyle-designer/comparison?days=7');
      setComparison(res.data);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'No active plan or no data';
      setComparison(null);
      if (tab === 'comparison') showAlert('Info', msg);
    }
    finally { setCompLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, []));

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    if (tab === 'comparison') await fetchComparison();
    setRefreshing(false);
  };

  const openCreateModal = () => {
    setEditPlan(null);
    setPlanForm({ name: '', description: '' });
    setAllocations(emptyAllocations());
    setActiveDayType('weekday');
    setShowPlanModal(true);
  };

  const openEditModal = async (plan: any) => {
    setEditPlan(plan);
    setPlanForm({ name: plan.name || '', description: plan.description || '' });
    setAllocations(plan.allocations || emptyAllocations());
    setActiveDayType('weekday');
    setShowPlanModal(true);
  };

  const handleSavePlan = async () => {
    if (!planForm.name.trim()) return showAlert('Error', 'Plan name is required');
    setSaving(true);
    try {
      const payload = { ...planForm, allocations, is_active: !editPlan };
      if (editPlan) {
        await api.put(`/lifestyle-designer/plans/${editPlan.plan_id}`, payload);
      } else {
        await api.post('/lifestyle-designer/plans', payload);
      }
      setShowPlanModal(false);
      fetchData();
    } catch (e) { showAlert('Error', 'Failed to save plan'); }
    finally { setSaving(false); }
  };

  const handleActivate = async (planId: string) => {
    try {
      await api.post(`/lifestyle-designer/plans/${planId}/activate`, {});
      showAlert('Success', 'Plan activated!');
      fetchData();
    } catch (e) { showAlert('Error', 'Failed to activate'); }
  };

  const handleDelete = (planId: string) => {
    showAlert('Delete', 'Delete this plan?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/lifestyle-designer/plans/${planId}`); fetchData(); }
        catch (e) { showAlert('Error', 'Failed to delete'); }
      }},
    ]);
  };

  const updateAreaHours = (area: string, value: string) => {
    const hrs = Math.min(24, Math.max(0, parseFloat(value) || 0));
    setAllocations(prev => ({
      ...prev,
      [activeDayType]: {
        ...prev[activeDayType],
        [area]: { ...(prev[activeDayType]?.[area] || { hours: 0, priority: 'medium', notes: '' }), hours: hrs },
      },
    }));
  };

  const getTotalHours = (dt: string): number => {
    return LIFE_AREAS.reduce((sum, la) => {
      const h = allocations[dt]?.[la.id]?.hours || 0;
      return sum + h;
    }, 0);
  };

  // ─── RENDER ────────────────────────────────────────────

  const renderPlansTab = () => (
    <>
      {/* Active Plan Banner */}
      {activePlan ? (
        <LinearGradient colors={['#059669', '#10B981']} style={s.activeBanner}>
          <Ionicons name="checkmark-circle" size={24} color="#FFF" />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={s.activeName}>{activePlan.name}</Text>
            <Text style={s.activeSub}>Active Plan</Text>
          </View>
          <TouchableOpacity onPress={() => { setTab('comparison'); fetchComparison(); }}>
            <View style={s.compareBtn}>
              <Ionicons name="bar-chart" size={16} color="#059669" />
              <Text style={s.compareBtnText}>Compare</Text>
            </View>
          </TouchableOpacity>
        </LinearGradient>
      ) : (
        <View style={s.noPlanBanner}>
          <Ionicons name="information-circle" size={20} color="#F59E0B" />
          <Text style={s.noPlanText}>No active plan. Create one to start tracking!</Text>
        </View>
      )}

      {/* Plan Cards */}
      <View style={s.planListHeader}>
        <Text style={s.sectionTitle}>My Plans ({plans.length})</Text>
        <TouchableOpacity style={s.createBtn} onPress={openCreateModal}>
          <Ionicons name="add" size={18} color="#FFF" />
          <Text style={s.createBtnText}>New Plan</Text>
        </TouchableOpacity>
      </View>

      {plans.length === 0 ? (
        <View style={s.emptyState}>
          <Ionicons name="color-palette-outline" size={48} color="#9CA3AF" />
          <Text style={s.emptyTitle}>No Lifestyle Plans Yet</Text>
          <Text style={s.emptySub}>Design your ideal day by allocating hours to each life area</Text>
        </View>
      ) : (
        plans.map(plan => (
          <View key={plan.plan_id} style={[s.planCard, plan.is_active && { borderColor: '#10B981', borderWidth: 1.5 }]}>
            <View style={s.planCardHeader}>
              <View style={{ flex: 1 }}>
                <Text style={s.planName}>{plan.name}</Text>
                {plan.description ? <Text style={s.planDesc}>{plan.description}</Text> : null}
                <TimestampLine entity={plan} compact />
              </View>
              {plan.is_active && (
                <View style={s.activeTag}>
                  <Text style={s.activeTagText}>Active</Text>
                </View>
              )}
            </View>

            {/* Quick allocation summary */}
            <View style={s.allocSummary}>
              {DAY_TYPES.map(dt => {
                const allocs = plan.allocations?.[dt.id] || {};
                const total = LIFE_AREAS.reduce((sum, la) => {
                  const a = allocs[la.id];
                  return sum + (a?.hours || 0);
                }, 0);
                return (
                  <View key={dt.id} style={s.allocSumItem}>
                    <Text style={s.allocSumLabel}>{dt.label}</Text>
                    <Text style={[s.allocSumHrs, total > 24 && { color: '#EF4444' }]}>
                      {total.toFixed(1)}h
                    </Text>
                  </View>
                );
              })}
            </View>

            {/* Top 3 areas by hours */}
            <View style={s.topAreasRow}>
              {LIFE_AREAS
                .map(la => ({ ...la, hrs: plan.allocations?.weekday?.[la.id]?.hours || 0 }))
                .sort((a, b) => b.hrs - a.hrs)
                .slice(0, 4)
                .filter(a => a.hrs > 0)
                .map(a => (
                  <View key={a.id} style={[s.topAreaChip, { backgroundColor: a.color + '20' }]}>
                    <Ionicons name={a.icon as any} size={12} color={a.color} />
                    <Text style={[s.topAreaText, { color: a.color }]}>{a.hrs}h</Text>
                  </View>
                ))}
            </View>

            <View style={s.planActions}>
              {!plan.is_active && (
                <TouchableOpacity style={s.actionBtn} onPress={() => handleActivate(plan.plan_id)}>
                  <Ionicons name="checkmark-circle" size={16} color="#10B981" />
                  <Text style={[s.actionText, { color: '#10B981' }]}>Activate</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity style={s.actionBtn} onPress={() => openEditModal(plan)}>
                <Ionicons name="pencil" size={16} color="#3B82F6" />
                <Text style={[s.actionText, { color: '#3B82F6' }]}>Edit</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.actionBtn} onPress={() => handleDelete(plan.plan_id)}>
                <Ionicons name="trash" size={16} color="#EF4444" />
                <Text style={[s.actionText, { color: '#EF4444' }]}>Delete</Text>
              </TouchableOpacity>
            </View>
          </View>
        ))
      )}
    </>
  );

  const renderComparisonTab = () => {
    if (compLoading) return <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />;
    if (!comparison) {
      return (
        <View style={s.emptyState}>
          <Ionicons name="bar-chart-outline" size={48} color="#9CA3AF" />
          <Text style={s.emptyTitle}>No Comparison Data</Text>
          <Text style={s.emptySub}>Activate a plan and log LEE activities to see comparison</Text>
          <TouchableOpacity style={[s.createBtn, { marginTop: 16 }]} onPress={() => setTab('plans')}>
            <Text style={s.createBtnText}>Go to Plans</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return (
      <>
        <Text style={s.sectionTitle}>
          Planned vs Actual — {comparison.plan_name} ({comparison.days_analyzed} days)
        </Text>

        {/* Day Type Tabs */}
        <View style={s.dtTabs}>
          {DAY_TYPES.map(dt => (
            <TouchableOpacity
              key={dt.id}
              style={[s.dtTab, activeDayType === dt.id && s.dtTabActive]}
              onPress={() => setActiveDayType(dt.id)}
            >
              <Ionicons name={dt.icon as any} size={14} color={activeDayType === dt.id ? '#FFF' : '#94A3B8'} />
              <Text style={[s.dtTabText, activeDayType === dt.id && { color: '#FFF' }]}>{dt.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Comparison Areas */}
        {(comparison.comparison?.[activeDayType]?.areas || []).map((area: any) => {
          const barWidth = Math.min(100, area.achievement_pct);
          const barColor = area.status === 'on_track' ? '#10B981' : area.status === 'over' ? '#F59E0B' : '#EF4444';
          return (
            <View key={area.area_id} style={s.compRow}>
              <View style={s.compHeader}>
                <Ionicons name={area.icon as any} size={18} color={area.color} />
                <Text style={s.compAreaName}>{area.area_name}</Text>
                <View style={[s.compStatusBadge, { backgroundColor: barColor + '20' }]}>
                  <Text style={[s.compStatusText, { color: barColor }]}>
                    {area.status === 'on_track' ? 'On Track' : area.status === 'over' ? 'Over' : 'Under'}
                  </Text>
                </View>
              </View>
              <View style={s.compBarBg}>
                <View style={[s.compBarFill, { width: `${barWidth}%`, backgroundColor: barColor }]} />
              </View>
              <View style={s.compNums}>
                <Text style={s.compNumLabel}>
                  Planned: <Text style={{ color: '#FFF', fontWeight: '700' }}>{area.planned_hours}h</Text>
                </Text>
                <Text style={s.compNumLabel}>
                  Actual: <Text style={{ color: '#FFF', fontWeight: '700' }}>{area.actual_hours}h</Text>
                </Text>
                <Text style={[s.compGap, { color: barColor }]}>
                  {area.gap_hours > 0 ? '+' : ''}{area.gap_hours}h ({area.achievement_pct}%)
                </Text>
              </View>
            </View>
          );
        })}

        {/* Totals */}
        {comparison.comparison?.[activeDayType] && (
          <View style={s.totalRow}>
            <Text style={s.totalLabel}>Total</Text>
            <Text style={s.totalVal}>
              Planned: {comparison.comparison[activeDayType].total_planned_hours?.toFixed(1)}h
              {'   '}
              Actual: {comparison.comparison[activeDayType].total_actual_hours?.toFixed(1)}h
            </Text>
          </View>
        )}
      </>
    );
  };

  const renderPlanModal = () => (
    <Modal visible={showPlanModal} animationType="slide" transparent>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={s.modalOverlay}
      >
        <View style={s.modalContent}>
          <View style={s.modalHeader}>
            <Text style={s.modalTitle}>{editPlan ? 'Edit Plan' : 'New Lifestyle Plan'}</Text>
            <TouchableOpacity onPress={() => setShowPlanModal(false)}>
              <Ionicons name="close" size={24} color="#6B7280" />
            </TouchableOpacity>
          </View>

          <ScrollView style={{ maxHeight: 520 }} showsVerticalScrollIndicator={false}>
            <Text style={s.fieldLabel}>Plan Name *</Text>
            <TextInput
              style={s.input} placeholder="e.g., My Ideal Weekday"
              value={planForm.name} onChangeText={t => setPlanForm({ ...planForm, name: t })}
              placeholderTextColor="#9CA3AF"
            />

            <Text style={s.fieldLabel}>Description</Text>
            <TextInput
              style={[s.input, { height: 50, textAlignVertical: 'top' }]}
              multiline placeholder="Brief description..."
              value={planForm.description} onChangeText={t => setPlanForm({ ...planForm, description: t })}
              placeholderTextColor="#9CA3AF"
            />

            {/* Day Type Tabs */}
            <Text style={s.fieldLabel}>Hour Allocations</Text>
            <View style={s.dtTabs}>
              {DAY_TYPES.map(dt => {
                const total = getTotalHours(dt.id);
                return (
                  <TouchableOpacity
                    key={dt.id}
                    style={[s.dtTab, activeDayType === dt.id && s.dtTabActive]}
                    onPress={() => setActiveDayType(dt.id)}
                  >
                    <Text style={[s.dtTabText, activeDayType === dt.id && { color: '#FFF' }]}>
                      {dt.label} ({total.toFixed(1)}h)
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {getTotalHours(activeDayType) > 24 && (
              <View style={s.warningBar}>
                <Ionicons name="warning" size={14} color="#FFF" />
                <Text style={s.warningText}>Total exceeds 24h! Adjust allocations.</Text>
              </View>
            )}

            {/* Area allocation inputs */}
            {LIFE_AREAS.map(la => {
              const val = allocations[activeDayType]?.[la.id]?.hours || 0;
              return (
                <View key={la.id} style={s.allocRow}>
                  <View style={[s.allocIcon, { backgroundColor: la.color + '20' }]}>
                    <Ionicons name={la.icon as any} size={16} color={la.color} />
                  </View>
                  <Text style={s.allocName} numberOfLines={1}>{la.name}</Text>
                  <View style={s.allocInputWrap}>
                    <TouchableOpacity
                      style={s.incBtn}
                      onPress={() => updateAreaHours(la.id, String(Math.max(0, val - 0.5)))}
                    >
                      <Ionicons name="remove" size={14} color="#94A3B8" />
                    </TouchableOpacity>
                    <TextInput
                      style={s.allocInput}
                      keyboardType="decimal-pad"
                      value={val > 0 ? String(val) : ''}
                      placeholder="0"
                      onChangeText={t => updateAreaHours(la.id, t)}
                      placeholderTextColor="#6B7280"
                    />
                    <TouchableOpacity
                      style={s.incBtn}
                      onPress={() => updateAreaHours(la.id, String(val + 0.5))}
                    >
                      <Ionicons name="add" size={14} color="#94A3B8" />
                    </TouchableOpacity>
                    <Text style={s.hrsLabel}>hrs</Text>
                  </View>
                </View>
              );
            })}
          </ScrollView>

          <TouchableOpacity
            style={[s.saveBtn, saving && { opacity: 0.6 }]}
            onPress={handleSavePlan} disabled={saving}
          >
            {saving ? <ActivityIndicator color="#FFF" /> : (
              <Text style={s.saveBtnText}>{editPlan ? 'Update Plan' : 'Create Plan'}</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );

  if (loading) {
    return (
      <SafeAreaView style={s.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container}>
      <ScrollView
        contentContainerStyle={{ padding: 16, paddingBottom: 120 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Header */}
        <View style={s.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Lifestyle Designer</Text>
          <TouchableOpacity onPress={openCreateModal}>
            <Ionicons name="add-circle" size={28} color="#FFF" />
          </TouchableOpacity>
        </View>

        <LinearGradient colors={['#FFFFFF', '#F8FAFC']} style={s.heroBanner}>
          <Ionicons name="color-palette" size={32} color="#A78BFA" />
          <View style={{ marginLeft: 12, flex: 1 }}>
            <Text style={s.heroTitle}>Design Your Ideal Lifestyle</Text>
            <Text style={s.heroSub}>Allocate hours per life area. Compare planned vs actual.</Text>
          </View>
        </LinearGradient>

        {/* Tab Switcher */}
        <View style={s.tabRow}>
          <TouchableOpacity
            style={[s.tabBtn, tab === 'plans' && s.tabBtnActive]}
            onPress={() => setTab('plans')}
          >
            <Ionicons name="document-text" size={16} color={tab === 'plans' ? '#FFF' : '#94A3B8'} />
            <Text style={[s.tabBtnText, tab === 'plans' && { color: '#FFF' }]}>Plans</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[s.tabBtn, tab === 'comparison' && s.tabBtnActive]}
            onPress={() => { setTab('comparison'); fetchComparison(); }}
          >
            <Ionicons name="bar-chart" size={16} color={tab === 'comparison' ? '#FFF' : '#94A3B8'} />
            <Text style={[s.tabBtnText, tab === 'comparison' && { color: '#FFF' }]}>Compare</Text>
          </TouchableOpacity>
        </View>

        {tab === 'plans' ? renderPlansTab() : renderComparisonTab()}
      </ScrollView>

      {renderPlanModal()}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  headerTitle: { color: '#0F172A', fontSize: 18, fontWeight: '700', flex: 1, marginLeft: 12 },
  heroBanner: { borderRadius: 16, padding: 16, flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  heroTitle: { color: '#0F172A', fontSize: 16, fontWeight: '700' },
  heroSub: { color: '#94A3B8', fontSize: 12, marginTop: 4 },

  // Tabs
  tabRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  tabBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, backgroundColor: '#FFFFFF' },
  tabBtnActive: { backgroundColor: '#6366F1' },
  tabBtnText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },

  // Active Banner
  activeBanner: { borderRadius: 14, padding: 14, flexDirection: 'row', alignItems: 'center', marginBottom: 16 },
  activeName: { color: '#0F172A', fontSize: 15, fontWeight: '700' },
  activeSub: { color: 'rgba(255,255,255,0.7)', fontSize: 12 },
  compareBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#FFF', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6 },
  compareBtnText: { color: '#059669', fontSize: 12, fontWeight: '600' },

  noPlanBanner: { backgroundColor: '#78350F', borderRadius: 10, padding: 12, flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 16 },
  noPlanText: { color: '#FDE68A', fontSize: 13, flex: 1 },

  // Section
  sectionTitle: { color: '#0F172A', fontSize: 16, fontWeight: '700', marginBottom: 12, marginTop: 4 },
  planListHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  createBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#6366F1', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8 },
  createBtnText: { color: '#0F172A', fontSize: 13, fontWeight: '600' },

  // Empty
  emptyState: { alignItems: 'center', paddingVertical: 40 },
  emptyTitle: { color: '#9CA3AF', fontSize: 16, fontWeight: '600', marginTop: 12 },
  emptySub: { color: '#6B7280', fontSize: 13, marginTop: 4, textAlign: 'center', paddingHorizontal: 24 },

  // Plan Card
  planCard: { backgroundColor: '#FFFFFF', borderRadius: 14, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: 'transparent' },
  planCardHeader: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: 10 },
  planName: { color: '#0F172A', fontSize: 15, fontWeight: '700' },
  planDesc: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  activeTag: { backgroundColor: '#059669', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  activeTagText: { color: '#0F172A', fontSize: 11, fontWeight: '700' },

  allocSummary: { flexDirection: 'row', gap: 12, marginBottom: 8 },
  allocSumItem: { flex: 1, alignItems: 'center' },
  allocSumLabel: { color: '#6B7280', fontSize: 11 },
  allocSumHrs: { color: '#0F172A', fontSize: 14, fontWeight: '700' },

  topAreasRow: { flexDirection: 'row', gap: 6, marginBottom: 10, flexWrap: 'wrap' },
  topAreaChip: { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  topAreaText: { fontSize: 11, fontWeight: '600' },

  planActions: { flexDirection: 'row', gap: 12, borderTopWidth: 1, borderTopColor: '#334155', paddingTop: 10 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  actionText: { fontSize: 12, fontWeight: '600' },

  // Comparison
  dtTabs: { flexDirection: 'row', gap: 6, marginBottom: 12 },
  dtTab: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8, backgroundColor: '#FFFFFF', flexDirection: 'row', justifyContent: 'center', gap: 4 },
  dtTabActive: { backgroundColor: '#6366F1' },
  dtTabText: { color: '#94A3B8', fontSize: 12, fontWeight: '600' },

  compRow: { backgroundColor: '#FFFFFF', borderRadius: 12, padding: 12, marginBottom: 8 },
  compHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  compAreaName: { color: '#0F172A', fontSize: 13, fontWeight: '600', flex: 1 },
  compStatusBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  compStatusText: { fontSize: 11, fontWeight: '600' },
  compBarBg: { height: 6, borderRadius: 3, backgroundColor: '#334155', overflow: 'hidden' },
  compBarFill: { height: 6, borderRadius: 3 },
  compNums: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 },
  compNumLabel: { color: '#94A3B8', fontSize: 11 },
  compGap: { fontSize: 11, fontWeight: '700' },

  totalRow: { backgroundColor: '#FFFFFF', borderRadius: 12, padding: 14, marginTop: 4, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  totalLabel: { color: '#0F172A', fontSize: 14, fontWeight: '700' },
  totalVal: { color: '#94A3B8', fontSize: 12, fontWeight: '600' },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '90%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { color: '#0F172A', fontSize: 18, fontWeight: '700' },
  fieldLabel: { color: '#94A3B8', fontSize: 12, fontWeight: '600', marginBottom: 6, marginTop: 8 },
  input: { backgroundColor: '#F8FAFC', borderRadius: 10, borderWidth: 1, borderColor: '#334155', color: '#0F172A', paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, marginBottom: 4 },

  warningBar: { backgroundColor: '#DC2626', borderRadius: 8, padding: 8, flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  warningText: { color: '#0F172A', fontSize: 12, fontWeight: '600' },

  allocRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#FFFFFF' },
  allocIcon: { width: 32, height: 32, borderRadius: 8, justifyContent: 'center', alignItems: 'center', marginRight: 8 },
  allocName: { color: '#475569', fontSize: 13, flex: 1 },
  allocInputWrap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  incBtn: { width: 28, height: 28, borderRadius: 6, backgroundColor: '#F8FAFC', justifyContent: 'center', alignItems: 'center' },
  allocInput: { width: 48, textAlign: 'center', backgroundColor: '#F8FAFC', borderRadius: 6, color: '#0F172A', fontSize: 14, fontWeight: '600', paddingVertical: 4, borderWidth: 1, borderColor: '#334155' },
  hrsLabel: { color: '#6B7280', fontSize: 11, marginLeft: 2 },

  saveBtn: { backgroundColor: '#6366F1', borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 12 },
  saveBtnText: { color: '#0F172A', fontSize: 16, fontWeight: '700' },
});
