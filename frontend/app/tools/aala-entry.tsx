import React, { useState, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Platform, KeyboardAvoidingView,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

interface AALAEntry {
  area_id: string;
  area_name: string;
  subcategory_id: string;
  subcategory_name: string;
  current_liabilities: string;
  current_liabilities_value: number;
  accrued_liabilities: string;
  accrued_liabilities_value: number;
  current_assets: string;
  current_assets_value: number;
  accrued_assets: string;
  accrued_assets_value: number;
  notes: string;
}

interface TaxonomyArea {
  area_id: string;
  area_name: string;
  area_number: number;
  icon: string;
  subcategories: { id: string; name: string }[];
}

const FREQ_OPTIONS = [
  { id: 'daily', label: 'Daily', icon: 'today' },
  { id: 'weekly', label: 'Weekly', icon: 'calendar' },
  { id: 'fortnightly', label: 'Fortnightly', icon: 'calendar-outline' },
];

const COL_COLORS = {
  current_liabilities: '#EF4444',
  accrued_liabilities: '#F97316',
  current_assets: '#10B981',
  accrued_assets: '#0EA5E9',
};

export default function AALAEntryScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const editId = params.id as string | undefined;
  const isBaseline = params.baseline === 'true';

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [taxonomy, setTaxonomy] = useState<TaxonomyArea[]>([]);
  const [title, setTitle] = useState(isBaseline ? 'Baseline Assessment' : 'Periodic Snapshot');
  const [frequency, setFrequency] = useState('weekly');
  const [baseline, setBaseline] = useState(isBaseline);
  const [summaryNotes, setSummaryNotes] = useState('');
  const [entries, setEntries] = useState<AALAEntry[]>([]);
  const [expandedArea, setExpandedArea] = useState('');

  useEffect(() => { loadTaxonomy(); }, []);
  useEffect(() => { if (editId) loadEntry(); }, [editId]);

  const loadTaxonomy = async () => {
    try {
      const res = await api.get('/aala/taxonomy');
      const tax: TaxonomyArea[] = res.data?.taxonomy || [];
      setTaxonomy(tax);
      if (!editId) {
        // Build empty entries from taxonomy
        const empty: AALAEntry[] = [];
        for (const area of tax) {
          if (area.subcategories.length === 0) {
            empty.push(makeEntry(area.area_id, area.area_name, area.area_id, area.area_name));
          } else {
            for (const sub of area.subcategories) {
              empty.push(makeEntry(area.area_id, area.area_name, sub.id, sub.name));
            }
          }
        }
        setEntries(empty);
      }
    } catch (e) { console.error('Taxonomy error:', e); }
  };

  const makeEntry = (areaId: string, areaName: string, subId: string, subName: string): AALAEntry => ({
    area_id: areaId, area_name: areaName,
    subcategory_id: subId, subcategory_name: subName,
    current_liabilities: '', current_liabilities_value: 0,
    accrued_liabilities: '', accrued_liabilities_value: 0,
    current_assets: '', current_assets_value: 0,
    accrued_assets: '', accrued_assets_value: 0,
    notes: '',
  });

  const loadEntry = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/aala/assessments/${editId}`);
      const d = res.data;
      setTitle(d.title || '');
      setFrequency(d.tracking_frequency || 'weekly');
      setBaseline(d.is_baseline || false);
      setSummaryNotes(d.summary_notes || '');
      setEntries(d.entries || []);
    } catch (e) {
      showAlert('Error', 'Failed to load assessment');
      safeBack(router);
    } finally { setLoading(false); }
  };

  const updateEntry = (idx: number, field: keyof AALAEntry, value: string | number) => {
    setEntries(prev => {
      const copy = [...prev];
      copy[idx] = { ...copy[idx], [field]: value };
      return copy;
    });
  };

  const handleSave = async () => {
    if (!title.trim()) { showAlert('Required', 'Please enter a title'); return; }
    setSaving(true);
    try {
      const payload = {
        title: title.trim(),
        tracking_frequency: frequency,
        is_baseline: baseline,
        entries,
        summary_notes: summaryNotes.trim(),
        status: 'active',
      };
      if (editId) {
        await api.put(`/aala/assessments/${editId}`, payload);
      } else {
        await api.post('/aala/assessments', payload);
      }
      showAlert('Saved', 'AALA Assessment saved!', [
        { text: 'OK', onPress: () => safeBack(router) }
      ]);
    } catch (e) {
      showAlert('Error', 'Failed to save');
    } finally { setSaving(false); }
  };

  const getAreaEntries = (areaId: string) => entries.filter(e => e.area_id === areaId);
  const getAreaFilledCount = (areaId: string) => {
    return getAreaEntries(areaId).filter(e =>
      e.current_liabilities || e.accrued_liabilities || e.current_assets || e.accrued_assets
    ).length;
  };

  if (loading) {
    return (
      <SafeAreaView style={st.container}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#2563EB" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <LinearGradient colors={['#0EA5E9', '#2563EB']} style={st.header}>
          <TouchableOpacity onPress={() => safeBack(router)} style={st.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <Text style={st.headerTitle}>{editId ? 'Edit Assessment' : baseline ? 'Baseline Assessment' : 'New Snapshot'}</Text>
        </LinearGradient>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 100 }} showsVerticalScrollIndicator={false}>
          {/* Title & Settings */}
          <View style={st.section}>
            <Text style={st.label}>Title *</Text>
            <TextInput style={st.input} value={title} onChangeText={setTitle}
              placeholder="Assessment title" placeholderTextColor={COLORS.textMuted} />

            <Text style={st.label}>Tracking Frequency</Text>
            <View style={st.freqRow}>
              {FREQ_OPTIONS.map(f => (
                <TouchableOpacity key={f.id}
                  style={[st.freqChip, frequency === f.id && st.freqActive]}
                  onPress={() => setFrequency(f.id)}
                >
                  <Ionicons name={f.icon as any} size={14} color={frequency === f.id ? '#FFF' : COLORS.textMuted} />
                  <Text style={[st.freqText, frequency === f.id && { color: '#FFF' }]}>{f.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <TouchableOpacity style={st.baselineToggle} onPress={() => setBaseline(!baseline)}>
              <Ionicons name={baseline ? 'checkbox' : 'square-outline'} size={20} color="#2563EB" />
              <Text style={st.baselineLabel}>Mark as Baseline Assessment</Text>
            </TouchableOpacity>
          </View>

          {/* Column Legend */}
          <View style={st.legendRow}>
            <View style={[st.legendDot, { backgroundColor: COL_COLORS.current_liabilities }]} />
            <Text style={st.legendText}>CL (≤1yr)</Text>
            <View style={[st.legendDot, { backgroundColor: COL_COLORS.accrued_liabilities }]} />
            <Text style={st.legendText}>AL</Text>
            <View style={[st.legendDot, { backgroundColor: COL_COLORS.current_assets }]} />
            <Text style={st.legendText}>CA (≤1yr)</Text>
            <View style={[st.legendDot, { backgroundColor: COL_COLORS.accrued_assets }]} />
            <Text style={st.legendText}>AA</Text>
          </View>

          {/* Life Areas Accordion */}
          {taxonomy.map(area => {
            const areaEntries = getAreaEntries(area.area_id);
            const filled = getAreaFilledCount(area.area_id);
            const isExpanded = expandedArea === area.area_id;

            return (
              <View key={area.area_id}>
                <TouchableOpacity
                  style={[st.areaHeader, isExpanded && { backgroundColor: '#EFF6FF' }]}
                  onPress={() => setExpandedArea(isExpanded ? '' : area.area_id)}
                >
                  <View style={st.areaIconWrap}>
                    <Ionicons name={area.icon as any} size={18} color="#2563EB" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={st.areaName}>{area.area_number}. {area.area_name}</Text>
                    <Text style={st.areaSub}>{filled}/{areaEntries.length} filled</Text>
                  </View>
                  {filled > 0 && (
                    <View style={st.filledBadge}>
                      <Text style={st.filledText}>{filled}</Text>
                    </View>
                  )}
                  <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color={COLORS.textMuted} />
                </TouchableOpacity>

                {isExpanded && (
                  <View style={st.areaContent}>
                    {areaEntries.map((entry, _i) => {
                      const idx = entries.findIndex(
                        e => e.area_id === entry.area_id && e.subcategory_id === entry.subcategory_id
                      );
                      return (
                        <View key={entry.subcategory_id} style={st.subCard}>
                          <Text style={st.subName}>{entry.subcategory_name}</Text>

                          {/* 4 columns: CL, AL, CA, AA */}
                          <View style={st.colGroup}>
                            <View style={st.colItem}>
                              <View style={[st.colDot, { backgroundColor: COL_COLORS.current_liabilities }]} />
                              <Text style={st.colLabel}>Current Liabilities</Text>
                              <TextInput style={st.colInput} placeholder="Description..."
                                placeholderTextColor={COLORS.textMuted}
                                value={entry.current_liabilities}
                                onChangeText={v => updateEntry(idx, 'current_liabilities', v)} multiline />
                              <TextInput style={st.colValInput} placeholder="Value (₹)"
                                placeholderTextColor={COLORS.textMuted} keyboardType="numeric"
                                value={entry.current_liabilities_value ? String(entry.current_liabilities_value) : ''}
                                onChangeText={v => updateEntry(idx, 'current_liabilities_value', parseFloat(v) || 0)} />
                            </View>

                            <View style={st.colItem}>
                              <View style={[st.colDot, { backgroundColor: COL_COLORS.accrued_liabilities }]} />
                              <Text style={st.colLabel}>Accrued Liabilities</Text>
                              <TextInput style={st.colInput} placeholder="Description..."
                                placeholderTextColor={COLORS.textMuted}
                                value={entry.accrued_liabilities}
                                onChangeText={v => updateEntry(idx, 'accrued_liabilities', v)} multiline />
                              <TextInput style={st.colValInput} placeholder="Value (₹)"
                                placeholderTextColor={COLORS.textMuted} keyboardType="numeric"
                                value={entry.accrued_liabilities_value ? String(entry.accrued_liabilities_value) : ''}
                                onChangeText={v => updateEntry(idx, 'accrued_liabilities_value', parseFloat(v) || 0)} />
                            </View>

                            <View style={st.colItem}>
                              <View style={[st.colDot, { backgroundColor: COL_COLORS.current_assets }]} />
                              <Text style={st.colLabel}>Current Assets</Text>
                              <TextInput style={st.colInput} placeholder="Description..."
                                placeholderTextColor={COLORS.textMuted}
                                value={entry.current_assets}
                                onChangeText={v => updateEntry(idx, 'current_assets', v)} multiline />
                              <TextInput style={st.colValInput} placeholder="Value (₹)"
                                placeholderTextColor={COLORS.textMuted} keyboardType="numeric"
                                value={entry.current_assets_value ? String(entry.current_assets_value) : ''}
                                onChangeText={v => updateEntry(idx, 'current_assets_value', parseFloat(v) || 0)} />
                            </View>

                            <View style={st.colItem}>
                              <View style={[st.colDot, { backgroundColor: COL_COLORS.accrued_assets }]} />
                              <Text style={st.colLabel}>Accrued Assets</Text>
                              <TextInput style={st.colInput} placeholder="Description..."
                                placeholderTextColor={COLORS.textMuted}
                                value={entry.accrued_assets}
                                onChangeText={v => updateEntry(idx, 'accrued_assets', v)} multiline />
                              <TextInput style={st.colValInput} placeholder="Value (₹)"
                                placeholderTextColor={COLORS.textMuted} keyboardType="numeric"
                                value={entry.accrued_assets_value ? String(entry.accrued_assets_value) : ''}
                                onChangeText={v => updateEntry(idx, 'accrued_assets_value', parseFloat(v) || 0)} />
                            </View>
                          </View>
                        </View>
                      );
                    })}
                  </View>
                )}
              </View>
            );
          })}

          {/* Summary Notes */}
          <View style={st.section}>
            <Text style={st.label}>Summary Notes</Text>
            <TextInput style={[st.input, { minHeight: 80, textAlignVertical: 'top' }]}
              value={summaryNotes} onChangeText={setSummaryNotes}
              placeholder="Overall observations about your assets & liabilities..."
              placeholderTextColor={COLORS.textMuted} multiline numberOfLines={4} />
          </View>
        </ScrollView>

        {/* Save button */}
        <View style={st.bottom}>
          <TouchableOpacity style={[st.saveBtn, saving && { opacity: 0.7 }]} onPress={handleSave} disabled={saving}>
            {saving ? <ActivityIndicator size="small" color="#FFF" /> : (
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
  label: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginTop: 10, marginBottom: 4 },
  input: { backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 14, paddingVertical: 12, fontSize: 14, color: COLORS.textPrimary },

  freqRow: { flexDirection: 'row', gap: 8, marginTop: 4 },
  freqChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  freqActive: { backgroundColor: '#2563EB', borderColor: '#2563EB' },
  freqText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },

  baselineToggle: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12, paddingVertical: 6 },
  baselineLabel: { fontSize: 13, fontWeight: '500', color: COLORS.textPrimary },

  legendRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 8, backgroundColor: COLORS.white, borderTopWidth: 1, borderBottomWidth: 1, borderColor: COLORS.divider },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted, marginRight: 6 },

  // Area accordion
  areaHeader: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider, gap: 10 },
  areaIconWrap: { width: 36, height: 36, borderRadius: 10, backgroundColor: '#EFF6FF', justifyContent: 'center', alignItems: 'center' },
  areaName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  areaSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  filledBadge: { backgroundColor: '#10B98120', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  filledText: { fontSize: 10, fontWeight: '700', color: '#10B981' },
  areaContent: { paddingHorizontal: 16, paddingVertical: 8, backgroundColor: '#F8FAFC' },

  subCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  subName: { fontSize: 13, fontWeight: '700', color: '#1E40AF', marginBottom: 8, borderBottomWidth: 1, borderBottomColor: COLORS.divider, paddingBottom: 6 },

  colGroup: { gap: 10 },
  colItem: { gap: 4 },
  colDot: { width: 8, height: 8, borderRadius: 4 },
  colLabel: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },
  colInput: { backgroundColor: COLORS.background, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 10, paddingVertical: 6, fontSize: 12, color: COLORS.textPrimary, minHeight: 36, textAlignVertical: 'top' },
  colValInput: { backgroundColor: COLORS.background, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 10, paddingVertical: 6, fontSize: 12, color: COLORS.textPrimary, width: 120 },

  bottom: { padding: 16, paddingBottom: Platform.OS === 'ios' ? 20 : 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#2563EB', borderRadius: 14, paddingVertical: 16 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
