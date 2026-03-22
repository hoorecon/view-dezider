import React from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import type { Factor } from '../../types/decision';
import {
  UNIT_PRESETS,
  NUMERIC_OPERATORS,
  TEXT_OPERATORS,
  senseDataType,
} from '../../utils/decisionHelpers';

export default function Step2() {
  const {
    decision, saveDecision, updateFactor, removeFactor, addFactor,
    newFactorName, setNewFactorName,
    expectedInputs, setExpectedInputs,
    newSubFactorName, setNewSubFactorName,
    expandedGroups, setExpandedGroups,
    subWeightInputs, setSubWeightInputs,
    showUnitPicker, setShowUnitPicker,
    customUnitInput, setCustomUnitInput,
    setCurrentStep,
  } = useDecision();

  const handleExpectedValueChange = (factorId: string, value: string) => {
    setExpectedInputs({ ...expectedInputs, [factorId]: value });
  };

  const handleExpectedValueBlur = (factorId: string) => {
    const raw = (expectedInputs[factorId] ?? '').trim();
    if (!raw) {
      updateFactor(factorId, { expected_value: undefined, data_type: undefined, operator: undefined });
      return;
    }
    const detectedType = senseDataType(raw);
    const numericVal = detectedType === 'numeric' ? parseFloat(raw) : undefined;
    const currentOp = decision.factors.find(f => f.id === factorId)?.operator;
    const validOps = detectedType === 'numeric'
      ? NUMERIC_OPERATORS.map(o => o.value)
      : TEXT_OPERATORS.map(o => o.value);
    const newOp = currentOp && validOps.includes(currentOp) ? currentOp : validOps[0];
    updateFactor(factorId, {
      expected_value: numericVal !== undefined ? numericVal : raw,
      data_type: detectedType,
      operator: newOp,
    });
  };

  const getExpectedInput = (factor: Factor): string => {
    if (expectedInputs[factor.id] !== undefined) return expectedInputs[factor.id];
    if (factor.expected_value !== undefined && factor.expected_value !== null) return String(factor.expected_value);
    return '';
  };

  const getDetectedType = (factor: Factor): 'numeric' | 'text' => {
    if (factor.data_type) return factor.data_type;
    const val = expectedInputs[factor.id] ?? (factor.expected_value !== undefined ? String(factor.expected_value) : '');
    return senseDataType(val);
  };

  const addSubFactor = (parentId: string) => {
    const name = (newSubFactorName[parentId] || '').trim();
    if (!name) return;
    const newSub: Factor = {
      id: `sf_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      name,
      category: 'secondary',
      rating: 0,
      order: decision.factors.filter(f => f.parent_id === parentId).length,
      parent_id: parentId,
      weight: 0,
    };
    const updated = [...decision.factors, newSub];
    saveDecision({ factors: updated });
    setNewSubFactorName({ ...newSubFactorName, [parentId]: '' });
    setExpandedGroups({ ...expandedGroups, [parentId]: true });
  };

  const handleWeightBlur = (factorId: string, _parentId: string) => {
    const raw = (subWeightInputs[factorId] || '').trim();
    const val = parseInt(raw) || 0;
    const clamped = Math.min(100, Math.max(0, val));
    updateFactor(factorId, { weight: clamped });
  };

  const topLevelFactors = decision.factors.filter(f => !f.parent_id);
  const getSubFactors = (parentId: string) =>
    decision.factors.filter(f => f.parent_id === parentId).sort((a, b) => a.order - b.order);
  const getSubWeightTotal = (parentId: string) =>
    getSubFactors(parentId).reduce((sum, f) => sum + (f.weight || 0), 0);

  const toggleGroup = (factorId: string) => {
    setExpandedGroups({ ...expandedGroups, [factorId]: !expandedGroups[factorId] });
  };

  const renderCriteria = (factor: Factor, indent: boolean = false) => {
    const detectedType = getDetectedType(factor);
    const operators = detectedType === 'numeric' ? NUMERIC_OPERATORS : TEXT_OPERATORS;
    const hasExpected = factor.expected_value !== undefined && factor.expected_value !== null;

    return (
      <View style={indent ? styles.subFactorCriteria : undefined}>
        <View style={styles.expectedRow}>
          <Text style={styles.expectedLabel}>Expected:</Text>
          <TextInput
            style={styles.expectedInput}
            placeholder="e.g. 20 or Bangalore"
            placeholderTextColor={COLORS.textMuted}
            value={getExpectedInput(factor)}
            onChangeText={(v) => handleExpectedValueChange(factor.id, v)}
            onBlur={() => handleExpectedValueBlur(factor.id)}
          />
          <View style={[styles.dataTypeBadge, detectedType === 'text' ? styles.dataTypeBadgeText : null]}>
            <Text style={styles.dataTypeBadgeLabel}>{detectedType === 'numeric' ? '123' : 'abc'}</Text>
          </View>
        </View>

        {hasExpected && (
          <View style={styles.operatorRow}>
            <Text style={styles.operatorLabel}>Operator:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }}>
              <View style={styles.operatorChipsContainer}>
                {operators.map((op) => (
                  <TouchableOpacity
                    key={op.value}
                    style={[styles.operatorChip, factor.operator === op.value && styles.operatorChipActive]}
                    onPress={() => updateFactor(factor.id, { operator: op.value })}
                  >
                    <Text style={[styles.operatorChipText, factor.operator === op.value && styles.operatorChipTextActive]}>{op.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </ScrollView>
          </View>
        )}

        {detectedType === 'numeric' && (
          <View style={styles.unitSelectorRow}>
            <Text style={styles.unitSelectorLabel}>Unit:</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.unitChipsScroll}>
              <View style={styles.unitChipsContainer}>
                {factor.unit && (
                  <TouchableOpacity style={[styles.unitChip, styles.unitChipClear]} onPress={() => updateFactor(factor.id, { unit: undefined })}>
                    <Ionicons name="close" size={12} color={COLORS.error} />
                  </TouchableOpacity>
                )}
                {UNIT_PRESETS.map((preset) => (
                  <TouchableOpacity key={preset.value} style={[styles.unitChip, factor.unit === preset.value && styles.unitChipActive]} onPress={() => updateFactor(factor.id, { unit: preset.value })}>
                    <Text style={[styles.unitChipText, factor.unit === preset.value && styles.unitChipTextActive]}>{preset.label}</Text>
                  </TouchableOpacity>
                ))}
                <TouchableOpacity style={[styles.unitChip, styles.unitChipCustom, showUnitPicker[factor.id] && styles.unitChipActive]} onPress={() => setShowUnitPicker({ ...showUnitPicker, [factor.id]: !showUnitPicker[factor.id] })}>
                  <Text style={[styles.unitChipText, showUnitPicker[factor.id] && styles.unitChipTextActive]}>✎</Text>
                </TouchableOpacity>
              </View>
            </ScrollView>
          </View>
        )}
        {showUnitPicker[factor.id] && detectedType === 'numeric' && (
          <View style={styles.customUnitRow}>
            <TextInput style={styles.customUnitInput} placeholder="Custom unit (e.g., Km/Liter)" placeholderTextColor={COLORS.textMuted} value={customUnitInput[factor.id] || ''} onChangeText={(v) => setCustomUnitInput({ ...customUnitInput, [factor.id]: v })} onSubmitEditing={() => { const val = (customUnitInput[factor.id] || '').trim(); if (val) { updateFactor(factor.id, { unit: val }); setShowUnitPicker({ ...showUnitPicker, [factor.id]: false }); } }} />
            <TouchableOpacity style={styles.customUnitApplyBtn} onPress={() => { const val = (customUnitInput[factor.id] || '').trim(); if (val) { updateFactor(factor.id, { unit: val }); setShowUnitPicker({ ...showUnitPicker, [factor.id]: false }); } }}>
              <Ionicons name="checkmark" size={18} color={COLORS.white} />
            </TouchableOpacity>
          </View>
        )}
      </View>
    );
  };

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 2: Define Factors & Criteria</Text>
      <Text style={styles.stepDescription}>
        List factors, group them with sub-factors (splitting 100%), then assign expected values, operators, and units.
      </Text>

      {topLevelFactors.map((factor) => {
        const subs = getSubFactors(factor.id);
        const hasChildren = subs.length > 0;
        const isExpanded = expandedGroups[factor.id] !== false;
        const weightTotal = getSubWeightTotal(factor.id);
        const hasExpected = factor.expected_value !== undefined && factor.expected_value !== null;

        return (
          <Card key={factor.id} style={[styles.factorCard, hasChildren && styles.factorCardGroup]}>
            <View style={styles.factorHeader}>
              {hasChildren && (
                <TouchableOpacity onPress={() => toggleGroup(factor.id)} style={styles.expandBtn}>
                  <Ionicons name={isExpanded ? 'chevron-down' : 'chevron-forward'} size={18} color={COLORS.textSecondary} />
                </TouchableOpacity>
              )}
              <Text style={[styles.factorName, { flex: 1 }]}>{factor.name}</Text>
              {hasChildren && (
                <View style={[styles.weightTotalBadge, weightTotal === 100 && styles.weightTotalComplete, weightTotal > 100 && styles.weightTotalOver]}>
                  <Text style={styles.weightTotalText}>{weightTotal}%</Text>
                </View>
              )}
              {hasExpected && !hasChildren && (
                <View style={styles.criteriaPreview}>
                  <Text style={styles.criteriaPreviewText}>
                    {factor.operator || '≥'} {String(factor.expected_value)}{factor.unit ? ` ${factor.unit}` : ''}
                  </Text>
                </View>
              )}
              <TouchableOpacity onPress={() => removeFactor(factor.id)}>
                <Ionicons name="close-circle" size={22} color={COLORS.error} />
              </TouchableOpacity>
            </View>

            {!hasChildren && renderCriteria(factor)}

            {hasChildren && isExpanded && (
              <View style={styles.subFactorsContainer}>
                <View style={styles.weightProgressRow}>
                  <View style={styles.weightProgressBar}>
                    <View style={[
                      styles.weightProgressFill,
                      { width: `${Math.min(100, weightTotal)}%` },
                      weightTotal === 100 && { backgroundColor: '#10B981' },
                      weightTotal > 100 && { backgroundColor: '#EF4444' },
                    ]} />
                  </View>
                  <Text style={[styles.weightProgressText, weightTotal === 100 && { color: '#10B981' }, weightTotal > 100 && { color: '#EF4444' }]}>
                    {weightTotal}/100%
                  </Text>
                </View>

                {subs.map((sub) => {
                  const subHasExpected = sub.expected_value !== undefined && sub.expected_value !== null;
                  return (
                    <View key={sub.id} style={styles.subFactorItem}>
                      <View style={styles.subFactorHeader}>
                        <View style={styles.subFactorDot} />
                        <Text style={styles.subFactorName}>{sub.name}</Text>
                        {subHasExpected && (
                          <View style={[styles.criteriaPreview, { marginRight: 4 }]}>
                            <Text style={styles.criteriaPreviewText}>
                              {sub.operator || '≥'} {String(sub.expected_value)}{sub.unit ? ` ${sub.unit}` : ''}
                            </Text>
                          </View>
                        )}
                        <View style={styles.weightInputWrap}>
                          <TextInput
                            style={styles.weightInput}
                            value={subWeightInputs[sub.id] !== undefined ? subWeightInputs[sub.id] : (sub.weight ? String(sub.weight) : '')}
                            onChangeText={(v) => setSubWeightInputs({ ...subWeightInputs, [sub.id]: v.replace(/[^0-9]/g, '') })}
                            onBlur={() => handleWeightBlur(sub.id, factor.id)}
                            keyboardType="number-pad"
                            placeholder="0"
                            placeholderTextColor={COLORS.textMuted}
                          />
                          <Text style={styles.weightPercent}>%</Text>
                        </View>
                        <TouchableOpacity onPress={() => removeFactor(sub.id)}>
                          <Ionicons name="close-circle" size={18} color={COLORS.error} />
                        </TouchableOpacity>
                      </View>
                      {renderCriteria(sub, true)}
                    </View>
                  );
                })}

                <View style={styles.addSubFactorRow}>
                  <TextInput
                    style={styles.addSubFactorInput}
                    placeholder="Add sub-factor..."
                    placeholderTextColor={COLORS.textMuted}
                    value={newSubFactorName[factor.id] || ''}
                    onChangeText={(v) => setNewSubFactorName({ ...newSubFactorName, [factor.id]: v })}
                    onSubmitEditing={() => addSubFactor(factor.id)}
                  />
                  <TouchableOpacity style={styles.addSubFactorBtn} onPress={() => addSubFactor(factor.id)}>
                    <Ionicons name="add" size={18} color={COLORS.white} />
                  </TouchableOpacity>
                </View>
              </View>
            )}

            {!hasChildren && (
              <TouchableOpacity style={styles.addSubToggle} onPress={() => {
                setExpandedGroups({ ...expandedGroups, [factor.id]: true });
                const firstSub: Factor = {
                  id: `sf_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
                  name: factor.name + ' - Part 1',
                  category: factor.category || 'secondary',
                  rating: 0,
                  order: 0,
                  parent_id: factor.id,
                  weight: 50,
                };
                saveDecision({ factors: [...decision.factors, firstSub] });
              }}>
                <Ionicons name="git-branch-outline" size={14} color={COLORS.primary} />
                <Text style={styles.addSubToggleText}>Split into sub-factors</Text>
              </TouchableOpacity>
            )}
          </Card>
        );
      })}

      <View style={styles.addFactorRow}>
        <TextInput
          style={styles.addInput}
          placeholder="Add a factor (e.g., Cost, Performance, Location)"
          placeholderTextColor={COLORS.textMuted}
          value={newFactorName}
          onChangeText={setNewFactorName}
          onSubmitEditing={addFactor}
        />
        <TouchableOpacity style={styles.addButton} onPress={addFactor}>
          <Ionicons name="add" size={24} color={COLORS.white} />
        </TouchableOpacity>
      </View>

      <GradientButton
        title="Continue to Classification"
        onPress={() => setCurrentStep(3)}
        disabled={topLevelFactors.length < 2}
        style={styles.continueButton}
      />
    </View>
  );
}
