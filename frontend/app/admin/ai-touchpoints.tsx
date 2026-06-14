/**
 * /admin/ai-touchpoints — static catalog of every AI-metered touchpoint
 * across the user app, with: avg credits, USD cost, and spending mode.
 *
 * Five spending modes (Wave-5 per user spec):
 *   1. user_buy         — user wallet, user-paid (post-paid via credit balance)
 *   2. org_buy_prepaid  — partner org pool, prepaid pack draws down
 *   3. org_buy_postpaid — partner org pool, invoiced at month-end
 *   4. org_sponsor_free — admin policy 'always' free-tier; user not prompted
 *   5. user_optin_free  — per-run choice (Skip top-up button in Deep Import)
 *
 * Static for now — easier to keep accurate than auto-discovery from ledger.
 */
import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

type Mode = 'user_buy' | 'org_buy_prepaid' | 'org_buy_postpaid' | 'org_sponsor_free' | 'user_optin_free';

const MODE_META: Record<Mode, { label: string; color: string; bg: string }> = {
  user_buy:         { label: 'User buy',          color: '#1F2937', bg: '#F3F4F6' },
  org_buy_prepaid:  { label: 'Org buy · Prepaid', color: '#1E40AF', bg: '#DBEAFE' },
  org_buy_postpaid: { label: 'Org buy · Postpaid', color: '#5B21B6', bg: '#EDE9FE' },
  org_sponsor_free: { label: 'Org sponsor (silent free-tier)', color: '#065F46', bg: '#D1FAE5' },
  user_optin_free:  { label: 'User opt-in (per-run free-tier)', color: '#9A3412', bg: '#FFEDD5' },
};

interface Row { name: string; avg: number; usd: string; mode: Mode; }

const ROWS: Row[] = [
  // Step 2 — Import URL flows
  { name: 'Step 2 · Import URL (Fast)',          avg: 22,  usd: '~$0.005', mode: 'user_optin_free' },
  { name: 'Step 2 · Import URL (Precise)',       avg: 100, usd: '~$0.022', mode: 'user_optin_free' },
  { name: 'Step 2 · Deep Import (5 pages)',      avg: 250, usd: '~$0.055', mode: 'user_optin_free' },
  { name: 'Step 2 · Deep Import (10 pages)',     avg: 450, usd: '~$0.099', mode: 'user_optin_free' },
  // Step 4–7 — AI inside decisions
  { name: 'Step 4 · Prompt Auto-Tune',           avg: 18,  usd: '~$0.004', mode: 'user_buy' },
  { name: 'Step 5 · AI factor suggestions',      avg: 25,  usd: '~$0.005', mode: 'user_buy' },
  { name: 'Step 7 · AI Assist (per cell)',       avg: 6,   usd: '~$0.001', mode: 'user_buy' },
  { name: 'Step 7 · AI Assess All',              avg: 75,  usd: '~$0.016', mode: 'user_buy' },
  { name: 'Step 9 · MPPS plan',                  avg: 60,  usd: '~$0.013', mode: 'user_buy' },
  // Emotional Gatekeeper
  { name: 'AIM · Analyze & Insights',            avg: 35,  usd: '~$0.008', mode: 'org_sponsor_free' },
  { name: 'AIM · Breakthrough Report',           avg: 20,  usd: '~$0.004', mode: 'org_sponsor_free' },
  { name: 'Outlet · Pattern analysis',           avg: 30,  usd: '~$0.007', mode: 'org_sponsor_free' },
  { name: 'Outlet · Breakthrough Report',        avg: 20,  usd: '~$0.004', mode: 'org_sponsor_free' },
  // Pros & Cons + Solution Finder
  { name: 'Pros & Cons Wizard · AI',             avg: 28,  usd: '~$0.006', mode: 'user_buy' },
  { name: 'Solution Finder · AI ideas',          avg: 30,  usd: '~$0.007', mode: 'user_buy' },
  // Partner / Embed Console — billed to partner org
  { name: 'Embed · Pros & Cons (partner)',       avg: 28,  usd: '~$0.006', mode: 'org_buy_prepaid' },
  { name: 'Embed · MyDezider (partner)',         avg: 40,  usd: '~$0.009', mode: 'org_buy_prepaid' },
  { name: 'Embed · Screener Top-N (partner)',    avg: 250, usd: '~$0.055', mode: 'org_buy_postpaid' },
  // CLD Engine
  { name: 'CLD · AI Suggestions (Phase B/C)',    avg: 45,  usd: '~$0.010', mode: 'user_buy' },
];

export default function AdminAiTouchpointsScreen() {
  return (
    <ScrollView style={s.wrap} contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
      <View style={s.headerCard}>
        <View style={s.headerIcon}><Ionicons name="receipt" size={20} color="#FFF" /></View>
        <View style={{ flex: 1 }}>
          <Text style={s.h1}>AI Touchpoints Catalog</Text>
          <Text style={s.sub}>
            All AI-metered surfaces in the user app, their average credit cost, the underlying
            USD cost, and how the credits are paid for. Static reference — keep this list in
            sync with /app/backend/core/ai_estimates.json.
          </Text>
        </View>
      </View>

      {/* Mode legend */}
      <View style={s.legend}>
        <Text style={s.legendTitle}>Spending modes</Text>
        {(Object.keys(MODE_META) as Mode[]).map(m => (
          <View key={m} style={s.legendRow}>
            <View style={[s.modeChip, { backgroundColor: MODE_META[m].bg }]}>
              <Text style={[s.modeText, { color: MODE_META[m].color }]}>{MODE_META[m].label}</Text>
            </View>
          </View>
        ))}
      </View>

      {/* Table */}
      <View style={s.tableHeader}>
        <Text style={[s.th, { flex: 3 }]}>Touchpoint</Text>
        <Text style={[s.th, { flex: 1, textAlign: 'right' }]}>Avg cr</Text>
        <Text style={[s.th, { flex: 1, textAlign: 'right' }]}>≈ USD</Text>
        <Text style={[s.th, { flex: 2 }]}>Spending mode</Text>
      </View>
      {ROWS.map((r, i) => (
        <View key={i} style={s.row} testID={`ai-touchpoint-row-${i}`}>
          <Text style={[s.td, { flex: 3 }]}>{r.name}</Text>
          <Text style={[s.td, { flex: 1, textAlign: 'right', fontWeight: '700' }]}>{r.avg}</Text>
          <Text style={[s.td, { flex: 1, textAlign: 'right', color: '#6B7280' }]}>{r.usd}</Text>
          <View style={{ flex: 2 }}>
            <View style={[s.modeChipSm, { backgroundColor: MODE_META[r.mode].bg }]}>
              <Text style={[s.modeText, { color: MODE_META[r.mode].color }]}>{MODE_META[r.mode].label}</Text>
            </View>
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#F8FAFC' },
  headerCard: { flexDirection: 'row', gap: 12, backgroundColor: '#FFF', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 12 },
  headerIcon: { width: 40, height: 40, borderRadius: 10, backgroundColor: '#7C3AED', alignItems: 'center', justifyContent: 'center' },
  h1: { fontSize: 17, fontWeight: '700', color: '#0F172A', marginBottom: 4 },
  sub: { fontSize: 12.5, color: '#64748B', lineHeight: 18 },
  legend: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 12 },
  legendTitle: { fontSize: 12, fontWeight: '800', color: '#0F172A', marginBottom: 8 },
  legendRow: { marginBottom: 4 },
  modeChip: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  modeChipSm: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999 },
  modeText: { fontSize: 11, fontWeight: '700' },
  tableHeader: { flexDirection: 'row', gap: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#CBD5E1' },
  th: { fontSize: 11, fontWeight: '800', color: '#475569', textTransform: 'uppercase', letterSpacing: 0.4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  td: { fontSize: 12.5, color: '#1F2937' },
});
