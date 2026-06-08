import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet, Modal, FlatList, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import type { Factor, FactorDataSource } from '../../types/decision';
import api from '../../utils/api';
import { showAlert } from '../../utils/alert';
import UrlAccessConsentModal, { UrlConsentPayload } from '../UrlAccessConsentModal';
import {
  UNIT_PRESETS,
  NUMERIC_OPERATORS,
  TEXT_OPERATORS,
  senseDataType,
} from '../../utils/decisionHelpers';

const DATA_SOURCE_TYPES = [
  { key: 'webhook', label: 'Webhook/API', icon: 'link-outline', color: '#3B82F6' },
  { key: 'web_surf', label: 'Web Surf', icon: 'globe-outline', color: '#10B981' },
  { key: 'ai_llm', label: 'AI/LLM', icon: 'sparkles-outline', color: '#8B5CF6' },
] as const;

export default function Step2() {
  const {
    decision, saveDecision, updateFactor, removeFactor, addFactor, addFactorsFromTemplate,
    newFactorName, setNewFactorName,
    expectedInputs, setExpectedInputs,
    newSubFactorName, setNewSubFactorName,
    expandedGroups, setExpandedGroups,
    subWeightInputs, setSubWeightInputs,
    showUnitPicker, setShowUnitPicker,
    customUnitInput, setCustomUnitInput,
    setCurrentStep,
    fetchDecision,
  } = useDecision();

  const [showDataSourceConfig, setShowDataSourceConfig] = useState<{ [key: string]: boolean }>({});

  // ── "Import from URL" — crawl a comparison page → fill factors (with Expected),
  // options (Step 6) and partial assessments (Step 7), behind the consent gate.
  const [importUrl, setImportUrl] = useState('');
  const [importConsentOpen, setImportConsentOpen] = useState(false);
  const [importing, setImporting] = useState(false);

  const startImport = () => {
    if (!/^https?:\/\/.+/i.test(importUrl.trim())) {
      showAlert('Enter a URL', 'Paste a valid http(s) link to a comparison or filter page.');
      return;
    }
    setImportConsentOpen(true);
  };

  const runImport = async (consent: UrlConsentPayload) => {
    setImporting(true);
    try {
      const { data } = await api.post(`/url-analyze/decision/${decision.id}/import`, {
        url: importUrl.trim(),
        eligibility_type: consent.eligibility_type,
        custom_note: consent.custom_note,
        accepted: true,
      });
      setImportConsentOpen(false);
      setImporting(false);
      setImportUrl('');
      await fetchDecision();
      showAlert(
        'Imported from URL',
        `Added ${data.factors_added} factor${data.factors_added === 1 ? '' : 's'} and ${data.options_added} option${data.options_added === 1 ? '' : 's'} from ${data.item_count} items. Review the factors & Expected values below, then continue — Options (Step 6) and actuals (Step 7) are pre-filled.`,
      );
    } catch (e: any) {
      setImporting(false);
      const msg = e?.response?.data?.detail || 'Could not import from this URL. Try a page that lists items in a table.';
      showAlert('Import failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  // Inline rename — pencil icon next to each factor name. Critical for
  // SWOT-converted decisions where factors are AI-pre-filled and users
  // want to refine the wording before continuing (e.g., "SHOULD NOT -
  // Limited budget" → "Budget ≥ ₹5 L").
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const startFactorRename = (f: Factor) => {
    setRenameId(f.id);
    setRenameDraft(f.name || '');
  };
  const commitFactorRename = () => {
    if (!renameId) return;
    const trimmed = renameDraft.trim();
    if (trimmed) {
      updateFactor(renameId, { name: trimmed });
    }
    setRenameId(null);
    setRenameDraft('');
  };

  // Social Learning Templates for Factors
  const [showSLFactorModal, setShowSLFactorModal] = useState(false);
  const [slFactorTemplates, setSlFactorTemplates] = useState<any[]>([]);
  const [loadingSLFactors, setLoadingSLFactors] = useState(false);

  const fetchSLFactorTemplates = async () => {
    setLoadingSLFactors(true);
    try {
      const res = await api.get('/social-learning/templates-for-decision', {
        params: { life_area: decision.life_area || undefined, include_personal: true, limit: 20 },
      });
      // Combine all 3 tiers into a flat list with tier labels
      const all: any[] = [];
      (res.data?.tier_1_personal || []).forEach((t: any) => all.push({ ...t, _tierLabel: 'Personal' }));
      (res.data?.tier_2_authorized || []).forEach((t: any) => all.push({ ...t, _tierLabel: 'Authorized' }));
      (res.data?.tier_3_ai_derived || []).forEach((t: any) => all.push({ ...t, _tierLabel: 'AI Premium' }));
      setSlFactorTemplates(all);
    } catch (e) {
      console.error('Failed to load SL factor templates:', e);
      setSlFactorTemplates([]);
    } finally {
      setLoadingSLFactors(false);
    }
  };

  const handleImportFactors = (t: any) => {
    const factors = t.factors || [];
    if (factors.length === 0) return;
    const added = addFactorsFromTemplate(factors);
    setShowSLFactorModal(false);
    if (added > 0) {
      // Alert through a simple visual feedback
    }
  };

  // "Fetch My Best Factors" — AI proposes factors from life area + decision type
  // + title/description, auto-filling Step 2 so the user can refine & continue.
  const [aiFactorsLoading, setAiFactorsLoading] = useState(false);
  const handleFetchBestFactors = async () => {
    if (aiFactorsLoading) return;
    setAiFactorsLoading(true);
    try {
      const res = await api.post('/ai/suggest-factors', { decision_id: decision.id });
      const factors = res.data?.factors || [];
      if (factors.length === 0) {
        const unavailable = res.data?.used_model == null;
        showAlert(
          unavailable ? 'AI temporarily unavailable' : 'No suggestions',
          unavailable
            ? 'Could not reach the AI service right now. Please try again shortly, or add factors manually.'
            : 'AI could not suggest factors this time. Please add factors manually.'
        );
        return;
      }
      const added = addFactorsFromTemplate(factors);
      showAlert(
        added > 0 ? 'Factors added' : 'Already covered',
        added > 0
          ? `Added ${added} AI-suggested factor${added === 1 ? '' : 's'}. Review, reorder or remove any, then continue to Step 3.`
          : 'These factors are already in your list.'
      );
    } catch (e: any) {
      showAlert('Could not fetch factors', e?.response?.data?.detail || 'Please try again, or add factors manually.');
    } finally {
      setAiFactorsLoading(false);
    }
  };

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

  // Auto-split 100% equally across all sub-factors of a parent (largest-remainder
  // so the total is exactly 100). Clears the local input cache so the UI repaints.
  const autoSplitWeights = (parentId: string) => {
    const subs = getSubFactors(parentId);
    if (subs.length === 0) return;
    const base = Math.floor(100 / subs.length);
    const remainder = 100 - base * subs.length;
    const updated = decision.factors.map((f) => {
      const idx = subs.findIndex((s) => s.id === f.id);
      if (idx === -1) return f;
      return { ...f, weight: base + (idx < remainder ? 1 : 0) };
    });
    saveDecision({ factors: updated });
    const cleared = { ...subWeightInputs };
    subs.forEach((s) => { delete cleared[s.id]; });
    setSubWeightInputs(cleared);
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

    return (
      <View style={indent ? styles.subFactorCriteria : undefined}>
        {/* Operator */}
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

        {/* Expected Value */}
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

        {/* Unit */}
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

      <TouchableOpacity
        onPress={handleFetchBestFactors}
        disabled={aiFactorsLoading}
        activeOpacity={0.85}
        accessibilityLabel="Fetch My Best Factors with AI"
        style={{
          flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
          backgroundColor: '#7C3AED', borderRadius: 12, paddingVertical: 13, paddingHorizontal: 16,
          marginBottom: 6, opacity: aiFactorsLoading ? 0.7 : 1,
          shadowColor: '#7C3AED', shadowOffset: { width: 0, height: 3 }, shadowOpacity: 0.25, shadowRadius: 6, elevation: 3,
        }}
      >
        {aiFactorsLoading
          ? <ActivityIndicator size="small" color="#FFF" />
          : <Ionicons name="sparkles" size={18} color="#FFF" />}
        <Text style={{ color: '#FFF', fontSize: 15, fontWeight: '800' }}>
          {aiFactorsLoading ? 'Fetching your best factors…' : 'Fetch My Best Factors'}
        </Text>
      </TouchableOpacity>
      <Text style={{ fontSize: 11, color: COLORS.textMuted, textAlign: 'center', marginBottom: 14, lineHeight: 16, paddingHorizontal: 8 }}>
        AI suggests factors from your Life Area, decision type &amp; description. Review, reorder or remove any, then continue to Step 3.
      </Text>

      <View style={iurl.box}>
        <View style={iurl.head}>
          <Ionicons name="link" size={15} color="#2563EB" />
          <Text style={iurl.title}>Import from a URL</Text>
        </View>
        <Text style={iurl.sub}>
          Paste a comparison / filter page — we&apos;ll add its factors (with suggested Expected values)
          and options, and pre-fill the assessment matrix. You&apos;ll confirm your access rights first.
        </Text>
        <View style={iurl.row}>
          <TextInput
            testID="step2-import-url-input"
            style={iurl.input}
            placeholder="https://… comparison page"
            placeholderTextColor="#9CA3AF"
            value={importUrl}
            onChangeText={setImportUrl}
            autoCapitalize="none"
            keyboardType="url"
          />
          <TouchableOpacity
            testID="step2-import-url-btn"
            style={[iurl.btn, (!importUrl.trim() || importing) && { opacity: 0.5 }]}
            onPress={startImport}
            disabled={!importUrl.trim() || importing}
          >
            {importing ? <ActivityIndicator size="small" color="#fff" /> : <Text style={iurl.btnText}>Import</Text>}
          </TouchableOpacity>
        </View>
      </View>

      <UrlAccessConsentModal
        visible={importConsentOpen}
        url={importUrl.trim()}
        busy={importing}
        primary="#2563EB"
        onCancel={() => { if (!importing) setImportConsentOpen(false); }}
        onConfirm={runImport}
      />

      {topLevelFactors.map((factor) => {
        const subs = getSubFactors(factor.id);
        const hasChildren = subs.length > 0;
        const isExpanded = expandedGroups[factor.id] !== false;
        const weightTotalRaw = getSubWeightTotal(factor.id);
        const weightTotal = Math.round(weightTotalRaw * 10) / 10;          // tidy display
        const weightComplete = Math.abs(weightTotalRaw - 100) < 0.5;       // float-safe "= 100"
        const weightOver = weightTotalRaw - 100 >= 0.5;
        const hasExpected = factor.expected_value !== undefined && factor.expected_value !== null;

        return (
          <Card key={factor.id} style={[styles.factorCard, hasChildren && styles.factorCardGroup]}>
            <View style={styles.factorHeader}>
              {hasChildren && (
                <TouchableOpacity onPress={() => toggleGroup(factor.id)} style={styles.expandBtn}>
                  <Ionicons name={isExpanded ? 'chevron-down' : 'chevron-forward'} size={18} color={COLORS.textSecondary} />
                </TouchableOpacity>
              )}
              {renameId === factor.id ? (
                <TextInput
                  style={[styles.addInput, { flex: 1, marginRight: 8, paddingVertical: 6 }]}
                  value={renameDraft}
                  onChangeText={setRenameDraft}
                  onSubmitEditing={commitFactorRename}
                  onBlur={commitFactorRename}
                  autoFocus
                />
              ) : (
                <>
                  <Text style={[styles.factorName, { flex: 1 }]}>{factor.name}</Text>
                  <TouchableOpacity
                    onPress={() => startFactorRename(factor)}
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    style={{ marginRight: 8 }}
                  >
                    <Ionicons name="pencil" size={16} color={COLORS.primary} />
                  </TouchableOpacity>
                </>
              )}
              {hasChildren && (
                <View style={[styles.weightTotalBadge, weightComplete && styles.weightTotalComplete, weightOver && styles.weightTotalOver]}>
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

            {/* Factor Type Toggle: Quantitative / Qualitative — placed ABOVE the Operator/Expected/Unit criteria */}
            {!hasChildren && (
              <View style={dsStyles.factorTypeRow}>
                <Text style={dsStyles.factorTypeLabel}>Type:</Text>
                <TouchableOpacity
                  style={[dsStyles.typeChip, (factor.factor_type || (factor.data_type === 'text' ? 'qualitative' : 'quantitative')) === 'quantitative' && dsStyles.typeChipActiveBlue]}
                  onPress={() => updateFactor(factor.id, { factor_type: 'quantitative' })}
                >
                  <Ionicons name="calculator-outline" size={12} color={(factor.factor_type || (factor.data_type === 'text' ? 'qualitative' : 'quantitative')) === 'quantitative' ? '#FFF' : COLORS.textMuted} />
                  <Text style={[dsStyles.typeChipText, (factor.factor_type || (factor.data_type === 'text' ? 'qualitative' : 'quantitative')) === 'quantitative' && dsStyles.typeChipTextActive]}>Quantitative</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[dsStyles.typeChip, (factor.factor_type || (factor.data_type === 'text' ? 'qualitative' : 'quantitative')) === 'qualitative' && dsStyles.typeChipActiveGreen]}
                  onPress={() => updateFactor(factor.id, { factor_type: 'qualitative' })}
                >
                  <Ionicons name="text-outline" size={12} color={(factor.factor_type || (factor.data_type === 'text' ? 'qualitative' : 'quantitative')) === 'qualitative' ? '#FFF' : COLORS.textMuted} />
                  <Text style={[dsStyles.typeChipText, (factor.factor_type || (factor.data_type === 'text' ? 'qualitative' : 'quantitative')) === 'qualitative' && dsStyles.typeChipTextActive]}>Qualitative</Text>
                </TouchableOpacity>
              </View>
            )}

            {!hasChildren && renderCriteria(factor)}

            {/* Data Source toggle — kept adjacent to its collapsible config panel below */}
            {!hasChildren && (
              <View style={dsStyles.factorTypeRow}>
                <TouchableOpacity
                  style={[dsStyles.dsToggleBtn, factor.data_source?.type && dsStyles.dsToggleBtnActive]}
                  onPress={() => setShowDataSourceConfig({ ...showDataSourceConfig, [factor.id]: !showDataSourceConfig[factor.id] })}
                >
                  <Ionicons name="cloud-download-outline" size={14} color={factor.data_source?.type ? '#FFF' : COLORS.primary} />
                  <Text style={[dsStyles.dsToggleBtnText, factor.data_source?.type && { color: '#FFF' }]}>
                    {factor.data_source?.type ? DATA_SOURCE_TYPES.find(d => d.key === factor.data_source?.type)?.label : 'Data Source'}
                  </Text>
                </TouchableOpacity>
              </View>
            )}

            {/* Data Source Configuration (collapsible) */}
            {showDataSourceConfig[factor.id] && (
              <View style={dsStyles.dsConfigContainer}>
                <Text style={dsStyles.dsConfigTitle}>Auto-Fetch Configuration</Text>
                <View style={dsStyles.dsTypeRow}>
                  {DATA_SOURCE_TYPES.map((ds) => (
                    <TouchableOpacity
                      key={ds.key}
                      style={[dsStyles.dsTypeChip, factor.data_source?.type === ds.key && { backgroundColor: ds.color, borderColor: ds.color }]}
                      onPress={() => {
                        const currentDs = factor.data_source || { type: ds.key, config: {} };
                        updateFactor(factor.id, { data_source: { ...currentDs, type: ds.key as any } });
                      }}
                    >
                      <Ionicons name={ds.icon as any} size={14} color={factor.data_source?.type === ds.key ? '#FFF' : ds.color} />
                      <Text style={[dsStyles.dsTypeChipText, factor.data_source?.type === ds.key && { color: '#FFF' }]}>{ds.label}</Text>
                    </TouchableOpacity>
                  ))}
                  {factor.data_source?.type && (
                    <TouchableOpacity
                      style={dsStyles.dsClearBtn}
                      onPress={() => updateFactor(factor.id, { data_source: undefined })}
                    >
                      <Ionicons name="close" size={14} color={COLORS.error} />
                    </TouchableOpacity>
                  )}
                </View>

                {factor.data_source?.type === 'webhook' && (
                  <View style={dsStyles.dsFieldsContainer}>
                    <Text style={dsStyles.dsFieldLabel}>Webhook URL</Text>
                    <TextInput
                      style={dsStyles.dsFieldInput}
                      value={factor.data_source.config?.url || ''}
                      onChangeText={(text) => updateFactor(factor.id, {
                        data_source: { ...factor.data_source!, config: { ...factor.data_source!.config, url: text } }
                      })}
                      placeholder="https://api.example.com/data"
                      placeholderTextColor={COLORS.textMuted}
                      autoCapitalize="none"
                    />
                    <Text style={dsStyles.dsFieldLabel}>Custom Headers (JSON, optional)</Text>
                    <TextInput
                      style={dsStyles.dsFieldInput}
                      value={factor.data_source.config?.headers || ''}
                      onChangeText={(text) => updateFactor(factor.id, {
                        data_source: { ...factor.data_source!, config: { ...factor.data_source!.config, headers: text } }
                      })}
                      placeholder='{"Authorization": "Bearer ..."}'
                      placeholderTextColor={COLORS.textMuted}
                      autoCapitalize="none"
                    />
                    <Text style={dsStyles.dsHint}>POST request with factor_name, option_name, decision_title in body. Expects {'{"value": ...}'} in response.</Text>
                  </View>
                )}

                {factor.data_source?.type === 'web_surf' && (
                  <View style={dsStyles.dsFieldsContainer}>
                    <Text style={dsStyles.dsFieldLabel}>Search Query Template</Text>
                    <TextInput
                      style={dsStyles.dsFieldInput}
                      value={factor.data_source.config?.search_query || ''}
                      onChangeText={(text) => updateFactor(factor.id, {
                        data_source: { ...factor.data_source!, config: { ...factor.data_source!.config, search_query: text } }
                      })}
                      placeholder="{factor} for {option} in {title}"
                      placeholderTextColor={COLORS.textMuted}
                    />
                    <Text style={dsStyles.dsHint}>Use {'{factor}'}, {'{option}'}, {'{title}'} as placeholders. AI will search and extract the value.</Text>
                  </View>
                )}

                {factor.data_source?.type === 'ai_llm' && (
                  <View style={dsStyles.dsFieldsContainer}>
                    <Text style={dsStyles.dsFieldLabel}>Custom Prompt</Text>
                    <TextInput
                      style={[dsStyles.dsFieldInput, { minHeight: 60 }]}
                      value={factor.data_source.config?.prompt || ''}
                      onChangeText={(text) => updateFactor(factor.id, {
                        data_source: { ...factor.data_source!, config: { ...factor.data_source!.config, prompt: text } }
                      })}
                      placeholder="What is the {factor} for {option}?"
                      placeholderTextColor={COLORS.textMuted}
                      multiline
                    />
                    <Text style={dsStyles.dsHint}>AI will answer using decision context. Use {'{factor}'}, {'{option}'}, {'{title}'} placeholders.</Text>
                  </View>
                )}
              </View>
            )}

            {hasChildren && isExpanded && (
              <View style={styles.subFactorsContainer}>
                <View style={styles.weightProgressRow}>
                  <View style={styles.weightProgressBar}>
                    <View style={[
                      styles.weightProgressFill,
                      { width: `${Math.min(100, weightTotal)}%` },
                      weightComplete && { backgroundColor: '#10B981' },
                      weightOver && { backgroundColor: '#EF4444' },
                    ]} />
                  </View>
                  <Text style={[styles.weightProgressText, weightComplete && { color: '#10B981' }, weightOver && { color: '#EF4444' }]}>
                    {weightTotal}/100%
                  </Text>
                  {subs.length > 1 && (
                    <TouchableOpacity
                      onPress={() => autoSplitWeights(factor.id)}
                      style={sfStyles.autoSplitBtn}
                      testID={`md-split-${factor.id}`}
                      accessibilityLabel="Split weightage equally"
                    >
                      <Ionicons name="git-compare-outline" size={13} color="#7C3AED" />
                      <Text style={sfStyles.autoSplitBtnText}>Split evenly</Text>
                    </TouchableOpacity>
                  )}
                </View>
                {weightTotal !== 100 && (
                  <Text style={sfStyles.weightHint}>
                    {weightTotal > 100
                      ? `Total exceeds 100% by ${weightTotal - 100}. Adjust or tap “Split evenly”.`
                      : `${100 - weightTotal}% left to allocate. You can continue — weights are normalised — or tap “Split evenly”.`}
                  </Text>
                )}

                {subs.map((sub) => {
                  const subHasExpected = sub.expected_value !== undefined && sub.expected_value !== null;
                  return (
                    <View key={sub.id} style={styles.subFactorItem}>
                      <View style={styles.subFactorHeader}>
                        <View style={styles.subFactorDot} />
                        {renameId === sub.id ? (
                          <TextInput
                            style={[styles.addInput, { flex: 1, marginRight: 8, paddingVertical: 4 }]}
                            value={renameDraft}
                            onChangeText={setRenameDraft}
                            onSubmitEditing={commitFactorRename}
                            onBlur={commitFactorRename}
                            autoFocus
                          />
                        ) : (
                          <>
                            <Text style={[styles.subFactorName, { flex: 1 }]}>{sub.name}</Text>
                            <TouchableOpacity
                              onPress={() => startFactorRename(sub)}
                              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                              style={{ marginRight: 6 }}
                            >
                              <Ionicons name="pencil" size={14} color={COLORS.primary} />
                            </TouchableOpacity>
                          </>
                        )}
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
                            testID={`md-subweight-${sub.id}`}
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

      {/* Social Learning Factors Import */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F3FF', borderRadius: 12, padding: 12, marginTop: 8, marginBottom: 8, borderWidth: 1, borderColor: '#DDD6FE', gap: 10 }}
        onPress={() => { setShowSLFactorModal(true); fetchSLFactorTemplates(); }}
      >
        <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: '#7C3AED', justifyContent: 'center', alignItems: 'center' }}>
          <Ionicons name="newspaper" size={16} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 13, fontWeight: '600', color: '#7C3AED' }}>Import Factors from Social Learning</Text>
          <Text style={{ fontSize: 10, color: '#8B5CF6' }}>Pre-prioritized factors from real-world scenarios</Text>
        </View>
        <Ionicons name="chevron-forward" size={16} color="#7C3AED" />
      </TouchableOpacity>

      <GradientButton
        title="Continue to Classification"
        onPress={() => setCurrentStep(3)}
        disabled={topLevelFactors.length < 2}
        style={styles.continueButton}
      />

      {/* Social Learning Factor Templates Modal */}
      <Modal visible={showSLFactorModal} transparent animationType="slide">
        <View style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' }}>
          <View style={{ backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '80%' }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <Ionicons name="newspaper" size={20} color="#7C3AED" />
                <Text style={{ fontSize: 16, fontWeight: '700', color: '#1F2937' }}>Import Factors</Text>
              </View>
              <TouchableOpacity onPress={() => setShowSLFactorModal(false)}>
                <Ionicons name="close" size={24} color="#6B7280" />
              </TouchableOpacity>
            </View>

            <Text style={{ fontSize: 12, color: '#9CA3AF', marginBottom: 4 }}>
              Factors are auto-grouped: Priority ≥ 7 → Primary (Mandatory), {'<'} 7 → Secondary (Optional)
            </Text>
            <Text style={{ fontSize: 11, color: '#D1D5DB', marginBottom: 12 }}>
              Expected values & factor types are pre-filled from AI analysis
            </Text>

            {loadingSLFactors ? (
              <ActivityIndicator size="large" color="#7C3AED" style={{ marginTop: 40 }} />
            ) : slFactorTemplates.length === 0 ? (
              <View style={{ alignItems: 'center', paddingVertical: 40 }}>
                <Ionicons name="newspaper-outline" size={40} color="#D1D5DB" />
                <Text style={{ fontSize: 14, color: '#9CA3AF', marginTop: 8 }}>No templates available</Text>
                <Text style={{ fontSize: 12, color: '#D1D5DB', marginTop: 4, textAlign: 'center' }}>Upload news in Social Learning to generate factor templates</Text>
              </View>
            ) : (
              <FlatList
                data={slFactorTemplates}
                keyExtractor={(item) => item.id}
                contentContainerStyle={{ paddingBottom: 20 }}
                renderItem={({ item }) => (
                  <TouchableOpacity
                    style={{ backgroundColor: '#F9FAFB', borderRadius: 10, padding: 12, marginBottom: 8, borderLeftWidth: 3, borderLeftColor: item.tier === 3 ? '#7C3AED' : item.tier === 2 ? '#059669' : '#6B7280' }}
                    onPress={() => handleImportFactors(item)}
                  >
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                      <View style={{ backgroundColor: item.tier === 3 ? '#F5F3FF' : item.tier === 2 ? '#ECFDF5' : '#F3F4F6', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 }}>
                        <Text style={{ fontSize: 9, fontWeight: '700', color: item.tier === 3 ? '#7C3AED' : item.tier === 2 ? '#059669' : '#6B7280' }}>
                          {item._tierLabel || (item.tier === 3 ? 'AI Premium' : item.tier === 2 ? 'Authorized' : 'Personal')}
                        </Text>
                      </View>
                      <Text style={{ fontSize: 11, color: '#6B7280' }}>{item.category}</Text>
                    </View>
                    <Text style={{ fontSize: 13, fontWeight: '600', color: '#1F2937' }} numberOfLines={1}>
                      {item.scenario_title || item.title}
                    </Text>
                    <Text style={{ fontSize: 11, color: '#6B7280', marginTop: 2 }} numberOfLines={1}>
                      {(item.factors || []).length} factors • {item.sub_area || ''}
                    </Text>
                    {(item.factors || []).length > 0 && (
                      <View style={{ marginTop: 6 }}>
                        {(item.factors || []).slice(0, 4).map((f: any, idx: number) => (
                          <View key={idx} style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                            <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: f.classification === 'mandatory' ? '#EF4444' : '#F59E0B' }} />
                            <Text style={{ fontSize: 11, color: '#374151', flex: 1 }} numberOfLines={1}>{f.name}</Text>
                            <Text style={{ fontSize: 9, color: f.classification === 'mandatory' ? '#EF4444' : '#D97706', fontWeight: '600' }}>
                              {f.practical_priority || `P${f.practical_priority_num || 5}`} • {f.classification === 'mandatory' ? 'Mandatory' : 'Optional'}
                            </Text>
                            {f.expected_value_pct !== undefined && (
                              <Text style={{ fontSize: 9, color: '#6B7280' }}>Exp: {f.expected_value_pct}%</Text>
                            )}
                          </View>
                        ))}
                        {(item.factors || []).length > 4 && (
                          <Text style={{ fontSize: 10, color: '#9CA3AF', marginTop: 2 }}>
                            +{(item.factors || []).length - 4} more factors
                          </Text>
                        )}
                      </View>
                    )}
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6 }}>
                      <Ionicons name="download" size={14} color="#7C3AED" />
                      <Text style={{ fontSize: 10, color: '#7C3AED', fontWeight: '500' }}>Tap to import all factors</Text>
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

const dsStyles = StyleSheet.create({
  factorTypeRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, flexWrap: 'wrap' },
  factorTypeLabel: { fontSize: 11, color: COLORS.textMuted, fontWeight: '600' },
  typeChip: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: '#F8FAFC' },
  typeChipActiveBlue: { backgroundColor: '#3B82F6', borderColor: '#3B82F6' },
  typeChipActiveGreen: { backgroundColor: '#10B981', borderColor: '#10B981' },
  typeChipText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },
  typeChipTextActive: { color: '#FFF' },
  dsToggleBtn: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, borderWidth: 1.5, borderColor: COLORS.primary, backgroundColor: '#F5F3FF', marginLeft: 'auto' },
  dsToggleBtnActive: { backgroundColor: COLORS.primary },
  dsToggleBtnText: { fontSize: 11, fontWeight: '600', color: COLORS.primary },
  dsConfigContainer: { marginTop: 8, padding: 10, backgroundColor: '#F8FAFC', borderRadius: 10, borderWidth: 1, borderColor: COLORS.border },
  dsConfigTitle: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  dsTypeRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap', marginBottom: 8 },
  dsTypeChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 10, borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: '#FFF' },
  dsTypeChipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  dsClearBtn: { padding: 6, borderRadius: 8, backgroundColor: '#FEE2E2' },
  dsFieldsContainer: { gap: 6 },
  dsFieldLabel: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted, marginTop: 4 },
  dsFieldInput: { height: 36, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 10, fontSize: 12, color: COLORS.textPrimary, backgroundColor: '#FFF' },
  dsHint: { fontSize: 10, color: COLORS.textMuted, fontStyle: 'italic', marginTop: 2 },
});

const sfStyles = StyleSheet.create({
  autoSplitBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 10, backgroundColor: '#F5F3FF', borderWidth: 1, borderColor: '#DDD6FE', marginLeft: 8 },
  autoSplitBtnText: { fontSize: 11, fontWeight: '700', color: '#7C3AED' },
  weightHint: { fontSize: 10.5, color: COLORS.textMuted, marginTop: 4, marginBottom: 2, lineHeight: 15 },
});

const iurl = StyleSheet.create({
  box: { backgroundColor: '#EFF6FF', borderWidth: 1, borderColor: '#BFDBFE', borderRadius: 12, padding: 12, marginBottom: 16 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  title: { fontSize: 13.5, fontWeight: '800', color: '#1E40AF' },
  sub: { fontSize: 11.5, lineHeight: 16, color: '#1E40AF', marginBottom: 10 },
  row: { flexDirection: 'row', gap: 8 },
  input: { flex: 1, backgroundColor: '#fff', borderWidth: 1, borderColor: '#BFDBFE', borderRadius: 10, paddingHorizontal: 11, paddingVertical: 9, fontSize: 13, color: COLORS.textPrimary },
  btn: { backgroundColor: '#2563EB', borderRadius: 10, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center', minWidth: 80 },
  btnText: { color: '#fff', fontSize: 13.5, fontWeight: '800' },
});

