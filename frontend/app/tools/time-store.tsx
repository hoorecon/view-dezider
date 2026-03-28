import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import Slider from '@react-native-community/slider';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const ACTION_CONFIG: Record<string, { color: string; bg: string; icon: string }> = {
  eliminate: { color: '#DC2626', bg: '#FEE2E2', icon: 'close-circle' },
  reduce: { color: '#16A34A', bg: '#DCFCE7', icon: 'contract' },
  delegate: { color: '#3B82F6', bg: '#DBEAFE', icon: 'people' },
  batch: { color: '#7C3AED', bg: '#F3E8FF', icon: 'layers' },
  automate: { color: '#D97706', bg: '#FEF3C7', icon: 'cog' },
};

const TEPFI_COLORS: Record<string, string> = {
  time: '#EF4444',
  effort: '#F59E0B',
  people: '#3B82F6',
  finance: '#10B981',
  infrastructure: '#7C3AED',
};

export default function TimeStoreScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [budget, setBudget] = useState<any>(null);
  const [desiredHours, setDesiredHours] = useState(2);
  const [period, setPeriod] = useState<'daily' | 'weekly'>('daily');
  const [analyzing, setAnalyzing] = useState(false);
  const [suggestions, setSuggestions] = useState<any>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const fetchBudget = async () => {
    try {
      const res = await api.get(`/time-store/budget?period=${period}`);
      setBudget(res.data);
    } catch (err) {
      console.error('Budget fetch error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchBudget(); }, [period]));

  const analyze = async () => {
    setAnalyzing(true);
    setSuggestions(null);
    setSelectedIds(new Set());
    try {
      const res = await api.post('/time-store/analyze', {
        desired_free_hours: desiredHours,
        period,
      });
      setSuggestions(res.data);
      // Auto-select all
      const ids = new Set<string>();
      (res.data?.suggestions || []).forEach((s: any) => ids.add(s.activity_id));
      setSelectedIds(ids);
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleSuggestion = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const applySuggestions = async () => {
    if (selectedIds.size === 0) {
      showAlert('Select Suggestions', 'Please select at least one suggestion to apply.');
      return;
    }
    const selected = (suggestions?.suggestions || []).filter((s: any) => selectedIds.has(s.activity_id));
    try {
      const res = await api.post('/time-store/apply', { suggestions: selected });
      showAlert('Applied', `${res.data.applied} optimizations applied.`);
      setSuggestions(null);
      fetchBudget();
    } catch {
      showAlert('Error', 'Failed to apply suggestions');
    }
  };

  const totalSaved = (suggestions?.suggestions || [])
    .filter((s: any) => selectedIds.has(s.activity_id))
    .reduce((sum: number, s: any) => sum + (s.time_saved_minutes || 0), 0);

  if (loading) {
    return (
      <SafeAreaView style={st.container}>
        <View style={st.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.container}>
      {/* Header */}
      <View style={st.header}>
        <TouchableOpacity onPress={() => router.back()} style={st.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={st.title}>Time Store</Text>
          <Text style={st.subtitle}>Buy back your time intelligently</Text>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={st.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchBudget(); }} colors={[COLORS.primary]} />}
      >
        {/* Hero Card */}
        <LinearGradient colors={['#7C3AED', '#A855F7']} style={st.heroCard}>
          <Ionicons name="time-outline" size={32} color="#FFF" />
          <Text style={st.heroTitle}>How much free time do you need?</Text>
          <Text style={st.heroValue}>{desiredHours}h / {period}</Text>
          <Slider
            style={st.heroSlider}
            minimumValue={0.5}
            maximumValue={period === 'daily' ? 8 : 40}
            step={0.5}
            value={desiredHours}
            onValueChange={setDesiredHours}
            minimumTrackTintColor="#FFF"
            maximumTrackTintColor="rgba(255,255,255,0.3)"
            thumbTintColor="#FFF"
          />
          {/* Period Toggle */}
          <View style={st.periodToggle}>
            {(['daily', 'weekly'] as const).map(p => (
              <TouchableOpacity
                key={p}
                style={[st.periodBtn, period === p && st.periodBtnActive]}
                onPress={() => { setPeriod(p); setDesiredHours(p === 'daily' ? 2 : 10); setLoading(true); }}
              >
                <Text style={[st.periodBtnText, period === p && st.periodBtnTextActive]}>
                  {p === 'daily' ? 'Per Day' : 'Per Week'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </LinearGradient>

        {/* Current Budget */}
        {budget && (
          <View style={st.budgetCard}>
            <Text style={st.budgetTitle}>Current Time Budget</Text>
            <View style={st.budgetRow}>
              <View style={st.budgetItem}>
                <Text style={st.budgetNum}>{Math.round(budget.available_minutes / 60 * 10) / 10}h</Text>
                <Text style={st.budgetLabel}>Available</Text>
              </View>
              <View style={st.budgetItem}>
                <Text style={[st.budgetNum, { color: '#EF4444' }]}>{Math.round(budget.committed_minutes / 60 * 10) / 10}h</Text>
                <Text style={st.budgetLabel}>Committed</Text>
              </View>
              <View style={st.budgetItem}>
                <Text style={[st.budgetNum, { color: '#16A34A' }]}>{Math.round(budget.free_minutes / 60 * 10) / 10}h</Text>
                <Text style={st.budgetLabel}>Free</Text>
              </View>
            </View>
            {/* Utilization Bar */}
            <View style={st.utilBar}>
              <View style={[st.utilFill, { width: `${Math.min(100, budget.utilization_percent || 0)}%` }]} />
            </View>
            <Text style={st.utilText}>{budget.utilization_percent}% utilized</Text>

            {/* By Area */}
            {budget.by_area && Object.keys(budget.by_area).length > 0 && (
              <View style={st.areaSection}>
                <Text style={st.areaSectionTitle}>Time by Life Area</Text>
                {Object.entries(budget.by_area)
                  .sort((a: any, b: any) => b[1] - a[1])
                  .map(([area, mins]: [string, any]) => (
                    <View key={area} style={st.areaRow}>
                      <Text style={st.areaName}>{area.replace(/_/g, ' ')}</Text>
                      <View style={st.areaBarBg}>
                        <View style={[st.areaBar, { width: `${Math.min(100, (mins / Math.max(budget.committed_minutes, 1)) * 100)}%` }]} />
                      </View>
                      <Text style={st.areaMins}>{Math.round(mins / 60 * 10) / 10}h</Text>
                    </View>
                  ))}
              </View>
            )}
          </View>
        )}

        {/* Analyze Button */}
        <TouchableOpacity style={st.analyzeBtn} onPress={analyze} disabled={analyzing}>
          {analyzing ? (
            <>
              <ActivityIndicator size="small" color="#FFF" />
              <Text style={st.analyzeBtnText}>Analyzing with AI + CLD + TEPFI...</Text>
            </>
          ) : (
            <>
              <Ionicons name="search" size={18} color="#FFF" />
              <Text style={st.analyzeBtnText}>Find {desiredHours}h of Free Time</Text>
            </>
          )}
        </TouchableOpacity>

        {/* Suggestions */}
        {suggestions && (
          <View style={st.suggestionsSection}>
            {/* Summary */}
            <View style={[st.feasibilityBadge, {
              backgroundColor: suggestions.feasibility === 'achievable' ? '#DCFCE7' :
                suggestions.feasibility === 'partial' ? '#FEF3C7' : '#FEE2E2',
            }]}>
              <Ionicons
                name={suggestions.feasibility === 'achievable' ? 'checkmark-circle' :
                  suggestions.feasibility === 'partial' ? 'alert-circle' : 'warning'}
                size={16}
                color={suggestions.feasibility === 'achievable' ? '#16A34A' :
                  suggestions.feasibility === 'partial' ? '#D97706' : '#DC2626'}
              />
              <Text style={[st.feasibilityText, {
                color: suggestions.feasibility === 'achievable' ? '#16A34A' :
                  suggestions.feasibility === 'partial' ? '#D97706' : '#DC2626',
              }]}>
                {suggestions.feasibility === 'achievable' ? 'Goal Achievable' :
                  suggestions.feasibility === 'partial' ? 'Partially Achievable' : 'Difficult to Achieve'}
              </Text>
            </View>

            {suggestions.overall_recommendation && (
              <Text style={st.recommendation}>{suggestions.overall_recommendation}</Text>
            )}

            <View style={st.savedSummary}>
              <Text style={st.savedNum}>{Math.round(totalSaved / 60 * 10) / 10}h</Text>
              <Text style={st.savedLabel}>can be recovered from {selectedIds.size} selected changes</Text>
            </View>

            {/* Suggestion Cards */}
            {(suggestions.suggestions || []).map((sug: any, idx: number) => {
              const actionCfg = ACTION_CONFIG[sug.action] || ACTION_CONFIG.reduce;
              const isSelected = selectedIds.has(sug.activity_id);
              const tepfiColor = TEPFI_COLORS[sug.tepfi_dimension] || '#94A3B8';

              return (
                <TouchableOpacity
                  key={idx}
                  style={[st.sugCard, isSelected && { borderColor: actionCfg.color, borderWidth: 2 }]}
                  onPress={() => toggleSuggestion(sug.activity_id)}
                >
                  <View style={st.sugTop}>
                    <TouchableOpacity onPress={() => toggleSuggestion(sug.activity_id)} style={st.checkbox}>
                      <Ionicons
                        name={isSelected ? 'checkbox' : 'square-outline'}
                        size={22}
                        color={isSelected ? actionCfg.color : COLORS.textMuted}
                      />
                    </TouchableOpacity>
                    <View style={{ flex: 1 }}>
                      <Text style={st.sugTitle}>{sug.activity_title}</Text>
                      <View style={st.sugBadges}>
                        <View style={[st.sugBadge, { backgroundColor: actionCfg.bg }]}>
                          <Ionicons name={actionCfg.icon as any} size={10} color={actionCfg.color} />
                          <Text style={[st.sugBadgeText, { color: actionCfg.color }]}>
                            {(sug.action || '').toUpperCase()}
                          </Text>
                        </View>
                        <View style={[st.sugBadge, { backgroundColor: `${tepfiColor}15` }]}>
                          <Text style={[st.sugBadgeText, { color: tepfiColor }]}>
                            {sug.tepfi_dimension}/{sug.tepfi_layer}
                          </Text>
                        </View>
                        {sug.time_saved_minutes > 0 && (
                          <Text style={st.sugTimeSaved}>⏱ {sug.time_saved_minutes}m</Text>
                        )}
                      </View>
                    </View>
                  </View>

                  <Text style={st.sugDesc}>{sug.description}</Text>

                  {sug.delegate_to && (
                    <View style={st.delegateRow}>
                      <Ionicons name="person" size={12} color="#3B82F6" />
                      <Text style={st.delegateText}>Delegate to: {sug.delegate_to}</Text>
                    </View>
                  )}
                  {sug.tool_suggestion && (
                    <View style={st.delegateRow}>
                      <Ionicons name="construct" size={12} color="#7C3AED" />
                      <Text style={[st.delegateText, { color: '#7C3AED' }]}>Tool: {sug.tool_suggestion}</Text>
                    </View>
                  )}
                  {sug.cost_estimate && (
                    <View style={st.delegateRow}>
                      <Ionicons name="cash" size={12} color="#10B981" />
                      <Text style={[st.delegateText, { color: '#10B981' }]}>Cost: {sug.cost_estimate}</Text>
                    </View>
                  )}

                  <View style={st.sugMeta}>
                    <Text style={st.sugMetaText}>Impact: {sug.impact_risk}/10</Text>
                    <Text style={st.sugMetaText}>Goal Align: {sug.goal_alignment_score}/10</Text>
                    {sug.cld_centrality !== undefined && (
                      <Text style={st.sugMetaText}>CLD: {(sug.cld_centrality * 100).toFixed(0)}%</Text>
                    )}
                  </View>

                  {sug.reasoning && (
                    <Text style={st.sugReasoning}>{sug.reasoning}</Text>
                  )}
                </TouchableOpacity>
              );
            })}

            {/* Apply Button */}
            {(suggestions.suggestions || []).length > 0 && (
              <TouchableOpacity style={st.applyBtn} onPress={applySuggestions}>
                <Ionicons name="checkmark-circle" size={18} color="#FFF" />
                <Text style={st.applyBtnText}>
                  Apply {selectedIds.size} Suggestions ({Math.round(totalSaved / 60 * 10) / 10}h saved)
                </Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* How It Works */}
        {!suggestions && (
          <View style={st.howSection}>
            <Text style={st.howTitle}>How Time Store Works</Text>
            {[
              { icon: 'analytics', label: 'Scans all CTT tasks & Lifestyle routines' },
              { icon: 'grid', label: 'Analyzes TEPFI: Time, Effort, People, Finance, Infra' },
              { icon: 'git-network', label: 'CLD-based impact analysis on factor chains' },
              { icon: 'bulb', label: 'AI suggests: Eliminate, Reduce, Delegate, Batch, Automate' },
              { icon: 'flash', label: 'Apply changes directly to your tasks & routines' },
            ].map((step, i) => (
              <View key={i} style={st.howStep}>
                <View style={st.howStepIcon}>
                  <Ionicons name={step.icon as any} size={16} color={COLORS.primary} />
                </View>
                <Text style={st.howStepText}>{step.label}</Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted },
  scrollContent: { padding: 16, paddingBottom: 40 },

  // Hero
  heroCard: { borderRadius: 16, padding: 20, alignItems: 'center', gap: 6, marginBottom: 14 },
  heroTitle: { fontSize: 15, fontWeight: '600', color: 'rgba(255,255,255,0.9)' },
  heroValue: { fontSize: 36, fontWeight: '800', color: '#FFF' },
  heroSlider: { width: '100%', height: 32, marginTop: 4 },
  periodToggle: { flexDirection: 'row', backgroundColor: 'rgba(255,255,255,0.2)', borderRadius: 10, padding: 3, marginTop: 4 },
  periodBtn: { flex: 1, paddingVertical: 6, borderRadius: 8, alignItems: 'center' },
  periodBtnActive: { backgroundColor: '#FFF' },
  periodBtnText: { fontSize: 12, fontWeight: '600', color: 'rgba(255,255,255,0.8)' },
  periodBtnTextActive: { color: '#7C3AED' },

  // Budget
  budgetCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: COLORS.border, marginBottom: 14 },
  budgetTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10 },
  budgetRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 10 },
  budgetItem: { alignItems: 'center' },
  budgetNum: { fontSize: 20, fontWeight: '800', color: COLORS.textPrimary },
  budgetLabel: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },
  utilBar: { height: 6, backgroundColor: '#F1F5F9', borderRadius: 3, overflow: 'hidden', marginBottom: 4 },
  utilFill: { height: 6, backgroundColor: COLORS.primary, borderRadius: 3 },
  utilText: { fontSize: 10, color: COLORS.textMuted, textAlign: 'right' },
  areaSection: { marginTop: 10, gap: 6 },
  areaSectionTitle: { fontSize: 12, fontWeight: '700', color: COLORS.textSecondary },
  areaRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  areaName: { width: 90, fontSize: 11, color: COLORS.textSecondary, textTransform: 'capitalize' },
  areaBarBg: { flex: 1, height: 6, backgroundColor: '#F1F5F9', borderRadius: 3, overflow: 'hidden' },
  areaBar: { height: 6, backgroundColor: COLORS.primary, borderRadius: 3 },
  areaMins: { width: 35, fontSize: 11, fontWeight: '600', color: COLORS.textPrimary, textAlign: 'right' },

  // Analyze
  analyzeBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#7C3AED', borderRadius: 14, paddingVertical: 16, marginBottom: 14 },
  analyzeBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },

  // Suggestions
  suggestionsSection: { gap: 10 },
  feasibilityBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 12, alignSelf: 'flex-start' },
  feasibilityText: { fontSize: 14, fontWeight: '700' },
  recommendation: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18, marginBottom: 4 },
  savedSummary: { flexDirection: 'row', alignItems: 'baseline', gap: 6, marginBottom: 6 },
  savedNum: { fontSize: 28, fontWeight: '800', color: '#16A34A' },
  savedLabel: { fontSize: 12, color: COLORS.textMuted },

  sugCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: COLORS.border, marginBottom: 8 },
  sugTop: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  checkbox: { paddingTop: 1 },
  sugTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  sugBadges: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 },
  sugBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  sugBadgeText: { fontSize: 10, fontWeight: '700' },
  sugTimeSaved: { fontSize: 11, fontWeight: '700', color: '#16A34A' },
  sugDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 6, lineHeight: 17 },
  delegateRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  delegateText: { fontSize: 12, fontWeight: '600', color: '#3B82F6' },
  sugMeta: { flexDirection: 'row', gap: 10, marginTop: 6 },
  sugMetaText: { fontSize: 10, color: COLORS.textMuted },
  sugReasoning: { fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic', marginTop: 4 },
  applyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#16A34A', borderRadius: 14, paddingVertical: 16, marginTop: 6 },
  applyBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },

  // How It Works
  howSection: { backgroundColor: '#F8FAFC', borderRadius: 14, padding: 16, gap: 10, marginTop: 4 },
  howTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  howStep: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  howStepIcon: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#EDE9FE', alignItems: 'center', justifyContent: 'center' },
  howStepText: { flex: 1, fontSize: 12, color: COLORS.textSecondary },
});
