import React, { useState, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert, ActivityIndicator, Platform, KeyboardAvoidingView,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import { LIFE_AREAS as CATALOG_LIFE_AREAS } from '../../src/constants/lifeAreas';
import api from '../../src/utils/api';
import Slider from '@react-native-community/slider';
import { safeBack } from '../../src/utils/navigation';

const DIMENSIONS = [
  { id: 'time', name: 'Time', icon: 'time', color: '#3B82F6', desc: 'Time allocated & required' },
  { id: 'effort', name: 'Effort', icon: 'flash', color: '#F59E0B', desc: '8 components: Attitude to Action' },
  { id: 'people', name: 'People', icon: 'people', color: '#10B981', desc: 'Human resources involved' },
  { id: 'finance', name: 'Finance', icon: 'cash', color: '#8B5CF6', desc: 'Financial resources needed' },
  { id: 'infrastructure', name: 'Infrastructure', icon: 'construct', color: '#EF4444', desc: 'Tools, tech & facilities' },
];

const EFFORT_SUBS = [
  { id: 'attitude', name: 'Attitude', icon: 'happy', desc: 'Mindset & willingness' },
  { id: 'knowledge', name: 'Knowledge', icon: 'book', desc: 'Information & understanding' },
  { id: 'skills', name: 'Skills', icon: 'construct', desc: 'Practical abilities' },
  { id: 'physical_health', name: 'Physical Health', icon: 'fitness', desc: 'Physical capacity & health' },
  { id: 'mental_state', name: 'Mental State', icon: 'bulb', desc: 'Mental clarity & focus' },
  { id: 'emotional_wellness', name: 'Emotional Wellness', icon: 'heart', desc: 'Emotional resilience' },
  { id: 'energy_level', name: 'Energy Level', icon: 'flash', desc: 'Available energy & stamina' },
  { id: 'action', name: 'Action', icon: 'rocket', desc: 'Execution & initiative' },
];

const LAYERS = [
  { id: 'self', name: 'Self', icon: 'person', color: '#06B6D4', desc: 'Your personal resources' },
  { id: 'micro', name: 'Micro', icon: 'people-circle', color: '#F97316', desc: 'Immediate circle (family, team)' },
  { id: 'macro', name: 'Macro', icon: 'globe', color: '#8B5CF6', desc: 'Broader network & society' },
];

// Canonical L0 life areas — single source of truth from Catalog Manager.
// Aligned with Lifestyle Designer / AIM / Outlets so chip labels never drift.
const LIFE_AREAS = CATALOG_LIFE_AREAS.map(a => ({ id: a.id, name: a.short, icon: a.icon }));

type Matrix = Record<string, Record<string, { description: string; score: number; notes: string }>>;

function buildEmptyMatrix(): Matrix {
  const m: Matrix = {};
  DIMENSIONS.forEach(d => {
    if (d.id === 'effort') {
      // Effort has 8 sub-dimensions, each with 3 layers
      m[d.id] = {};
      EFFORT_SUBS.forEach(sub => {
        LAYERS.forEach(l => {
          const key = `${sub.id}_${l.id}`;
          m[d.id][key] = { description: '', score: 0, notes: '' };
        });
      });
      // Also keep aggregate layer-level entries for backward compat
      LAYERS.forEach(l => {
        m[d.id][l.id] = { description: '', score: 0, notes: '' };
      });
    } else {
      m[d.id] = {};
      LAYERS.forEach(l => {
        m[d.id][l.id] = { description: '', score: 0, notes: '' };
      });
    }
  });
  return m;
}

function getScoreColor(score: number): string {
  if (score >= 8) return '#10B981';
  if (score >= 6) return '#3B82F6';
  if (score >= 4) return '#F59E0B';
  if (score >= 2) return '#F97316';
  return '#EF4444';
}

export default function TEPFIEntryScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const editId = id as string | undefined;
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const [title, setTitle] = useState('');
  const [lifeArea, setLifeArea] = useState('');
  const [overallNotes, setOverallNotes] = useState('');
  const [matrix, setMatrix] = useState<Matrix>(buildEmptyMatrix());
  const [expandedDim, setExpandedDim] = useState<string>(DIMENSIONS[0].id);

  useEffect(() => { if (editId) loadEntry(); }, [editId]);

  const loadEntry = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/tepfi/entries/${editId}`);
      const d = res.data;
      setTitle(d.title || '');
      setLifeArea(d.life_area || '');
      setOverallNotes(d.overall_notes || '');
      if (d.matrix) setMatrix(d.matrix);
    } catch (e) {
      showAlert('Error', 'Failed to load entry');
      safeBack(router);
    } finally {
      setLoading(false);
    }
  };

  const updateCell = (dim: string, layer: string, field: string, value: any) => {
    setMatrix(prev => ({
      ...prev,
      [dim]: {
        ...prev[dim],
        [layer]: {
          ...prev[dim][layer],
          [field]: value,
        },
      },
    }));
  };

  const handleSave = async () => {
    if (!title.trim()) {
      showAlert('Required', 'Please enter a title for this assessment');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        title: title.trim(),
        life_area: lifeArea,
        matrix,
        overall_notes: overallNotes.trim(),
        status: 'active',
      };
      if (editId) {
        await api.put(`/tepfi/entries/${editId}`, payload);
      } else {
        await api.post('/tepfi/entries', payload);
      }
      safeBack(router);
    } catch (e) {
      showAlert('Error', 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={st.container}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#7C3AED" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <LinearGradient colors={['#7C3AED', '#A855F7']} style={st.header}>
          <TouchableOpacity onPress={() => safeBack(router)} style={st.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <Text style={st.headerTitle}>{editId ? 'Edit Assessment' : 'New Capabilities Assessment'}</Text>
        </LinearGradient>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 100 }} showsVerticalScrollIndicator={false}>
          {/* Title & Life Area */}
          <View style={st.section}>
            <Text style={st.label}>Assessment Title *</Text>
            <TextInput
              style={st.input}
              value={title}
              onChangeText={setTitle}
              placeholder="e.g. Career Development Resources Q1"
              placeholderTextColor={COLORS.textMuted}
            />

            <Text style={st.label}>Life Area</Text>
            {/* Flex-wrap chips so all 10 L0 areas are visible at-a-glance (no h-scroll). */}
            <View style={st.chipRow}>
              {LIFE_AREAS.map(a => (
                <TouchableOpacity
                  key={a.id}
                  style={[st.chip, lifeArea === a.id && st.chipActive]}
                  onPress={() => setLifeArea(lifeArea === a.id ? '' : a.id)}
                >
                  <Ionicons name={a.icon as any} size={12} color={lifeArea === a.id ? '#FFF' : COLORS.primary} />
                  <Text style={[st.chipText, lifeArea === a.id && { color: '#FFF' }]}>{a.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* TEPFI Dimensions */}
          {DIMENSIONS.map(dim => (
            <View key={dim.id}>
              <TouchableOpacity
                style={[st.dimHeader, expandedDim === dim.id && { backgroundColor: dim.color + '10' }]}
                onPress={() => setExpandedDim(expandedDim === dim.id ? '' : dim.id)}
              >
                <View style={[st.dimIconWrap, { backgroundColor: dim.color + '20' }]}>
                  <Ionicons name={dim.icon as any} size={20} color={dim.color} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={[st.dimName, { color: dim.color }]}>{dim.name}</Text>
                  <Text style={st.dimDesc}>{dim.desc}</Text>
                </View>
                {/* Quick score summary */}
                <View style={st.dimScores}>
                  {LAYERS.map(l => {
                    const score = matrix[dim.id]?.[l.id]?.score || 0;
                    return (
                      <View key={l.id} style={[st.dimScoreDot, { backgroundColor: score ? getScoreColor(score) : '#E5E7EB' }]}>
                        <Text style={st.dimScoreDotText}>{score || '-'}</Text>
                      </View>
                    );
                  })}
                </View>
                <Ionicons name={expandedDim === dim.id ? 'chevron-up' : 'chevron-down'} size={18} color={COLORS.textMuted} />
              </TouchableOpacity>

              {expandedDim === dim.id && (
                <View style={st.dimContent}>
                  {dim.id === 'effort' ? (
                    /* Effort: Show 8 sub-dimensions, each with 3 layers */
                    EFFORT_SUBS.map(sub => (
                      <View key={sub.id} style={st.layerCard}>
                        <View style={st.layerHeader}>
                          <Ionicons name={sub.icon as any} size={16} color="#F59E0B" />
                          <Text style={[st.layerName, { color: '#F59E0B' }]}>{sub.name}</Text>
                          <Text style={st.layerDesc}>{sub.desc}</Text>
                        </View>
                        {LAYERS.map(layer => {
                          const cellKey = `${sub.id}_${layer.id}`;
                          return (
                            <View key={layer.id} style={{ marginBottom: 8, paddingLeft: 4 }}>
                              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 2 }}>
                                <Ionicons name={layer.icon as any} size={12} color={layer.color} />
                                <Text style={{ fontSize: 11, fontWeight: '600', color: layer.color }}>{layer.name}</Text>
                                <Text style={{ fontSize: 11, fontWeight: '700', color: COLORS.textPrimary, marginLeft: 'auto' }}>
                                  {matrix[dim.id]?.[cellKey]?.score || 0}/10 · {(matrix[dim.id]?.[cellKey]?.score || 0) * 10}%
                                </Text>
                              </View>
                              <Slider
                                style={{ height: 28 }}
                                minimumValue={0}
                                maximumValue={10}
                                step={1}
                                value={matrix[dim.id]?.[cellKey]?.score || 0}
                                onValueChange={(v: number) => updateCell(dim.id, cellKey, 'score', Math.round(v))}
                                minimumTrackTintColor="#F59E0B"
                                maximumTrackTintColor={COLORS.divider}
                                thumbTintColor="#F59E0B"
                              />
                              <TextInput
                                style={[st.cellInput, { minHeight: 32, fontSize: 12 }]}
                                value={matrix[dim.id]?.[cellKey]?.description || ''}
                                onChangeText={(t) => updateCell(dim.id, cellKey, 'description', t)}
                                placeholder={`${sub.name} at ${layer.name.toLowerCase()} level?`}
                                placeholderTextColor={COLORS.textMuted}
                              />
                            </View>
                          );
                        })}
                      </View>
                    ))
                  ) : (
                    /* Other dimensions: Standard 3 layers */
                    LAYERS.map(layer => (
                    <View key={layer.id} style={st.layerCard}>
                      <View style={st.layerHeader}>
                        <Ionicons name={layer.icon as any} size={16} color={layer.color} />
                        <Text style={[st.layerName, { color: layer.color }]}>{layer.name}</Text>
                        <Text style={st.layerDesc}>{layer.desc}</Text>
                      </View>

                      <Text style={st.cellLabel}>
                        Score: {matrix[dim.id]?.[layer.id]?.score || 0}/10 · {(matrix[dim.id]?.[layer.id]?.score || 0) * 10}%
                      </Text>
                      <Slider
                        style={{ height: 40 }}
                        minimumValue={0}
                        maximumValue={10}
                        step={1}
                        value={matrix[dim.id]?.[layer.id]?.score || 0}
                        onValueChange={(v: number) => updateCell(dim.id, layer.id, 'score', Math.round(v))}
                        minimumTrackTintColor={dim.color}
                        maximumTrackTintColor={COLORS.divider}
                        thumbTintColor={dim.color}
                      />

                      <TextInput
                        style={st.cellInput}
                        value={matrix[dim.id]?.[layer.id]?.description || ''}
                        onChangeText={(t) => updateCell(dim.id, layer.id, 'description', t)}
                        placeholder={`What ${dim.name.toLowerCase()} resources at ${layer.name.toLowerCase()} level?`}
                        placeholderTextColor={COLORS.textMuted}
                        multiline
                      />

                      <TextInput
                        style={[st.cellInput, { minHeight: 48 }]}
                        value={matrix[dim.id]?.[layer.id]?.notes || ''}
                        onChangeText={(t) => updateCell(dim.id, layer.id, 'notes', t)}
                        placeholder="Additional notes..."
                        placeholderTextColor={COLORS.textMuted}
                        multiline
                      />
                    </View>
                  ))
                  )}
                </View>
              )}
            </View>
          ))}

          {/* Overall notes */}
          <View style={st.section}>
            <Text style={st.label}>Overall Notes</Text>
            <TextInput
              style={[st.input, { minHeight: 80, textAlignVertical: 'top' }]}
              value={overallNotes}
              onChangeText={setOverallNotes}
              placeholder="Summary observations about your resource allocation..."
              placeholderTextColor={COLORS.textMuted}
              multiline
              numberOfLines={4}
            />
          </View>
        </ScrollView>

        {/* Save button */}
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
                <Text style={st.saveBtnText}>{editId ? 'Update' : 'Save Assessment'}</Text>
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

  section: { paddingHorizontal: 16, paddingVertical: 12 },
  label: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12, marginBottom: 6 },
  input: { backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 14, paddingVertical: 12, fontSize: 14, color: COLORS.textPrimary },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, rowGap: 6 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  chipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  chipText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  // Dimension accordion
  dimHeader: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, backgroundColor: COLORS.white, borderTopWidth: 1, borderTopColor: COLORS.divider, marginTop: 4, gap: 10 },
  dimIconWrap: { width: 40, height: 40, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  dimName: { fontSize: 15, fontWeight: '700' },
  dimDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  dimScores: { flexDirection: 'row', gap: 4 },
  dimScoreDot: { width: 24, height: 24, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  dimScoreDotText: { fontSize: 10, fontWeight: '700', color: '#FFF' },

  dimContent: { paddingHorizontal: 16, paddingVertical: 8 },
  layerCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  layerHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  layerName: { fontSize: 13, fontWeight: '700' },
  layerDesc: { fontSize: 11, color: COLORS.textMuted, flex: 1 },
  cellLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary, marginTop: 4 },
  cellInput: { backgroundColor: COLORS.background, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 12, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary, marginTop: 6, minHeight: 40 },

  bottom: { padding: 16, paddingBottom: Platform.OS === 'ios' ? 20 : 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#7C3AED', borderRadius: 14, paddingVertical: 16 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
