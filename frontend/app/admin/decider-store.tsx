/**
 * Admin · The Decider Store — author & authorize public Decision Templates.
 *
 * Flow: Download the Excel template → fill option×factor grid → Import (Excel or
 * Google Sheet) → set metadata/pricing/clone-modes → Create → Classify factors
 * (mandatory/optional + priority) → Authorize (goes public).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, Switch, Platform, Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';
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

type Factor = {
  id: string; name: string; order?: number; factor_type?: string;
  category?: string; priority?: number; possible_values?: string[];
  has_sub_pct?: boolean;
};
type Template = {
  template_id: string; title: string; subtitle?: string; description?: string;
  category?: string; decision_type?: string; pricing_type?: string;
  price_paise?: number; creator_split_pct?: number; allowed_clone_modes?: string[];
  factors?: Factor[]; options?: any[]; status?: string; is_public?: boolean;
  install_count?: number;
};

export default function AdminDeciderStore() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
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

  // build-from-solution-store
  const [fromOpen, setFromOpen] = useState(false);
  const [solList, setSolList] = useState<any[]>([]);
  const [selSols, setSelSols] = useState<Record<string, boolean>>({});
  const [fsTitle, setFsTitle] = useState('');

  // classify editor
  const [classifyId, setClassifyId] = useState<string | null>(null);
  const [classFactors, setClassFactors] = useState<Factor[]>([]);

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
    setFModeFull(true); setFModeValues(true); setFAutoPush(false); setParsed(null);
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
  const unpublish = async (t: Template) => {
    try { await api.post(`/decider-store/${t.template_id}/unpublish`); load(); }
    catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
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
          </View>
          {parsed && (
            <TouchableOpacity style={s.parsedPill} onPress={() => setShowCreate(true)}>
              <Ionicons name="checkmark-circle" size={14} color="#16A34A" />
              <Text style={s.parsedText}>Parsed {parsed.factors.length} factors · {parsed.options.length} options — tap to create</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Templates list */}
        {loading ? (
          <ActivityIndicator color="#4F46E5" style={{ marginTop: 24 }} />
        ) : templates.length === 0 ? (
          <Text style={s.empty}>No templates yet. Import one above.</Text>
        ) : templates.map(t => (
          <View key={t.template_id} style={s.tCard}>
            <View style={s.tHead}>
              <Text style={s.tTitle} numberOfLines={2}>{t.title}</Text>
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
              <TouchableOpacity style={[s.act, { backgroundColor: '#EEF2FF' }]} onPress={() => openClassify(t)}>
                <Ionicons name="options" size={13} color="#4F46E5" /><Text style={[s.actText, { color: '#4F46E5' }]}>Classify</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.act, { backgroundColor: '#E0F2FE' }]} onPress={() => pushStores(t)}>
                <Ionicons name="cloud-upload" size={13} color="#0369A1" /><Text style={[s.actText, { color: '#0369A1' }]}>Push to Stores</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[s.act, { backgroundColor: '#F3E8FF' }]} onPress={() => syncStores(t)}>
                <Ionicons name="sync" size={13} color="#9333EA" /><Text style={[s.actText, { color: '#9333EA' }]}>Sync</Text>
              </TouchableOpacity>
              {!(t.status === 'authorized' && t.is_public) ? (
                <TouchableOpacity style={[s.act, { backgroundColor: '#DCFCE7' }]} onPress={() => authorize(t)}>
                  <Ionicons name="rocket" size={13} color="#16A34A" /><Text style={[s.actText, { color: '#16A34A' }]}>Authorize</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity style={[s.act, { backgroundColor: '#FEF9C3' }]} onPress={() => unpublish(t)}>
                  <Ionicons name="eye-off" size={13} color="#A16207" /><Text style={[s.actText, { color: '#A16207' }]}>Unpublish</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity style={[s.act, { backgroundColor: '#FEE2E2' }]} onPress={() => remove(t)}>
                <Ionicons name="trash" size={13} color="#DC2626" /><Text style={[s.actText, { color: '#DC2626' }]}>Delete</Text>
              </TouchableOpacity>
            </View>
          </View>
        ))}
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

      {/* Classify factors modal */}
      <Modal visible={!!classifyId} transparent animationType="slide" onRequestClose={() => setClassifyId(null)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHeader}>
              <Text style={s.mTitle}>Classify factors</Text>
              <TouchableOpacity onPress={() => setClassifyId(null)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            <Text style={s.help}>Set Mandatory/Optional & Priority (1–10) — used when a user picks "Full clone".</Text>
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
                </View>
              ))}
            </ScrollView>
            <TouchableOpacity style={s.createBtn} onPress={saveClassify} disabled={busy}>
              {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.createBtnText}>Save classification</Text>}
            </TouchableOpacity>
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
});
