import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, TextInput, Modal,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

interface SwotItem {
  id: string;
  text: string;
  description: string;
  impact: number;
}

interface SwotAnalysis {
  id: string;
  title: string;
  context: string;
  life_area: string | null;
  decision_type: string | null;
  strengths: SwotItem[];
  weaknesses: SwotItem[];
  opportunities: SwotItem[];
  threats: SwotItem[];
  converted_decision_id: string | null;
  created_at: string;
}

type QuadrantKey = 'strengths' | 'weaknesses' | 'opportunities' | 'threats';

const QUADRANTS: { key: QuadrantKey; label: string; icon: string; color: string; bgColor: string; borderColor: string; nature: string }[] = [
  { key: 'strengths', label: 'Strengths', icon: 'shield-checkmark', color: '#059669', bgColor: '#ECFDF5', borderColor: '#A7F3D0', nature: 'Internal +' },
  { key: 'weaknesses', label: 'Weaknesses', icon: 'warning', color: '#DC2626', bgColor: '#FEF2F2', borderColor: '#FECACA', nature: 'Internal −' },
  { key: 'opportunities', label: 'Opportunities', icon: 'trending-up', color: '#2563EB', bgColor: '#EFF6FF', borderColor: '#BFDBFE', nature: 'External +' },
  { key: 'threats', label: 'Threats', icon: 'thunderstorm', color: '#D97706', bgColor: '#FFFBEB', borderColor: '#FDE68A', nature: 'External −' },
];

const LIFE_AREAS = [
  { key: 'career', label: 'Career', icon: 'briefcase' },
  { key: 'finance', label: 'Finance', icon: 'cash' },
  { key: 'relationships', label: 'Relationships', icon: 'heart' },
  { key: 'holistic_health', label: 'Health', icon: 'fitness' },
  { key: 'assets', label: 'Assets', icon: 'home' },
  { key: 'knowledge_skills', label: 'Knowledge', icon: 'school' },
  { key: 'social_image', label: 'Social', icon: 'people' },
  { key: 'hobbies_entertainment', label: 'Hobbies', icon: 'game-controller' },
  { key: 'spirituality_religion', label: 'Spirituality', icon: 'leaf' },
];

export default function SwotScreen() {
  const router = useRouter();
  const [analyses, setAnalyses] = useState<SwotAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newContext, setNewContext] = useState('');
  const [newLifeArea, setNewLifeArea] = useState('');
  const [creating, setCreating] = useState(false);

  // Detail/Edit view
  const [selectedAnalysis, setSelectedAnalysis] = useState<SwotAnalysis | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [addingTo, setAddingTo] = useState<QuadrantKey | null>(null);
  const [newItemText, setNewItemText] = useState('');
  const [newItemDesc, setNewItemDesc] = useState('');
  const [newItemImpact, setNewItemImpact] = useState(5);
  const [converting, setConverting] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchAnalyses = async () => {
    try {
      const res = await api.get('/swot');
      setAnalyses(res.data || []);
    } catch (err) {
      console.error('Error fetching swot:', err);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchAnalyses(); }, []));

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchAnalyses();
    setRefreshing(false);
  };

  const handleCreate = async () => {
    if (!newTitle.trim()) {
      showAlert('Required', 'Please enter a title for your SWOT analysis');
      return;
    }
    setCreating(true);
    try {
      const res = await api.post('/swot', {
        title: newTitle.trim(),
        context: newContext.trim(),
        life_area: newLifeArea || null,
      });
      setShowCreateModal(false);
      setNewTitle('');
      setNewContext('');
      setNewLifeArea('');
      await fetchAnalyses();
      const newDoc = await api.get(`/swot/${res.data.id}`);
      setSelectedAnalysis(newDoc.data);
      setShowDetail(true);
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to create analysis');
    } finally {
      setCreating(false);
    }
  };

  const handleOpenDetail = async (id: string) => {
    try {
      const res = await api.get(`/swot/${id}`);
      setSelectedAnalysis(res.data);
      setShowDetail(true);
    } catch (err) {
      showAlert('Error', 'Failed to load analysis');
    }
  };

  const handleAddItem = async () => {
    if (!newItemText.trim() || !selectedAnalysis || !addingTo) return;
    const newItem: SwotItem = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      text: newItemText.trim(),
      description: newItemDesc.trim(),
      impact: newItemImpact,
    };

    const updated = { ...selectedAnalysis };
    updated[addingTo] = [...(updated[addingTo] || []), newItem];

    setSaving(true);
    try {
      await api.put(`/swot/${selectedAnalysis.id}`, {
        [addingTo]: updated[addingTo],
      });
      setSelectedAnalysis(updated);
      setNewItemText('');
      setNewItemDesc('');
      setNewItemImpact(5);
      setAddingTo(null);
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to save item');
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveItem = async (quadrant: QuadrantKey, itemId: string) => {
    if (!selectedAnalysis) return;
    const updated = { ...selectedAnalysis };
    updated[quadrant] = updated[quadrant].filter(item => item.id !== itemId);

    try {
      await api.put(`/swot/${selectedAnalysis.id}`, {
        [quadrant]: updated[quadrant],
      });
      setSelectedAnalysis(updated);
    } catch (err) {
      showAlert('Error', 'Failed to remove item');
    }
  };

  const handleConvertToDecision = async () => {
    if (!selectedAnalysis) return;
    if (selectedAnalysis.converted_decision_id) {
      showAlert('Already Converted', 'This SWOT analysis has already been converted to a PRR Decision.');
      return;
    }
    const totalItems =
      (selectedAnalysis.strengths?.length || 0) +
      (selectedAnalysis.weaknesses?.length || 0) +
      (selectedAnalysis.opportunities?.length || 0) +
      (selectedAnalysis.threats?.length || 0);

    if (totalItems === 0) {
      showAlert('Empty', 'Add at least one item in any quadrant before converting.');
      return;
    }

    showAlert(
      'Convert to PRR Decision',
      `This will create a PRR Decision with ${totalItems} factors.\n\nStrengths + Opportunities → Factors (as-is)\nWeaknesses + Threats → Factors (prefixed with "NOT")\n\nAI will generate expected values.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Convert',
          style: 'default',
          onPress: async () => {
            setConverting(true);
            try {
              const res = await api.post(`/swot/${selectedAnalysis.id}/convert-to-decision`);
              showAlert(
                'Decision Created!',
                res.data.message,
                [{
                  text: 'Open Decision',
                  onPress: () => {
                    setShowDetail(false);
                    router.push(`/tools/new-decision?id=${res.data.decision_id}` as any);
                  }
                }]
              );
              setSelectedAnalysis({
                ...selectedAnalysis,
                converted_decision_id: res.data.decision_id,
              });
              fetchAnalyses();
            } catch (err: any) {
              showAlert('Error', err.response?.data?.detail || 'Failed to convert');
            } finally {
              setConverting(false);
            }
          }
        }
      ]
    );
  };

  const handleDelete = async (id: string) => {
    showAlert('Delete Analysis', 'Are you sure you want to delete this SWOT analysis?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try {
            await api.delete(`/swot/${id}`);
            fetchAnalyses();
            if (selectedAnalysis?.id === id) {
              setShowDetail(false);
              setSelectedAnalysis(null);
            }
          } catch (err) {
            showAlert('Error', 'Failed to delete');
          }
        }
      }
    ]);
  };

  const getQuadrantInfo = (key: QuadrantKey) => QUADRANTS.find(q => q.key === key)!;

  const getTotalItems = (a: SwotAnalysis) =>
    (a.strengths?.length || 0) + (a.weaknesses?.length || 0) +
    (a.opportunities?.length || 0) + (a.threats?.length || 0);

  // ========== RENDER DETAIL VIEW ==========
  if (showDetail && selectedAnalysis) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        >
          {/* Detail Header */}
          <LinearGradient
            colors={['#1E40AF', '#3B82F6']}
            start={{ x: 0, y: 0 }}
            end={{ x: 1, y: 1 }}
            style={styles.detailHeader}
          >
            <TouchableOpacity
              style={styles.backBtn}
              onPress={() => { setShowDetail(false); setSelectedAnalysis(null); setAddingTo(null); }}
            >
              <Ionicons name="arrow-back" size={22} color="#FFF" />
            </TouchableOpacity>
            <View style={{ flex: 1 }}>
              <Text style={styles.detailTitle} numberOfLines={2}>{selectedAnalysis.title}</Text>
              {selectedAnalysis.context ? (
                <Text style={styles.detailSubtitle} numberOfLines={1}>{selectedAnalysis.context}</Text>
              ) : null}
            </View>
            {selectedAnalysis.converted_decision_id && (
              <View style={styles.convertedBadge}>
                <Ionicons name="checkmark-circle" size={14} color="#FFF" />
                <Text style={styles.convertedBadgeText}>PRR</Text>
              </View>
            )}
          </LinearGradient>

          <ScrollView
            style={{ flex: 1 }}
            contentContainerStyle={{ paddingBottom: 120 }}
            showsVerticalScrollIndicator={false}
          >
            {/* Quadrant Summary */}
            <View style={styles.quadrantSummary}>
              {QUADRANTS.map(q => (
                <View key={q.key} style={[styles.quadrantBox, { backgroundColor: q.bgColor, borderColor: q.borderColor }]}>
                  <Ionicons name={q.icon as any} size={18} color={q.color} />
                  <Text style={[styles.quadrantNum, { color: q.color }]}>
                    {(selectedAnalysis[q.key] || []).length}
                  </Text>
                  <Text style={styles.quadrantLabel}>{q.label}</Text>
                  <Text style={styles.quadrantNature}>{q.nature}</Text>
                </View>
              ))}
            </View>

            {/* Each Quadrant Section */}
            {QUADRANTS.map(q => (
              <View key={q.key} style={styles.sectionWrap}>
                <View style={styles.sectionHeader}>
                  <View style={[styles.sectionBullet, { backgroundColor: q.color }]} />
                  <Ionicons name={q.icon as any} size={16} color={q.color} />
                  <Text style={styles.sectionTitle}>{q.label}</Text>
                  <Text style={styles.sectionNature}>{q.nature}</Text>
                  <TouchableOpacity
                    style={[styles.addItemBtn, { backgroundColor: q.bgColor }]}
                    onPress={() => {
                      setAddingTo(q.key);
                      setNewItemText('');
                      setNewItemDesc('');
                      setNewItemImpact(5);
                    }}
                  >
                    <Ionicons name="add" size={16} color={q.color} />
                    <Text style={{ color: q.color, fontWeight: '600', fontSize: 12 }}>Add</Text>
                  </TouchableOpacity>
                </View>

                {(selectedAnalysis[q.key] || []).length === 0 ? (
                  <View style={[styles.emptySection, { backgroundColor: q.bgColor + '40' }]}>
                    <Ionicons name={q.icon as any} size={24} color={q.borderColor} />
                    <Text style={styles.emptyText}>No {q.label.toLowerCase()} added</Text>
                  </View>
                ) : (
                  (selectedAnalysis[q.key] || []).map(item => (
                    <View key={item.id} style={[styles.itemCard, { borderLeftColor: q.color }]}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.itemText}>{item.text}</Text>
                        {item.description ? <Text style={styles.itemDesc}>{item.description}</Text> : null}
                        <View style={styles.impactRow}>
                          <Text style={styles.impactLabel}>Impact:</Text>
                          <View style={styles.impactDots}>
                            {[...Array(10)].map((_, i) => (
                              <View
                                key={i}
                                style={[
                                  styles.impactDot,
                                  { backgroundColor: i < item.impact ? q.color : '#E5E7EB' }
                                ]}
                              />
                            ))}
                          </View>
                          <Text style={[styles.impactVal, { color: q.color }]}>{item.impact}/10</Text>
                        </View>
                      </View>
                      <TouchableOpacity
                        style={styles.removeBtn}
                        onPress={() => handleRemoveItem(q.key, item.id)}
                      >
                        <Ionicons name="trash-outline" size={16} color="#9CA3AF" />
                      </TouchableOpacity>
                    </View>
                  ))
                )}
              </View>
            ))}

            {/* How it converts info */}
            <View style={styles.infoBox}>
              <Ionicons name="information-circle" size={18} color="#6366F1" />
              <Text style={styles.infoText}>
                When you convert: Strengths & Opportunities → PRR factors as-is. Weaknesses & Threats are prefixed with "NOT" (e.g., "High cost" → "NOT High cost") and become PRR factors. AI generates expected values for all.
              </Text>
            </View>
          </ScrollView>

          {/* Add Item Modal */}
          {addingTo && (
            <Modal visible={true} transparent animationType="slide">
              <View style={styles.modalOverlay}>
                <View style={styles.modalContent}>
                  <View style={styles.modalHeader}>
                    <Text style={styles.modalTitle}>
                      Add {getQuadrantInfo(addingTo).label.slice(0, -1)}
                    </Text>
                    <TouchableOpacity onPress={() => setAddingTo(null)}>
                      <Ionicons name="close" size={24} color={COLORS.textSecondary} />
                    </TouchableOpacity>
                  </View>

                  <View style={[styles.quadrantTag, { backgroundColor: getQuadrantInfo(addingTo).bgColor }]}>
                    <Ionicons name={getQuadrantInfo(addingTo).icon as any} size={14} color={getQuadrantInfo(addingTo).color} />
                    <Text style={{ color: getQuadrantInfo(addingTo).color, fontSize: 12, fontWeight: '600' }}>
                      {getQuadrantInfo(addingTo).label} ({getQuadrantInfo(addingTo).nature})
                    </Text>
                  </View>

                  <Text style={styles.inputLabel}>Description *</Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder={
                      addingTo === 'strengths' ? 'e.g., Strong brand recognition' :
                      addingTo === 'weaknesses' ? 'e.g., High employee turnover' :
                      addingTo === 'opportunities' ? 'e.g., Growing market demand' :
                      'e.g., Increasing competition'
                    }
                    value={newItemText}
                    onChangeText={setNewItemText}
                    autoFocus
                  />

                  <Text style={styles.inputLabel}>Additional notes (optional)</Text>
                  <TextInput
                    style={[styles.textInput, { height: 60 }]}
                    placeholder="Add more context..."
                    value={newItemDesc}
                    onChangeText={setNewItemDesc}
                    multiline
                  />

                  <Text style={styles.inputLabel}>Impact: {newItemImpact}/10</Text>
                  <View style={styles.impactSelector}>
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                      <TouchableOpacity
                        key={n}
                        style={[
                          styles.impactSelectorBtn,
                          n <= newItemImpact && {
                            backgroundColor: getQuadrantInfo(addingTo).color
                          }
                        ]}
                        onPress={() => setNewItemImpact(n)}
                      >
                        <Text style={[
                          styles.impactSelectorText,
                          n <= newItemImpact && { color: '#FFF' }
                        ]}>{n}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  <TouchableOpacity
                    style={[
                      styles.addConfirmBtn,
                      { backgroundColor: getQuadrantInfo(addingTo).color }
                    ]}
                    onPress={handleAddItem}
                    disabled={saving || !newItemText.trim()}
                  >
                    {saving ? (
                      <ActivityIndicator color="#FFF" size="small" />
                    ) : (
                      <Text style={styles.addConfirmText}>
                        Add {getQuadrantInfo(addingTo).label.slice(0, -1)}
                      </Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            </Modal>
          )}

          {/* Bottom Convert Button */}
          {!selectedAnalysis.converted_decision_id && (
            <View style={styles.bottomBar}>
              <TouchableOpacity
                style={styles.convertBtn}
                onPress={handleConvertToDecision}
                disabled={converting}
              >
                <LinearGradient
                  colors={['#6366F1', '#8B5CF6']}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 0 }}
                  style={styles.convertGradient}
                >
                  {converting ? (
                    <>
                      <ActivityIndicator color="#FFF" size="small" />
                      <Text style={styles.convertText}>AI generating values...</Text>
                    </>
                  ) : (
                    <>
                      <Ionicons name="flash" size={20} color="#FFF" />
                      <Text style={styles.convertText}>Convert to PRR Decision</Text>
                    </>
                  )}
                </LinearGradient>
              </TouchableOpacity>
            </View>
          )}

          {selectedAnalysis.converted_decision_id && (
            <View style={styles.bottomBar}>
              <TouchableOpacity
                style={styles.convertBtn}
                onPress={() => {
                  setShowDetail(false);
                  router.push(`/tools/new-decision?id=${selectedAnalysis.converted_decision_id}` as any);
                }}
              >
                <LinearGradient
                  colors={['#059669', '#10B981']}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 0 }}
                  style={styles.convertGradient}
                >
                  <Ionicons name="open-outline" size={20} color="#FFF" />
                  <Text style={styles.convertText}>Open PRR Decision</Text>
                </LinearGradient>
              </TouchableOpacity>
            </View>
          )}
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  // ========== RENDER LIST VIEW ==========
  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <LinearGradient
        colors={['#1E40AF', '#3B82F6']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.header}
      >
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>SWOT Analysis</Text>
          <Text style={styles.headerSub}>Strengths, Weaknesses, Opportunities, Threats → PRR</Text>
        </View>
        <TouchableOpacity
          style={styles.createBtnHeader}
          onPress={() => setShowCreateModal(true)}
        >
          <Ionicons name="add" size={22} color="#1E40AF" />
        </TouchableOpacity>
      </LinearGradient>

      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          showsVerticalScrollIndicator={false}
        >
          {/* How it works */}
          <View style={styles.howItWorks}>
            <Ionicons name="bulb-outline" size={20} color="#2563EB" />
            <Text style={styles.howItWorksText}>
              Map your Strengths, Weaknesses, Opportunities & Threats. Then convert them into PRR factors with AI-generated expected values.
            </Text>
          </View>

          {analyses.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="grid-outline" size={48} color="#D1D5DB" />
              <Text style={styles.emptyStateTitle}>No SWOT Analyses Yet</Text>
              <Text style={styles.emptyStateText}>
                Create your first SWOT analysis to identify key decision factors.
              </Text>
              <TouchableOpacity
                style={styles.emptyCreateBtn}
                onPress={() => setShowCreateModal(true)}
              >
                <Ionicons name="add" size={20} color="#FFF" />
                <Text style={styles.emptyCreateText}>Create SWOT Analysis</Text>
              </TouchableOpacity>
            </View>
          ) : (
            analyses.map(a => (
              <TouchableOpacity
                key={a.id}
                style={styles.listCard}
                onPress={() => handleOpenDetail(a.id)}
                activeOpacity={0.7}
              >
                <View style={styles.listCardHeader}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.listCardTitle} numberOfLines={1}>{a.title}</Text>
                    {a.context ? <Text style={styles.listCardContext} numberOfLines={1}>{a.context}</Text> : null}
                  </View>
                  {a.converted_decision_id && (
                    <View style={styles.prrBadge}>
                      <Ionicons name="checkmark-circle" size={12} color="#2563EB" />
                      <Text style={[styles.prrBadgeText, { color: '#2563EB' }]}>PRR</Text>
                    </View>
                  )}
                </View>

                {/* SWOT mini grid */}
                <View style={styles.miniGrid}>
                  {QUADRANTS.map(q => (
                    <View key={q.key} style={[styles.miniCell, { backgroundColor: q.bgColor }]}>
                      <Ionicons name={q.icon as any} size={12} color={q.color} />
                      <Text style={[styles.miniCellNum, { color: q.color }]}>
                        {(a[q.key] || []).length}
                      </Text>
                      <Text style={styles.miniCellLabel}>{q.label.charAt(0)}</Text>
                    </View>
                  ))}
                </View>

                <View style={styles.listCardFooter}>
                  <Text style={styles.listCardDate}>
                    {new Date(a.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                  </Text>
                  <Text style={styles.listTotalItems}>{getTotalItems(a)} items</Text>
                  <View style={{ flex: 1 }} />
                  <TouchableOpacity
                    style={styles.deleteBtn}
                    onPress={(e) => { e.stopPropagation(); handleDelete(a.id); }}
                  >
                    <Ionicons name="trash-outline" size={16} color="#9CA3AF" />
                  </TouchableOpacity>
                </View>
              </TouchableOpacity>
            ))
          )}
        </ScrollView>
      )}

      {/* Create Modal */}
      <Modal visible={showCreateModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={{ width: '100%', alignItems: 'center' }}
          >
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>New SWOT Analysis</Text>
                <TouchableOpacity onPress={() => setShowCreateModal(false)}>
                  <Ionicons name="close" size={24} color={COLORS.textSecondary} />
                </TouchableOpacity>
              </View>

              <Text style={styles.inputLabel}>Decision / Topic *</Text>
              <TextInput
                style={styles.textInput}
                placeholder="e.g., Launch new product line"
                value={newTitle}
                onChangeText={setNewTitle}
                autoFocus
              />

              <Text style={styles.inputLabel}>Context (optional)</Text>
              <TextInput
                style={[styles.textInput, { height: 70 }]}
                placeholder="Add any relevant background..."
                value={newContext}
                onChangeText={setNewContext}
                multiline
              />

              <Text style={styles.inputLabel}>Life Area (optional)</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  {LIFE_AREAS.map(area => (
                    <TouchableOpacity
                      key={area.key}
                      style={[
                        styles.lifeAreaChip,
                        newLifeArea === area.key && styles.lifeAreaChipActive
                      ]}
                      onPress={() => setNewLifeArea(newLifeArea === area.key ? '' : area.key)}
                    >
                      <Ionicons
                        name={area.icon as any}
                        size={14}
                        color={newLifeArea === area.key ? '#FFF' : COLORS.textSecondary}
                      />
                      <Text style={[
                        styles.lifeAreaChipText,
                        newLifeArea === area.key && { color: '#FFF' }
                      ]}>{area.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>

              <TouchableOpacity
                style={[styles.createConfirmBtn, (!newTitle.trim() || creating) && { opacity: 0.5 }]}
                onPress={handleCreate}
                disabled={!newTitle.trim() || creating}
              >
                {creating ? (
                  <ActivityIndicator color="#FFF" size="small" />
                ) : (
                  <Text style={styles.createConfirmText}>Create SWOT Analysis</Text>
                )}
              </TouchableOpacity>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  // Header
  header: {
    flexDirection: 'row', alignItems: 'center',
    padding: 16, paddingTop: 12, paddingBottom: 20, gap: 12,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.8)', marginTop: 2 },
  createBtnHeader: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: '#FFF',
    justifyContent: 'center', alignItems: 'center',
  },

  // How it works
  howItWorks: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    backgroundColor: '#EFF6FF', borderRadius: 12, padding: 14,
    marginBottom: 16, borderWidth: 1, borderColor: '#BFDBFE',
  },
  howItWorksText: { flex: 1, fontSize: 13, color: '#1E40AF', lineHeight: 18 },

  // Empty state
  emptyState: {
    alignItems: 'center', paddingVertical: 48, gap: 12,
  },
  emptyStateTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptyStateText: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', paddingHorizontal: 32 },
  emptyCreateBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#1E40AF', paddingHorizontal: 20, paddingVertical: 12,
    borderRadius: 12, marginTop: 8,
  },
  emptyCreateText: { fontSize: 15, fontWeight: '600', color: '#FFF' },

  // List card
  listCard: {
    backgroundColor: '#FFF', borderRadius: 14, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: '#E5E7EB',
  },
  listCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  listCardTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  listCardContext: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  prrBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#EFF6FF', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8,
  },
  prrBadgeText: { fontSize: 11, fontWeight: '700' },

  // Mini SWOT grid
  miniGrid: {
    flexDirection: 'row', gap: 8, marginBottom: 10,
  },
  miniCell: {
    flex: 1, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'center', gap: 4,
    paddingVertical: 8, borderRadius: 8,
  },
  miniCellNum: { fontSize: 14, fontWeight: '800' },
  miniCellLabel: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600' },

  listCardFooter: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  listCardDate: { fontSize: 11, color: COLORS.textMuted },
  listTotalItems: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '600' },
  deleteBtn: { padding: 6 },

  // Detail Header
  detailHeader: {
    flexDirection: 'row', alignItems: 'center',
    padding: 16, paddingTop: 12, paddingBottom: 20, gap: 12,
  },
  detailTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  detailSubtitle: { fontSize: 12, color: 'rgba(255,255,255,0.8)', marginTop: 2 },
  convertedBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(255,255,255,0.25)',
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8,
  },
  convertedBadgeText: { fontSize: 11, fontWeight: '700', color: '#FFF' },

  // Quadrant Summary
  quadrantSummary: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 10, padding: 16, paddingBottom: 8,
  },
  quadrantBox: {
    width: '47%', flexGrow: 1, alignItems: 'center',
    padding: 12, borderRadius: 12, borderWidth: 1, gap: 4,
  },
  quadrantNum: { fontSize: 20, fontWeight: '800' },
  quadrantLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  quadrantNature: { fontSize: 10, color: COLORS.textMuted },

  // Sections
  sectionWrap: { paddingHorizontal: 16, marginTop: 16 },
  sectionHeader: {
    flexDirection: 'row', alignItems: 'center', marginBottom: 12, gap: 6,
  },
  sectionBullet: { width: 4, height: 20, borderRadius: 2 },
  sectionTitle: { flex: 1, fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  sectionNature: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600' },
  addItemBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8,
  },

  emptySection: {
    alignItems: 'center', paddingVertical: 20, gap: 6, borderRadius: 12,
  },
  emptyText: { fontSize: 13, color: COLORS.textMuted },

  // Item cards
  itemCard: {
    flexDirection: 'row', alignItems: 'flex-start',
    backgroundColor: '#FFF', borderRadius: 12, padding: 14,
    marginBottom: 10, borderLeftWidth: 4, borderWidth: 1, borderColor: '#F3F4F6',
  },
  itemText: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  itemDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 4 },
  impactRow: { flexDirection: 'row', alignItems: 'center', marginTop: 8, gap: 6 },
  impactLabel: { fontSize: 11, color: COLORS.textMuted },
  impactDots: { flexDirection: 'row', gap: 2 },
  impactDot: { width: 7, height: 7, borderRadius: 4 },
  impactVal: { fontSize: 11, fontWeight: '700' },
  removeBtn: { padding: 6, marginLeft: 8 },

  // Info box
  infoBox: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    margin: 16, padding: 14, backgroundColor: '#EEF2FF',
    borderRadius: 12, borderWidth: 1, borderColor: '#C7D2FE',
  },
  infoText: { flex: 1, fontSize: 12, color: '#4338CA', lineHeight: 17 },

  // Bottom bar
  bottomBar: {
    padding: 16, paddingBottom: 24,
    backgroundColor: '#FFF', borderTopWidth: 1, borderTopColor: '#E5E7EB',
  },
  convertBtn: { borderRadius: 14, overflow: 'hidden' },
  convertGradient: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingVertical: 16, gap: 10,
  },
  convertText: { fontSize: 16, fontWeight: '700', color: '#FFF' },

  // Modal
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end', alignItems: 'center',
  },
  modalContent: {
    width: '100%', maxWidth: 500,
    backgroundColor: '#FFF', borderTopLeftRadius: 24, borderTopRightRadius: 24,
    padding: 24, maxHeight: '85%',
  },
  modalHeader: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 20,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  inputLabel: {
    fontSize: 13, fontWeight: '600', color: COLORS.textSecondary,
    marginBottom: 6, marginTop: 4,
  },
  textInput: {
    backgroundColor: '#F9FAFB', borderRadius: 12, padding: 14,
    fontSize: 15, color: COLORS.textPrimary, borderWidth: 1,
    borderColor: '#E5E7EB', marginBottom: 12,
  },

  // Quadrant tag in modal
  quadrantTag: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    alignSelf: 'flex-start', paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 8, marginBottom: 16,
  },

  // Impact selector
  impactSelector: {
    flexDirection: 'row', gap: 4, marginBottom: 20, justifyContent: 'center',
  },
  impactSelectorBtn: {
    width: 30, height: 30, borderRadius: 8, justifyContent: 'center',
    alignItems: 'center', backgroundColor: '#F3F4F6',
  },
  impactSelectorText: { fontSize: 12, fontWeight: '700', color: COLORS.textSecondary },

  addConfirmBtn: {
    borderRadius: 12, paddingVertical: 14, alignItems: 'center',
  },
  addConfirmText: { fontSize: 16, fontWeight: '700', color: '#FFF' },

  // Life area chips
  lifeAreaChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20,
    backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: '#E5E7EB',
  },
  lifeAreaChipActive: { backgroundColor: '#1E40AF', borderColor: '#1E40AF' },
  lifeAreaChipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },

  // Create confirm
  createConfirmBtn: {
    backgroundColor: '#1E40AF', borderRadius: 14,
    paddingVertical: 16, alignItems: 'center',
  },
  createConfirmText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
