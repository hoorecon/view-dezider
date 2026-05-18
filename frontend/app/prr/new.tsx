import React, { useState, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Input } from '../../src/components/Input';
import { GradientButton } from '../../src/components/GradientButton';
import api from '../../src/utils/api';
import TimingFieldset, { TimingValue } from '../../src/components/decisions/TimingFieldset';
import DecisionLinkPicker, { LinkSelection } from '../../src/components/decisions/DecisionLinkPicker';
import LinkedSourcePill from '../../src/components/decisions/LinkedSourcePill';
import { addDaysISO } from '../../src/utils/dateLocalize';

const FOLDERS = [
  { id: 'holistic_health', name: 'Holistic Health', icon: 'fitness', color: '#10B981' },
  { id: 'knowledge_skills', name: 'Knowledge & Skills', icon: 'book', color: '#3B82F6' },
  { id: 'relationships', name: 'Relationships', icon: 'heart', color: '#EC4899' },
  { id: 'finance', name: 'Finance', icon: 'cash', color: '#F59E0B' },
  { id: 'assets', name: 'Assets', icon: 'home', color: '#8B5CF6' },
  { id: 'career', name: 'Career', icon: 'briefcase', color: '#6366F1' },
  { id: 'hobbies_entertainment', name: 'Hobbies & Entertainment', icon: 'game-controller', color: '#14B8A6' },
  { id: 'social_image', name: 'Social Image & Influence', icon: 'star', color: '#F97316' },
  { id: 'social_contributions', name: 'Social Contributions', icon: 'people', color: '#06B6D4' },
  { id: 'spirituality_religion', name: 'Spirituality & Religion', icon: 'leaf', color: '#A855F7' },
];

const DECISION_TYPES = [
  { id: 'problem', name: 'Problem', icon: 'warning', color: '#EF4444', desc: 'Solving a challenge' },
  { id: 'need', name: 'Need', icon: 'flag', color: '#F59E0B', desc: 'Fulfilling a requirement' },
  { id: 'aspiration', name: 'Aspiration', icon: 'rocket', color: '#10B981', desc: 'Pursuing a goal' },
];

interface Template {
  id: string;
  name: string;
  description: string;
  life_area: string;
  decision_type: string;
  factors: any[];
  is_official: boolean;
  submitted_by_name?: string;
}

export default function NewPRRDecision() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [context, setContext] = useState('');
  const [selectedFolder, setSelectedFolder] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [loading, setLoading] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);

  // Enhancement #4 — Timing (default 1 week)
  const [timing, setTiming] = useState<TimingValue>({
    deadline_date: addDaysISO(7),
    impact_horizon_value: 7,
    impact_horizon_unit: 'days',
  });

  // Enhancement #5a — Linked source decision
  const [linkedSource, setLinkedSource] = useState<LinkSelection | null>(null);
  const [showLinkPicker, setShowLinkPicker] = useState(false);

  // Fetch templates when life area or decision type changes
  useEffect(() => {
    if (selectedFolder || selectedType) {
      fetchTemplates();
    } else {
      setTemplates([]);
    }
  }, [selectedFolder, selectedType]);

  const fetchTemplates = async () => {
    setLoadingTemplates(true);
    try {
      const params: any = {};
      // Map folder to life_area
      if (selectedFolder) params.life_area = selectedFolder;
      if (selectedType) params.decision_type = selectedType;
      const query = new URLSearchParams(params).toString();
      const resp = await api.get(`/decision-templates?${query}`);
      setTemplates(resp.data || []);
    } catch (e) {
      setTemplates([]);
    } finally {
      setLoadingTemplates(false);
    }
  };

  const applyTemplate = (template: Template) => {
    setSelectedTemplate(template);
    if (!title.trim()) setTitle(template.name);
    if (!context.trim()) setContext(template.description);
    setShowTemplates(false);
    showAlert(
      'Template Applied',
      `"${template.name}" will pre-load ${template.factors.length} factors with classification, prioritization & ratings when you proceed.`
    );
  };

  const handleCreate = async () => {
    if (!title.trim()) {
      showAlert('Error', 'Please enter a decision title');
      return;
    }
    if (!context.trim()) {
      showAlert('Error', 'Please describe the decision context');
      return;
    }

    setLoading(true);
    try {
      const payload: any = {
        title,
        context,
        folder: selectedFolder,
        life_area: selectedFolder,
        decision_type: selectedType,
        // Timing
        deadline_date: timing.deadline_date,
        impact_horizon_value: timing.impact_horizon_value,
        impact_horizon_unit: timing.impact_horizon_unit,
        // Linking
        linked_from_decision_id: linkedSource?.linked_from_decision_id || null,
        linked_from_module: linkedSource?.linked_from_module || null,
        linked_from_option_label: linkedSource?.linked_from_option_label || null,
        linked_from_score_pct: linkedSource?.linked_from_score_pct ?? null,
      };

      const response = await api.post('/decisions', payload);
      const decisionId = response.data.id;

      // If a template was selected, pre-load its factors
      if (selectedTemplate && selectedTemplate.factors.length > 0) {
        await api.put(`/decisions/${decisionId}`, {
          factors: selectedTemplate.factors,
        });
      }

      router.replace(`/prr/${decisionId}`);
    } catch (error) {
      showAlert('Error', 'Failed to create decision');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.header}>
            <Text style={styles.stepLabel}>Step 1 of 10</Text>
            <Text style={styles.title}>State Context & Options</Text>
            <Text style={styles.description}>
              Select a life area, decision type, and optionally use a template to pre-load factors.
            </Text>
          </View>

          <View style={styles.form}>
            {/* Folder / Life Area Selection */}
            <View style={styles.folderSection}>
              <Text style={styles.folderLabel}>Life Area</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.folderScroll}>
                {FOLDERS.map((folder) => (
                  <TouchableOpacity
                    key={folder.id}
                    style={[
                      styles.folderChip,
                      { borderColor: folder.color + '50' },
                      selectedFolder === folder.id && {
                        borderColor: folder.color,
                        backgroundColor: folder.color + '15',
                      },
                    ]}
                    onPress={() => setSelectedFolder(selectedFolder === folder.id ? '' : folder.id)}
                    activeOpacity={0.7}
                  >
                    <Ionicons
                      name={folder.icon as any}
                      size={14}
                      color={selectedFolder === folder.id ? folder.color : COLORS.textMuted}
                    />
                    <Text
                      style={[
                        styles.folderChipText,
                        selectedFolder === folder.id && { color: folder.color, fontWeight: '600' },
                      ]}
                      numberOfLines={1}
                    >
                      {folder.name}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>

            {/* Decision Type Selection */}
            <View style={styles.folderSection}>
              <Text style={styles.folderLabel}>Decision Type</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {DECISION_TYPES.map((dt) => (
                  <TouchableOpacity
                    key={dt.id}
                    style={[
                      styles.typeChip,
                      { borderColor: dt.color + '50' },
                      selectedType === dt.id && { borderColor: dt.color, backgroundColor: dt.color + '15' },
                    ]}
                    onPress={() => setSelectedType(selectedType === dt.id ? '' : dt.id)}
                  >
                    <Ionicons name={dt.icon as any} size={16} color={selectedType === dt.id ? dt.color : COLORS.textMuted} />
                    <View>
                      <Text style={[styles.typeChipName, selectedType === dt.id && { color: dt.color }]}>{dt.name}</Text>
                      <Text style={styles.typeChipDesc}>{dt.desc}</Text>
                    </View>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* Template Suggestions */}
            {(selectedFolder || selectedType) && (
              <View style={styles.templateSection}>
                <TouchableOpacity
                  style={styles.templateToggle}
                  onPress={() => setShowTemplates(!showTemplates)}
                >
                  <Ionicons name="layers-outline" size={16} color={COLORS.primary} />
                  <Text style={styles.templateToggleText}>
                    {loadingTemplates ? 'Loading templates...' : `Templates (${templates.length})`}
                  </Text>
                  <Ionicons name={showTemplates ? 'chevron-up' : 'chevron-down'} size={16} color={COLORS.textMuted} />
                </TouchableOpacity>

                {showTemplates && (
                  <View style={styles.templateList}>
                    {loadingTemplates && <ActivityIndicator size="small" color={COLORS.primary} />}
                    {!loadingTemplates && templates.length === 0 && (
                      <Text style={{ fontSize: 12, color: COLORS.textMuted, padding: 8 }}>No templates available for this selection.</Text>
                    )}
                    {templates.map((t) => (
                      <TouchableOpacity
                        key={t.id}
                        style={[styles.templateItem, selectedTemplate?.id === t.id && styles.templateItemSelected]}
                        onPress={() => applyTemplate(t)}
                      >
                        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                          {t.is_official && <Ionicons name="shield-checkmark" size={12} color={COLORS.primary} />}
                          <Text style={styles.templateItemName}>{t.name}</Text>
                          <Text style={{ fontSize: 10, color: COLORS.textMuted }}>({t.factors.length} factors)</Text>
                        </View>
                        {t.description ? <Text style={styles.templateItemDesc} numberOfLines={2}>{t.description}</Text> : null}
                        {t.submitted_by_name && !t.is_official && (
                          <Text style={{ fontSize: 10, color: COLORS.textMuted }}>by {t.submitted_by_name}</Text>
                        )}
                      </TouchableOpacity>
                    ))}
                  </View>
                )}

                {selectedTemplate && (
                  <View style={styles.selectedTemplateBadge}>
                    <Ionicons name="checkmark-circle" size={14} color="#16A34A" />
                    <Text style={{ fontSize: 12, color: '#16A34A', fontWeight: '600', flex: 1 }}>
                      Template: {selectedTemplate.name} ({selectedTemplate.factors.length} factors)
                    </Text>
                    <TouchableOpacity onPress={() => setSelectedTemplate(null)}>
                      <Ionicons name="close-circle" size={16} color={COLORS.textMuted} />
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            )}

            <Input
              label="Decision Title"
              placeholder="e.g., Career choice between Company A and B"
              value={title}
              onChangeText={setTitle}
            />

            <Input
              label="Context Description"
              placeholder="Describe the situation, why this decision is important, any constraints..."
              value={context}
              onChangeText={setContext}
              multiline
              numberOfLines={5}
            />

            <View style={styles.tip}>
              <Text style={styles.tipTitle}>Dezider Tip:</Text>
              <Text style={styles.tipText}>
                {selectedTemplate
                  ? `Template "${selectedTemplate.name}" will pre-load factors. You can customize them in Step 2.`
                  : 'Select a template to pre-load factors, or start from scratch.'}
              </Text>
            </View>
          </View>

          {/* Enhancement #4 — Timing fieldset (default 1 week) */}
          <TimingFieldset value={timing} onChange={setTiming} />

          {/* Enhancement #5a — Link from previous decision */}
          {linkedSource ? (
            <LinkedSourcePill
              decision_id={linkedSource.linked_from_decision_id}
              module={linkedSource.linked_from_module}
              option_label={linkedSource.linked_from_option_label}
              score_pct={linkedSource.linked_from_score_pct ?? undefined}
              title={linkedSource.title}
              onRemove={() => setLinkedSource(null)}
            />
          ) : (
            <TouchableOpacity
              style={styles.linkBtn}
              onPress={() => setShowLinkPicker(true)}
              testID="prr-link-from-prev"
            >
              <Ionicons name="link-outline" size={14} color={COLORS.primary} />
              <Text style={styles.linkBtnText}>Link from previous decision (optional)</Text>
            </TouchableOpacity>
          )}

          <GradientButton
            title={selectedTemplate ? 'Create with Template' : 'Create & Continue'}
            onPress={handleCreate}
            loading={loading}
            style={styles.button}
          />

          <DecisionLinkPicker
            visible={showLinkPicker}
            onClose={() => setShowLinkPicker(false)}
            onSelect={(sel) => setLinkedSource(sel)}
          />

          {/* Save as Template button for returning users */}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  keyboardView: { flex: 1 },
  scrollContent: { padding: 16 },
  linkBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 10, paddingHorizontal: 12, borderRadius: 8, borderWidth: 1, borderColor: COLORS.primary, borderStyle: 'dashed', justifyContent: 'center', marginBottom: 8 },
  linkBtnText: { fontSize: 12, fontWeight: '600', color: COLORS.primary },
  header: { marginBottom: 24 },
  stepLabel: { fontSize: 14, fontWeight: '600', color: COLORS.primary, marginBottom: 8 },
  title: { fontSize: 24, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  description: { fontSize: 14, color: COLORS.textSecondary, lineHeight: 20 },
  form: { marginBottom: 24 },
  folderSection: { marginBottom: 16 },
  folderLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 8 },
  folderScroll: { flexGrow: 0 },
  folderChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 7,
    borderRadius: 16, borderWidth: 1.5, borderColor: COLORS.border,
    marginRight: 7, backgroundColor: COLORS.white,
  },
  folderChipText: { fontSize: 12, color: COLORS.textSecondary },
  typeChip: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 10,
    borderRadius: 12, borderWidth: 1.5, borderColor: COLORS.border,
    backgroundColor: COLORS.white,
  },
  typeChipName: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  typeChipDesc: { fontSize: 10, color: COLORS.textMuted },
  templateSection: { marginBottom: 12 },
  templateToggle: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 8, paddingHorizontal: 12,
    backgroundColor: '#EDE9FE', borderRadius: 10,
  },
  templateToggleText: { flex: 1, fontSize: 13, fontWeight: '600', color: COLORS.primary },
  templateList: {
    backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    marginTop: 6, maxHeight: 200, padding: 4,
  },
  templateItem: {
    padding: 10, borderRadius: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  templateItemSelected: { backgroundColor: '#F0FDF4', borderColor: '#16A34A' },
  templateItemName: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  templateItemDesc: { fontSize: 11, color: COLORS.textSecondary, marginTop: 2 },
  selectedTemplateBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 6,
    backgroundColor: '#F0FDF4', borderRadius: 8, borderWidth: 1, borderColor: '#16A34A',
    marginTop: 6,
  },
  tip: {
    backgroundColor: 'rgba(142,36,170,0.08)', borderRadius: 12, padding: 16, marginTop: 8,
  },
  tipTitle: { fontSize: 14, fontWeight: '600', color: COLORS.primary, marginBottom: 4 },
  tipText: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18 },
  button: { marginBottom: 32 },
});
