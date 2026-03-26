import React, { useState, useEffect } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator,
  StyleSheet, Alert, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';

const COLORS = {
  bg: '#0F172A', surface: '#1E293B', surfaceLight: '#334155',
  primary: '#3B82F6', secondary: '#8B5CF6', accent: '#10B981',
  text: '#F8FAFC', textSecondary: '#94A3B8', textMuted: '#64748B',
  border: '#334155', danger: '#EF4444',
};

const TYPES = [
  { id: 'PRODUCT', icon: 'cube', label: 'Product', color: '#3B82F6' },
  { id: 'SERVICE', icon: 'construct', label: 'Service', color: '#10B981' },
  { id: 'EVENT', icon: 'calendar', label: 'Event', color: '#F59E0B' },
  { id: 'PROJECT', icon: 'rocket', label: 'Project', color: '#8B5CF6' },
  { id: 'PERSON_CONTACT', icon: 'person', label: 'Person', color: '#EC4899' },
];

const VISIBILITY = [
  { id: 'PRIVATE', icon: 'lock-closed', label: 'Private (Only Me)' },
  { id: 'ORG', icon: 'people', label: 'My Organization' },
];

export default function AddSolutionScreen() {
  const router = useRouter();
  const { session } = useAuthStore();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [lifeAreas, setLifeAreas] = useState<any[]>([]);
  const [subAreas, setSubAreas] = useState<any[]>([]);

  // Form data
  const [form, setForm] = useState({
    type: '', name: '', description: '', provider: '', url: '',
    price_range: '', currency: 'INR', visibility: 'PRIVATE',
    life_area_id: '', sub_area_id: '', country: 'IN', state: 'TN', city: 'Chennai',
    tags: '',
  });
  const [typeSpecific, setTypeSpecific] = useState<Record<string, string>>({});
  const [quantFactors, setQuantFactors] = useState<Array<{ factor_name: string; value: string; unit: string }>>([
    { factor_name: '', value: '', unit: '' },
  ]);

  useEffect(() => {
    api.get('/hos/life-areas').then(r => setLifeAreas(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (form.life_area_id) {
      api.get('/hos/sub-areas', { params: { life_area_id: form.life_area_id } })
        .then(r => setSubAreas(r.data)).catch(() => {});
    }
  }, [form.life_area_id]);

  const updateForm = (key: string, value: string) => setForm(prev => ({ ...prev, [key]: value }));

  const addQuantFactor = () => setQuantFactors(prev => [...prev, { factor_name: '', value: '', unit: '' }]);
  const removeQuantFactor = (i: number) => setQuantFactors(prev => prev.filter((_, idx) => idx !== i));
  const updateQuantFactor = (i: number, key: string, val: string) =>
    setQuantFactors(prev => prev.map((f, idx) => idx === i ? { ...f, [key]: val } : f));

  const TYPE_FIELDS: Record<string, string[]> = {
    PRODUCT: ['brand', 'model', 'warranty_months', 'specifications'],
    SERVICE: ['duration', 'frequency', 'delivery_mode', 'availability'],
    EVENT: ['event_date', 'location', 'venue', 'capacity'],
    PROJECT: ['timeline_months', 'team_size', 'budget'],
    PERSON_CONTACT: ['phone', 'email', 'designation', 'organization', 'expertise'],
  };

  const submit = async () => {
    if (!form.name.trim()) return Alert.alert('Error', 'Name is required');
    if (!form.type) return Alert.alert('Error', 'Select a type');
    if (!form.life_area_id) return Alert.alert('Error', 'Select a life area');

    setSubmitting(true);
    try {
      const body = {
        ...form,
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
        type_specific: typeSpecific,
        quantitative_factors: quantFactors
          .filter(f => f.factor_name.trim())
          .map(f => ({
            factor_name: f.factor_name,
            value: isNaN(Number(f.value)) ? f.value : Number(f.value),
            unit: f.unit,
            data_type: isNaN(Number(f.value)) ? 'text' : 'numeric',
          })),
      };

      await api.post('/solutions-store/solutions', body, {
        headers: { Authorization: `Bearer ${session}` },
      });

      Alert.alert('Success', 'Solution added to store!', [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail || 'Failed to create solution');
    } finally {
      setSubmitting(false);
    }
  };

  const renderStep0 = () => (
    <>
      <Text style={styles.stepTitle}>What type of solution?</Text>
      <View style={styles.typeGrid}>
        {TYPES.map(t => (
          <TouchableOpacity
            key={t.id}
            style={[styles.typeCard, form.type === t.id && { borderColor: t.color, backgroundColor: t.color + '15' }]}
            onPress={() => { updateForm('type', t.id); setStep(1); }}
          >
            <Ionicons name={t.icon as any} size={28} color={form.type === t.id ? t.color : COLORS.textMuted} />
            <Text style={[styles.typeLabel, form.type === t.id && { color: t.color }]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </>
  );

  const renderStep1 = () => (
    <>
      <Text style={styles.stepTitle}>Basic Details</Text>
      <Text style={styles.inputLabel}>Name *</Text>
      <TextInput style={styles.input} placeholder="Solution name" placeholderTextColor={COLORS.textMuted}
        value={form.name} onChangeText={v => updateForm('name', v)} />

      <Text style={styles.inputLabel}>Description</Text>
      <TextInput style={[styles.input, { height: 80, textAlignVertical: 'top' }]} placeholder="Describe this solution..."
        placeholderTextColor={COLORS.textMuted} value={form.description} onChangeText={v => updateForm('description', v)} multiline />

      <Text style={styles.inputLabel}>Provider / Company</Text>
      <TextInput style={styles.input} placeholder="Who provides this?" placeholderTextColor={COLORS.textMuted}
        value={form.provider} onChangeText={v => updateForm('provider', v)} />

      <Text style={styles.inputLabel}>URL</Text>
      <TextInput style={styles.input} placeholder="https://..." placeholderTextColor={COLORS.textMuted}
        value={form.url} onChangeText={v => updateForm('url', v)} keyboardType="url" />

      <Text style={styles.inputLabel}>Price Range</Text>
      <TextInput style={styles.input} placeholder="e.g. ₹5,000 - ₹10,000" placeholderTextColor={COLORS.textMuted}
        value={form.price_range} onChangeText={v => updateForm('price_range', v)} />

      <Text style={styles.inputLabel}>Tags (comma separated)</Text>
      <TextInput style={styles.input} placeholder="health, fitness, Chennai" placeholderTextColor={COLORS.textMuted}
        value={form.tags} onChangeText={v => updateForm('tags', v)} />
    </>
  );

  const renderStep2 = () => (
    <>
      <Text style={styles.stepTitle}>Categorize</Text>
      <Text style={styles.inputLabel}>Life Area *</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12, maxHeight: 44 }}>
        {lifeAreas.map((la: any) => (
          <TouchableOpacity key={la.id}
            style={[styles.chip, form.life_area_id === la.id && { backgroundColor: la.color + '30', borderColor: la.color }]}
            onPress={() => updateForm('life_area_id', la.id)}>
            <Ionicons name={la.icon as any} size={14} color={form.life_area_id === la.id ? la.color : COLORS.textMuted} />
            <Text style={[styles.chipText, form.life_area_id === la.id && { color: la.color }]} numberOfLines={1}>
              {la.name.length > 18 ? la.name.substring(0, 18) + '...' : la.name}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {subAreas.length > 0 && (
        <>
          <Text style={styles.inputLabel}>Sub-Area</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12, maxHeight: 44 }}>
            {subAreas.map((sa: any) => (
              <TouchableOpacity key={sa.id}
                style={[styles.chip, form.sub_area_id === sa.id && styles.chipActive]}
                onPress={() => updateForm('sub_area_id', sa.id)}>
                <Text style={[styles.chipText, form.sub_area_id === sa.id && styles.chipTextActive]}>{sa.name}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </>
      )}

      <Text style={styles.inputLabel}>Visibility</Text>
      {VISIBILITY.map(v => (
        <TouchableOpacity key={v.id}
          style={[styles.visOption, form.visibility === v.id && styles.visOptionActive]}
          onPress={() => updateForm('visibility', v.id)}>
          <Ionicons name={v.icon as any} size={18} color={form.visibility === v.id ? COLORS.primary : COLORS.textMuted} />
          <Text style={[styles.visText, form.visibility === v.id && { color: COLORS.primary }]}>{v.label}</Text>
        </TouchableOpacity>
      ))}

      <Text style={styles.inputLabel}>City</Text>
      <TextInput style={styles.input} placeholder="Chennai" placeholderTextColor={COLORS.textMuted}
        value={form.city} onChangeText={v => updateForm('city', v)} />
    </>
  );

  const renderStep3 = () => (
    <>
      <Text style={styles.stepTitle}>Type-Specific Details</Text>
      {(TYPE_FIELDS[form.type] || []).map(field => (
        <View key={field}>
          <Text style={styles.inputLabel}>{field.replace(/_/g, ' ')}</Text>
          <TextInput style={styles.input} placeholder={`Enter ${field.replace(/_/g, ' ')}`}
            placeholderTextColor={COLORS.textMuted}
            value={typeSpecific[field] || ''}
            onChangeText={v => setTypeSpecific(prev => ({ ...prev, [field]: v }))} />
        </View>
      ))}

      <Text style={[styles.stepTitle, { marginTop: 16 }]}>Quantitative Factors</Text>
      <Text style={styles.stepSubtitle}>Measurable data points (price, rating, capacity, etc.)</Text>
      {quantFactors.map((f, i) => (
        <View style={styles.factorRow} key={i}>
          <TextInput style={[styles.input, { flex: 2, marginBottom: 0 }]} placeholder="Factor name"
            placeholderTextColor={COLORS.textMuted} value={f.factor_name}
            onChangeText={v => updateQuantFactor(i, 'factor_name', v)} />
          <TextInput style={[styles.input, { flex: 1, marginBottom: 0 }]} placeholder="Value"
            placeholderTextColor={COLORS.textMuted} value={f.value}
            onChangeText={v => updateQuantFactor(i, 'value', v)} />
          <TextInput style={[styles.input, { flex: 1, marginBottom: 0 }]} placeholder="Unit"
            placeholderTextColor={COLORS.textMuted} value={f.unit}
            onChangeText={v => updateQuantFactor(i, 'unit', v)} />
          <TouchableOpacity onPress={() => removeQuantFactor(i)} style={styles.removeBtn}>
            <Ionicons name="close-circle" size={20} color={COLORS.danger} />
          </TouchableOpacity>
        </View>
      ))}
      <TouchableOpacity style={styles.addFactorBtn} onPress={addQuantFactor}>
        <Ionicons name="add-circle" size={18} color={COLORS.primary} />
        <Text style={styles.addFactorText}>Add Factor</Text>
      </TouchableOpacity>
    </>
  );

  const steps = [renderStep0, renderStep1, renderStep2, renderStep3];
  const stepTitles = ['Type', 'Details', 'Category', 'Factors'];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => step > 0 ? setStep(step - 1) : router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Add Solution</Text>
          <Text style={styles.stepIndicator}>{step + 1}/{steps.length}</Text>
        </View>

        {/* Progress */}
        <View style={styles.progressRow}>
          {stepTitles.map((t, i) => (
            <View key={i} style={[styles.progressDot, i <= step && styles.progressDotActive]}>
              <Text style={[styles.progressText, i <= step && { color: COLORS.primary }]}>{t}</Text>
            </View>
          ))}
        </View>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 100 }}>
          {steps[step]()}
        </ScrollView>

        {/* Bottom Buttons */}
        <View style={styles.bottomBar}>
          {step < steps.length - 1 ? (
            <TouchableOpacity style={styles.nextBtn} onPress={() => setStep(step + 1)}>
              <Text style={styles.nextBtnText}>Next</Text>
              <Ionicons name="arrow-forward" size={18} color={COLORS.text} />
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={[styles.nextBtn, { backgroundColor: COLORS.accent }, submitting && { opacity: 0.6 }]}
              onPress={submit} disabled={submitting}
            >
              {submitting ? <ActivityIndicator color="#FFF" /> :
                <>
                  <Ionicons name="checkmark" size={18} color={COLORS.text} />
                  <Text style={styles.nextBtnText}>Add to Store</Text>
                </>
              }
            </TouchableOpacity>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { padding: 8, marginRight: 8 },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: COLORS.text },
  stepIndicator: { fontSize: 14, color: COLORS.textMuted },
  progressRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 8 },
  progressDot: { flex: 1, paddingVertical: 6, alignItems: 'center', borderBottomWidth: 2, borderColor: COLORS.border },
  progressDotActive: { borderColor: COLORS.primary },
  progressText: { fontSize: 11, color: COLORS.textMuted, fontWeight: '500' },
  stepTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text, marginBottom: 12 },
  stepSubtitle: { fontSize: 13, color: COLORS.textMuted, marginBottom: 12, marginTop: -8 },
  typeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  typeCard: { width: '47%', backgroundColor: COLORS.surface, borderRadius: 16, padding: 20, alignItems: 'center', gap: 8, borderWidth: 1.5, borderColor: COLORS.border },
  typeLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textMuted },
  inputLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 6, marginTop: 4 },
  input: { backgroundColor: COLORS.surface, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12, color: COLORS.text, fontSize: 14, borderWidth: 1, borderColor: COLORS.border, marginBottom: 10 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 16, borderWidth: 1, borderColor: COLORS.border, marginRight: 8, backgroundColor: COLORS.surface },
  chipActive: { backgroundColor: COLORS.primary + '30', borderColor: COLORS.primary },
  chipText: { fontSize: 12, color: COLORS.textMuted },
  chipTextActive: { color: COLORS.primary },
  visOption: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.surface, borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  visOptionActive: { borderColor: COLORS.primary, backgroundColor: COLORS.primary + '10' },
  visText: { fontSize: 14, color: COLORS.textMuted },
  factorRow: { flexDirection: 'row', gap: 6, alignItems: 'center', marginBottom: 8 },
  removeBtn: { padding: 4 },
  addFactorBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 10 },
  addFactorText: { fontSize: 14, color: COLORS.primary, fontWeight: '500' },
  bottomBar: { paddingHorizontal: 16, paddingVertical: 12, borderTopWidth: 1, borderTopColor: COLORS.border },
  nextBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 14 },
  nextBtnText: { fontSize: 16, fontWeight: '700', color: COLORS.text },
});
