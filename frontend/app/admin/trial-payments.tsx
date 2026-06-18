/**
 * Admin · Trial Payment Instruments
 * Read-only viewer for saved cards/UPI tokens captured at trial opt-in.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';

interface PI { user_id: string; email?: string; trial_type: string; method?: string; last4?: string; status: string; created_at?: string; razorpay_customer_id?: string; }

export default function AdminTrialPayments() {
  const router = useRouter();
  const [items, setItems] = useState<PI[]>([]);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState<string>('');

  const load = async () => {
    setBusy(true);
    try {
      const params = filter ? `?status=${filter}` : '';
      const { data } = await api.get(`/acm-v2/trial-payments${params}`);
      setItems(data?.items || []);
    } finally { setBusy(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [filter]);

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.title}>Trial Payment Instruments</Text>
        <Text style={s.subtitle}>{items.length} record(s)</Text>
      </View>
      <View style={s.filterRow}>
        {['', 'active', 'cancelled', 'expired'].map(f => (
          <TouchableOpacity key={f || 'all'} onPress={() => setFilter(f)} style={[s.fchip, filter === f && s.fchipOn]}>
            <Text style={[s.fchipText, filter === f && s.fchipTextOn]}>{f || 'all'}</Text>
          </TouchableOpacity>
        ))}
      </View>
      {busy ? <ActivityIndicator style={{ marginTop: 40 }} /> : (
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        {items.length === 0 ? (
          <View style={s.empty}><Text style={s.emptyText}>No trial payment instruments saved yet.</Text></View>
        ) : items.map((p, i) => (
          <View key={i} style={s.card}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Text style={s.cardTitle}>{p.email || p.user_id}</Text>
              <Text style={[s.pill, p.status === 'active' ? s.pillOk : s.pillDim]}>{p.status}</Text>
            </View>
            <Text style={s.meta}>{p.trial_type} · {p.method || 'card'}{p.last4 ? ` ····${p.last4}` : ''}</Text>
            {p.razorpay_customer_id && <Text style={s.meta}>cust: {p.razorpay_customer_id}</Text>}
            {p.created_at && <Text style={s.meta}>saved: {new Date(p.created_at).toLocaleString()}</Text>}
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
  filterRow: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingVertical: 10 },
  fchip: { backgroundColor: '#111B2F', borderColor: '#1F2A44', borderWidth: 1, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14 },
  fchipOn: { backgroundColor: '#5B7CFA', borderColor: '#5B7CFA' },
  fchipText: { color: '#8A95B0', fontSize: 12 },
  fchipTextOn: { color: '#FFF', fontWeight: '700' },
  card: { backgroundColor: '#111B2F', padding: 14, borderRadius: 12, marginBottom: 10, borderColor: '#1F2A44', borderWidth: 1 },
  cardTitle: { color: '#FFF', fontWeight: '700', fontSize: 14 },
  meta: { color: '#8A95B0', fontSize: 12, marginTop: 4 },
  pill: { fontSize: 11, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8, overflow: 'hidden' },
  pillOk: { color: '#10B981', backgroundColor: '#10B98122' },
  pillDim: { color: '#8A95B0', backgroundColor: '#1F2A44' },
  empty: { padding: 24, alignItems: 'center' },
  emptyText: { color: '#8A95B0' },
});
