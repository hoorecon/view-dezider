/**
 * /tools/aala  — Accrued Assets & Liabilities Analysis grid (5×3).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, Modal, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';
import { showAlert } from '../../src/utils/alert';

const TEPFI = ['time', 'energy', 'people', 'finance', 'infrastructure'];
const LEVELS = ['self', 'micro', 'macro'];
const FACTOR_ICONS: any = { time: 'time', energy: 'flash', people: 'people', finance: 'cash', infrastructure: 'business' };

export default function AALAScreen() {
  const router = useRouter();
  const [cells, setCells] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [picked, setPicked] = useState<any | null>(null);

  const load = useCallback(async () => {
    try { setLoading(true);
      const r = await api.get('/aala/me');
      setCells(r.data.aala.cells);
    } catch (e: any) { showAlert('Load failed', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const cellAt = (factor: string, level: string) => cells.find(c => c.factor === factor && c.level === level) || { factor, level, balance_score: 0, assets: [], liabilities: [], assets_summary: '', liabilities_summary: '' };

  const colorForBalance = (s: number) => s >= 5 ? '#10B981' : s >= 0 ? '#F59E0B' : '#DC2626';

  if (loading) return <SafeAreaView style={s.container}><View style={s.center}><ActivityIndicator color={COLORS.primary} /></View></SafeAreaView>;

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
        <View style={{ flex: 1, marginHorizontal: 12 }}>
          <Text style={s.title}>AALA · Resource Ledger</Text>
          <Text style={s.subtitle}>TEPFI × Self/Micro/Macro — Accrued Assets & Liabilities</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
        <Text style={s.helper}>Tap any cell to log assets, liabilities, and current balance score (-10 … +10). Time Dezider uses these to know which TEPFI/level resources have spare capacity.</Text>

        <SpawnSolutionRow />

        {/* Header row */}
        <View style={s.gridHeader}>
          <Text style={[s.colHead, { flex: 1.4 }]}>Factor</Text>
          {LEVELS.map(l => <Text key={l} style={[s.colHead, { flex: 1 }]}>{l}</Text>)}
        </View>

        {/* 5 rows of TEPFI × 3 cells */}
        {TEPFI.map(factor => (
          <View key={factor} style={s.gridRow}>
            <View style={[s.factorCell, { flex: 1.4 }]}>
              <Ionicons name={FACTOR_ICONS[factor] as any} size={16} color={COLORS.primary} />
              <Text style={s.factorText}>{factor.charAt(0).toUpperCase() + factor.slice(1)}</Text>
            </View>
            {LEVELS.map(level => {
              const cell = cellAt(factor, level);
              return (
                <TouchableOpacity
                  key={level}
                  testID={`aala-cell-${factor}-${level}`}
                  style={[s.cell, { flex: 1, backgroundColor: colorForBalance(cell.balance_score) + '15', borderColor: colorForBalance(cell.balance_score) }]}
                  onPress={() => setPicked(cell)}
                >
                  <Text style={[s.cellScore, { color: colorForBalance(cell.balance_score) }]}>{cell.balance_score >= 0 ? '+' : ''}{cell.balance_score.toFixed(1)}</Text>
                  <Text style={s.cellMeta}>{cell.assets?.length || 0}▲ / {cell.liabilities?.length || 0}▼</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        ))}
      </ScrollView>

      {picked && <CellSheet cell={picked} onClose={() => { setPicked(null); load(); }} />}
    </SafeAreaView>
  );
}

function SpawnSolutionRow() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!title.trim()) return showAlert('Required', 'Problem title is required');
    try { setBusy(true);
      const r = await api.post('/aala/me/spawn-solution-matrix', {
        problem_title: title, problem_description: desc, area_of_life: 'general',
      });
      setOpen(false); setTitle(''); setDesc('');
      showAlert('Created', 'Solution Matrix spawned from your AALA snapshot.');
      router.push(`/tools/solution-matrix?entry_id=${r.data.entry_id}` as any);
    } catch (e: any) { showAlert('Spawn failed', e?.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  return (
    <>
      <TouchableOpacity testID="aala-spawn-sm" onPress={() => setOpen(true)} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 12, borderRadius: 10, backgroundColor: '#7C3AED', marginBottom: 12 }}>
        <Ionicons name="construct" size={16} color="#FFF" />
        <Text style={{ color: '#FFF', fontSize: 13, fontWeight: '700' }}>Spawn Solution Matrix from this AALA snapshot</Text>
      </TouchableOpacity>
      {open && (
        <Modal visible transparent animationType="slide" onRequestClose={() => setOpen(false)}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' }}>
            <View style={{ backgroundColor: '#FFF', borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18 }}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <Text style={{ fontSize: 16, fontWeight: '700', color: COLORS.textPrimary }}>Spawn Solution Matrix</Text>
                <TouchableOpacity onPress={() => setOpen(false)}><Ionicons name="close" size={24} color={COLORS.textPrimary} /></TouchableOpacity>
              </View>
              <Text style={{ fontSize: 12, color: COLORS.textMuted, marginBottom: 8 }}>
                Your current AALA cells (TEPFI × Self/Micro/Macro) will be copied into a new Solution Matrix as a problem-scoped snapshot. Edit the matrix afterwards to refine for the specific problem.
              </Text>
              <Text style={{ fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 6 }}>Problem title *</Text>
              <TextInput style={{ borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, marginTop: 4 }} value={title} onChangeText={setTitle} placeholder="e.g. How to triple revenue while keeping health" placeholderTextColor={COLORS.textMuted} />
              <Text style={{ fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10 }}>Description</Text>
              <TextInput style={{ borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, marginTop: 4, minHeight: 70 }} multiline value={desc} onChangeText={setDesc} placeholder="Context, constraints, what 'solved' looks like…" placeholderTextColor={COLORS.textMuted} />
              <TouchableOpacity testID="aala-spawn-submit" onPress={submit} disabled={busy} style={{ backgroundColor: '#7C3AED', paddingVertical: 12, borderRadius: 8, alignItems: 'center', marginTop: 14, opacity: busy ? 0.6 : 1 }}>
                {busy ? <ActivityIndicator color="#FFF" /> : <Text style={{ color: '#FFF', fontSize: 14, fontWeight: '700' }}>Spawn & open</Text>}
              </TouchableOpacity>
            </View>
          </KeyboardAvoidingView>
        </Modal>
      )}
    </>
  );
}


function CellSheet({ cell, onClose }: { cell: any; onClose: () => void }) {
  const [score, setScore] = useState(String(cell.balance_score ?? 0));  const [aSum, setASum] = useState(cell.assets_summary || '');
  const [lSum, setLSum] = useState(cell.liabilities_summary || '');
  const [newAsset, setNewAsset] = useState('');
  const [newLiab, setNewLiab] = useState('');
  const [items, setItems] = useState({ assets: cell.assets || [], liabilities: cell.liabilities || [] });
  const [busy, setBusy] = useState(false);

  const save = async () => {
    try { setBusy(true);
      await api.put(`/aala/me/cell/${cell.factor}/${cell.level}`, {
        assets_summary: aSum, liabilities_summary: lSum,
        balance_score: Math.max(-10, Math.min(10, parseFloat(score) || 0)),
      });
      onClose();
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  const addA = async () => {
    if (!newAsset.trim()) return;
    try {
      const r = await api.post(`/aala/me/cell/${cell.factor}/${cell.level}/asset`, { label: newAsset });
      setItems(p => ({ ...p, assets: [...p.assets, r.data.asset] }));
      setNewAsset('');
    } catch (e: any) { showAlert('Add failed', e?.response?.data?.detail || e.message); }
  };
  const addL = async () => {
    if (!newLiab.trim()) return;
    try {
      const r = await api.post(`/aala/me/cell/${cell.factor}/${cell.level}/liability`, { label: newLiab });
      setItems(p => ({ ...p, liabilities: [...p.liabilities, r.data.liability] }));
      setNewLiab('');
    } catch (e: any) { showAlert('Add failed', e?.response?.data?.detail || e.message); }
  };
  const delA = async (id: string) => {
    await api.delete(`/aala/me/cell/${cell.factor}/${cell.level}/asset/${id}`);
    setItems(p => ({ ...p, assets: p.assets.filter((a: any) => a.item_id !== id) }));
  };
  const delL = async (id: string) => {
    await api.delete(`/aala/me/cell/${cell.factor}/${cell.level}/liability/${id}`);
    setItems(p => ({ ...p, liabilities: p.liabilities.filter((l: any) => l.item_id !== id) }));
  };

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={s.overlay}>
        <View style={s.sheet}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={s.sheetTitle}>{cell.factor.toUpperCase()} × {cell.level.toUpperCase()}</Text>
            <TouchableOpacity onPress={onClose}><Ionicons name="close" size={24} color={COLORS.textPrimary} /></TouchableOpacity>
          </View>

          <ScrollView style={{ maxHeight: 460 }}>
            <Text style={s.fieldLabel}>Net balance score (-10 … +10)</Text>
            <TextInput style={s.input} keyboardType="numeric" value={score} onChangeText={setScore} />

            <Text style={s.fieldLabel}>Assets summary</Text>
            <TextInput style={[s.input, { minHeight: 50 }]} multiline value={aSum} onChangeText={setASum} placeholder="Short note about your accrued assets…" placeholderTextColor={COLORS.textMuted} />

            <Text style={s.fieldLabel}>Liabilities summary</Text>
            <TextInput style={[s.input, { minHeight: 50 }]} multiline value={lSum} onChangeText={setLSum} placeholder="Short note about your accrued liabilities…" placeholderTextColor={COLORS.textMuted} />

            <Text style={s.fieldLabel}>Asset items ▲</Text>
            {items.assets.map((a: any) => (
              <View key={a.item_id} style={s.itemRow}>
                <Text style={{ flex: 1, fontSize: 13, color: COLORS.textPrimary }}>{a.label} {a.value ? `(${a.value} ${a.units || ''})` : ''}</Text>
                <TouchableOpacity onPress={() => delA(a.item_id)}><Ionicons name="close-circle" size={18} color="#DC2626" /></TouchableOpacity>
              </View>
            ))}
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
              <TextInput style={[s.input, { flex: 1 }]} value={newAsset} onChangeText={setNewAsset} placeholder="Add asset…" placeholderTextColor={COLORS.textMuted} />
              <TouchableOpacity onPress={addA} style={s.smallBtn}><Text style={s.smallBtnText}>+</Text></TouchableOpacity>
            </View>

            <Text style={s.fieldLabel}>Liability items ▼</Text>
            {items.liabilities.map((l: any) => (
              <View key={l.item_id} style={s.itemRow}>
                <Text style={{ flex: 1, fontSize: 13, color: COLORS.textPrimary }}>{l.label} {l.value ? `(${l.value} ${l.units || ''})` : ''}</Text>
                <TouchableOpacity onPress={() => delL(l.item_id)}><Ionicons name="close-circle" size={18} color="#DC2626" /></TouchableOpacity>
              </View>
            ))}
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
              <TextInput style={[s.input, { flex: 1 }]} value={newLiab} onChangeText={setNewLiab} placeholder="Add liability…" placeholderTextColor={COLORS.textMuted} />
              <TouchableOpacity onPress={addL} style={s.smallBtn}><Text style={s.smallBtnText}>+</Text></TouchableOpacity>
            </View>
          </ScrollView>

          <TouchableOpacity testID="aala-save-cell" onPress={save} disabled={busy} style={[s.primary, { marginTop: 12, opacity: busy ? 0.6 : 1 }]}>
            {busy ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryText}>Save cell</Text>}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  title: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  helper: { fontSize: 11, color: COLORS.textMuted, marginBottom: 10, lineHeight: 16 },
  gridHeader: { flexDirection: 'row', paddingHorizontal: 4, paddingBottom: 4 },
  colHead: { fontSize: 10, fontWeight: '700', color: COLORS.textMuted, textTransform: 'uppercase', textAlign: 'center', letterSpacing: 0.5 },
  gridRow: { flexDirection: 'row', gap: 4, marginBottom: 6 },
  factorCell: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 8, backgroundColor: COLORS.white, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border },
  factorText: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary, textTransform: 'capitalize' },
  cell: { padding: 10, borderRadius: 8, borderWidth: 1, alignItems: 'center', justifyContent: 'center', minHeight: 56 },
  cellScore: { fontSize: 16, fontWeight: '800' },
  cellMeta: { fontSize: 9, color: COLORS.textSecondary, marginTop: 2 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },
  itemRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  smallBtn: { backgroundColor: COLORS.primary, width: 40, alignItems: 'center', justifyContent: 'center', borderRadius: 8, marginTop: 4 },
  smallBtnText: { color: '#FFF', fontSize: 18, fontWeight: '700' },
  primary: { backgroundColor: COLORS.primary, paddingVertical: 12, borderRadius: 8, alignItems: 'center' },
  primaryText: { color: '#FFF', fontSize: 14, fontWeight: '700' },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '92%' },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
});
