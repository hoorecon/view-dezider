import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, Modal, FlatList, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import api from '../../utils/api';

const TYPE_ICONS: Record<string, string> = {
  PRODUCT: 'cube', SERVICE: 'construct', EVENT: 'calendar',
  PROJECT: 'rocket', PERSON_CONTACT: 'person',
};
const TYPE_COLORS: Record<string, string> = {
  PRODUCT: '#3B82F6', SERVICE: '#10B981', EVENT: '#F59E0B',
  PROJECT: '#8B5CF6', PERSON_CONTACT: '#EC4899',
};

export default function Step6() {
  const { decision, addOption, addOptionFromStore, removeOption, newOptionName, setNewOptionName, setCurrentStep } = useDecision();

  const [showStoreModal, setShowStoreModal] = useState(false);
  const [storeSolutions, setStoreSolutions] = useState<any[]>([]);
  const [loadingStore, setLoadingStore] = useState(false);

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

      {/* Current Options */}
      {decision.options.map((option) => (
        <Card key={option.id} style={styles.optionCard}>
          <View style={styles.optionHeader}>
            <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              {option.solution_id && (
                <View style={localStyles.storeBadge}>
                  <Ionicons name="storefront" size={10} color="#10B981" />
                </View>
              )}
              <Text style={styles.optionName}>{option.name}</Text>
            </View>
            <TouchableOpacity onPress={() => removeOption(option.id)}>
              <Ionicons name="close-circle" size={22} color={COLORS.error} />
            </TouchableOpacity>
          </View>
        </Card>
      ))}

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
          onPress={() => setCurrentStep(7)}
          disabled={decision.options.length < 2}
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
    </View>
  );
}

const localStyles = StyleSheet.create({
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
