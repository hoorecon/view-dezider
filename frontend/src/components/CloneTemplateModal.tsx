import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Modal,
  TextInput,
  ScrollView,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import { showAlert } from '../utils/alert';
import api from '../utils/api';

interface CloneTemplateModalProps {
  visible: boolean;
  onClose: () => void;
  decision: any;
  onCloneSuccess: (newId: string) => void;
  onTemplateSuccess?: () => void;
  /** Current step (1..10) of the parent PRR flow. Used to disable copy
   *  levels the step does not yet support. Step 2 → Factors only;
   *  Step 6 → up to Options; Step 7+ → all levels. Optional — when
   *  omitted, every level is enabled (legacy behaviour). */
  currentStep?: number;
  /** Which tab to open on. Defaults to 'clone'. Set to 'template' from the
   *  MyDezider list-page bookmark icon so the user lands directly on the
   *  Save-as-Template workflow. */
  initialTab?: 'clone' | 'template';
}

// Shared 5-level copy depth — used identically by BOTH the Clone and Template tabs.
// Levels are cumulative (each includes everything above it).
const COPY_LEVELS = [
  {
    key: 'factors',
    label: 'Copy Factors',
    icon: 'list-outline' as const,
    description: 'Factor names only — start fresh with classification',
    color: '#3B82F6',
  },
  {
    key: 'classification',
    label: 'Copy Classification',
    icon: 'git-branch-outline' as const,
    description: 'Factors + Primary/Secondary classification',
    color: '#8B5CF6',
  },
  {
    key: 'prioritization',
    label: 'Copy Prioritization',
    icon: 'bar-chart-outline' as const,
    description: 'Factors + Classification + Ratings',
    // At Step 5 the description dynamically upgrades to note the extra
    // Realistic-Gap adjustment carried over. See renderCopyLevel().
    color: '#EC4899',
  },
  {
    key: 'options',
    label: 'Copy Options',
    icon: 'layers-outline' as const,
    description: 'All above + Option names (no assessments)',
    color: '#F59E0B',
  },
  {
    key: 'assessment',
    label: 'Copy Assessment',
    icon: 'copy-outline' as const,
    description: 'Everything — factors, options & all assessments',
    color: '#10B981',
  },
];

// Which copy levels are meaningful at which step. `factors` = Step 2 minimum;
// `classification` = Step 3; `prioritization` = Step 4/5; `options` = Step 6;
// `assessment` = Step 7 onwards (once option-vs-factor cells are populated).
const COPY_LEVEL_MIN_STEP: Record<string, number> = {
  factors: 2,
  classification: 3,
  prioritization: 4,
  options: 6,
  assessment: 7,
};

// Default standard policies pre-filled when publishing publicly. Editable in
// the modal before Save. Kept short and India-context aware.
const DEFAULT_PRIVACY_POLICY =
  'By publishing this template publicly you agree that any lead-generation contact ' +
  'details you provide (name, email, WhatsApp) may be shown to interested viewers ' +
  'so they can reach out to you. JELCOS AI does not sell or share this data with ' +
  'third parties and stores it only for the purpose of connecting viewers with you.';
const DEFAULT_TERMS_OF_USE =
  'This template is offered as a starting point for decision-making. The publisher ' +
  'is not liable for outcomes of any decision made using this template. Viewers may ' +
  'clone and modify the template for personal use; commercial re-distribution requires ' +
  'written permission from the publisher.';

type Tab = 'clone' | 'template';

// Template names are auto-prefixed by visibility so they are easy to tell apart.
const TEMPLATE_PREFIXES: Record<string, string> = {
  private: '[Private-Template] ',
  shared: '[Shared-Template] ',
  public: '[Public-Template] ',
};
const stripTemplatePrefix = (name: string) =>
  name.replace(/^\s*\[(Private|Shared|Public)-Template\]\s*/i, '');

const VISIBILITY_OPTIONS = [
  {
    key: 'private',
    label: 'Private',
    icon: 'lock-closed-outline' as const,
    description: 'Only visible to you',
    color: COLORS.textSecondary,
  },
  {
    key: 'shared',
    label: 'Shared',
    icon: 'people-outline' as const,
    description: 'Share with specific accounts',
    color: '#3B82F6',
  },
  {
    key: 'public',
    label: 'Public',
    icon: 'globe-outline' as const,
    description: 'Visible to all app users',
    color: '#10B981',
  },
];

export default function CloneTemplateModal({
  visible,
  onClose,
  decision,
  onCloneSuccess,
  onTemplateSuccess,
  currentStep,
  initialTab,
}: CloneTemplateModalProps) {
  const [activeTab, setActiveTab] = useState<Tab>(initialTab || 'clone');
  const [selectedCloneLevel, setSelectedCloneLevel] = useState('prioritization');
  const [selectedTemplateType, setSelectedTemplateType] = useState('options');
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [visibility, setVisibility] = useState('private');
  const [sharedEmails, setSharedEmails] = useState('');

  // Lead-Gen fields (visible only when visibility === 'public') — same schema
  // is used for BOTH Public Decision Templates AND Decider Apps.
  const [leadName, setLeadName] = useState('');
  const [leadOrg, setLeadOrg] = useState('');
  const [leadDesignation, setLeadDesignation] = useState('');
  const [leadEmail, setLeadEmail] = useState('');
  const [leadWhatsapp, setLeadWhatsapp] = useState('');
  const [leadMobile, setLeadMobile] = useState('');
  const [leadRedirectUrl, setLeadRedirectUrl] = useState('');

  // Policy consent (visible only when visibility === 'public').
  const [privacyPolicy, setPrivacyPolicy] = useState(DEFAULT_PRIVACY_POLICY);
  const [termsOfUse, setTermsOfUse] = useState(DEFAULT_TERMS_OF_USE);
  const [policyAgreed, setPolicyAgreed] = useState(false);

  // A flow counts as "Completed" only when the unified status model says so.
  // The Solution Box / API returns `status === 'completed'` (and progress_pct === 100)
  // for flows that have reached their final step AND filled the full assessment.
  const isCompleted = decision?.status === 'completed';

  const getTimestampPrefix = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  };

  const getDefaultTitle = () => {
    if (activeTab === 'clone') {
      return `${getTimestampPrefix()} ${decision?.title || 'Decision'}`;
    }
    return `${getTimestampPrefix()} ${decision?.title || 'Template'}`;
  };

  React.useEffect(() => {
    if (visible) {
      // Respect the caller's preferred starting tab on every open.
      if (initialTab && initialTab !== activeTab) setActiveTab(initialTab);
      setTitle(getDefaultTitle());
      // Prefill lead-gen contact from the current user's profile when Public
      // is selected — user can edit as needed. Uses decision.owner_* fields
      // populated by the backend on /decisions/{id}.
      if (!leadName && decision?.owner_name) setLeadName(decision.owner_name);
      if (!leadEmail && decision?.owner_email) setLeadEmail(decision.owner_email);
      // If a non-completed flow had Public left selected, fall back to Private.
      if (!isCompleted && visibility === 'public') setVisibility('private');
      // If the current step doesn't support the previously-selected copy
      // level, downgrade to the highest one that IS supported.
      if (currentStep) {
        const min = COPY_LEVEL_MIN_STEP[selectedTemplateType] || 2;
        if (currentStep < min) {
          // Find the deepest level allowed at this step.
          const allowed = [...COPY_LEVELS]
            .reverse()
            .find((l) => currentStep >= (COPY_LEVEL_MIN_STEP[l.key] || 2));
          if (allowed) setSelectedTemplateType(allowed.key);
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, activeTab, currentStep]);

  // Convenience — is a given copy level unavailable at the current step?
  const isLevelLocked = (key: string): boolean => {
    if (!currentStep) return false;
    const min = COPY_LEVEL_MIN_STEP[key];
    return typeof min === 'number' && currentStep < min;
  };

  const handleClone = async () => {
    if (!title.trim()) {
      showAlert('Error', 'Please enter a title for the cloned decision');
      return;
    }
    
    setLoading(true);
    try {
      const response = await api.post(`/decisions/${decision.id}/clone`, {
        title: title.trim(),
        clone_level: selectedCloneLevel,
      });
      onCloneSuccess(response.data.id);
      onClose();
      showAlert('Cloned!', `Decision cloned with "${COPY_LEVELS.find(l => l.key === selectedCloneLevel)?.label}"`);
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to clone decision');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveTemplate = async () => {
    if (!title.trim()) {
      showAlert('Error', 'Please enter a name for the template');
      return;
    }
    if (visibility === 'shared' && !sharedEmails.trim()) {
      showAlert('Error', 'Please enter at least one email to share with');
      return;
    }
    if (visibility === 'public' && !isCompleted) {
      showAlert(
        'Completed flows only',
        'Public templates can only be created from a Completed (100%) flow. Save it as Private or Shared, or finish the assessment to publish publicly.'
      );
      return;
    }
    // Lead-Gen + policy validation is required only when publishing publicly.
    if (visibility === 'public') {
      if (!leadName.trim() || !leadEmail.trim() || !leadWhatsapp.trim()) {
        showAlert(
          'Contact details required',
          'Public templates need a contact person name, email and WhatsApp number so interested viewers can reach out to you.'
        );
        return;
      }
      if (!policyAgreed) {
        showAlert('Policies', 'Please agree to the Privacy Policy and Terms of Use before publishing.');
        return;
      }
    }
    // Guard against saving a level the current step cannot back with real data.
    if (currentStep && isLevelLocked(selectedTemplateType)) {
      showAlert(
        'Not available at this step',
        `"${COPY_LEVELS.find((l) => l.key === selectedTemplateType)?.label}" needs data from a later step. Pick a level supported at Step ${currentStep}.`
      );
      return;
    }

    setLoading(true);
    try {
      const shared_with = visibility === 'shared'
        ? sharedEmails.split(',').map(e => e.trim()).filter(e => e)
        : [];

      // Auto-prefix the template name by visibility so templates are easy to tell apart.
      const prefix = TEMPLATE_PREFIXES[visibility] || TEMPLATE_PREFIXES.private;
      const finalName = (prefix + stripTemplatePrefix(title.trim())).trim();

      const payload: any = {
        name: finalName,
        template_type: selectedTemplateType,
        visibility,
        shared_with,
      };
      if (visibility === 'public') {
        payload.lead_gen = {
          contact_name: leadName.trim(),
          organization: leadOrg.trim(),
          designation: leadDesignation.trim(),
          email: leadEmail.trim(),
          whatsapp: leadWhatsapp.trim(),
          mobile: leadMobile.trim(),
          redirect_url: leadRedirectUrl.trim(),
        };
        payload.policies = {
          privacy_policy: privacyPolicy.trim(),
          terms_of_use: termsOfUse.trim(),
          agreed_at: new Date().toISOString(),
        };
      }

      await api.post(`/decisions/${decision.id}/save-as-template`, payload);
      onTemplateSuccess?.();
      onClose();
      const visLabel = visibility === 'public' ? 'publicly' : visibility === 'shared' ? `with ${shared_with.length} account(s)` : 'privately';
      showAlert('Saved!', `Template saved ${visLabel} as "${finalName}"`);
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.headerTitle}>
              {activeTab === 'clone' ? 'Clone Decision' : 'Save as Template'}
            </Text>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
              <Ionicons name="close" size={24} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>

          {/* Tab Switcher */}
          <View style={styles.tabRow}>
            <TouchableOpacity
              style={[styles.tab, activeTab === 'clone' && styles.tabActive]}
              onPress={() => setActiveTab('clone')}
            >
              <Ionicons name="copy-outline" size={18} color={activeTab === 'clone' ? COLORS.primary : COLORS.textMuted} />
              <Text style={[styles.tabText, activeTab === 'clone' && styles.tabTextActive]}>Clone</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tab, activeTab === 'template' && styles.tabActive]}
              onPress={() => setActiveTab('template')}
            >
              <Ionicons name="bookmark-outline" size={18} color={activeTab === 'template' ? COLORS.primary : COLORS.textMuted} />
              <Text style={[styles.tabText, activeTab === 'template' && styles.tabTextActive]}>Template</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Source decision info */}
            <View style={styles.sourceInfo}>
              <Ionicons name="document-text-outline" size={16} color={COLORS.textMuted} />
              <Text style={styles.sourceText} numberOfLines={1}>
                From: {decision?.title}
              </Text>
            </View>

            {/* Title Input */}
            <View style={styles.inputSection}>
              <Text style={styles.inputLabel}>
                {activeTab === 'clone' ? 'New Decision Title' : 'Template Name'}
              </Text>
              <TextInput
                style={styles.input}
                value={title}
                onChangeText={setTitle}
                placeholder={activeTab === 'clone' ? 'Enter decision title...' : 'Enter template name...'}
                placeholderTextColor={COLORS.textMuted}
              />
              {activeTab === 'template' && (
                <Text style={styles.savedAsHint}>
                  Saved as: {TEMPLATE_PREFIXES[visibility]}{stripTemplatePrefix(title.trim()) || '…'}
                </Text>
              )}
            </View>

            {/* Clone Levels / Template Types */}
            {activeTab === 'clone' ? (
              <View style={styles.optionsSection}>
                <Text style={styles.sectionLabel}>What to copy?</Text>
                {COPY_LEVELS.map((level) => (
                  <TouchableOpacity
                    key={level.key}
                    style={[
                      styles.optionCard,
                      selectedCloneLevel === level.key && styles.optionCardSelected,
                      selectedCloneLevel === level.key && { borderColor: level.color },
                    ]}
                    onPress={() => setSelectedCloneLevel(level.key)}
                  >
                    <View style={[styles.optionIcon, { backgroundColor: `${level.color}15` }]}>
                      <Ionicons name={level.icon} size={20} color={level.color} />
                    </View>
                    <View style={styles.optionInfo}>
                      <Text style={styles.optionLabel}>{level.label}</Text>
                      <Text style={styles.optionDesc}>{level.description}</Text>
                    </View>
                    <View style={[
                      styles.radio,
                      selectedCloneLevel === level.key && { borderColor: level.color, backgroundColor: level.color },
                    ]}>
                      {selectedCloneLevel === level.key && (
                        <Ionicons name="checkmark" size={14} color="#FFF" />
                      )}
                    </View>
                  </TouchableOpacity>
                ))}
              </View>
            ) : (
              <View style={styles.optionsSection}>
                <Text style={styles.sectionLabel}>What to copy?</Text>
                {currentStep ? (
                  <Text style={styles.sectionSubLabel}>
                    Some levels are disabled — the data they need is added in later steps. You&apos;re on Step {currentStep}.
                  </Text>
                ) : null}
                {COPY_LEVELS.map((type) => {
                  const locked = isLevelLocked(type.key);
                  const isActive = selectedTemplateType === type.key && !locked;
                  return (
                  <TouchableOpacity
                    key={type.key}
                    activeOpacity={locked ? 1 : 0.7}
                    style={[
                      styles.optionCard,
                      isActive && styles.optionCardSelected,
                      isActive && { borderColor: type.color },
                      locked && styles.optionCardLocked,
                    ]}
                    onPress={() => {
                      if (locked) {
                        showAlert(
                          'Not available at this step',
                          `${type.label} needs data added in Step ${COPY_LEVEL_MIN_STEP[type.key]}. Continue the flow to unlock this option.`
                        );
                        return;
                      }
                      setSelectedTemplateType(type.key);
                    }}
                    testID={`template-copy-${type.key}${locked ? '-locked' : ''}`}
                  >
                    <View style={[styles.optionIcon, { backgroundColor: `${type.color}15` }]}>
                      <Ionicons name={locked ? 'lock-closed-outline' : type.icon} size={20} color={locked ? COLORS.textMuted : type.color} />
                    </View>
                    <View style={styles.optionInfo}>
                      <Text style={[styles.optionLabel, locked && { color: COLORS.textMuted }]}>
                        {type.label}{locked ? ` · Step ${COPY_LEVEL_MIN_STEP[type.key]}+` : ''}
                      </Text>
                      <Text style={styles.optionDesc}>
                        {locked
                          ? `Available after Step ${COPY_LEVEL_MIN_STEP[type.key]}`
                          : (type.key === 'prioritization' && currentStep && currentStep >= 5)
                            ? 'Factors + Classification + Ratings + Realistic-Gap adjustment (from Step 5)'
                            : type.description}
                      </Text>
                      {/* Step 5-specific hint: even if we're technically at
                          Step 4, tell the user *what extra* they'd gain if
                          they wait until Step 5 to save. */}
                      {type.key === 'prioritization' && !locked && currentStep === 4 && (
                        <Text style={[styles.optionDesc, { marginTop: 3, fontStyle: 'italic', color: '#B45309' }]}>
                          Complete Step 5 to also carry the Realistic-Gap adjustment.
                        </Text>
                      )}
                    </View>
                    <View style={[
                      styles.radio,
                      isActive && { borderColor: type.color, backgroundColor: type.color },
                    ]}>
                      {isActive && (
                        <Ionicons name="checkmark" size={14} color="#FFF" />
                      )}
                    </View>
                  </TouchableOpacity>
                  );
                })}

                {/* Visibility Selector */}
                <Text style={[styles.sectionLabel, { marginTop: 16 }]}>Who can see this?</Text>
                {VISIBILITY_OPTIONS.map((opt) => {
                  const locked = opt.key === 'public' && !isCompleted;
                  return (
                  <React.Fragment key={opt.key}>
                    <TouchableOpacity
                      testID={`visibility-${opt.key}`}
                      style={[
                        styles.visibilityOption,
                        visibility === opt.key && styles.visibilityOptionActive,
                        visibility === opt.key && { borderColor: opt.color },
                        locked && styles.visibilityOptionLocked,
                      ]}
                      activeOpacity={locked ? 1 : 0.7}
                      onPress={() => {
                        if (locked) {
                          showAlert(
                            'Completed flows only',
                            'Public templates can only be created from a Completed (100%) flow. Save as Private or Shared instead, or finish the assessment to publish publicly.'
                          );
                          return;
                        }
                        setVisibility(opt.key);
                      }}
                    >
                      <Ionicons name={locked ? 'lock-closed' : opt.icon} size={18} color={visibility === opt.key ? opt.color : COLORS.textMuted} />
                      <View style={styles.visibilityInfo}>
                        <Text style={[styles.visibilityLabel, visibility === opt.key && { color: opt.color }, locked && { color: COLORS.textMuted }]}>
                          {opt.label}{locked ? ' · Completed only' : ''}
                        </Text>
                        <Text style={styles.visibilityDesc}>
                          {locked ? 'Finish the flow (100%) to share publicly' : opt.description}
                        </Text>
                      </View>
                      <View style={[
                        styles.radio,
                        visibility === opt.key && { borderColor: opt.color, backgroundColor: opt.color },
                      ]}>
                        {visibility === opt.key && (
                          <Ionicons name="checkmark" size={14} color="#FFF" />
                        )}
                      </View>
                    </TouchableOpacity>

                    {/* Shared-with emails — rendered inline right below the Shared
                        option (and above Public) so it's immediately visible. */}
                    {opt.key === 'shared' && visibility === 'shared' && (
                      <View style={styles.sharedEmailsSection}>
                        <Text style={styles.sharedEmailsLabel}>Share with (comma-separated emails)</Text>
                        <TextInput
                          style={styles.sharedEmailsInput}
                          value={sharedEmails}
                          onChangeText={setSharedEmails}
                          placeholder="user1@email.com, user2@email.com"
                          placeholderTextColor={COLORS.textMuted}
                          multiline
                          autoCapitalize="none"
                          keyboardType="email-address"
                        />
                      </View>
                    )}

                    {/* Public-only: Lead-Gen contact + Policy consent. Same
                        block is reused for Public Decider Apps (see the Apps
                        publish flow). */}
                    {opt.key === 'public' && visibility === 'public' && (
                      <View style={styles.publicExtras}>
                        <Text style={styles.publicExtrasHead}>Lead-Gen · How interested viewers reach out to you</Text>
                        <TextInput style={styles.leadInput} value={leadName} onChangeText={setLeadName}
                          placeholder="Contact person name *" placeholderTextColor={COLORS.textMuted} />
                        <TextInput style={styles.leadInput} value={leadOrg} onChangeText={setLeadOrg}
                          placeholder="Organization" placeholderTextColor={COLORS.textMuted} />
                        <TextInput style={styles.leadInput} value={leadDesignation} onChangeText={setLeadDesignation}
                          placeholder="Designation" placeholderTextColor={COLORS.textMuted} />
                        <TextInput style={styles.leadInput} value={leadEmail} onChangeText={setLeadEmail}
                          placeholder="Email *" placeholderTextColor={COLORS.textMuted}
                          autoCapitalize="none" keyboardType="email-address" />
                        <TextInput style={styles.leadInput} value={leadWhatsapp} onChangeText={setLeadWhatsapp}
                          placeholder="WhatsApp number *" placeholderTextColor={COLORS.textMuted}
                          keyboardType="phone-pad" />
                        <TextInput style={styles.leadInput} value={leadMobile} onChangeText={setLeadMobile}
                          placeholder="Contact mobile number" placeholderTextColor={COLORS.textMuted}
                          keyboardType="phone-pad" />
                        <TextInput style={styles.leadInput} value={leadRedirectUrl} onChangeText={setLeadRedirectUrl}
                          placeholder="Redirection link (opens in new tab)" placeholderTextColor={COLORS.textMuted}
                          autoCapitalize="none" keyboardType="url" />

                        <Text style={[styles.publicExtrasHead, { marginTop: 12 }]}>Policies · Editable, pre-filled with standard copy</Text>
                        <Text style={styles.policyLabel}>Privacy Policy</Text>
                        <TextInput style={styles.policyInput} value={privacyPolicy} onChangeText={setPrivacyPolicy} multiline />
                        <Text style={[styles.policyLabel, { marginTop: 8 }]}>Terms of Use</Text>
                        <TextInput style={styles.policyInput} value={termsOfUse} onChangeText={setTermsOfUse} multiline />

                        <TouchableOpacity style={styles.consentRow} onPress={() => setPolicyAgreed(!policyAgreed)} testID="template-policy-consent">
                          <Ionicons name={policyAgreed ? 'checkbox' : 'square-outline'} size={20} color={policyAgreed ? COLORS.primary : COLORS.textMuted} />
                          <Text style={styles.consentText}>I agree to the Privacy Policy and Terms of Use above.</Text>
                        </TouchableOpacity>
                      </View>
                    )}
                  </React.Fragment>
                  );
                })}
              </View>
            )}
          </ScrollView>

          {/* Action Button */}
          <View style={styles.footer}>
            <TouchableOpacity
              style={[styles.actionBtn, loading && styles.actionBtnDisabled]}
              onPress={activeTab === 'clone' ? handleClone : handleSaveTemplate}
              disabled={loading}
            >
              {loading ? (
                <ActivityIndicator size="small" color="#FFF" />
              ) : (
                <>
                  <Ionicons
                    name={activeTab === 'clone' ? 'copy' : 'bookmark'}
                    size={20}
                    color="#FFF"
                  />
                  <Text style={styles.actionBtnText}>
                    {activeTab === 'clone' ? 'Clone Decision' : 'Save Template'}
                  </Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  container: {
    backgroundColor: COLORS.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '90%',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 20,
    paddingBottom: 12,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  closeBtn: {
    padding: 4,
  },
  tabRow: {
    flexDirection: 'row',
    marginHorizontal: 20,
    backgroundColor: COLORS.background,
    borderRadius: 12,
    padding: 4,
    marginBottom: 16,
  },
  tab: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  tabActive: {
    backgroundColor: COLORS.white,
    elevation: 2,
    boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.1)',
  },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textMuted,
  },
  tabTextActive: {
    color: COLORS.primary,
  },
  body: {
    paddingHorizontal: 20,
    maxHeight: 450,
  },
  sourceInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: COLORS.background,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    marginBottom: 16,
  },
  sourceText: {
    fontSize: 13,
    color: COLORS.textSecondary,
    flex: 1,
  },
  inputSection: {
    marginBottom: 16,
  },
  inputLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  input: {
    backgroundColor: COLORS.background,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 15,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  savedAsHint: {
    fontSize: 12,
    color: COLORS.primary,
    marginTop: 6,
    fontWeight: '600',
  },
  optionsSection: {
    marginBottom: 16,
  },
  sectionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 4,
  },
  sectionSubLabel: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginBottom: 12,
    fontStyle: 'italic',
  },
  optionCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: COLORS.border,
    marginBottom: 8,
    gap: 12,
  },
  optionCardSelected: {
    backgroundColor: 'rgba(142, 36, 170, 0.04)',
  },
  optionIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
  },
  optionInfo: {
    flex: 1,
  },
  optionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  optionDesc: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  radio: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: COLORS.border,
    justifyContent: 'center',
    alignItems: 'center',
  },
  footer: {
    padding: 20,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.divider,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.primary,
    borderRadius: 14,
    paddingVertical: 14,
    gap: 8,
  },
  actionBtnDisabled: {
    opacity: 0.7,
  },
  actionBtnText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFF',
  },
  visibilityOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    marginBottom: 6,
    gap: 10,
  },
  visibilityOptionActive: {
    backgroundColor: 'rgba(142, 36, 170, 0.04)',
  },
  visibilityOptionLocked: {
    opacity: 0.55,
  },
  visibilityInfo: {
    flex: 1,
  },
  visibilityLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  visibilityDesc: {
    fontSize: 11,
    color: COLORS.textMuted,
    marginTop: 1,
  },
  sharedEmailsSection: {
    marginTop: 12,
  },
  sharedEmailsLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 6,
  },
  sharedEmailsInput: {
    backgroundColor: COLORS.background,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.border,
    minHeight: 60,
    textAlignVertical: 'top',
  },
  optionCardLocked: {
    opacity: 0.5,
    backgroundColor: '#F8FAFC',
  },
  publicExtras: {
    marginTop: 10,
    marginBottom: 6,
    padding: 12,
    backgroundColor: '#F0FDF4',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#BBF7D0',
    gap: 6,
  },
  publicExtrasHead: {
    fontSize: 13,
    fontWeight: '700',
    color: '#065F46',
    marginBottom: 4,
  },
  leadInput: {
    backgroundColor: '#FFF',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 13.5,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: '#BBF7D0',
  },
  policyLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: '#065F46',
  },
  policyInput: {
    backgroundColor: '#FFF',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 12.5,
    color: COLORS.textSecondary,
    borderWidth: 1,
    borderColor: '#BBF7D0',
    minHeight: 60,
    textAlignVertical: 'top',
    lineHeight: 17,
  },
  consentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 10,
    paddingVertical: 6,
  },
  consentText: {
    fontSize: 12.5,
    color: '#065F46',
    fontWeight: '600',
    flex: 1,
  },
});
