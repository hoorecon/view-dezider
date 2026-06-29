/**
 * Financial Model — the "Financial Model" branch on L1 (Financial) of an Org's
 * 6 LeGS tree. From revenue projections + assumptions it builds a 3-statement
 * forecast (P&L / Balance Sheet / Cash Flow), key ratios (incl. DSCR), and an
 * FCFF-DCF valuation (Enterprise Value, Equity Value, Per-Share Price).
 *
 * Phase 1 = on-screen dashboard. Phase 2 (CMA Excel + Investor PDF export) and
 * Phase 3 (Zoho Books / Analytics 2-way sync) build on top of this.
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput,
  ActivityIndicator, useWindowDimensions, Modal, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';
import { downloadAuthedFile } from '../../src/utils/downloadFile';
import { pickAndReadFile } from '../../src/utils/filePick';
import { uploadFileChunked } from '../../src/utils/chunkUpload';

const CURRENCY_SYMBOL: Record<string, string> = {
  INR: '₹', USD: '$', EUR: '€', GBP: '£', AED: 'د.إ', SGD: 'S$',
};

const SECTIONS: { title: string; icon: string; fields: { key: string; label: string; type: 'num' | 'array' }[] }[] = [
  { title: 'Revenue', icon: 'trending-up', fields: [
    { key: 'revenue_by_year', label: 'Revenue by year (primary driver)', type: 'array' },
    { key: 'year1_revenue', label: 'Year-1 revenue (quick-fill)', type: 'num' },
    { key: 'revenue_growth_pct', label: 'Growth % p.a. (quick-fill)', type: 'num' },
  ] },
  { title: 'Costs & Margins', icon: 'pie-chart', fields: [
    { key: 'gross_margin_pct', label: 'Gross margin %', type: 'num' },
    { key: 'opex_pct', label: 'Opex % of revenue', type: 'num' },
    { key: 'other_income_pct', label: 'Other income %', type: 'num' },
    { key: 'depreciation_pct', label: 'Depreciation % of gross block', type: 'num' },
    { key: 'tax_rate_pct', label: 'Tax rate %', type: 'num' },
  ] },
  { title: 'Assets & Capex', icon: 'business', fields: [
    { key: 'opening_gross_block', label: 'Opening gross block', type: 'num' },
    { key: 'capex_by_year', label: 'Capex by year', type: 'array' },
  ] },
  { title: 'Working Capital (days)', icon: 'sync', fields: [
    { key: 'debtor_days', label: 'Debtor days', type: 'num' },
    { key: 'inventory_days', label: 'Inventory days', type: 'num' },
    { key: 'creditor_days', label: 'Creditor days', type: 'num' },
  ] },
  { title: 'Debt', icon: 'card', fields: [
    { key: 'opening_debt', label: 'Opening debt', type: 'num' },
    { key: 'interest_rate_pct', label: 'Interest rate %', type: 'num' },
    { key: 'new_debt_by_year', label: 'New debt drawn by year', type: 'array' },
    { key: 'repayment_by_year', label: 'Repayment by year', type: 'array' },
  ] },
  { title: 'Equity & Cash', icon: 'wallet', fields: [
    { key: 'opening_equity_capital', label: 'Opening share capital', type: 'num' },
    { key: 'opening_cash', label: 'Opening cash', type: 'num' },
    { key: 'new_equity_by_year', label: 'New equity raised by year', type: 'array' },
    { key: 'shares_outstanding', label: 'Shares outstanding', type: 'num' },
    { key: 'dividend_payout_pct', label: 'Dividend payout %', type: 'num' },
  ] },
  { title: 'Valuation (DCF)', icon: 'calculator', fields: [
    { key: 'wacc_pct', label: 'WACC / discount rate %', type: 'num' },
    { key: 'terminal_growth_pct', label: 'Terminal growth %', type: 'num' },
  ] },
  { title: 'WACC build-up (CAPM) — used when WACC mode = CAPM', icon: 'trending-up', fields: [
    { key: 'risk_free_pct', label: 'Risk-free rate %', type: 'num' },
    { key: 'beta', label: 'Beta', type: 'num' },
    { key: 'market_risk_premium_pct', label: 'Market risk premium %', type: 'num' },
    { key: 'cost_of_debt_pct', label: 'Cost of debt % (pre-tax)', type: 'num' },
    { key: 'market_cap', label: 'Market cap (0 = use price×shares)', type: 'num' },
    { key: 'share_price', label: 'Share price (if no market cap)', type: 'num' },
    { key: 'debt_weight_pct', label: 'Debt weight % (if no market cap)', type: 'num' },
  ] },
  { title: 'Market-EV cross-checks (IIMB)', icon: 'business', fields: [
    { key: 'minority_interest', label: 'Minority (non-controlling) interest', type: 'num' },
    { key: 'preference_capital', label: 'Preference capital', type: 'num' },
    { key: 'non_operating_assets', label: 'Non-operating assets', type: 'num' },
  ] },
];

const PNL_ROWS = [
  ['revenue', 'Revenue'], ['cogs', 'Cost of Goods Sold'], ['gross_profit', 'Gross Profit'],
  ['other_income', 'Other Income'], ['opex', 'Operating Expenses'], ['ebitda', 'EBITDA'],
  ['depreciation', 'Depreciation'], ['ebit', 'EBIT'], ['interest', 'Interest'],
  ['pbt', 'Profit Before Tax'], ['tax', 'Tax'], ['pat', 'Profit After Tax (PAT)'],
  ['dividend', 'Dividend'], ['retained', 'Retained Earnings'],
];
const BS_ROWS = [
  ['gross_block', 'Gross Block'], ['acc_depreciation', 'Less: Acc. Depreciation'], ['net_block', 'Net Block'],
  ['inventory', 'Inventory'], ['debtors', 'Debtors'], ['cash', 'Cash & Bank'],
  ['total_current_assets', 'Total Current Assets'], ['total_assets', 'TOTAL ASSETS'],
  ['equity_capital', 'Share Capital'], ['reserves', 'Reserves & Surplus'], ['net_worth', 'Net Worth'],
  ['debt', 'Debt'], ['creditors', 'Creditors'], ['total_current_liabilities', 'Total Current Liabilities'],
  ['total_liabilities', 'TOTAL LIABILITIES'], ['balance_check', 'Balance Check (≈0)'],
];
const CF_ROWS = [
  ['opening_cash', 'Opening Cash'], ['cfo', 'Cash from Operations'], ['cfi', 'Cash from Investing'],
  ['cff', 'Cash from Financing'], ['net_change', 'Net Change in Cash'], ['closing_cash', 'Closing Cash'],
];
const RATIO_ROWS: [string, string, boolean][] = [
  ['current_ratio', 'Current Ratio', false], ['quick_ratio', 'Quick Ratio', false],
  ['debt_equity', 'Debt / Equity', false], ['interest_coverage', 'Interest Coverage', false],
  ['dscr', 'DSCR', false], ['gross_margin_pct', 'Gross Margin', true],
  ['ebitda_margin_pct', 'EBITDA Margin', true], ['net_margin_pct', 'Net Margin', true],
  ['roce_pct', 'ROCE', true], ['roe_pct', 'ROE', true],
  ['debtor_days', 'Debtor Days', false], ['inventory_days', 'Inventory Days', false],
  ['creditor_days', 'Creditor Days', false],
];

const TABS = ['assumptions', 'pnl', 'bs', 'cf', 'ratios', 'valuation', 'iimb'] as const;
const TAB_LABEL: Record<string, string> = {
  assumptions: 'Inputs', pnl: 'P&L', bs: 'Balance Sheet', cf: 'Cash Flow', ratios: 'Ratios', valuation: 'Valuation', iimb: 'Valuation (IIMB)',
};

export default function FinancialModelScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const orgId = params.org as string | undefined;
  const legGoalId = params.goal as string | undefined;
  const presetModelId = params.model as string | undefined;
  const { width } = useWindowDimensions();

  const [meta, setMeta] = useState<any>(null);
  const [model, setModel] = useState<any>(null);
  const [models, setModels] = useState<any[]>([]);
  const [assumptions, setAssumptions] = useState<any>({});
  const [computed, setComputed] = useState<any>(null);
  const [unitsId, setUnitsId] = useState('absolute');
  const [currency, setCurrency] = useState('INR');
  const [tab, setTab] = useState<string>('assumptions');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [importing, setImporting] = useState<string | null>(null);
  const [sheetModal, setSheetModal] = useState(false);
  const [sheetUrl, setSheetUrl] = useState('');
  const [zohoModal, setZohoModal] = useState(false);
  const [zohoFrom, setZohoFrom] = useState('');
  const [zohoTo, setZohoTo] = useState('');

  const sym = CURRENCY_SYMBOL[currency] || '';
  const unit = useMemo(() => (meta?.units || []).find((u: any) => u.id === unitsId) || { divisor: 1, suffix: '' }, [meta, unitsId]);

  const fmt = useCallback((v: number) => {
    const n = (Number(v) || 0) / (unit.divisor || 1);
    const s = n.toLocaleString(undefined, { maximumFractionDigits: (unit.divisor || 1) > 1 ? 2 : 0 });
    return unit.suffix ? `${s}${unit.suffix}` : s;
  }, [unit]);

  const loadModel = useCallback(async (id: string) => {
    const { data } = await api.get(`/financial-models/${id}`);
    setModel(data); setAssumptions(data.assumptions || {}); setComputed(data.computed || null);
    setUnitsId(data.units || 'absolute'); setCurrency(data.currency || 'INR');
  }, []);

  const init = useCallback(async () => {
    setLoading(true);
    try {
      const m = await api.get('/financial-models/meta');
      setMeta(m.data);
      setAssumptions(m.data.default_assumptions || {});
      if (presetModelId) { await loadModel(presetModelId); return; }
      if (orgId) {
        const list = await api.get('/financial-models', { params: { user_org_id: orgId } });
        const arr = list.data?.models || [];
        setModels(arr);
        if (arr.length) await loadModel(arr[0].id);
      }
    } catch (e: any) {
      showAlert('Could not load', e?.response?.data?.detail || e.message);
    } finally { setLoading(false); }
  }, [orgId, presetModelId, loadModel]);

  useEffect(() => { init(); }, [init]);

  const recalc = useCallback(async (a = assumptions) => {
    setBusy(true);
    try {
      const { data } = await api.post('/financial-models/compute', {
        assumptions: a, projection_years: model?.projection_years || 5,
      });
      setComputed(data.computed); setDirty(false);
    } catch (e: any) {
      showAlert('Compute failed', e?.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  }, [assumptions, model]);

  const setField = (key: string, value: any) => {
    setAssumptions((p: any) => ({ ...p, [key]: value }));
    setDirty(true);
  };

  const goTab = (t: string) => {
    if (t !== 'assumptions' && dirty) recalc();
    setTab(t);
  };

  const createModel = async () => {
    if (!orgId) return;
    setBusy(true);
    try {
      const { data } = await api.post('/financial-models', {
        user_org_id: orgId, leg_goal_id: legGoalId || null,
        name: 'Financial Model', currency, units: unitsId,
        assumptions, projection_years: 5,
      });
      setModel(data); setComputed(data.computed); setDirty(false);
      const list = await api.get('/financial-models', { params: { user_org_id: orgId } });
      setModels(list.data?.models || []);
      showAlert('Saved', 'Financial model created.');
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  const saveModel = async () => {
    if (!model) { await createModel(); return; }
    setBusy(true);
    try {
      const { data } = await api.put(`/financial-models/${model.id}`, {
        assumptions, units: unitsId, currency,
      });
      setModel(data); setComputed(data.computed); setDirty(false);
      showAlert('Saved', 'Financial model updated.');
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  // ── seed base year + export reports (Phase 2) ──
  const seedFromExcel = async () => {
    setSeeding(true);
    try {
      const picked = await pickAndReadFile();
      if (!picked) { setSeeding(false); return; }
      const uploadId = await uploadFileChunked(picked);
      const { data } = await api.post('/financial-models/seed-from-file', {
        filename: picked.filename, upload_id: uploadId, ai_tier: 'fast',
      }, { timeout: 180000 });
      const patch = data?.patch || {};
      if (!Object.keys(patch).length) {
        showAlert('Nothing found', 'Could not read opening balances from this file.');
        return;
      }
      const next = { ...assumptions, ...patch };
      setAssumptions(next);
      setDirty(true);
      await recalc(next);
      showAlert('Base year seeded', `Pre-filled ${Object.keys(patch).length} field(s): ${(data.found || []).join(', ')}.`);
    } catch (e: any) {
      showAlert('Seed failed', e?.response?.data?.detail || e.message || 'Try a clearer Excel/PDF.');
    } finally { setSeeding(false); }
  };

  const applyPatch = async (patch: any, found: string[]) => {
    const next = { ...assumptions, ...patch };
    setAssumptions(next);
    setDirty(true);
    await recalc(next);
    showAlert('Imported', `Filled ${found.length} field(s): ${found.join(', ')}.`);
  };

  const downloadTemplate = async () => {
    setImporting('tpl');
    try {
      const q = model?.id ? `?model_id=${model.id}` : '';
      await downloadAuthedFile(`/financial-models/templates/inputs.xlsx${q}`, 'financial-model-template.xlsx', XLSX_MIME);
    } catch (e: any) {
      showAlert('Download failed', e?.message || 'Could not download the template.');
    } finally { setImporting(null); }
  };

  const importFromExcel = async () => {
    setImporting('xls');
    try {
      const picked = await pickAndReadFile();
      if (!picked) { setImporting(null); return; }
      if (picked.sizeBytes && picked.sizeBytes > MAX_UPLOAD_BYTES) {
        showAlert('File too large', `Please choose a file under ${MAX_UPLOAD_LABEL}.`);
        return;
      }
      const uploadId = await uploadFileChunked(picked);
      const { data } = await api.post('/financial-models/import-file', { filename: picked.filename, upload_id: uploadId }, { timeout: 120000 });
      await applyPatch(data?.patch || {}, data?.found || []);
    } catch (e: any) {
      showAlert('Import failed', e?.response?.data?.detail || e.message || 'Use the provided template.');
    } finally { setImporting(null); }
  };

  const importFromSheet = async () => {
    if (!sheetUrl.trim()) return;
    setImporting('sheet');
    try {
      const { data } = await api.post('/financial-models/import-sheet', { sheet_url: sheetUrl.trim() }, { timeout: 120000 });
      setSheetModal(false); setSheetUrl('');
      await applyPatch(data?.patch || {}, data?.found || []);
    } catch (e: any) {
      showAlert('Import failed', e?.response?.data?.detail || e.message || 'Check the sheet link & sharing.');
    } finally { setImporting(null); }
  };

  const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

  const lastCompletedFY = (): { from: string; to: string } => {
    const now = new Date();
    const endY = (now.getMonth() + 1) >= 4 ? now.getFullYear() : now.getFullYear() - 1;
    return { from: `${endY - 1}-04-01`, to: `${endY}-03-31` };
  };

  const openZohoModal = () => {
    if (!zohoFrom || !zohoTo) {
      const fy = lastCompletedFY();
      setZohoFrom(fy.from); setZohoTo(fy.to);
    }
    setZohoModal(true);
  };

  const syncZoho = async () => {
    if (!zohoFrom.trim() || !zohoTo.trim()) {
      showAlert('Pick dates', 'Enter a From and To date (YYYY-MM-DD).');
      return;
    }
    setImporting('zoho');
    try {
      const { data } = await api.post('/financial-models/zoho-sync', {
        from_date: zohoFrom.trim(), to_date: zohoTo.trim(), as_of: zohoTo.trim(),
      }, { timeout: 120000 });
      setZohoModal(false);
      await applyPatch(data?.patch || {}, data?.found || []);
    } catch (e: any) {
      showAlert('Zoho sync failed', e?.response?.data?.detail || e.message || 'Could not reach Zoho Books.');
    } finally { setImporting(null); }
  };

  const toggleAutoSync = async () => {
    if (!model?.id) { showAlert('Save first', 'Save the model before enabling nightly auto-sync.'); return; }
    const enabled = !model.zoho_auto_sync;
    setImporting('autosync');
    try {
      const { data } = await api.post(`/financial-models/${model.id}/zoho-autosync`, { enabled });
      setModel({ ...model, zoho_auto_sync: data.zoho_auto_sync, zoho_snapshot: data.zoho_snapshot ?? model.zoho_snapshot });
      showAlert(
        enabled ? 'Nightly auto-sync ON' : 'Auto-sync OFF',
        enabled ? 'A fresh Zoho snapshot is fetched nightly. Review & tap Apply — it never overwrites your inputs automatically.' : 'Nightly Zoho sync disabled.');
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || e.message || 'Try again.');
    } finally { setImporting(null); }
  };

  const applyZohoSnapshot = async () => {
    const snap = model?.zoho_snapshot;
    if (!snap?.patch) return;
    await applyPatch(snap.patch, snap.found || Object.keys(snap.patch));
  };

  const exportReport = async (kind: 'investor' | 'cma', fmt: 'pdf' | 'xlsx') => {
    if (!model?.id) {
      showAlert('Save first', 'Create or Save the model before exporting a report.');
      return;
    }
    if (dirty) { await saveModel(); }
    const key = `${kind}-${fmt}`;
    setExporting(key);
    try {
      const mime = fmt === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      const slug = (model.name || 'financial-model').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'financial-model';
      const filename = `${slug}-${kind}.${fmt}`;
      await downloadAuthedFile(`/financial-models/${model.id}/export/${kind}.${fmt}`, filename, mime);
    } catch (e: any) {
      showAlert('Export failed', e?.message || 'Could not generate the file.');
    } finally { setExporting(null); }
  };

  // ── renderers ──
  const yearLabels: string[] = computed?.year_labels || ['Y1', 'Y2', 'Y3', 'Y4', 'Y5'];

  const renderTable = (rows: any[], data: any, opts?: { strongKeys?: string[] }) => (
    <ScrollView horizontal showsHorizontalScrollIndicator>
      <View>
        <View style={[t.row, t.headRow]}>
          <Text style={[t.cellLabel, t.headCell]}>Line item</Text>
          {yearLabels.map((y, i) => <Text key={i} style={[t.cell, t.headCell]}>{y}</Text>)}
        </View>
        {rows.map(([key, label, isPct]: any) => {
          const strong = opts?.strongKeys?.includes(key) || /TOTAL|Net Worth|EBITDA|PAT|Closing/.test(label);
          const series = (data?.[key]) || [];
          return (
            <View key={key} style={t.row}>
              <Text style={[t.cellLabel, strong && t.strong]} numberOfLines={2}>{label}</Text>
              {yearLabels.map((_, i) => (
                <Text key={i} style={[t.cell, strong && t.strong]}>
                  {isPct ? `${(series[i] ?? 0).toFixed(1)}%` : (tab === 'ratios' ? (series[i] ?? 0).toFixed(2) : fmt(series[i] ?? 0))}
                </Text>
              ))}
            </View>
          );
        })}
      </View>
    </ScrollView>
  );

  const renderAssumptions = () => (
    <View>
      <TouchableOpacity style={s.seedBtn} onPress={seedFromExcel} disabled={seeding} testID="fm-seed">
        {seeding ? <ActivityIndicator color="#003087" /> : (
          <>
            <Ionicons name="cloud-upload-outline" size={16} color="#003087" />
            <Text style={s.seedTxt}>  Seed base year from Excel</Text>
          </>
        )}
      </TouchableOpacity>
      <Text style={s.seedHint}>Upload last year&apos;s P&amp;L + Balance Sheet (Excel/PDF) — AI fills your opening balances. Uses AI credits.</Text>
      <View style={s.impRow}>
        <TouchableOpacity style={s.impBtn} onPress={downloadTemplate} disabled={!!importing} testID="fm-template-dl">
          {importing === 'tpl' ? <ActivityIndicator color="#003087" /> : <><Ionicons name="download-outline" size={15} color="#003087" /><Text style={s.impTxt}>Template</Text></>}
        </TouchableOpacity>
        <TouchableOpacity style={s.impBtn} onPress={importFromExcel} disabled={!!importing} testID="fm-import-xls">
          {importing === 'xls' ? <ActivityIndicator color="#003087" /> : <><Ionicons name="grid-outline" size={15} color="#003087" /><Text style={s.impTxt}>Import Excel</Text></>}
        </TouchableOpacity>
        <TouchableOpacity style={s.impBtn} onPress={() => setSheetModal(true)} disabled={!!importing} testID="fm-import-sheet">
          {importing === 'sheet' ? <ActivityIndicator color="#003087" /> : <><Ionicons name="logo-google" size={15} color="#003087" /><Text style={s.impTxt}>Google Sheet</Text></>}
        </TouchableOpacity>
      </View>
      <Text style={s.seedHint}>Download the template, fill it, then import (Excel or Google Sheet) — no AI credits used.</Text>
      <TouchableOpacity style={s.zohoBtn} onPress={openZohoModal} disabled={!!importing} testID="fm-zoho-sync">
        {importing === 'zoho' ? <ActivityIndicator color="#FFF" /> : (
          <>
            <Ionicons name="sync-outline" size={16} color="#FFF" />
            <Text style={s.zohoTxt}>  Sync historicals from Zoho Books</Text>
          </>
        )}
      </TouchableOpacity>
      <Text style={s.seedHint}>Pulls last financial year&apos;s P&amp;L + Balance Sheet from your connected Zoho Books org.</Text>
      <View style={s.waccBar}>
        <Text style={s.waccLabel}>Nightly auto-sync</Text>
        <TouchableOpacity style={[s.waccChip, model?.zoho_auto_sync && s.waccChipOn]} onPress={toggleAutoSync} disabled={importing === 'autosync'} testID="fm-zoho-autosync">
          {importing === 'autosync' ? <ActivityIndicator color="#003087" /> : <Text style={[s.waccChipTxt, model?.zoho_auto_sync && s.waccChipTxtOn]}>{model?.zoho_auto_sync ? 'ON' : 'OFF'}</Text>}
        </TouchableOpacity>
      </View>
      {!!model?.zoho_snapshot?.patch && Object.keys(model.zoho_snapshot.patch).length > 0 && (
        <View style={s.snapCard}>
          <Text style={s.snapTitle}>Latest from Zoho · {String(model.zoho_snapshot.fetched_at || '').slice(0, 10)}</Text>
          <Text style={s.snapHint}>{(model.zoho_snapshot.found || []).length} field(s): {(model.zoho_snapshot.found || []).join(', ')}</Text>
          <TouchableOpacity style={s.snapApply} onPress={applyZohoSnapshot} testID="fm-zoho-apply">
            <Text style={s.snapApplyTxt}>Apply to model</Text>
          </TouchableOpacity>
        </View>
      )}
      <View style={s.waccBar}>
        <Text style={s.waccLabel}>WACC source</Text>
        {(['direct', 'capm'] as const).map((m) => (
          <TouchableOpacity
            key={m}
            style={[s.waccChip, (assumptions.wacc_mode || 'direct') === m && s.waccChipOn]}
            onPress={() => setField('wacc_mode', m)}
            testID={`fm-wacc-${m}`}
          >
            <Text style={[s.waccChipTxt, (assumptions.wacc_mode || 'direct') === m && s.waccChipTxtOn]}>{m === 'direct' ? 'Direct WACC %' : 'CAPM build-up'}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={s.unitBar}>
        <Text style={s.unitBarLabel}>Units</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {(meta?.units || []).map((u: any) => (
            <TouchableOpacity key={u.id} style={[s.unitChip, unitsId === u.id && s.unitChipOn]} onPress={() => setUnitsId(u.id)}>
              <Text style={[s.unitChipTxt, unitsId === u.id && s.unitChipTxtOn]}>{u.name}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>
      {SECTIONS.map((sec) => (
        <View key={sec.title} style={s.secCard}>
          <View style={s.secHead}>
            <Ionicons name={sec.icon as any} size={16} color="#003087" />
            <Text style={s.secTitle}>{sec.title}</Text>
          </View>
          {sec.fields.map((f) => (
            <View key={f.key} style={s.fieldRow}>
              <Text style={s.fieldLabel}>{f.label}</Text>
              {f.type === 'num' ? (
                <TextInput
                  testID={`fm-${f.key}`}
                  style={s.input}
                  keyboardType="numeric"
                  value={assumptions[f.key] != null ? String(assumptions[f.key]) : ''}
                  onChangeText={(v) => setField(f.key, v === '' ? '' : Number(v.replace(/[^0-9.\-]/g, '')))}
                  placeholder="0" placeholderTextColor="#94A3B8"
                />
              ) : (
                <View style={s.arrayRow}>
                  {Array.from({ length: model?.projection_years || 5 }).map((_, i) => (
                    <TextInput
                      key={i}
                      style={s.arrayInput}
                      keyboardType="numeric"
                      value={(assumptions[f.key]?.[i] != null) ? String(assumptions[f.key][i]) : ''}
                      onChangeText={(v) => {
                        const arr = Array.isArray(assumptions[f.key]) ? [...assumptions[f.key]] : [];
                        while (arr.length < (model?.projection_years || 5)) arr.push(0);
                        arr[i] = v === '' ? 0 : Number(v.replace(/[^0-9.\-]/g, ''));
                        setField(f.key, arr);
                      }}
                      placeholder={`Y${i + 1}`} placeholderTextColor="#94A3B8"
                    />
                  ))}
                </View>
              )}
            </View>
          ))}
        </View>
      ))}
      <TouchableOpacity style={s.recalcBtn} onPress={() => recalc()} disabled={busy} testID="fm-recalc">
        {busy ? <ActivityIndicator color="#FFF" /> : <><Ionicons name="calculator" size={18} color="#FFF" /><Text style={s.recalcTxt}>  Recalculate</Text></>}
      </TouchableOpacity>
    </View>
  );

  const renderValuation = () => {
    const v = computed?.valuation || {};
    const sum = computed?.summary || {};
    return (
      <View>
        <View style={s.valCards}>
          <View style={[s.valCard, { backgroundColor: '#003087' }]}>
            <Text style={s.valCardLabel}>Enterprise Value</Text>
            <Text style={s.valCardNum}>{sym}{fmt(v.enterprise_value)}</Text>
          </View>
          <View style={[s.valCard, { backgroundColor: '#16A34A' }]}>
            <Text style={s.valCardLabel}>Equity Value</Text>
            <Text style={s.valCardNum}>{sym}{fmt(v.equity_value)}</Text>
          </View>
          <View style={[s.valCard, { backgroundColor: '#7C3AED' }]}>
            <Text style={s.valCardLabel}>Per-Share Price</Text>
            <Text style={s.valCardNum}>{sym}{(v.per_share ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</Text>
          </View>
        </View>
        <View style={s.kvCard}>
          <Text style={s.kvTitle}>DCF Breakdown (FCFF)</Text>
          {renderTable([['fcff', 'Free Cash Flow (FCFF)'], ['pv_fcff', 'PV of FCFF']], v)}
          {[
            ['Sum of PV (FCFF)', fmt(v.sum_pv_fcff)],
            ['Terminal Value', fmt(v.terminal_value)],
            ['PV of Terminal Value', fmt(v.pv_terminal)],
            ['(=) Enterprise Value', fmt(v.enterprise_value)],
            ['Less: Net Debt', fmt(v.net_debt)],
            ['(=) Equity Value', fmt(v.equity_value)],
            ['WACC / Discount rate', `${v.wacc_pct ?? 0}%`],
            ['Terminal growth', `${v.terminal_growth_pct ?? 0}%`],
          ].map(([k, val]) => (
            <View key={k as string} style={s.kvRow}>
              <Text style={s.kvK}>{k}</Text><Text style={s.kvV}>{sym}{val}</Text>
            </View>
          ))}
        </View>
        <View style={s.kvCard}>
          <Text style={s.kvTitle}>Headline Indicators</Text>
          {[
            ['Revenue CAGR', `${sum.revenue_cagr_pct ?? 0}%`],
            ['Average DSCR', `${sum.dscr_avg ?? 0}x`],
            ['Minimum DSCR', `${sum.min_dscr ?? 0}x`],
            ['Final-year PAT', `${sym}${fmt(sum.final_year_pat)}`],
          ].map(([k, val]) => (
            <View key={k as string} style={s.kvRow}><Text style={s.kvK}>{k}</Text><Text style={[s.kvV, { color: '#16A34A' }]}>{val}</Text></View>
          ))}
        </View>
        <View style={s.kvCard}>
          <Text style={s.kvTitle}>Investor &amp; Bank Reports</Text>
          <Text style={s.exportHint}>Download a polished, ready-to-share report. Investor pack = summary + 3 statements + DCF. Bank CMA = RBI-style working-capital workbook.</Text>
          {!model?.id && <Text style={s.exportWarn}>Save the model first to enable downloads.</Text>}
          <View style={s.exportGrid}>
            {([
              ['Investor PDF', 'investor', 'pdf', 'document-text-outline'],
              ['Investor Excel', 'investor', 'xlsx', 'grid-outline'],
              ['Bank CMA PDF', 'cma', 'pdf', 'document-text-outline'],
              ['Bank CMA Excel', 'cma', 'xlsx', 'grid-outline'],
            ] as const).map(([label, kind, fmt, icon]) => {
              const key = `${kind}-${fmt}`;
              return (
                <TouchableOpacity
                  key={key}
                  style={[s.exportBtn, !model?.id && { opacity: 0.5 }]}
                  disabled={!!exporting || !model?.id}
                  onPress={() => exportReport(kind, fmt)}
                  testID={`fm-export-${key}`}
                >
                  {exporting === key ? <ActivityIndicator color="#003087" /> : (
                    <>
                      <Ionicons name={icon as any} size={16} color="#003087" />
                      <Text style={s.exportBtnTxt}>{label}</Text>
                    </>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      </View>
    );
  };

  const renderIIMB = () => {
    const i = computed?.iimb || {};
    return (
      <View>
        <View style={s.valCards}>
          <View style={[s.valCard, { backgroundColor: '#003087' }]}>
            <Text style={s.valCardLabel}>Enterprise Value</Text>
            <Text style={s.valCardNum}>{sym}{fmt(i.enterprise_value)}</Text>
          </View>
          <View style={[s.valCard, { backgroundColor: '#16A34A' }]}>
            <Text style={s.valCardLabel}>Equity Value</Text>
            <Text style={s.valCardNum}>{sym}{fmt(i.equity_value)}</Text>
          </View>
          <View style={[s.valCard, { backgroundColor: '#7C3AED' }]}>
            <Text style={s.valCardLabel}>Per-Share</Text>
            <Text style={s.valCardNum}>{sym}{(i.per_share ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</Text>
          </View>
        </View>
        <View style={s.kvCard}>
          <Text style={s.kvTitle}>WACC build-up (CAPM)</Text>
          {[
            ['WACC source', i.wacc_mode === 'capm' ? 'CAPM build-up' : 'Direct %'],
            ['Cost of Equity (Ke = Rf + β·MRP)', `${i.cost_of_equity_pct ?? 0}%`],
            ['Cost of Debt (pre-tax)', `${i.cost_of_debt_pre_pct ?? 0}%`],
            ['Cost of Debt (after tax)', `${i.cost_of_debt_after_tax_pct ?? 0}%`],
            ['Equity weight (E/V)', `${i.equity_weight_pct ?? 0}%`],
            ['Debt weight (D/V)', `${i.debt_weight_pct ?? 0}%`],
            ['WACC (CAPM)', `${i.wacc_capm_pct ?? 0}%`],
            ['WACC used in DCF', `${i.wacc_used_pct ?? 0}%`],
          ].map(([k, val]) => (
            <View key={k as string} style={s.kvRow}><Text style={s.kvK}>{k}</Text><Text style={s.kvV}>{val}</Text></View>
          ))}
        </View>
        <View style={s.kvCard}>
          <Text style={s.kvTitle}>NOPLAT → FCFF bridge</Text>
          {renderTable([
            ['noplat', 'NOPLAT = EBIT×(1−tax)'], ['depreciation', '(+) Depreciation'],
            ['gross_cash_flow', '(=) Gross Cash Flow'], ['capex', '(−) Capex'],
            ['increase_in_nwc', '(−) Increase in NWC'], ['fcff', '(=) FCFF'], ['pv_fcff', 'PV of FCFF'],
          ], i)}
          {[
            ['Sum of PV (FCFF)', fmt(i.sum_pv_fcff)],
            ['Terminal Value', fmt(i.terminal_value)],
            ['PV of Terminal Value', fmt(i.pv_terminal)],
            ['(=) Enterprise Value', fmt(i.enterprise_value)],
            ['Less: Net Debt', fmt(i.net_debt)],
            ['Less: Minority + Preference', fmt((i.minority_interest || 0) + (i.preference_capital || 0))],
            ['Add: Non-operating assets', fmt(i.non_operating_assets)],
            ['(=) Equity Value', fmt(i.equity_value)],
          ].map(([k, val]) => (
            <View key={k as string} style={s.kvRow}><Text style={s.kvK}>{k}</Text><Text style={s.kvV}>{sym}{val}</Text></View>
          ))}
        </View>
        <View style={s.kvCard}>
          <Text style={s.kvTitle}>Market-EV cross-checks</Text>
          {[
            ['Market cap', fmt(i.market_cap)],
            ['Simple EV (MktCap + Net Debt)', fmt(i.simple_market_ev)],
            ['Fuller EV (+ Minority + Pref − Non-op)', fmt(i.fuller_market_ev)],
          ].map(([k, val]) => (
            <View key={k as string} style={s.kvRow}><Text style={s.kvK}>{k}</Text><Text style={[s.kvV, { color: '#7C3AED' }]}>{sym}{val}</Text></View>
          ))}
          <Text style={s.exportHint}>Per IIMB Valuation Course: DCF Enterprise Value vs market-based EV cross-checks. Switch WACC source in the Inputs tab.</Text>
        </View>
      </View>
    );
  };

  if (loading) return <SafeAreaView style={s.wrap}><ActivityIndicator style={{ marginTop: 80 }} color="#003087" /></SafeAreaView>;

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => { try { safeBack(router); } catch {} }} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>💰 Financial Model</Text>
          <Text style={s.subtitle}>3-statement forecast · ratios · DCF valuation</Text>
        </View>
        <TouchableOpacity onPress={saveModel} style={s.saveBtn} disabled={busy} testID="fm-save">
          <Ionicons name="save" size={16} color="#003087" />
          <Text style={s.saveBtnTxt}>{model ? 'Save' : 'Create'}</Text>
        </TouchableOpacity>
      </View>

      <View style={s.tabsWrap}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 8 }}>
          {TABS.map((tk) => (
            <TouchableOpacity key={tk} style={[s.tab, tab === tk && s.tabOn]} onPress={() => goTab(tk)} testID={`fm-tab-${tk}`}>
              <Text style={[s.tabTxt, tab === tk && s.tabTxtOn]}>{TAB_LABEL[tk]}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {dirty && tab !== 'assumptions' && (
        <TouchableOpacity style={s.dirtyBar} onPress={() => recalc()}>
          <Ionicons name="refresh" size={13} color="#92400E" />
          <Text style={s.dirtyTxt}>Inputs changed — tap to recalculate</Text>
        </TouchableOpacity>
      )}

      <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 60 }}>
        {tab === 'assumptions' && renderAssumptions()}
        {tab !== 'assumptions' && !computed && (
          <View style={s.emptyCard}>
            <Ionicons name="calculator-outline" size={40} color="#CBD5E1" />
            <Text style={s.emptyTxt}>No results yet — fill the Inputs and tap Recalculate.</Text>
          </View>
        )}
        {tab === 'pnl' && computed && renderTable(PNL_ROWS, computed.pnl)}
        {tab === 'bs' && computed && renderTable(BS_ROWS, computed.balance_sheet)}
        {tab === 'cf' && computed && renderTable(CF_ROWS, computed.cash_flow)}
        {tab === 'ratios' && computed && renderTable(RATIO_ROWS, computed.ratios)}
        {tab === 'valuation' && computed && renderValuation()}
        {tab === 'iimb' && computed && renderIIMB()}
        {tab !== 'assumptions' && computed && (
          <Text style={s.disclaimer}>
            Indicative model for planning. Use the Valuation tab to download bank-ready CMA (Excel/PDF) &amp; investor reports. Phase 3 will add Zoho Books sync.
          </Text>
        )}
      </ScrollView>

      <Modal visible={sheetModal} transparent animationType="fade" onRequestClose={() => setSheetModal(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={s.modalWrap}>
          <View style={s.modalCard}>
            <Text style={s.modalTitle}>Import from Google Sheet</Text>
            <Text style={s.modalHint}>Fill the downloaded template in Google Sheets, then paste its link. Public links work instantly; private sheets use your connected Google account.</Text>
            <TextInput
              style={s.modalInput}
              value={sheetUrl}
              onChangeText={setSheetUrl}
              placeholder="https://docs.google.com/spreadsheets/d/…"
              placeholderTextColor="#94A3B8"
              autoCapitalize="none"
              testID="fm-sheet-url"
            />
            <View style={s.modalBtns}>
              <TouchableOpacity style={s.modalCancel} onPress={() => { setSheetModal(false); setSheetUrl(''); }}>
                <Text style={s.modalCancelTxt}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.modalGo} onPress={importFromSheet} disabled={importing === 'sheet'} testID="fm-sheet-import">
                {importing === 'sheet' ? <ActivityIndicator color="#FFF" /> : <Text style={s.modalGoTxt}>Import</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      <Modal visible={zohoModal} transparent animationType="fade" onRequestClose={() => setZohoModal(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={s.modalWrap}>
          <View style={s.modalCard}>
            <Text style={s.modalTitle}>Sync from Zoho Books</Text>
            <Text style={s.modalHint}>Pick the period to pull P&amp;L + Balance Sheet for. Defaults to your last completed financial year.</Text>
            <View style={s.waccBar}>
              {[0, 1, 2].map((back) => {
                const now = new Date();
                const baseEndY = (now.getMonth() + 1) >= 4 ? now.getFullYear() : now.getFullYear() - 1;
                const endY = baseEndY - back;
                const from = `${endY - 1}-04-01`; const to = `${endY}-03-31`;
                const on = zohoFrom === from && zohoTo === to;
                return (
                  <TouchableOpacity key={back} style={[s.waccChip, on && s.waccChipOn]} onPress={() => { setZohoFrom(from); setZohoTo(to); }} testID={`fm-zoho-fy-${endY}`}>
                    <Text style={[s.waccChipTxt, on && s.waccChipTxtOn]}>{`FY${endY - 1}-${String(endY).slice(2)}`}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            <Text style={s.modalHint}>From (YYYY-MM-DD)</Text>
            <TextInput style={s.modalInput} value={zohoFrom} onChangeText={setZohoFrom} placeholder="2025-04-01" placeholderTextColor="#94A3B8" autoCapitalize="none" testID="fm-zoho-from" />
            <Text style={s.modalHint}>To (YYYY-MM-DD)</Text>
            <TextInput style={s.modalInput} value={zohoTo} onChangeText={setZohoTo} placeholder="2026-03-31" placeholderTextColor="#94A3B8" autoCapitalize="none" testID="fm-zoho-to" />
            <View style={s.modalBtns}>
              <TouchableOpacity style={s.modalCancel} onPress={() => setZohoModal(false)}>
                <Text style={s.modalCancelTxt}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.modalGo, { backgroundColor: '#0F9D58' }]} onPress={syncZoho} disabled={importing === 'zoho'} testID="fm-zoho-go">
                {importing === 'zoho' ? <ActivityIndicator color="#FFF" /> : <Text style={s.modalGoTxt}>Sync</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, backgroundColor: '#003087' },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center' },
  title: { color: '#FFF', fontSize: 17, fontWeight: '800' },
  subtitle: { color: 'rgba(255,255,255,0.8)', fontSize: 11, marginTop: 1 },
  saveBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#FFF', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8 },
  saveBtnTxt: { color: '#003087', fontWeight: '800', fontSize: 12 },
  tabsWrap: { backgroundColor: '#FFF', borderBottomWidth: 1, borderColor: '#E2E8F0', paddingVertical: 6 },
  tab: { paddingHorizontal: 14, paddingVertical: 8, marginRight: 4, borderRadius: 8 },
  tabOn: { backgroundColor: '#EEF2FF' },
  tabTxt: { fontSize: 12.5, fontWeight: '700', color: '#64748B' },
  tabTxtOn: { color: '#003087' },
  dirtyBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#FEF3C7', paddingVertical: 7 },
  dirtyTxt: { color: '#92400E', fontSize: 12, fontWeight: '700' },
  unitBar: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  impRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  impBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, backgroundColor: '#F1F5F9', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 9, paddingVertical: 10 },
  impTxt: { color: '#003087', fontWeight: '800', fontSize: 11.5 },
  zohoBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#0F9D58', borderRadius: 10, paddingVertical: 12, marginTop: 8 },
  zohoTxt: { color: '#FFF', fontWeight: '800', fontSize: 13.5 },
  snapCard: { backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0', borderRadius: 10, padding: 12, marginTop: 8 },
  snapTitle: { fontSize: 12.5, fontWeight: '800', color: '#065F46' },
  snapHint: { fontSize: 11, color: '#047857', marginTop: 4, lineHeight: 15 },
  snapApply: { alignSelf: 'flex-start', marginTop: 10, backgroundColor: '#0F9D58', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 9 },
  snapApplyTxt: { color: '#FFF', fontWeight: '800', fontSize: 12.5 },
  waccBar: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4, marginBottom: 10 },
  waccLabel: { fontSize: 12, fontWeight: '700', color: '#64748B' },
  waccChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, backgroundColor: '#F1F5F9', borderWidth: 1, borderColor: '#CBD5E1' },
  waccChipOn: { backgroundColor: '#003087', borderColor: '#003087' },
  waccChipTxt: { fontSize: 12, fontWeight: '700', color: '#64748B' },
  waccChipTxtOn: { color: '#FFF' },
  modalWrap: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', padding: 22 },
  modalCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 18 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: '#003087' },
  modalHint: { fontSize: 11.5, color: '#64748B', marginTop: 6, lineHeight: 16 },
  modalInput: { borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 9, paddingHorizontal: 12, paddingVertical: 10, marginTop: 12, fontSize: 13, color: '#0F172A' },
  modalBtns: { flexDirection: 'row', gap: 10, marginTop: 14 },
  modalCancel: { flex: 1, alignItems: 'center', paddingVertical: 12, borderRadius: 9, backgroundColor: '#F1F5F9' },
  modalCancelTxt: { color: '#64748B', fontWeight: '800', fontSize: 13 },
  modalGo: { flex: 1, alignItems: 'center', paddingVertical: 12, borderRadius: 9, backgroundColor: '#003087' },
  modalGoTxt: { color: '#FFF', fontWeight: '800', fontSize: 13 },
  unitBarLabel: { fontSize: 12, fontWeight: '800', color: '#475569' },
  unitChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1', marginRight: 6, backgroundColor: '#FFF' },
  unitChipOn: { backgroundColor: '#003087', borderColor: '#003087' },
  unitChipTxt: { fontSize: 11.5, fontWeight: '700', color: '#475569' },
  unitChipTxtOn: { color: '#FFF' },
  secCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  secHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  secTitle: { fontSize: 13, fontWeight: '800', color: '#003087' },
  fieldRow: { marginBottom: 8 },
  fieldLabel: { fontSize: 11.5, fontWeight: '600', color: '#475569', marginBottom: 4 },
  input: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 9, fontSize: 13, color: '#0F172A' },
  arrayRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  arrayInput: { flexGrow: 1, minWidth: 56, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 8, fontSize: 12, color: '#0F172A', textAlign: 'center' },
  recalcBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#003087', borderRadius: 10, paddingVertical: 13, marginTop: 4, marginBottom: 20 },
  recalcTxt: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  emptyCard: { alignItems: 'center', paddingVertical: 40 },
  emptyTxt: { fontSize: 13, color: '#94A3B8', marginTop: 10, textAlign: 'center' },
  disclaimer: { fontSize: 10.5, color: '#94A3B8', marginTop: 14, lineHeight: 15, fontStyle: 'italic' },
  seedBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#C7D2FE', borderRadius: 10, paddingVertical: 12, marginBottom: 4 },
  seedTxt: { color: '#003087', fontWeight: '800', fontSize: 13.5 },
  seedHint: { fontSize: 10.5, color: '#94A3B8', marginBottom: 12, lineHeight: 14 },
  exportHint: { fontSize: 11, color: '#64748B', marginBottom: 10, lineHeight: 15 },
  exportWarn: { fontSize: 11, color: '#B45309', marginBottom: 8, fontWeight: '700' },
  exportGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  exportBtn: { flexGrow: 1, flexBasis: '45%', minWidth: 130, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingVertical: 12 },
  exportBtnTxt: { color: '#003087', fontWeight: '800', fontSize: 12.5 },
  // valuation
  valCards: { flexDirection: 'row', gap: 8, marginBottom: 12, flexWrap: 'wrap' },
  valCard: { flexGrow: 1, flexBasis: '30%', minWidth: 100, borderRadius: 12, padding: 12 },
  valCardLabel: { color: 'rgba(255,255,255,0.85)', fontSize: 11, fontWeight: '700' },
  valCardNum: { color: '#FFF', fontSize: 18, fontWeight: '900', marginTop: 4 },
  kvCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  kvTitle: { fontSize: 13, fontWeight: '800', color: '#003087', marginBottom: 8 },
  kvRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5, borderBottomWidth: 1, borderColor: '#F1F5F9' },
  kvK: { fontSize: 12.5, color: '#475569', flex: 1 },
  kvV: { fontSize: 12.5, fontWeight: '800', color: '#0F172A' },
});

const t = StyleSheet.create({
  row: { flexDirection: 'row', borderBottomWidth: 1, borderColor: '#F1F5F9' },
  headRow: { backgroundColor: '#EEF2FF', borderTopLeftRadius: 8, borderTopRightRadius: 8 },
  cellLabel: { width: 170, paddingVertical: 9, paddingHorizontal: 8, fontSize: 11.5, color: '#334155' },
  cell: { width: 92, paddingVertical: 9, paddingHorizontal: 6, fontSize: 11.5, color: '#0F172A', textAlign: 'right' },
  headCell: { fontWeight: '800', color: '#003087', fontSize: 11 },
  strong: { fontWeight: '800', color: '#0F172A' },
});
