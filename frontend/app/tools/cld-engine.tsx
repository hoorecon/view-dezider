import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

interface Decision {
  id: string;
  title: string;
  context: string;
  factors: any[];
  life_area?: string;
  decision_type?: string;
  status: string;
  created_at: string;
}

interface CLDSummary {
  decision_id: string;
  nodes: any[];
  links: any[];
  loops: any[];
  layout_type: string;
  updated_at: string;
}

interface ModuleCLD {
  cld_id: string;
  module_type: string;
  context_id: string;
  node_count: number;
  link_count: number;
  updated_at: string;
}

const MODULE_TYPES_META = [
  { id: 'master', name: 'Master CLD', icon: 'globe-outline', color: '#7C3AED', desc: 'Cross-module aggregation' },
  { id: 'decision', name: 'Decisions', icon: 'git-branch-outline', color: '#2563EB', desc: 'PRR decision factors' },
  { id: 'pna', name: 'PNA', icon: 'layers-outline', color: '#059669', desc: 'Problems/Needs/Aspirations' },
  { id: 'goal', name: 'Goals', icon: 'trophy-outline', color: '#D97706', desc: 'GEM + Goal Setter + Manifestation' },
  { id: 'lifestyle', name: 'Lifestyle', icon: 'sunny-outline', color: '#EC4899', desc: 'Lifestyle Designer + Dezider' },
  { id: 'conflict_breaker', name: 'Conflict Breaker', icon: 'shield-half-outline', color: '#DC2626', desc: 'Crucial conversations' },
  { id: 'emotional_gatekeeper', name: 'Emotional Gatekeeper', icon: 'heart-outline', color: '#8B5CF6', desc: 'Emotional tools' },
  { id: 'aala', name: 'AALA', icon: 'pie-chart-outline', color: '#0891B2', desc: 'Assets & Liabilities' },
  { id: 'ctt', name: 'CTT Tasks', icon: 'checkbox-outline', color: '#4F46E5', desc: 'Task tracker' },
  { id: 'solutions_store', name: 'Solutions Store', icon: 'storefront-outline', color: '#0D9488', desc: 'Solutions & DEO' },
  { id: 'unconditional_happiness', name: 'Happiness', icon: 'happy-outline', color: '#F59E0B', desc: 'UH tracker' },
  { id: 'time_dezider', name: 'Time Dezider', icon: 'time-outline', color: '#6366F1', desc: 'Time management' },
  { id: 'tepfi', name: 'Capabilities & Resources Index', icon: 'grid-outline', color: '#0F766E', desc: 'Resource analysis' },
  { id: 'consciousness', name: 'Consciousness', icon: 'eye-outline', color: '#7C3AED', desc: 'Diary insights' },
  { id: 'ai_assistant', name: 'AI Assistant', icon: 'chatbubbles-outline', color: '#2563EB', desc: 'Conversation patterns' },
  { id: 'meditation', name: 'Meditation', icon: 'leaf-outline', color: '#059669', desc: 'KalphaVriksha sessions' },
];

export default function CLDEngineScreen() {
  const router = useRouter();
  const [tab, setTab] = useState<'decisions' | 'modules'>('modules');
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [clds, setClds] = useState<CLDSummary[]>([]);
  const [moduleClds, setModuleClds] = useState<ModuleCLD[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generating, setGenerating] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [decRes, cldRes, modRes] = await Promise.all([
        api.get('/decisions'),
        api.get('/cld/list'),
        api.get('/cld/list-modules'),
      ]);
      setDecisions(decRes.data || []);
      setClds(cldRes.data?.clds || []);
      setModuleClds(Array.isArray(modRes.data) ? modRes.data : []);
    } catch (err) {
      console.error('Failed to fetch CLD data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchData();
    }, [])
  );

  const getCLDForDecision = (decisionId: string) => {
    return clds.find(c => c.decision_id === decisionId);
  };

  const openCLDForDecision = (decision: Decision) => {
    router.push(`/prr/${decision.id}` as any);
  };

  const deleteCLD = async (decisionId: string) => {
    showAlert('Delete CLD', 'Remove the saved CLD diagram for this decision?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try {
            await api.delete(`/cld/${decisionId}`);
            setClds(prev => prev.filter(c => c.decision_id !== decisionId));
          } catch {
            showAlert('Error', 'Failed to delete CLD');
          }
        },
      },
    ]);
  };

  const generateModuleCLD = async (moduleType: string) => {
    setGenerating(moduleType);
    try {
      const res = await api.post(`/cld/module/${moduleType}/generate`, {});
      showAlert('Success', `${moduleType} CLD generated with ${res.data?.nodes?.length || 0} nodes and ${res.data?.links?.length || 0} links`);
      fetchData();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Generation failed';
      showAlert('Error', msg);
    } finally {
      setGenerating(null);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      </SafeAreaView>
    );
  }

  const decisionsWithFactors = decisions.filter(d => d.factors && d.factors.filter((f: any) => !f.parent_id).length >= 2);
  const decisionsWithCLD = decisionsWithFactors.filter(d => getCLDForDecision(d.id));
  const decisionsWithoutCLD = decisionsWithFactors.filter(d => !getCLDForDecision(d.id));
  const getModuleCLD = (moduleType: string) => moduleClds.find(m => m.module_type === moduleType);

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>CLD Engine</Text>
          <Text style={styles.subtitle}>Causal Loop Diagrams · Systems Thinking</Text>
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabRow}>
        <TouchableOpacity
          style={[styles.tabBtn, tab === 'modules' && styles.tabBtnActive]}
          onPress={() => setTab('modules')}
        >
          <Text style={[styles.tabText, tab === 'modules' && styles.tabTextActive]}>Module CLDs</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabBtn, tab === 'decisions' && styles.tabBtnActive]}
          onPress={() => setTab('decisions')}
        >
          <Text style={[styles.tabText, tab === 'decisions' && styles.tabTextActive]}>Decision CLDs</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} colors={[COLORS.primary]} />}
      >
        {tab === 'modules' && (
          <>
            {/* Hero */}
            <LinearGradient colors={['#7C3AED', '#A78BFA']} style={styles.heroCard}>
              <Ionicons name="globe-outline" size={36} color="#FFF" />
              <Text style={styles.heroTitle}>Cross-Module Intelligence</Text>
              <Text style={styles.heroSubtitle}>
                Generate causal loop diagrams for each life module or aggregate everything into a Master CLD.
              </Text>
              <View style={styles.heroStatsRow}>
                <View style={styles.heroStat}>
                  <Text style={styles.heroStatNum}>{moduleClds.length}</Text>
                  <Text style={styles.heroStatLabel}>Module CLDs</Text>
                </View>
                <View style={styles.heroStat}>
                  <Text style={styles.heroStatNum}>
                    {moduleClds.reduce((sum, c) => sum + (c.node_count || 0), 0)}
                  </Text>
                  <Text style={styles.heroStatLabel}>Total Nodes</Text>
                </View>
                <View style={styles.heroStat}>
                  <Text style={styles.heroStatNum}>
                    {moduleClds.reduce((sum, c) => sum + (c.link_count || 0), 0)}
                  </Text>
                  <Text style={styles.heroStatLabel}>Total Links</Text>
                </View>
              </View>
            </LinearGradient>

            {/* Module Grid */}
            {MODULE_TYPES_META.map(mod => {
              const existing = getModuleCLD(mod.id);
              const isGenerating = generating === mod.id;
              return (
                <View key={mod.id} style={[styles.moduleCard, existing && { borderLeftWidth: 3, borderLeftColor: mod.color }]}>
                  <View style={styles.moduleCardRow}>
                    <View style={[styles.moduleIcon, { backgroundColor: mod.color + '20' }]}>
                      <Ionicons name={mod.icon as any} size={20} color={mod.color} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.moduleCardTitle}>{mod.name}</Text>
                      <Text style={styles.moduleCardDesc}>{mod.desc}</Text>
                      {existing && (
                        <Text style={styles.moduleCardStats}>
                          {existing.node_count} nodes · {existing.link_count} links
                        </Text>
                      )}
                    </View>
                    <TouchableOpacity
                      style={[styles.editBtn, { borderColor: mod.color }]}
                      onPress={() => router.push({ pathname: '/cld/editor', params: { module_type: mod.id } } as any)}
                    >
                      <Ionicons name="create-outline" size={14} color={mod.color} />
                      <Text style={[styles.editBtnText, { color: mod.color }]}>Edit</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.genBtn, { backgroundColor: mod.color }, isGenerating && { opacity: 0.5 }]}
                      onPress={() => generateModuleCLD(mod.id)}
                      disabled={isGenerating}
                    >
                      {isGenerating ? (
                        <ActivityIndicator size="small" color="#FFF" />
                      ) : (
                        <Ionicons name={existing ? "refresh" : "flash"} size={16} color="#FFF" />
                      )}
                    </TouchableOpacity>
                  </View>
                </View>
              );
            })}
          </>
        )}

        {tab === 'decisions' && (
          <>
            {/* Decision CLD Hero */}
            <LinearGradient colors={['#1E40AF', '#3B82F6']} style={styles.heroCard}>
              <Ionicons name="git-network-outline" size={36} color="#FFF" />
              <Text style={styles.heroTitle}>Decision Factor Analysis</Text>
              <Text style={styles.heroSubtitle}>
                Understand how your decision factors influence each other through causal loops.
              </Text>
              <View style={styles.heroStatsRow}>
                <View style={styles.heroStat}>
                  <Text style={styles.heroStatNum}>{decisionsWithCLD.length}</Text>
                  <Text style={styles.heroStatLabel}>CLDs Created</Text>
                </View>
                <View style={styles.heroStat}>
                  <Text style={styles.heroStatNum}>
                    {clds.reduce((sum, c) => sum + (c.links?.length || 0), 0)}
                  </Text>
                  <Text style={styles.heroStatLabel}>Causal Links</Text>
                </View>
                <View style={styles.heroStat}>
                  <Text style={styles.heroStatNum}>
                    {clds.reduce((sum, c) => sum + (c.loops?.length || 0), 0)}
                  </Text>
                  <Text style={styles.heroStatLabel}>Feedback Loops</Text>
                </View>
              </View>
            </LinearGradient>

            {/* Existing CLDs */}
            {decisionsWithCLD.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>Active CLDs</Text>
                {decisionsWithCLD.map(decision => {
                  const cld = getCLDForDecision(decision.id);
                  return (
                    <TouchableOpacity
                      key={decision.id}
                      style={styles.decisionCard}
                      onPress={() => openCLDForDecision(decision)}
                    >
                      <View style={styles.decisionCardHeader}>
                        <View style={styles.cldStatusBadge}>
                          <Ionicons name="checkmark-circle" size={14} color="#16A34A" />
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.decisionCardTitle} numberOfLines={1}>{decision.title}</Text>
                          <Text style={styles.decisionCardSub} numberOfLines={1}>
                            {decision.life_area || 'General'} · {cld?.nodes?.length || 0} nodes · {cld?.links?.length || 0} links
                          </Text>
                        </View>
                        <TouchableOpacity style={styles.deleteBtn} onPress={() => deleteCLD(decision.id)}>
                          <Ionicons name="trash-outline" size={16} color={COLORS.error} />
                        </TouchableOpacity>
                      </View>
                      <Text style={styles.tapHint}>Tap to open CLD in decision flow →</Text>
                    </TouchableOpacity>
                  );
                })}
              </>
            )}

            {/* Decisions Ready for CLD */}
            {decisionsWithoutCLD.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>Ready for CLD Analysis</Text>
                <Text style={styles.sectionSubtitle}>Decisions with 2+ factors</Text>
                {decisionsWithoutCLD.map(decision => (
                  <TouchableOpacity
                    key={decision.id}
                    style={[styles.decisionCard, { borderLeftWidth: 3, borderLeftColor: '#F59E0B' }]}
                    onPress={() => openCLDForDecision(decision)}
                  >
                    <View style={styles.decisionCardHeader}>
                      <View style={[styles.cldStatusBadge, { backgroundColor: '#FEF3C7' }]}>
                        <Ionicons name="add-circle-outline" size={14} color="#D97706" />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.decisionCardTitle} numberOfLines={1}>{decision.title}</Text>
                        <Text style={styles.decisionCardSub} numberOfLines={1}>
                          {decision.life_area || 'General'} · {decision.factors.filter((f: any) => !f.parent_id).length} factors
                        </Text>
                      </View>
                    </View>
                    <Text style={styles.tapHint}>Tap to open & generate CLD →</Text>
                  </TouchableOpacity>
                ))}
              </>
            )}

            {/* Empty State */}
            {decisionsWithFactors.length === 0 && (
              <View style={styles.emptyState}>
                <Ionicons name="git-network-outline" size={48} color={COLORS.textMuted} />
                <Text style={styles.emptyTitle}>No Decisions Ready</Text>
                <Text style={styles.emptySubtitle}>
                  Create a decision with at least 2 factors to generate a Causal Loop Diagram
                </Text>
              </View>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 12, color: COLORS.textMuted },

  // Tabs
  tabRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 4 },
  tabBtn: { flex: 1, paddingVertical: 10, borderRadius: 10, backgroundColor: '#F1F5F9', alignItems: 'center' },
  tabBtnActive: { backgroundColor: COLORS.primary },
  tabText: { fontSize: 13, fontWeight: '600', color: COLORS.textMuted },
  tabTextActive: { color: '#FFF' },

  scrollContent: { padding: 16, paddingBottom: 40 },

  // Hero
  heroCard: { borderRadius: 16, padding: 20, marginBottom: 16, alignItems: 'center', gap: 8 },
  heroTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  heroSubtitle: { fontSize: 13, color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 18 },
  heroStatsRow: { flexDirection: 'row', gap: 20, marginTop: 8 },
  heroStat: { alignItems: 'center' },
  heroStatNum: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  heroStatLabel: { fontSize: 10, color: 'rgba(255,255,255,0.7)', marginTop: 2 },

  // Module Cards
  moduleCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  moduleCardRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  moduleIcon: { width: 40, height: 40, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  moduleCardTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  moduleCardDesc: { fontSize: 11, color: COLORS.textMuted },
  moduleCardStats: { fontSize: 11, color: COLORS.primary, fontWeight: '600', marginTop: 2 },
  genBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  editBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16, borderWidth: 1, marginRight: 6 },
  editBtnText: { fontSize: 11, fontWeight: '700' },

  // Sections
  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4, marginTop: 8 },
  sectionSubtitle: { fontSize: 12, color: COLORS.textMuted, marginBottom: 8 },

  // Decision Cards
  decisionCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  decisionCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 },
  cldStatusBadge: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#DCFCE7', alignItems: 'center', justifyContent: 'center' },
  decisionCardTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  decisionCardSub: { fontSize: 11, color: COLORS.textMuted },
  deleteBtn: { padding: 6 },
  tapHint: { fontSize: 11, color: COLORS.primary, fontWeight: '600', marginTop: 2 },

  // Empty
  emptyState: { alignItems: 'center', paddingVertical: 40, gap: 10 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  emptySubtitle: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', maxWidth: 280 },
});
