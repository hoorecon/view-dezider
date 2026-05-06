/**
 * /tools/life-directions-compass  — Set & rank your life freedoms.
 *
 * Drag-to-reorder is approximated with up/down chevrons (no extra deps).
 * Pin-this-week toggles a hard 1.5x weight in Time Dezider for that freedom.
 * Influence slider sets how much LDC weights vs urgency in Time Dezider math.
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

interface Freedom {
  key: string;
  label: string;
  rank: number;
  weight: number;
  icon?: string;
  color?: string;
  custom?: boolean;
  pinned_this_week?: boolean;
  pinned_until?: string;
}

export default function LDCScreen() {
  const router = useRouter();
  const [freedoms, setFreedoms] = useState<Freedom[]>([]);
  const [influence, setInfluence] = useState(30);
  const [reserved, setReserved] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const load = useCallback(async () => {
    try { setLoading(true);
      const r = await api.get('/ldc/me');
      setFreedoms(r.data.compass.freedoms);
      setInfluence(r.data.compass.influence_pct);
      setReserved(r.data.reserved_suggestions || []);
    } catch (e: any) { showAlert('Load failed', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const persist = async (next: Freedom[], inf?: number) => {
    try { setSaving(true);
      const body: any = { freedoms: next.map(f => ({ key: f.key, label: f.label, icon: f.icon, color: f.color, custom: f.custom })) };
      if (inf !== undefined) body.influence_pct = inf;
      const r = await api.put('/ldc/me', body);
      setFreedoms(r.data.compass.freedoms);
      if (inf !== undefined) setInfluence(inf);
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(false); }
  };

  const move = (i: number, dir: -1 | 1) => {
    const j = i + dir;
    if (j < 0 || j >= freedoms.length) return;
    const next = [...freedoms];
    [next[i], next[j]] = [next[j], next[i]];
    persist(next);
  };

  const remove = (key: string) => {
    if (freedoms.length <= 2) return showAlert('Min 2 freedoms', 'Keep at least 2 to compute weights.');
    persist(freedoms.filter(f => f.key !== key));
  };

  const togglePin = async (f: Freedom) => {
    try {
      await api.post('/ldc/me/pin', { key: f.pinned_this_week ? null : f.key });
      load();
    } catch (e: any) { showAlert('Pin failed', e?.response?.data?.detail || e.message); }
  };

  const addReserved = (item: any) => {
    if (freedoms.find(f => f.key === item.key)) return showAlert('Already added', `${item.label} is already in your list.`);
    persist([...freedoms, { ...item, custom: false } as Freedom]);
    setShowAdd(false);
  };

  const addCustom = (label: string) => {
    const slug = label.trim().toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '').slice(0, 40);
    if (!slug) return showAlert('Bad name', 'Use letters/numbers');
    if (freedoms.find(f => f.key === slug)) return showAlert('Duplicate', 'You already have that.');
    persist([...freedoms, { key: slug, label: label.trim(), rank: 99, weight: 1, custom: true, color: '#64748B', icon: 'star' }]);
    setShowAdd(false);
  };

  if (loading) return <SafeAreaView style={s.container}><View style={s.center}><ActivityIndicator color={COLORS.primary} /></View></SafeAreaView>;

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
        <View style={{ flex: 1, marginHorizontal: 12 }}>
          <Text style={s.title}>Life Directions Compass</Text>
          <Text style={s.subtitle}>Your personal north star</Text>
        </View>
        <TouchableOpacity testID="ldc-drift" onPress={() => router.push('/tools/drift-report' as any)}>
          <Ionicons name="analytics" size={20} color={COLORS.primary} />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 80 }}>
        <View style={s.heroCard}>
          <Text style={s.heroLabel}>Time Dezider influence</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 8 }}>
            {[0, 25, 50, 75, 100].map(v => (
              <TouchableOpacity key={v} onPress={() => persist(freedoms, v)} style={[s.infChip, influence === v && s.infChipActive]}>
                <Text style={[s.infChipText, influence === v && s.infChipTextActive]}>{v}%</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={s.helper}>Higher = your compass overrides urgency in allocation. Lower = urgency wins.</Text>
        </View>

        <Text style={s.sectionLabel}>Your freedoms (top → bottom = highest → lowest priority)</Text>
        {freedoms.map((f, i) => (
          <View key={f.key} style={[s.row, f.pinned_this_week && { borderColor: COLORS.primary, borderWidth: 2 }]}>
            <View style={[s.iconCircle, { backgroundColor: (f.color || COLORS.primary) + '22' }]}>
              <Ionicons name={(f.icon as any) || 'star'} size={18} color={f.color || COLORS.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.rowLabel}>{f.label}</Text>
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 2, alignItems: 'center' }}>
                <Text style={s.rankBadge}>#{f.rank}</Text>
                <Text style={s.weightBadge}>w {f.weight}</Text>
                {f.pinned_this_week && <Text style={s.pinnedBadge}>📌 this week ×1.5</Text>}
                {f.custom && <Text style={s.customBadge}>custom</Text>}
              </View>
            </View>
            <View style={{ flexDirection: 'row', gap: 4 }}>
              <TouchableOpacity testID={`ldc-up-${f.key}`} onPress={() => move(i, -1)} disabled={i === 0} style={[s.iconBtn, i === 0 && { opacity: 0.3 }]}>
                <Ionicons name="chevron-up" size={20} color={COLORS.textPrimary} />
              </TouchableOpacity>
              <TouchableOpacity testID={`ldc-down-${f.key}`} onPress={() => move(i, 1)} disabled={i === freedoms.length - 1} style={[s.iconBtn, i === freedoms.length - 1 && { opacity: 0.3 }]}>
                <Ionicons name="chevron-down" size={20} color={COLORS.textPrimary} />
              </TouchableOpacity>
              <TouchableOpacity testID={`ldc-pin-${f.key}`} onPress={() => togglePin(f)} style={s.iconBtn}>
                <Ionicons name={f.pinned_this_week ? 'flag' : 'flag-outline'} size={18} color={f.pinned_this_week ? COLORS.primary : COLORS.textMuted} />
              </TouchableOpacity>
              <TouchableOpacity onPress={() => remove(f.key)} style={s.iconBtn}>
                <Ionicons name="trash-outline" size={18} color="#DC2626" />
              </TouchableOpacity>
            </View>
          </View>
        ))}

        <TouchableOpacity testID="ldc-add" onPress={() => setShowAdd(true)} style={s.addBtn}>
          <Ionicons name="add" size={18} color={COLORS.primary} />
          <Text style={s.addBtnText}>Add a freedom</Text>
        </TouchableOpacity>
        {saving && <Text style={{ textAlign: 'center', color: COLORS.textMuted, fontSize: 11, marginTop: 8 }}>Saving…</Text>}
      </ScrollView>

      <Modal visible={showAdd} transparent animationType="slide" onRequestClose={() => setShowAdd(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={s.overlay}>
          <View style={s.sheet}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={s.sheetTitle}>Add a freedom</Text>
              <TouchableOpacity onPress={() => setShowAdd(false)}><Ionicons name="close" size={24} color={COLORS.textPrimary} /></TouchableOpacity>
            </View>
            <Text style={[s.helper, { marginTop: 4 }]}>Suggestions reserved by us:</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
              {reserved.map((r: any) => (
                <TouchableOpacity key={r.key} onPress={() => addReserved(r)} style={[s.reservedChip, { borderColor: r.color }]}>
                  <Ionicons name={r.icon as any} size={14} color={r.color} />
                  <Text style={[s.reservedChipText, { color: r.color }]}>{r.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={[s.helper, { marginTop: 14 }]}>Or add your own:</Text>
            <CustomAddRow onAdd={addCustom} />
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

function CustomAddRow({ onAdd }: { onAdd: (label: string) => void }) {
  const [v, setV] = useState('');
  return (
    <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
      <TextInput style={[s.input, { flex: 1 }]} value={v} onChangeText={setV} placeholder="Customer Freedom, Network Freedom, …" placeholderTextColor={COLORS.textMuted} />
      <TouchableOpacity onPress={() => { onAdd(v); setV(''); }} style={[s.addBtn, { paddingHorizontal: 14, marginTop: 0 }]}>
        <Text style={s.addBtnText}>Add</Text>
      </TouchableOpacity>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  title: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  heroCard: { backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 },
  heroLabel: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary, textTransform: 'uppercase', letterSpacing: 0.5 },
  helper: { fontSize: 11, color: COLORS.textMuted, marginTop: 6, lineHeight: 16 },
  infChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FAFAFA' },
  infChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  infChipText: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '600' },
  infChipTextActive: { color: '#FFF' },
  sectionLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8, marginTop: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 10, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border, marginBottom: 8 },
  iconCircle: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  rowLabel: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  rankBadge: { fontSize: 10, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, backgroundColor: '#F3F4F6', color: COLORS.textSecondary, fontWeight: '700' },
  weightBadge: { fontSize: 10, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, backgroundColor: '#EEF2FF', color: '#4338CA', fontWeight: '700' },
  pinnedBadge: { fontSize: 10, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, backgroundColor: COLORS.primary + '22', color: COLORS.primary, fontWeight: '700' },
  customBadge: { fontSize: 10, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, backgroundColor: '#FEF3C7', color: '#92400E', fontWeight: '700' },
  iconBtn: { padding: 6 },
  addBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: COLORS.primary, backgroundColor: '#FFF', marginTop: 4 },
  addBtnText: { color: COLORS.primary, fontSize: 13, fontWeight: '700' },
  reservedChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, backgroundColor: '#FFF' },
  reservedChipText: { fontSize: 12, fontWeight: '600' },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '70%' },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
});
