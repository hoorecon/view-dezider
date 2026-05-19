/**
 * /admin/pricing — Pricing page wrapped inside the AdminShell.
 *
 * For admins, the public /pricing screen opens standalone (no admin nav).
 * This thin wrapper renders the same data inside the admin frame so the
 * sidebar/topbar stay visible. Data comes from the same /api/pricing
 * endpoint.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, ActivityIndicator, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';

interface Tier { key: string; order: number; chakra_sanskrit: string; label: string; aspiration: string; color: string; icon: string; monthly_price_inr: number }
interface MatrixRow { module_id: string; module_name?: string; module_icon?: string; tiers: Record<string, boolean> }

export default function AdminPricingScreen() {
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [rows, setRows] = useState<MatrixRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/pricing');
        setTiers(r.data.tiers || []);
        setRows(r.data.matrix_rows || []);
      } catch (e) {
        console.error('Pricing load failed', e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <View style={s.container}>
      <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 60 }} showsVerticalScrollIndicator>
        <View style={s.header}>
          <Text style={s.title}>Pricing Page (Admin View)</Text>
          <Text style={s.subtitle}>
            Public-facing pricing • 7-Chakra subscription tiers. To edit the module ↔ tier mapping use{' '}
            <Text style={{ fontWeight: '700' }}>Tier Matrix</Text> in the sidebar.
          </Text>
        </View>

        {loading ? (
          <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
        ) : (
          <>
            {/* Tier cards */}
            <View style={s.tierGrid}>
              {tiers.map(t => (
                <View key={t.key} style={[s.tierCard, { borderColor: t.color }]}>
                  <View style={[s.tierIconWrap, { backgroundColor: t.color + '20' }]}>
                    <Ionicons name={(t.icon || 'star') as any} size={22} color={t.color} />
                  </View>
                  <Text style={s.tierLabel}>{t.label}</Text>
                  <Text style={s.tierSanskrit}>{t.chakra_sanskrit}</Text>
                  <Text style={s.tierAspiration}>{t.aspiration}</Text>
                  <Text style={s.tierPrice}>₹{t.monthly_price_inr || 0}<Text style={s.tierPriceUnit}> /mo</Text></Text>
                </View>
              ))}
            </View>

            {/* Module x Tier compact table */}
            <Text style={s.sectionHeader}>Module Availability by Tier</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator>
              <View>
                <View style={s.tableHeaderRow}>
                  <Text style={[s.cell, s.cellHeader, s.colModule]}>Module</Text>
                  {tiers.map(t => (
                    <Text key={t.key} style={[s.cell, s.cellHeader, s.colTier]}>{t.label}</Text>
                  ))}
                </View>
                {rows.map(r => (
                  <View key={r.module_id} style={s.tableRow}>
                    <Text style={[s.cell, s.colModule, s.cellModule]}>{r.module_name || r.module_id}</Text>
                    {tiers.map(t => (
                      <View key={t.key} style={[s.cell, s.colTier, s.cellCheck]}>
                        <Ionicons
                          name={r.tiers?.[t.key] ? 'checkmark-circle' : 'close-circle-outline'}
                          size={18}
                          color={r.tiers?.[t.key] ? '#10B981' : '#D1D5DB'}
                        />
                      </View>
                    ))}
                  </View>
                ))}
              </View>
            </ScrollView>

            <View style={s.linkRow}>
              <TouchableOpacity
                onPress={() => {
                  if (typeof window !== 'undefined') window.open('/pricing', '_blank');
                }}
                style={s.linkBtn}
              >
                <Ionicons name="open-outline" size={14} color={COLORS.primary} />
                <Text style={s.linkBtnText}>Open public pricing page (new tab)</Text>
              </TouchableOpacity>
            </View>
          </>
        )}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, minHeight: 600, backgroundColor: COLORS.background },
  header: { marginBottom: 16 },
  title: { fontSize: 22, fontWeight: '800', color: COLORS.textPrimary },
  subtitle: { fontSize: 13, color: COLORS.textMuted, marginTop: 4 },
  tierGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 24 },
  tierCard: {
    width: 160, padding: 14, borderRadius: 12, borderWidth: 2,
    backgroundColor: COLORS.cardBg, alignItems: 'flex-start',
  },
  tierIconWrap: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  tierLabel: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  tierSanskrit: { fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic' },
  tierAspiration: { fontSize: 11, color: COLORS.textSecondary, marginTop: 4, marginBottom: 8 },
  tierPrice: { fontSize: 18, fontWeight: '800', color: COLORS.primary },
  tierPriceUnit: { fontSize: 11, fontWeight: '500', color: COLORS.textMuted },
  sectionHeader: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10 },
  tableHeaderRow: { flexDirection: 'row', borderBottomWidth: 2, borderColor: COLORS.border, backgroundColor: COLORS.cardBg },
  tableRow: { flexDirection: 'row', borderBottomWidth: 1, borderColor: COLORS.border },
  cell: { paddingVertical: 8, paddingHorizontal: 8 },
  cellHeader: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center' },
  cellModule: { fontSize: 12, color: COLORS.textPrimary, fontWeight: '500' },
  cellCheck: { alignItems: 'center' },
  colModule: { width: 180 },
  colTier: { width: 80 },
  linkRow: { marginTop: 20 },
  linkBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
    backgroundColor: COLORS.primary + '12', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8,
  },
  linkBtnText: { color: COLORS.primary, fontSize: 13, fontWeight: '600' },
});
