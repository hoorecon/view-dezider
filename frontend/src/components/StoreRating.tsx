import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../utils/api';
import { showAlert } from '../utils/alert';

/**
 * Store rating widget — Play-Store-style aggregate + 3-factor rating
 * (Usefulness · Affordability · Accuracy). Shows aggregate for everyone;
 * lets an authenticated user submit / update their rating.
 */

type Aggregate = {
  count: number; overall: number;
  usefulness: number; affordability: number; accuracy: number;
};

const FACTORS: Array<{ key: 'usefulness' | 'affordability' | 'accuracy'; label: string }> = [
  { key: 'usefulness', label: 'Usefulness' },
  { key: 'affordability', label: 'Affordability' },
  { key: 'accuracy', label: 'Accuracy' },
];

export default function StoreRating({ itemId, isAuthenticated }: { itemId: string; isAuthenticated: boolean }) {
  const [agg, setAgg] = useState<Aggregate | null>(null);
  const [mine, setMine] = useState<{ usefulness?: number; affordability?: number; accuracy?: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/decider-store/${itemId}/rating`);
      setAgg(r.data);
    } catch { /* silent */ }
    if (isAuthenticated) {
      try {
        const r = await api.get(`/decider-store/${itemId}/my-rating`);
        setMine(r.data?.mine || null);
      } catch { /* silent */ }
    }
  }, [itemId, isAuthenticated]);

  useEffect(() => { load(); }, [load]);

  const setStar = (k: 'usefulness' | 'affordability' | 'accuracy', v: number) => {
    setMine((prev) => ({ ...(prev || {}), [k]: v }));
  };

  const submit = async () => {
    if (!isAuthenticated) { showAlert('Sign in required', 'Please sign in to rate this item.'); return; }
    const u = mine?.usefulness, a = mine?.affordability, c = mine?.accuracy;
    if (!u || !a || !c) { showAlert('Rate all three', 'Please star each factor (Usefulness, Affordability, Accuracy) from 1–5.'); return; }
    setBusy(true);
    try {
      await api.post(`/decider-store/${itemId}/rate`, { usefulness: u, affordability: a, accuracy: c });
      await load();
      setExpanded(false);
    } catch (e: any) {
      showAlert('Rating failed', e?.response?.data?.detail || 'Please try again.');
    } finally { setBusy(false); }
  };

  const overall = agg?.overall || 0;
  const count = agg?.count || 0;

  return (
    <View style={styles.wrap}>
      <TouchableOpacity style={styles.summary} onPress={() => setExpanded(!expanded)} activeOpacity={0.8}>
        <View style={styles.starsRow}>
          {[1, 2, 3, 4, 5].map((i) => (
            <Ionicons key={i}
              name={overall >= i - 0.25 ? 'star' : overall >= i - 0.75 ? 'star-half' : 'star-outline'}
              size={16} color="#F59E0B" />
          ))}
          <Text style={styles.aggTxt}>{overall > 0 ? overall.toFixed(1) : '—'}</Text>
          <Text style={styles.countTxt}>{count === 0 ? 'Be the first to rate' : `${count} rating${count === 1 ? '' : 's'}`}</Text>
        </View>
        {isAuthenticated && (
          <View style={styles.rateBtn}>
            <Ionicons name={mine ? 'create' : 'star'} size={13} color="#4F46E5" />
            <Text style={styles.rateBtnTxt}>{mine ? 'Edit rating' : 'Rate'}</Text>
          </View>
        )}
      </TouchableOpacity>

      {agg && count > 0 && (
        <View style={styles.breakdown}>
          {FACTORS.map((f) => (
            <View key={f.key} style={styles.breakRow}>
              <Text style={styles.breakLabel}>{f.label}</Text>
              <View style={styles.miniBarBg}>
                <View style={[styles.miniBar, { width: `${((agg as any)[f.key] || 0) / 5 * 100}%` }]} />
              </View>
              <Text style={styles.breakVal}>{((agg as any)[f.key] || 0).toFixed(1)}</Text>
            </View>
          ))}
        </View>
      )}

      {expanded && isAuthenticated && (
        <View style={styles.rater}>
          <Text style={styles.raterTitle}>Rate this {count === 0 ? '(be the first!)' : ''}</Text>
          {FACTORS.map((f) => {
            const v: number = (mine?.[f.key] as any) || 0;
            return (
              <View key={f.key} style={styles.raterRow}>
                <Text style={styles.raterLabel}>{f.label}</Text>
                <View style={{ flexDirection: 'row', gap: 3 }}>
                  {[1, 2, 3, 4, 5].map((i) => (
                    <TouchableOpacity key={i} onPress={() => setStar(f.key, i)}>
                      <Ionicons name={v >= i ? 'star' : 'star-outline'} size={22} color="#F59E0B" />
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            );
          })}
          <TouchableOpacity style={styles.submitBtn} onPress={submit} disabled={busy}>
            {busy ? <ActivityIndicator size="small" color="#FFF" /> : <>
              <Ionicons name="checkmark" size={16} color="#FFF" />
              <Text style={styles.submitTxt}>{mine ? 'Update my rating' : 'Submit rating'}</Text>
            </>}
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: 14, marginBottom: 10, backgroundColor: '#FAFAFA', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#E5E7EB' },
  summary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  starsRow: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  aggTxt: { marginLeft: 6, fontSize: 15, fontWeight: '800', color: '#0F172A' },
  countTxt: { marginLeft: 8, fontSize: 12, color: '#64748B' },
  rateBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#EEF2FF', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999 },
  rateBtnTxt: { color: '#4F46E5', fontWeight: '800', fontSize: 12 },
  breakdown: { marginTop: 10, gap: 4 },
  breakRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  breakLabel: { width: 92, fontSize: 11, color: '#475569', fontWeight: '700' },
  miniBarBg: { flex: 1, height: 6, backgroundColor: '#E2E8F0', borderRadius: 3, overflow: 'hidden' },
  miniBar: { height: '100%', backgroundColor: '#F59E0B', borderRadius: 3 },
  breakVal: { width: 30, textAlign: 'right', fontSize: 11, color: '#0F172A', fontWeight: '700' },
  rater: { marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: '#E5E7EB' },
  raterTitle: { fontSize: 12, fontWeight: '800', color: '#0F172A', marginBottom: 8 },
  raterRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  raterLabel: { fontSize: 13, color: '#334155', fontWeight: '700' },
  submitBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#4F46E5', paddingVertical: 10, borderRadius: 10, marginTop: 6 },
  submitTxt: { color: '#FFF', fontWeight: '800', fontSize: 13 },
});
