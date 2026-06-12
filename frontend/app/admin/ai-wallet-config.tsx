/**
 * /admin/ai-wallet-config — Super-Admin AI Wallet pricing & Razorpay-Route config.
 *
 * Controls:
 *   • Seed balances + token→credit ratio + confirm threshold
 *   • Gemini blended USD/Mtok rate + USD→INR fallback
 *   • Hidden markup % (user vs admin)
 *   • markup_routed_pct  — what fraction of the markup is transferred via
 *     Razorpay Route to the linked account (rest stays in the primary
 *     "treasury" account to cover the gateway fee + GST).
 *   • Razorpay Route linked-account id
 *   • Minimum custom-credits floor (keeps every order ≥ ₹1)
 *
 * Live worked-example panel: shows the ₹-breakdown for a sample ₹100 LLM cost
 * so the super-admin can SEE whether the primary account will break even or
 * leak money after the Razorpay fee.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TextInput, TouchableOpacity,
  ActivityIndicator, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

const C = {
  bg: '#F8FAFC', card: '#FFFFFF', border: '#E2E8F0', text: '#0F172A',
  muted: '#64748B', primary: '#7C3AED', green: '#059669', red: '#DC2626',
  amber: '#D97706', chipBg: '#F1F5F9',
};

const inr = (v: number | null | undefined) =>
  v === null || v === undefined || Number.isNaN(v as any)
    ? '—'
    : `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })}`;

interface Cfg {
  default_user_credits: number;
  default_admin_credits: number;
  tokens_per_credit: number;
  confirm_threshold_credits: number;
  blended_usd_per_mtok: number;
  usd_to_inr_fallback: number;
  markup_admin_pct: number;
  markup_user_pct: number;
  markup_routed_pct: number;
  razorpay_fee_pct: number;
  razorpay_gst_pct: number;
  route_linked_account_id: string;
  min_custom_credits: number;
  precise_model: string;
  precise_usd_per_mtok: number;
  import_group_threshold: number;
}

const FIELDS: Array<{
  key: keyof Cfg; label: string; hint: string; unit?: string; min?: number; max?: number;
}> = [
  { key: 'markup_user_pct', label: 'Markup % (regular users)', hint: 'Hidden over Gemini cost · default 13% covers RZP fee + ~10% net', unit: '%', min: 0, max: 100 },
  { key: 'markup_admin_pct', label: 'Markup % (admin buyers)', hint: 'Internal staff get cost-only (default 1%)', unit: '%', min: 0, max: 100 },
  { key: 'markup_routed_pct', label: 'Markup % routed to linked account', hint: '% of the markup transferred via Razorpay Route. The rest stays in primary to cover the gateway fee+GST. Default 77 → ≈10% routed, ≈3% retained on a 13% markup.', unit: '%', min: 0, max: 100 },
  { key: 'razorpay_fee_pct', label: 'Razorpay fee %', hint: 'Standard INR domestic-card rate (default 2.0%). Update if RZP renegotiates your gateway pricing.', unit: '%', min: 0, max: 100 },
  { key: 'razorpay_gst_pct', label: 'GST % on Razorpay fee', hint: 'GST charged ON the gateway fee (default 18%). Effective deduction = fee × (1 + gst/100).', unit: '%', min: 0, max: 100 },
  { key: 'route_linked_account_id', label: 'Razorpay linked account id', hint: 'e.g. acc_xxxxxxxxxxxxxx · leave blank to disable Route' },
  { key: 'min_custom_credits', label: 'Min custom credits per refill', hint: 'Floor for "Custom amount" — keeps every order ≥ ₹1', min: 1 },
  { key: 'tokens_per_credit', label: 'Tokens per credit', hint: 'Lower = each credit covers fewer tokens → more revenue per credit', min: 1 },
  { key: 'confirm_threshold_credits', label: 'Confirm threshold (credits)', hint: 'Above this estimated cost, the UI asks the user to confirm before spending', min: 0 },
  { key: 'blended_usd_per_mtok', label: 'Gemini blended $/Mtok', hint: 'Single blended price ($) per 1M tokens — set from Gemini list price', unit: '$', min: 0.01 },
  { key: 'precise_usd_per_mtok', label: 'Precise-AI blended $/Mtok', hint: '“Costly & Precise AI” tier (Claude via Emergent universal key). Credit multiplier = this ÷ Gemini $/Mtok — same markup math stays zero-loss.', unit: '$', min: 0.01 },
  { key: 'precise_model', label: 'Precise-AI model', hint: 'Claude model used by the “Costly & Precise AI” import tier (e.g. claude-sonnet-4-6)' },
  { key: 'import_group_threshold', label: 'AI grouping threshold (factors)', hint: 'Import-from-URL: AI may auto-group ungrouped factors into categories only when the page defines no grouping AND the factor count exceeds this (default 15). Page-defined groups are never modified.', min: 2 },
  { key: 'usd_to_inr_fallback', label: 'USD → INR fallback', hint: 'Used when live FX fetch fails', unit: '₹', min: 1 },
  { key: 'default_user_credits', label: 'New-user seed credits', hint: 'Free starting balance for non-admin signups', min: 0 },
  { key: 'default_admin_credits', label: 'New-admin seed credits', hint: 'Free starting balance for admin signups', min: 0 },
];

export default function AdminAIWalletConfigScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isWide = width >= 1000;

  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/ai-wallet/config');
      setCfg(res.data);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load AI wallet config');
    } finally { setLoading(false); }
  };

  const onChange = (k: keyof Cfg, v: string) => {
    if (!cfg) return;
    if (k === 'route_linked_account_id' || k === 'precise_model') {
      setCfg({ ...cfg, [k]: v } as Cfg);
    } else {
      const num = v === '' ? 0 : parseFloat(v);
      setCfg({ ...cfg, [k]: Number.isNaN(num) ? 0 : num } as Cfg);
    }
  };

  const save = async () => {
    if (!cfg) return;
    setSaving(true);
    try {
      const res = await api.put('/admin/ai-wallet/config', cfg);
      setCfg(res.data);
      showAlert('Saved', 'AI Wallet config updated.');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  // ── Live worked example: ₹100 actual LLM cost ──
  const example = useMemo(() => {
    if (!cfg) return null;
    const cost = 100; // ₹100 LLM cost (sample)
    const markupPct = cfg.markup_user_pct || 0;
    const routedPct = cfg.markup_routed_pct || 0;
    const feePct = cfg.razorpay_fee_pct || 0;
    const gstPct = cfg.razorpay_gst_pct || 0;
    const charged = cost * (1 + markupPct / 100);
    const markup = charged - cost;
    const routed = markup * (routedPct / 100);
    const retainedFromMarkup = markup - routed;
    // RZP fee rate including GST on the fee itself.
    // Effective = fee% × (1 + gst%/100). Default = 2 × 1.18 = 2.36%
    const rzpFeeRate = (feePct / 100) * (1 + gstPct / 100);
    const rzpFee = charged * rzpFeeRate;
    const primaryNet = charged - routed - rzpFee;
    const surplus = primaryNet - cost;
    return {
      cost, charged, markup, routed, retainedFromMarkup, rzpFee, primaryNet, surplus,
      rzpFeeRatePct: rzpFeeRate * 100,
    };
  }, [cfg]);

  if (loading || !cfg) {
    return (
      <SafeAreaView style={[s.root, { alignItems: 'center', justifyContent: 'center' }]}>
        <ActivityIndicator color={C.primary} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.root} testID="admin-ai-wallet-config-screen">
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator>
        {/* Header */}
        <View style={s.headerRow}>
          <TouchableOpacity onPress={() => router.back()} style={s.backBtn} testID="awc-back">
            <Ionicons name="chevron-back" size={18} color={C.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.h1} testID="awc-title">AI Wallet — Pricing & Route Config</Text>
            <Text style={s.sub}>
              Tune markup, Route split, FX, seeds. Changes apply to NEW orders only — past orders keep their original breakdown.
            </Text>
          </View>
          <TouchableOpacity
            style={[s.saveBtn, saving && { opacity: 0.6 }]}
            onPress={save}
            disabled={saving}
            testID="awc-save-btn"
          >
            {saving ? <ActivityIndicator size="small" color="#fff" />
              : <Ionicons name="save" size={15} color="#fff" />}
            <Text style={s.saveBtnTxt}>{saving ? 'Saving…' : 'Save changes'}</Text>
          </TouchableOpacity>
        </View>

        {/* Live worked example */}
        {example && (
          <View style={[s.example, { borderColor: example.surplus < 0 ? C.red : C.green }]} testID="awc-example">
            <View style={s.exampleHead}>
              <Ionicons name="calculator" size={16} color={example.surplus < 0 ? C.red : C.green} />
              <Text style={[s.exampleTitle, { color: example.surplus < 0 ? C.red : C.green }]}>
                Worked example — on a ₹100 actual Gemini cost
              </Text>
            </View>
            <View style={[s.exGrid, !isWide && { flexDirection: 'column' }]}>
              <ExRow label="Cost to Google (Gemini)" value={inr(example.cost)} />
              <ExRow label={`+ Markup (${cfg.markup_user_pct}%)`} value={inr(example.markup)} />
              <ExRow label="= Charged to user" value={inr(example.charged)} bold />
              <ExRow label={`− Routed to linked a/c (${cfg.markup_routed_pct}% of markup)`} value={`− ${inr(example.routed)}`} muted />
              <ExRow label={`− Razorpay fee (${example.rzpFeeRatePct.toFixed(2)}% incl. GST)`} value={`− ${inr(example.rzpFee)}`} muted />
              <ExRow label="= Primary (treasury) net" value={inr(example.primaryNet)} bold />
              <ExRow
                label="Surplus vs Gemini cost"
                value={inr(example.surplus)}
                color={example.surplus < 0 ? C.red : C.green}
                bold
              />
              <ExRow
                label={`Precise tier (${cfg.precise_model || 'Claude'}) credit multiplier`}
                value={`× ${(Math.max(1, (cfg.precise_usd_per_mtok || 0) / Math.max(0.01, cfg.blended_usd_per_mtok || 0.01))).toFixed(2)}`}
                muted
              />
            </View>
            {example.surplus < 0 ? (
              <Text style={[s.exHint, { color: C.red }]}>
                {`⚠ Primary account loses ${inr(-example.surplus)} on every ₹100 of LLM cost. Reduce “Markup routed %” or increase “Markup %”.`}
              </Text>
            ) : (
              <Text style={[s.exHint, { color: C.green }]}>
                ✓ Primary covers Gemini cost with {inr(example.surplus)} buffer. Zero-loss guaranteed.
              </Text>
            )}
          </View>
        )}

        {/* Fields */}
        <View style={s.fieldsGrid}>
          {FIELDS.map((f) => (
            <View key={f.key} style={[s.fieldCard, { width: isWide ? '48%' : '100%' }]} testID={`awc-field-${f.key}`}>
              <Text style={s.fieldLabel}>{f.label}</Text>
              <View style={s.inputWrap}>
                {f.unit && <Text style={s.unit}>{f.unit}</Text>}
                <TextInput
                  style={s.input}
                  value={String((cfg as any)[f.key] ?? '')}
                  onChangeText={(t) => onChange(f.key, t)}
                  keyboardType={f.key === 'route_linked_account_id' || f.key === 'precise_model' ? 'default' : 'decimal-pad'}
                  placeholder={f.key === 'route_linked_account_id' ? 'acc_xxxxxxxxxxxxxx' : f.key === 'precise_model' ? 'claude-sonnet-4-6' : '0'}
                  placeholderTextColor={C.muted}
                  testID={`awc-input-${f.key}`}
                />
              </View>
              <Text style={s.fieldHint}>{f.hint}</Text>
            </View>
          ))}
        </View>

        {/* Footer */}
        <View style={s.footerNote}>
          <Ionicons name="information-circle" size={14} color={C.muted} />
          <Text style={s.footerTxt}>
            Past orders keep their original breakdown — only orders created AFTER you save reflect new values.
            Recon dashboard uses the actual synced Razorpay transfer amount, so the routed totals there are always real.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const ExRow = ({ label, value, bold, muted, color }: any) => (
  <View style={s.exRow}>
    <Text style={[s.exLabel, muted && { color: C.muted }]}>{label}</Text>
    <Text style={[s.exVal, bold && { fontWeight: '800' }, color && { color }, muted && { color: C.muted }]}>
      {value}
    </Text>
  </View>
);

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  scroll: { padding: 20, paddingBottom: 60 },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 12 },
  backBtn: { padding: 6, borderRadius: 8, backgroundColor: C.card, borderWidth: 1, borderColor: C.border },
  h1: { fontSize: 22, fontWeight: '800', color: C.text },
  sub: { fontSize: 13, color: C.muted, marginTop: 2 },
  saveBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: C.primary,
    paddingHorizontal: 14, paddingVertical: 9, borderRadius: 8,
  },
  saveBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 13 },

  example: {
    backgroundColor: C.card, borderRadius: 12, borderWidth: 2, padding: 16, marginBottom: 16,
  },
  exampleHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  exampleTitle: { fontSize: 14, fontWeight: '700' },
  exGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  exRow: {
    width: '100%', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  exLabel: { fontSize: 13, color: C.text, flex: 1 },
  exVal: { fontSize: 13, color: C.text, fontVariant: ['tabular-nums'], textAlign: 'right' },
  exHint: { fontSize: 12, marginTop: 10, fontWeight: '600' },

  fieldsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  fieldCard: {
    backgroundColor: C.card, borderRadius: 10, borderWidth: 1, borderColor: C.border, padding: 14,
  },
  fieldLabel: { fontSize: 13, fontWeight: '700', color: C.text, marginBottom: 8 },
  inputWrap: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: C.chipBg,
    borderRadius: 8, paddingHorizontal: 10,
  },
  unit: { fontSize: 13, color: C.muted, marginRight: 6, fontWeight: '700' },
  input: {
    flex: 1, paddingVertical: 9, fontSize: 14, color: C.text, fontVariant: ['tabular-nums'],
  },
  fieldHint: { fontSize: 11, color: C.muted, marginTop: 6, lineHeight: 16 },

  footerNote: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginTop: 16,
    paddingHorizontal: 4,
  },
  footerTxt: { flex: 1, fontSize: 11, color: C.muted, lineHeight: 16 },
});
