import React, { useState, useEffect, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Alert, KeyboardAvoidingView, Platform, FlatList,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import { useAuthStore } from '../../src/store/authStore';
import api from '../../src/utils/api';

// ====== TYPES ======
interface LifeArea { id: string; name: string; slug: string; icon: string; color: string; order: number; }
interface AskType { id: string; name: string; slug: string; icon: string; color: string; description: string; priority_label: string; }
interface SubArea { id: string; name: string; life_area_id: string; }
interface Template {
  id: string; title: string; description: string; template_type: string;
  tags?: string[]; popularity?: number; life_area_id: string; ask_type_id: string;
  acting_as_contexts: string[];
}

// ====== CONSTANTS ======
const ACTING_AS = [
  { key: 'INDIVIDUAL', label: 'Individual', icon: 'person', color: '#6366F1', desc: 'Personal decision' },
  { key: 'ORGANIZATION', label: 'Organization', icon: 'business', color: '#0EA5E9', desc: 'Business / team decision' },
  { key: 'GOVERNMENT', label: 'Government', icon: 'globe', color: '#8B5CF6', desc: 'Public / policy decision' },
];

const TEMPLATE_TYPE_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  AUTHORIZED_STANDARD: { label: 'Curated', color: '#10B981', icon: 'shield-checkmark' },
  DYNAMIC_CLD_STARTER: { label: 'CLD Starter', color: '#F59E0B', icon: 'flash' },
};

const STEPS = ['Context', 'Life Area', 'Ask Type', 'Describe', 'Choose Template'];

export default function NewDecisionIntake() {
  const router = useRouter();
  const { user } = useAuthStore();

  // Step tracking
  const [step, setStep] = useState(0);

  // Selections
  const [actingAs, setActingAs] = useState('INDIVIDUAL');
  const [selectedArea, setSelectedArea] = useState<LifeArea | null>(null);
  const [selectedAskType, setSelectedAskType] = useState<AskType | null>(null);
  const [searchText, setSearchText] = useState('');
  const [customTitle, setCustomTitle] = useState('');

  // Data
  const [lifeAreas, setLifeAreas] = useState<LifeArea[]>([]);
  const [askTypes, setAskTypes] = useState<AskType[]>([]);
  const [subAreas, setSubAreas] = useState<SubArea[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);

  // Loading
  const [loadingAreas, setLoadingAreas] = useState(true);
  const [loadingTypes, setLoadingTypes] = useState(true);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [creating, setCreating] = useState(false);
  const [seeding, setSeeding] = useState(false);

  // ====== SEED + FETCH ======
  const seedAndFetch = useCallback(async () => {
    try {
      // Seed master data (idempotent)
      setSeeding(true);
      await api.post('/hos/seed');
    } catch (_e) { /* already seeded or error */ }
    setSeeding(false);

    // Fetch life areas
    setLoadingAreas(true);
    try {
      const r = await api.get('/hos/life-areas');
      setLifeAreas(r.data || []);
    } catch (_e) { setLifeAreas([]); }
    setLoadingAreas(false);

    // Fetch ask types
    setLoadingTypes(true);
    try {
      const r = await api.get('/hos/ask-types');
      setAskTypes(r.data || []);
    } catch (_e) { setAskTypes([]); }
    setLoadingTypes(false);
  }, []);

  useEffect(() => { seedAndFetch(); }, [seedAndFetch]);

  // Fetch templates when context is ready
  useEffect(() => {
    if (selectedArea && selectedAskType) {
      fetchTemplates();
    }
  }, [selectedArea, selectedAskType, searchText]);

  const fetchTemplates = async () => {
    if (!selectedArea || !selectedAskType) return;
    setLoadingTemplates(true);
    try {
      const params = new URLSearchParams({
        acting_as: actingAs,
        life_area_id: selectedArea.id,
        ask_type_id: selectedAskType.id,
      });
      if (searchText.trim()) params.append('q', searchText.trim());
      const r = await api.get(`/hos/templates/suggest?${params}`);
      setTemplates(r.data || []);
    } catch (_e) { setTemplates([]); }
    setLoadingTemplates(false);
  };

  // Fetch sub-areas when life area selected
  useEffect(() => {
    if (selectedArea) {
      api.get(`/hos/sub-areas?life_area_id=${selectedArea.id}`)
        .then(r => setSubAreas(r.data || []))
        .catch(() => setSubAreas([]));
    }
  }, [selectedArea]);

  // ====== DETERMINE ACTING AS FROM USER CONTEXT ======
  useEffect(() => {
    if (user?.org_id) {
      setActingAs('ORGANIZATION');
    }
  }, [user]);

  // ====== CREATE DECISION ======
  const handleCreateDecision = async (templateId?: string, sourceType?: string) => {
    const title = customTitle.trim() || searchText.trim();
    if (!title && !templateId) {
      showAlert('Title Required', 'Please enter a decision title or select a template.');
      return;
    }
    if (!selectedArea || !selectedAskType) {
      showAlert('Missing Context', 'Please select a life area and ask type.');
      return;
    }

    setCreating(true);
    try {
      const payload = {
        acting_as_context: actingAs,
        life_area_id: selectedArea.id,
        ask_type_id: selectedAskType.id,
        template_id: templateId || undefined,
        title: title || (templateId ? templates.find(t => t.id === templateId)?.title || 'New Decision' : 'New Decision'),
        raw_user_input: searchText.trim() || title,
        source_type: sourceType || (templateId ? 'AUTHORIZED_STANDARD' : 'CUSTOM_BLANK'),
      };

      const r = await api.post('/hos/decisions', payload);
      const decisionId = r.data.id;
      const factorsLoaded = r.data.factors_loaded || 0;

      if (factorsLoaded > 0) {
        showAlert(
          'Template Loaded',
          `${factorsLoaded} pre-configured factors loaded with classifications, priorities & ratings. You can review and modify them in the PRR flow.`,
          [{ text: 'Start Analysis', onPress: () => router.replace(`/prr/${decisionId}`) }]
        );
      } else {
        router.replace(`/prr/${decisionId}`);
      }
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to create decision');
    } finally {
      setCreating(false);
    }
  };

  // ====== STEP NAVIGATION ======
  const canProceed = () => {
    if (step === 0) return true; // acting as always has default
    if (step === 1) return !!selectedArea;
    if (step === 2) return !!selectedAskType;
    if (step === 3) return true; // search text is optional
    return true;
  };

  const nextStep = () => {
    if (step < STEPS.length - 1 && canProceed()) setStep(step + 1);
  };
  const prevStep = () => { if (step > 0) setStep(step - 1); };

  // ====== RENDERERS ======

  const renderStepIndicator = () => (
    <View style={s.stepRow}>
      {STEPS.map((label, i) => (
        <View key={i} style={s.stepItem}>
          <View style={[s.stepDot, i <= step && s.stepDotActive, i < step && s.stepDotDone]}>
            {i < step ? (
              <Ionicons name="checkmark" size={12} color="#FFF" />
            ) : (
              <Text style={[s.stepDotText, i <= step && s.stepDotTextActive]}>{i + 1}</Text>
            )}
          </View>
          {i < STEPS.length - 1 && <View style={[s.stepLine, i < step && s.stepLineActive]} />}
        </View>
      ))}
    </View>
  );

  const renderStep0 = () => (
    <View>
      <Text style={s.stepTitle}>This decision is for...</Text>
      <Text style={s.stepSubtitle}>Select the context for this decision</Text>
      <View style={s.contextCards}>
        {ACTING_AS.map(a => (
          <TouchableOpacity
            key={a.key}
            style={[s.contextCard, actingAs === a.key && { borderColor: a.color, backgroundColor: a.color + '10' }]}
            onPress={() => setActingAs(a.key)}
          >
            <View style={[s.contextIcon, { backgroundColor: a.color + '20' }]}>
              <Ionicons name={a.icon as any} size={28} color={a.color} />
            </View>
            <Text style={[s.contextLabel, actingAs === a.key && { color: a.color, fontWeight: '700' }]}>{a.label}</Text>
            <Text style={s.contextDesc}>{a.desc}</Text>
            {actingAs === a.key && (
              <View style={[s.checkCircle, { backgroundColor: a.color }]}>
                <Ionicons name="checkmark" size={14} color="#FFF" />
              </View>
            )}
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  const renderStep1 = () => (
    <View>
      <Text style={s.stepTitle}>Choose Life Area</Text>
      <Text style={s.stepSubtitle}>What domain does this decision belong to?</Text>
      {loadingAreas ? <ActivityIndicator style={{ marginTop: 30 }} /> : (
        <View style={s.areaGrid}>
          {lifeAreas.map(area => (
            <TouchableOpacity
              key={area.id}
              style={[s.areaCard, selectedArea?.id === area.id && { borderColor: area.color, backgroundColor: area.color + '10' }]}
              onPress={() => setSelectedArea(area)}
            >
              <Ionicons name={area.icon as any} size={24} color={selectedArea?.id === area.id ? area.color : COLORS.textMuted} />
              <Text style={[s.areaName, selectedArea?.id === area.id && { color: area.color, fontWeight: '700' }]} numberOfLines={2}>
                {area.name}
              </Text>
              {selectedArea?.id === area.id && (
                <View style={[s.areaCheck, { backgroundColor: area.color }]}>
                  <Ionicons name="checkmark" size={10} color="#FFF" />
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );

  const renderStep2 = () => (
    <View>
      <Text style={s.stepTitle}>What type of decision?</Text>
      <Text style={s.stepSubtitle}>This helps prioritize and find relevant templates</Text>
      {loadingTypes ? <ActivityIndicator style={{ marginTop: 30 }} /> : (
        <View style={s.askTypeCards}>
          {askTypes.map(t => (
            <TouchableOpacity
              key={t.id}
              style={[s.askTypeCard, selectedAskType?.id === t.id && { borderColor: t.color, backgroundColor: t.color + '10' }]}
              onPress={() => setSelectedAskType(t)}
            >
              <View style={[s.askTypeIcon, { backgroundColor: t.color + '20' }]}>
                <Ionicons name={t.icon as any} size={28} color={t.color} />
              </View>
              <View style={s.askTypeInfo}>
                <View style={s.askTypeHeader}>
                  <Text style={[s.askTypeName, selectedAskType?.id === t.id && { color: t.color }]}>{t.name}</Text>
                  <View style={[s.priorityBadge, { backgroundColor: t.color + '20' }]}>
                    <Text style={[s.priorityText, { color: t.color }]}>{t.priority_label}</Text>
                  </View>
                </View>
                <Text style={s.askTypeDesc}>{t.description}</Text>
              </View>
              {selectedAskType?.id === t.id && (
                <Ionicons name="checkmark-circle" size={22} color={t.color} />
              )}
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );

  const renderStep3 = () => (
    <View>
      <Text style={s.stepTitle}>Describe your decision</Text>
      <Text style={s.stepSubtitle}>Type keywords or a question to find relevant templates</Text>
      <TextInput
        style={s.searchInput}
        placeholder='e.g. "Should I quit my job?", "cash flow issue"'
        value={searchText}
        onChangeText={setSearchText}
        placeholderTextColor={COLORS.textMuted}
        multiline={false}
        returnKeyType="search"
        onSubmitEditing={nextStep}
      />
      {/* Sub-areas as quick chips */}
      {subAreas.length > 0 && (
        <View style={{ marginTop: 16 }}>
          <Text style={s.chipSectionLabel}>Related sub-areas in {selectedArea?.name}:</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipScroll}>
            {subAreas.map(sa => (
              <TouchableOpacity
                key={sa.id}
                style={s.subAreaChip}
                onPress={() => setSearchText(sa.name)}
              >
                <Text style={s.subAreaChipText}>{sa.name}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      )}
      <Text style={s.hintText}>You can also skip this and browse all templates</Text>
    </View>
  );

  const renderStep4 = () => (
    <View style={{ flex: 1 }}>
      <Text style={s.stepTitle}>Choose a template or start fresh</Text>
      <Text style={s.stepSubtitle}>
        {templates.length > 0
          ? `${templates.length} templates found for ${selectedArea?.name} / ${selectedAskType?.name}`
          : 'No templates match — create a custom decision'}
      </Text>

      {/* Custom title input */}
      <TextInput
        style={[s.searchInput, { marginBottom: 12 }]}
        placeholder="Decision title (or pick a template below)"
        value={customTitle}
        onChangeText={setCustomTitle}
        placeholderTextColor={COLORS.textMuted}
      />

      {/* Create from scratch button — always visible */}
      <TouchableOpacity
        style={s.scratchCard}
        onPress={() => handleCreateDecision(undefined, 'CUSTOM_BLANK')}
        disabled={creating}
      >
        <View style={s.scratchIconBox}>
          <Ionicons name="create" size={24} color={COLORS.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.scratchTitle}>Create from scratch</Text>
          <Text style={s.scratchDesc}>Start a blank decision with your own factors</Text>
        </View>
        <Ionicons name="arrow-forward" size={20} color={COLORS.primary} />
      </TouchableOpacity>

      {/* Template list */}
      {loadingTemplates ? (
        <ActivityIndicator style={{ marginTop: 20 }} />
      ) : (
        <FlatList
          data={templates}
          keyExtractor={item => item.id}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={s.templateCard}
              onPress={() => handleCreateDecision(item.id, item.template_type)}
              disabled={creating}
            >
              <View style={s.templateHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={s.templateTitle}>{item.title}</Text>
                  <Text style={s.templateDesc} numberOfLines={2}>{item.description}</Text>
                </View>
              </View>
              <View style={s.templateFooter}>
                {TEMPLATE_TYPE_CONFIG[item.template_type] && (
                  <View style={[s.typeBadge, { backgroundColor: TEMPLATE_TYPE_CONFIG[item.template_type].color + '15' }]}>
                    <Ionicons name={TEMPLATE_TYPE_CONFIG[item.template_type].icon as any} size={12} color={TEMPLATE_TYPE_CONFIG[item.template_type].color} />
                    <Text style={[s.typeBadgeText, { color: TEMPLATE_TYPE_CONFIG[item.template_type].color }]}>
                      {TEMPLATE_TYPE_CONFIG[item.template_type].label}
                    </Text>
                  </View>
                )}
                {(item.tags || []).slice(0, 3).map((tag, i) => (
                  <View key={i} style={s.tagChip}>
                    <Text style={s.tagText}>{tag}</Text>
                  </View>
                ))}
              </View>
            </TouchableOpacity>
          )}
          ListEmptyComponent={
            !loadingTemplates ? (
              <View style={s.emptyTemplates}>
                <Ionicons name="documents-outline" size={40} color={COLORS.textMuted} />
                <Text style={s.emptyText}>No templates match your search</Text>
                <Text style={s.emptyHint}>Try different keywords or create from scratch</Text>
              </View>
            ) : null
          }
          style={{ maxHeight: 400 }}
          showsVerticalScrollIndicator={false}
        />
      )}
    </View>
  );

  // ====== MAIN RENDER ======
  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {/* Header */}
        <LinearGradient colors={['#6366F1', '#8B5CF6']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.header}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <View>
            <Text style={s.headerTitle}>My Dezider</Text>
            <Text style={s.headerSubtitle}>New Decision</Text>
          </View>
          <View style={{ width: 40 }} />
        </LinearGradient>

        {/* Step indicator */}
        {renderStepIndicator()}

        {/* Content */}
        <ScrollView style={s.content} contentContainerStyle={s.contentInner} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          {seeding ? (
            <View style={{ alignItems: 'center', paddingVertical: 40 }}>
              <ActivityIndicator size="large" />
              <Text style={s.seedingText}>Initializing decision catalog...</Text>
            </View>
          ) : (
            <>
              {step === 0 && renderStep0()}
              {step === 1 && renderStep1()}
              {step === 2 && renderStep2()}
              {step === 3 && renderStep3()}
              {step === 4 && renderStep4()}
            </>
          )}
        </ScrollView>

        {/* Navigation buttons */}
        {!seeding && step < 4 && (
          <View style={s.navRow}>
            {step > 0 && (
              <TouchableOpacity style={s.navBtnBack} onPress={prevStep}>
                <Ionicons name="arrow-back" size={18} color={COLORS.textSecondary} />
                <Text style={s.navBtnBackText}>Back</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity
              style={[s.navBtnNext, !canProceed() && s.navBtnDisabled]}
              onPress={nextStep}
              disabled={!canProceed()}
            >
              <Text style={s.navBtnNextText}>{step === 3 ? 'Find Templates' : 'Next'}</Text>
              <Ionicons name="arrow-forward" size={18} color="#FFF" />
            </TouchableOpacity>
          </View>
        )}

        {/* Creating overlay */}
        {creating && (
          <View style={s.overlay}>
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text style={s.overlayText}>Creating your decision...</Text>
          </View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 16, paddingTop: 8,
  },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF', textAlign: 'center' },
  headerSubtitle: { fontSize: 12, color: 'rgba(255,255,255,0.8)', textAlign: 'center', marginTop: 2 },

  // Step indicator
  stepRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 16, paddingHorizontal: 24 },
  stepItem: { flexDirection: 'row', alignItems: 'center' },
  stepDot: {
    width: 26, height: 26, borderRadius: 13, backgroundColor: COLORS.border,
    justifyContent: 'center', alignItems: 'center',
  },
  stepDotActive: { backgroundColor: COLORS.primary + '30', borderWidth: 2, borderColor: COLORS.primary },
  stepDotDone: { backgroundColor: COLORS.primary, borderWidth: 0 },
  stepDotText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },
  stepDotTextActive: { color: COLORS.primary },
  stepLine: { width: 24, height: 2, backgroundColor: COLORS.border, marginHorizontal: 2 },
  stepLineActive: { backgroundColor: COLORS.primary },

  content: { flex: 1 },
  contentInner: { padding: 20, paddingBottom: 40 },

  // Step titles
  stepTitle: { fontSize: 22, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  stepSubtitle: { fontSize: 14, color: COLORS.textSecondary, marginBottom: 20, lineHeight: 20 },

  // Step 0: Context cards
  contextCards: { gap: 12 },
  contextCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.white,
    borderRadius: 14, padding: 16, borderWidth: 2, borderColor: COLORS.border, gap: 14,
  },
  contextIcon: { width: 52, height: 52, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  contextLabel: { fontSize: 16, fontWeight: '600', color: COLORS.textPrimary },
  contextDesc: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  checkCircle: {
    position: 'absolute', top: 12, right: 12, width: 24, height: 24, borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
  },

  // Step 1: Life area grid
  areaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  areaCard: {
    width: '47%' as any, backgroundColor: COLORS.white, borderRadius: 12, padding: 14,
    borderWidth: 2, borderColor: COLORS.border, alignItems: 'center', gap: 8, minHeight: 90,
  },
  areaName: { fontSize: 12, fontWeight: '500', color: COLORS.textPrimary, textAlign: 'center' },
  areaCheck: {
    position: 'absolute', top: 6, right: 6, width: 18, height: 18, borderRadius: 9,
    justifyContent: 'center', alignItems: 'center',
  },

  // Step 2: Ask type
  askTypeCards: { gap: 12 },
  askTypeCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.white,
    borderRadius: 14, padding: 16, borderWidth: 2, borderColor: COLORS.border, gap: 14,
  },
  askTypeIcon: { width: 50, height: 50, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  askTypeInfo: { flex: 1 },
  askTypeHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  askTypeName: { fontSize: 17, fontWeight: '600', color: COLORS.textPrimary },
  priorityBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  priorityText: { fontSize: 11, fontWeight: '700' },
  askTypeDesc: { fontSize: 13, color: COLORS.textSecondary, marginTop: 4 },

  // Step 3: Search
  searchInput: {
    backgroundColor: COLORS.white, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, color: COLORS.textPrimary,
  },
  chipSectionLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 8 },
  chipScroll: { gap: 8 },
  subAreaChip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20,
    backgroundColor: COLORS.primary + '10', borderWidth: 1, borderColor: COLORS.primary + '30',
  },
  subAreaChipText: { fontSize: 13, color: COLORS.primary, fontWeight: '500' },
  hintText: { fontSize: 12, color: COLORS.textMuted, marginTop: 16, fontStyle: 'italic' },

  // Step 4: Templates
  scratchCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.primary + '08',
    borderRadius: 14, padding: 16, borderWidth: 1.5, borderColor: COLORS.primary + '30',
    borderStyle: 'dashed', gap: 12, marginBottom: 16,
  },
  scratchIconBox: {
    width: 44, height: 44, borderRadius: 12, backgroundColor: COLORS.primary + '15',
    justifyContent: 'center', alignItems: 'center',
  },
  scratchTitle: { fontSize: 15, fontWeight: '700', color: COLORS.primary },
  scratchDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },

  templateCard: {
    backgroundColor: COLORS.white, borderRadius: 12, padding: 16, marginBottom: 10,
    borderWidth: 1, borderColor: COLORS.border,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.04, shadowRadius: 3, elevation: 1,
  },
  templateHeader: { flexDirection: 'row', gap: 12, marginBottom: 10 },
  templateTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },
  templateDesc: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18 },
  templateFooter: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' },
  typeBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6,
  },
  typeBadgeText: { fontSize: 11, fontWeight: '600' },
  tagChip: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, backgroundColor: COLORS.background },
  tagText: { fontSize: 10, color: COLORS.textMuted },

  emptyTemplates: { alignItems: 'center', paddingVertical: 30 },
  emptyText: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12 },
  emptyHint: { fontSize: 13, color: COLORS.textMuted, marginTop: 4 },

  // Nav buttons
  navRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white,
  },
  navBtnBack: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 12, paddingHorizontal: 16, borderRadius: 12,
    backgroundColor: COLORS.background, borderWidth: 1, borderColor: COLORS.border,
  },
  navBtnBackText: { fontSize: 15, color: COLORS.textSecondary, fontWeight: '500' },
  navBtnNext: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginLeft: 'auto',
    paddingVertical: 12, paddingHorizontal: 24, borderRadius: 12,
    backgroundColor: COLORS.primary,
  },
  navBtnDisabled: { opacity: 0.4 },
  navBtnNextText: { fontSize: 15, color: '#FFF', fontWeight: '700' },

  // Overlay
  overlay: {
    ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(255,255,255,0.85)',
    justifyContent: 'center', alignItems: 'center', zIndex: 100,
  },
  overlayText: { fontSize: 16, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12 },

  seedingText: { fontSize: 14, color: COLORS.textSecondary, marginTop: 12 },
});
