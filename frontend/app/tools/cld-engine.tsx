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

export default function CLDEngineScreen() {
  const router = useRouter();
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [clds, setClds] = useState<CLDSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    try {
      const [decRes, cldRes] = await Promise.all([
        api.get('/decisions'),
        api.get('/cld/list'),
      ]);
      setDecisions(decRes.data || []);
      setClds(cldRes.data?.clds || []);
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
    // Navigate to the decision PRR flow, and the user can open CLD from there
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

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>CLD Engine</Text>
          <Text style={styles.subtitle}>Causal Loop Diagrams · Systems Thinking</Text>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} colors={[COLORS.primary]} />}
      >
        {/* Hero */}
        <LinearGradient colors={['#1E40AF', '#3B82F6']} style={styles.heroCard}>
          <Ionicons name="git-network-outline" size={36} color="#FFF" />
          <Text style={styles.heroTitle}>Systems Thinking Analysis</Text>
          <Text style={styles.heroSubtitle}>
            Understand how your decision factors influence each other through causal loops,
            feedback systems, and dynamic simulations.
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
                        {decision.life_area || 'General'} · {cld?.nodes?.length || 0} nodes · {cld?.links?.length || 0} links · {cld?.loops?.length || 0} loops
                      </Text>
                    </View>
                    <TouchableOpacity style={styles.deleteBtn} onPress={() => deleteCLD(decision.id)}>
                      <Ionicons name="trash-outline" size={16} color={COLORS.error} />
                    </TouchableOpacity>
                  </View>
                  <View style={styles.cldPreviewRow}>
                    {cld?.nodes?.slice(0, 5).map((node: any, idx: number) => (
                      <View
                        key={idx}
                        style={[styles.miniNode, {
                          backgroundColor: node.classification === 'primary' ? COLORS.primary : '#10B981',
                        }]}
                      >
                        <Text style={styles.miniNodeText}>{(node.name || '').slice(0, 3)}</Text>
                      </View>
                    ))}
                    {(cld?.nodes?.length || 0) > 5 && (
                      <Text style={styles.moreText}>+{(cld?.nodes?.length || 0) - 5}</Text>
                    )}
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
            <Text style={styles.sectionSubtitle}>
              These decisions have 2+ factors and can generate a CLD
            </Text>
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
                      {decision.life_area || 'General'} · {decision.factors.filter((f: any) => !f.parent_id).length} factors · No CLD yet
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
            <TouchableOpacity
              style={styles.createBtn}
              onPress={() => router.push('/tools/new-decision')}
            >
              <Ionicons name="add-circle" size={18} color="#FFF" />
              <Text style={styles.createBtnText}>New Decision</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* How It Works */}
        <View style={styles.howItWorks}>
          <Text style={styles.howTitle}>How CLD Engine Works</Text>
          <View style={styles.howStep}>
            <View style={[styles.howStepIcon, { backgroundColor: '#EDE9FE' }]}>
              <Text style={styles.howStepNum}>1</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.howStepTitle}>Generate</Text>
              <Text style={styles.howStepDesc}>AI analyzes causal relationships between your factors</Text>
            </View>
          </View>
          <View style={styles.howStep}>
            <View style={[styles.howStepIcon, { backgroundColor: '#DBEAFE' }]}>
              <Text style={styles.howStepNum}>2</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.howStepTitle}>Edit & Refine</Text>
              <Text style={styles.howStepDesc}>Adjust nodes, links, strength, and relationship types</Text>
            </View>
          </View>
          <View style={styles.howStep}>
            <View style={[styles.howStepIcon, { backgroundColor: '#D1FAE5' }]}>
              <Text style={styles.howStepNum}>3</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.howStepTitle}>Simulate</Text>
              <Text style={styles.howStepDesc}>Run "what-if" scenarios to see ripple effects</Text>
            </View>
          </View>
          <View style={styles.howStep}>
            <View style={[styles.howStepIcon, { backgroundColor: '#FEF3C7' }]}>
              <Text style={styles.howStepNum}>4</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.howStepTitle}>Apply</Text>
              <Text style={styles.howStepDesc}>Auto-populate classifications, priorities, and ratings</Text>
            </View>
          </View>
        </View>
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
  scrollContent: { padding: 16, paddingBottom: 40 },

  // Hero
  heroCard: { borderRadius: 16, padding: 20, marginBottom: 16, alignItems: 'center', gap: 8 },
  heroTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  heroSubtitle: { fontSize: 13, color: 'rgba(255,255,255,0.8)', textAlign: 'center', lineHeight: 18 },
  heroStatsRow: { flexDirection: 'row', gap: 20, marginTop: 8 },
  heroStat: { alignItems: 'center' },
  heroStatNum: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  heroStatLabel: { fontSize: 10, color: 'rgba(255,255,255,0.7)', marginTop: 2 },

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
  cldPreviewRow: { flexDirection: 'row', gap: 6, marginBottom: 4 },
  miniNode: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  miniNodeText: { fontSize: 8, fontWeight: '700', color: '#FFF' },
  moreText: { fontSize: 11, color: COLORS.textMuted, alignSelf: 'center' },
  tapHint: { fontSize: 11, color: COLORS.primary, fontWeight: '600', marginTop: 2 },

  // Empty
  emptyState: { alignItems: 'center', paddingVertical: 40, gap: 10 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  emptySubtitle: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', maxWidth: 280 },
  createBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: COLORS.primary, paddingHorizontal: 20, paddingVertical: 10, borderRadius: 12, marginTop: 8 },
  createBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },

  // How It Works
  howItWorks: { backgroundColor: '#F8FAFC', borderRadius: 14, padding: 16, marginTop: 16, gap: 12 },
  howTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  howStep: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  howStepIcon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  howStepNum: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  howStepTitle: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  howStepDesc: { fontSize: 11, color: COLORS.textMuted },
});
