import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const LIFE_AREAS = [
  { id: 'career', name: 'Career', icon: 'briefcase' },
  { id: 'finance', name: 'Finance', icon: 'cash' },
  { id: 'relationships', name: 'Relationships', icon: 'heart' },
  { id: 'holistic_health', name: 'Holistic Health', icon: 'fitness' },
  { id: 'assets', name: 'Assets', icon: 'home' },
  { id: 'knowledge_skills', name: 'Knowledge & Skills', icon: 'school' },
  { id: 'social_image', name: 'Social Image', icon: 'people' },
  { id: 'social_contributions', name: 'Social Contributions', icon: 'globe' },
  { id: 'hobbies_entertainment', name: 'Hobbies & Entertainment', icon: 'game-controller' },
  { id: 'spirituality_religion', name: 'Spirituality', icon: 'leaf' },
];

const MATRIX_FIELDS = [
  { key: 'summary', label: 'Summary', icon: 'document-text' },
  { key: 'knowledge_skills', label: 'Knowledge & Skills', icon: 'school' },
  { key: 'capacity', label: 'Capacity (Physical, Mental, Emotional & Energy)', icon: 'fitness' },
  { key: 'time', label: 'Time', icon: 'time' },
  { key: 'people', label: 'People', icon: 'people' },
  { key: 'finance', label: 'Finance', icon: 'cash' },
  { key: 'infrastructure', label: 'Infrastructure', icon: 'construct' },
];

const SOLUTION_CATEGORIES = [
  { key: 'completely_solvable', label: 'Completely Solvable', color: '#10B981' },
  { key: 'partially_solvable', label: 'Partially Solvable', color: '#F59E0B' },
  { key: 'not_solvable', label: 'Not Solvable', color: '#EF4444' },
  { key: 'patience_period', label: 'Patience Period', color: '#6366F1' },
  { key: 'accept_let_go', label: 'Accept & Let Go', color: '#8B5CF6' },
  { key: 'surrender_trust', label: 'Surrender & Trust the Process', color: '#06B6D4' },
  { key: 'surrender_ignore', label: 'Surrender & Ignore', color: '#64748B' },
  { key: 'surrender_involve', label: 'Surrender & Involve (Choiceless Awareness)', color: '#EC4899' },
];

const SOLUTION_SOURCES = [
  { key: 'from_self', label: 'Solution from Self', icon: 'person' },
  { key: 'from_wellwisher', label: 'Solution from Well-wisher', icon: 'heart' },
  { key: 'from_experienced', label: 'Solution from Experienced', icon: 'school' },
  { key: 'from_expert', label: 'Solution from On-Demand Expert', icon: 'star' },
  { key: 'from_coach', label: 'Solution from Regular Coach', icon: 'fitness' },
];

interface MatrixLayer {
  summary: string;
  knowledge_skills: string;
  capacity: string;
  time: string;
  people: string;
  finance: string;
  infrastructure: string;
}

const emptyMatrix = (): MatrixLayer => ({
  summary: '', knowledge_skills: '', capacity: '',
  time: '', people: '', finance: '', infrastructure: '',
});

interface ActionItem {
  who: string;
  what: string;
  by_when: string;
  status: string;
}

export default function SolutionMatrixScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const editId = params.id as string | undefined;

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  // Form state
  const [areaOfLife, setAreaOfLife] = useState('');
  const [smartGoal, setSmartGoal] = useState('');
  const [milestones, setMilestones] = useState([{ description: '', timeline: '' }]);
  const [q1AllConcerns, setQ1AllConcerns] = useState('');
  const [q2PriorityConcerns, setQ2PriorityConcerns] = useState('');
  // Simpler Solutions (3.1.1)
  const [simplerSolutions, setSimplerSolutions] = useState('');
  const [simplerCapabilities, setSimplerCapabilities] = useState('');
  const [simplerResources, setSimplerResources] = useState('');
  const [simplerHelpAspect, setSimplerHelpAspect] = useState('');
  const [simplerHelpLevel, setSimplerHelpLevel] = useState('');
  const [simplerHelpFrom, setSimplerHelpFrom] = useState('');
  // Matrix layers (3.1.2)
  const [matrixSelf, setMatrixSelf] = useState<MatrixLayer>(emptyMatrix());
  const [matrixMicro, setMatrixMicro] = useState<MatrixLayer>(emptyMatrix());
  const [matrixMacro, setMatrixMacro] = useState<MatrixLayer>(emptyMatrix());
  // Solution Category (3.2)
  const [solutionCategory, setSolutionCategory] = useState<Record<string, boolean>>(
    Object.fromEntries(SOLUTION_CATEGORIES.map(c => [c.key, false]))
  );
  // Solution Sources (3.3)
  const [solutionSources, setSolutionSources] = useState<Record<string, string>>(
    Object.fromEntries(SOLUTION_SOURCES.map(s => [s.key, '']))
  );
  // Risk (Q4)
  const [q4NegConsequences, setQ4NegConsequences] = useState('');
  const [q4Mitigation, setQ4Mitigation] = useState('');
  const [q4Contingency, setQ4Contingency] = useState('');
  // Action Plan (Q5)
  const [actionItems, setActionItems] = useState<ActionItem[]>([{ who: '', what: '', by_when: '', status: 'pending' }]);

  const steps = [
    { title: 'Life Area & Goal', icon: 'flag' },
    { title: 'Concerns', icon: 'alert-circle' },
    { title: 'Simpler Solutions', icon: 'bulb' },
    { title: 'Solution Matrix', icon: 'grid' },
    { title: 'Categories & Sources', icon: 'layers' },
    { title: 'Risk Management', icon: 'shield-checkmark' },
    { title: 'Action Plan', icon: 'rocket' },
  ];

  useEffect(() => {
    if (editId) loadEntry();
  }, [editId]);

  const loadEntry = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/solution-matrices/${editId}`);
      const d = res.data;
      setAreaOfLife(d.area_of_life || '');
      setSmartGoal(d.smart_goal || '');
      setMilestones(d.milestones?.length ? d.milestones : [{ description: '', timeline: '' }]);
      setQ1AllConcerns(d.q1_all_concerns || '');
      setQ2PriorityConcerns(d.q2_priority_concerns || '');
      setSimplerSolutions(d.simpler_solutions || '');
      setSimplerCapabilities(d.simpler_capabilities || '');
      setSimplerResources(d.simpler_resources || '');
      setSimplerHelpAspect(d.simpler_help_aspect || '');
      setSimplerHelpLevel(d.simpler_help_level || '');
      setSimplerHelpFrom(d.simpler_help_from || '');
      setMatrixSelf({ ...emptyMatrix(), ...d.matrix_self });
      setMatrixMicro({ ...emptyMatrix(), ...d.matrix_micro });
      setMatrixMacro({ ...emptyMatrix(), ...d.matrix_macro });
      if (d.solution_category) setSolutionCategory(prev => ({ ...prev, ...d.solution_category }));
      if (d.solution_sources) setSolutionSources(prev => ({ ...prev, ...d.solution_sources }));
      setQ4NegConsequences(d.q4_negative_consequences || '');
      setQ4Mitigation(d.q4_mitigation_plans || '');
      setQ4Contingency(d.q4_contingency_plans || '');
      setActionItems(d.action_items?.length ? d.action_items : [{ who: '', what: '', by_when: '', status: 'pending' }]);
    } catch (e) {
      Alert.alert('Error', 'Failed to load entry');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!areaOfLife || !smartGoal.trim()) {
      Alert.alert('Required', 'Please select area and enter SMART goal');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        area_of_life: areaOfLife,
        smart_goal: smartGoal,
        milestones: milestones.filter(m => m.description.trim()),
        q1_all_concerns: q1AllConcerns,
        q2_priority_concerns: q2PriorityConcerns,
        simpler_solutions: simplerSolutions,
        simpler_capabilities: simplerCapabilities,
        simpler_resources: simplerResources,
        simpler_help_aspect: simplerHelpAspect,
        simpler_help_level: simplerHelpLevel,
        simpler_help_from: simplerHelpFrom,
        matrix_self: matrixSelf,
        matrix_micro: matrixMicro,
        matrix_macro: matrixMacro,
        solution_category: solutionCategory,
        solution_sources: solutionSources,
        q4_negative_consequences: q4NegConsequences,
        q4_mitigation_plans: q4Mitigation,
        q4_contingency_plans: q4Contingency,
        action_items: actionItems.filter(a => a.what.trim()),
        status: currentStep >= 6 ? 'completed' : 'in_progress',
      };

      if (editId) {
        await api.put(`/solution-matrices/${editId}`, payload);
      } else {
        await api.post('/solution-matrices', payload);
      }
      Alert.alert('Saved', 'Solution Matrix saved successfully!', [
        { text: 'OK', onPress: () => router.back() }
      ]);
    } catch (e) {
      Alert.alert('Error', 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const updateMatrixField = (layer: 'self' | 'micro' | 'macro', field: string, value: string) => {
    if (layer === 'self') setMatrixSelf(prev => ({ ...prev, [field]: value }));
    else if (layer === 'micro') setMatrixMicro(prev => ({ ...prev, [field]: value }));
    else setMatrixMacro(prev => ({ ...prev, [field]: value }));
  };

  const getMatrixLayer = (layer: 'self' | 'micro' | 'macro') => {
    if (layer === 'self') return matrixSelf;
    if (layer === 'micro') return matrixMicro;
    return matrixMacro;
  };

  const addMilestone = () => setMilestones([...milestones, { description: '', timeline: '' }]);
  const removeMilestone = (i: number) => {
    if (milestones.length > 1) setMilestones(milestones.filter((_, idx) => idx !== i));
  };
  const updateMilestone = (i: number, field: string, val: string) => {
    const u = [...milestones];
    u[i] = { ...u[i], [field]: val };
    setMilestones(u);
  };

  const addActionItem = () => setActionItems([...actionItems, { who: '', what: '', by_when: '', status: 'pending' }]);
  const removeActionItem = (i: number) => {
    if (actionItems.length > 1) setActionItems(actionItems.filter((_, idx) => idx !== i));
  };
  const updateActionItem = (i: number, field: keyof ActionItem, val: string) => {
    const u = [...actionItems];
    u[i] = { ...u[i], [field]: val };
    setActionItems(u);
  };

  const [activeMatrixTab, setActiveMatrixTab] = useState<'self' | 'micro' | 'macro'>('self');

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  const renderMatrixSection = () => {
    const layer = getMatrixLayer(activeMatrixTab);
    const layerLabels = { self: 'SELF', micro: 'MICRO', macro: 'MACRO' };
    const layerColors = { self: '#10B981', micro: '#6366F1', macro: '#F59E0B' };

    return (
      <View>
        <Text style={styles.sectionHeader}>Solution Matrix (Extended Solutions)</Text>

        {/* Tab selector */}
        <View style={styles.matrixTabs}>
          {(['self', 'micro', 'macro'] as const).map(tab => (
            <TouchableOpacity
              key={tab}
              style={[
                styles.matrixTab,
                activeMatrixTab === tab && { backgroundColor: layerColors[tab] }
              ]}
              onPress={() => setActiveMatrixTab(tab)}
            >
              <Text style={[
                styles.matrixTabText,
                activeMatrixTab === tab && { color: '#FFF' }
              ]}>{layerLabels[tab]}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={[styles.matrixCard, { borderLeftColor: layerColors[activeMatrixTab] }]}>
          {MATRIX_FIELDS.map(f => (
            <View key={f.key}>
              <View style={styles.matrixFieldLabel}>
                <Ionicons name={f.icon as any} size={14} color={layerColors[activeMatrixTab]} />
                <Text style={styles.matrixFieldText}>{f.label}</Text>
              </View>
              <TextInput
                style={styles.matrixInput}
                placeholder={`${layerLabels[activeMatrixTab]} - ${f.label}`}
                placeholderTextColor={COLORS.textMuted}
                value={layer[f.key as keyof MatrixLayer]}
                onChangeText={v => updateMatrixField(activeMatrixTab, f.key, v)}
                multiline
                numberOfLines={2}
              />
            </View>
          ))}
        </View>
      </View>
    );
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0: // Life Area & Goal
        return (
          <View>
            <Text style={styles.stepLabel}>Select Area of Life</Text>
            <View style={styles.areaGrid}>
              {LIFE_AREAS.map(area => (
                <TouchableOpacity
                  key={area.id}
                  style={[styles.areaChip, areaOfLife === area.id && styles.areaChipActive]}
                  onPress={() => setAreaOfLife(area.id)}
                >
                  <Ionicons name={area.icon as any} size={16} color={areaOfLife === area.id ? '#FFF' : COLORS.primary} />
                  <Text style={[styles.areaChipText, areaOfLife === area.id && styles.areaChipTextActive]}>{area.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={styles.stepLabel}>SMART Goal</Text>
            <TextInput
              style={styles.textArea}
              placeholder="Define your Specific, Measurable, Achievable, Relevant, Time-bound goal"
              placeholderTextColor={COLORS.textMuted}
              value={smartGoal}
              onChangeText={setSmartGoal}
              multiline numberOfLines={3}
            />
            <View style={styles.labelRow}>
              <Text style={styles.stepLabel}>Milestones</Text>
              <TouchableOpacity onPress={addMilestone}>
                <Ionicons name="add-circle" size={22} color={COLORS.primary} />
              </TouchableOpacity>
            </View>
            {milestones.map((m, i) => (
              <View key={i} style={styles.milestoneCard}>
                <View style={styles.milestoneHeader}>
                  <Text style={styles.milestoneNum}>#{i + 1}</Text>
                  {milestones.length > 1 && (
                    <TouchableOpacity onPress={() => removeMilestone(i)}>
                      <Ionicons name="close-circle" size={20} color={COLORS.error} />
                    </TouchableOpacity>
                  )}
                </View>
                <TextInput style={styles.input} placeholder="Milestone description" placeholderTextColor={COLORS.textMuted}
                  value={m.description} onChangeText={v => updateMilestone(i, 'description', v)} />
                <TextInput style={styles.input} placeholder="Timeline" placeholderTextColor={COLORS.textMuted}
                  value={m.timeline} onChangeText={v => updateMilestone(i, 'timeline', v)} />
              </View>
            ))}
          </View>
        );

      case 1: // Concerns
        return (
          <View>
            <Text style={styles.stepLabel}>Q1. What are ALL your concerns?</Text>
            <TextInput style={styles.textArea} placeholder="List all concerns..." placeholderTextColor={COLORS.textMuted}
              value={q1AllConcerns} onChangeText={setQ1AllConcerns} multiline numberOfLines={5} />
            <Text style={styles.stepLabel}>Q2. What are your PRIORITY concerns?</Text>
            <TextInput style={styles.textArea} placeholder="Top priorities..." placeholderTextColor={COLORS.textMuted}
              value={q2PriorityConcerns} onChangeText={setQ2PriorityConcerns} multiline numberOfLines={4} />
          </View>
        );

      case 2: // Simpler Solutions (3.1.1)
        return (
          <View>
            <Text style={styles.sectionHeader}>(3.1.1) Simpler Solutions</Text>
            <Text style={styles.stepLabel}>Solutions within Current Influence Level</Text>
            <TextInput style={styles.textArea} placeholder="What can you do now?" placeholderTextColor={COLORS.textMuted}
              value={simplerSolutions} onChangeText={setSimplerSolutions} multiline numberOfLines={4} />
            <Text style={styles.stepLabel}>Current Capabilities</Text>
            <TextInput style={styles.textArea} placeholder="Knowledge, Skills..." placeholderTextColor={COLORS.textMuted}
              value={simplerCapabilities} onChangeText={setSimplerCapabilities} multiline numberOfLines={3} />
            <Text style={styles.stepLabel}>Resources at Present</Text>
            <TextInput style={styles.textArea} placeholder="Contacts, Time, Money, Assets..." placeholderTextColor={COLORS.textMuted}
              value={simplerResources} onChangeText={setSimplerResources} multiline numberOfLines={3} />
            <Text style={styles.sectionHeader}>External Help</Text>
            <TextInput style={styles.input} placeholder="What aspect needs help?" placeholderTextColor={COLORS.textMuted}
              value={simplerHelpAspect} onChangeText={setSimplerHelpAspect} />
            <TextInput style={styles.input} placeholder="Level of help (Consulting/Problem Solving/Coaching)" placeholderTextColor={COLORS.textMuted}
              value={simplerHelpLevel} onChangeText={setSimplerHelpLevel} />
            <TextInput style={styles.input} placeholder="Help from whom?" placeholderTextColor={COLORS.textMuted}
              value={simplerHelpFrom} onChangeText={setSimplerHelpFrom} />
          </View>
        );

      case 3: // Solution Matrix (3.1.2)
        return renderMatrixSection();

      case 4: // Categories & Sources
        return (
          <View>
            <Text style={styles.sectionHeader}>(3.2) Solution Category</Text>
            <Text style={styles.hint}>Select all that apply to your situation</Text>
            {SOLUTION_CATEGORIES.map(cat => (
              <TouchableOpacity
                key={cat.key}
                style={[styles.categoryRow, solutionCategory[cat.key] && { backgroundColor: cat.color + '15', borderColor: cat.color }]}
                onPress={() => setSolutionCategory(prev => ({ ...prev, [cat.key]: !prev[cat.key] }))}
              >
                <Ionicons
                  name={solutionCategory[cat.key] ? 'checkbox' : 'square-outline'}
                  size={22}
                  color={solutionCategory[cat.key] ? cat.color : COLORS.textMuted}
                />
                <Text style={[styles.categoryText, solutionCategory[cat.key] && { color: cat.color, fontWeight: '600' }]}>
                  {cat.label}
                </Text>
              </TouchableOpacity>
            ))}

            <Text style={[styles.sectionHeader, { marginTop: 24 }]}>(3.3) Solution Sources</Text>
            {SOLUTION_SOURCES.map(src => (
              <View key={src.key}>
                <View style={styles.sourceLabel}>
                  <Ionicons name={src.icon as any} size={16} color={COLORS.primary} />
                  <Text style={styles.sourceLabelText}>{src.label}</Text>
                </View>
                <TextInput
                  style={styles.textArea}
                  placeholder={`Describe solution from ${src.label.replace('Solution from ', '')}...`}
                  placeholderTextColor={COLORS.textMuted}
                  value={solutionSources[src.key]}
                  onChangeText={v => setSolutionSources(prev => ({ ...prev, [src.key]: v }))}
                  multiline numberOfLines={2}
                />
              </View>
            ))}
          </View>
        );

      case 5: // Risk Management
        return (
          <View>
            <Text style={styles.sectionHeader}>Q4. Risk Management</Text>
            <Text style={styles.stepLabel}>Possible Negative Consequences</Text>
            <TextInput style={styles.textArea} placeholder="What could go wrong?" placeholderTextColor={COLORS.textMuted}
              value={q4NegConsequences} onChangeText={setQ4NegConsequences} multiline numberOfLines={4} />
            <Text style={styles.stepLabel}>Mitigation Plans</Text>
            <TextInput style={styles.textArea} placeholder="How to prevent?" placeholderTextColor={COLORS.textMuted}
              value={q4Mitigation} onChangeText={setQ4Mitigation} multiline numberOfLines={4} />
            <Text style={styles.stepLabel}>Contingency Plans</Text>
            <TextInput style={styles.textArea} placeholder="Backup plans..." placeholderTextColor={COLORS.textMuted}
              value={q4Contingency} onChangeText={setQ4Contingency} multiline numberOfLines={4} />
          </View>
        );

      case 6: // Action Plan
        return (
          <View>
            <Text style={styles.sectionHeader}>Q5. Action Plan</Text>
            <View style={styles.labelRow}>
              <Text style={styles.stepLabel}>Action Items</Text>
              <TouchableOpacity onPress={addActionItem}>
                <Ionicons name="add-circle" size={22} color={COLORS.primary} />
              </TouchableOpacity>
            </View>
            {actionItems.map((item, i) => (
              <View key={i} style={styles.actionCard}>
                <View style={styles.milestoneHeader}>
                  <Text style={styles.milestoneNum}>Action #{i + 1}</Text>
                  {actionItems.length > 1 && (
                    <TouchableOpacity onPress={() => removeActionItem(i)}>
                      <Ionicons name="close-circle" size={20} color={COLORS.error} />
                    </TouchableOpacity>
                  )}
                </View>
                <TextInput style={styles.input} placeholder="WHAT action?" placeholderTextColor={COLORS.textMuted}
                  value={item.what} onChangeText={v => updateActionItem(i, 'what', v)} />
                <View style={styles.twoCol}>
                  <TextInput style={[styles.input, { flex: 1 }]} placeholder="WHO does?" placeholderTextColor={COLORS.textMuted}
                    value={item.who} onChangeText={v => updateActionItem(i, 'who', v)} />
                  <TextInput style={[styles.input, { flex: 1 }]} placeholder="By WHEN?" placeholderTextColor={COLORS.textMuted}
                    value={item.by_when} onChangeText={v => updateActionItem(i, 'by_when', v)} />
                </View>
                <View style={styles.statusRow}>
                  {['pending', 'in_progress', 'completed'].map(s => (
                    <TouchableOpacity key={s}
                      style={[styles.statusChip, item.status === s && styles.statusChipActive]}
                      onPress={() => updateActionItem(i, 'status', s)}>
                      <Text style={[styles.statusChipText, item.status === s && styles.statusChipTextActive]}>
                        {s.replace('_', ' ').toUpperCase()}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            ))}
          </View>
        );

      default:
        return null;
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <LinearGradient colors={['#E91E63', '#8E24AA']} style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerTitle}>Advanced Solution Matrix</Text>
            <Text style={styles.headerSub}>Step {currentStep + 1} of {steps.length}</Text>
          </View>
        </LinearGradient>

        {/* Step Indicators */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.stepScroll}>
          <View style={styles.stepIndicator}>
            {steps.map((step, i) => (
              <TouchableOpacity
                key={i}
                style={[
                  styles.stepPill,
                  currentStep === i && styles.stepPillActive,
                  currentStep > i && styles.stepPillDone
                ]}
                onPress={() => setCurrentStep(i)}
              >
                <Ionicons name={step.icon as any} size={14}
                  color={currentStep >= i ? '#FFF' : COLORS.textMuted} />
                <Text style={[
                  styles.stepPillText,
                  currentStep >= i && { color: '#FFF' }
                ]} numberOfLines={1}>{step.title}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>

        <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          <Text style={styles.currentStepTitle}>{steps[currentStep].title}</Text>
          {renderStepContent()}
        </ScrollView>

        <View style={styles.bottomNav}>
          {currentStep > 0 && (
            <TouchableOpacity style={styles.navBtnSecondary} onPress={() => setCurrentStep(currentStep - 1)}>
              <Ionicons name="arrow-back" size={18} color={COLORS.accent} />
              <Text style={[styles.navBtnSecondaryText, { color: COLORS.accent }]}>Back</Text>
            </TouchableOpacity>
          )}
          <View style={{ flex: 1 }} />
          {currentStep < steps.length - 1 ? (
            <TouchableOpacity style={[styles.navBtnPrimary, { backgroundColor: COLORS.accent }]}
              onPress={() => setCurrentStep(currentStep + 1)}>
              <Text style={styles.navBtnPrimaryText}>Next</Text>
              <Ionicons name="arrow-forward" size={18} color="#FFF" />
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={[styles.navBtnPrimary, { backgroundColor: COLORS.accent }, saving && { opacity: 0.7 }]}
              onPress={handleSave} disabled={saving}>
              {saving ? <ActivityIndicator size="small" color="#FFF" /> : (
                <><Ionicons name="checkmark-circle" size={18} color="#FFF" />
                <Text style={styles.navBtnPrimaryText}>Save</Text></>
              )}
            </TouchableOpacity>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingBottom: 20 },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center', marginRight: 12,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  stepScroll: {
    backgroundColor: COLORS.white,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  stepIndicator: {
    flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 10, gap: 8,
  },
  stepPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 20, backgroundColor: COLORS.divider,
  },
  stepPillActive: { backgroundColor: COLORS.accent },
  stepPillDone: { backgroundColor: COLORS.success },
  stepPillText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },
  scrollView: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 32 },
  currentStepTitle: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 16 },
  stepLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginTop: 16, marginBottom: 6 },
  hint: { fontSize: 12, color: COLORS.textMuted, marginBottom: 8 },
  sectionHeader: {
    fontSize: 16, fontWeight: '700', color: COLORS.accent,
    marginTop: 20, marginBottom: 4,
    borderBottomWidth: 1, borderBottomColor: COLORS.border, paddingBottom: 6,
  },
  areaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  areaChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 20, borderWidth: 1, borderColor: COLORS.primary,
    backgroundColor: 'rgba(142,36,170,0.05)',
  },
  areaChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  areaChipText: { fontSize: 12, fontWeight: '500', color: COLORS.primary },
  areaChipTextActive: { color: '#FFF' },
  input: {
    backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, marginBottom: 8,
  },
  textArea: {
    backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary,
    minHeight: 80, textAlignVertical: 'top', marginBottom: 8,
  },
  labelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  milestoneCard: {
    backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 10,
    borderWidth: 1, borderColor: COLORS.border,
  },
  milestoneHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  milestoneNum: { fontSize: 13, fontWeight: '600', color: COLORS.primary },
  actionCard: {
    backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 12,
    borderWidth: 1, borderColor: COLORS.border,
  },
  twoCol: { flexDirection: 'row', gap: 8 },
  statusRow: { flexDirection: 'row', gap: 6, marginTop: 4 },
  statusChip: {
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12,
    borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.divider,
  },
  statusChipActive: { backgroundColor: COLORS.success, borderColor: COLORS.success },
  statusChipText: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted },
  statusChipTextActive: { color: '#FFF' },
  // Matrix specific
  matrixTabs: {
    flexDirection: 'row', gap: 8, marginVertical: 12,
  },
  matrixTab: {
    flex: 1, paddingVertical: 10, borderRadius: 12,
    backgroundColor: COLORS.divider, alignItems: 'center',
  },
  matrixTabText: { fontSize: 13, fontWeight: '700', color: COLORS.textMuted },
  matrixCard: {
    backgroundColor: COLORS.white, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: COLORS.border,
    borderLeftWidth: 4,
  },
  matrixFieldLabel: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginTop: 10, marginBottom: 4,
  },
  matrixFieldText: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  matrixInput: {
    backgroundColor: COLORS.background, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 12, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary,
    minHeight: 50, textAlignVertical: 'top',
  },
  // Category
  categoryRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingHorizontal: 14, paddingVertical: 12,
    borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    backgroundColor: COLORS.white, marginBottom: 8,
  },
  categoryText: { fontSize: 14, color: COLORS.textPrimary, flex: 1 },
  // Source
  sourceLabel: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, marginBottom: 4,
  },
  sourceLabelText: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  // Bottom nav
  bottomNav: {
    flexDirection: 'row', alignItems: 'center', padding: 16,
    borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white,
  },
  navBtnSecondary: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: 10, borderWidth: 1, borderColor: COLORS.accent,
  },
  navBtnSecondaryText: { fontSize: 14, fontWeight: '600' },
  navBtnPrimary: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 20, paddingVertical: 12, borderRadius: 10,
  },
  navBtnPrimaryText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
});
