import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert, ActivityIndicator, Platform, KeyboardAvoidingView, Switch,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const LIFE_AREAS = [
  { id: 'career', name: 'Career', icon: 'briefcase' },
  { id: 'finance', name: 'Finance', icon: 'cash' },
  { id: 'relationships', name: 'Relationships', icon: 'heart' },
  { id: 'holistic_health', name: 'Health', icon: 'fitness' },
  { id: 'assets', name: 'Assets', icon: 'home' },
  { id: 'knowledge_skills', name: 'Knowledge', icon: 'school' },
  { id: 'social_image', name: 'Social Image', icon: 'people' },
  { id: 'social_contributions', name: 'Contributions', icon: 'hand-left' },
  { id: 'hobbies_entertainment', name: 'Hobbies', icon: 'game-controller' },
  { id: 'spirituality_religion', name: 'Spirituality', icon: 'leaf' },
];

const FREQUENCIES = [
  { id: 'hourly', label: 'Hourly', icon: 'time-outline', color: '#EF4444' },
  { id: 'daily', label: 'Daily', icon: 'today', color: '#3B82F6' },
  { id: 'weekly', label: 'Weekly', icon: 'calendar', color: '#10B981' },
  { id: 'fortnightly', label: 'Fortnightly', icon: 'calendar-outline', color: '#F59E0B' },
  { id: 'monthly', label: 'Monthly', icon: 'calendar-number', color: '#8B5CF6' },
];

const PRIORITIES = [
  { id: 'critical', label: 'Critical', color: '#EF4444' },
  { id: 'high', label: 'High', color: '#F59E0B' },
  { id: 'medium', label: 'Medium', color: '#3B82F6' },
  { id: 'low', label: 'Low', color: '#6B7280' },
];

const CATEGORIES = [
  { id: 'primary', label: 'Primary Factor', desc: 'Core routine critical to your lifestyle' },
  { id: 'secondary', label: 'Secondary Factor', desc: 'Supporting routine that enhances quality' },
];

export default function LifestyleRoutineScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams();
  const editId = id as string | undefined;
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [lifeArea, setLifeArea] = useState('');
  const [frequency, setFrequency] = useState('daily');
  const [timeSlot, setTimeSlot] = useState('');
  const [priority, setPriority] = useState('medium');
  const [category, setCategory] = useState('primary');
  const [expectedValue, setExpectedValue] = useState('');
  const [unit, setUnit] = useState('');
  const [isActive, setIsActive] = useState(true);

  useEffect(() => { if (editId) loadRoutine(); }, [editId]);

  const loadRoutine = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/lifestyle/routines/${editId}`);
      const d = res.data;
      setName(d.name || '');
      setDescription(d.description || '');
      setLifeArea(d.life_area || '');
      setFrequency(d.frequency || 'daily');
      setTimeSlot(d.time_slot || '');
      setPriority(d.priority || 'medium');
      setCategory(d.category || 'primary');
      setExpectedValue(d.expected_value || '');
      setUnit(d.unit || '');
      setIsActive(d.is_active !== false);
    } catch (e) {
      Alert.alert('Error', 'Failed to load routine');
      router.back();
    } finally { setLoading(false); }
  };

  const handleSave = async () => {
    if (!name.trim()) { Alert.alert('Required', 'Routine name is required'); return; }
    setSaving(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        life_area: lifeArea,
        frequency,
        time_slot: timeSlot.trim(),
        priority,
        category,
        expected_value: expectedValue.trim(),
        unit: unit.trim(),
        is_active: isActive,
      };
      if (editId) {
        await api.put(`/lifestyle/routines/${editId}`, payload);
      } else {
        await api.post('/lifestyle/routines', payload);
      }
      router.back();
    } catch (e) { Alert.alert('Error', 'Failed to save'); }
    finally { setSaving(false); }
  };

  if (loading) {
    return (
      <SafeAreaView style={st.container}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#059669" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <LinearGradient colors={['#065F46', '#059669']} style={st.header}>
          <TouchableOpacity onPress={() => router.back()} style={st.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <Text style={st.headerTitle}>{editId ? 'Edit Routine' : 'New Routine'}</Text>
          {editId && (
            <TouchableOpacity
              style={st.deleteBtn}
              onPress={() => Alert.alert('Delete', 'Delete this routine?', [
                { text: 'Cancel', style: 'cancel' },
                { text: 'Delete', style: 'destructive', onPress: async () => {
                  try { await api.delete(`/lifestyle/routines/${editId}`); router.back(); }
                  catch (e) { Alert.alert('Error', 'Failed to delete'); }
                }},
              ])}
            >
              <Ionicons name="trash-outline" size={18} color="#FF6B6B" />
            </TouchableOpacity>
          )}
        </LinearGradient>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 100 }} showsVerticalScrollIndicator={false}>
          <View style={st.section}>
            <Text style={st.label}>Routine Name *</Text>
            <TextInput style={st.input} value={name} onChangeText={setName} placeholder="e.g. Morning meditation" placeholderTextColor={COLORS.textMuted} />

            <Text style={st.label}>Description</Text>
            <TextInput style={[st.input, { minHeight: 60, textAlignVertical: 'top' }]} value={description} onChangeText={setDescription} placeholder="What does this routine involve?" placeholderTextColor={COLORS.textMuted} multiline />
          </View>

          {/* Frequency */}
          <View style={st.section}>
            <Text style={st.label}>Frequency</Text>
            <View style={st.chipRow}>
              {FREQUENCIES.map(f => (
                <TouchableOpacity
                  key={f.id}
                  style={[st.freqChip, frequency === f.id && { backgroundColor: f.color, borderColor: f.color }]}
                  onPress={() => setFrequency(f.id)}
                >
                  <Ionicons name={f.icon as any} size={14} color={frequency === f.id ? '#FFF' : f.color} />
                  <Text style={[st.chipText, frequency === f.id && { color: '#FFF' }]}>{f.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Life Area */}
          <View style={st.section}>
            <Text style={st.label}>Life Area</Text>
            <View style={st.areaGrid}>
              {LIFE_AREAS.map(a => (
                <TouchableOpacity
                  key={a.id}
                  style={[st.areaChip, lifeArea === a.id && st.areaActive]}
                  onPress={() => setLifeArea(lifeArea === a.id ? '' : a.id)}
                >
                  <Ionicons name={a.icon as any} size={14} color={lifeArea === a.id ? '#FFF' : COLORS.primary} />
                  <Text style={[st.areaText, lifeArea === a.id && { color: '#FFF' }]}>{a.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Priority */}
          <View style={st.section}>
            <Text style={st.label}>Priority</Text>
            <View style={st.chipRow}>
              {PRIORITIES.map(p => (
                <TouchableOpacity
                  key={p.id}
                  style={[st.freqChip, priority === p.id && { backgroundColor: p.color, borderColor: p.color }]}
                  onPress={() => setPriority(p.id)}
                >
                  <Text style={[st.chipText, priority === p.id && { color: '#FFF' }]}>{p.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Category (for PRR factor classification) */}
          <View style={st.section}>
            <Text style={st.label}>Factor Category (for Lifestyle Assessment)</Text>
            {CATEGORIES.map(c => (
              <TouchableOpacity
                key={c.id}
                style={[st.categoryCard, category === c.id && st.categoryActive]}
                onPress={() => setCategory(c.id)}
              >
                <Ionicons name={category === c.id ? 'radio-button-on' : 'radio-button-off'} size={18} color={category === c.id ? '#059669' : COLORS.textMuted} />
                <View style={{ flex: 1 }}>
                  <Text style={[st.categoryName, category === c.id && { color: '#059669' }]}>{c.label}</Text>
                  <Text style={st.categoryDesc}>{c.desc}</Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>

          {/* Scheduling */}
          <View style={st.section}>
            <Text style={st.label}>Time Slot</Text>
            <TextInput style={st.input} value={timeSlot} onChangeText={setTimeSlot} placeholder="e.g. 6:00 AM - 6:30 AM" placeholderTextColor={COLORS.textMuted} />

            <View style={{ flexDirection: 'row', gap: 10, marginTop: 8 }}>
              <View style={{ flex: 1 }}>
                <Text style={st.label}>Expected Value</Text>
                <TextInput style={st.input} value={expectedValue} onChangeText={setExpectedValue} placeholder="e.g. 30" placeholderTextColor={COLORS.textMuted} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={st.label}>Unit</Text>
                <TextInput style={st.input} value={unit} onChangeText={setUnit} placeholder="e.g. minutes, km" placeholderTextColor={COLORS.textMuted} />
              </View>
            </View>
          </View>

          {/* Active toggle */}
          <View style={[st.section, { flexDirection: 'row', alignItems: 'center' }]}>
            <View style={{ flex: 1 }}>
              <Text style={st.label}>Active</Text>
              <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Inactive routines won't appear in assessments</Text>
            </View>
            <Switch
              value={isActive}
              onValueChange={setIsActive}
              trackColor={{ false: '#D1D5DB', true: '#059669' + '80' }}
              thumbColor={isActive ? '#059669' : '#9CA3AF'}
            />
          </View>
        </ScrollView>

        <View style={st.bottom}>
          <TouchableOpacity style={[st.saveBtn, saving && { opacity: 0.7 }]} onPress={handleSave} disabled={saving}>
            {saving ? <ActivityIndicator size="small" color="#FFF" /> : (
              <><Ionicons name="checkmark-circle" size={20} color="#FFF" /><Text style={st.saveBtnText}>{editId ? 'Update Routine' : 'Create Routine'}</Text></>
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
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF', flex: 1 },
  deleteBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center' },

  section: { paddingHorizontal: 16, paddingVertical: 8 },
  label: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginTop: 8, marginBottom: 6 },
  input: { backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 14, paddingVertical: 12, fontSize: 14, color: COLORS.textPrimary },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chipText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },
  freqChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: COLORS.white },

  areaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  areaChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 12, borderWidth: 1.5, borderColor: COLORS.primary + '30', backgroundColor: COLORS.primary + '08', minWidth: '45%' },
  areaActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  areaText: { fontSize: 12, fontWeight: '600', color: COLORS.primary },

  categoryCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1.5, borderColor: COLORS.border },
  categoryActive: { borderColor: '#059669', backgroundColor: '#05966908' },
  categoryName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  categoryDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },

  bottom: { padding: 16, paddingBottom: Platform.OS === 'ios' ? 20 : 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#065F46', borderRadius: 14, paddingVertical: 16 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
