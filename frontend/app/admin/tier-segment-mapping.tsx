/**
 * Admin · Tier ↔ Customer-Segment Mapping
 * Pick which Customer Segments are reachable from each 7-Chakra tier.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';

interface Tier { id: string; name: string; }
interface Segment { id: string; name: string; }

export default function AdminTierSegmentMapping() {
  const router = useRouter();
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [mapping, setMapping] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const [savingTier, setSavingTier] = useState<string | null>(null);

  const load = async () => {
    setBusy(true);
    try {
      const [t, sg, m] = await Promise.all([
        api.get('/tiers').catch(() => ({ data: { tiers: [] } })),
        api.get('/customer-segments').catch(() => ({ data: { segments: [] } })),
        api.get('/acm-v2/tier-segment-mapping'),
      ]);
      setTiers(t.data?.tiers || t.data || []);
      setSegments(sg.data?.segments || sg.data || []);
      const mp: Record<string, string[]> = {};
      for (const r of (m.data?.mappings || [])) mp[r.tier_id] = r.segment_ids || [];
      setMapping(mp);
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  };
  useEffect(() => { load(); }, []);

  const toggle = (tierId: string, segId: string) => {
    setMapping(prev => {
      const cur = prev[tierId] || [];
      const next = cur.includes(segId) ? cur.filter(x => x !== segId) : [...cur, segId];
      return { ...prev, [tierId]: next };
    });
  };

  const saveTier = async (tierId: string) => {
    setSavingTier(tierId);
    try {
      await api.put(`/acm-v2/tier-segment-mapping/${tierId}`, { segment_ids: mapping[tierId] || [] });
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || e.message);
    } finally { setSavingTier(null); }
  };

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.title}>Tier ↔ Customer Segments</Text>
        <Text style={s.subtitle}>{tiers.length} tiers · {segments.length} segments</Text>
      </View>
      {busy ? <ActivityIndicator style={{ marginTop: 40 }} /> : (
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        {tiers.length === 0 && (
          <View style={s.empty}><Text style={s.emptyText}>No tiers found. Configure Tier Matrix first.</Text></View>
        )}
        {tiers.map(t => (
          <View key={t.id} style={s.card}>
            <View style={s.cardHeader}>
              <Text style={s.cardTitle}>{t.name}</Text>
              <TouchableOpacity onPress={() => saveTier(t.id)} style={s.saveSmall}>
                {savingTier === t.id ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.saveSmallText}>Save</Text>}
              </TouchableOpacity>
            </View>
            <View style={s.chipsWrap}>
              {segments.map(sg => {
                const on = (mapping[t.id] || []).includes(sg.id);
                return (
                  <TouchableOpacity key={sg.id} onPress={() => toggle(t.id, sg.id)} style={[s.chip, on && s.chipOn]}>
                    <Text style={[s.chipText, on && s.chipTextOn]}>{sg.name}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        ))}
      </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#0B1220' },
  header: { paddingHorizontal: 16, paddingVertical: 14, backgroundColor: '#111B2F', borderBottomColor: '#1F2A44', borderBottomWidth: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  backBtn: { padding: 6 },
  title: { color: '#FFF', fontSize: 18, fontWeight: '700' },
  subtitle: { color: '#8A95B0', fontSize: 12, marginTop: 2, flex: 1 },
  card: { backgroundColor: '#111B2F', padding: 14, borderRadius: 12, marginBottom: 14, borderColor: '#1F2A44', borderWidth: 1 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  cardTitle: { color: '#FFF', fontWeight: '700', fontSize: 15 },
  saveSmall: { backgroundColor: '#5B7CFA', paddingHorizontal: 14, paddingVertical: 6, borderRadius: 8 },
  saveSmallText: { color: '#FFF', fontWeight: '700', fontSize: 12 },
  chipsWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { backgroundColor: '#0B1220', borderColor: '#1F2A44', borderWidth: 1, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16 },
  chipOn: { backgroundColor: '#5B7CFA', borderColor: '#5B7CFA' },
  chipText: { color: '#8A95B0', fontSize: 12 },
  chipTextOn: { color: '#FFF', fontWeight: '700' },
  empty: { padding: 24, alignItems: 'center' },
  emptyText: { color: '#8A95B0' },
});
