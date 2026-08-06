/**
 * Admin · The Decider Store — author & authorize public Decision Templates.
 *
 * Flow: Download the Excel template → fill option×factor grid → Import (Excel or
 * Google Sheet) → set metadata/pricing/clone-modes → Create → Classify factors
 * (mandatory/optional + priority) → Authorize (goes public).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, Switch, Linking, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';
import Tooltip from '../../src/components/Tooltip';
import { pickAndReadFile } from '../../src/utils/filePick';

const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const TEMPLATE_URL = `${BACKEND}/api/decider-store/import-template.xlsx`;

const DECISION_TYPES = [
  { id: 'present_problem', label: 'Present Problem' },
  { id: 'need', label: 'Need' },
  { id: 'future_risk', label: 'Future Risk' },
  { id: 'aspiration', label: 'Aspiration' },
];
const CATEGORIES = ['Financial', 'Career', 'Business', 'Health', 'Relationships',
  'Learning', 'Spiritual', 'Social', 'Recreation', 'General'];

// Sub-factor helper: legacy factors (no sub_factors) behave as a single sub-factor.
type SubFactor = {
  id: string; name: string; order?: number;
  data_type?: string; ui_object?: string; split_pct?: number;
};
const subsOf = (f: Factor): SubFactor[] =>
  (f.sub_factors && f.sub_factors.length)
    ? f.sub_factors
    : [{ id: f.id, name: f.name, data_type: 'Text', split_pct: 100 }];

type Factor = {
  id: string; name: string; order?: number; factor_type?: string;
  category?: string; priority?: number; possible_values?: string[];
  sub_factors?: SubFactor[];
};
type Template = {
  template_id: string; title: string; subtitle?: string; description?: string;
  category?: string; decision_type?: string; pricing_type?: string;
  price_paise?: number; creator_split_pct?: number; allowed_clone_modes?: string[];
  factors?: Factor[]; options?: any[]; status?: string; is_public?: boolean;
  install_count?: number; kind?: string; finder_settings?: any; catalog_node_id?: string | null;
  lead_gen?: {
    contact_name?: string; organization?: string; designation?: string;
    email?: string; whatsapp?: string; mobile?: string; redirect_url?: string;
  } | null;
  policies?: { privacy_policy?: string; terms_of_use?: string } | null;
};

export default function AdminDeciderStore() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  // Admin-side view filters: which kind (templates vs apps) and which
  // moderation bucket to show. Both persist across restarts via just
  // component state — no need for URL params here.
  const [adminKindTab, setAdminKindTab] = useState<'template' | 'app'>('template');
  const [adminVerifFilter, setAdminVerifFilter] = useState<'all' | 'jai_verified' | 'unverified' | 'disapproved'>('all');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // create/import state
  const [showCreate, setShowCreate] = useState(false);
  const [parsed, setParsed] = useState<{ factors: Factor[]; options: any[] } | null>(null);
  const [gsheetOpen, setGsheetOpen] = useState(false);
  const [gsheetUrl, setGsheetUrl] = useState('');

  // form fields
  const [fTitle, setFTitle] = useState('');
  const [fSubtitle, setFSubtitle] = useState('');
  const [fDesc, setFDesc] = useState('');
  const [fCategory, setFCategory] = useState('General');
  const [fType, setFType] = useState('aspiration');
  const [fPaid, setFPaid] = useState(false);
  const [fPrice, setFPrice] = useState('');           // rupees
  const [fSplit, setFSplit] = useState('70');
  const [fModeFull, setFModeFull] = useState(true);
  const [fModeValues, setFModeValues] = useState(true);
  const [fAutoPush, setFAutoPush] = useState(false);
  const [fKind, setFKind] = useState<'template' | 'app'>('template');

  // Finder defaults + Landing settings modal
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Per-item Publisher Contact override modal
  const [pubEditItem, setPubEditItem] = useState<Template | null>(null);
  const [pubGlobal, setPubGlobal] = useState<any>({});
  const [pubContactName, setPubContactName] = useState('');
  const [pubOrg, setPubOrg] = useState('');
  const [pubDesignation, setPubDesignation] = useState('');
  const [pubEmail, setPubEmail] = useState('');
  const [pubWhatsapp, setPubWhatsapp] = useState('');
  const [pubMobile, setPubMobile] = useState('');
  const [pubRedirectUrl, setPubRedirectUrl] = useState('');
  const [pubPrivacyUrl, setPubPrivacyUrl] = useState('');
  const [pubTermsUrl, setPubTermsUrl] = useState('');
  const openPublisherEditor = async (t: Template) => {
    setPubEditItem(t);
    setPubContactName(t.lead_gen?.contact_name || '');
    setPubOrg(t.lead_gen?.organization || '');
    setPubDesignation(t.lead_gen?.designation || '');
    setPubEmail(t.lead_gen?.email || '');
    setPubWhatsapp(t.lead_gen?.whatsapp || '');
    setPubMobile(t.lead_gen?.mobile || '');
    setPubRedirectUrl(t.lead_gen?.redirect_url || '');
    setPubPrivacyUrl(t.policies?.privacy_policy || '');
    setPubTermsUrl(t.policies?.terms_of_use || '');
    try {
      const r = await api.get('/admin/publisher-defaults');
      setPubGlobal(r.data || {});
    } catch { setPubGlobal({}); }
  };
  const savePublisherEditor = async () => {
    if (!pubEditItem) return;
    setBusy(true);
    try {
      await api.put(`/decider-store/${pubEditItem.template_id}`, {
        lead_gen: {
          contact_name: pubContactName.trim(),
          organization: pubOrg.trim(),
          designation: pubDesignation.trim(),
          email: pubEmail.trim(),
          whatsapp: pubWhatsapp.trim(),
          mobile: pubMobile.trim(),
          redirect_url: pubRedirectUrl.trim(),
        },
        policies: {
          privacy_policy: pubPrivacyUrl.trim(),
          terms_of_use: pubTermsUrl.trim(),
        },
      });
      setPubEditItem(null);
      await load();
      showAlert('Saved', 'Publisher contact & policies updated for this item.');
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Try again');
    } finally {
      setBusy(false);
    }
  };
  const [fdMin, setFdMin] = useState('3');
  const [fdMax, setFdMax] = useState('15');
  const [fdTop, setFdTop] = useState('5');
  const [fdMatch, setFdMatch] = useState<'all' | 'any'>('all');
  const [fdEngine, setFdEngine] = useState<'deterministic' | 'llm'>('deterministic');
  const [fdCutoff, setFdCutoff] = useState('60');
  const [fdSponsN, setFdSponsN] = useState('3');
  const [ldTitle, setLdTitle] = useState('');
  const [ldSubtitle, setLdSubtitle] = useState('');
  const [ldHero, setLdHero] = useState('');
  const [ldCta, setLdCta] = useState('');
  const [ldTarget, setLdTarget] = useState('');

  // build-from-solution-store
  const [fromOpen, setFromOpen] = useState(false);
  const [solList, setSolList] = useState<any[]>([]);
  const [selSols, setSelSols] = useState<Record<string, boolean>>({});
  const [fsTitle, setFsTitle] = useState('');

  // classify editor
  const [classifyId, setClassifyId] = useState<string | null>(null);
  const [classFactors, setClassFactors] = useState<Factor[]>([]);

  // per-cell data editor
  const [dataId, setDataId] = useState<string | null>(null);
  const [dataFactors, setDataFactors] = useState<Factor[]>([]);
  const [dataOpts, setDataOpts] = useState<any[]>([]);
  const [cellText, setCellText] = useState<Record<string, string>>({});
  const [expandedOpt, setExpandedOpt] = useState<string | null>(null);
  const [optSearch, setOptSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/decider-store/admin/all');
      setTemplates(r.data.templates || []);
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Try again');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const resetForm = () => {
    setFTitle(''); setFSubtitle(''); setFDesc(''); setFCategory('General');
    setFType('aspiration'); setFPaid(false); setFPrice(''); setFSplit('70');
    setFModeFull(true); setFModeValues(true); setFAutoPush(false); setFKind('template'); setParsed(null);
  };

  const doImportExcel = async () => {
    try {
      const file = await pickAndReadFile();
      if (!file) return;
      setBusy(true);
      const r = await api.post('/decider-store/import/excel', { file_b64: file.base64 });
      setParsed(r.data);
      showAlert('Imported', `Parsed ${r.data.factors.length} factors · ${r.data.options.length} options. Fill the details below and create.`);
      if (!fTitle) setFTitle(file.filename.replace(/\.(xlsx|xls|csv)$/i, ''));
      setShowCreate(true);
    } catch (e: any) {
      showAlert('Import failed', e?.response?.data?.detail || 'Could not parse the file.');
    } finally { setBusy(false); }
  };

  const doImportGsheet = async () => {
    if (!gsheetUrl.trim()) return;
    setBusy(true);
    try {
      const r = await api.post('/decider-store/import/gsheet', { sheet_url: gsheetUrl.trim() });
      setParsed(r.data);
      setGsheetOpen(false);
      showAlert('Imported', `Parsed ${r.data.factors.length} factors · ${r.data.options.length} options.`);
      setShowCreate(true);
    } catch (e: any) {
      showAlert('Import failed', e?.response?.data?.detail || 'Could not read the sheet.');
    } finally { setBusy(false); }
  };

  const createTemplate = async () => {
    if (!fTitle.trim()) return showAlert('Title required', 'Give the template a title.');
    if (!parsed) return showAlert('Import first', 'Import factors & options from Excel or Google Sheet first.');
    const modes = [fModeFull && 'full', fModeValues && 'values_only'].filter(Boolean);
    if (modes.length === 0) return showAlert('Pick a clone mode', 'Enable at least one clone mode.');
    setBusy(true);
    try {
      await api.post('/decider-store', {
        title: fTitle.trim(), subtitle: fSubtitle.trim(), description: fDesc.trim(),
        category: fCategory, decision_type: fType,
        pricing_type: fPaid ? 'paid' : 'free',
        price_paise: fPaid ? Math.round((parseFloat(fPrice) || 0) * 100) : 0,
        creator_split_pct: parseInt(fSplit) || 70,
        allowed_clone_modes: modes, auto_push_on_authorize: fAutoPush,
        kind: fKind,
        factors: parsed.factors, options: parsed.options,
      });
      setShowCreate(false); resetForm(); load();
      showAlert('Created', 'Template created & authorized (public). Tip: use "Classify" to set mandatory/optional + priority for Full-clone.');
    } catch (e: any) {
      showAlert('Create failed', e?.response?.data?.detail || 'Try again');
    } finally { setBusy(false); }
  };

  const authorize = async (t: Template) => {
    try { await api.post(`/decider-store/${t.template_id}/authorize`); load(); }
    catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
  };
  const toggleKind = async (t: Template) => {
    const next = t.kind === 'app' ? 'template' : 'app';
    try { await api.put(`/decider-store/${t.template_id}`, { kind: next }); load(); }
    catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
  };
  const openSettings = async () => {
    try {
      const [cfg, land] = await Promise.all([
        api.get('/admin/ai-wallet/config').catch(() => ({ data: {} })),
        api.get('/decider-store/landing'),
      ]);
      const c = cfg.data || {};
      setFdMin(String(c.finder_min_options ?? 3));
      setFdMax(String(c.finder_max_options ?? 15));
      setFdTop(String(c.finder_top_n ?? 5));
      setFdMatch(c.finder_match_rule === 'any' ? 'any' : 'all');
      setFdEngine(c.finder_engine === 'llm' ? 'llm' : 'deterministic');
      setFdCutoff(String(c.finder_min_cutoff_pct ?? 60));
      setFdSponsN(String(c.finder_sponsored_n ?? 3));
      const l = land.data || {};
      setLdTitle(l.title || ''); setLdSubtitle(l.subtitle || ''); setLdHero(l.hero || '');
      setLdCta(l.cta_label || ''); setLdTarget(l.cta_target || '');
      setSettingsOpen(true);
    } catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
  };
  const saveSettings = async () => {
    setBusy(true);
    try {
      await api.put('/admin/ai-wallet/config', {
        finder_min_options: parseInt(fdMin) || 3,
        finder_max_options: parseInt(fdMax) || 15,
        finder_top_n: parseInt(fdTop) || 5,
        finder_match_rule: fdMatch, finder_engine: fdEngine,
      }).catch((e: any) => { if (e?.response?.status === 403) throw new Error('Finder defaults need Super-Admin. Landing saved.'); throw e; });
    } catch (e: any) {
      // continue to save landing even if finder-config was forbidden
      showAlert('Note', e?.message || 'Finder defaults not saved (permission).');
    }
    try {
      await api.put('/decider-store/landing', {
        title: ldTitle, subtitle: ldSubtitle, hero: ldHero, cta_label: ldCta, cta_target: ldTarget,
      });
      setSettingsOpen(false);
      showAlert('Saved', 'Finder defaults & landing page updated.');
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Try again');
    } finally { setBusy(false); }
  };
  const unpublish = async (t: Template) => {
    try { await api.post(`/decider-store/${t.template_id}/unpublish`); load(); }
    catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
  };
  // Central-Catalog (Scenario) mapping — drives Sponsored cutoff/slots inheritance
  const [catForId, setCatForId] = useState<string | null>(null);
  const [catNodes, setCatNodes] = useState<any[]>([]);
  const [catSearch, setCatSearch] = useState('');
  const openCatalog = async (t: Template) => {
    setCatForId(t.template_id); setCatSearch('');
    if (!catNodes.length) {
      try {
        const r = await api.get('/catalog/nodes?is_active=true');
        setCatNodes(r.data.items || []);
      } catch { /* non-fatal */ }
    }
  };
  const setCatalogNode = async (nodeId: string | null) => {
    try {
      await api.put(`/decider-store/${catForId}`, { catalog_node_id: nodeId });
      setCatForId(null); load();
    } catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
  };
  // Option Bank (10M-scale Finder) management
  const [bankForId, setBankForId] = useState<string | null>(null);
  const [bankStats, setBankStats] = useState<any>(null);
  const [bankBusy, setBankBusy] = useState(false);
  // In-modal toast (replaces system Alert which used to render BEHIND the
  // Bank modal on RN Web / web preview). Auto-clears after 4s.
  const [bankToast, setBankToast] = useState('');
  const openBank = async (t: Template) => {
    setBankForId(t.template_id); setBankStats(null); setBankToast('');
    try {
      const r = await api.get(`/decider-store/${t.template_id}/bank`);
      setBankStats(r.data);
    } catch (e: any) { setBankToast(`Failed — ${e?.response?.data?.detail || 'try again'}`); }
  };
  const bankAction = async (path: string, method: 'post' | 'delete' = 'post') => {
    if (!bankForId) return;
    setBankBusy(true);
    try {
      const r = method === 'delete'
        ? await api.delete(`/decider-store/${bankForId}/bank`)
        : await api.post(`/decider-store/${bankForId}/bank/${path}`);
      const d = r.data;
      setBankToast(d.deleted != null
        ? `Done · Deleted ${d.deleted} bank rows`
        : `Done · ${d.source}: +${d.inserted} new, ${d.updated} updated, ${d.skipped || 0} skipped`);
      setTimeout(() => setBankToast(''), 4500);
      const st = await api.get(`/decider-store/${bankForId}/bank`);
      setBankStats(st.data);
    } catch (e: any) {
      setBankToast(`Failed — ${e?.response?.data?.detail || 'try again'}`);
    } finally { setBankBusy(false); }
  };
  // Downloads the current Option Bank as an Excel-friendly CSV so the admin
  // can edit hundreds of rows in Excel / Google Sheets and re-import later.
  // Uses the existing GET /bank endpoint which returns the rows array; we
  // stream it to a Blob and force download on web.
  const downloadBankExcel = async () => {
    if (!bankForId) return;
    setBankBusy(true);
    try {
      const r = await api.get(`/decider-store/${bankForId}/bank/rows`, { params: { limit: 100000 } });
      const rows: any[] = r.data?.rows || [];
      if (!rows.length) { setBankToast('Bank is empty — sync template options first.'); setTimeout(() => setBankToast(''), 4000); return; }
      const cols = Array.from(rows.reduce((set: Set<string>, row: any) => {
        Object.keys(row || {}).forEach((k) => set.add(k));
        return set;
      }, new Set<string>()));
      const esc = (v: any) => {
        const s = v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v);
        return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
      };
      const csv = [cols.join(','), ...rows.map((row: any) => cols.map((c) => esc(row[c])).join(','))].join('\n');
      if (typeof window !== 'undefined' && (window as any).URL && (window as any).document) {
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `bank_${bankForId}_${Date.now()}.csv`;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        URL.revokeObjectURL(url);
        setBankToast(`Downloaded ${rows.length} rows — edit in Excel/Sheets and re-import with the Upload button below.`);
      } else {
        setBankToast(`Prepared ${rows.length} rows.`);
      }
      setTimeout(() => setBankToast(''), 5500);
    } catch (e: any) {
      setBankToast(`Failed — ${e?.response?.data?.detail || 'try again'}`);
    } finally { setBankBusy(false); }
  };

  // Import edited CSV back into the bank via /bank/ingest/bulk. The CSV
  // must carry `name` + `val__<sub_factor_id>` columns (matches the download
  // export format).
  const uploadBankCsv = async (file: File) => {
    if (!bankForId || !file) return;
    setBankBusy(true);
    try {
      const text = await file.text();
      const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
      if (lines.length < 2) throw new Error('CSV must have a header row + at least 1 data row');
      // Simple CSV parser (handles double-quoted commas).
      const parseCsvLine = (line: string): string[] => {
        const out: string[] = []; let cur = ''; let inQ = false;
        for (let i = 0; i < line.length; i++) {
          const ch = line[i];
          if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; continue; }
          if (ch === '"') { inQ = !inQ; continue; }
          if (ch === ',' && !inQ) { out.push(cur); cur = ''; continue; }
          cur += ch;
        }
        out.push(cur);
        return out;
      };
      const header = parseCsvLine(lines[0]);
      const items = lines.slice(1).map((ln) => {
        const cells = parseCsvLine(ln);
        const row: any = {}; const values: any = {};
        header.forEach((h, i) => {
          const v = cells[i];
          if (v === undefined) return;
          if (h.startsWith('val__')) values[h.slice(5)] = v;
          else row[h] = v;
        });
        return { name: row.name || '(unnamed)', description: row.description || '', source_ref: row.source_ref || null, values };
      });
      const r = await api.post(`/decider-store/${bankForId}/bank/ingest/bulk`, { items, source: 'bulk' });
      const d = r.data || {};
      setBankToast(`Uploaded · +${d.inserted || 0} new, ${d.updated || 0} updated, ${d.skipped || 0} skipped`);
      setTimeout(() => setBankToast(''), 5500);
      const st = await api.get(`/decider-store/${bankForId}/bank`);
      setBankStats(st.data);
    } catch (e: any) {
      setBankToast(`Upload failed — ${e?.message || e?.response?.data?.detail || 'try again'}`);
    } finally { setBankBusy(false); }
  };

  const remove = async (t: Template) => {
    showAlert('Delete template?', t.title, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/decider-store/${t.template_id}`); load(); }
        catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
      } },
    ]);
  };

  const pushStores = async (t: Template) => {
    setBusy(true);
    try {
      const r = await api.post(`/decider-store/${t.template_id}/push-to-stores`);
      showAlert('Pushed to stores', `${r.data.solutions} solutions → Solution Store · ${r.data.reviews} baselines → ReviewNet.`);
      load();
    } catch (e: any) { showAlert('Push failed', e?.response?.data?.detail || 'Try again'); }
    finally { setBusy(false); }
  };
  const syncStores = async (t: Template) => {
    setBusy(true);
    try {
      const r = await api.post(`/decider-store/${t.template_id}/sync-from-stores`);
      showAlert('Synced from stores', `${r.data.options} options refreshed from Solution Store + ReviewNet.`);
      load();
    } catch (e: any) { showAlert('Sync failed', e?.response?.data?.detail || 'Try again'); }
    finally { setBusy(false); }
  };

  // One-click moderation toggle from the row action bar. Uses the admin
  // moderation endpoints introduced in the previous iteration so behaviour
  // stays consistent with the dedicated /admin/decider-moderation screen.
  const setModerationStatus = async (t: Template, status: 'jai_verified' | 'unverified' | 'disapproved') => {
    setBusy(true);
    try {
      const path = status === 'jai_verified' ? 'approve' : status === 'unverified' ? 'reset' : 'disapprove';
      await api.post(`/admin/moderation/${t.template_id}/${path}`, status === 'disapproved' ? { reason: 'Blocked by admin' } : {});
      load();
    } catch (e: any) {
      showAlert('Moderation update failed', e?.response?.data?.detail || 'Try again');
    } finally { setBusy(false); }
  };

  const openFrom = async () => {
    setFromOpen(true); setSelSols({}); setFsTitle('');
    try {
      const r = await api.get('/solutions-store/solutions', { params: { type: 'STRATEGY', limit: 100 } });
      setSolList(r.data.solutions || r.data.items || r.data || []);
    } catch { setSolList([]); }
  };
  const buildFromSolutions = async () => {
    const ids = Object.keys(selSols).filter(k => selSols[k]);
    if (ids.length === 0) return showAlert('Select solutions', 'Pick at least one solution.');
    if (!fsTitle.trim()) return showAlert('Title required', 'Name the new template.');
    setBusy(true);
    try {
      await api.post('/decider-store/from-solutions', { solution_ids: ids, title: fsTitle.trim() });
      setFromOpen(false); load();
      showAlert('Template created', `Built from ${ids.length} solution(s).`);
    } catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
    finally { setBusy(false); }
  };

  const openClassify = (t: Template) => {
    setClassifyId(t.template_id);
    setClassFactors((t.factors || []).map(f => ({ ...f })));
  };
  const saveClassify = async () => {
    if (!classifyId) return;
    setBusy(true);
    try {
      await api.put(`/decider-store/${classifyId}`, { factors: classFactors });
      setClassifyId(null); load();
      showAlert('Saved', 'Factor classification updated.');
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Try again');
    } finally { setBusy(false); }
  };

  // ── Per-cell option/value editor (CRUD without re-importing) ──────────────
  const openData = (t: Template) => {
    const facs = (t.factors || []).map(f => ({ ...f }));
    const opts = (t.options || []).map((o: any) => ({ ...o, values: { ...(o.values || {}) } }));
    const text: Record<string, string> = {};
    opts.forEach((o: any) => facs.forEach(f => subsOf(f).forEach(sf => {
      const v = o.values?.[sf.id];
      text[`${o.id}::${sf.id}`] = v == null ? '' : String((v.raw ?? v) || '');
    })));
    setDataId(t.template_id); setDataFactors(facs); setDataOpts(opts);
    setCellText(text); setExpandedOpt(opts[0]?.id || null); setOptSearch('');
  };
  const addOption = () => {
    const nid = `opt_${Date.now()}`;
    setDataOpts(prev => [...prev, { id: nid, name: 'New option', values: {} }]);
    setExpandedOpt(nid);
  };
  const deleteOption = (oid: string) => {
    setDataOpts(prev => prev.filter(o => o.id !== oid));
  };
  const saveData = async () => {
    if (!dataId) return;
    setBusy(true);
    try {
      const options = dataOpts.map((o: any) => {
        const values: Record<string, any> = {};
        dataFactors.forEach(f => subsOf(f).forEach(sf => {
          const raw = (cellText[`${o.id}::${sf.id}`] || '').trim();
          if (!raw) return;
          const isText = (sf.data_type || '').toLowerCase().startsWith('text');
          const n = parseFloat(raw.replace(/[^0-9.\-]/g, ''));
          values[sf.id] = { raw, num: isText || isNaN(n) ? null : n };
        }));
        return { ...o, values };
      });
      await api.put(`/decider-store/${dataId}`, { options });
      setDataId(null); load();
      showAlert('Saved', 'Option values updated.');
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Try again');
    } finally { setBusy(false); }
  };

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity style={s.backBtn} onPress={() => safeBack(router, '/admin')}>
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>The Decider Store</Text>
          <Text style={s.sub}>Author · import · authorize public Decision Templates</Text>
        </View>
        <TouchableOpacity
          style={s.pubDefaultsBtn}
          onPress={() => router.push('/admin/publisher-defaults')}
          testID="admin-publisher-defaults-link"
        >
          <Ionicons name="person-circle" size={16} color="#4F46E5" />
          <Text style={s.pubDefaultsText}>Publisher Defaults</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={s.body}>
        {/* Import toolbar */}
        <View style={s.card}>
          <Text style={s.cardTitle}>Add a template</Text>
          <Text style={s.help}>
            1) Download the Excel template & fill your option×factor grid  ·  2) Import it here  ·
            3) Set details → Create  ·  4) Classify factors → it goes live in the public store.
          </Text>
          <View style={s.toolRow}>
            <TouchableOpacity style={[s.tool, { backgroundColor: '#EEF2FF' }]} onPress={() => Linking.openURL(TEMPLATE_URL)}>
              <Ionicons name="download" size={16} color="#4F46E5" />
              <Text style={[s.toolText, { color: '#4F46E5' }]}>Excel template</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.tool, { backgroundColor: '#DCFCE7' }]} onPress={doImportExcel} disabled={busy}>
              <Ionicons name="cloud-upload" size={16} color="#16A34A" />
              <Text style={[s.toolText, { color: '#16A34A' }]}>Import Excel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.tool, { backgroundColor: '#FEF3C7' }]} onPress={() => setGsheetOpen(true)} disabled={busy}>
              <Ionicons name="logo-google" size={16} color="#B45309" />
              <Text style={[s.toolText, { color: '#B45309' }]}>Import Google Sheet</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.tool, { backgroundColor: '#E0F2FE' }]} onPress={openFrom} disabled={busy}>
              <Ionicons name="git-compare" size={16} color="#0369A1" />
              <Text style={[s.toolText, { color: '#0369A1' }]}>Build from Solution Store</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.tool, { backgroundColor: '#F1F5F9' }]} onPress={openSettings} disabled={busy}>
              <Ionicons name="settings" size={16} color="#475569" />
              <Text style={[s.toolText, { color: '#475569' }]}>Finder & Landing</Text>
            </TouchableOpacity>
          </View>
          {parsed && (
            <TouchableOpacity style={s.parsedPill} onPress={() => setShowCreate(true)}>
              <Ionicons name="checkmark-circle" size={14} color="#16A34A" />
              <Text style={s.parsedText}>Parsed {parsed.factors.length} factors · {parsed.options.length} options — tap to create</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* 2-tab filter + Verification filter — same pattern as public
            Decider Store so admins can browse by kind and quickly find
            Unverified items to review. */}
        <View style={s.adminTabBar}>
          <TouchableOpacity style={[s.adminTab, adminKindTab === 'template' && s.adminTabOn]} onPress={() => setAdminKindTab('template')} testID="admin-tab-templates">
            <Ionicons name="document-text" size={13} color={adminKindTab === 'template' ? '#FFF' : '#4F46E5'} />
            <Text style={[s.adminTabText, adminKindTab === 'template' && s.adminTabTextOn]}>Decision Templates ({templates.filter(t => t.kind !== 'app').length})</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[s.adminTab, adminKindTab === 'app' && s.adminTabOn]} onPress={() => setAdminKindTab('app')} testID="admin-tab-apps">
            <Ionicons name="cube" size={13} color={adminKindTab === 'app' ? '#FFF' : '#4F46E5'} />
            <Text style={[s.adminTabText, adminKindTab === 'app' && s.adminTabTextOn]}>Decider Apps ({templates.filter(t => t.kind === 'app').length})</Text>
          </TouchableOpacity>
          <View style={{ flex: 1 }} />
          {(['all', 'jai_verified', 'unverified', 'disapproved'] as const).map((v) => (
            <TouchableOpacity key={v} style={[s.adminVerifChip, adminVerifFilter === v && s.adminVerifChipOn]} onPress={() => setAdminVerifFilter(v)}>
              <Text style={[s.adminVerifText, adminVerifFilter === v && s.adminVerifTextOn]}>
                {v === 'all' ? 'All' : v === 'jai_verified' ? '✓ jAI' : v === 'unverified' ? '⏳ Unv' : '✕ Disap'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Templates list */}
        {loading ? (
          <ActivityIndicator color="#4F46E5" style={{ marginTop: 24 }} />
        ) : (() => {
          const filtered = templates.filter(t => {
            const kindOk = adminKindTab === 'app' ? t.kind === 'app' : t.kind !== 'app';
            const ms = (t as any).moderation_status;
            const verOk = adminVerifFilter === 'all'
              ? true
              : adminVerifFilter === 'unverified'
                ? (!ms || ms === 'unverified')
                : ms === adminVerifFilter;
            return kindOk && verOk;
          });
          if (filtered.length === 0) return <Text style={s.empty}>No {adminKindTab === 'app' ? 'apps' : 'templates'} match the current filters.</Text>;
          return filtered.map(t => (
          <View key={t.template_id} style={s.tCard}>
            <View style={s.tHead}>
              <Text style={s.tTitle} numberOfLines={2}>{t.title}</Text>
              {t.kind === 'app' && (
                <View style={[s.badge, { backgroundColor: '#EEF2FF' }]}>
                  <Text style={[s.badgeText, { color: '#4F46E5' }]}>FINDER</Text>
                </View>
              )}
              <View style={[s.badge, { backgroundColor: t.status === 'authorized' && t.is_public ? '#DCFCE7' : t.status === 'pending' ? '#FEF3C7' : '#E2E8F0' }]}>
                <Text style={[s.badgeText, { color: t.status === 'authorized' && t.is_public ? '#166534' : t.status === 'pending' ? '#B45309' : '#475569' }]}>
                  {t.status === 'authorized' && t.is_public ? 'LIVE' : (t.status || 'draft').toUpperCase()}
                </Text>
              </View>
            </View>
            {!!t.subtitle && <Text style={s.tSub}>{t.subtitle}</Text>}
            <View style={s.tMeta}>
              <Text style={s.tMetaText}>📊 {(t.factors || []).length} factors</Text>
              <Text style={s.tMetaText}>🧩 {(t.options || []).length} options</Text>
              <Text style={s.tMetaText}>{t.pricing_type === 'paid' ? `💰 ₹${((t.price_paise || 0) / 100).toFixed(0)}` : '🆓 Free'}</Text>
              <Text style={s.tMetaText}>⬇️ {t.install_count || 0}</Text>
            </View>
            <View style={s.tMeta}>
              {(t.allowed_clone_modes || []).map(m => (
                <View key={m} style={s.modeChip}><Text style={s.modeChipText}>{m === 'full' ? 'Full clone' : 'Values-only'}</Text></View>
              ))}
            </View>
            <View style={s.tActions}>
              {/* Moderation status pill + one-click toggle. Only enabled
                  when item is public (`status=authorized`). */}
              {t.is_public && (
                (t as any).moderation_status === 'jai_verified' ? (
                  <Tooltip text="Currently jAI Verified · Tap to move back to Unverified">
                    <TouchableOpacity style={[s.act, { backgroundColor: '#D1FAE5' }]} onPress={() => setModerationStatus(t, 'unverified')} testID={`admin-unverify-${t.template_id}`}>
                      <Ionicons name="shield-checkmark" size={13} color="#059669" /><Text style={[s.actText, { color: '#059669' }]}>jAI Verified</Text>
                    </TouchableOpacity>
                  </Tooltip>
                ) : (
                  <Tooltip text="Currently Unverified · Tap to mark as jAI Verified">
                    <TouchableOpacity style={[s.act, { backgroundColor: '#FEF3C7' }]} onPress={() => setModerationStatus(t, 'jai_verified')} testID={`admin-verify-${t.template_id}`}>
                      <Ionicons name="time" size={13} color="#B45309" /><Text style={[s.actText, { color: '#B45309' }]}>Unverified · Verify</Text>
                    </TouchableOpacity>
                  </Tooltip>
                )
              )}
              <Tooltip text="Classify factors as Mandatory/Optional and set priority ratings (used for Full-clone)">
                <TouchableOpacity style={[s.act, { backgroundColor: '#EEF2FF' }]} onPress={() => openClassify(t)}>
                  <Ionicons name="options" size={13} color="#4F46E5" /><Text style={[s.actText, { color: '#4F46E5' }]}>Classify</Text>
                </TouchableOpacity>
              </Tooltip>
              <Tooltip text={t.kind === 'app' ? 'Convert to Template (manual assessment by users)' : 'Convert to Decider App / Finder (fully automated AI assessment)'}>
                <TouchableOpacity style={[s.act, { backgroundColor: '#F1F5F9' }]} onPress={() => toggleKind(t)}>
                  <Ionicons name="swap-horizontal" size={13} color="#475569" /><Text style={[s.actText, { color: '#475569' }]}>{t.kind === 'app' ? '→ Template' : '→ Finder'}</Text>
                </TouchableOpacity>
              </Tooltip>
              <Tooltip text="Link this item to a Central Catalog Manager L0 Life-area / L1 node (for cross-app taxonomy)">
                <TouchableOpacity style={[s.act, { backgroundColor: '#EDE9FE' }]} onPress={() => openCatalog(t)}>
                  <Ionicons name="git-network" size={13} color="#7C3AED" /><Text style={[s.actText, { color: '#7C3AED' }]}>{t.catalog_node_id ? 'Catalog ✓' : 'Catalog'}</Text>
                </TouchableOpacity>
              </Tooltip>
              <Tooltip text="Option Bank — the 10M-scale catalogue of options the Finder ranks against. Bulk import/purge here.">
                <TouchableOpacity style={[s.act, { backgroundColor: '#ECFDF5' }]} onPress={() => openBank(t)}>
                  <Ionicons name="server" size={13} color="#059669" /><Text style={[s.actText, { color: '#059669' }]}>Bank</Text>
                </TouchableOpacity>
              </Tooltip>
              <Tooltip text="Edit each option's per-factor value cells (small tweaks). For bulk edits, use Bank → Download Excel.">
                <TouchableOpacity style={[s.act, { backgroundColor: '#FEF9C3' }]} onPress={() => openData(t)}>
                  <Ionicons name="create" size={13} color="#A16207" /><Text style={[s.actText, { color: '#A16207' }]}>Edit Data</Text>
                </TouchableOpacity>
              </Tooltip>
              <Tooltip text="Push this template's options into Solution Store + create empty ReviewNet rating slots for each">
                <TouchableOpacity style={[s.act, { backgroundColor: '#E0F2FE' }]} onPress={() => pushStores(t)}>
                  <Ionicons name="cloud-upload" size={13} color="#0369A1" /><Text style={[s.actText, { color: '#0369A1' }]}>Push to Stores</Text>
                </TouchableOpacity>
              </Tooltip>
              <Tooltip text="Sync template options from Solution Store (quantitative values) + ReviewNet (qualitative ratings)">
                <TouchableOpacity style={[s.act, { backgroundColor: '#F3E8FF' }]} onPress={() => syncStores(t)}>
                  <Ionicons name="sync" size={13} color="#9333EA" /><Text style={[s.actText, { color: '#9333EA' }]}>Sync</Text>
                </TouchableOpacity>
              </Tooltip>
              {!(t.status === 'authorized' && t.is_public) ? (
                <Tooltip text="Publish this item to the public Decider Store">
                  <TouchableOpacity style={[s.act, { backgroundColor: '#DCFCE7' }]} onPress={() => authorize(t)}>
                    <Ionicons name="rocket" size={13} color="#16A34A" /><Text style={[s.actText, { color: '#16A34A' }]}>Authorize</Text>
                  </TouchableOpacity>
                </Tooltip>
              ) : (
                <Tooltip text="Hide from the public Decider Store (keeps the data; you can re-Authorize any time)">
                  <TouchableOpacity style={[s.act, { backgroundColor: '#FEF9C3' }]} onPress={() => unpublish(t)}>
                    <Ionicons name="eye-off" size={13} color="#A16207" /><Text style={[s.actText, { color: '#A16207' }]}>Unpublish</Text>
                  </TouchableOpacity>
                </Tooltip>
              )}
              <Tooltip text="Edit Publisher Contact & Policies for this item (overrides the global defaults)">
                <TouchableOpacity style={[s.act, { backgroundColor: '#EEF2FF' }]} onPress={() => openPublisherEditor(t)}>
                  <Ionicons name="person-circle" size={13} color="#4F46E5" /><Text style={[s.actText, { color: '#4F46E5' }]}>Publisher</Text>
                </TouchableOpacity>
              </Tooltip>
              <Tooltip text="Permanently delete this template/app. This cannot be undone.">
                <TouchableOpacity style={[s.act, { backgroundColor: '#FEE2E2' }]} onPress={() => remove(t)}>
                  <Ionicons name="trash" size={13} color="#DC2626" /><Text style={[s.actText, { color: '#DC2626' }]}>Delete</Text>
                </TouchableOpacity>
              </Tooltip>
            </View>
          </View>
          ));
        })()}
      </ScrollView>

      {/* Google Sheet URL modal */}
      <Modal visible={gsheetOpen} transparent animationType="fade" onRequestClose={() => setGsheetOpen(false)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <Text style={s.mTitle}>Import from Google Sheet</Text>
            <Text style={s.help}>Make the sheet link-shareable (Anyone with the link) or Publish-to-web, then paste its URL.</Text>
            <TextInput style={s.input} value={gsheetUrl} onChangeText={setGsheetUrl} placeholder="https://docs.google.com/spreadsheets/d/…" placeholderTextColor="#9CA3AF" autoCapitalize="none" />
            <View style={s.mBtns}>
              <TouchableOpacity style={s.mCancel} onPress={() => setGsheetOpen(false)}><Text style={s.mCancelText}>Cancel</Text></TouchableOpacity>
              <TouchableOpacity style={s.mSave} onPress={doImportGsheet} disabled={busy}>
                {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.mSaveText}>Import</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Finder defaults + Landing page settings modal */}
      <Modal visible={settingsOpen} transparent animationType="slide" onRequestClose={() => setSettingsOpen(false)}>
        <View style={s.overlay}>
          <View style={s.modalCard}>
            <View style={s.mHead}>
              <Text style={s.mTitle}>Finder & Landing settings</Text>
              <TouchableOpacity onPress={() => setSettingsOpen(false)}><Ionicons name="close" size={22} color="#64748B" /></TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ paddingBottom: 20 }}>
              <Text style={s.secLabel}>🔍 Finder defaults (users can override per run)</Text>
              <View style={s.row2}>
                <View style={{ flex: 1 }}><Text style={s.label}>Min options</Text>
                  <TextInput style={s.input} value={fdMin} onChangeText={setFdMin} keyboardType="numeric" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>Max options</Text>
                  <TextInput style={s.input} value={fdMax} onChangeText={setFdMax} keyboardType="numeric" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>Top N</Text>
                  <TextInput style={s.input} value={fdTop} onChangeText={setFdTop} keyboardType="numeric" /></View>
              </View>
              <Text style={s.label}>Sub-factor match rule</Text>
              <View style={s.kindRow}>
                {(['all', 'any'] as const).map((m) => (
                  <TouchableOpacity key={m} style={[s.kindBtn, fdMatch === m && s.kindOnApp]} onPress={() => setFdMatch(m)}>
                    <Text style={[s.kindTitle, fdMatch === m && { color: '#FFF' }]}>{m === 'all' ? 'Match ALL' : 'Match ANY'}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={s.label}>Assessment engine</Text>
              <View style={s.kindRow}>
                {(['deterministic', 'llm'] as const).map((m) => (
                  <TouchableOpacity key={m} style={[s.kindBtn, fdEngine === m && s.kindOnApp]} onPress={() => setFdEngine(m)}>
                    <Text style={[s.kindTitle, fdEngine === m && { color: '#FFF' }]}>{m === 'deterministic' ? '⚡ Fast (rules)' : '🤖 AI (LLM)'}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={[s.secLabel, { marginTop: 20 }]}>📣 Sponsored Solutions (global defaults)</Text>
              <Text style={s.help}>
                Min Cutoff % = quality gate for ad eligibility · N = Sponsored slots shown BELOW organic.
                Central-Catalog nodes can override per LifeArea/SubArea/Scenario (Admin → AdMaker & AdTaker → Cutoffs).
              </Text>
              <View style={s.row2}>
                <View style={{ flex: 1 }}><Text style={s.label}>Min Cutoff %</Text>
                  <TextInput style={s.input} value={fdCutoff} onChangeText={setFdCutoff} keyboardType="numeric" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>Sponsored slots (N)</Text>
                  <TextInput style={s.input} value={fdSponsN} onChangeText={setFdSponsN} keyboardType="numeric" /></View>
              </View>

              <Text style={[s.secLabel, { marginTop: 20 }]}>🌐 TheDecider.store landing page</Text>
              <Text style={s.help}>Edit the public landing page. Preview: /api/decider-store/landing.html</Text>
              <Text style={s.label}>Title</Text>
              <TextInput style={s.input} value={ldTitle} onChangeText={setLdTitle} placeholder="The Decider Store" placeholderTextColor="#9CA3AF" />
              <Text style={s.label}>Subtitle</Text>
              <TextInput style={s.input} value={ldSubtitle} onChangeText={setLdSubtitle} placeholderTextColor="#9CA3AF" />
              <Text style={s.label}>Hero paragraph</Text>
              <TextInput style={[s.input, { height: 80 }]} value={ldHero} onChangeText={setLdHero} multiline placeholderTextColor="#9CA3AF" />
              <Text style={s.label}>CTA button label</Text>
              <TextInput style={s.input} value={ldCta} onChangeText={setLdCta} placeholder="Explore Decider Apps" placeholderTextColor="#9CA3AF" />
              <Text style={s.label}>CTA target URL (opens masked)</Text>
              <TextInput style={s.input} value={ldTarget} onChangeText={setLdTarget} autoCapitalize="none" placeholder="https://jelcos.ai/decider-store" placeholderTextColor="#9CA3AF" />
              <TouchableOpacity style={s.createBtn} onPress={saveSettings} disabled={busy}>
                {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.createBtnText}>Save settings</Text>}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Central-Catalog (Scenario) mapping modal */}
      <Modal visible={!!catForId} transparent animationType="fade" onRequestClose={() => setCatForId(null)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHeader}>
              <Text style={s.mTitle}>Map to Central Catalog</Text>
              <TouchableOpacity onPress={() => setCatForId(null)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            <Text style={s.help}>
              The mapped LifeArea/SubArea/Scenario node decides which Min-Cutoff % and Sponsored-slot
              defaults apply to this app&apos;s Finder results (nearest configured ancestor wins).
            </Text>
            {(() => {
              const cur = templates.find(t => t.template_id === catForId);
              const name = cur?.catalog_node_id
                ? (catNodes.find(n => n.node_id === cur.catalog_node_id)?.name || cur.catalog_node_id)
                : 'not mapped (global defaults apply)';
              return <Text style={s.curMap}>Current: {name}</Text>;
            })()}
            <TextInput style={s.input} value={catSearch} onChangeText={setCatSearch}
              placeholder="Search nodes…" placeholderTextColor="#9CA3AF" />
            <ScrollView style={{ maxHeight: 300 }}>
              {catNodes
                .filter(n => { const q = catSearch.trim().toLowerCase(); return !q || (n.name || '').toLowerCase().includes(q); })
                .slice(0, 40).map(n => (
                  <TouchableOpacity key={n.node_id} style={s.catRow} onPress={() => setCatalogNode(n.node_id)}>
                    <Text style={s.catLevel}>L{n.level}</Text>
                    <Text style={s.catName} numberOfLines={1}>{n.name}</Text>
                  </TouchableOpacity>
                ))}
            </ScrollView>
            <TouchableOpacity style={s.clearMapBtn} onPress={() => setCatalogNode(null)}>
              <Text style={s.clearMapText}>Clear mapping</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Option Bank modal (10M-scale Finder ingestion) */}
      <Modal visible={!!bankForId} transparent animationType="fade" statusBarTranslucent onRequestClose={() => setBankForId(null)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHeader}>
              <Text style={s.mTitle}>Option Bank</Text>
              <TouchableOpacity onPress={() => setBankForId(null)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            <Text style={s.help}>
              The indexed Option Bank powers the scaled Finder (streamed Top-K over millions of
              options). Sources: this template&apos;s own options, bridged Solution Store + ReviewNet
              items, partner APIs and Deep-Import (via the bank ingest API).
            </Text>
            {!bankStats ? <ActivityIndicator color="#059669" style={{ marginVertical: 16 }} /> : (
              <>
                <Text style={s.bankTotal}>{(bankStats.total || 0).toLocaleString()} options in bank</Text>
                {Object.entries(bankStats.by_source || {}).map(([src, n]: any) => (
                  <Text key={src} style={s.bankSrc}>• {src}: {Number(n).toLocaleString()}</Text>
                ))}
                {/* Bulk edit affordance — export the whole bank to Excel,
                    edit locally, re-import. Way faster than "Edit Data"
                    for multi-option updates. */}
                <TouchableOpacity style={[s.bankBtn, { backgroundColor: '#065F46' }]} disabled={bankBusy}
                  onPress={() => downloadBankExcel()}
                  testID="admin-bank-download-xlsx">
                  <Text style={s.bankBtnText}>⬇ Download Bank as Excel/CSV (bulk edit)</Text>
                </TouchableOpacity>
                {/* Upload edited CSV back. Web-only file picker — hidden
                    <input> triggered by a styled button. */}
                {Platform.OS === 'web' && (
                  <View>
                    <TouchableOpacity style={[s.bankBtn, { backgroundColor: '#1D4ED8' }]} disabled={bankBusy}
                      onPress={() => {
                        try {
                          // @ts-ignore — DOM only on web
                          (document.getElementById('bank-upload-input') as HTMLInputElement)?.click();
                        } catch {}
                      }} testID="admin-bank-upload-xlsx">
                      <Text style={s.bankBtnText}>⬆ Upload edited CSV / Excel</Text>
                    </TouchableOpacity>
                    {/* @ts-ignore — raw HTML on web only */}
                    <input
                      id="bank-upload-input"
                      type="file"
                      accept=".csv,text/csv,application/vnd.ms-excel"
                      style={{ display: 'none' }}
                      onChange={(e: any) => {
                        const file = e.target.files?.[0];
                        if (file) uploadBankCsv(file);
                        e.target.value = '';
                      }}
                    />
                  </View>
                )}
                <TouchableOpacity style={[s.bankBtn, { backgroundColor: '#059669' }]} disabled={bankBusy}
                  onPress={() => bankAction('sync-template')}>
                  <Text style={s.bankBtnText}>Sync template options → bank</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[s.bankBtn, { backgroundColor: '#0369A1' }]} disabled={bankBusy}
                  onPress={() => bankAction('ingest/solutions')}>
                  <Text style={s.bankBtnText}>Ingest bridged Solution Store + ReviewNet</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[s.bankBtn, { backgroundColor: '#FEE2E2' }]} disabled={bankBusy}
                  onPress={() => bankAction('', 'delete')}>
                  <Text style={[s.bankBtnText, { color: '#DC2626' }]}>Clear bank</Text>
                </TouchableOpacity>
                <Text style={s.bankApiNote}>
                  Bulk import via Excel: after downloading, edit values, then hit the &ldquo;Ingest bulk&rdquo; API
                  (POST /api/decider-store/{bankForId}/bank/ingest/bulk) with the rows JSON.
                  Partner API: POST /api/decider-store/{bankForId}/bank/ingest/partner.
                </Text>
                {/* In-modal inline banner — replaces the system Alert
                    which used to render BEHIND the modal on web/RN Web. */}
                {!!bankToast && (
                  <View style={[s.bankBtn, { backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0' }]}>
                    <Text style={[s.bankBtnText, { color: '#065F46' }]}>{bankToast}</Text>
                  </View>
                )}
              </>
            )}
          </View>
        </View>
      </Modal>


      {/* Create modal */}
      <Modal visible={showCreate} transparent animationType="slide" onRequestClose={() => setShowCreate(false)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHeader}>
              <Text style={s.mTitle}>New template</Text>
              <TouchableOpacity onPress={() => setShowCreate(false)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 480 }}>
              {parsed && <Text style={s.parsedText}>{parsed.factors.length} factors · {parsed.options.length} options ready</Text>}
              <Text style={s.label}>Title *</Text>
              <TextInput style={s.input} value={fTitle} onChangeText={setFTitle} placeholder="The 55 Business Model Patterns" placeholderTextColor="#9CA3AF" />
              <Text style={s.label}>Subtitle</Text>
              <TextInput style={s.input} value={fSubtitle} onChangeText={setFSubtitle} placeholder="One-line hook" placeholderTextColor="#9CA3AF" />
              <Text style={s.label}>Description</Text>
              <TextInput style={[s.input, { height: 72 }]} value={fDesc} onChangeText={setFDesc} placeholder="What this template helps decide" placeholderTextColor="#9CA3AF" multiline />
              <Text style={s.label}>Category</Text>
              <View style={s.chipsWrap}>
                {CATEGORIES.map(c => (
                  <TouchableOpacity key={c} style={[s.chip, fCategory === c && s.chipOn]} onPress={() => setFCategory(c)}>
                    <Text style={[s.chipText, fCategory === c && s.chipTextOn]}>{c}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={s.label}>Decision type</Text>
              <View style={s.chipsWrap}>
                {DECISION_TYPES.map(d => (
                  <TouchableOpacity key={d.id} style={[s.chip, fType === d.id && s.chipOn]} onPress={() => setFType(d.id)}>
                    <Text style={[s.chipText, fType === d.id && s.chipTextOn]}>{d.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={s.label}>Store kind</Text>
              <View style={s.kindRow}>
                <TouchableOpacity style={[s.kindBtn, fKind === 'template' && s.kindOn]} onPress={() => setFKind('template')}>
                  <Ionicons name="documents" size={16} color={fKind === 'template' ? '#FFF' : '#0D9488'} />
                  <View style={{ flex: 1 }}>
                    <Text style={[s.kindTitle, fKind === 'template' && { color: '#FFF' }]}>Decision Template</Text>
                    <Text style={[s.kindSub, fKind === 'template' && { color: '#D1FAE5' }]}>User assesses options manually</Text>
                  </View>
                </TouchableOpacity>
                <TouchableOpacity style={[s.kindBtn, fKind === 'app' && s.kindOnApp]} onPress={() => setFKind('app')}>
                  <Ionicons name="search-circle" size={16} color={fKind === 'app' ? '#FFF' : '#4F46E5'} />
                  <View style={{ flex: 1 }}>
                    <Text style={[s.kindTitle, fKind === 'app' && { color: '#FFF' }]}>DeciderApp · Finder</Text>
                    <Text style={[s.kindSub, fKind === 'app' && { color: '#E0E7FF' }]}>System auto-ranks Top-N</Text>
                  </View>
                </TouchableOpacity>
              </View>
              <Text style={s.label}>Clone modes offered</Text>
              <View style={s.rowBetween}>
                <Text style={s.switchLabel}>Full (factors + mandatory/optional + priority + options + values)</Text>
                <Switch value={fModeFull} onValueChange={setFModeFull} />
              </View>
              <View style={s.rowBetween}>
                <Text style={s.switchLabel}>Values-only (user classifies & prioritizes)</Text>
                <Switch value={fModeValues} onValueChange={setFModeValues} />
              </View>
              <View style={s.rowBetween}>
                <Text style={s.switchLabel}>Paid template</Text>
                <Switch value={fPaid} onValueChange={setFPaid} />
              </View>
              <View style={s.rowBetween}>
                <Text style={s.switchLabel}>Auto-push to Solution Store & ReviewNet on Authorize</Text>
                <Switch value={fAutoPush} onValueChange={setFAutoPush} />
              </View>
              {fPaid && (
                <View style={s.row2}>
                  <View style={{ flex: 1 }}>
                    <Text style={s.label}>Price (₹)</Text>
                    <TextInput style={s.input} value={fPrice} onChangeText={setFPrice} placeholder="499" placeholderTextColor="#9CA3AF" keyboardType="numeric" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.label}>Creator split %</Text>
                    <TextInput style={s.input} value={fSplit} onChangeText={setFSplit} placeholder="70" placeholderTextColor="#9CA3AF" keyboardType="numeric" />
                  </View>
                </View>
              )}
              <TouchableOpacity style={s.createBtn} onPress={createTemplate} disabled={busy}>
                {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.createBtnText}>Create & Authorize</Text>}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* Build from Solution Store modal */}
      <Modal visible={fromOpen} transparent animationType="slide" onRequestClose={() => setFromOpen(false)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHeader}>
              <Text style={s.mTitle}>Build from Solution Store</Text>
              <TouchableOpacity onPress={() => setFromOpen(false)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            <Text style={s.help}>Pick Strategy solutions — their quantitative factors + ReviewNet qualitative baselines become a new Decider template.</Text>
            <Text style={s.label}>New template title *</Text>
            <TextInput style={s.input} value={fsTitle} onChangeText={setFsTitle} placeholder="e.g. Growth Strategies 2026" placeholderTextColor="#9CA3AF" />
            <ScrollView style={{ maxHeight: 320, marginTop: 10 }}>
              {solList.length === 0 ? (
                <Text style={s.empty}>No Strategy solutions found. Push a template to Stores first.</Text>
              ) : solList.map((sol) => {
                const on = !!selSols[sol.solution_id];
                return (
                  <TouchableOpacity key={sol.solution_id} style={s.solRow}
                    onPress={() => setSelSols(prev => ({ ...prev, [sol.solution_id]: !prev[sol.solution_id] }))}>
                    <Ionicons name={on ? 'checkbox' : 'square-outline'} size={20} color={on ? '#0369A1' : '#94A3B8'} />
                    <View style={{ flex: 1 }}>
                      <Text style={s.solName} numberOfLines={1}>{sol.name}</Text>
                      <Text style={s.solMeta} numberOfLines={1}>{(sol.quantitative_factors || []).length} quant · {sol.decider_template_id ? 'from Decider' : sol.type}</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
            <TouchableOpacity style={s.createBtn} onPress={buildFromSolutions} disabled={busy}>
              {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.createBtnText}>Create template</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Per-cell option/value editor modal */}
      <Modal visible={!!dataId} transparent animationType="slide" onRequestClose={() => setDataId(null)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHeader}>
              <Text style={s.mTitle}>Edit option values</Text>
              <TouchableOpacity onPress={() => setDataId(null)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            <Text style={s.help}>Tap an option to edit its per-sub-factor values (one input per sub-factor). Enter the value (e.g. 100 for 100%). Leave blank if N/A.</Text>
            <View style={s.search}>
              <Ionicons name="search" size={15} color="#94A3B8" />
              <TextInput style={s.searchInput} value={optSearch} onChangeText={setOptSearch} placeholder="Filter options…" placeholderTextColor="#9CA3AF" />
            </View>
            <ScrollView style={{ maxHeight: 420, marginTop: 8 }}>
              {dataOpts
                .filter(o => !optSearch || (o.name || '').toLowerCase().includes(optSearch.toLowerCase()))
                .map((o) => {
                  const open = expandedOpt === o.id;
                  return (
                    <View key={o.id} style={s.optCard}>
                      <View style={s.optHead}>
                        <TouchableOpacity style={s.optHeadMain} onPress={() => setExpandedOpt(open ? null : o.id)}>
                          <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={16} color="#64748B" />
                          <TextInput
                            style={s.optNameInput}
                            value={o.name}
                            onChangeText={(v) => setDataOpts(prev => prev.map(x => x.id === o.id ? { ...x, name: v } : x))}
                            placeholder="Option name"
                            placeholderTextColor="#9CA3AF"
                          />
                        </TouchableOpacity>
                        <TouchableOpacity onPress={() => deleteOption(o.id)}><Ionicons name="trash-outline" size={18} color="#DC2626" /></TouchableOpacity>
                      </View>
                      {open && dataFactors.map((f) => (
                        <View key={f.id} style={s.facBlock}>
                          <Text style={s.facBlockName} numberOfLines={2}>{f.name}
                            <Text style={s.cellType}>{(f.factor_type === 'quantitative') ? '  ·Quant' : '  ·Qual'}</Text>
                          </Text>
                          {subsOf(f).map((sf) => (
                            <View key={sf.id} style={s.cellRow}>
                              <Text style={s.cellLabel} numberOfLines={1}>{sf.name}
                                {sf.split_pct != null && <Text style={s.cellType}>{`  (split ${sf.split_pct}%)`}</Text>}
                              </Text>
                              <TextInput
                                style={s.cellInput}
                                value={cellText[`${o.id}::${sf.id}`] || ''}
                                onChangeText={(v) => setCellText(prev => ({ ...prev, [`${o.id}::${sf.id}`]: v }))}
                                placeholder={sf.data_type || '%'}
                                placeholderTextColor="#CBD5E1"
                                keyboardType={((sf.data_type || '').toLowerCase().startsWith('text')) ? 'default' : 'numeric'}
                              />
                            </View>
                          ))}
                        </View>
                      ))}
                    </View>
                  );
                })}
              <TouchableOpacity style={s.addOptBtn} onPress={addOption}>
                <Ionicons name="add-circle" size={18} color="#4F46E5" /><Text style={s.addOptText}>Add option</Text>
              </TouchableOpacity>
            </ScrollView>
            <TouchableOpacity style={s.createBtn} onPress={saveData} disabled={busy}>
              {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.createBtnText}>Save option values</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Classify factors modal */}
      <Modal visible={!!classifyId} transparent animationType="slide" onRequestClose={() => setClassifyId(null)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHeader}>
              <Text style={s.mTitle}>Classify factors</Text>
              <TouchableOpacity onPress={() => setClassifyId(null)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            <Text style={s.help}>Set Mandatory/Optional & Priority (1–10) — used when a user picks {'"Full clone"'}.</Text>
            <ScrollView style={{ maxHeight: 460 }}>
              {classFactors.map((f, i) => (
                <View key={f.id} style={s.facRow}>
                  <Text style={s.facName} numberOfLines={2}>{i + 1}. {f.name}</Text>
                  <View style={s.facControls}>
                    <TouchableOpacity
                      style={[s.segBtn, (f.category === 'mandatory' || !f.category) && s.segMand]}
                      onPress={() => setClassFactors(prev => prev.map((x, j) => j === i ? { ...x, category: 'mandatory' } : x))}>
                      <Text style={[s.segText, (f.category === 'mandatory' || !f.category) && { color: '#FFF' }]}>Mandatory</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[s.segBtn, f.category === 'optional' && s.segOpt]}
                      onPress={() => setClassFactors(prev => prev.map((x, j) => j === i ? { ...x, category: 'optional' } : x))}>
                      <Text style={[s.segText, f.category === 'optional' && { color: '#FFF' }]}>Optional</Text>
                    </TouchableOpacity>
                    <View style={s.priBox}>
                      <TouchableOpacity onPress={() => setClassFactors(prev => prev.map((x, j) => j === i ? { ...x, priority: Math.max(0, (x.priority || 0) - 1) } : x))}><Ionicons name="remove-circle" size={20} color="#94A3B8" /></TouchableOpacity>
                      <Text style={s.priNum}>{f.priority || 0}</Text>
                      <TouchableOpacity onPress={() => setClassFactors(prev => prev.map((x, j) => j === i ? { ...x, priority: Math.min(10, (x.priority || 0) + 1) } : x))}><Ionicons name="add-circle" size={20} color="#4F46E5" /></TouchableOpacity>
                    </View>
                  </View>
                  <View style={s.facTypeRow}>
                    <Text style={s.facTypeLabel}>Type:</Text>
                    <TouchableOpacity
                      style={[s.typeBtn, (f.factor_type || 'qualitative') === 'quantitative' && s.typeQuant]}
                      onPress={() => setClassFactors(prev => prev.map((x, j) => j === i ? { ...x, factor_type: 'quantitative' } : x))}>
                      <Ionicons name="stats-chart" size={12} color={(f.factor_type || '') === 'quantitative' ? '#FFF' : '#0369A1'} />
                      <Text style={[s.typeText, (f.factor_type || '') === 'quantitative' && { color: '#FFF' }]}>Quantitative → Solution Store</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={[s.typeBtn, (f.factor_type || 'qualitative') === 'qualitative' && s.typeQual]}
                      onPress={() => setClassFactors(prev => prev.map((x, j) => j === i ? { ...x, factor_type: 'qualitative' } : x))}>
                      <Ionicons name="chatbubbles" size={12} color={(f.factor_type || 'qualitative') === 'qualitative' ? '#FFF' : '#9333EA'} />
                      <Text style={[s.typeText, (f.factor_type || 'qualitative') === 'qualitative' && { color: '#FFF' }]}>Qualitative → ReviewNet</Text>
                    </TouchableOpacity>
                  </View>
                  {!!(f.sub_factors && f.sub_factors.length) && (
                    <View style={s.subWrap}>
                      {(() => {
                        const sum = Math.round((f.sub_factors || []).reduce((a, x) => a + (x.split_pct || 0), 0) * 100) / 100;
                        const ok = Math.abs(sum - 100) <= 0.5;
                        return <Text style={[s.subHint, !ok && { color: '#DC2626' }]}>Sub-factors · Split total {sum}% {ok ? '✓' : '(should be 100%)'}</Text>;
                      })()}
                      {(f.sub_factors || []).map((sf, si) => (
                        <View key={sf.id} style={s.subRow}>
                          <Text style={s.subName} numberOfLines={1}>{sf.name}</Text>
                          <Text style={s.subMeta}>{sf.data_type || '%'}</Text>
                          <View style={s.subSplit}>
                            <TextInput
                              style={s.subSplitInput}
                              value={String(sf.split_pct ?? '')}
                              keyboardType="numeric"
                              onChangeText={(v) => setClassFactors(prev => prev.map((x, j) => j === i
                                ? { ...x, sub_factors: (x.sub_factors || []).map((y, k) => k === si ? { ...y, split_pct: parseFloat(v) || 0 } : y) }
                                : x))}
                            />
                            <Text style={s.subPct}>%</Text>
                          </View>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              ))}
            </ScrollView>
            <TouchableOpacity style={s.createBtn} onPress={saveClassify} disabled={busy}>
              {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.createBtnText}>Save classification</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Per-item Publisher Contact & Policies override */}
      <Modal visible={!!pubEditItem} transparent animationType="slide" onRequestClose={() => setPubEditItem(null)}>
        <View style={s.overlay}>
          <View style={s.modalCard}>
            <View style={s.mHead}>
              <Text style={s.mTitle}>Publisher Contact · {pubEditItem?.title}</Text>
              <TouchableOpacity onPress={() => setPubEditItem(null)}><Ionicons name="close" size={22} color="#64748B" /></TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ paddingBottom: 20 }}>
              <Text style={s.help}>Overrides the global Publisher Defaults for this specific item. Placeholders show the current global default — leave a field blank to inherit it.</Text>
              <Text style={s.secLabel}>👤 Lead-gen contact</Text>
              <TextInput style={s.input} value={pubContactName} onChangeText={setPubContactName} placeholder={pubGlobal.contact_name || 'Contact name'} placeholderTextColor="#9CA3AF" />
              <TextInput style={s.input} value={pubOrg} onChangeText={setPubOrg} placeholder={pubGlobal.organization || 'Organization'} placeholderTextColor="#9CA3AF" />
              <TextInput style={s.input} value={pubDesignation} onChangeText={setPubDesignation} placeholder={pubGlobal.designation || 'Designation'} placeholderTextColor="#9CA3AF" />
              <TextInput style={s.input} value={pubEmail} onChangeText={setPubEmail} placeholder={pubGlobal.email || 'Email'} placeholderTextColor="#9CA3AF" autoCapitalize="none" keyboardType="email-address" />
              <TextInput style={s.input} value={pubWhatsapp} onChangeText={setPubWhatsapp} placeholder={pubGlobal.whatsapp || 'WhatsApp (with country code)'} placeholderTextColor="#9CA3AF" keyboardType="phone-pad" />
              <TextInput style={s.input} value={pubMobile} onChangeText={setPubMobile} placeholder={pubGlobal.mobile || 'Mobile'} placeholderTextColor="#9CA3AF" keyboardType="phone-pad" />
              <TextInput style={s.input} value={pubRedirectUrl} onChangeText={setPubRedirectUrl} placeholder={pubGlobal.redirect_url || 'Website / Redirect URL'} placeholderTextColor="#9CA3AF" autoCapitalize="none" />
              <Text style={s.secLabel}>📜 Policies (URLs shown to end-users before Clone)</Text>
              <TextInput style={s.input} value={pubPrivacyUrl} onChangeText={setPubPrivacyUrl} placeholder="Privacy Policy URL" placeholderTextColor="#9CA3AF" autoCapitalize="none" />
              <TextInput style={s.input} value={pubTermsUrl} onChangeText={setPubTermsUrl} placeholder="Terms of Use URL" placeholderTextColor="#9CA3AF" autoCapitalize="none" />
            </ScrollView>
            <View style={s.mBtns}>
              <TouchableOpacity style={s.mCancel} onPress={() => setPubEditItem(null)}><Text style={s.mCancelText}>Cancel</Text></TouchableOpacity>
              <TouchableOpacity style={s.mSave} onPress={savePublisherEditor} disabled={busy}>
                {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.mSaveText}>Save</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  backBtn: { padding: 4 },
  title: { fontSize: 20, fontWeight: '800', color: '#0F172A' },
  sub: { fontSize: 12, color: '#64748B', marginTop: 2 },
  pubDefaultsBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 8, backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#C7D2FE' },
  pubDefaultsText: { fontSize: 12, fontWeight: '700', color: '#4F46E5' },
  body: { padding: 16, paddingBottom: 60, maxWidth: 640, width: '100%', alignSelf: 'center' },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 16 },
  cardTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', marginBottom: 6 },
  help: { fontSize: 12, color: '#64748B', marginBottom: 10, lineHeight: 17 },
  toolRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tool: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10 },
  toolText: { fontSize: 12.5, fontWeight: '700' },
  parsedPill: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, backgroundColor: '#F0FDF4', borderRadius: 10, padding: 10 },
  parsedText: { fontSize: 12.5, color: '#166534', fontWeight: '600' },
  empty: { textAlign: 'center', color: '#94A3B8', marginTop: 24 },
  adminTabBar: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap', paddingHorizontal: 12, paddingVertical: 10, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0', marginBottom: 8, borderRadius: 10 },
  adminTab: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#C7D2FE' },
  adminTabOn: { backgroundColor: '#4F46E5', borderColor: '#4F46E5' },
  adminTabText: { fontSize: 12, fontWeight: '800', color: '#4F46E5' },
  adminTabTextOn: { color: '#FFF' },
  adminVerifChip: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 999, backgroundColor: '#F1F5F9', borderWidth: 1, borderColor: 'transparent' },
  adminVerifChipOn: { backgroundColor: '#065F46' },
  adminVerifText: { fontSize: 10.5, fontWeight: '800', color: '#334155' },
  adminVerifTextOn: { color: '#FFF' },
  tCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 12 },
  tHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  tTitle: { flex: 1, fontSize: 15, fontWeight: '800', color: '#0F172A' },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  badgeText: { fontSize: 10, fontWeight: '800' },
  tSub: { fontSize: 12.5, color: '#64748B', marginTop: 4 },
  tMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 8 },
  tMetaText: { fontSize: 12, color: '#475569' },
  modeChip: { backgroundColor: '#EEF2FF', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  modeChipText: { fontSize: 10.5, color: '#4F46E5', fontWeight: '700' },
  tActions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  act: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 9 },
  actText: { fontSize: 12, fontWeight: '700' },
  overlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.5)', justifyContent: 'flex-end', alignItems: 'center' },
  modalCard: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, width: '100%', maxWidth: 560, maxHeight: '90%', alignSelf: 'center' },
  mHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  secLabel: { fontSize: 13.5, fontWeight: '800', color: '#0F172A', marginTop: 8, marginBottom: 6 },
  kindRow: { flexDirection: 'row', gap: 10, marginBottom: 4 },
  kindBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 12, padding: 11, backgroundColor: '#FFF' },
  kindOn: { backgroundColor: '#0D9488', borderColor: '#0D9488' },
  kindOnApp: { backgroundColor: '#4F46E5', borderColor: '#4F46E5' },
  kindTitle: { fontSize: 13, fontWeight: '800', color: '#0F172A' },
  kindSub: { fontSize: 10.5, color: '#64748B', marginTop: 1 },
  sheet: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, width: '100%', maxWidth: 520, alignSelf: 'center' },
  mHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  mTitle: { fontSize: 17, fontWeight: '800', color: '#0F172A' },
  label: { fontSize: 12.5, fontWeight: '700', color: '#334155', marginTop: 12, marginBottom: 5 },
  input: { backgroundColor: '#F8FAFC', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A', borderWidth: 1, borderColor: '#E2E8F0' },
  chipsWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { paddingHorizontal: 11, paddingVertical: 7, borderRadius: 16, borderWidth: 1, borderColor: '#E2E8F0', backgroundColor: '#FFF' },
  chipOn: { backgroundColor: '#4F46E5', borderColor: '#4F46E5' },
  chipText: { fontSize: 12, color: '#475569', fontWeight: '600' },
  chipTextOn: { color: '#FFF' },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 12 },
  switchLabel: { flex: 1, fontSize: 12.5, color: '#334155' },
  row2: { flexDirection: 'row', gap: 12 },
  createBtn: { backgroundColor: '#4F46E5', borderRadius: 12, paddingVertical: 13, alignItems: 'center', marginTop: 16 },
  createBtnText: { color: '#FFF', fontSize: 14.5, fontWeight: '800' },
  mBtns: { flexDirection: 'row', gap: 10, marginTop: 16 },
  mCancel: { flex: 1, paddingVertical: 12, borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', alignItems: 'center' },
  mCancelText: { color: '#475569', fontWeight: '700' },
  mSave: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#4F46E5', alignItems: 'center' },
  mSaveText: { color: '#FFF', fontWeight: '800' },
  facRow: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  facName: { fontSize: 13, fontWeight: '600', color: '#0F172A', marginBottom: 6 },
  facControls: { flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' },
  segBtn: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: '#E2E8F0', backgroundColor: '#FFF' },
  segMand: { backgroundColor: '#4F46E5', borderColor: '#4F46E5' },
  segOpt: { backgroundColor: '#0D9488', borderColor: '#0D9488' },
  segText: { fontSize: 11.5, fontWeight: '700', color: '#475569' },
  priBox: { flexDirection: 'row', alignItems: 'center', gap: 6, marginLeft: 'auto' },
  priNum: { fontSize: 14, fontWeight: '800', color: '#0F172A', minWidth: 18, textAlign: 'center' },
  facTypeRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, flexWrap: 'wrap' },
  facTypeLabel: { fontSize: 11.5, color: '#64748B', fontWeight: '700' },
  typeBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 9, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: '#E2E8F0', backgroundColor: '#FFF' },
  typeQuant: { backgroundColor: '#0369A1', borderColor: '#0369A1' },
  typeQual: { backgroundColor: '#9333EA', borderColor: '#9333EA' },
  typeText: { fontSize: 10.5, fontWeight: '700', color: '#475569' },
  solRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  solName: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  solMeta: { fontSize: 11, color: '#94A3B8', marginTop: 1 },
  search: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F1F5F9', borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8, marginTop: 8 },
  searchInput: { flex: 1, fontSize: 13, color: '#0F172A', padding: 0 },
  optCard: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, padding: 10, marginBottom: 8 },
  optHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  optHeadMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 },
  optNameInput: { flex: 1, fontSize: 13.5, fontWeight: '700', color: '#0F172A', paddingVertical: 4 },
  cellRow: { marginTop: 8 },
  facBlock: { marginTop: 10, borderTopWidth: 1, borderTopColor: '#F1F5F9', paddingTop: 6 },
  facBlockName: { fontSize: 12.5, fontWeight: '800', color: '#334155' },
  subWrap: { marginTop: 8, backgroundColor: '#F8FAFC', borderRadius: 8, padding: 8 },
  subHint: { fontSize: 11, fontWeight: '700', color: '#16A34A', marginBottom: 4 },
  subRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 3 },
  subName: { flex: 1, fontSize: 12, color: '#0F172A' },
  subMeta: { fontSize: 10.5, color: '#94A3B8', width: 52, textAlign: 'right' },
  subSplit: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  subSplitInput: { width: 46, backgroundColor: '#FFF', borderRadius: 6, borderWidth: 1, borderColor: '#E2E8F0', paddingVertical: 4, paddingHorizontal: 6, fontSize: 12, color: '#0F172A', textAlign: 'center' },
  subPct: { fontSize: 11, color: '#64748B' },
  cellLabel: { fontSize: 11.5, fontWeight: '700', color: '#475569', marginBottom: 3 },
  cellType: { fontSize: 10, fontWeight: '600', color: '#94A3B8' },
  cellInput: { backgroundColor: '#F8FAFC', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 12.5, color: '#0F172A', borderWidth: 1, borderColor: '#E2E8F0' },
  addOptBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, marginTop: 4 },
  addOptText: { fontSize: 13, fontWeight: '700', color: '#4F46E5' },
  curMap: { fontSize: 12, fontWeight: '700', color: '#7C3AED', marginBottom: 8 },
  catRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, paddingHorizontal: 8, borderRadius: 8 },
  catLevel: { fontSize: 10, fontWeight: '900', color: '#94A3B8', width: 22 },
  catName: { flex: 1, fontSize: 13, fontWeight: '600', color: '#0F172A' },
  clearMapBtn: { alignItems: 'center', paddingVertical: 10, marginTop: 6 },
  clearMapText: { fontSize: 12.5, fontWeight: '700', color: '#DC2626' },
  bankTotal: { fontSize: 15, fontWeight: '900', color: '#059669', marginBottom: 4 },
  bankSrc: { fontSize: 12, color: '#475569', fontWeight: '600', marginBottom: 2 },
  bankBtn: { borderRadius: 10, paddingVertical: 11, alignItems: 'center', marginTop: 8 },
  bankBtnText: { color: '#FFF', fontSize: 13, fontWeight: '800' },
  bankApiNote: { fontSize: 10.5, color: '#94A3B8', marginTop: 10, lineHeight: 15 },
});
