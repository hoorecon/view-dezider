import React, { useState, useEffect, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
  RefreshControl,
  Platform,
  KeyboardAvoidingView,
  Modal,
} from 'react-native';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
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

const HELP_LEVELS = [
  'One-time Consulting',
  'Problem Solving',
  'Regular Coaching',
];

interface ActionItem {
  action: string;
  who: string;
  by_when: string;
  status: string;
}

interface Milestone {
  description: string;
  timeline: string;
}

export default function SolutionFinderScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const editId = params.id as string | undefined;

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [savedId, setSavedId] = useState<string | null>(editId || null);

  // Collaboration
  const [showCollabModal, setShowCollabModal] = useState(false);
  const [collabModes, setCollabModes] = useState<any[]>([]);
  const [collabContacts, setCollabContacts] = useState<any[]>([]);
  const [collabSelectedMode, setCollabSelectedMode] = useState('equal');
  const [collabSelectedContacts, setCollabSelectedContacts] = useState<Set<string>>(new Set());
  const [collabSessionMode, setCollabSessionMode] = useState('async');
  const [collabCreating, setCollabCreating] = useState(false);
  const [existingCollabs, setExistingCollabs] = useState<any[]>([]);

  // Form state
  const [areaOfLife, setAreaOfLife] = useState('');
  const [smartGoal, setSmartGoal] = useState('');
  const [milestones, setMilestones] = useState<Milestone[]>([{ description: '', timeline: '' }]);
  const [q1AllConcerns, setQ1AllConcerns] = useState('');
  const [q2PrimaryConcerns, setQ2PrimaryConcerns] = useState('');
  const [q3Capabilities, setQ3Capabilities] = useState('');
  const [q3Resources, setQ3Resources] = useState('');
  const [q3Solutions, setQ3Solutions] = useState('');
  const [externalHelpAspect, setExternalHelpAspect] = useState('');
  const [externalHelpLevel, setExternalHelpLevel] = useState('');
  const [externalHelpFrom, setExternalHelpFrom] = useState('');
  const [q4NegConsequences, setQ4NegConsequences] = useState('');
  const [q4Mitigation, setQ4Mitigation] = useState('');
  const [q4Contingency, setQ4Contingency] = useState('');
  const [actionItems, setActionItems] = useState<ActionItem[]>([{ action: '', who: '', by_when: '', status: 'pending' }]);

  // Social Learning for Q4
  const [showSLRiskModal, setShowSLRiskModal] = useState(false);
  const [slRiskTemplates, setSlRiskTemplates] = useState<any[]>([]);
  const [loadingSLRisk, setLoadingSLRisk] = useState(false);

  // Prefill from Social Learning templates
  useEffect(() => {
    if (params.from_social_learning) {
      if (params.prefill_goal) setSmartGoal(params.prefill_goal as string);
      if (params.prefill_concerns) setQ1AllConcerns(params.prefill_concerns as string);
      if (params.prefill_risks) setQ4Mitigation(params.prefill_risks as string);
      if (params.prefill_actions) setQ4Contingency(params.prefill_actions as string);
      if (params.prefill_area) setAreaOfLife(params.prefill_area as string);
    }
  }, [params.from_social_learning]);

  const steps = [
    { title: 'Life Area & Goal', icon: 'flag' },
    { title: 'Concerns', icon: 'alert-circle' },
    { title: 'Influence & Solutions', icon: 'bulb' },
    { title: 'Risk Management', icon: 'shield-checkmark' },
    { title: 'Action Plan', icon: 'rocket' },
  ];

  useEffect(() => {
    if (editId) loadEntry();
  }, [editId]);

  const loadEntry = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/solution-finders/${editId}`);
      const d = res.data;
      setAreaOfLife(d.area_of_life || '');
      setSmartGoal(d.smart_goal || '');
      setMilestones(d.milestones?.length ? d.milestones : [{ description: '', timeline: '' }]);
      setQ1AllConcerns(d.q1_all_concerns || '');
      setQ2PrimaryConcerns(d.q2_primary_concerns || '');
      setQ3Capabilities(d.q3_capabilities || '');
      setQ3Resources(d.q3_resources || '');
      setQ3Solutions(d.q3_solutions || '');
      setExternalHelpAspect(d.external_help_aspect || '');
      setExternalHelpLevel(d.external_help_level || '');
      setExternalHelpFrom(d.external_help_from || '');
      setQ4NegConsequences(d.q4_negative_consequences || '');
      setQ4Mitigation(d.q4_mitigation_plans || '');
      setQ4Contingency(d.q4_contingency_plans || '');
      setActionItems(d.action_items?.length ? d.action_items : [{ action: '', who: '', by_when: '', status: 'pending' }]);
    } catch (e) {
      showAlert('Error', 'Failed to load entry');
    } finally {
      setLoading(false);
    }
  };

  // Social Learning templates for Q4 Risk
  const fetchSLRiskTemplates = async () => {
    setLoadingSLRisk(true);
    try {
      const res = await api.get('/social-learning/templates-for-solution-finder', {
        params: { life_area: areaOfLife || undefined, include_personal: true, limit: 20 },
      });
      // Combine all 3 tiers
      const all: any[] = [];
      (res.data?.tier_1_personal || []).forEach((t: any) => all.push({ ...t, _tierLabel: 'Personal' }));
      (res.data?.tier_2_authorized || []).forEach((t: any) => all.push({ ...t, _tierLabel: 'Authorized' }));
      (res.data?.tier_3_ai_derived || []).forEach((t: any) => all.push({ ...t, _tierLabel: 'AI Premium' }));
      setSlRiskTemplates(all);
    } catch (e) {
      console.error('Failed to load SL risk templates:', e);
      setSlRiskTemplates([]);
    } finally {
      setLoadingSLRisk(false);
    }
  };

  const applySLRiskTemplate = (t: any) => {
    const risks = t.risks || [];
    const riskLines = risks.map((r: any) =>
      `[Risk Index: ${r.risk_index || 'N/A'}] ${r.risk_name} (Prob: ${r.probability}/10, Impact: ${r.impact}/10)`
    ).join('\n');
    const mitigations = risks.map((r: any) => r.mitigation_plan).filter(Boolean).join('\n');
    const contingencies = risks.map((r: any) => r.contingency_plan).filter(Boolean).join('\n');

    if (riskLines) setQ4NegConsequences(prev => prev ? prev + '\n' + riskLines : riskLines);
    if (mitigations) setQ4Mitigation(prev => prev ? prev + '\n' + mitigations : mitigations);
    if (contingencies) setQ4Contingency(prev => prev ? prev + '\n' + contingencies : contingencies);
    setShowSLRiskModal(false);
    showAlert('Applied', `${risks.length} risks with mitigations & contingencies added from ${t._tierLabel || 'Social Learning'}.`);
  };

  const handleSave = async () => {
    if (!areaOfLife) {
      showAlert('Required', 'Please select an area of life');
      return;
    }
    if (!smartGoal.trim()) {
      showAlert('Required', 'Please enter a SMART goal');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        area_of_life: areaOfLife,
        smart_goal: smartGoal,
        milestones: milestones.filter(m => m.description.trim()),
        q1_all_concerns: q1AllConcerns,
        q2_primary_concerns: q2PrimaryConcerns,
        q3_capabilities: q3Capabilities,
        q3_resources: q3Resources,
        q3_solutions: q3Solutions,
        external_help_aspect: externalHelpAspect,
        external_help_level: externalHelpLevel,
        external_help_from: externalHelpFrom,
        q4_negative_consequences: q4NegConsequences,
        q4_mitigation_plans: q4Mitigation,
        q4_contingency_plans: q4Contingency,
        action_items: actionItems.filter(a => a.action.trim()),
        status: currentStep >= 4 ? 'completed' : 'in_progress',
      };

      if (editId) {
        await api.put(`/solution-finders/${editId}`, payload);
      } else {
        const res = await api.post('/solution-finders', payload);
        if (res.data?.id) setSavedId(res.data.id);
      }
      showAlert('Saved', 'Solution Finder saved successfully!', [
        { text: 'OK', onPress: () => router.back() }
      ]);
    } catch (e) {
      showAlert('Error', 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const addMilestone = () => setMilestones([...milestones, { description: '', timeline: '' }]);
  const removeMilestone = (i: number) => {
    if (milestones.length > 1) setMilestones(milestones.filter((_, idx) => idx !== i));
  };
  const updateMilestone = (i: number, field: keyof Milestone, val: string) => {
    const updated = [...milestones];
    updated[i] = { ...updated[i], [field]: val };
    setMilestones(updated);
  };

  const addActionItem = () => setActionItems([...actionItems, { action: '', who: '', by_when: '', status: 'pending' }]);
  const removeActionItem = (i: number) => {
    if (actionItems.length > 1) setActionItems(actionItems.filter((_, idx) => idx !== i));
  };
  const updateActionItem = (i: number, field: keyof ActionItem, val: string) => {
    const updated = [...actionItems];
    updated[i] = { ...updated[i], [field]: val };
    setActionItems(updated);
  };

  // ======== COLLABORATION ========
  const openCollabModal = async () => {
    if (!savedId) {
      showAlert('Save First', 'Please save this Solution Finder entry before starting a collaboration session.');
      return;
    }
    try {
      const [modesRes, contactsRes, sessionsRes] = await Promise.all([
        api.get('/collaboration/decision-modes').catch(() => ({ data: [] })),
        api.get('/contacts?limit=100').catch(() => ({ data: [] })),
        api.get('/collaboration/sessions').catch(() => ({ data: [] })),
      ]);
      setCollabModes(modesRes.data || []);
      setCollabContacts(contactsRes.data || []);
      // Filter sessions linked to this solution finder
      const linked = (sessionsRes.data || []).filter((s: any) => s.module_id === savedId && s.module_type === 'solution_finder');
      setExistingCollabs(linked);
    } catch (e) { /* ignore */ }
    setShowCollabModal(true);
  };

  const handleCreateCollab = async () => {
    if (collabSelectedContacts.size === 0) {
      showAlert('Required', 'Select at least one participant');
      return;
    }
    setCollabCreating(true);
    try {
      await api.post('/collaboration/sessions', {
        module_type: 'solution_finder',
        module_id: savedId,
        title: `${areaOfLife ? areaOfLife.replace(/_/g, ' ') + ': ' : ''}${smartGoal.slice(0, 50) || 'Solution Finder'}`,
        decision_mode_id: collabSelectedMode,
        participant_contact_ids: Array.from(collabSelectedContacts),
        auth_config: { methods_required: 0, verify_each_time: false, enabled_methods: [] },
        notify_participants: true,
        session_mode: collabSessionMode,
      });
      showAlert('Session Created', 'Group collaboration session launched! Participants will be notified.');
      setShowCollabModal(false);
      setCollabSelectedContacts(new Set());
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to create session');
    } finally {
      setCollabCreating(false);
    }
  };

  const toggleCollabContact = (id: string) => {
    const newSet = new Set(collabSelectedContacts);
    if (newSet.has(id)) newSet.delete(id); else newSet.add(id);
    setCollabSelectedContacts(newSet);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <View>
            <Text style={styles.stepLabel}>Select Area of Life</Text>
            <View style={styles.areaGrid}>
              {LIFE_AREAS.map(area => (
                <TouchableOpacity
                  key={area.id}
                  style={[
                    styles.areaChip,
                    areaOfLife === area.id && styles.areaChipActive
                  ]}
                  onPress={() => setAreaOfLife(area.id)}
                >
                  <Ionicons
                    name={area.icon as any}
                    size={18}
                    color={areaOfLife === area.id ? '#FFF' : COLORS.primary}
                  />
                  <Text style={[
                    styles.areaChipText,
                    areaOfLife === area.id && styles.areaChipTextActive
                  ]}>{area.name}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.stepLabel}>SMART Goal</Text>
            <TextInput
              style={styles.textArea}
              placeholder="e.g., To earn minimum Rs.3 lakh income on or before 30.10.2025"
              placeholderTextColor={COLORS.textMuted}
              value={smartGoal}
              onChangeText={setSmartGoal}
              multiline
              numberOfLines={3}
            />

            <View style={styles.labelRow}>
              <Text style={styles.stepLabel}>Milestones</Text>
              <TouchableOpacity onPress={addMilestone} style={styles.addBtn}>
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
                <TextInput
                  style={styles.input}
                  placeholder="Milestone description"
                  placeholderTextColor={COLORS.textMuted}
                  value={m.description}
                  onChangeText={v => updateMilestone(i, 'description', v)}
                />
                <TextInput
                  style={styles.input}
                  placeholder="Timeline (e.g., 15.09.2025)"
                  placeholderTextColor={COLORS.textMuted}
                  value={m.timeline}
                  onChangeText={v => updateMilestone(i, 'timeline', v)}
                />
              </View>
            ))}
          </View>
        );

      case 1:
        return (
          <View>
            <Text style={styles.stepLabel}>Q1. What are ALL your concerns?</Text>
            <Text style={styles.hint}>List every worry, challenge, or obstacle related to your goal</Text>
            <TextInput
              style={styles.textArea}
              placeholder="1. Fees negotiation\n2. Health concerns\n3. Time management..."
              placeholderTextColor={COLORS.textMuted}
              value={q1AllConcerns}
              onChangeText={setQ1AllConcerns}
              multiline
              numberOfLines={5}
            />

            <Text style={styles.stepLabel}>Q2. What are your PRIMARY concerns now?</Text>
            <Text style={styles.hint}>Prioritize the most critical concerns from Q1</Text>
            <TextInput
              style={styles.textArea}
              placeholder="1. Time management\n2. Marketing & Sales..."
              placeholderTextColor={COLORS.textMuted}
              value={q2PrimaryConcerns}
              onChangeText={setQ2PrimaryConcerns}
              multiline
              numberOfLines={4}
            />
          </View>
        );

      case 2:
        return (
          <View>
            <Text style={styles.sectionHeader}>Q3.1 Current Influence Level</Text>

            <Text style={styles.stepLabel}>Capabilities (Knowledge, Skills)</Text>
            <TextInput
              style={styles.textArea}
              placeholder="e.g., 1. Domain knowledge\n2. Communication skills"
              placeholderTextColor={COLORS.textMuted}
              value={q3Capabilities}
              onChangeText={setQ3Capabilities}
              multiline
              numberOfLines={3}
            />

            <Text style={styles.stepLabel}>Resources (Contacts, Time, Money, Assets)</Text>
            <TextInput
              style={styles.textArea}
              placeholder="e.g., 1. Social image\n2. Existing contacts\n3. Time"
              placeholderTextColor={COLORS.textMuted}
              value={q3Resources}
              onChangeText={setQ3Resources}
              multiline
              numberOfLines={3}
            />

            <Text style={styles.sectionHeader}>Q3.2 Solutions within Influence</Text>
            <Text style={styles.hint}>What can you do within your current influence level to address primary concerns?</Text>
            <TextInput
              style={styles.textArea}
              placeholder="e.g., 1. Prepare a fees structure\n2. Learn online teaching"
              placeholderTextColor={COLORS.textMuted}
              value={q3Solutions}
              onChangeText={setQ3Solutions}
              multiline
              numberOfLines={4}
            />

            <Text style={styles.sectionHeader}>External Help Needed</Text>

            <Text style={styles.stepLabel}>What aspect needs external help?</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g., Social media marketing"
              placeholderTextColor={COLORS.textMuted}
              value={externalHelpAspect}
              onChangeText={setExternalHelpAspect}
            />

            <Text style={styles.stepLabel}>Level of Help</Text>
            <View style={styles.helpLevelRow}>
              {HELP_LEVELS.map(level => (
                <TouchableOpacity
                  key={level}
                  style={[
                    styles.helpChip,
                    externalHelpLevel === level && styles.helpChipActive
                  ]}
                  onPress={() => setExternalHelpLevel(level)}
                >
                  <Text style={[
                    styles.helpChipText,
                    externalHelpLevel === level && styles.helpChipTextActive
                  ]}>{level}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.stepLabel}>Help from whom?</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g., Friend, Mentor, Expert"
              placeholderTextColor={COLORS.textMuted}
              value={externalHelpFrom}
              onChangeText={setExternalHelpFrom}
            />
          </View>
        );

      case 3:
        return (
          <View>
            <Text style={styles.sectionHeader}>Q4. Risk Management</Text>

            {/* Social Learning Risk Templates */}
            <TouchableOpacity
              style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F3FF', borderRadius: 10, padding: 12, marginBottom: 14, borderWidth: 1, borderColor: '#DDD6FE', gap: 10 }}
              onPress={() => { setShowSLRiskModal(true); fetchSLRiskTemplates(); }}
            >
              <Ionicons name="newspaper" size={18} color="#7C3AED" />
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 13, fontWeight: '600', color: '#7C3AED' }}>Load from Social Learning</Text>
                <Text style={{ fontSize: 10, color: '#8B5CF6' }}>Auto-fill risks from real-world scenarios</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color="#7C3AED" />
            </TouchableOpacity>

            <Text style={styles.stepLabel}>Possible Negative Consequences</Text>
            <TextInput
              style={styles.textArea}
              placeholder="1. Family disturbance\n2. Health/Mindset problems"
              placeholderTextColor={COLORS.textMuted}
              value={q4NegConsequences}
              onChangeText={setQ4NegConsequences}
              multiline
              numberOfLines={4}
            />

            <Text style={styles.stepLabel}>Mitigation Plans</Text>
            <Text style={styles.hint}>How will you prevent these consequences?</Text>
            <TextInput
              style={styles.textArea}
              placeholder="1. Set boundaries\n2. Regular self-care"
              placeholderTextColor={COLORS.textMuted}
              value={q4Mitigation}
              onChangeText={setQ4Mitigation}
              multiline
              numberOfLines={4}
            />

            <Text style={styles.stepLabel}>Contingency Plans</Text>
            <Text style={styles.hint}>Backup plans if consequences occur despite mitigation</Text>
            <TextInput
              style={styles.textArea}
              placeholder="1. Pause sales temporarily\n2. Seek professional help"
              placeholderTextColor={COLORS.textMuted}
              value={q4Contingency}
              onChangeText={setQ4Contingency}
              multiline
              numberOfLines={4}
            />
          </View>
        );

      case 4:
        return (
          <View>
            <Text style={styles.sectionHeader}>Q5. Action Plan</Text>

            <View style={styles.labelRow}>
              <Text style={styles.stepLabel}>Action Items</Text>
              <TouchableOpacity onPress={addActionItem} style={styles.addBtn}>
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
                <TextInput
                  style={styles.input}
                  placeholder="What action?"
                  placeholderTextColor={COLORS.textMuted}
                  value={item.action}
                  onChangeText={v => updateActionItem(i, 'action', v)}
                />
                <View style={styles.twoCol}>
                  <TextInput
                    style={[styles.input, { flex: 1 }]}
                    placeholder="Who does?"
                    placeholderTextColor={COLORS.textMuted}
                    value={item.who}
                    onChangeText={v => updateActionItem(i, 'who', v)}
                  />
                  <TextInput
                    style={[styles.input, { flex: 1 }]}
                    placeholder="By when?"
                    placeholderTextColor={COLORS.textMuted}
                    value={item.by_when}
                    onChangeText={v => updateActionItem(i, 'by_when', v)}
                  />
                </View>
                <View style={styles.statusRow}>
                  {['pending', 'in_progress', 'completed'].map(s => (
                    <TouchableOpacity
                      key={s}
                      style={[
                        styles.statusChip,
                        item.status === s && styles.statusChipActive
                      ]}
                      onPress={() => updateActionItem(i, 'status', s)}
                    >
                      <Text style={[
                        styles.statusChipText,
                        item.status === s && styles.statusChipTextActive
                      ]}>{s.replace('_', ' ').toUpperCase()}</Text>
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
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        {/* Header */}
        <LinearGradient colors={GRADIENTS.header} style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerTitle}>Simple Solution Finder</Text>
            <Text style={styles.headerSub}>Step {currentStep + 1} of {steps.length}</Text>
          </View>
          <TouchableOpacity style={styles.collabHdrBtn} onPress={openCollabModal}>
            <Ionicons name="people" size={18} color="#7C3AED" />
          </TouchableOpacity>
        </LinearGradient>

        {/* Step Indicators */}
        <View style={styles.stepIndicator}>
          {steps.map((step, i) => (
            <TouchableOpacity
              key={i}
              style={[
                styles.stepDot,
                currentStep === i && styles.stepDotActive,
                currentStep > i && styles.stepDotDone
              ]}
              onPress={() => setCurrentStep(i)}
            >
              <Ionicons
                name={step.icon as any}
                size={16}
                color={currentStep >= i ? '#FFF' : COLORS.textMuted}
              />
            </TouchableOpacity>
          ))}
        </View>

        <ScrollView
          style={styles.scrollView}
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.currentStepTitle}>{steps[currentStep].title}</Text>
          {renderStepContent()}
        </ScrollView>

        {/* Bottom Nav */}
        <View style={styles.bottomNav}>
          {currentStep > 0 && (
            <TouchableOpacity
              style={styles.navBtnSecondary}
              onPress={() => setCurrentStep(currentStep - 1)}
            >
              <Ionicons name="arrow-back" size={18} color={COLORS.primary} />
              <Text style={styles.navBtnSecondaryText}>Back</Text>
            </TouchableOpacity>
          )}
          <View style={{ flex: 1 }} />
          {currentStep < steps.length - 1 ? (
            <TouchableOpacity
              style={styles.navBtnPrimary}
              onPress={() => setCurrentStep(currentStep + 1)}
            >
              <Text style={styles.navBtnPrimaryText}>Next</Text>
              <Ionicons name="arrow-forward" size={18} color="#FFF" />
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={[styles.navBtnPrimary, saving && { opacity: 0.7 }]}
              onPress={handleSave}
              disabled={saving}
            >
              {saving ? (
                <ActivityIndicator size="small" color="#FFF" />
              ) : (
                <>
                  <Ionicons name="checkmark-circle" size={18} color="#FFF" />
                  <Text style={styles.navBtnPrimaryText}>Save</Text>
                </>
              )}
            </TouchableOpacity>
          )}
        </View>

        {/* Collaboration Modal */}
        <Modal visible={showCollabModal} transparent animationType="slide">
          <View style={styles.collabOverlay}>
            <View style={styles.collabModalContent}>
              <View style={styles.collabModalHeader}>
                <Ionicons name="people" size={22} color="#7C3AED" />
                <Text style={styles.collabModalTitle}>Group Collaborate</Text>
                <View style={{ flex: 1 }} />
                <TouchableOpacity onPress={() => setShowCollabModal(false)}>
                  <Ionicons name="close" size={24} color="#6B7280" />
                </TouchableOpacity>
              </View>

              <ScrollView style={{ maxHeight: 400 }} showsVerticalScrollIndicator={false}>
                {/* Existing Sessions */}
                {existingCollabs.length > 0 && (
                  <View style={styles.existingCollabSection}>
                    <Text style={styles.collabSectionTitle}>Active Sessions ({existingCollabs.length})</Text>
                    {existingCollabs.map((s: any) => (
                      <View key={s.id} style={styles.existingCollabCard}>
                        <Ionicons name="git-network" size={16} color="#7C3AED" />
                        <View style={{ flex: 1 }}>
                          <Text style={styles.existingCollabTitle}>{s.title}</Text>
                          <Text style={styles.existingCollabMeta}>
                            {s.session_mode === 'live_sync' ? 'Live Sync' : 'Async'} • {(s.participants || []).length} people
                          </Text>
                        </View>
                        <View style={[styles.existingCollabStatus, { backgroundColor: s.status === 'active' ? '#ECFDF5' : '#EFF6FF' }]}>
                          <Text style={{ fontSize: 10, fontWeight: '600', color: s.status === 'active' ? '#059669' : '#3B82F6' }}>
                            {s.status}
                          </Text>
                        </View>
                      </View>
                    ))}
                  </View>
                )}

                {/* Create New */}
                <Text style={styles.collabSectionTitle}>New Session</Text>

                {/* Session Mode */}
                <View style={{ flexDirection: 'row', gap: 8, marginBottom: 12 }}>
                  {[{key: 'async', label: 'Async', icon: 'time-outline'}, {key: 'live_sync', label: 'Live Sync', icon: 'videocam-outline'}].map(m => (
                    <TouchableOpacity key={m.key}
                      style={[styles.collabModeChip, collabSessionMode === m.key && styles.collabModeChipActive]}
                      onPress={() => setCollabSessionMode(m.key)}>
                      <Ionicons name={m.icon as any} size={14} color={collabSessionMode === m.key ? '#FFF' : '#6B7280'} />
                      <Text style={[styles.collabModeChipText, collabSessionMode === m.key && { color: '#FFF' }]}>{m.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Decision Mode */}
                {collabModes.length > 0 && (
                  <View style={{ marginBottom: 12 }}>
                    <Text style={styles.collabFieldLabel}>Decision Mode</Text>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                      <View style={{ flexDirection: 'row', gap: 6 }}>
                        {collabModes.map((mode: any) => (
                          <TouchableOpacity key={mode.id}
                            style={[styles.collabModeChip, collabSelectedMode === mode.id && styles.collabModeChipActive]}
                            onPress={() => setCollabSelectedMode(mode.id)}>
                            <Text style={[styles.collabModeChipText, collabSelectedMode === mode.id && { color: '#FFF' }]}>{mode.name}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </ScrollView>
                  </View>
                )}

                {/* Select Participants */}
                <Text style={styles.collabFieldLabel}>Participants ({collabSelectedContacts.size} selected)</Text>
                {collabContacts.length === 0 ? (
                  <Text style={styles.collabNoContacts}>No contacts found. Add contacts from the Contacts screen first.</Text>
                ) : (
                  collabContacts.map((c: any) => (
                    <TouchableOpacity key={c.id}
                      style={[styles.collabContactRow, collabSelectedContacts.has(c.id) && styles.collabContactRowActive]}
                      onPress={() => toggleCollabContact(c.id)}>
                      <View style={styles.collabContactAvatar}>
                        <Text style={{ fontSize: 12, fontWeight: '700', color: '#FFF' }}>{(c.name || '?')[0].toUpperCase()}</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.collabContactName}>{c.name}</Text>
                        <Text style={styles.collabContactMeta}>{[c.profession, c.org_type].filter(Boolean).join(' • ')}</Text>
                      </View>
                      <Ionicons name={collabSelectedContacts.has(c.id) ? 'checkmark-circle' : 'ellipse-outline'} size={20}
                        color={collabSelectedContacts.has(c.id) ? '#059669' : '#D1D5DB'} />
                    </TouchableOpacity>
                  ))
                )}
              </ScrollView>

              <TouchableOpacity style={styles.collabLaunchBtn} onPress={handleCreateCollab} disabled={collabCreating}>
                {collabCreating ? <ActivityIndicator color="#FFF" size="small" /> : (
                  <>
                    <Ionicons name="rocket" size={16} color="#FFF" />
                    <Text style={styles.collabLaunchText}>Launch Group Session</Text>
                  </>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </Modal>

        {/* Social Learning Risk Templates Modal */}
        <Modal visible={showSLRiskModal} transparent animationType="slide">
          <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' }}>
            <View style={{ backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '70%' }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <Ionicons name="newspaper" size={20} color="#7C3AED" />
                  <Text style={{ fontSize: 16, fontWeight: '700', color: '#1F2937' }}>Social Learning Risks</Text>
                </View>
                <TouchableOpacity onPress={() => setShowSLRiskModal(false)}>
                  <Ionicons name="close" size={24} color="#6B7280" />
                </TouchableOpacity>
              </View>
              <Text style={{ fontSize: 12, color: '#9CA3AF', marginBottom: 12 }}>
                Select a template to auto-populate risk insights
              </Text>
              {loadingSLRisk ? (
                <ActivityIndicator size="large" color="#7C3AED" style={{ marginTop: 40 }} />
              ) : slRiskTemplates.length === 0 ? (
                <View style={{ alignItems: 'center', paddingVertical: 40 }}>
                  <Ionicons name="newspaper-outline" size={40} color="#D1D5DB" />
                  <Text style={{ fontSize: 14, color: '#9CA3AF', marginTop: 8 }}>No risk templates available</Text>
                </View>
              ) : (
                <ScrollView showsVerticalScrollIndicator={false}>
                  {slRiskTemplates.map((t: any) => (
                    <TouchableOpacity
                      key={t.id}
                      style={{ backgroundColor: '#F9FAFB', borderRadius: 10, padding: 12, marginBottom: 8, borderLeftWidth: 3, borderLeftColor: t.tier === 3 ? '#7C3AED' : t.tier === 2 ? '#059669' : '#6B7280' }}
                      onPress={() => applySLRiskTemplate(t)}
                    >
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                        <View style={{ backgroundColor: t.tier === 3 ? '#F5F3FF' : t.tier === 2 ? '#ECFDF5' : '#F3F4F6', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 }}>
                          <Text style={{ fontSize: 9, fontWeight: '700', color: t.tier === 3 ? '#7C3AED' : t.tier === 2 ? '#059669' : '#6B7280' }}>
                            {t._tierLabel}
                          </Text>
                        </View>
                        <Text style={{ fontSize: 10, color: '#9CA3AF' }}>{(t.risks || []).length} risks</Text>
                      </View>
                      <Text style={{ fontSize: 13, fontWeight: '600', color: '#1F2937' }} numberOfLines={1}>
                        {t.scenario_title || t.title}
                      </Text>
                      {(t.risks || []).length > 0 && (
                        <View style={{ marginTop: 6 }}>
                          {(t.risks || []).slice(0, 3).map((r: any, i: number) => (
                            <View key={i} style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginBottom: 3 }}>
                              <View style={{ width: 18, height: 18, borderRadius: 4, backgroundColor: (r.risk_index || 0) >= 50 ? '#FEF2F2' : (r.risk_index || 0) >= 25 ? '#FFFBEB' : '#ECFDF5', justifyContent: 'center', alignItems: 'center' }}>
                                <Text style={{ fontSize: 8, fontWeight: '700', color: (r.risk_index || 0) >= 50 ? '#EF4444' : (r.risk_index || 0) >= 25 ? '#D97706' : '#059669' }}>
                                  {r.risk_index || '?'}
                                </Text>
                              </View>
                              <Text style={{ fontSize: 10, color: '#374151', flex: 1 }} numberOfLines={1}>{r.risk_name}</Text>
                              <Text style={{ fontSize: 8, color: '#9CA3AF' }}>P{r.probability} × I{r.impact}</Text>
                            </View>
                          ))}
                        </View>
                      )}
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6 }}>
                        <Ionicons name="add-circle" size={14} color="#7C3AED" />
                        <Text style={{ fontSize: 10, color: '#7C3AED', fontWeight: '500' }}>Tap to apply risks + mitigations</Text>
                      </View>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              )}
            </View>
          </View>
        </Modal>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    paddingBottom: 20,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
    marginRight: 12,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  stepIndicator: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 12,
    paddingVertical: 14,
    backgroundColor: COLORS.white,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  stepDot: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: COLORS.divider,
    justifyContent: 'center', alignItems: 'center',
  },
  stepDotActive: { backgroundColor: COLORS.primary },
  stepDotDone: { backgroundColor: COLORS.success },
  scrollView: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 32 },
  currentStepTitle: {
    fontSize: 20, fontWeight: '700', color: COLORS.textPrimary,
    marginBottom: 16,
  },
  stepLabel: {
    fontSize: 14, fontWeight: '600', color: COLORS.textPrimary,
    marginTop: 16, marginBottom: 6,
  },
  hint: {
    fontSize: 12, color: COLORS.textMuted, marginBottom: 8,
  },
  sectionHeader: {
    fontSize: 16, fontWeight: '700', color: COLORS.primary,
    marginTop: 20, marginBottom: 4,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
    paddingBottom: 6,
  },
  areaGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8,
  },
  areaChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 20, borderWidth: 1, borderColor: COLORS.primary,
    backgroundColor: 'rgba(142,36,170,0.05)',
  },
  areaChipActive: {
    backgroundColor: COLORS.primary, borderColor: COLORS.primary,
  },
  areaChipText: {
    fontSize: 12, fontWeight: '500', color: COLORS.primary,
  },
  areaChipTextActive: { color: '#FFF' },
  input: {
    backgroundColor: COLORS.white,
    borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 10,
    fontSize: 14, color: COLORS.textPrimary,
    marginBottom: 8,
  },
  textArea: {
    backgroundColor: COLORS.white,
    borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 10,
    fontSize: 14, color: COLORS.textPrimary,
    minHeight: 80, textAlignVertical: 'top',
    marginBottom: 8,
  },
  labelRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  addBtn: { padding: 4 },
  milestoneCard: {
    backgroundColor: COLORS.white, borderRadius: 12,
    padding: 12, marginBottom: 10,
    borderWidth: 1, borderColor: COLORS.border,
  },
  milestoneHeader: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 8,
  },
  milestoneNum: {
    fontSize: 13, fontWeight: '600', color: COLORS.primary,
  },
  actionCard: {
    backgroundColor: COLORS.white, borderRadius: 12,
    padding: 12, marginBottom: 12,
    borderWidth: 1, borderColor: COLORS.border,
  },
  twoCol: {
    flexDirection: 'row', gap: 8,
  },
  helpLevelRow: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8,
  },
  helpChip: {
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 20, borderWidth: 1, borderColor: COLORS.border,
    backgroundColor: COLORS.white,
  },
  helpChipActive: {
    backgroundColor: COLORS.teal, borderColor: COLORS.teal,
  },
  helpChipText: {
    fontSize: 12, fontWeight: '500', color: COLORS.textSecondary,
  },
  helpChipTextActive: { color: '#FFF' },
  statusRow: {
    flexDirection: 'row', gap: 6, marginTop: 4,
  },
  statusChip: {
    paddingHorizontal: 10, paddingVertical: 5,
    borderRadius: 12, borderWidth: 1, borderColor: COLORS.border,
    backgroundColor: COLORS.divider,
  },
  statusChipActive: {
    backgroundColor: COLORS.success, borderColor: COLORS.success,
  },
  statusChipText: {
    fontSize: 10, fontWeight: '600', color: COLORS.textMuted,
  },
  statusChipTextActive: { color: '#FFF' },
  bottomNav: {
    flexDirection: 'row', alignItems: 'center',
    padding: 16, borderTopWidth: 1,
    borderTopColor: COLORS.border, backgroundColor: COLORS.white,
  },
  navBtnSecondary: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: 10, borderWidth: 1, borderColor: COLORS.primary,
  },
  navBtnSecondaryText: {
    fontSize: 14, fontWeight: '600', color: COLORS.primary,
  },
  navBtnPrimary: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 20, paddingVertical: 12,
    borderRadius: 10, backgroundColor: COLORS.primary,
  },
  navBtnPrimaryText: {
    fontSize: 14, fontWeight: '600', color: '#FFF',
  },

  // Collaboration integration styles
  collabHdrBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#FFF', justifyContent: 'center', alignItems: 'center' },
  collabOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end', alignItems: 'center' },
  collabModalContent: { width: '100%', maxWidth: 500, backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '80%' },
  collabModalHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 16 },
  collabModalTitle: { fontSize: 18, fontWeight: '700', color: '#1F2937' },
  collabSectionTitle: { fontSize: 14, fontWeight: '700', color: '#374151', marginBottom: 8, marginTop: 4 },
  existingCollabSection: { marginBottom: 16, borderBottomWidth: 1, borderBottomColor: '#F3F4F6', paddingBottom: 12 },
  existingCollabCard: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 8, backgroundColor: '#F5F3FF', marginBottom: 6 },
  existingCollabTitle: { fontSize: 12, fontWeight: '600', color: '#374151' },
  existingCollabMeta: { fontSize: 10, color: '#9CA3AF', marginTop: 1 },
  existingCollabStatus: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  collabModeChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: '#E5E7EB' },
  collabModeChipActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  collabModeChipText: { fontSize: 12, fontWeight: '600', color: '#6B7280' },
  collabFieldLabel: { fontSize: 12, fontWeight: '600', color: '#6B7280', marginBottom: 6 },
  collabNoContacts: { fontSize: 12, color: '#9CA3AF', fontStyle: 'italic', marginBottom: 12 },
  collabContactRow: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 8, backgroundColor: '#F9FAFB', marginBottom: 4 },
  collabContactRowActive: { backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0' },
  collabContactAvatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#7C3AED', justifyContent: 'center', alignItems: 'center' },
  collabContactName: { fontSize: 12, fontWeight: '600', color: '#374151' },
  collabContactMeta: { fontSize: 10, color: '#9CA3AF' },
  collabLaunchBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#059669', borderRadius: 12, paddingVertical: 14, marginTop: 12 },
  collabLaunchText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
});
