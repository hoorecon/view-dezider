import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, TextInput, Modal, Switch,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

interface DecisionMode {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  weight_logic: string;
  config: any;
  active: boolean;
  order: number;
}

export default function DecisionModesScreen() {
  const router = useRouter();
  const [modes, setModes] = useState<DecisionMode[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingMode, setEditingMode] = useState<DecisionMode | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchModes = async () => {
    try {
      const res = await api.get('/collaboration/decision-modes');
      setModes(res.data || []);
    } catch (err) {
      console.error('Error fetching modes:', err);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchModes(); }, []));

  const handleToggleActive = async (mode: DecisionMode) => {
    try {
      await api.put(`/collaboration/decision-modes/${mode.id}`, { active: !mode.active });
      setModes(prev => prev.map(m => m.id === mode.id ? { ...m, active: !m.active } : m));
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to update');
    }
  };

  const handleSaveConfig = async () => {
    if (!editingMode) return;
    setSaving(true);
    try {
      await api.put(`/collaboration/decision-modes/${editingMode.id}`, {
        name: editingMode.name,
        description: editingMode.description,
        config: editingMode.config,
      });
      setModes(prev => prev.map(m => m.id === editingMode.id ? editingMode : m));
      setEditingMode(null);
      showAlert('Saved', 'Decision mode configuration updated.');
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const getModeIcon = (icon: string) => {
    const map: Record<string, string> = {
      people: 'people', 'hand-left': 'hand-left', shield: 'shield',
      school: 'school', options: 'options', 'checkmark-done-circle': 'checkmark-done-circle',
    };
    return (map[icon] || 'ellipse') as any;
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#4C1D95', '#7C3AED']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => safeBack(router)}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Decision Making Modes</Text>
          <Text style={styles.headerSub}>Configure how multi-user decisions are resolved</Text>
        </View>
      </LinearGradient>

      {loading ? (
        <View style={styles.centered}><ActivityIndicator size="large" color="#7C3AED" /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 100 }} showsVerticalScrollIndicator={false}>
          {/* Info */}
          <View style={styles.infoBox}>
            <Ionicons name="information-circle" size={18} color="#7C3AED" />
            <Text style={styles.infoText}>
              These modes determine how participant contributions are weighted and merged in group decisions and solution finders. Toggle modes on/off and configure their parameters.
            </Text>
          </View>

          {modes.map((mode, idx) => (
            <View key={mode.id} style={[styles.modeCard, !mode.active && { opacity: 0.6 }]}>
              <View style={styles.modeHeader}>
                <View style={[styles.modeIcon, { backgroundColor: mode.color }]}>
                  <Ionicons name={getModeIcon(mode.icon)} size={20} color="#FFF" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.modeName}>{mode.name}</Text>
                  <Text style={styles.modeDesc}>{mode.description}</Text>
                </View>
                <Switch
                  value={mode.active}
                  onValueChange={() => handleToggleActive(mode)}
                  trackColor={{ false: '#D1D5DB', true: mode.color + '80' }}
                  thumbColor={mode.active ? mode.color : '#9CA3AF'}
                />
              </View>

              {/* Weight Logic visual */}
              <View style={styles.weightVisual}>
                {mode.weight_logic === 'equal' && (
                  <View style={styles.weightRow}>
                    <View style={[styles.weightBar, { flex: 1, backgroundColor: mode.color + '30' }]}>
                      <Text style={styles.weightBarText}>Everyone gets equal weight</Text>
                    </View>
                  </View>
                )}
                {mode.weight_logic === 'command' && (
                  <View style={styles.weightRow}>
                    <View style={[styles.weightBar, { flex: mode.config?.leader_weight_pct || 50, backgroundColor: mode.color }]}>
                      <Text style={[styles.weightBarText, { color: '#FFF' }]}>Leader {mode.config?.leader_weight_pct || 50}%</Text>
                    </View>
                    <View style={[styles.weightBar, { flex: 100 - (mode.config?.leader_weight_pct || 50), backgroundColor: mode.color + '30' }]}>
                      <Text style={styles.weightBarText}>Others {100 - (mode.config?.leader_weight_pct || 50)}%</Text>
                    </View>
                  </View>
                )}
                {mode.weight_logic === 'sme' && (
                  <View style={styles.weightRow}>
                    <View style={[styles.weightBar, { flex: mode.config?.sme_total_weight_pct || 50, backgroundColor: mode.color }]}>
                      <Text style={[styles.weightBarText, { color: '#FFF' }]}>SMEs {mode.config?.sme_total_weight_pct || 50}%</Text>
                    </View>
                    <View style={[styles.weightBar, { flex: 100 - (mode.config?.sme_total_weight_pct || 50), backgroundColor: mode.color + '30' }]}>
                      <Text style={styles.weightBarText}>Others {100 - (mode.config?.sme_total_weight_pct || 50)}%</Text>
                    </View>
                  </View>
                )}
                {mode.weight_logic === 'voting' && (
                  <View style={styles.votingConfig}>
                    <Ionicons name="hand-left" size={14} color={mode.color} />
                    <Text style={styles.votingText}>
                      Threshold: {mode.config?.threshold_type === 'majority' ? 'Majority (51%)' : `Custom ${mode.config?.custom_threshold_pct || 51}%`}
                    </Text>
                  </View>
                )}
                {mode.weight_logic === 'custom' && (
                  <View style={styles.votingConfig}>
                    <Ionicons name="options" size={14} color={mode.color} />
                    <Text style={styles.votingText}>Owner assigns specific % to each participant</Text>
                  </View>
                )}
                {mode.weight_logic === 'consensus' && (
                  <View style={styles.votingConfig}>
                    <Ionicons name="checkmark-done" size={14} color={mode.color} />
                    <Text style={styles.votingText}>Requires 100% acceptance from all participants</Text>
                  </View>
                )}
              </View>

              {/* Configure button */}
              {mode.active && (mode.weight_logic === 'command' || mode.weight_logic === 'sme' || mode.weight_logic === 'voting') && (
                <TouchableOpacity style={[styles.configBtn, { borderColor: mode.color }]} onPress={() => setEditingMode({ ...mode })}>
                  <Ionicons name="settings-outline" size={14} color={mode.color} />
                  <Text style={[styles.configBtnText, { color: mode.color }]}>Configure</Text>
                </TouchableOpacity>
              )}
            </View>
          ))}
        </ScrollView>
      )}

      {/* Edit Modal */}
      {editingMode && (
        <Modal visible={true} transparent animationType="slide">
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Configure: {editingMode.name}</Text>
                <TouchableOpacity onPress={() => setEditingMode(null)}>
                  <Ionicons name="close" size={24} color={COLORS.textSecondary} />
                </TouchableOpacity>
              </View>

              {editingMode.weight_logic === 'command' && (
                <View>
                  <Text style={styles.configLabel}>Leader Weight %</Text>
                  <Text style={styles.configHint}>The main user (session owner) gets this % of the total weight.</Text>
                  <View style={styles.sliderRow}>
                    {[30, 40, 50, 60, 70].map(v => (
                      <TouchableOpacity key={v}
                        style={[styles.pctBtn, editingMode.config?.leader_weight_pct === v && { backgroundColor: editingMode.color }]}
                        onPress={() => setEditingMode({ ...editingMode, config: { ...editingMode.config, leader_weight_pct: v } })}>
                        <Text style={[styles.pctBtnText, editingMode.config?.leader_weight_pct === v && { color: '#FFF' }]}>{v}%</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              )}

              {editingMode.weight_logic === 'sme' && (
                <View>
                  <Text style={styles.configLabel}>SME Combined Weight %</Text>
                  <Text style={styles.configHint}>Total weight shared among all designated SMEs. Rest is split equally among non-SME participants.</Text>
                  <View style={styles.sliderRow}>
                    {[30, 40, 50, 60, 70].map(v => (
                      <TouchableOpacity key={v}
                        style={[styles.pctBtn, editingMode.config?.sme_total_weight_pct === v && { backgroundColor: editingMode.color }]}
                        onPress={() => setEditingMode({ ...editingMode, config: { ...editingMode.config, sme_total_weight_pct: v } })}>
                        <Text style={[styles.pctBtnText, editingMode.config?.sme_total_weight_pct === v && { color: '#FFF' }]}>{v}%</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              )}

              {editingMode.weight_logic === 'voting' && (
                <View>
                  <Text style={styles.configLabel}>Threshold Type</Text>
                  <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
                    <TouchableOpacity
                      style={[styles.thresholdBtn, editingMode.config?.threshold_type === 'majority' && { backgroundColor: editingMode.color, borderColor: editingMode.color }]}
                      onPress={() => setEditingMode({ ...editingMode, config: { ...editingMode.config, threshold_type: 'majority', custom_threshold_pct: 51 } })}>
                      <Text style={[styles.thresholdText, editingMode.config?.threshold_type === 'majority' && { color: '#FFF' }]}>Majority (51%)</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[styles.thresholdBtn, editingMode.config?.threshold_type === 'custom' && { backgroundColor: editingMode.color, borderColor: editingMode.color }]}
                      onPress={() => setEditingMode({ ...editingMode, config: { ...editingMode.config, threshold_type: 'custom' } })}>
                      <Text style={[styles.thresholdText, editingMode.config?.threshold_type === 'custom' && { color: '#FFF' }]}>Custom %</Text>
                    </TouchableOpacity>
                  </View>
                  {editingMode.config?.threshold_type === 'custom' && (
                    <View>
                      <Text style={styles.configLabel}>Custom Threshold %</Text>
                      <View style={styles.sliderRow}>
                        {[51, 60, 67, 75, 80, 90].map(v => (
                          <TouchableOpacity key={v}
                            style={[styles.pctBtn, editingMode.config?.custom_threshold_pct === v && { backgroundColor: editingMode.color }]}
                            onPress={() => setEditingMode({ ...editingMode, config: { ...editingMode.config, custom_threshold_pct: v } })}>
                            <Text style={[styles.pctBtnText, editingMode.config?.custom_threshold_pct === v && { color: '#FFF' }]}>{v}%</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  )}
                </View>
              )}

              <TouchableOpacity style={[styles.saveConfigBtn, { backgroundColor: editingMode.color }]} onPress={handleSaveConfig} disabled={saving}>
                {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.saveConfigText}>Save Configuration</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingTop: 12, paddingBottom: 18, gap: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  infoBox: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, backgroundColor: '#F5F3FF', borderRadius: 12, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: '#DDD6FE' },
  infoText: { flex: 1, fontSize: 12, color: '#5B21B6', lineHeight: 17 },
  modeCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#E5E7EB' },
  modeHeader: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  modeIcon: { width: 40, height: 40, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  modeName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  modeDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2, paddingRight: 40 },
  weightVisual: { marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: '#F3F4F6' },
  weightRow: { flexDirection: 'row', height: 28, borderRadius: 8, overflow: 'hidden', gap: 2 },
  weightBar: { justifyContent: 'center', alignItems: 'center', borderRadius: 6 },
  weightBarText: { fontSize: 10, fontWeight: '700', color: COLORS.textSecondary },
  votingConfig: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  votingText: { fontSize: 12, color: COLORS.textSecondary },
  configBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', marginTop: 10, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, borderWidth: 1 },
  configBtnText: { fontSize: 12, fontWeight: '600' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end', alignItems: 'center' },
  modalContent: { width: '100%', maxWidth: 500, backgroundColor: '#FFF', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  configLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  configHint: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 12 },
  sliderRow: { flexDirection: 'row', gap: 8, marginBottom: 16, flexWrap: 'wrap' },
  pctBtn: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 10, backgroundColor: '#F3F4F6' },
  pctBtnText: { fontSize: 14, fontWeight: '700', color: COLORS.textSecondary },
  thresholdBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: 'center', backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: '#E5E7EB' },
  thresholdText: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  saveConfigBtn: { borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 8 },
  saveConfigText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
