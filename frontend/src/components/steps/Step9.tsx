import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { useRouter } from 'expo-router';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import { TEPFI_ELEMENTS, TEPFI_LAYERS } from '../../utils/decisionHelpers';
import type { Factor, MPPSImprovement, MPPSActionItem } from '../../types/decision';

export default function Step9() {
  const { decision, saveDecision, calculateDynamicWorth, setCurrentStep } = useDecision();
  const router = useRouter();

  const topLevelFactors = decision.factors.filter(f => !f.parent_id);
  const mppsTimeframe = decision.mpps_timeframe || '';
  const mppsByOption = decision.mpps_by_option || {};
  // Phase 4: MPPS can be applied to ANY option (not just the best one).
  const [selectedMppsOptionId, setSelectedMppsOptionId] = useState<string>(decision.mpps_option_id || '');

  const optionsWithDynamicWorth = decision.options.map(option => ({
    ...option,
    dynamic_worth: calculateDynamicWorth(option).worth,
  }));
  const sortedOptions = [...optionsWithDynamicWorth].sort((a, b) => b.dynamic_worth - a.dynamic_worth);
  const bestOption = sortedOptions[0];

  if (!bestOption) {
    return (
      <View style={styles.stepContent}>
        <Text style={styles.stepTitle}>Step 9: MPPS Analysis</Text>
        <Text style={styles.stepDescription}>No options available.</Text>
      </View>
    );
  }

  const mppsOptionId = selectedMppsOptionId || decision.mpps_option_id || bestOption.id;
  const targetOption = decision.options.find(o => o.id === mppsOptionId) || bestOption;
  // Improvements for the currently-selected option (legacy single-option store as fallback).
  const improvements: MPPSImprovement[] = mppsByOption[mppsOptionId]
    || (mppsOptionId === decision.mpps_option_id ? (decision.mpps_improvements || []) : []);
  const targetWorth = calculateDynamicWorth(targetOption).worth;

  const getFactorAssessmentPctLocal = (factor: Factor): number | null => {
    const subs = decision.factors.filter(f => f.parent_id === factor.id);
    if (subs.length === 0) {
      const a = targetOption.assessments.find(a => a.factor_id === factor.id);
      return a?.percentage ?? null;
    }
    let wSum = 0; let wTotal = 0; let anyAssessed = false;
    for (const sub of subs) {
      const sa = targetOption.assessments.find(a => a.factor_id === sub.id);
      const sw = sub.weight || 0;
      if (sa?.percentage !== undefined && sa?.percentage !== null && sw > 0) {
        wSum += (sa.percentage * sw) / 100; wTotal += sw; anyAssessed = true;
      }
    }
    if (!anyAssessed || wTotal === 0) return null;
    return Math.round(wSum * (100 / wTotal) * 10) / 10;
  };

  const calculateMPPSWorth = (): number => {
    const totalRating = topLevelFactors.reduce((sum, f) => sum + f.rating, 0);
    if (totalRating === 0) return 0;
    let weightedSum = 0;
    for (const factor of topLevelFactors) {
      const imp = improvements.find(i => i.factor_id === factor.id);
      const currentPct = getFactorAssessmentPctLocal(factor);
      const effectivePct = imp?.projected_percentage ?? currentPct ?? 0;
      const clamped = Math.min(100, Math.max(0, effectivePct));
      weightedSum += factor.rating * (clamped / 100);
    }
    const rawWorth = (weightedSum / totalRating) * 100;
    return Math.round(Math.min(100, Math.max(0, rawWorth)) * 10) / 10;
  };

  const mppsWorth = calculateMPPSWorth();
  const improvementDelta = mppsWorth - targetWorth;

  const updateImprovement = (factorId: string, updates: Partial<MPPSImprovement>) => {
    const existing = [...improvements];
    const idx = existing.findIndex(i => i.factor_id === factorId);
    const currentPct = getFactorAssessmentPctLocal(topLevelFactors.find(f => f.id === factorId)!);
    if (idx >= 0) {
      const merged = { ...existing[idx], ...updates };
      if (merged.projected_percentage !== undefined && merged.projected_percentage !== null) {
        merged.delta_percentage = (merged.projected_percentage) - (merged.original_percentage ?? currentPct ?? 0);
      }
      existing[idx] = merged;
    } else {
      const newImp: MPPSImprovement = {
        factor_id: factorId,
        original_percentage: currentPct ?? undefined,
        projected_percentage: updates.projected_percentage,
        delta_percentage: updates.projected_percentage !== undefined ? (updates.projected_percentage - (currentPct ?? 0)) : undefined,
        expected_value: updates.expected_value,
        expected_unit: updates.expected_unit,
        improvement_plan: updates.improvement_plan || '',
        tepfi_elements: updates.tepfi_elements || [],
        tepfi_layer: updates.tepfi_layer,
        action_items: updates.action_items || [],
      };
      existing.push(newImp);
    }
    saveDecision({
      mpps_option_id: mppsOptionId,
      mpps_improvements: existing,
      mpps_by_option: { ...mppsByOption, [mppsOptionId]: existing },
    });
  };

  const addActionItem = (factorId: string) => {
    const imp = improvements.find(i => i.factor_id === factorId);
    const items = [...(imp?.action_items || []), { assignee_name: '', assignee_email: '', assignee_mobile: '', task: '', deadline: '' }];
    updateImprovement(factorId, { action_items: items });
  };

  const updateActionItem = (factorId: string, itemIdx: number, updates: Partial<MPPSActionItem>) => {
    const imp = improvements.find(i => i.factor_id === factorId);
    const items = [...(imp?.action_items || [])];
    items[itemIdx] = { ...items[itemIdx], ...updates };
    updateImprovement(factorId, { action_items: items });
  };

  const removeActionItem = (factorId: string, itemIdx: number) => {
    const imp = improvements.find(i => i.factor_id === factorId);
    const items = [...(imp?.action_items || [])];
    items.splice(itemIdx, 1);
    updateImprovement(factorId, { action_items: items });
  };

  const toggleTEPFI = (factorId: string, element: string) => {
    const imp = improvements.find(i => i.factor_id === factorId);
    const elements = [...(imp?.tepfi_elements || [])];
    const idx = elements.indexOf(element);
    if (idx >= 0) elements.splice(idx, 1);
    else elements.push(element);
    updateImprovement(factorId, { tepfi_elements: elements });
  };

  const saveMPPSWorth = () => {
    saveDecision({
      mpps_option_id: mppsOptionId,
      mpps_improvements: improvements,
      mpps_projected_worth: mppsWorth,
      mpps_timeframe: mppsTimeframe,
      mpps_by_option: { ...mppsByOption, [mppsOptionId]: improvements },
    });
  };

  const downloadActionPlan = async () => {
    try {
      const token = await AsyncStorage.getItem('session_token');
      const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
      const url = `${baseUrl}/api/decisions/${decision.id}/mpps-action-plan`;
      if (typeof window !== 'undefined') {
        const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        const blob = await response.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = `MPPS_Action_Plan.csv`;
        a.click();
        URL.revokeObjectURL(blobUrl);
      }
      Alert.alert('Success', 'Action plan downloaded');
    } catch (err) {
      Alert.alert('Error', 'Failed to download action plan');
    }
  };

  // Wave 2 (#10) — MPPS reorder by Step-4 priority + Primary/Secondary
  // grouping. Step 4 classifies each factor as `primary` (mandatory) or
  // `secondary` (nice-to-have) and Step 5 turns that into a per-factor
  // `rating` (higher = more important). The MPPS plan should therefore
  // tackle the HIGHEST-priority factors first, grouped by category — not
  // just weakest cells indiscriminately. Within each priority tier we
  // keep weakest-first so the easiest wins stay at the top of each group.
  const sortedFactors = (() => {
    const cmp = (a: Factor, b: Factor) => {
      const ar = a.rating ?? 0;
      const br = b.rating ?? 0;
      if (ar !== br) return br - ar; // higher rating first
      const aPct = getFactorAssessmentPctLocal(a) ?? 0;
      const bPct = getFactorAssessmentPctLocal(b) ?? 0;
      return aPct - bPct; // weakest first within same priority tier
    };
    const primary = topLevelFactors.filter(f => f.category === 'primary').sort(cmp);
    const secondary = topLevelFactors.filter(f => f.category !== 'primary').sort(cmp);
    return [...primary, ...secondary];
  })();
  const primaryCount = sortedFactors.filter(f => f.category === 'primary').length;
  const secondaryCount = sortedFactors.length - primaryCount;

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 9: MPPS Analysis</Text>
      <Text style={styles.stepDescription}>
        Max Possible Practical Solution — improve weak factors of any option within a defined
        timeframe. A lower-ranked option can become #1 after improvements.
      </Text>

      {/* Phase 4: choose ANY option to run MPPS on */}
      <Text style={{ fontSize: 12, color: COLORS.textMuted, marginBottom: 6 }}>
        Select an option to improve:
      </Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        {sortedOptions.map((o, idx) => {
          const selected = o.id === mppsOptionId;
          return (
            <TouchableOpacity
              key={o.id}
              onPress={() => setSelectedMppsOptionId(o.id)}
              style={{
                paddingVertical: 8, paddingHorizontal: 12, borderRadius: 10, borderWidth: 1.5,
                borderColor: selected ? COLORS.primary : COLORS.border,
                backgroundColor: selected ? COLORS.primary + '15' : COLORS.white,
              }}
            >
              <Text style={{ fontSize: 13, fontWeight: '700', color: selected ? COLORS.primary : COLORS.textPrimary }}>
                #{idx + 1} {o.name}
              </Text>
              <Text style={{ fontSize: 11, color: COLORS.textMuted }}>
                Worth {o.dynamic_worth.toFixed(1)}%
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Option + Timeframe header */}
      <Card style={[styles.factorCard, { borderLeftWidth: 3, borderLeftColor: COLORS.primary }]}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Analyzing</Text>
            <Text style={{ fontSize: 16, fontWeight: '700', color: COLORS.textPrimary }}>{targetOption.name}</Text>
          </View>
          <View style={{ alignItems: 'center' }}>
            <Text style={{ fontSize: 11, color: COLORS.textMuted }}>Current Worth</Text>
            <Text style={{ fontSize: 22, fontWeight: '800', color: COLORS.primary }}>{targetWorth.toFixed(1)}%</Text>
          </View>
        </View>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <Ionicons name="calendar-outline" size={16} color={COLORS.textMuted} />
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Timeframe:</Text>
          <TextInput
            style={{
              flex: 1, height: 34, borderWidth: 1, borderColor: COLORS.border,
              borderRadius: 8, paddingHorizontal: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white,
            }}
            value={mppsTimeframe}
            onChangeText={(text) => saveDecision({ mpps_timeframe: text })}
            placeholder="e.g., 3 months, 6 weeks..."
            placeholderTextColor={COLORS.textMuted}
          />
        </View>
      </Card>

      {/* MPPS Projection Summary */}
      <Card style={[styles.factorCard, { backgroundColor: improvementDelta > 0 ? '#F0FDF4' : '#FAFAFA' }]}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <View>
            <Text style={{ fontSize: 12, color: COLORS.textMuted }}>MPPS Projected Worth</Text>
            <Text style={{ fontSize: 24, fontWeight: '800', color: improvementDelta > 0 ? '#16A34A' : COLORS.textPrimary }}>{mppsWorth.toFixed(1)}%</Text>
          </View>
          {improvementDelta > 0 && (
            <View style={{ backgroundColor: '#DCFCE7', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 }}>
              <Text style={{ fontSize: 14, fontWeight: '700', color: '#16A34A' }}>+{improvementDelta.toFixed(1)}%</Text>
            </View>
          )}
          <View style={{ alignItems: 'center' }}>
            <Text style={{ fontSize: 11, color: COLORS.textMuted }}>Type</Text>
            <Text style={{ fontSize: 13, fontWeight: '600', color: mppsWorth >= 100 ? '#16A34A' : mppsWorth >= 50 ? COLORS.primary : '#EF4444' }}>
              {mppsWorth >= 100 ? 'Ideal' : mppsWorth >= 50 ? 'Practical' : 'Unavoidable'}
            </Text>
          </View>
        </View>
      </Card>

      {/* Factor Improvement Plans Header + AI Button */}
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, marginBottom: 4 }}>
        <Text style={{ fontSize: 14, fontWeight: '700', color: COLORS.textPrimary }}>Factor Improvement Plans</Text>
        <TouchableOpacity
          onPress={async () => {
            try {
              const token = await AsyncStorage.getItem('session_token');
              const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
              const resp = await fetch(`${baseUrl}/api/tepfi-auto-map`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                body: JSON.stringify({
                  title: decision.title,
                  context: decision.context,
                  factors: topLevelFactors.map(f => ({ name: f.name, category: f.category, unit: f.unit })),
                }),
              });
              const data = await resp.json();
              if (data.mappings && data.mappings.length > 0) {
                const existing = [...improvements];
                for (const m of data.mappings) {
                  const factor = topLevelFactors.find(f => f.name === m.factor_name);
                  if (!factor) continue;
                  const idx = existing.findIndex(i => i.factor_id === factor.id);
                  const currentPct = getFactorAssessmentPctLocal(factor);
                  if (idx >= 0) {
                    existing[idx] = { ...existing[idx], tepfi_elements: m.tepfi_elements || [], tepfi_layer: m.tepfi_layer };
                  } else {
                    existing.push({ factor_id: factor.id, original_percentage: currentPct ?? undefined, improvement_plan: '', tepfi_elements: m.tepfi_elements || [], tepfi_layer: m.tepfi_layer, action_items: [] });
                  }
                }
                saveDecision({ mpps_option_id: mppsOptionId, mpps_improvements: existing });
                Alert.alert('AI Mapped', 'TEPFI elements auto-mapped. You can override manually.');
              }
            } catch (err) {
              Alert.alert('Error', 'AI mapping failed. Try again.');
            }
          }}
          style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#EDE9FE', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12 }}
        >
          <Ionicons name="sparkles" size={14} color={COLORS.primary} />
          <Text style={{ fontSize: 12, fontWeight: '600', color: COLORS.primary }}>AI Auto-Map TEPFI</Text>
        </TouchableOpacity>
      </View>

      {sortedFactors.map((factor, idx) => {
        // Wave 2 (#10) — Section header when entering Primary or Secondary block.
        const isFirstInGroup =
          idx === 0 ||
          (sortedFactors[idx - 1].category === 'primary' && factor.category !== 'primary');
        const sectionLabel = factor.category === 'primary'
          ? `Primary factors (${primaryCount}) — mandatory, tackle these first`
          : `Secondary factors (${secondaryCount}) — nice-to-have, optional`;
        const currentPct = getFactorAssessmentPctLocal(factor);
        const imp = improvements.find(i => i.factor_id === factor.id);
        const projPct = imp?.projected_percentage;
        const deltaPct = imp?.delta_percentage;
        const pctColor = (currentPct ?? 0) < 40 ? '#EF4444' : (currentPct ?? 0) < 70 ? '#F59E0B' : '#10B981';
        const actionItems = imp?.action_items || [];

        const factorCard = (
          <Card key={factor.id} style={[styles.factorCard, imp?.improvement_plan ? { borderLeftWidth: 3, borderLeftColor: '#16A34A' } : {}]}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>{factor.name}</Text>
                <Text style={{ fontSize: 11, color: COLORS.textMuted }}>Rating: {factor.rating} · {factor.category}</Text>
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <View style={{ alignItems: 'center' }}>
                  <Text style={{ fontSize: 10, color: COLORS.textMuted }}>Now</Text>
                  <Text style={{ fontSize: 16, fontWeight: '700', color: pctColor }}>{currentPct !== null ? `${currentPct}%` : '--'}</Text>
                </View>
                {projPct !== undefined && projPct !== null && (
                  <>
                    <Ionicons name="arrow-forward" size={14} color={COLORS.textMuted} />
                    <View style={{ alignItems: 'center' }}>
                      <Text style={{ fontSize: 10, color: '#16A34A' }}>Target</Text>
                      <Text style={{ fontSize: 16, fontWeight: '700', color: '#16A34A' }}>{projPct}%</Text>
                    </View>
                    {deltaPct !== undefined && deltaPct > 0 && (
                      <View style={{ backgroundColor: '#DCFCE7', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 8 }}>
                        <Text style={{ fontSize: 11, fontWeight: '700', color: '#16A34A' }}>+{deltaPct}%</Text>
                      </View>
                    )}
                  </>
                )}
              </View>
            </View>

            <View style={{ flexDirection: 'row', gap: 8, marginBottom: 6 }}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 11, color: COLORS.textMuted, marginBottom: 2 }}>Projected %</Text>
                <TextInput
                  style={{ height: 34, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 8, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white }}
                  value={projPct !== undefined && projPct !== null ? String(projPct) : ''}
                  onChangeText={(text) => {
                    const num = parseInt(text);
                    if (text === '') updateImprovement(factor.id, { projected_percentage: undefined });
                    else if (!isNaN(num) && num >= 0 && num <= 100) updateImprovement(factor.id, { projected_percentage: num });
                  }}
                  keyboardType="numeric" maxLength={3}
                  placeholder={currentPct !== null ? String(currentPct) : '0'}
                  placeholderTextColor={COLORS.textMuted}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 11, color: COLORS.textMuted, marginBottom: 2 }}>Target Value</Text>
                <TextInput
                  style={{ height: 34, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 8, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white }}
                  value={imp?.expected_value || ''}
                  onChangeText={(text) => updateImprovement(factor.id, { expected_value: text })}
                  placeholder="e.g., 120000"
                  placeholderTextColor={COLORS.textMuted}
                />
              </View>
              <View style={{ width: 70 }}>
                <Text style={{ fontSize: 11, color: COLORS.textMuted, marginBottom: 2 }}>Unit</Text>
                <TextInput
                  style={{ height: 34, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 6, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white }}
                  value={imp?.expected_unit || factor.unit || ''}
                  onChangeText={(text) => updateImprovement(factor.id, { expected_unit: text })}
                  placeholder={factor.unit || 'unit'}
                  placeholderTextColor={COLORS.textMuted}
                />
              </View>
            </View>

            <TextInput
              style={{ borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, fontSize: 12, color: COLORS.textPrimary, backgroundColor: COLORS.white, minHeight: 38, textAlignVertical: 'top', marginBottom: 6 }}
              value={imp?.improvement_plan || ''}
              onChangeText={(text) => updateImprovement(factor.id, { improvement_plan: text })}
              placeholder="How to achieve this improvement?"
              placeholderTextColor={COLORS.textMuted}
              multiline
            />

            <View style={{ marginBottom: 4 }}>
              <Text style={{ fontSize: 11, color: COLORS.textMuted, marginBottom: 3 }}>TEPFI Elements</Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
                {TEPFI_ELEMENTS.map((te) => {
                  const isActive = (imp?.tepfi_elements || []).includes(te.key);
                  return (
                    <TouchableOpacity key={te.key} onPress={() => toggleTEPFI(factor.id, te.key)}
                      style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12, borderWidth: 1.5, borderColor: isActive ? te.color : COLORS.border, backgroundColor: isActive ? te.color + '18' : 'transparent' }}
                    >
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
                        <Ionicons name={te.icon as any} size={11} color={isActive ? te.color : COLORS.textMuted} />
                        <Text style={{ fontSize: 11, fontWeight: '600', color: isActive ? te.color : COLORS.textMuted }}>{te.label}</Text>
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>

            <View style={{ flexDirection: 'row', gap: 4, marginBottom: 8 }}>
              <Text style={{ fontSize: 11, color: COLORS.textMuted, marginRight: 4, alignSelf: 'center' }}>Layer:</Text>
              {TEPFI_LAYERS.map((tl) => (
                <TouchableOpacity key={tl.key} onPress={() => updateImprovement(factor.id, { tepfi_layer: imp?.tepfi_layer === tl.key ? undefined : tl.key })}
                  style={{ paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12, borderWidth: 1.5, borderColor: imp?.tepfi_layer === tl.key ? tl.color : COLORS.border, backgroundColor: imp?.tepfi_layer === tl.key ? tl.color + '18' : 'transparent' }}
                >
                  <Text style={{ fontSize: 11, fontWeight: '600', color: imp?.tepfi_layer === tl.key ? tl.color : COLORS.textMuted }}>{tl.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <View style={{ borderTopWidth: 1, borderTopColor: COLORS.border, paddingTop: 6 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <Text style={{ fontSize: 12, fontWeight: '600', color: COLORS.textPrimary }}>Action Items</Text>
                <TouchableOpacity onPress={() => addActionItem(factor.id)} style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
                  <Ionicons name="add-circle-outline" size={16} color={COLORS.primary} />
                  <Text style={{ fontSize: 11, color: COLORS.primary, fontWeight: '600' }}>Add</Text>
                </TouchableOpacity>
              </View>

              {actionItems.map((ai, aiIdx) => (
                <View key={aiIdx} style={{ backgroundColor: '#F8FAFC', borderRadius: 8, padding: 8, marginBottom: 6 }}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <Text style={{ fontSize: 11, fontWeight: '600', color: COLORS.textMuted }}>#{aiIdx + 1}</Text>
                    <TouchableOpacity onPress={() => removeActionItem(factor.id, aiIdx)}>
                      <Ionicons name="close-circle" size={16} color="#EF4444" />
                    </TouchableOpacity>
                  </View>
                  <TextInput
                    style={{ height: 32, borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 8, fontSize: 12, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginBottom: 4 }}
                    value={ai.task}
                    onChangeText={(t) => updateActionItem(factor.id, aiIdx, { task: t })}
                    placeholder="Does What?"
                    placeholderTextColor={COLORS.textMuted}
                  />
                  <View style={{ flexDirection: 'row', gap: 4, marginBottom: 4 }}>
                    <TextInput
                      style={{ flex: 1, height: 32, borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 6, fontSize: 11, color: COLORS.textPrimary, backgroundColor: COLORS.white }}
                      value={ai.assignee_name}
                      onChangeText={(t) => updateActionItem(factor.id, aiIdx, { assignee_name: t })}
                      placeholder="Who? (Name)"
                      placeholderTextColor={COLORS.textMuted}
                    />
                    <TextInput
                      style={{ flex: 1, height: 32, borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 6, fontSize: 11, color: COLORS.textPrimary, backgroundColor: COLORS.white }}
                      value={ai.assignee_email}
                      onChangeText={(t) => updateActionItem(factor.id, aiIdx, { assignee_email: t })}
                      placeholder="Email"
                      placeholderTextColor={COLORS.textMuted}
                      keyboardType="email-address"
                    />
                  </View>
                  <View style={{ flexDirection: 'row', gap: 4 }}>
                    <TextInput
                      style={{ flex: 1, height: 32, borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 6, fontSize: 11, color: COLORS.textPrimary, backgroundColor: COLORS.white }}
                      value={ai.assignee_mobile}
                      onChangeText={(t) => updateActionItem(factor.id, aiIdx, { assignee_mobile: t })}
                      placeholder="Mobile"
                      placeholderTextColor={COLORS.textMuted}
                      keyboardType="phone-pad"
                    />
                    <TextInput
                      style={{ flex: 1, height: 32, borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 6, fontSize: 11, color: COLORS.textPrimary, backgroundColor: COLORS.white }}
                      value={ai.deadline || ''}
                      onChangeText={(t) => updateActionItem(factor.id, aiIdx, { deadline: t })}
                      placeholder="By When?"
                      placeholderTextColor={COLORS.textMuted}
                    />
                  </View>
                </View>
              ))}
            </View>
          </Card>
        );
        if (isFirstInGroup) {
          return (
            <React.Fragment key={`grp-${factor.id}`}>
              <View
                testID={`step9-section-${factor.category}`}
                style={{
                  marginTop: idx === 0 ? 4 : 14, marginBottom: 6,
                  paddingHorizontal: 10, paddingVertical: 6,
                  backgroundColor: factor.category === 'primary' ? '#FEF3C7' : '#E0F2FE',
                  borderRadius: 8, alignSelf: 'flex-start',
                }}>
                <Text style={{
                  fontSize: 11, fontWeight: '800', letterSpacing: 0.4,
                  color: factor.category === 'primary' ? '#92400E' : '#075985',
                }}>
                  {sectionLabel.toUpperCase()}
                </Text>
              </View>
              {factorCard}
            </React.Fragment>
          );
        }
        return factorCard;
      })}

      {/* Download buttons */}
      <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
        <TouchableOpacity
          onPress={downloadActionPlan}
          style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, backgroundColor: '#F0FDF4', borderRadius: 10, borderWidth: 1, borderColor: '#16A34A' }}
        >
          <Ionicons name="document-text-outline" size={16} color="#16A34A" />
          <Text style={{ fontSize: 13, fontWeight: '600', color: '#16A34A' }}>CSV</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={async () => {
            try {
              const token = await AsyncStorage.getItem('session_token');
              const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
              const url = `${baseUrl}/api/decisions/${decision.id}/mpps-action-plan-pdf`;
              if (typeof window !== 'undefined') {
                const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
                const blob = await response.blob();
                const blobUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                a.download = `MPPS_Action_Plan.pdf`;
                a.click();
                URL.revokeObjectURL(blobUrl);
              }
              Alert.alert('Success', 'PDF downloaded');
            } catch (err) {
              Alert.alert('Error', 'Failed to download PDF');
            }
          }}
          style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, backgroundColor: '#EDE9FE', borderRadius: 10, borderWidth: 1, borderColor: COLORS.primary }}
        >
          <Ionicons name="download-outline" size={16} color={COLORS.primary} />
          <Text style={{ fontSize: 13, fontWeight: '600', color: COLORS.primary }}>PDF</Text>
        </TouchableOpacity>
      </View>

      {/* ─── Action Center bridge (Phase B) ──────────────────────────
          Push the inline MPPS action items into the universal Action
          Item store so they can be ported into CTT or LifeStyle and
          tracked centrally. Idempotent on the server side. */}
      <TouchableOpacity
        onPress={async () => {
          try {
            const token = await AsyncStorage.getItem('session_token');
            const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
            const r = await fetch(`${baseUrl}/api/action-items/import-from-mpps/${decision.id}`, {
              method: 'POST',
              headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            });
            const j = await r.json();
            if (!r.ok) throw new Error(j.detail || 'Import failed');
            Alert.alert(
              'Imported',
              `${j.imported_count || 0} action item${(j.imported_count||0)===1?'':'s'} pushed to the Action Center.`,
              [
                { text: 'Stay here' },
                { text: 'Open Action Center', onPress: () => { try { router.push('/tools/action-center' as any); } catch {} } },
              ]
            );
          } catch (err: any) {
            Alert.alert('Could not import', err?.message || 'Try again');
          }
        }}
        style={{ marginTop: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, backgroundColor: '#F0FDFA', borderRadius: 10, borderWidth: 1, borderColor: '#0D9488' }}
      >
        <Ionicons name="link" size={16} color="#0D9488" />
        <Text style={{ fontSize: 13, fontWeight: '700', color: '#0D9488' }}>Push to Action Center · CTT / LifeStyle</Text>
      </TouchableOpacity>

      <View style={styles.navButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(8)}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        <GradientButton
          title="Final Decision"
          onPress={() => { saveMPPSWorth(); setCurrentStep(10); }}
          style={styles.nextButton}
        />
      </View>
    </View>
  );
}
