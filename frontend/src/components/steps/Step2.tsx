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
import ImportReviewModal from '../ImportReviewModal';
import ImportCreditsStrip from '../ImportCreditsStrip';
import DeepImport from './DeepImport';
import TrainAIPanel from '../TrainAIPanel';
import { downloadAssessmentTemplate, importAssessmentTemplate } from '../../utils/assessmentXlsx';
import {
  UNIT_PRESETS,
  NUMERIC_OPERATORS,
  TEXT_OPERATORS,
  senseDataType,
  parseCountInput,
} from '../../utils/decisionHelpers';
import LoaderMusicChip from '../LoaderMusicChip';
import { useAiTouchpoint } from '../../utils/aiEstimates';
import DecisionLinkPicker from '../DecisionLinkPicker';
import { useRouter } from 'expo-router';
import { pickAndReadFile, PickedFile } from '../../utils/filePick';
import { uploadFileChunked, MAX_UPLOAD_BYTES, MAX_UPLOAD_LABEL } from '../../utils/chunkUpload';

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
    setHighlightOptionName,
    fetchDecision,
  } = useDecision();

  const [showDataSourceConfig, setShowDataSourceConfig] = useState<{ [key: string]: boolean }>({});
  const aiBestFactorsEnabled = useAiTouchpoint('tp_best_factors');
  const [linkPickerOpen, setLinkPickerOpen] = useState(false);
  const router = useRouter();

  // Open the linked target decision in a new flow view.
  const openLinkedDecision = (factor: Factor) => {
    const id = factor.data_source?.config?.linked_decision_id;
    if (id) router.push(`/prr/${id}` as any);
  };
  // Manual refresh of a single linked factor's value from its target.
  const refreshLinkedFactor = async (factor: Factor) => {
    try {
      const r = await api.post(`/decisions/${decision.id}/links/${factor.id}/resolve`);
      if (r.data?.ok === false) {
        showAlert('Not yet scored', 'The linked decision has no scored options yet.');
        return;
      }
      await fetchDecision();
      if (r.data?.changed) showAlert('Updated', `Value refreshed to ${r.data.new}%.`);
    } catch {
      showAlert('Refresh failed', 'Could not refresh the linked value.');
    }
  };

  // ── "Import from URL" — crawl a comparison page → fill factors (with Expected),
  // options (Step 6) and partial assessments (Step 7), behind the consent gate.
  const [importUrl, setImportUrl] = useState('');
  const [importTier, setImportTier] = useState<'fast' | 'precise'>('fast');
  const [importConsentOpen, setImportConsentOpen] = useState(false);
  const [importing, setImporting] = useState(false);

  // ── Optional accuracy hints — verified server-side with one self-healing
  // corrective retry when the extraction mismatches them. All optional.
  const [hintsOpen, setHintsOpen] = useState(true);
  const [hintFactorCount, setHintFactorCount] = useState('');
  const [hintOptionCount, setHintOptionCount] = useState('');
  const [hintFirstFactor, setHintFirstFactor] = useState('');
  const [hintFirstOption, setHintFirstOption] = useState('');

  // ── 1-tap import accuracy feedback (👍/👎) — labels the telemetry run that
  // powers the admin Import-Analytics learning loop. ──
  const [importFeedback, setImportFeedback] = useState<{ runId: string; voted: 'up' | 'down' | null } | null>(null);
  const [trainPanelOpen, setTrainPanelOpen] = useState(false);

  const sendImportFeedback = async (verdict: 'up' | 'down') => {
    if (!importFeedback) return;
    setImportFeedback({ ...importFeedback, voted: verdict });
    // Auto-open the Train AI panel on 👎 so the user can pinpoint the exact
    // factor / option / cell-level issue while still looking at Step 2.
    if (verdict === 'down') setTrainPanelOpen(true);
    try {
      await api.post(`/url-analyze/runs/${importFeedback.runId}/feedback`, { verdict });
    } catch { /* non-fatal — verdict already reflected in UI */ }
  };

  // ── Provenance ("Source quotes"): the exact page line each imported value
  // came from — page-grounding transparency (ex-showroom vs on-road etc.). ──
  const [provenance, setProvenance] = useState<{ open: boolean; loading: boolean; items: any[]; verification: any } | null>(null);

  const openProvenance = async () => {
    if (!importFeedback) return;
    setProvenance({ open: true, loading: true, items: [], verification: {} });
    try {
      const { data } = await api.get(`/url-analyze/runs/${importFeedback.runId}/provenance`);
      setProvenance({ open: true, loading: false, items: data.evidence || [], verification: data.verification || {} });
    } catch {
      setProvenance({ open: true, loading: false, items: [], verification: {} });
    }
  };

  // ── Live import progress — backend reports real stages to
  // /url-analyze/progress/{id}; we poll while the import POST is in flight. ──
  const [importProgress, setImportProgress] = useState<{ pct: number; label: string; elapsed: number } | null>(null);

  // ── Review-before-merge for AI-conversation imports (ChatGPT/Claude/Gemini):
  // the backend returns the detected factors/options as a PREVIEW; the user
  // trims/renames them in a modal, then we merge the reviewed list (free). ──
  const [reviewItems, setReviewItems] = useState<{ factors: string[]; options: string[] } | null>(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const isConversationShare = (u: string) => {
    const s = (u || '').toLowerCase();
    return /(chatgpt\.com|chat\.openai\.com|claude\.ai|gemini\.google\.com|g\.co|poe\.com)/.test(s)
      && /(\/share\/|\/c\/|\/g\/)/.test(s);
  };

  const confirmReviewedImport = async (factors: string[], options: string[]) => {
    setReviewBusy(true);
    try {
      const { data } = await api.post(
        `/url-analyze/decision/${decision.id}/import/confirm`, { factors, options });
      void data;
      await fetchDecision();
      setReviewItems(null);
      // Auto-jump to Step 6 (Options) and spotlight the top-ranked option so the
      // user immediately sees their reordered priority in context.
      const topOption = options.find(o => o && o.trim());
      if (topOption) setHighlightOptionName(topOption.trim());
      setCurrentStep(6);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Could not add the reviewed items.';
      showAlert('Could not add', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setReviewBusy(false);
    }
  };

  const runImport = async (consent: UrlConsentPayload) => {
    const progressId = `imp_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    setImportConsentOpen(false);
    setImporting(true);
    const startedAt = Date.now();
    setImportProgress({ pct: 5, label: 'Starting…', elapsed: 0 });
    const poll = setInterval(async () => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      try {
        const { data } = await api.get(`/url-analyze/progress/${progressId}`);
        setImportProgress(p => p
          ? { pct: Math.max(p.pct, data?.pct || 0), label: data?.label || p.label, elapsed }
          : p);
      } catch {
        setImportProgress(p => (p ? { ...p, elapsed } : p));
      }
    }, 1200);
    try {
      const { data } = await api.post(`/url-analyze/decision/${decision.id}/import`, {
        url: importUrl.trim(),
        eligibility_type: consent.eligibility_type,
        custom_note: consent.custom_note,
        accepted: true,
        ai_tier: importTier,
        progress_id: progressId,
        preview: isConversationShare(importUrl.trim()),
        expected_factor_count: parseCountInput(hintFactorCount),
        expected_option_count: parseCountInput(hintOptionCount),
        first_factor_name: hintFirstFactor.trim() || undefined,
        first_option_name: hintFirstOption.trim() || undefined,
      }, { timeout: 300000 }); // detail pages may need a rendered fetch + LLM pass (+1 retry)
      // AI-conversation imports return a PREVIEW — open the review modal instead
      // of writing straight to the decision.
      if (data.mode === 'conversation_preview') {
        setImportUrl('');
        setImportProgress(null);
        setImportConsentOpen(false);
        setReviewItems({ factors: data.factors || [], options: data.options || [] });
        return;
      }
      setImportUrl('');
      await fetchDecision();
      if (data.run_id) setImportFeedback({ runId: data.run_id, voted: null });
      const warn = (data.hint_warnings || []).length
        ? `\n\n⚠ Accuracy check: ${data.hint_warnings.join(' ')} Please review carefully.`
        : '';
      const ver = data.verification || {};
      const verNote = (ver.blanked || 0) > 0
        ? `\n\n⚠ Page-grounding check: ${ver.blanked} cell value${ver.blanked === 1 ? '' : 's'} (factor × option) could NOT be verified on the page text and ${ver.blanked === 1 ? 'was' : 'were'} left BLANK${(ver.unverified || []).length ? ` — ${(ver.unverified || []).slice(0, 5).join('; ')}` : ''}. Fill them manually in Step 7.`
        : (ver.verified || 0) > 0
          ? `\n\n✓ Page-grounding check: all ${ver.verified} cell values (factor × option) are traceable to the page text. Tap “Source quotes” under the import card to see the exact page line behind every value.`
          : '';
      // Localised-pricing note is now its OWN loud follow-up alert
      // (destructive style → red icon + accent) — money values are the
      // #1 source of confusion. We fire it immediately AFTER the success
      // alert is dismissed. Backend only sets `geo_note` when the import
      // actually contains money cells (factor implies money OR cell carries
      // a currency symbol), so non-monetary use cases (property specs,
      // gadget tables, education comparisons) won't see this alert.
      const showGeoAlert = () => {
        if (!data.geo_note) return;
        setTimeout(() => {
          showAlert(
            '💰 Heads up — prices may differ in your case',
            'Money values were read from the page\u2019s DEFAULT (non-localised) view. The amounts you see can differ based on your city, account, plan, taxes or any active offer (e.g. on-road vs ex-showroom, taxable vs after-tax salary, listed rent vs final negotiated rent). Tap “Source quotes” under the import card to see the exact page line behind each number, then refine cash factors in Step 7.',
            [{ text: 'Got it', style: 'destructive' }],
          );
        }, 250);
      };
      const dismissBtns = [{ text: 'OK', style: 'default' as const, onPress: showGeoAlert }];
      const expectedNote = '\n\nNote: Expected values are pre-suggested from the page data (best value of the set). Refine them anytime with “Set Expectations - By AI”, which re-evaluates against your decision context.';
      if (data.mode === 'detail') {
        const fellBack = importTier === 'precise' && data.ai_provider !== 'emergent_precise';
        const grouped = data.structure === 'hierarchical'
          ? ` grouped into ${data.category_count} categories (sub-factor weights split equally — editable)`
          : '';
        showAlert(
          'Imported from URL',
          `Detected a single-listing page — “${data.main_item}”. Added ${data.factors_added} factor${data.factors_added === 1 ? '' : 's'}${grouped} with smart operators & Expected values, plus ${data.options_added} option${data.options_added === 1 ? '' : 's'} (the listing + similar items). Review below, then continue — Options (Step 6) and actuals (Step 7) are pre-filled.${fellBack ? '\n\nNote: Precise AI was unavailable (check the Universal Key balance) — the Fast AI engine was used instead, billed at the normal rate.' : ''}${expectedNote}${verNote}${warn}`,
          dismissBtns,
        );
      } else {
        showAlert(
          'Imported from URL',
          `Added ${data.factors_added} factor${data.factors_added === 1 ? '' : 's'} and ${data.options_added} option${data.options_added === 1 ? '' : 's'} from ${data.item_count} items. Review the factors & Expected values below, then continue — Options (Step 6) and actuals (Step 7) are pre-filled.${expectedNote}${verNote}${warn}`,
          dismissBtns,
        );
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Could not import from this URL. Try a comparison page or a single item/listing detail page.';
      showAlert('Import failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      clearInterval(poll);
      setImportProgress(null);
      setImporting(false);
    }
  };

  // ── "Set Expectations - By AI" — enabled ONLY after a successful import has
  // filled factors (Step 2), options (Step 6) AND option values (Step 7).
  // One Claude-first call proposes Expected value + operator for every leaf
  // factor; everything stays user-overridable.
  const [settingExpectations, setSettingExpectations] = useState(false);
  const expFactorsOk = (decision.factors || []).length > 0;
  const expOptionsOk = (decision.options || []).length > 0;
  const expValuesOk = (decision.options || []).some((o: any) =>
    (o.assessments || []).some((a: any) => a.unit_value != null && a.unit_value !== ''));
  const canSetExpectations = expFactorsOk && expOptionsOk && expValuesOk;

  const runSetExpectations = async () => {
    setSettingExpectations(true);
    try {
      const { data } = await api.post(
        `/url-analyze/decision/${decision.id}/set-expectations`,
        { ai_tier: 'precise' }, { timeout: 120000 });
      await fetchDecision();
      const changed = data.changed ?? data.updated;
      const confirmed = data.confirmed ?? 0;
      showAlert(
        'Expectations set by AI',
        changed === 0
          ? `AI reviewed all ${data.factor_count} factors and CONFIRMED the existing Expected values — the import's page-based suggestions already match what AI recommends for your decision context.`
          : `AI reviewed ${data.factor_count} factors: CHANGED ${changed} expectation${changed === 1 ? '' : 's'} and confirmed ${confirmed} existing value${confirmed === 1 ? '' : 's'}, based on your decision context and the option values. Review and override any of them below.`,
      );
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Could not set expectations. Try again.';
      showAlert('Set Expectations failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSettingExpectations(false);
    }
  };

  // ── XLS / CSV / Google-Sheet matrix imports (Step-2) ──────────────────────
  const [importBusy, setImportBusy] = useState<'' | 'xls' | 'sheet' | 'tmpl'>('');
  const [urlDialogOpen, setUrlDialogOpen] = useState(false);
  const [sheetDialogOpen, setSheetDialogOpen] = useState(false);
  const [sheetUrl, setSheetUrl] = useState('');

  // ── "Import from File" — parse a doc/image → AI factors+options (+optional web crawl) ──
  const [fileDialogOpen, setFileDialogOpen] = useState(false);
  const [fileTier, setFileTier] = useState<'fast' | 'precise'>('fast');
  const [fileCrawl, setFileCrawl] = useState(false);
  const [fileContext, setFileContext] = useState('');
  const [fileBusy, setFileBusy] = useState(false);
  const [picked, setPicked] = useState<PickedFile | null>(null);

  const afterMatrixImport = async (data: any) => {
    await fetchDecision();
    showAlert(
      'Imported',
      `Added ${data.factors_added ?? 0} factor${(data.factors_added ?? 0) === 1 ? '' : 's'} and ` +
      `${data.options_added ?? 0} option${(data.options_added ?? 0) === 1 ? '' : 's'}. Review below, then continue.`,
    );
  };

  const handleDownloadTemplate = async () => {
    setImportBusy('tmpl');
    try {
      await downloadAssessmentTemplate(`/decisions/${decision.id}/factor-matrix-template.xlsx`, 'decision-matrix-template.xlsx');
    } catch (e: any) {
      showAlert('Download failed', e?.message || 'Could not download the template.');
    } finally {
      setImportBusy('');
    }
  };

  const handleUploadXls = async () => {
    setImportBusy('xls');
    try {
      const data = await importAssessmentTemplate(`/decisions/${decision.id}/import-matrix-file`);
      if (data) await afterMatrixImport(data);
    } catch (e: any) {
      showAlert('Import failed', e?.message || 'Could not read the file. Upload a .xlsx or .csv comparison matrix.');
    } finally {
      setImportBusy('');
    }
  };

  const runSheetImport = async () => {
    if (!/docs\.google\.com\/spreadsheets/i.test(sheetUrl.trim())) {
      showAlert('Paste a Google Sheet link', 'Use a Google Sheets URL (docs.google.com/spreadsheets/…).');
      return;
    }
    setImportBusy('sheet');
    try {
      const { data } = await api.post(`/decisions/${decision.id}/import-matrix-sheet`, { sheet_url: sheetUrl.trim() });
      setSheetDialogOpen(false);
      setSheetUrl('');
      await afterMatrixImport(data);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Could not import this Google Sheet.';
      showAlert('Import failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setImportBusy('');
    }
  };

  const choosePickFile = async () => {
    try {
      const f = await pickAndReadFile();
      if (!f) return;
      if (f.sizeBytes && f.sizeBytes > MAX_UPLOAD_BYTES) {
        showAlert('File too large', `That file is ${(f.sizeBytes / 1048576).toFixed(1)} MB. Please choose a file under ${MAX_UPLOAD_LABEL}.`);
        return;
      }
      setPicked(f);
    } catch (e: any) {
      showAlert('Could not read file', e?.message || 'Try another file.');
    }
  };

  const runFileImport = async () => {
    if (!picked) {
      showAlert('Pick a file', 'Choose a PDF, DOCX, TXT, XLS/CSV or image first.');
      return;
    }
    setFileBusy(true);
    try {
      const uploadId = await uploadFileChunked(picked);
      const { data } = await api.post(`/file-import/decision/${decision.id}`, {
        filename: picked.filename,
        upload_id: uploadId,
        ai_tier: fileTier,
        crawl_web: fileCrawl,
        context: fileContext.trim() || undefined,
      }, { timeout: 300000 });
      setFileDialogOpen(false);
      setPicked(null);
      setFileContext('');
      await fetchDecision();
      const topOption = (data.options || []).find((o: string) => o && o.trim());
      if (topOption) setHighlightOptionName(String(topOption).trim());
      const enrichedNote = data.enriched
        ? ` Web research enriched ${data.enriched_count} option${data.enriched_count === 1 ? '' : 's'} with extra detail.`
        : '';
      // Post-import: offer the existing metered, plan-capped "Fetch My Best Factors"
      // so AI can surface relevant factors the file missed (user's choice).
      showAlert(
        'Imported from file',
        `Added ${data.factors_added} factor${data.factors_added === 1 ? '' : 's'} and ${data.options_added} option${data.options_added === 1 ? '' : 's'} from your file.${enrichedNote}\n\nWould you like AI to also add any missed-out factors relevant to your context? It checks the web & your decision context (uses AI credits, capped by your plan).`,
        [
          { text: 'No — keep file factors', style: 'cancel' },
          { text: 'Yes — fetch best factors', onPress: () => { handleFetchBestFactors(); } },
        ],
      );
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Could not import from this file. Try a clearer file or add a context note.';
      showAlert('Import failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setFileBusy(false);
    }
  };


  const submitUrlDialog = () => {
    if (!/^https?:\/\/.+/i.test(importUrl.trim())) {
      showAlert('Enter a URL', 'Paste a valid http(s) link to a comparison or filter page.');
      return;
    }
    setUrlDialogOpen(false);
    setImportConsentOpen(true);
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

      {/* One-tap: AI-score every un-scored cell (e.g. a freshly imported comparison). */}
      {aiBestFactorsEnabled && (<>
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
      </>)}

      <TouchableOpacity
        testID="link-decision-btn"
        onPress={() => setLinkPickerOpen(true)}
        activeOpacity={0.85}
        style={{
          flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
          borderWidth: 1.5, borderColor: COLORS.primary, borderRadius: 12,
          paddingVertical: 12, paddingHorizontal: 16, marginBottom: 6, backgroundColor: '#F5F3FF',
        }}
      >
        <Ionicons name="git-network-outline" size={18} color={COLORS.primary} />
        <Text style={{ color: COLORS.primary, fontSize: 14.5, fontWeight: '800' }}>Link a Decision</Text>
      </TouchableOpacity>
      <Text style={{ fontSize: 11, color: COLORS.textMuted, textAlign: 'center', marginBottom: 14, lineHeight: 16, paddingHorizontal: 8 }}>
        Pull another scored decision's option result in as a factor (and optionally an option).
      </Text>

      <View style={iurl.box}>
        <View style={iurl.head}>
          <Ionicons name="cloud-upload-outline" size={15} color="#2563EB" />
          <Text style={iurl.title}>Import factors & options</Text>
        </View>
        <Text style={iurl.sub}>
          Bring in a comparison matrix from a spreadsheet or a web page — we&apos;ll add the factors
          (with suggested Expected values) and options, and pre-fill the assessment matrix.
        </Text>
        <View style={iurl.iconRow}>
          <TouchableOpacity testID="step2-import-xls" style={iurl.iconBtn} onPress={handleUploadXls} disabled={!!importBusy} activeOpacity={0.85}>
            {importBusy === 'xls' ? <ActivityIndicator size="small" color="#16A34A" /> : <Ionicons name="document-text-outline" size={22} color="#16A34A" />}
            <Text style={iurl.iconLabel}>XLS / CSV</Text>
          </TouchableOpacity>
          <TouchableOpacity testID="step2-import-sheet" style={iurl.iconBtn} onPress={() => setSheetDialogOpen(true)} disabled={!!importBusy} activeOpacity={0.85}>
            <Ionicons name="grid-outline" size={22} color="#0F9D58" />
            <Text style={iurl.iconLabel}>Google Sheet</Text>
          </TouchableOpacity>
          <TouchableOpacity testID="step2-import-url" style={iurl.iconBtn} onPress={() => setUrlDialogOpen(true)} disabled={!!importBusy || importing} activeOpacity={0.85}>
            <Ionicons name="link" size={22} color="#2563EB" />
            <Text style={iurl.iconLabel}>URL</Text>
          </TouchableOpacity>
          <TouchableOpacity testID="step2-import-file" style={iurl.iconBtn} onPress={() => setFileDialogOpen(true)} disabled={!!importBusy || fileBusy} activeOpacity={0.85}>
            {fileBusy ? <ActivityIndicator size="small" color="#7C3AED" /> : <Ionicons name="document-attach-outline" size={22} color="#7C3AED" />}
            <Text style={iurl.iconLabel}>File</Text>
          </TouchableOpacity>
        </View>
        <TouchableOpacity testID="step2-download-template" onPress={handleDownloadTemplate} disabled={!!importBusy} style={iurl.tmplLink}>
          <Ionicons name="download-outline" size={13} color="#2563EB" />
          <Text style={iurl.tmplText}>{importBusy === 'tmpl' ? 'Preparing…' : 'Download a fillable template (XLS)'}</Text>
        </TouchableOpacity>

        {/* Deep Import — opt-in multi-page crawl with factor-first review */}
        <DeepImport decisionId={decision.id} onMerged={fetchDecision} />
      </View>

      {/* 1-tap import accuracy verdict — appears after a URL import completes */}
      {importFeedback && (
        <View testID="import-feedback-row" style={{
          flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
          marginBottom: 14, paddingVertical: 9, paddingHorizontal: 14,
          backgroundColor: '#F0F9FF', borderRadius: 10, borderWidth: 1, borderColor: '#BAE6FD',
        }}>
          <Text style={{ fontSize: 12.5, color: '#0C4A6E', fontWeight: '600', flexShrink: 1 }}>
            {importFeedback.voted
              ? (importFeedback.voted === 'up'
                ? 'Thanks! Glad the import nailed it.'
                : 'Thanks — logged. We use this to tune extraction accuracy.')
              : 'Was this URL import accurate?'}
          </Text>
          {!importFeedback.voted && (
            <>
              <TouchableOpacity
                testID="import-feedback-up" activeOpacity={0.8}
                onPress={() => sendImportFeedback('up')}
                style={{ padding: 7, borderRadius: 8, backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0' }}>
                <Ionicons name="thumbs-up" size={15} color="#059669" />
              </TouchableOpacity>
              <TouchableOpacity
                testID="import-feedback-down" activeOpacity={0.8}
                onPress={() => sendImportFeedback('down')}
                style={{ padding: 7, borderRadius: 8, backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA' }}>
                <Ionicons name="thumbs-down" size={15} color="#DC2626" />
              </TouchableOpacity>
            </>
          )}
          <TouchableOpacity
            testID="import-view-sources" activeOpacity={0.8}
            onPress={openProvenance}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 4, padding: 7, borderRadius: 8, backgroundColor: '#EFF6FF', borderWidth: 1, borderColor: '#BFDBFE' }}>
            <Ionicons name="document-text-outline" size={14} color="#2563EB" />
            <Text style={{ fontSize: 11.5, fontWeight: '700', color: '#2563EB' }}>Source quotes</Text>
          </TouchableOpacity>
          {/* Train AI — opens an inline panel where the user can pinpoint the
              exact factor / option / option-factor cell with wrong/missing
              values. Always available, even after 👍 (so a user who's mostly
              happy but spotted one bad cell can still teach the AI). */}
          <TouchableOpacity
            testID="import-train-ai" activeOpacity={0.8}
            onPress={() => setTrainPanelOpen(v => !v)}
            style={{ flexDirection: 'row', alignItems: 'center', gap: 4, padding: 7, borderRadius: 8, backgroundColor: '#FFFBEB', borderWidth: 1, borderColor: '#FCD34D' }}>
            <Ionicons name={trainPanelOpen ? 'chevron-up' : 'school-outline'} size={14} color="#92400E" />
            <Text style={{ fontSize: 11.5, fontWeight: '800', color: '#92400E' }}>
              {trainPanelOpen ? 'Hide Train AI' : 'Train AI'}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Train AI — inline collapsible panel for structured user feedback */}
      {importFeedback && trainPanelOpen && (
        <TrainAIPanel
          runId={importFeedback.runId}
          decisionId={decision.id}
          factors={(decision.factors || []) as any}
          options={(decision.options || []) as any}
          onSaved={() => { /* keep open so user can confirm; allow re-edit */ }}
          onClose={() => setTrainPanelOpen(false)}
        />
      )}

      {/* "Set Expectations - By AI" — gated until import filled factors (Step 2),
          options (Step 6) and option values (Step 7). Always user-overridable. */}
      <TouchableOpacity
        testID="step2-set-expectations-ai"
        onPress={runSetExpectations}
        disabled={!canSetExpectations || settingExpectations}
        activeOpacity={0.85}
        style={[iurl.expectBtn, (!canSetExpectations || settingExpectations) && iurl.expectBtnDisabled]}
      >
        {settingExpectations
          ? <ActivityIndicator size="small" color="#FFF" />
          : <Ionicons name="options" size={17} color="#FFF" />}
        <Text style={iurl.expectBtnText}>
          {settingExpectations ? 'Setting expectations…' : 'Set Expectations - By AI'}
        </Text>
      </TouchableOpacity>
      <Text style={iurl.expectHint}>
        {canSetExpectations
          ? 'Imports pre-fill Expected values from the page (best value of the set). This button RE-EVALUATES them with AI using your decision context & the option values — results may match if the page suggestions were already ideal. You can override any value.'
          : 'Enabled after a successful import fills factors (Step 2), options (Step 6) and option values (Step 7).'}
      </Text>

      {/* URL dialog — collects the link, then opens the consent gate */}
      <Modal visible={urlDialogOpen} transparent animationType="fade" onRequestClose={() => setUrlDialogOpen(false)}>
        <View style={iurl.dlgOverlay}>
          <View style={iurl.dlg}>
            <Text style={iurl.dlgTitle}>Import from a URL</Text>
            <Text style={iurl.dlgSub}>Paste a comparison / filter page OR a single listing/product detail page. You&apos;ll confirm your access rights next.</Text>
            <TextInput
              testID="step2-import-url-input"
              style={[iurl.dlgInput, iurl.dlgInputHighlight]}
              placeholder="https://… comparison or listing page"
              placeholderTextColor="#9CA3AF"
              value={importUrl}
              onChangeText={setImportUrl}
              autoCapitalize="none"
              keyboardType="url"
              autoFocus
            />
            <Text style={iurl.tierLabel}>AI engine</Text>
            <View style={iurl.tierRow}>
              <TouchableOpacity
                testID="step2-ai-tier-fast"
                style={[iurl.tierBtn, importTier === 'fast' && iurl.tierBtnActive]}
                onPress={() => setImportTier('fast')}
                activeOpacity={0.85}
              >
                <Ionicons name="flash" size={15} color={importTier === 'fast' ? '#2563EB' : '#94A3B8'} />
                <View style={{ flex: 1 }}>
                  <Text style={[iurl.tierTxt, importTier === 'fast' && iurl.tierTxtActive]}>Cheap &amp; Fast AI</Text>
                  <Text style={iurl.tierHint}>Default · lowest credit cost</Text>
                </View>
                {importTier === 'fast' && <Ionicons name="checkmark-circle" size={16} color="#2563EB" />}
              </TouchableOpacity>
              <TouchableOpacity
                testID="step2-ai-tier-precise"
                style={[iurl.tierBtn, importTier === 'precise' && iurl.tierBtnActive]}
                onPress={() => setImportTier('precise')}
                activeOpacity={0.85}
              >
                <Ionicons name="diamond" size={15} color={importTier === 'precise' ? '#7C3AED' : '#94A3B8'} />
                <View style={{ flex: 1 }}>
                  <Text style={[iurl.tierTxt, importTier === 'precise' && { color: '#7C3AED' }]}>Costly &amp; Precise AI</Text>
                  <Text style={iurl.tierHint}>Claude-grade extraction · more credits</Text>
                </View>
                {importTier === 'precise' && <Ionicons name="checkmark-circle" size={16} color="#7C3AED" />}
              </TouchableOpacity>
            </View>
            <ImportCreditsStrip endpoint="import" tier={importTier} />

            {/* Optional accuracy hints — validated server-side with a corrective retry */}
            <TouchableOpacity testID="step2-import-hints-toggle" style={iurl.hintsToggle} onPress={() => setHintsOpen(!hintsOpen)} activeOpacity={0.8}>
              <Ionicons name={hintsOpen ? 'chevron-down' : 'chevron-forward'} size={14} color="#2563EB" />
              <Text style={iurl.hintsToggleText}>Boost accuracy (recommended, optional)</Text>
            </TouchableOpacity>
            {hintsOpen && (
              <View>
                <Text style={iurl.hintHelp}>Tell us what you see on the page — we verify the AI extraction against it and auto-correct mismatches. You can type a simple sum like <Text style={{ fontWeight: '700' }}>1+3</Text> (e.g. 1 main option + 3 similar) and it&apos;s evaluated for you.</Text>
                <View style={iurl.hintRow}>
                  <TextInput
                    testID="step2-hint-factor-count"
                    style={[iurl.dlgInput, iurl.hintInputSm]}
                    placeholder="Total # of factors (e.g. 8 or 2+6)"
                    placeholderTextColor="#9CA3AF"
                    value={hintFactorCount}
                    onChangeText={setHintFactorCount}
                  />
                  <TextInput
                    testID="step2-hint-option-count"
                    style={[iurl.dlgInput, iurl.hintInputSm]}
                    placeholder="Total # of options visible (main + similar)"
                    placeholderTextColor="#9CA3AF"
                    value={hintOptionCount}
                    onChangeText={setHintOptionCount}
                  />
                </View>
                <TextInput
                  testID="step2-hint-first-factor"
                  style={[iurl.dlgInput, iurl.hintInputFull]}
                  placeholder="First factor name, e.g. Rent (optional)"
                  placeholderTextColor="#9CA3AF"
                  value={hintFirstFactor}
                  onChangeText={setHintFirstFactor}
                />
                <TextInput
                  testID="step2-hint-first-option"
                  style={[iurl.dlgInput, iurl.hintInputFull]}
                  placeholder="First / main option name (optional)"
                  placeholderTextColor="#9CA3AF"
                  value={hintFirstOption}
                  onChangeText={setHintFirstOption}
                />
              </View>
            )}
            <View style={iurl.dlgBtns}>
              <TouchableOpacity style={iurl.dlgCancel} onPress={() => setUrlDialogOpen(false)}>
                <Text style={iurl.dlgCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity testID="step2-url-continue" style={iurl.dlgGo} onPress={submitUrlDialog}>
                <Text style={iurl.dlgGoText}>Continue</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Google Sheet dialog — paste a share link (public read, or your connected account) */}
      <Modal visible={sheetDialogOpen} transparent animationType="fade" onRequestClose={() => setSheetDialogOpen(false)}>
        <View style={iurl.dlgOverlay}>
          <View style={iurl.dlg}>
            <Text style={iurl.dlgTitle}>Import from Google Sheet</Text>
            <Text style={iurl.dlgSub}>Paste a Google Sheets link. Public/link-shared sheets work directly; private sheets use your connected Google account.</Text>
            <TextInput
              testID="step2-sheet-url-input"
              style={iurl.dlgInput}
              placeholder="https://docs.google.com/spreadsheets/…"
              placeholderTextColor="#9CA3AF"
              value={sheetUrl}
              onChangeText={setSheetUrl}
              autoCapitalize="none"
              keyboardType="url"
              autoFocus
            />
            <View style={iurl.dlgBtns}>
              <TouchableOpacity style={iurl.dlgCancel} onPress={() => { setSheetDialogOpen(false); setSheetUrl(''); }}>
                <Text style={iurl.dlgCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity testID="step2-sheet-import" style={iurl.dlgGo} onPress={runSheetImport} disabled={importBusy === 'sheet'}>
                {importBusy === 'sheet' ? <ActivityIndicator size="small" color="#fff" /> : <Text style={iurl.dlgGoText}>Import</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Import from File dialog — pdf/docx/txt/xls(x)/csv/image → AI factors+options */}
      <Modal visible={fileDialogOpen} transparent animationType="fade" onRequestClose={() => setFileDialogOpen(false)}>
        <View style={iurl.dlgOverlay}>
          <View style={iurl.dlg}>
            <Text style={iurl.dlgTitle}>Import from File</Text>
            <Text style={iurl.dlgSub}>Upload a PDF, Word, Excel/CSV, text or image file. AI extracts your factors &amp; options — great for VC lists, comparison sheets or profiles.</Text>

            <TouchableOpacity testID="step2-file-pick" style={ifile.pickBtn} onPress={choosePickFile} activeOpacity={0.85}>
              <Ionicons name={picked ? 'document-text' : 'cloud-upload-outline'} size={20} color="#7C3AED" />
              <Text style={ifile.pickTxt} numberOfLines={1}>
                {picked ? picked.filename : 'Choose a file…'}
              </Text>
              {picked ? <Ionicons name="checkmark-circle" size={18} color="#10B981" /> : null}
            </TouchableOpacity>
            <Text style={ifile.types}>PDF · DOCX · TXT · XLSX/XLS · CSV · JPG/PNG (max 8 MB)</Text>

            <Text style={iurl.tierLabel}>AI engine</Text>
            <View style={iurl.tierRow}>
              <TouchableOpacity
                testID="step2-file-tier-fast"
                style={[iurl.tierBtn, fileTier === 'fast' && iurl.tierBtnActive]}
                onPress={() => setFileTier('fast')}
                activeOpacity={0.85}
              >
                <Ionicons name="flash" size={15} color={fileTier === 'fast' ? '#2563EB' : '#94A3B8'} />
                <View style={{ flex: 1 }}>
                  <Text style={[iurl.tierTxt, fileTier === 'fast' && iurl.tierTxtActive]}>Cheap &amp; Fast AI</Text>
                  <Text style={iurl.tierHint}>Default · lowest credit cost</Text>
                </View>
                {fileTier === 'fast' && <Ionicons name="checkmark-circle" size={16} color="#2563EB" />}
              </TouchableOpacity>
              <TouchableOpacity
                testID="step2-file-tier-precise"
                style={[iurl.tierBtn, fileTier === 'precise' && iurl.tierBtnActive]}
                onPress={() => setFileTier('precise')}
                activeOpacity={0.85}
              >
                <Ionicons name="diamond" size={15} color={fileTier === 'precise' ? '#7C3AED' : '#94A3B8'} />
                <View style={{ flex: 1 }}>
                  <Text style={[iurl.tierTxt, fileTier === 'precise' && { color: '#7C3AED' }]}>Costly &amp; Precise AI</Text>
                  <Text style={iurl.tierHint}>Claude-grade extraction · more credits</Text>
                </View>
                {fileTier === 'precise' && <Ionicons name="checkmark-circle" size={16} color="#7C3AED" />}
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              testID="step2-file-crawl-toggle"
              style={[ifile.crawlRow, fileCrawl && ifile.crawlRowOn]}
              onPress={() => setFileCrawl(!fileCrawl)}
              activeOpacity={0.85}
            >
              <Ionicons name={fileCrawl ? 'checkbox' : 'square-outline'} size={20} color={fileCrawl ? '#7C3AED' : '#94A3B8'} />
              <View style={{ flex: 1 }}>
                <Text style={ifile.crawlTitle}>Also research the web (AI crawl)</Text>
                <Text style={ifile.crawlHint}>Enrich each option with details missing from the file. Uses more credits.</Text>
              </View>
            </TouchableOpacity>

            <TextInput
              testID="step2-file-context"
              style={[iurl.dlgInput, { marginTop: 10 }]}
              placeholder="Optional: what are you deciding? (helps AI focus)"
              placeholderTextColor="#9CA3AF"
              value={fileContext}
              onChangeText={setFileContext}
            />

            <ImportCreditsStrip endpoint="import" tier={fileTier} />

            <View style={iurl.dlgBtns}>
              <TouchableOpacity style={iurl.dlgCancel} onPress={() => { setFileDialogOpen(false); }}>
                <Text style={iurl.dlgCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity testID="step2-file-import" style={[iurl.dlgGo, !picked && { opacity: 0.5 }]} onPress={runFileImport} disabled={fileBusy || !picked}>
                {fileBusy ? <ActivityIndicator size="small" color="#fff" /> : <Text style={iurl.dlgGoText}>Import</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>


      <UrlAccessConsentModal
        visible={importConsentOpen}
        url={importUrl.trim()}
        busy={importing}
        primary="#2563EB"
        onCancel={() => { if (!importing) setImportConsentOpen(false); }}
        onConfirm={runImport}
      />

      <ImportReviewModal
        visible={!!reviewItems}
        factors={reviewItems?.factors || []}
        options={reviewItems?.options || []}
        busy={reviewBusy}
        primary="#2563EB"
        onCancel={() => { if (!reviewBusy) setReviewItems(null); }}
        onConfirm={confirmReviewedImport}
      />

      {/* ── Live import progress — real backend stages + % + elapsed time ── */}
      <Modal visible={!!importProgress} transparent animationType="fade">
        <View style={iurl.dlgOverlay}>
          <View style={iurl.dlg} testID="import-progress-modal">
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <ActivityIndicator size="small" color="#2563EB" />
              <Text style={iurl.dlgTitle}>Importing from URL…</Text>
            </View>
            <Text testID="import-progress-stage" style={{ fontSize: 13.5, color: '#0F172A', fontWeight: '600', marginBottom: 10 }}>
              {importProgress?.label}
            </Text>
            <View style={{ height: 8, borderRadius: 4, backgroundColor: '#E2E8F0', overflow: 'hidden' }}>
              <View style={{
                height: 8, borderRadius: 4, backgroundColor: '#2563EB',
                width: `${Math.min(100, importProgress?.pct || 0)}%`,
              }} />
            </View>
            <Text testID="import-progress-pct" style={{ fontSize: 12, color: '#475569', fontWeight: '700', marginTop: 6 }}>
              {Math.min(100, importProgress?.pct || 0)}% · {importProgress?.elapsed || 0}s elapsed
            </Text>
            <Text style={{ fontSize: 11.5, color: '#64748B', marginTop: 10, lineHeight: 16 }}>
              Pages that need AI extraction (single listings, JS-rendered pages) can take 1–2 minutes.
              Keep this screen open — we&apos;ll fill the factors, options and assessment matrix automatically.
            </Text>
            {/* Per-workflow loader music — admin slot `url_import` (falls back to default). */}
            <View style={{ marginTop: 10 }}>
              <LoaderMusicChip slot="url_import" enabled={!!importProgress} />
            </View>
          </View>
        </View>
      </Modal>

      {/* ── Source quotes (provenance): the exact page line behind every value ── */}
      <Modal visible={!!provenance?.open} transparent animationType="fade" onRequestClose={() => setProvenance(null)}>
        <View style={iurl.dlgOverlay}>
          <View style={[iurl.dlg, { maxWidth: 560 }]} testID="import-provenance-modal">
            <Text style={iurl.dlgTitle}>Source quotes — where each value came from</Text>
            {provenance?.loading ? (
              <ActivityIndicator color="#2563EB" style={{ marginVertical: 18 }} />
            ) : (
              <>
                <Text testID="import-provenance-summary" style={{ fontSize: 12, color: '#475569', marginBottom: 8 }}>
                  {(provenance?.verification?.verified || 0)} value{(provenance?.verification?.verified || 0) === 1 ? '' : 's'} verified on the page
                  {(provenance?.verification?.blanked || 0) > 0 ? ` · ${provenance?.verification?.blanked} left blank (not found on the page)` : ''}
                </Text>
                <ScrollView style={{ maxHeight: 380 }} showsVerticalScrollIndicator={false}>
                  {(provenance?.items || []).map((e: any, i: number) => (
                    <View key={i} style={{ paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' }}>
                      <Text style={{ fontSize: 12.5, fontWeight: '700', color: '#0F172A' }}>
                        {e.factor} · {e.option}: {e.value}
                      </Text>
                      <Text style={{ fontSize: 11.5, color: '#64748B', fontStyle: 'italic', marginTop: 2 }}>
                        “{e.quote}”
                      </Text>
                    </View>
                  ))}
                  {!(provenance?.items || []).length && (
                    <Text style={{ fontSize: 12, color: '#94A3B8', marginVertical: 12 }}>
                      No source quotes recorded for this run (older imports don&apos;t have them — re-import to get provenance).
                    </Text>
                  )}
                </ScrollView>
              </>
            )}
            <TouchableOpacity testID="import-provenance-close" onPress={() => setProvenance(null)}
              style={{ marginTop: 12, paddingVertical: 11, borderRadius: 10, backgroundColor: '#F1F5F9', alignItems: 'center' }}>
              <Text style={{ fontSize: 13.5, fontWeight: '700', color: '#475569' }}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

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

            {factor.data_source?.type === 'decision_link' && (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#F5F3FF',
                borderRadius: 8, paddingVertical: 6, paddingHorizontal: 8, marginTop: 2, marginBottom: 6 }}>
                <Ionicons name="git-network" size={13} color={COLORS.primary} />
                <Text style={{ flex: 1, fontSize: 11.5, color: COLORS.primary, fontWeight: '600' }} numberOfLines={1}>
                  {factor.data_source.config?.linked_title || 'Linked decision'}
                  {factor.data_source.config?.linked_option_name ? ` · ${factor.data_source.config.linked_option_name}` : ''}
                  {factor.data_source.last_value ? ` (${factor.data_source.last_value}%)` : ''}
                  {factor.data_source.config?.refresh === 'auto' ? ' · Auto' : ' · Manual'}
                </Text>
                {factor.data_source.config?.refresh === 'manual' && (
                  <TouchableOpacity onPress={() => refreshLinkedFactor(factor)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }} testID={`link-refresh-${factor.id}`}>
                    <Ionicons name="refresh" size={15} color={COLORS.primary} />
                  </TouchableOpacity>
                )}
                <TouchableOpacity onPress={() => openLinkedDecision(factor)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }} testID={`link-open-${factor.id}`}>
                  <Ionicons name="open-outline" size={15} color={COLORS.primary} />
                </TouchableOpacity>
              </View>
            )}

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
            {!hasChildren && factor.data_source?.type !== 'decision_link' && (
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

      <DecisionLinkPicker visible={linkPickerOpen} onClose={() => setLinkPickerOpen(false)} />
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

const ifile = StyleSheet.create({
  pickBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    borderWidth: 1.5, borderColor: '#DDD6FE', borderStyle: 'dashed',
    backgroundColor: '#F5F3FF', borderRadius: 12, paddingHorizontal: 14, paddingVertical: 14,
    marginTop: 4,
  },
  pickTxt: { flex: 1, fontSize: 14, fontWeight: '600', color: '#5B21B6' },
  types: { fontSize: 11, color: '#94A3B8', marginTop: 6, marginBottom: 4 },
  crawlRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 12,
    borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, padding: 12, backgroundColor: '#FFF',
  },
  crawlRowOn: { borderColor: '#7C3AED', backgroundColor: '#FAF5FF' },
  crawlTitle: { fontSize: 13.5, fontWeight: '700', color: '#0F172A' },
  crawlHint: { fontSize: 11, color: '#94A3B8', marginTop: 2, lineHeight: 15 },
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
  iconRow: { flexDirection: 'row', gap: 8 },
  iconBtn: { flex: 1, backgroundColor: '#fff', borderWidth: 1, borderColor: '#BFDBFE', borderRadius: 10, paddingVertical: 12, alignItems: 'center', justifyContent: 'center', gap: 5 },
  iconLabel: { fontSize: 11.5, fontWeight: '700', color: COLORS.textPrimary },
  tmplLink: { flexDirection: 'row', alignItems: 'center', gap: 5, marginTop: 9, alignSelf: 'flex-start' },
  tmplText: { fontSize: 11.5, fontWeight: '700', color: '#2563EB', textDecorationLine: 'underline' },
  dlgOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center', padding: 24 },
  dlg: { width: '100%', maxWidth: 440, backgroundColor: '#fff', borderRadius: 16, padding: 20 },
  dlgTitle: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary },
  dlgSub: { fontSize: 12, lineHeight: 17, color: COLORS.textMuted, marginTop: 6, marginBottom: 12 },
  dlgInput: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11, fontSize: 14, color: COLORS.textPrimary },
  dlgInputHighlight: { borderWidth: 2, borderColor: '#4F46E5', backgroundColor: '#EEF2FF', paddingHorizontal: 14, paddingVertical: 14, fontSize: 15, fontWeight: '600', color: '#111827', shadowColor: '#4F46E5', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.15, shadowRadius: 6, elevation: 2 },
  tierLabel: { fontSize: 11, fontWeight: '800', color: COLORS.textMuted, marginTop: 12, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4 },
  tierRow: { gap: 8 },
  tierBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 11, paddingVertical: 9, backgroundColor: '#F8FAFC' },
  tierBtnActive: { borderColor: '#2563EB', backgroundColor: '#EFF6FF' },
  tierTxt: { fontSize: 13, fontWeight: '800', color: COLORS.textPrimary },
  tierTxtActive: { color: '#2563EB' },
  tierHint: { fontSize: 10.5, color: COLORS.textMuted, marginTop: 1 },
  hintsToggle: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 12, paddingVertical: 2 },
  hintsToggleText: { fontSize: 12, fontWeight: '800', color: '#2563EB' },
  hintHelp: { fontSize: 12.5, color: '#111827', fontWeight: '500', lineHeight: 18, marginTop: 6, marginBottom: 10 },
  hintRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  hintInputSm: { flex: 1, paddingVertical: 9, fontSize: 13 },
  hintInputFull: { marginBottom: 8, paddingVertical: 9, fontSize: 13 },
  expectBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#0E7490', borderRadius: 12, paddingVertical: 12, paddingHorizontal: 16,
    marginTop: 12,
  },
  expectBtnDisabled: { backgroundColor: '#94A3B8', opacity: 0.7 },
  expectBtnText: { color: '#FFF', fontSize: 14.5, fontWeight: '800' },
  expectHint: { fontSize: 11, color: COLORS.textMuted, textAlign: 'center', marginTop: 6, marginBottom: 12, lineHeight: 15, paddingHorizontal: 8 },
  dlgBtns: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 16 },
  dlgCancel: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 10 },
  dlgCancelText: { fontSize: 13.5, fontWeight: '700', color: COLORS.textMuted },
  dlgGo: { backgroundColor: '#2563EB', paddingHorizontal: 20, paddingVertical: 10, borderRadius: 10, minWidth: 96, alignItems: 'center' },
  dlgGoText: { color: '#fff', fontSize: 13.5, fontWeight: '800' },
});
