/**
 * /admin/sku-pricing — Admin UI to configure the 4 on-demand SKU prices.
 *
 * Each SKU's price/name/tagline/quota/active flag is editable.
 * Defaults are the original ₹199/₹999/₹1,999/₹2,800 — never hardcoded on
 * the frontend; sourced from /api/store/skus.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TextInput, TouchableOpacity, Switch, ActivityIndicator, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { showAlert, confirmDialog } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';

interface Sku { code: string; name: string; tagline: string; description: string; price_paise: number; quota: number; active: boolean; display_order: number; badge_color: string; kind: string; }

function formatINR(p: number) {
  const rupees = p / 100;
  const fixed = rupees.toFixed(p % 100 === 0 ? 0 : 2);
  const [intPart, decPart] = fixed.split('.');
  const lastThree = intPart.slice(-3);
  const rest = intPart.slice(0, -3);
  const formatted = rest ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + lastThree : lastThree;
  return '₹' + formatted + (decPart ? '.' + decPart : '');
}

export default function AdminSkuPricing() {
  const [skus, setSkus] = useState<Sku[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingCode, setSavingCode] = useState<string | null>(null);
  const [dirty, setDirty] = useState<Record<string, Partial<Sku>>>({});

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get('/store/skus', { params: { active_only: false } });
      setSkus(r.data.skus || []);
      setDirty({});
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Could not fetch SKUs');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const patch = (code: string, field: keyof Sku, value: any) => {
    setDirty(d => ({ ...d, [code]: { ...d[code], [field]: value } }));
  };

  const save = useCallback(async (sku: Sku) => {
    const changes = dirty[sku.code];
    if (!changes || Object.keys(changes).length === 0) return;
    setSavingCode(sku.code);
    try {
      await api.put(`/store/admin/skus/${sku.code}`, changes);
      showAlert('Saved', `${sku.code} updated.`);
      await load();
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Error');
    } finally { setSavingCode(null); }
  }, [dirty, load]);

  const resetDefaults = useCallback(async () => {
    const ok = await confirmDialog('Reset SKU prices?', 'This restores the shipping defaults for all 4 SKUs. Existing user balances are untouched.', { confirmText: 'Reset', destructive: true });
    if (!ok) return;
    try {
      await api.post('/store/admin/skus/reset-defaults');
      showAlert('Reset complete', 'All SKUs restored to defaults.');
      await load();
    } catch (e: any) {
      showAlert('Reset failed', e?.response?.data?.detail || 'Error');
    }
  }, [load]);

  const seedInHouse = useCallback(async () => {
    try {
      const r = await api.post('/store/admin/seed-in-house-solutions');
      showAlert('Seeded', `${(r.data?.in_house_solutions || []).length} in-house solutions present in the Store.`);
    } catch (e: any) {
      showAlert('Seed failed', e?.response?.data?.detail || 'Error');
    }
  }, []);

  if (loading) return <View style={s.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>;

  return (
    <ScrollView contentContainerStyle={s.body}>
      <View style={s.topRow}>
        <View style={{ flex: 1 }}>
          <Text style={s.h1}>On-Demand SKU Pricing</Text>
          <Text style={s.sub}>Set prices, names, and quotas for the 4 pay-as-you-go packs. Defaults: ₹199 · ₹999 · ₹1,999 · ₹2,800.</Text>
        </View>
        <TouchableOpacity style={s.resetBtn} onPress={resetDefaults}>
          <Ionicons name="refresh" size={16} color="#DC2626" />
          <Text style={s.resetText}>Reset defaults</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={s.seedBtn} onPress={seedInHouse}>
        <Ionicons name="add-circle" size={18} color="#7C3AED" />
        <Text style={s.seedText}>Seed 3 in-house solutions into Solutions Store (org_id=0)</Text>
      </TouchableOpacity>

      {skus.map(sku => {
        const ch = dirty[sku.code] || {};
        const isDirty = Object.keys(ch).length > 0;
        const effective = { ...sku, ...ch };
        return (
          <View key={sku.code} style={s.card}>
            <View style={s.cardHead}>
              <View style={[s.layerChip, { backgroundColor: (sku.badge_color || '#7C3AED') + '22' }]}>
                <Text style={[s.layerText, { color: sku.badge_color || '#7C3AED' }]}>{sku.code}</Text>
              </View>
              <Text style={s.kind}>{sku.kind.toUpperCase()}</Text>
              <View style={{ flex: 1 }} />
              <View style={s.activeWrap}>
                <Text style={s.label}>Active</Text>
                <Switch value={effective.active} onValueChange={v => patch(sku.code, 'active', v)} />
              </View>
            </View>

            <Field label="Name" value={String(effective.name ?? '')} onChange={v => patch(sku.code, 'name', v)} />
            <Field label="Tagline" value={String(effective.tagline ?? '')} onChange={v => patch(sku.code, 'tagline', v)} />
            <Field label="Description" value={String(effective.description ?? '')} onChange={v => patch(sku.code, 'description', v)} multiline />

            <View style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Price (₹, excl. GST)</Text>
                <TextInput
                  value={String((effective.price_paise ?? 0) / 100)}
                  onChangeText={t => {
                    const num = parseFloat(t.replace(/[^0-9.]/g, '')) || 0;
                    patch(sku.code, 'price_paise', Math.round(num * 100));
                  }}
                  keyboardType="numeric"
                  style={s.input}
                />
                <Text style={s.hint}>{formatINR(effective.price_paise ?? 0)} → {Math.round((effective.price_paise ?? 0) * 1.18) / 100} incl. 18% GST</Text>
              </View>
              <View style={{ width: 14 }} />
              <View style={{ width: 110 }}>
                <Text style={s.label}>Quota</Text>
                <TextInput
                  value={String(effective.quota ?? 1)}
                  onChangeText={t => patch(sku.code, 'quota', Math.max(1, parseInt(t.replace(/[^0-9]/g, ''), 10) || 1))}
                  keyboardType="numeric"
                  style={s.input}
                />
              </View>
            </View>

            <View style={s.saveRow}>
              {isDirty && <Text style={s.dirtyDot}>● Unsaved</Text>}
              <View style={{ flex: 1 }} />
              <TouchableOpacity
                style={[s.saveBtn, !isDirty && s.saveBtnDisabled]}
                disabled={!isDirty || savingCode === sku.code}
                onPress={() => save(sku)}
              >
                {savingCode === sku.code
                  ? <ActivityIndicator size="small" color="#FFF" />
                  : <Text style={s.saveText}>Save {sku.code}</Text>}
              </TouchableOpacity>
            </View>
          </View>
        );
      })}
    </ScrollView>
  );
}

function Field({ label, value, onChange, multiline = false }: { label: string; value: string; onChange: (v: string) => void; multiline?: boolean }) {
  return (
    <View style={{ marginTop: 10 }}>
      <Text style={s.label}>{label}</Text>
      <TextInput value={value} onChangeText={onChange} style={[s.input, multiline && { minHeight: 70, paddingTop: 10, textAlignVertical: 'top' }]} multiline={multiline} />
    </View>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 },
  body: { padding: 18, gap: 14, paddingBottom: 60 },
  topRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  h1: { fontSize: 22, fontWeight: '800', color: '#0F172A' },
  sub: { fontSize: 13, color: '#64748B', marginTop: 4, lineHeight: 18 },
  resetBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: '#FECACA', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  resetText: { color: '#DC2626', fontWeight: '700', fontSize: 12 },
  seedBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderColor: '#DDD6FE', backgroundColor: '#F5F3FF', paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10 },
  seedText: { color: '#7C3AED', fontWeight: '600', fontSize: 13 },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#E5E7EB' },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  layerChip: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  layerText: { fontWeight: '800', fontSize: 12, letterSpacing: 0.5 },
  kind: { color: '#94A3B8', fontSize: 11, fontWeight: '700', letterSpacing: 0.6 },
  activeWrap: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  label: { fontSize: 11, color: '#475569', fontWeight: '700', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 },
  hint: { fontSize: 11, color: '#94A3B8', marginTop: 4 },
  input: { borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, paddingHorizontal: 12, paddingVertical: Platform.OS === 'web' ? 10 : 8, fontSize: 14, backgroundColor: '#F8FAFC', color: '#0F172A' },
  row: { flexDirection: 'row', alignItems: 'flex-start', marginTop: 10 },
  saveRow: { flexDirection: 'row', alignItems: 'center', marginTop: 14, gap: 10 },
  dirtyDot: { color: '#F59E0B', fontWeight: '700', fontSize: 12 },
  saveBtn: { backgroundColor: '#7C3AED', paddingHorizontal: 18, paddingVertical: 10, borderRadius: 10 },
  saveBtnDisabled: { backgroundColor: '#CBD5E1' },
  saveText: { color: '#FFF', fontWeight: '700', fontSize: 13 },
});
