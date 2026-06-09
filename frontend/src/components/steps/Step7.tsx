import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator, StyleSheet, Alert, Modal } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import AiCreditsBadge from '../AiCreditsBadge';
import { useAiWalletStore } from '../../store/aiWalletStore';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import { LMH_VALUES, effectiveFactorPct } from '../../utils/decisionHelpers';
import { downloadAssessmentTemplate, importAssessmentTemplate } from '../../utils/assessmentXlsx';
import { createAssessmentGsheet, importAssessmentGsheet, openSheetUrl } from '../../utils/googleSheets';
import { showAlert } from '../../utils/alert';
import { api } from '../../utils/api';
import type { Factor } from '../../types/decision';
import UrlAccessConsentModal, { UrlConsentPayload } from '../UrlAccessConsentModal';

export default function Step7() {
  const {
    decision, updateAssessment, getAssessmentValue, getAssessmentMode,
    getUnitValue, getActualValue, getAssessmentKey,
    showCustomInput, setShowCustomInput,
    customInputValues, setCustomInputValues,
    actualValues, setActualValues,
    calculateDynamicWorth, calculateAutoPercentage,
    setCurrentStep, fetchDecision,
    bulkAssessAllRemaining,
  } = useDecision();

  // Import ACTUAL VALUES from a URL (consent-gated), then auto AI-assess.
  const [actualsDialogOpen, setActualsDialogOpen] = useState(false);
  const [urlActualsOpen, setUrlActualsOpen] = useState(false);
  const [actualsUrl, setActualsUrl] = useState('');
  const [actualsBusy, setActualsBusy] = useState(false);

  const submitActualsDialog = () => {
    if (!/^https?:\/\/.+/i.test(actualsUrl.trim())) {
      showAlert('Enter a URL', 'Paste a valid http(s) link to a product / comparison page.');
      return;
    }
    setActualsDialogOpen(false);
    setUrlActualsOpen(true);
  };

  const runImportActuals = async (consent: UrlConsentPayload) => {
    setActualsBusy(true);
    try {
      const { data } = await api.post(`/decisions/${decision!.id}/import-actuals-from-url`, {
        url: actualsUrl.trim(),
        eligibility_type: consent.eligibility_type,
        custom_note: consent.custom_note,
        accepted: true,
      });
      setUrlActualsOpen(false);
      await fetchDecision();
      if ((data.filled_cells ?? 0) === 0) {
        showAlert('No matches found', 'Could not match this page to your options/factors. Try a closer comparison page.');
        return;
      }
      // Auto-run AI scoring on the freshly filled actuals.
      const res = await bulkAssessAllRemaining(true);
      showAlert(
        'Actuals imported',
        `Filled ${data.filled_cells} actual value(s) across ${data.matched_options} option(s)` +
        (res.done > 0 ? `, then AI-scored ${res.done} cell(s).` : '.') +
        (res.ranOut ? ' (AI credits ran out before finishing — top up to complete.)' : ''),
      );
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Could not import actual values from this URL.';
      showAlert('Import failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setActualsBusy(false);
    }
  };

  // ─── Phase C: XLS assessment template export / import ───
  const [xlsBusy, setXlsBusy] = useState(false);
  const router = useRouter();
  const refreshAiWallet = useAiWalletStore((s) => s.refresh);
  const handleDownloadTemplate = async () => {
    setXlsBusy(true);
    try {
      await downloadAssessmentTemplate(`/decisions/${decision.id}/assessment-template`, 'assessment-template.xlsx');
    } catch (e: any) {
      showAlert('Download failed', e?.message || 'Could not download the template.');
    } finally {
      setXlsBusy(false);
    }
  };
  const handleImportTemplate = async () => {
    setXlsBusy(true);
    try {
      const res = await importAssessmentTemplate(`/decisions/${decision.id}/assessment-import`);
      if (res) {
        await fetchDecision();
        showAlert('Import complete', `Applied ${res.applied} value(s) from ${res.rows} row(s).`);
      }
    } catch (e: any) {
      showAlert('Import failed', e?.message || 'Could not import the file.');
    } finally {
      setXlsBusy(false);
    }
  };
  const handleCreateGsheet = async () => {
    setXlsBusy(true);
    try {
      const res = await createAssessmentGsheet(`/decisions/${decision.id}/assessment-gsheet`);
      await openSheetUrl(res.url);
      showAlert('Google Sheet ready', 'A Google Sheet was created in your Drive. Fill the “Actual Value” and “Assess %” columns, then tap “Import Sheet”.');
    } catch (e: any) {
      showAlert('Google Sheet', e?.message || 'Could not create the Google Sheet.');
    } finally {
      setXlsBusy(false);
    }
  };
  const handleImportGsheet = async () => {
    setXlsBusy(true);
    try {
      const res = await importAssessmentGsheet(`/decisions/${decision.id}/assessment-gsheet/import`);
      await fetchDecision();
      showAlert('Import complete', `Applied ${res.applied} value(s) from ${res.rows} row(s).`);
    } catch (e: any) {
      showAlert('Import failed', e?.message || 'Could not import from the Google Sheet. Create one first if you haven’t.');
    } finally {
      setXlsBusy(false);
    }
  };

  const [fetchingData, setFetchingData] = useState<{ [key: string]: boolean }>({});
  const [fetchingStore, setFetchingStore] = useState<{ [key: string]: boolean }>({});
  // Per option×factor toggle for the optional direct/general assessment fallback.
  const [directOpen, setDirectOpen] = useState<{ [key: string]: boolean }>({});
  // Per option×factor busy flag for the LLM "AI" satisfaction assessment.
  const [aiAssessBusy, setAiAssessBusy] = useState<{ [key: string]: boolean }>({});

  // Fetch pre-populated data from Solutions Store for options linked to a solution
  const fetchFromSolutionStore = async (optionId: string, solutionId: string) => {
    const fetchKey = `store_${optionId}`;
    setFetchingStore(prev => ({ ...prev, [fetchKey]: true }));
    try {
      const token = await AsyncStorage.getItem('session_token');
      const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
      const resp = await fetch(`${baseUrl}/api/solutions-store/apply-to-option`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ solution_id: solutionId }),
      });
      const data = await resp.json();

      let matchCount = 0;

      // Auto-populate quantitative factors
      if (data.quantitative_factors && data.quantitative_factors.length > 0) {
        for (const qf of data.quantitative_factors) {
          // Try to find a matching factor in the decision
          const matchingFactor = decision.factors.find(f =>
            f.name.toLowerCase().includes(qf.factor_name.toLowerCase()) ||
            qf.factor_name.toLowerCase().includes(f.name.toLowerCase())
          );
          if (matchingFactor) {
            matchCount++;
            const key = getAssessmentKey(optionId, matchingFactor.id);
            const valStr = String(qf.value);
            setActualValues(prev => ({ ...prev, [key]: valStr }));
            const autoPercent = calculateAutoPercentage(matchingFactor, qf.value);
            const unitStr = matchingFactor.unit || qf.unit || '';
            const displayValue = `${qf.value}${unitStr ? ' ' + unitStr : ''}`;
            const numericActual = typeof qf.value === 'number' ? qf.value : parseFloat(String(qf.value));
            if (autoPercent !== null) {
              updateAssessment(optionId, matchingFactor.id, autoPercent, 'auto' as any, displayValue, isNaN(numericActual) ? undefined : numericActual);
            }
          }
        }
      }

      // Auto-populate qualitative factors (LEGACY db.solution_reviews — 1-10 scale)
      if (data.qualitative_factors && data.qualitative_factors.length > 0) {
        for (const qf of data.qualitative_factors) {
          const matchingFactor = decision.factors.find(f =>
            f.name.toLowerCase().includes(qf.factor_name.toLowerCase()) ||
            qf.factor_name.toLowerCase().includes(f.name.toLowerCase())
          );
          if (matchingFactor) {
            matchCount++;
            // Convert 1-10 qualitative rating to percentage (multiply by 10)
            const percentage = Math.min(100, Math.round(qf.avg_rating * 10));
            const key = getAssessmentKey(optionId, matchingFactor.id);
            setActualValues(prev => ({ ...prev, [key]: String(qf.avg_rating) }));
            updateAssessment(optionId, matchingFactor.id, percentage, 'auto' as any, `${qf.avg_rating}/10 (${qf.review_count} reviews)`, qf.avg_rating);
          }
        }
      }

      // NEW v3.7.2: ReviewNet (5-star scale, segmented) — overrides legacy if both present
      if (data.review_net && data.review_net.per_factor && data.review_net.per_factor.length > 0) {
        for (const rnf of data.review_net.per_factor) {
          const matchingFactor = decision.factors.find(f =>
            f.name.toLowerCase().includes(rnf.factor_name.toLowerCase()) ||
            rnf.factor_name.toLowerCase().includes(f.name.toLowerCase())
          );
          if (matchingFactor) {
            matchCount++;
            // Convert 1-5 star to percentage (×20). 4.2/5 → 84%
            const percentage = Math.min(100, Math.round(rnf.overall_avg * 20));
            const key = getAssessmentKey(optionId, matchingFactor.id);
            setActualValues(prev => ({ ...prev, [key]: String(rnf.overall_avg) }));
            // Segmented detail in display string
            const segDetails = Object.entries(rnf.by_segment || {})
              .filter(([_, agg]: any) => agg.count > 0)
              .map(([seg, agg]: any) => `${seg}:${agg.avg}/5(${agg.count})`)
              .join(' · ');
            updateAssessment(
              optionId,
              matchingFactor.id,
              percentage,
              'auto' as any,
              `★ ${rnf.overall_avg}/5 ReviewNet (${rnf.review_count} reviews)${segDetails ? ' — ' + segDetails : ''}`,
              rnf.overall_avg,
            );
          }
        }
      }

      if (matchCount > 0) {
        Alert.alert('Store Data Applied', `${matchCount} factor value${matchCount > 1 ? 's' : ''} auto-populated from Solutions Store & ReviewNet`);
      } else {
        Alert.alert('No Matches', 'No factor names matched between your decision and the solution data. Values are stored for reference.');
      }
    } catch (err) {
      console.error('Error fetching store data:', err);
      Alert.alert('Error', 'Failed to fetch data from Solutions Store');
    } finally {
      setFetchingStore(prev => ({ ...prev, [fetchKey]: false }));
    }
  };

  // Fetch data from configured data sources for all factors of an option
  const fetchFactorData = async (optionId: string, optionName: string) => {
    const factorsWithDataSource = decision.factors.filter(f => !f.parent_id && f.data_source?.type);
    if (factorsWithDataSource.length === 0) {
      Alert.alert('No Data Sources', 'No factors have auto-fetch data sources configured. Configure them in Step 2.');
      return;
    }
    const fetchKey = `option_${optionId}`;
    setFetchingData(prev => ({ ...prev, [fetchKey]: true }));
    try {
      const token = await AsyncStorage.getItem('session_token');
      const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
      const resp = await fetch(`${baseUrl}/api/factors/fetch-data`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          decision_title: decision.title,
          decision_context: decision.context,
          option_name: optionName,
          factors: factorsWithDataSource.map(f => ({
            id: f.id,
            name: f.name,
            factor_type: f.factor_type || (f.data_type === 'text' ? 'qualitative' : 'quantitative'),
            data_source: f.data_source,
            unit: f.unit,
            expected_value: f.expected_value,
            operator: f.operator,
          })),
        }),
      });
      const data = await resp.json();
      if (data.results && data.results.length > 0) {
        let successCount = 0;
        for (const result of data.results) {
          if (result.value !== null && result.value !== undefined) {
            successCount++;
            const factor = decision.factors.find(f => f.id === result.factor_id);
            const key = getAssessmentKey(optionId, result.factor_id);
            const valStr = String(result.value);
            setActualValues(prev => ({ ...prev, [key]: valStr }));
            // Auto-calculate percentage if possible
            if (factor) {
              const autoPercent = calculateAutoPercentage(factor, result.value);
              const unitStr = factor.unit || '';
              const displayValue = `${result.value}${unitStr ? ' ' + unitStr : ''}`;
              const numericActual = typeof result.value === 'number' ? result.value : parseFloat(String(result.value));
              if (autoPercent !== null) {
                updateAssessment(optionId, result.factor_id, autoPercent, 'auto' as any, displayValue, isNaN(numericActual) ? undefined : numericActual);
              }
            }
          }
        }
        const errorCount = data.results.filter((r: any) => r.error).length;
        Alert.alert('Data Fetched', `${successCount} values fetched${errorCount > 0 ? `, ${errorCount} failed` : ''}`);
      }
    } catch (err) {
      Alert.alert('Error', 'Failed to fetch data from sources');
    } finally {
      setFetchingData(prev => ({ ...prev, [fetchKey]: false }));
    }
  };

  const handleLMHSelect = (optionId: string, factorId: string, mode: 'L' | 'M' | 'H') => {
    const percentage = LMH_VALUES[mode].percentage;
    const key = getAssessmentKey(optionId, factorId);
    setShowCustomInput({ ...showCustomInput, [key]: false });
    setCustomInputValues({ ...customInputValues, [key]: '' });
    const currentActual = getActualValue(optionId, factorId);
    const factor = decision.factors.find(f => f.id === factorId);
    const unitStr = factor?.unit || '';
    const displayValue = currentActual !== undefined ? `${currentActual}${unitStr ? ' ' + unitStr : ''}` : '';
    updateAssessment(optionId, factorId, percentage, mode, displayValue, currentActual);
  };

  const handleCustomSelect = (optionId: string, factorId: string) => {
    const key = getAssessmentKey(optionId, factorId);
    const currentValue = getAssessmentValue(optionId, factorId);
    setShowCustomInput({ ...showCustomInput, [key]: true });
    setCustomInputValues({ ...customInputValues, [key]: String(currentValue) });
  };

  const handleCustomInputChange = (optionId: string, factorId: string, value: string) => {
    const key = getAssessmentKey(optionId, factorId);
    const cleanValue = value.replace(/[^0-9]/g, '');
    const num = parseInt(cleanValue) || 0;
    const clampedValue = num > 100 ? '100' : cleanValue;
    setCustomInputValues({ ...customInputValues, [key]: clampedValue });
  };

  const handleCustomInputBlur = (optionId: string, factorId: string) => {
    const key = getAssessmentKey(optionId, factorId);
    const inputValue = customInputValues[key] || '0';
    const num = parseInt(inputValue) || 0;
    const percentage = Math.min(100, Math.max(0, num));
    const currentActual = getActualValue(optionId, factorId);
    const factor = decision.factors.find(f => f.id === factorId);
    const unitStr = factor?.unit || '';
    const displayValue = currentActual !== undefined ? `${currentActual}${unitStr ? ' ' + unitStr : ''}` : '';
    updateAssessment(optionId, factorId, percentage, 'custom', displayValue, currentActual);
  };

  const handleUnitValueChange = (optionId: string, factorId: string, value: string) => {
    const key = getAssessmentKey(optionId, factorId);
    const factor = decision.factors.find(f => f.id === factorId);
    const isTextType = factor?.data_type === 'text';
    if (isTextType) {
      setActualValues({ ...actualValues, [key]: value });
    } else {
      const cleanValue = value.replace(/[^0-9.]/g, '');
      const parts = cleanValue.split('.');
      const sanitized = parts.length > 2 ? parts[0] + '.' + parts.slice(1).join('') : cleanValue;
      setActualValues({ ...actualValues, [key]: sanitized });
    }
  };

  const handleActualValueBlur = (optionId: string, factorId: string) => {
    const key = getAssessmentKey(optionId, factorId);
    const inputValue = (actualValues[key] || '').trim();
    const factor = decision.factors.find(f => f.id === factorId);
    const isTextType = factor?.data_type === 'text';
    let actualVal: number | string | undefined;
    if (isTextType) { actualVal = inputValue || undefined; }
    else { const numVal = parseFloat(inputValue); actualVal = isNaN(numVal) ? undefined : numVal; }
    const unitStr = factor?.unit || '';
    const displayValue = actualVal !== undefined ? `${actualVal}${unitStr ? ' ' + unitStr : ''}` : '';
    const numericActual = typeof actualVal === 'number' ? actualVal : undefined;
    const autoPercent = factor ? calculateAutoPercentage(factor, actualVal) : null;
    if (autoPercent !== null) {
      updateAssessment(optionId, factorId, autoPercent, 'auto' as any, displayValue, numericActual);
    } else {
      const currentMode = getAssessmentMode(optionId, factorId);
      const currentPercentage = getAssessmentValue(optionId, factorId);
      updateAssessment(optionId, factorId, currentPercentage as number, currentMode, displayValue, numericActual);
    }
  };

  const getActualInputValue = (optionId: string, factorId: string): string => {
    const key = getAssessmentKey(optionId, factorId);
    if (actualValues[key] !== undefined) return actualValues[key];
    const stored = getActualValue(optionId, factorId);
    if (stored !== undefined && stored !== null) return String(stored);
    const legacy = getUnitValue(optionId, factorId);
    if (legacy) {
      const factor = decision.factors.find(f => f.id === factorId);
      if (factor?.data_type === 'text') return legacy;
      const num = parseFloat(legacy);
      if (!isNaN(num)) return String(num);
    }
    return '';
  };

  // LLM-scored satisfaction % from expected vs actual. Validation mirrors the
  // backend (core/ai_assess): Quantitative needs Expected + Operator + Actual;
  // Qualitative/Subjective needs Expected only (AI fetches/infers the Actual).
  const handleAIAssess = async (optionId: string, factorId: string) => {
    const key = getAssessmentKey(optionId, factorId);
    const factor = decision.factors.find(f => f.id === factorId);
    const actual = getActualInputValue(optionId, factorId);
    const has = (v: any) => v !== undefined && v !== null && String(v).trim() !== '';
    const isQual = factor?.data_type === 'text' || factor?.factor_type === 'subjective' || factor?.factor_type === 'qualitative';
    if (!has(factor?.expected_value)) {
      Alert.alert(
        'Set an Expected value',
        isQual
          ? 'Add an Expected value for this qualitative factor so AI can assess against it.'
          : 'Add an Expected value (and Operator) for this quantitative factor before AI Assist.'
      );
      return;
    }
    if (!isQual) {
      if (!has(factor?.operator)) {
        Alert.alert('Set an Operator', 'Add an Operator (e.g. ≥) for this quantitative factor before AI Assist.');
        return;
      }
      if (!has(actual)) {
        Alert.alert(
          'Add an Actual value',
          'Quantitative factors need an Actual value. Enter it, set a Data Source, or link this option to a Solution Store item.'
        );
        return;
      }
    }
    setAiAssessBusy(prev => ({ ...prev, [key]: true }));
    try {
      const token = await AsyncStorage.getItem('session_token');
      const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
      const resp = await fetch(`${baseUrl}/api/decisions/${decision.id}/factors/${factorId}/ai-assess`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ option_id: optionId, actual_value: actual }),
      });
      if (!resp.ok) {
        const e = await resp.json().catch(() => ({}));
        if (resp.status === 402) {
          Alert.alert('Out of AI credits', e.detail || 'Top up your AI wallet to use AI Assist.', [
            { text: 'Not now', style: 'cancel' },
            { text: 'View wallet', onPress: () => router.push('/ai-wallet' as any) },
          ]);
          refreshAiWallet();
          return;
        }
        throw new Error(e.detail || `Failed (${resp.status})`);
      }
      const data = await resp.json();
      const pct = Math.max(0, Math.min(100, parseInt(String(data.percentage), 10) || 0));
      const unitStr = factor?.unit || '';
      // Prefer the AI-resolved actual (qualitative gap-fill) when the user left it blank.
      const effectiveActual = has(actual) ? actual : (data.actual_value != null ? String(data.actual_value) : '');
      const numericActual = parseFloat(effectiveActual);
      const displayValue = effectiveActual
        ? `${effectiveActual}${unitStr && !String(effectiveActual).includes(unitStr) ? ' ' + unitStr : ''}`
        : undefined;
      updateAssessment(optionId, factorId, pct, 'custom', displayValue, isNaN(numericActual) ? undefined : numericActual);
      setCustomInputValues(prev => ({ ...prev, [key]: String(pct) }));
      refreshAiWallet();
    } catch (err: any) {
      Alert.alert('AI assessment', err?.message || 'Could not auto-assess. Please enter % manually.');
    } finally {
      setAiAssessBusy(prev => ({ ...prev, [key]: false }));
    }
  };

  // ── "AI Assess All" — bulk metered assessment ───────────────────────────
  // Sequentially runs the same per-cell AI assist over every un-assessed cell.
  // Reusing the per-cell endpoint keeps each request small (no timeout risk)
  // and meters AI credits per cell, exactly like the single "AI" button.
  const [bulkAssessing, setBulkAssessing] = useState(false);
  const [bulkProgress, setBulkProgress] = useState<{ done: number; total: number }>({ done: 0, total: 0 });

  // Apply a single batch result to the local matrix state (instant UI update).
  const applyCellResult = (r: any) => {
    if (r.status !== 'done') return;
    const factor = decision.factors.find(f => f.id === r.factor_id);
    const pct = Math.max(0, Math.min(100, parseInt(String(r.percentage), 10) || 0));
    const unitStr = factor?.unit || '';
    const eff = r.actual_value != null ? String(r.actual_value) : '';
    const numericActual = parseFloat(eff);
    const displayValue = eff
      ? `${eff}${unitStr && !eff.includes(unitStr) ? ' ' + unitStr : ''}`
      : undefined;
    const key = getAssessmentKey(r.option_id, r.factor_id);
    updateAssessment(r.option_id, r.factor_id, pct, 'custom', displayValue, isNaN(numericActual) ? undefined : numericActual);
    setCustomInputValues(prev => ({ ...prev, [key]: String(pct) }));
  };

  // "AI Assess All" runs the cells in small server-side BATCHES (one request per
  // chunk) instead of dozens of individual POSTs. A burst of many requests can
  // be rejected by production edges/CDNs (405) and adds latency; batching keeps
  // it to a handful of requests while staying short enough to avoid timeouts.
  const runBulkAssess = async (cells: { optionId: string; factorId: string }[], forceFill: boolean = false) => {
    setBulkAssessing(true);
    setBulkProgress({ done: 0, total: cells.length });
    let done = 0, skipped = 0, errored = 0, ranOut = false, aiDown = false, processed = 0;
    const CHUNK = 6;
    for (let i = 0; i < cells.length; i += CHUNK) {
      const slice = cells.slice(i, i + CHUNK);
      try {
        const { data } = await api.post(`/decisions/${decision.id}/ai-assess-batch`, {
          force_fill: forceFill,
          cells: slice.map(c => ({
            option_id: c.optionId,
            factor_id: c.factorId,
            actual_value: getActualInputValue(c.optionId, c.factorId),
          })),
        });
        for (const r of (data.results || [])) {
          applyCellResult(r);
          if (r.status === 'done') done++;
          else if (r.status === 'skipped') skipped++;
          else errored++;
        }
        if (data.out_of_credits) { ranOut = true; processed += slice.length; setBulkProgress({ done: Math.min(processed, cells.length), total: cells.length }); break; }
        if (data.ai_unavailable) { aiDown = true; processed += slice.length; setBulkProgress({ done: Math.min(processed, cells.length), total: cells.length }); break; }
      } catch (e: any) {
        if (e?.response?.status === 402) { ranOut = true; break; }
        errored += slice.length;
      }
      processed += slice.length;
      setBulkProgress({ done: Math.min(processed, cells.length), total: cells.length });
    }
    setBulkAssessing(false);
    refreshAiWallet();
    // Final re-sync so the matrix + "All set" check reflect every saved cell.
    try { await fetchDecision(); } catch { /* non-fatal */ }
    if (ranOut) {
      showAlert('Out of AI credits', `Assessed ${done} cell(s) before credits ran out. Top up to finish the rest.`, [
        { text: 'Not now', style: 'cancel' },
        { text: 'View wallet', onPress: () => router.push('/ai-wallet' as any) },
      ]);
      return;
    }
    if (aiDown) {
      showAlert(
        'AI temporarily unavailable',
        `Assessed ${done} cell(s), then the AI service stopped responding. This usually means the Universal LLM key balance/budget is exhausted. ` +
        `Add balance (Profile → Universal Key → Add Balance) and try again — already-scored cells are saved.`,
      );
      return;
    }
    const parts = [`Assessed ${done} cell${done !== 1 ? 's' : ''}`];
    if (forceFill && done) parts[0] += ' (AI filled missing Expected/Actual)';
    if (skipped) parts.push(`${skipped} skipped (add Expected/Actual values)`);
    if (errored) parts.push(`${errored} failed`);
    showAlert('AI Assess All complete', parts.join(' • '));
  };

  // Split empty cells into those READY to assess (Expected present; quantitative
  // also has Operator + Actual) and those INCOMPLETE (missing Expected/Actual).
  const splitAssessCells = (cells: { optionId: string; factorId: string }[]) => {
    const has = (v: any) => v !== undefined && v !== null && String(v).trim() !== '';
    const ready: { optionId: string; factorId: string }[] = [];
    const incomplete: { optionId: string; factorId: string }[] = [];
    for (const c of cells) {
      const factor = decision.factors.find(f => f.id === c.factorId);
      if (!factor) continue;
      const isQual = factor?.data_type === 'text' || factor?.factor_type === 'subjective' || factor?.factor_type === 'qualitative';
      const actual = getActualInputValue(c.optionId, c.factorId);
      const bad = !has(factor?.expected_value) || (!isQual && (!has(factor?.operator) || !has(actual)));
      (bad ? incomplete : ready).push(c);
    }
    return { ready, incomplete };
  };

  const handleAIAssessAll = () => {
    if (bulkAssessing) return;
    const options = decision.options || [];
    const factors = decision.factors || [];
    const cells: { optionId: string; factorId: string }[] = [];
    for (const opt of options) {
      for (const f of factors) {
        const existing = getAssessmentValue(opt.id, f.id);
        if (existing === null || existing === undefined) cells.push({ optionId: opt.id, factorId: f.id });
      }
    }
    if (options.length === 0 || factors.length === 0) {
      showAlert('Nothing to assess', 'Add options and factors first.');
      return;
    }
    if (cells.length === 0) {
      showAlert('All set', 'Every option is already assessed against every factor.');
      return;
    }

    const { ready, incomplete } = splitAssessCells(cells);

    // No gaps → the simple confirm (unchanged behaviour).
    if (incomplete.length === 0) {
      showAlert(
        'AI Assess All',
        `AI will assess ${ready.length} empty cell${ready.length > 1 ? 's' : ''} across ${options.length} option${options.length > 1 ? 's' : ''}, using your AI credits. Continue?`,
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Assess', onPress: () => runBulkAssess(ready, false) },
        ]
      );
      return;
    }

    // There are gaps → let the user choose how to handle them.
    const buttons: any[] = [{ text: 'Cancel', style: 'cancel' }];
    if (ready.length > 0) {
      buttons.push({
        text: 'Ready only',
        onPress: () => runBulkAssess(ready, false),
      });
    }
    buttons.push({
      text: 'AI-fill all',
      onPress: () => runBulkAssess(cells, true),
    });
    showAlert(
      'AI Assess All',
      `${ready.length} cell${ready.length !== 1 ? 's are' : ' is'} ready to assess. ` +
      `${incomplete.length} cell${incomplete.length !== 1 ? 's are' : ' is'} missing Expected/Actual values.\n\n` +
      `Choose “AI-fill all” to let AI set a standard Expected value and estimate a realistic Actual for those too — this uses more AI credits.`,
      buttons
    );
  };

  const getCustomInputValue = (optionId: string, factorId: string): string => {
    const key = getAssessmentKey(optionId, factorId);
    if (customInputValues[key] !== undefined) return customInputValues[key];
    const value = getAssessmentValue(optionId, factorId);
    return value !== null ? String(value) : '';
  };

  const renderFactorAssessment = (option: { id: string }, f: Factor, indent: boolean = false, parentRating?: number) => {
    const key = getAssessmentKey(option.id, f.id);
    const currentMode = getAssessmentMode(option.id, f.id);
    const currentValue = getAssessmentValue(option.id, f.id);
    const isCustom = showCustomInput[key] || currentMode === 'custom';
    const hasValue = currentValue !== null;

    return (
      <View key={f.id} style={[styles.assessmentFactorContainer, indent && { marginLeft: 12, paddingLeft: 10, borderLeftWidth: 2, borderLeftColor: COLORS.border }]}>
        <View style={styles.assessmentLabelRow}>
          {indent && <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: COLORS.primary, marginRight: 6 }} />}
          <Text style={[styles.assessmentLabel, indent && { fontSize: 13 }]}>{f.name}</Text>
          {f.unit && (
            <View style={styles.factorUnitBadge}>
              <Text style={styles.factorUnitBadgeText}>{f.unit}</Text>
            </View>
          )}
          {f.expected_value !== undefined && f.expected_value !== null && (
            <View style={styles.expectedCriteriaBadge}>
              <Text style={styles.expectedCriteriaText}>
                {f.operator || '≥'} {String(f.expected_value)}{f.unit ? ` ${f.unit}` : ''}
              </Text>
            </View>
          )}
          {indent && f.weight ? (
            <View style={{ backgroundColor: '#EDE9FE', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 6, marginLeft: 4 }}>
              <Text style={{ fontSize: 10, color: COLORS.primary, fontWeight: '600' }}>{f.weight}%</Text>
            </View>
          ) : null}
          {!indent && parentRating !== undefined && <Text style={styles.assessmentRating}>({parentRating})</Text>}
        </View>

        <View style={styles.actualValueRow}>
          <View style={styles.actualValueInputWrap}>
            <TextInput
              style={styles.actualValueInput}
              placeholder={
                f.data_type === 'text'
                  ? `Enter ${f.name.toLowerCase()} value`
                  : f.unit ? `Value in ${f.unit}` : 'Actual value (optional)'
              }
              placeholderTextColor={COLORS.textMuted}
              value={getActualInputValue(option.id, f.id)}
              onChangeText={(value) => handleUnitValueChange(option.id, f.id, value)}
              onBlur={() => handleActualValueBlur(option.id, f.id)}
              keyboardType={f.data_type === 'text' ? 'default' : 'decimal-pad'}
            />
            {f.unit ? (
              <View style={styles.unitSuffix}>
                <Text style={styles.unitSuffixText}>{f.unit}</Text>
              </View>
            ) : null}
          </View>
        </View>

        <View style={styles.lmhContainer}>
          <TouchableOpacity
            style={[styles.lmhButton, { borderColor: LMH_VALUES.L.color }, currentMode === 'L' && { backgroundColor: LMH_VALUES.L.color }]}
            onPress={() => handleLMHSelect(option.id, f.id, 'L')}
          >
            <Text style={[styles.lmhText, { color: currentMode === 'L' ? COLORS.white : LMH_VALUES.L.color }]}>L</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.lmhButton, { borderColor: LMH_VALUES.M.color }, currentMode === 'M' && { backgroundColor: LMH_VALUES.M.color }]}
            onPress={() => handleLMHSelect(option.id, f.id, 'M')}
          >
            <Text style={[styles.lmhText, { color: currentMode === 'M' ? COLORS.white : LMH_VALUES.M.color }]}>M</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.lmhButton, { borderColor: LMH_VALUES.H.color }, currentMode === 'H' && { backgroundColor: LMH_VALUES.H.color }]}
            onPress={() => handleLMHSelect(option.id, f.id, 'H')}
          >
            <Text style={[styles.lmhText, { color: currentMode === 'H' ? COLORS.white : LMH_VALUES.H.color }]}>H</Text>
          </TouchableOpacity>

          {isCustom ? (
            <View style={[styles.customInputContainer, { backgroundColor: COLORS.primary }]}>
              <TextInput
                style={[styles.customPercentInput, { color: COLORS.white }]}
                value={getCustomInputValue(option.id, f.id)}
                onChangeText={(text) => handleCustomInputChange(option.id, f.id, text)}
                onBlur={() => handleCustomInputBlur(option.id, f.id)}
                keyboardType="numeric"
                maxLength={3}
                placeholderTextColor="rgba(255,255,255,0.6)"
                placeholder="0"
              />
              <Text style={[styles.customPercentSign, { color: COLORS.white }]}>%</Text>
            </View>
          ) : (
            <TouchableOpacity
              style={[styles.lmhButton, styles.customButton, currentMode === 'custom' && styles.customButtonActive]}
              onPress={() => handleCustomSelect(option.id, f.id)}
            >
              <Text style={[styles.lmhText, { color: currentMode === 'custom' ? COLORS.white : COLORS.primary }]}>%</Text>
            </TouchableOpacity>
          )}

          <TouchableOpacity
            style={[styles.lmhButton, styles.customButton, { borderColor: '#7C3AED', flexDirection: 'row', gap: 2, paddingHorizontal: 6, minWidth: 40 }]}
            onPress={() => handleAIAssess(option.id, f.id)}
            disabled={!!aiAssessBusy[key]}
            testID={`md-ai-${option.id}-${f.id}`}
          >
            {aiAssessBusy[key] ? (
              <ActivityIndicator size="small" color="#7C3AED" />
            ) : (
              <>
                <Ionicons name="sparkles" size={11} color="#7C3AED" />
                <Text style={[styles.lmhText, { color: '#7C3AED' }]}>AI</Text>
              </>
            )}
          </TouchableOpacity>

          <View style={[
            styles.currentValueBadge,
            !hasValue && styles.currentValueBadgeEmpty,
            currentMode === 'auto' && styles.currentValueBadgeAuto,
          ]}>
            {hasValue ? (
              <View style={styles.percentBadgeInner}>
                {currentMode === 'auto' && <Ionicons name="flash" size={10} color={'#6366F1'} />}
                <Text style={[styles.currentValueText, currentMode === 'auto' && styles.currentValueTextAuto]}>{currentValue}%</Text>
              </View>
            ) : (
              <Text style={styles.currentValueTextEmpty}>--</Text>
            )}
          </View>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 6-7: Assess & Calculate</Text>
      <Text style={styles.stepDescription}>
        Rate how well each option satisfies each factor using quick LMH toggles or specific percentage.
      </Text>

      <View style={[mdXls.bar, { flexWrap: 'wrap' }]}>
        <TouchableOpacity style={mdXls.btn} onPress={handleDownloadTemplate} disabled={xlsBusy} testID="md-xls-download">
          <Ionicons name="download-outline" size={15} color="#1F6FEB" />
          <Text style={mdXls.btnText}>Download XLS</Text>
        </TouchableOpacity>
        <TouchableOpacity style={mdXls.btn} onPress={handleImportTemplate} disabled={xlsBusy} testID="md-xls-import">
          {xlsBusy ? <ActivityIndicator size="small" color="#1F6FEB" /> : <Ionicons name="cloud-upload-outline" size={15} color="#1F6FEB" />}
          <Text style={mdXls.btnText}>Import XLS</Text>
        </TouchableOpacity>
        <TouchableOpacity style={mdXls.btn} onPress={handleCreateGsheet} disabled={xlsBusy} testID="md-gsheet-create">
          <Ionicons name="logo-google" size={15} color="#0F9D58" />
          <Text style={[mdXls.btnText, { color: '#0F9D58' }]}>Google Sheet</Text>
        </TouchableOpacity>
        <TouchableOpacity style={mdXls.btn} onPress={handleImportGsheet} disabled={xlsBusy} testID="md-gsheet-import">
          {xlsBusy ? <ActivityIndicator size="small" color="#0F9D58" /> : <Ionicons name="cloud-download-outline" size={15} color="#0F9D58" />}
          <Text style={[mdXls.btnText, { color: '#0F9D58' }]}>Import Sheet</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[mdXls.btn, { borderColor: '#C7B3FF', backgroundColor: '#F5F3FF' }]} onPress={() => setActualsDialogOpen(true)} disabled={actualsBusy} testID="md-import-actuals-url">
          {actualsBusy ? <ActivityIndicator size="small" color="#7C3AED" /> : <Ionicons name="link" size={15} color="#7C3AED" />}
          <Text style={[mdXls.btnText, { color: '#7C3AED' }]}>Import from URL</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.voiceInputRow}>
        <View style={styles.voiceHintBox}>
          <Ionicons name="mic-outline" size={16} color={COLORS.primary} />
          <Text style={styles.voiceHint}>Use the Voice Input button below to speak commands like “Salary High” or “All Medium”</Text>
        </View>
      </View>

      <Card style={styles.legendCard}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <Text style={[styles.legendTitle, { marginBottom: 0 }]}>Assessment Legend</Text>
          <AiCreditsBadge compact autoRefresh />
        </View>
        <View style={styles.legendRow}>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: LMH_VALUES.L.color }]} />
            <Text style={styles.legendText}>L = Low (25%)</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: LMH_VALUES.M.color }]} />
            <Text style={styles.legendText}>M = Medium (50%)</Text>
          </View>
          <View style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: LMH_VALUES.H.color }]} />
            <Text style={styles.legendText}>H = High (75%)</Text>
          </View>
        </View>

        {/* One-tap metered AI assessment of every empty option×factor cell. */}
        <TouchableOpacity
          style={[styles.aiAssessAllBtn, bulkAssessing && styles.aiAssessAllBtnBusy]}
          onPress={handleAIAssessAll}
          disabled={bulkAssessing}
          activeOpacity={0.85}
          testID="ai-assess-all"
        >
          {bulkAssessing ? (
            <>
              <ActivityIndicator size="small" color="#FFF" />
              <Text style={styles.aiAssessAllText}>Assessing {bulkProgress.done}/{bulkProgress.total}…</Text>
            </>
          ) : (
            <>
              <Ionicons name="sparkles" size={16} color="#FFF" />
              <Text style={styles.aiAssessAllText}>AI Assess All</Text>
            </>
          )}
        </TouchableOpacity>
        <Text style={styles.aiAssessAllHint}>
          Auto-rates every empty cell with AI. Uses AI credits • skips cells missing Expected/Actual values.
        </Text>
      </Card>

      {decision.options.map((option) => {
        const dynamicWorth = calculateDynamicWorth(option);
        return (
          <Card key={option.id} style={styles.assessmentCard}>
            <View style={styles.assessmentHeader}>
              <Text style={styles.optionName}>{option.name}</Text>
              <View style={[styles.worthBadge, dynamicWorth.assessedCount === 0 && styles.worthBadgeEmpty]}>
                {dynamicWorth.assessedCount > 0 ? (
                  <Text style={styles.worthText}>{dynamicWorth.worth.toFixed(1)}%</Text>
                ) : (
                  <Text style={styles.worthTextEmpty}>--</Text>
                )}
              </View>
            </View>
            <View style={styles.assessmentProgress}>
              <Text style={styles.progressText}>{dynamicWorth.assessedCount}/{dynamicWorth.totalCount} factors rated</Text>
              {/* Fetch Data button */}
              {decision.factors.some(f => !f.parent_id && f.data_source?.type) && (
                <TouchableOpacity
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#EDE9FE', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 }}
                  onPress={() => fetchFactorData(option.id, option.name)}
                  disabled={fetchingData[`option_${option.id}`]}
                >
                  {fetchingData[`option_${option.id}`] ? (
                    <ActivityIndicator size="small" color={COLORS.primary} />
                  ) : (
                    <Ionicons name="cloud-download-outline" size={14} color={COLORS.primary} />
                  )}
                  <Text style={{ fontSize: 11, fontWeight: '600', color: COLORS.primary }}>
                    {fetchingData[`option_${option.id}`] ? 'Fetching...' : 'Auto-Fetch'}
                  </Text>
                </TouchableOpacity>
              )}
            </View>

            {/* Fetch from Solutions Store button - for options linked to a solution */}
            {option.solution_id && (
              <TouchableOpacity
                style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#ECFDF5', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, marginBottom: 8, borderWidth: 1, borderColor: '#A7F3D0' }}
                onPress={() => fetchFromSolutionStore(option.id, option.solution_id!)}
                disabled={fetchingStore[`store_${option.id}`]}
              >
                {fetchingStore[`store_${option.id}`] ? (
                  <ActivityIndicator size="small" color="#059669" />
                ) : (
                  <Ionicons name="storefront" size={14} color="#059669" />
                )}
                <Text style={{ fontSize: 12, fontWeight: '600', color: '#059669', flex: 1 }}>
                  {fetchingStore[`store_${option.id}`] ? 'Fetching from Store...' : 'Auto-populate from Solutions Store & ReviewNet'}
                </Text>
                <Ionicons name="flash" size={14} color="#059669" />
              </TouchableOpacity>
            )}

            {decision.factors
              .filter(f => !f.parent_id)
              .sort((a, b) => b.rating - a.rating)
              .map((factor) => {
                const subs = decision.factors.filter(f => f.parent_id === factor.id).sort((a, b) => a.order - b.order);
                const hasSubs = subs.length > 0;

                const parentPct = hasSubs ? effectiveFactorPct(factor, decision.factors, option.assessments) : null;
                const anySubAssessed = hasSubs && subs.some(s => {
                  const sa = option.assessments.find(a => a.factor_id === s.id);
                  return sa?.percentage !== undefined && sa?.percentage !== null;
                });
                const directKey = `${option.id}_${factor.id}`;

                if (!hasSubs) return renderFactorAssessment(option, factor, false, factor.rating);

                return (
                  <View key={factor.id} style={styles.assessmentFactorContainer}>
                    <View style={[styles.assessmentLabelRow, { borderBottomWidth: 1, borderBottomColor: COLORS.border, paddingBottom: 6, marginBottom: 6 }]}>
                      <Ionicons name="git-branch-outline" size={14} color={COLORS.primary} style={{ marginRight: 4 }} />
                      <Text style={[styles.assessmentLabel, { fontWeight: '700' }]}>{factor.name}</Text>
                      <Text style={styles.assessmentRating}>({factor.rating})</Text>
                      <View style={[
                        styles.currentValueBadge,
                        parentPct === null && styles.currentValueBadgeEmpty,
                        parentPct !== null && { backgroundColor: '#EDE9FE' },
                      ]}>
                        {parentPct !== null ? (
                          <View style={styles.percentBadgeInner}>
                            <Ionicons name="calculator-outline" size={10} color={COLORS.primary} />
                            <Text style={[styles.currentValueText, { color: COLORS.primary, fontWeight: '700' }]}>{parentPct}%</Text>
                          </View>
                        ) : (
                          <Text style={styles.currentValueTextEmpty}>--</Text>
                        )}
                      </View>
                    </View>
                    {subs.map((sub) => renderFactorAssessment(option, sub, true))}

                    {/* General (direct) assessment fallback — used only when no  */}
                    {/* sub-factor above is rated. Keeps sub-factor rating optional. */}
                    <TouchableOpacity
                      onPress={() => setDirectOpen(o => ({ ...o, [directKey]: !o[directKey] }))}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 6, marginTop: 2 }}
                      accessibilityLabel={`Assess ${factor.name} directly`}
                    >
                      <Ionicons name={directOpen[directKey] ? 'chevron-down' : 'chevron-forward'} size={13} color={COLORS.textMuted} />
                      <Text style={{ fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic', flex: 1 }}>
                        Or assess “{factor.name}” directly{anySubAssessed ? ' (ignored — sub-factors are rated)' : ' (used as general assessment)'}
                      </Text>
                    </TouchableOpacity>
                    {directOpen[directKey] && (
                      <View style={anySubAssessed ? { opacity: 0.5 } : undefined}>
                        {renderFactorAssessment(option, factor, false)}
                      </View>
                    )}
                  </View>
                );
              })}
          </Card>
        );
      })}

      <View style={styles.navButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(6)}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        <GradientButton title="View Results" onPress={() => setCurrentStep(8)} style={styles.nextButton} />
      </View>

      {/* URL dialog — collects the link, then opens the consent gate */}
      <Modal visible={actualsDialogOpen} transparent animationType="fade" onRequestClose={() => setActualsDialogOpen(false)}>
        <View style={urlDlg.overlay}>
          <View style={urlDlg.dlg}>
            <Text style={urlDlg.title}>Import actual values from a URL</Text>
            <Text style={urlDlg.sub}>
              Paste a product or comparison page. We&apos;ll extract the actual values for your existing
              factors, then AI-score them automatically. You&apos;ll confirm your access rights next.
            </Text>
            <TextInput
              testID="md-actuals-url-input"
              style={urlDlg.input}
              placeholder="https://… product or comparison page"
              placeholderTextColor="#9CA3AF"
              value={actualsUrl}
              onChangeText={setActualsUrl}
              autoCapitalize="none"
              keyboardType="url"
              autoFocus
            />
            <View style={urlDlg.btns}>
              <TouchableOpacity style={urlDlg.cancel} onPress={() => setActualsDialogOpen(false)}>
                <Text style={urlDlg.cancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity testID="md-actuals-url-continue" style={urlDlg.go} onPress={submitActualsDialog}>
                <Text style={urlDlg.goText}>Continue</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      <UrlAccessConsentModal
        visible={urlActualsOpen}
        url={actualsUrl.trim()}
        busy={actualsBusy}
        primary="#7C3AED"
        onCancel={() => { if (!actualsBusy) setUrlActualsOpen(false); }}
        onConfirm={runImportActuals}
      />
    </View>
  );
}

const mdXls = StyleSheet.create({
  bar: { flexDirection: 'row', gap: 8, marginBottom: 12, flexWrap: 'wrap' },
  btn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#BBD6FF', backgroundColor: '#EFF6FF' },
  btnText: { fontSize: 12.5, fontWeight: '700', color: '#1F6FEB' },
});

const urlDlg = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center', padding: 24 },
  dlg: { width: '100%', maxWidth: 440, backgroundColor: '#fff', borderRadius: 16, padding: 20 },
  title: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary },
  sub: { fontSize: 12, lineHeight: 17, color: COLORS.textMuted, marginTop: 6, marginBottom: 12 },
  input: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11, fontSize: 14, color: COLORS.textPrimary },
  btns: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 16 },
  cancel: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 10 },
  cancelText: { fontSize: 13.5, fontWeight: '700', color: COLORS.textMuted },
  go: { backgroundColor: '#7C3AED', paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10, minWidth: 96, alignItems: 'center' },
  goText: { color: '#fff', fontSize: 13.5, fontWeight: '800' },
});
