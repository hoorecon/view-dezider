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

interface ProConItem {
  id: string;
  text: string;
  description: string;
  importance: number;
}

interface ProsConsAnalysis {
  id: string;
  title: string;
  context: string;
  life_area: string | null;
  decision_type: string | null;
  pros: ProConItem[];
  cons: ProConItem[];
  converted_decision_id: string | null;
  created_at: string;
}

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

export default function ProsConsScreen() {
  const router = useRouter();
  const [analyses, setAnalyses] = useState<ProsConsAnalysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Create modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newContext, setNewContext] = useState('');
  const [newLifeArea, setNewLifeArea] = useState('');
  const [creating, setCreating] = useState(false);

  // Detail/Edit view
  const [selectedAnalysis, setSelectedAnalysis] = useState<ProsConsAnalysis | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [addingTo, setAddingTo] = useState<'pro' | 'con' | null>(null);
  const [newItemText, setNewItemText] = useState('');
  const [newItemDesc, setNewItemDesc] = useState('');
  const [newItemImportance, setNewItemImportance] = useState(5);
  const [converting, setConverting] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchAnalyses = async () => {
    try {
      const res = await api.get('/pros-cons');
      setAnalyses(res.data || []);
    } catch (err) {
      console.error('Error fetching pros-cons:', err);
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
      showAlert('Required', 'Please enter a title for your analysis');
      return;
    }
    setCreating(true);
    try {
      const res = await api.post('/pros-cons', {
        title: newTitle.trim(),
        context: newContext.trim(),
        life_area: newLifeArea || null,
      });
      setShowCreateModal(false);
      setNewTitle('');
      setNewContext('');
      setNewLifeArea('');
      await fetchAnalyses();
      // Open the newly created analysis
      const newDoc = await api.get(`/pros-cons/${res.data.id}`);
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
      const res = await api.get(`/pros-cons/${id}`);
      setSelectedAnalysis(res.data);
      setShowDetail(true);
    } catch (err) {
      showAlert('Error', 'Failed to load analysis');
    }
  };

  const handleAddItem = async () => {
    if (!newItemText.trim() || !selectedAnalysis || !addingTo) return;
    const newItem = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      text: newItemText.trim(),
      description: newItemDesc.trim(),
      importance: newItemImportance,
    };

    const updatedPros = addingTo === 'pro'
      ? [...(selectedAnalysis.pros || []), newItem]
      : selectedAnalysis.pros;
    const updatedCons = addingTo === 'con'
      ? [...(selectedAnalysis.cons || []), newItem]
      : selectedAnalysis.cons;

    setSaving(true);
    try {
      await api.put(`/pros-cons/${selectedAnalysis.id}`, {
        pros: updatedPros,
        cons: updatedCons,
      });
      setSelectedAnalysis({ ...selectedAnalysis, pros: updatedPros, cons: updatedCons });
      setNewItemText('');
      setNewItemDesc('');
      setNewItemImportance(5);
      setAddingTo(null);
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to save item');
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveItem = async (type: 'pro' | 'con', itemId: string) => {
    if (!selectedAnalysis) return;
    const updatedPros = type === 'pro'
      ? selectedAnalysis.pros.filter(p => p.id !== itemId)
      : selectedAnalysis.pros;
    const updatedCons = type === 'con'
      ? selectedAnalysis.cons.filter(c => c.id !== itemId)
      : selectedAnalysis.cons;

    try {
      await api.put(`/pros-cons/${selectedAnalysis.id}`, {
        pros: updatedPros,
        cons: updatedCons,
      });
      setSelectedAnalysis({ ...selectedAnalysis, pros: updatedPros, cons: updatedCons });
    } catch (err) {
      showAlert('Error', 'Failed to remove item');
    }
  };

  const handleConvertToDecision = async () => {
    if (!selectedAnalysis) return;
    if (selectedAnalysis.converted_decision_id) {
      showAlert('Already Converted', 'This analysis has already been converted to a PRR Decision.');
      return;
    }
    const totalItems = (selectedAnalysis.pros?.length || 0) + (selectedAnalysis.cons?.length || 0);
    if (totalItems === 0) {
      showAlert('Empty', 'Add at least one pro or con before converting.');
      return;
    }

    showAlert(
      'Convert to PRR Decision',
      `This will create a PRR Decision with ${totalItems} factors.\n\nPros → Factors (as-is)\nCons → Factors (prefixed with "NOT")\n\nAI will generate expected values for each factor.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Convert',
          style: 'default',
          onPress: async () => {
            setConverting(true);
            try {
              const res = await api.post(`/pros-cons/${selectedAnalysis.id}/convert-to-decision`);
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
    showAlert('Delete Analysis', 'Are you sure you want to delete this analysis?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try {
            await api.delete(`/pros-cons/${id}`);
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
            colors={['#059669', '#10B981']}
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
            {/* Score Summary */}
            <View style={styles.scoreSummary}>
              <View style={[styles.scoreBox, { backgroundColor: '#ECFDF5', borderColor: '#A7F3D0' }]}>
                <Ionicons name="thumbs-up" size={20} color="#059669" />
                <Text style={[styles.scoreNum, { color: '#059669' }]}>{selectedAnalysis.pros?.length || 0}</Text>
                <Text style={styles.scoreLabel}>Pros</Text>
              </View>
              <View style={[styles.scoreBox, { backgroundColor: '#FEF2F2', borderColor: '#FECACA' }]}>
                <Ionicons name="thumbs-down" size={20} color="#DC2626" />
                <Text style={[styles.scoreNum, { color: '#DC2626' }]}>{selectedAnalysis.cons?.length || 0}</Text>
                <Text style={styles.scoreLabel}>Cons</Text>
              </View>
              <View style={[styles.scoreBox, { backgroundColor: '#EFF6FF', borderColor: '#BFDBFE' }]}>
                <Ionicons name="analytics" size={20} color="#2563EB" />
                <Text style={[styles.scoreNum, { color: '#2563EB' }]}>
                  {(selectedAnalysis.pros?.length || 0) + (selectedAnalysis.cons?.length || 0)}
                </Text>
                <Text style={styles.scoreLabel}>Total</Text>
              </View>
            </View>

            {/* PROS Section */}
            <View style={styles.sectionWrap}>
              <View style={styles.sectionHeader}>
                <View style={[styles.sectionBullet, { backgroundColor: '#059669' }]} />
                <Text style={styles.sectionTitle}>Pros</Text>
                <TouchableOpacity
                  style={[styles.addItemBtn, { backgroundColor: '#ECFDF5' }]}
                  onPress={() => { setAddingTo('pro'); setNewItemText(''); setNewItemDesc(''); setNewItemImportance(5); }}
                >
                  <Ionicons name="add" size={18} color="#059669" />
                  <Text style={{ color: '#059669', fontWeight: '600', fontSize: 13 }}>Add Pro</Text>
                </TouchableOpacity>
              </View>
              {(selectedAnalysis.pros || []).length === 0 ? (
                <View style={styles.emptySection}>
                  <Ionicons name="thumbs-up-outline" size={28} color="#D1FAE5" />
                  <Text style={styles.emptyText}>No pros added yet</Text>
                </View>
              ) : (
                (selectedAnalysis.pros || []).map((item, idx) => (
                  <View key={item.id} style={[styles.itemCard, { borderLeftColor: '#059669' }]}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.itemText}>{item.text}</Text>
                      {item.description ? <Text style={styles.itemDesc}>{item.description}</Text> : null}
                      <View style={styles.importanceRow}>
                        <Text style={styles.importanceLabel}>Importance:</Text>
                        <View style={styles.importanceDots}>
                          {[...Array(10)].map((_, i) => (
                            <View
                              key={i}
                              style={[
                                styles.importanceDot,
                                { backgroundColor: i < item.importance ? '#059669' : '#E5E7EB' }
                              ]}
                            />
                          ))}
                        </View>
                        <Text style={[styles.importanceVal, { color: '#059669' }]}>{item.importance}/10</Text>
                      </View>
                    </View>
                    <TouchableOpacity
                      style={styles.removeBtn}
                      onPress={() => handleRemoveItem('pro', item.id)}
                    >
                      <Ionicons name="trash-outline" size={16} color="#9CA3AF" />
                    </TouchableOpacity>
                  </View>
                ))
              )}
            </View>

            {/* CONS Section */}
            <View style={styles.sectionWrap}>
              <View style={styles.sectionHeader}>
                <View style={[styles.sectionBullet, { backgroundColor: '#DC2626' }]} />
                <Text style={styles.sectionTitle}>Cons</Text>
                <TouchableOpacity
                  style={[styles.addItemBtn, { backgroundColor: '#FEF2F2' }]}
                  onPress={() => { setAddingTo('con'); setNewItemText(''); setNewItemDesc(''); setNewItemImportance(5); }}
                >
                  <Ionicons name="add" size={18} color="#DC2626" />
                  <Text style={{ color: '#DC2626', fontWeight: '600', fontSize: 13 }}>Add Con</Text>
                </TouchableOpacity>
              </View>
              {(selectedAnalysis.cons || []).length === 0 ? (
                <View style={styles.emptySection}>
                  <Ionicons name="thumbs-down-outline" size={28} color="#FECACA" />
                  <Text style={styles.emptyText}>No cons added yet</Text>
                </View>
              ) : (
                (selectedAnalysis.cons || []).map((item, idx) => (
                  <View key={item.id} style={[styles.itemCard, { borderLeftColor: '#DC2626' }]}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.itemText}>{item.text}</Text>
                      {item.description ? <Text style={styles.itemDesc}>{item.description}</Text> : null}
                      <View style={styles.importanceRow}>
                        <Text style={styles.importanceLabel}>Importance:</Text>
                        <View style={styles.importanceDots}>
                          {[...Array(10)].map((_, i) => (
                            <View
                              key={i}
                              style={[
                                styles.importanceDot,
                                { backgroundColor: i < item.importance ? '#DC2626' : '#E5E7EB' }
                              ]}
                            />
                          ))}
                        </View>
                        <Text style={[styles.importanceVal, { color: '#DC2626' }]}>{item.importance}/10</Text>
                      </View>
                    </View>
                    <TouchableOpacity
                      style={styles.removeBtn}
                      onPress={() => handleRemoveItem('con', item.id)}
                    >
                      <Ionicons name="trash-outline" size={16} color="#9CA3AF" />
                    </TouchableOpacity>
                  </View>
                ))
              )}
            </View>

            {/* How it converts info */}
            <View style={styles.infoBox}>
              <Ionicons name="information-circle" size={18} color="#6366F1" />
              <Text style={styles.infoText}>
                When you convert: Pros become PRR factors as-is. Cons are prefixed with "NOT" (e.g., "High cost" → "NOT High cost") and become factors. AI generates expected values for each.
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
                      Add {addingTo === 'pro' ? 'Pro' : 'Con'}
                    </Text>
                    <TouchableOpacity onPress={() => setAddingTo(null)}>
                      <Ionicons name="close" size={24} color={COLORS.textSecondary} />
                    </TouchableOpacity>
                  </View>

                  <Text style={styles.inputLabel}>
                    {addingTo === 'pro' ? 'What is the advantage?' : 'What is the disadvantage?'}
                  </Text>
                  <TextInput
                    style={styles.textInput}
                    placeholder={addingTo === 'pro' ? 'e.g., Higher salary' : 'e.g., Longer commute'}
                    value={newItemText}
                    onChangeText={setNewItemText}
                    autoFocus
                  />

                  <Text style={styles.inputLabel}>Description (optional)</Text>
                  <TextInput
                    style={[styles.textInput, { height: 60 }]}
                    placeholder="Add more context..."
                    value={newItemDesc}
                    onChangeText={setNewItemDesc}
                    multiline
                  />

                  <Text style={styles.inputLabel}>Importance: {newItemImportance}/10</Text>
                  <View style={styles.importanceSelector}>
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                      <TouchableOpacity
                        key={n}
                        style={[
                          styles.importanceBtn,
                          n <= newItemImportance && {
                            backgroundColor: addingTo === 'pro' ? '#059669' : '#DC2626'
                          }
                        ]}
                        onPress={() => setNewItemImportance(n)}
                      >
                        <Text style={[
                          styles.importanceBtnText,
                          n <= newItemImportance && { color: '#FFF' }
                        ]}>{n}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  <TouchableOpacity
                    style={[
                      styles.addConfirmBtn,
                      { backgroundColor: addingTo === 'pro' ? '#059669' : '#DC2626' }
                    ]}
                    onPress={handleAddItem}
                    disabled={saving || !newItemText.trim()}
                  >
                    {saving ? (
                      <ActivityIndicator color="#FFF" size="small" />
                    ) : (
                      <Text style={styles.addConfirmText}>
                        Add {addingTo === 'pro' ? 'Pro' : 'Con'}
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
        colors={['#059669', '#10B981']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.header}
      >
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Pros & Cons</Text>
          <Text style={styles.headerSub}>Weigh advantages vs disadvantages → PRR</Text>
        </View>
        <TouchableOpacity
          style={styles.createBtn}
          onPress={() => setShowCreateModal(true)}
        >
          <Ionicons name="add" size={22} color="#059669" />
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
            <Ionicons name="bulb-outline" size={20} color="#F59E0B" />
            <Text style={styles.howItWorksText}>
              List your pros & cons, rate importance, then convert to a full PRR Decision with AI-generated expected values.
            </Text>
          </View>

          {analyses.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="swap-horizontal-outline" size={48} color="#D1D5DB" />
              <Text style={styles.emptyStateTitle}>No Analyses Yet</Text>
              <Text style={styles.emptyStateText}>
                Create your first Pros & Cons analysis to start making better decisions.
              </Text>
              <TouchableOpacity
                style={styles.emptyCreateBtn}
                onPress={() => setShowCreateModal(true)}
              >
                <Ionicons name="add" size={20} color="#FFF" />
                <Text style={styles.emptyCreateText}>Create Analysis</Text>
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
                      <Ionicons name="checkmark-circle" size={12} color="#059669" />
                      <Text style={styles.prrBadgeText}>PRR</Text>
                    </View>
                  )}
                </View>
                <View style={styles.listCardStats}>
                  <View style={styles.listStatChip}>
                    <Ionicons name="thumbs-up" size={13} color="#059669" />
                    <Text style={[styles.listStatText, { color: '#059669' }]}>
                      {a.pros?.length || 0} Pros
                    </Text>
                  </View>
                  <View style={styles.listStatChip}>
                    <Ionicons name="thumbs-down" size={13} color="#DC2626" />
                    <Text style={[styles.listStatText, { color: '#DC2626' }]}>
                      {a.cons?.length || 0} Cons
                    </Text>
                  </View>
                  <View style={{ flex: 1 }} />
                  <TouchableOpacity
                    style={styles.deleteBtn}
                    onPress={(e) => { e.stopPropagation(); handleDelete(a.id); }}
                  >
                    <Ionicons name="trash-outline" size={16} color="#9CA3AF" />
                  </TouchableOpacity>
                </View>
                <Text style={styles.listCardDate}>
                  {new Date(a.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                </Text>
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
                <Text style={styles.modalTitle}>New Pros & Cons Analysis</Text>
                <TouchableOpacity onPress={() => setShowCreateModal(false)}>
                  <Ionicons name="close" size={24} color={COLORS.textSecondary} />
                </TouchableOpacity>
              </View>

              <Text style={styles.inputLabel}>Decision / Topic *</Text>
              <TextInput
                style={styles.textInput}
                placeholder="e.g., Should I take the new job offer?"
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
                  <Text style={styles.createConfirmText}>Create Analysis</Text>
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
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    paddingTop: 12,
    paddingBottom: 20,
    gap: 12,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 12, color: 'rgba(255,255,255,0.8)', marginTop: 2 },
  createBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: '#FFF',
    justifyContent: 'center', alignItems: 'center',
  },

  // How it works
  howItWorks: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    backgroundColor: '#FFFBEB', borderRadius: 12, padding: 14,
    marginBottom: 16, borderWidth: 1, borderColor: '#FDE68A',
  },
  howItWorksText: { flex: 1, fontSize: 13, color: '#92400E', lineHeight: 18 },

  // Empty state
  emptyState: {
    alignItems: 'center', paddingVertical: 48, gap: 12,
  },
  emptyStateTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptyStateText: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', paddingHorizontal: 32 },
  emptyCreateBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#059669', paddingHorizontal: 20, paddingVertical: 12,
    borderRadius: 12, marginTop: 8,
  },
  emptyCreateText: { fontSize: 15, fontWeight: '600', color: '#FFF' },

  // List card
  listCard: {
    backgroundColor: '#FFF', borderRadius: 14, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: '#E5E7EB',
  },
  listCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  listCardTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  listCardContext: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  prrBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#ECFDF5', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8,
  },
  prrBadgeText: { fontSize: 11, fontWeight: '700', color: '#059669' },
  listCardStats: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  listStatChip: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  listStatText: { fontSize: 13, fontWeight: '600' },
  deleteBtn: { padding: 6 },
  listCardDate: { fontSize: 11, color: COLORS.textMuted, marginTop: 8 },

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

  // Score summary
  scoreSummary: {
    flexDirection: 'row', gap: 12, padding: 16, paddingBottom: 8,
  },
  scoreBox: {
    flex: 1, alignItems: 'center', padding: 12, borderRadius: 12,
    borderWidth: 1, gap: 4,
  },
  scoreNum: { fontSize: 22, fontWeight: '800' },
  scoreLabel: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '600' },

  // Sections
  sectionWrap: { paddingHorizontal: 16, marginTop: 16 },
  sectionHeader: {
    flexDirection: 'row', alignItems: 'center', marginBottom: 12, gap: 8,
  },
  sectionBullet: { width: 4, height: 20, borderRadius: 2 },
  sectionTitle: { flex: 1, fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  addItemBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8,
  },

  emptySection: {
    alignItems: 'center', paddingVertical: 24, gap: 8,
    backgroundColor: '#F9FAFB', borderRadius: 12,
  },
  emptyText: { fontSize: 13, color: COLORS.textMuted },

  // Item cards
  itemCard: {
    flexDirection: 'row', alignItems: 'flex-start',
    backgroundColor: '#FFF', borderRadius: 12, padding: 14,
    marginBottom: 10, borderLeftWidth: 4, borderWidth: 1, borderColor: '#F3F4F6',
  },
  itemText: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  itemDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 4 },
  importanceRow: { flexDirection: 'row', alignItems: 'center', marginTop: 8, gap: 6 },
  importanceLabel: { fontSize: 11, color: COLORS.textMuted },
  importanceDots: { flexDirection: 'row', gap: 2 },
  importanceDot: { width: 8, height: 8, borderRadius: 4 },
  importanceVal: { fontSize: 11, fontWeight: '700' },
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

  // Importance selector
  importanceSelector: {
    flexDirection: 'row', gap: 4, marginBottom: 20, justifyContent: 'center',
  },
  importanceBtn: {
    width: 30, height: 30, borderRadius: 8, justifyContent: 'center',
    alignItems: 'center', backgroundColor: '#F3F4F6',
  },
  importanceBtnText: { fontSize: 12, fontWeight: '700', color: COLORS.textSecondary },

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
  lifeAreaChipActive: { backgroundColor: '#059669', borderColor: '#059669' },
  lifeAreaChipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },

  // Create confirm
  createConfirmBtn: {
    backgroundColor: '#059669', borderRadius: 14,
    paddingVertical: 16, alignItems: 'center',
  },
  createConfirmText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
