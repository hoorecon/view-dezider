import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, FlatList, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import api from '../../utils/api';
import { useRouter } from 'expo-router';
import InsertFromModulesButton from '../PassableValuePicker';

const TYPE_ICONS: Record<string, string> = {
  PRODUCT: 'cube', SERVICE: 'construct', EVENT: 'calendar',
  PROJECT: 'rocket', PERSON_CONTACT: 'person',
};
const TYPE_COLORS: Record<string, string> = {
  PRODUCT: '#3B82F6', SERVICE: '#10B981', EVENT: '#F59E0B',
  PROJECT: '#8B5CF6', PERSON_CONTACT: '#EC4899',
};

export default function Step6() {
  const router = useRouter();
  const { decision, addOption, addOptionByName, addOptionFromStore, removeOption, newOptionName, setNewOptionName, setCurrentStep, saveDecision, highlightOptionName, setHighlightOptionName } = useDecision();

  // Auto-clear the post-import spotlight after a few seconds.
  useEffect(() => {
    if (!highlightOptionName) return;
    const t = setTimeout(() => setHighlightOptionName(null), 4500);
    return () => clearTimeout(t);
  }, [highlightOptionName, setHighlightOptionName]);


  const [showStoreModal, setShowStoreModal] = useState(false);
  const [storeSolutions, setStoreSolutions] = useState<any[]>([]);
  const [loadingStore, setLoadingStore] = useState(false);

  // Social Learning Templates
  const [showSLModal, setShowSLModal] = useState(false);
  const [slTemplates, setSlTemplates] = useState<any[]>([]);
  const [loadingSL, setLoadingSL] = useState(false);

  const fetchStoreSolutions = async () => {
    setLoadingStore(true);
    try {
      const lifeArea = decision.life_area || '';
      const res = await api.get('/solutions-store/for-decision', {
        params: { life_area_id: lifeArea },
      });
      setStoreSolutions(res.data?.solutions || []);
    } catch (e) {
      console.error('Failed to load solutions store:', e);
      // Try fetching all solutions if life_area filter fails
      try {
        const res = await api.get('/solutions-store/solutions');
        setStoreSolutions(res.data || []);
      } catch {
        setStoreSolutions([]);
      }
    } finally {
      setLoadingStore(false);
    }
  };

  const handleSelectSolution = (sol: any) => {
    addOptionFromStore(sol.name, sol.solution_id);
    setShowStoreModal(false);
  };

  const isAlreadyAdded = (solutionId: string) =>
    decision.options.some(o => o.solution_id === solutionId);

  // Social Learning Templates
  const fetchSLTemplates = async () => {
    setLoadingSL(true);
    try {
      const res = await api.get('/social-learning/templates-for-decision', {
        params: { life_area: decision.life_area || undefined, limit: 20 },
      });
      setSlTemplates(res.data?.templates || []);
    } catch (e) {
      console.error('Failed to load SL templates:', e);
      setSlTemplates([]);
    } finally {
      setLoadingSL(false);
    }
  };

  const handleUseSLTemplate = (t: any) => {
    // Add each suggested option from the template
    const opts = t.options_to_evaluate || [];
    opts.forEach((opt: string) => {
      addOptionByName(opt);
    });
    setShowSLModal(false);
  };

  // ── SWOT-converted single-option mode ───────────────────────────────
  // A decision created via SWOT → Decider conversion represents ONE
  // implicit scenario ("Current Scenario - YYYY-MM-DD HH:MM"). The user
  // shouldn't be adding more options here, just optionally renaming the
  // one we auto-injected. Hide the Solutions Store / Social Learning
  // entry points, the manual-add row, and the delete button. Allow
  // inline rename via a small pencil-edit button so they can label it
  // contextually (e.g., "Q2 2026 baseline").
  const isSwotSourced = (decision as any)?.source_module === 'swot';
  const singleOption = isSwotSourced ? decision.options[0] : null;
  const [renaming, setRenaming] = useState(false);
  const [renameDraft, setRenameDraft] = useState('');
  const startRename = () => {
    if (!singleOption) return;
    setRenameDraft(singleOption.name);
    setRenaming(true);
  };
  const commitRename = () => {
    if (!singleOption) return;
    const trimmed = renameDraft.trim();
    if (!trimmed || trimmed === singleOption.name) { setRenaming(false); return; }
    const updated = decision.options.map((o, i) =>
      i === 0 ? { ...o, name: trimmed } : o
    );
    saveDecision({ options: updated });
    setRenaming(false);
  };

  if (isSwotSourced && singleOption) {
    return (
      <View style={styles.stepContent}>
        <Text style={styles.stepTitle}>Step 6: Current Scenario</Text>
        <Text style={styles.stepDescription}>
          SWOT-converted decisions analyse a single scenario — your current
          state at the moment of conversion. You can rename it for clarity,
          but you can't add multiple options here.
        </Text>

        <Card style={styles.optionCard}>
          <View style={styles.optionHeader}>
            <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <View style={[localStyles.storeBadge, { backgroundColor: '#FEF3C7' }]}>
                <Ionicons name="time" size={10} color="#92400E" />
              </View>
              {renaming ? (
                <TextInput
                  style={[styles.addInput, { flex: 1, marginRight: 8 }]}
                  value={renameDraft}
                  onChangeText={setRenameDraft}
                  onSubmitEditing={commitRename}
                  onBlur={commitRename}
                  autoFocus
                />
              ) : (
                <Text style={styles.optionName}>{singleOption.name}</Text>
              )}
            </View>
            {!renaming && (
              <TouchableOpacity onPress={startRename} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                <Ionicons name="pencil" size={18} color={COLORS.primary} />
              </TouchableOpacity>
            )}
          </View>
        </Card>

        <View style={styles.navButtons}>
          <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(5)}>
            <Ionicons name="arrow-back" size={18} color={COLORS.text} />
            <Text style={styles.backButtonText}>Back</Text>
          </TouchableOpacity>
          <GradientButton title="Next" onPress={() => setCurrentStep(7)} />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 6: Define Options</Text>
      <Text style={styles.stepDescription}>
        List all the options you're considering. You can add manually or pick from the Solutions Store.
      </Text>

      {/* Browse Solutions Store Button */}
      <TouchableOpacity
        style={localStyles.storeButton}
        onPress={() => { setShowStoreModal(true); fetchStoreSolutions(); }}
        activeOpacity={0.7}
      >
        <View style={localStyles.storeIconWrap}>
          <Ionicons name="storefront" size={20} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={localStyles.storeButtonTitle}>Browse Solutions Store</Text>
          <Text style={localStyles.storeButtonSub}>
            Pick from verified products, services, events & more
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.primary} />
      </TouchableOpacity>

      {/* Social Learning Templates Button */}
      <TouchableOpacity
        style={[localStyles.storeButton, { backgroundColor: '#F5F3FF', borderColor: '#DDD6FE' }]}
        onPress={() => { setShowSLModal(true); fetchSLTemplates(); }}
        activeOpacity={0.7}
      >
        <View style={[localStyles.storeIconWrap, { backgroundColor: '#7C3AED' }]}>
          <Ionicons name="newspaper" size={20} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[localStyles.storeButtonTitle, { color: '#7C3AED' }]}>Social Learning Templates</Text>
          <Text style={[localStyles.storeButtonSub, { color: '#8B5CF6' }]}>
            Options from real-world scenarios & news
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color="#7C3AED" />
      </TouchableOpacity>

      {/* Current Options */}
      {decision.options.map((option) => {
        const isStore = !!option.solution_id || option.source === 'store';
        const isTop = !!highlightOptionName && option.name.trim() === highlightOptionName.trim();
        return (
          <Card key={option.id} style={[styles.optionCard, isTop && localStyles.topPickCard]}>
            <View style={styles.optionHeader}>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
                  {isTop ? (
                    <View style={localStyles.topPickBadge}>
                      <Ionicons name="star" size={10} color="#fff" />
                      <Text style={localStyles.topPickBadgeText}>Top pick</Text>
                    </View>
                  ) : null}
                  {isStore ? (
                    <View style={localStyles.srcBadgeStore}>
                      <Ionicons name="storefront" size={10} color="#047857" />
                      <Text style={localStyles.srcBadgeStoreText}>Store</Text>
                    </View>
                  ) : option.source === 'ai' ? (
                    <View style={localStyles.srcBadgeAi}>
                      <Ionicons name="sparkles" size={10} color="#7C3AED" />
                      <Text style={localStyles.srcBadgeAiText}>AI</Text>
                    </View>
                  ) : null}
                  <Text style={styles.optionName}>{option.name}</Text>
                </View>
                {option.sf_ref?.entry_id ? (
                  <TouchableOpacity
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4, alignSelf: 'flex-start', backgroundColor: '#EEF2FF', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 }}
                    onPress={() => router.push({ pathname: '/tools/solution-finder', params: { id: option.sf_ref!.entry_id } } as any)}
                  >
                    <Ionicons name="link" size={11} color="#4F46E5" />
                    <Text style={{ fontSize: 10, fontWeight: '700', color: '#4F46E5' }}>Solution Finder — open action plan</Text>
                  </TouchableOpacity>
                ) : null}
                {/* Store price / rating chips */}
                {(option.price_range || typeof option.rating === 'number') && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 }}>
                    {option.price_range ? (
                      <View style={localStyles.metaChip}>
                        <Ionicons name="pricetag" size={9} color="#0369A1" />
                        <Text style={localStyles.metaChipText}>{option.price_range}</Text>
                      </View>
                    ) : null}
                    {typeof option.rating === 'number' ? (
                      <View style={[localStyles.metaChip, { backgroundColor: '#FEF3C7' }]}>
                        <Ionicons name="star" size={9} color="#B45309" />
                        <Text style={[localStyles.metaChipText, { color: '#92400E' }]}>{option.rating}</Text>
                      </View>
                    ) : null}
                  </View>
                )}
                {/* Auto-scored worth (from prefilled actual values) */}
                {typeof option.worth_percentage === 'number' && option.worth_percentage > 0 && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 }}>
                    <View style={[localStyles.metaChip, { backgroundColor: '#DCFCE7' }]}>
                      <Ionicons name="calculator" size={9} color="#15803D" />
                      <Text style={[localStyles.metaChipText, { color: '#15803D' }]}>
                        Auto worth {option.worth_percentage}%
                      </Text>
                    </View>
                  </View>
                )}
                {/* AI rationale */}
                {option.ai_rationale ? (
                  <Text style={localStyles.rationale}>{option.ai_rationale}</Text>
                ) : null}
                {/* Optional 2-3 line option description — user-editable inline.
                    Shown on Decider Apps / template flows so users can briefly
                    understand each finalist before assessment. */}
                <TextInput
                  style={localStyles.optDescInput}
                  placeholder="Add a short description (optional, 2-3 lines) — e.g., key features, pricing tier, best-fit use case…"
                  placeholderTextColor={COLORS.textMuted}
                  value={(option as any).description || ''}
                  onChangeText={(v) => {
                    const updated = decision.options.map((o) =>
                      o.id === option.id ? { ...o, description: v } : o
                    );
                    saveDecision({ options: updated });
                  }}
                  multiline
                  numberOfLines={2}
                  maxLength={280}
                  testID={`step6-opt-desc-${option.id}`}
                />
              </View>
              <TouchableOpacity onPress={() => removeOption(option.id)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                <Ionicons name="close-circle" size={22} color={COLORS.error} />
              </TouchableOpacity>
            </View>
          </Card>
        );
      })}

      {/* Manual Input */}
      <View style={styles.addFactorRow}>
        <TextInput
          style={styles.addInput}
          placeholder="Add a custom option (e.g., Company A)"
          placeholderTextColor={COLORS.textMuted}
          value={newOptionName}
          onChangeText={setNewOptionName}
          onSubmitEditing={addOption}
        />
        <InsertFromModulesButton
          accept="text"
          title="Insert as Option Name"
          onPick={(it) => {
            if (it.module === 'SOLUTION_FINDER') addOptionByName(it.value, { entry_id: it.ref_id, label: 'Solution Finder' });
            else setNewOptionName(it.value);
          }}
        />
        <TouchableOpacity style={styles.addButton} onPress={addOption}>
          <Ionicons name="add" size={24} color={COLORS.white} />
        </TouchableOpacity>
      </View>

      <View style={styles.navButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(5)}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        <GradientButton
          title="Assess Options"
          onPress={() => {
            if (decision.options.length === 1) {
              // Enhancement #5b — single-option assessment confirmation
              const proceed = (typeof window !== 'undefined' && window.confirm)
                ? window.confirm('Only ONE option added. Proceed with single-option (standalone) assessment? (Like assessing a single matrimonial alliance enquiry without comparing with another.)')
                : true;
              if (!proceed) return;
              saveDecision({ allow_single_option: true } as any);
            }
            setCurrentStep(7);
          }}
          disabled={decision.options.length < 1}
          style={styles.nextButton}
        />
      </View>

      {/* Solutions Store Modal */}
      <Modal visible={showStoreModal} animationType="slide" transparent>
        <View style={localStyles.modalOverlay}>
          <View style={localStyles.modalContent}>
            <View style={localStyles.modalHeader}>
              <View>
                <Text style={localStyles.modalTitle}>Solutions Store</Text>
                <Text style={localStyles.modalSubtitle}>
                  {decision.life_area ? `Filtered by your decision's life area` : 'All solutions'}
                </Text>
              </View>
              <TouchableOpacity onPress={() => setShowStoreModal(false)} style={localStyles.closeBtn}>
                <Ionicons name="close" size={24} color="#333" />
              </TouchableOpacity>
            </View>

            {loadingStore ? (
              <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
            ) : storeSolutions.length === 0 ? (
              <View style={localStyles.emptyState}>
                <Ionicons name="storefront-outline" size={48} color={COLORS.textMuted} />
                <Text style={localStyles.emptyText}>No solutions found for this life area</Text>
                <Text style={localStyles.emptySubtext}>Try adding custom options manually</Text>
              </View>
            ) : (
              <FlatList
                data={storeSolutions}
                keyExtractor={(item) => item.solution_id}
                contentContainerStyle={{ paddingBottom: 20 }}
                renderItem={({ item }) => {
                  const added = isAlreadyAdded(item.solution_id);
                  const typeColor = TYPE_COLORS[item.type] || COLORS.primary;
                  return (
                    <TouchableOpacity
                      style={[localStyles.solCard, added && localStyles.solCardAdded]}
                      onPress={() => !added && handleSelectSolution(item)}
                      disabled={added}
                      activeOpacity={0.7}
                    >
                      <View style={localStyles.solCardTop}>
                        <View style={[localStyles.solTypeBadge, { backgroundColor: typeColor + '18' }]}>
                          <Ionicons name={(TYPE_ICONS[item.type] || 'ellipse') as any} size={14} color={typeColor} />
                          <Text style={[localStyles.solTypeText, { color: typeColor }]}>
                            {item.type === 'PERSON_CONTACT' ? 'Person' : item.type.charAt(0) + item.type.slice(1).toLowerCase()}
                          </Text>
                        </View>
                        {item.is_authorized && (
                          <View style={localStyles.verifiedBadge}>
                            <Ionicons name="shield-checkmark" size={12} color="#10B981" />
                          </View>
                        )}
                        {item.avg_rating && (
                          <View style={localStyles.ratingBadge}>
                            <Ionicons name="star" size={12} color="#F59E0B" />
                            <Text style={localStyles.ratingText}>{item.avg_rating}</Text>
                          </View>
                        )}
                      </View>
                      <Text style={localStyles.solName} numberOfLines={1}>{item.name}</Text>
                      <Text style={localStyles.solDesc} numberOfLines={2}>{item.description}</Text>
                      {item.provider ? (
                        <Text style={localStyles.solProvider}>{item.provider} · {item.price_range || ''}</Text>
                      ) : null}
                      {item.quantitative_factors?.length > 0 && (
                        <View style={localStyles.factorChips}>
                          {item.quantitative_factors.slice(0, 3).map((f: any, i: number) => (
                            <View key={i} style={localStyles.factorChip}>
                              <Text style={localStyles.factorChipText}>{f.factor_name}: {f.value} {f.unit}</Text>
                            </View>
                          ))}
                        </View>
                      )}
                      {added ? (
                        <View style={localStyles.addedBadge}>
                          <Ionicons name="checkmark-circle" size={16} color="#10B981" />
                          <Text style={localStyles.addedText}>Already added</Text>
                        </View>
                      ) : (
                        <View style={localStyles.selectBadge}>
                          <Ionicons name="add-circle" size={16} color={COLORS.primary} />
                          <Text style={localStyles.selectText}>Tap to add as option</Text>
                        </View>
                      )}
                    </TouchableOpacity>
                  );
                }}
              />
            )}
          </View>
        </View>
      </Modal>

      {/* Social Learning Templates Modal */}
      <Modal visible={showSLModal} animationType="slide" transparent>
        <View style={localStyles.modalOverlay}>
          <View style={localStyles.modalContent}>
            <View style={localStyles.modalHeader}>
              <View>
                <Text style={localStyles.modalTitle}>Social Learning Templates</Text>
                <Text style={localStyles.modalSubtitle}>
                  Options from real-world scenarios
                </Text>
              </View>
              <TouchableOpacity onPress={() => setShowSLModal(false)} style={localStyles.closeBtn}>
                <Ionicons name="close" size={24} color="#333" />
              </TouchableOpacity>
            </View>

            {loadingSL ? (
              <ActivityIndicator size="large" color="#7C3AED" style={{ marginTop: 40 }} />
            ) : slTemplates.length === 0 ? (
              <View style={localStyles.emptyState}>
                <Ionicons name="newspaper-outline" size={48} color={COLORS.textMuted} />
                <Text style={localStyles.emptyText}>No social learning templates available</Text>
                <Text style={localStyles.emptySubtext}>Upload news in Social Learning to generate templates</Text>
              </View>
            ) : (
              <FlatList
                data={slTemplates}
                keyExtractor={(item) => item.id}
                contentContainerStyle={{ paddingBottom: 20 }}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    style={[localStyles.solCard, { borderLeftWidth: 3, borderLeftColor: '#7C3AED' }]}
                    onPress={() => handleUseSLTemplate(item)}
                    activeOpacity={0.7}
                  >
                    <View style={localStyles.solCardTop}>
                      <View style={[localStyles.solTypeBadge, { backgroundColor: '#F5F3FF' }]}>
                        <Ionicons name={item.tier === 3 ? 'diamond' : 'shield-checkmark'} size={14} color="#7C3AED" />
                        <Text style={[localStyles.solTypeText, { color: '#7C3AED' }]}>
                          {item.tier === 3 ? 'Premium' : 'Authorized'}
                        </Text>
                      </View>
                      <View style={[localStyles.solTypeBadge, { backgroundColor: item.category === 'problem' ? '#FEF2F2' : item.category === 'need' ? '#FFFBEB' : '#ECFDF5' }]}>
                        <Text style={[localStyles.solTypeText, { color: item.category === 'problem' ? '#EF4444' : item.category === 'need' ? '#D97706' : '#059669' }]}>
                          {item.category}
                        </Text>
                      </View>
                    </View>
                    <Text style={localStyles.solName} numberOfLines={1}>{item.scenario_title || item.title}</Text>
                    <Text style={localStyles.solDesc} numberOfLines={2}>{item.problem_statement}</Text>
                    {(item.options_to_evaluate || []).length > 0 && (
                      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                        {item.options_to_evaluate.map((opt: string, idx: number) => (
                          <View key={idx} style={{ backgroundColor: '#F5F3FF', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 }}>
                            <Text style={{ fontSize: 10, color: '#7C3AED', fontWeight: '500' }}>+ {opt}</Text>
                          </View>
                        ))}
                      </View>
                    )}
                    <View style={localStyles.selectBadge}>
                      <Ionicons name="add-circle" size={16} color="#7C3AED" />
                      <Text style={[localStyles.selectText, { color: '#7C3AED' }]}>Tap to add options from template</Text>
                    </View>
                  </TouchableOpacity>
                )}
              />
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
}

const localStyles = StyleSheet.create({
  topPickCard: {
    borderWidth: 2,
    borderColor: '#F59E0B',
    backgroundColor: '#FFFBEB',
  },
  topPickBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    backgroundColor: '#F59E0B',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  topPickBadgeText: { color: '#fff', fontSize: 10, fontWeight: '800' },
  storeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EEF2FF',
    borderRadius: 14,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#C7D2FE',
    gap: 12,
  },
  storeIconWrap: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  storeButtonTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.primary,
  },
  storeButtonSub: {
    fontSize: 11,
    color: '#6366F1',
    marginTop: 2,
  },
  storeBadge: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#D1FAE5',
    justifyContent: 'center',
    alignItems: 'center',
  },
  srcBadgeStore: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#D1FAE5', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2,
  },
  srcBadgeStoreText: { fontSize: 9, fontWeight: '800', color: '#047857' },
  srcBadgeAi: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#F3E8FF', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2,
  },
  srcBadgeAiText: { fontSize: 9, fontWeight: '800', color: '#7C3AED' },
  metaChip: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    backgroundColor: '#E0F2FE', borderRadius: 8, paddingHorizontal: 6, paddingVertical: 2,
  },
  metaChipText: { fontSize: 9, fontWeight: '700', color: '#0369A1' },
  rationale: { fontSize: 11, color: '#64748B', lineHeight: 16, marginTop: 4, fontStyle: 'italic' },
  optDescInput: {
    marginTop: 8, backgroundColor: '#F8FAFC', borderRadius: 8,
    borderWidth: 1, borderColor: '#E2E8F0',
    paddingHorizontal: 10, paddingVertical: 8,
    fontSize: 12.5, color: '#0F172A', lineHeight: 17,
    minHeight: 44, textAlignVertical: 'top',
  },
  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#F8FAFC',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: 16,
    paddingTop: 16,
    maxHeight: '85%',
    minHeight: '50%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1E293B',
  },
  modalSubtitle: {
    fontSize: 12,
    color: '#64748B',
    marginTop: 2,
  },
  closeBtn: {
    padding: 4,
  },
  emptyState: {
    alignItems: 'center',
    paddingTop: 40,
  },
  emptyText: {
    fontSize: 15,
    color: '#64748B',
    marginTop: 12,
  },
  emptySubtext: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 4,
  },
  // Solution cards
  solCard: {
    backgroundColor: '#FFF',
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  solCardAdded: {
    backgroundColor: '#F0FDF4',
    borderColor: '#86EFAC',
  },
  solCardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  solTypeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    gap: 4,
  },
  solTypeText: {
    fontSize: 10,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  verifiedBadge: {
    padding: 2,
  },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  ratingText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#F59E0B',
  },
  solName: {
    fontSize: 15,
    fontWeight: '700',
    color: '#1E293B',
    marginBottom: 2,
  },
  solDesc: {
    fontSize: 12,
    color: '#64748B',
    lineHeight: 17,
    marginBottom: 4,
  },
  solProvider: {
    fontSize: 11,
    color: '#94A3B8',
    marginBottom: 6,
  },
  factorChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
    marginBottom: 8,
  },
  factorChip: {
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
  },
  factorChipText: {
    fontSize: 10,
    color: '#475569',
  },
  addedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  addedText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#10B981',
  },
  selectBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  selectText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.primary,
  },
});
