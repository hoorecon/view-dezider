/**
 * PassableValuePicker — the generic inter-module hand-off picker.
 * Lists live "passable values" (Option Names, Case-1 Worth %, MPPS Worth %,
 * P&C Score %, Solution Finder SMART Goals) aggregated by the backend and
 * lets the user insert one into the current input. SF entries carry a
 * navigable link (detailed Q5 action plan opens in the Solution Finder).
 *
 * Usage:
 *   <InsertFromModulesButton accept="text" onPick={(it) => setValue(it.value)} />
 */
import React, { useState, useEffect, useMemo } from 'react';
import {
  View, Text, StyleSheet, Modal, TouchableOpacity, TextInput,
  ScrollView, ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../utils/api';

export type PassableValue = {
  kind: 'text' | 'percent';
  category: string;
  value: string;
  source: string;
  module: string;
  link: string;
  ref_id: string;
};

const MODULE_COLORS: Record<string, string> = {
  MYDEZIDER: '#8E24AA', PROS_CONS: '#0D9488', SOLUTION_FINDER: '#4F46E5',
};

type PickerProps = {
  visible: boolean;
  accept: 'text' | 'percent' | 'all';
  onClose: () => void;
  onPick: (item: PassableValue) => void;
  title?: string;
};

export function PassableValuePicker({ visible, accept, onClose, onPick, title }: PickerProps) {
  const router = useRouter();
  const [items, setItems] = useState<PassableValue[]>([]);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState('');

  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    api.get('/integrations/passable-values')
      .then(r => setItems(r.data?.values || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, [visible]);

  const filtered = useMemo(() => {
    let list = items;
    if (accept !== 'all') list = list.filter(i => i.kind === accept);
    const t = q.trim().toLowerCase();
    if (t) list = list.filter(i => (i.value + ' ' + i.source + ' ' + i.category).toLowerCase().includes(t));
    return list;
  }, [items, accept, q]);

  const grouped = useMemo(() => {
    const g: Record<string, PassableValue[]> = {};
    filtered.forEach(i => { (g[i.category] = g[i.category] || []).push(i); });
    return g;
  }, [filtered]);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.head}>
            <Ionicons name="swap-horizontal" size={18} color="#4F46E5" />
            <Text style={s.title}>{title || 'Insert from other modules'}</Text>
            <TouchableOpacity onPress={onClose}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
          </View>
          <Text style={s.hint}>
            Live values from MyDezider (Step 10), Pros &amp; Cons (Step 8) and Solution Finder SMART Goals.
          </Text>
          <View style={s.searchRow}>
            <Ionicons name="search" size={14} color="#94A3B8" />
            <TextInput style={s.searchInput} value={q} onChangeText={setQ} placeholder="Search values…" placeholderTextColor="#94A3B8" />
          </View>
          {loading ? <ActivityIndicator color="#4F46E5" style={{ marginVertical: 30 }} /> : (
            <ScrollView style={{ maxHeight: 420 }}>
              {Object.keys(grouped).length === 0 && (
                <Text style={s.empty}>No passable values yet — complete a MyDezider decision, Pros &amp; Cons analysis or Solution Finder goal first.</Text>
              )}
              {Object.entries(grouped).map(([cat, list]) => (
                <View key={cat}>
                  <Text style={s.catTitle}>{cat} ({list.length})</Text>
                  {list.map((it, idx) => (
                    <TouchableOpacity key={`${cat}-${idx}`} style={s.row} onPress={() => { onPick(it); onClose(); }}>
                      <View style={[s.modChip, { backgroundColor: (MODULE_COLORS[it.module] || '#64748B') + '18' }]}>
                        <Text style={[s.modChipT, { color: MODULE_COLORS[it.module] || '#64748B' }]}>
                          {it.module === 'MYDEZIDER' ? 'MyDezider' : it.module === 'PROS_CONS' ? 'P&C' : 'SF'}
                        </Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.rowVal} numberOfLines={2}>{it.kind === 'percent' ? `${it.value}%` : it.value}</Text>
                        <Text style={s.rowSrc} numberOfLines={1}>{it.source}</Text>
                      </View>
                      {!!it.link && (
                        <TouchableOpacity hitSlop={8} onPress={() => { onClose(); router.push(it.link as any); }}>
                          <Ionicons name="open-outline" size={16} color="#4F46E5" />
                        </TouchableOpacity>
                      )}
                    </TouchableOpacity>
                  ))}
                </View>
              ))}
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
}

type BtnProps = {
  accept: 'text' | 'percent' | 'all';
  onPick: (item: PassableValue) => void;
  title?: string;
  compact?: boolean;
};

export default function InsertFromModulesButton({ accept, onPick, title, compact }: BtnProps) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <TouchableOpacity
        style={[s.btn, compact && s.btnCompact]}
        onPress={() => setOpen(true)}
        accessibilityLabel="Insert from other modules"
      >
        <Ionicons name="swap-horizontal" size={compact ? 12 : 15} color="#4F46E5" />
        {!compact && <Text style={s.btnT}>⇄</Text>}
      </TouchableOpacity>
      <PassableValuePicker visible={open} accept={accept} title={title} onClose={() => setOpen(false)} onPick={onPick} />
    </>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#FFF', borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 16, maxWidth: 640, width: '100%', alignSelf: 'center' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { flex: 1, fontSize: 15, fontWeight: '800', color: '#0F172A' },
  hint: { fontSize: 11, color: '#64748B', marginTop: 4, lineHeight: 15 },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingHorizontal: 10, marginTop: 10 },
  searchInput: { flex: 1, paddingVertical: 8, fontSize: 13, color: '#0F172A' },
  empty: { fontSize: 12, color: '#64748B', textAlign: 'center', marginVertical: 24, lineHeight: 18 },
  catTitle: { fontSize: 10, fontWeight: '800', color: '#64748B', textTransform: 'uppercase', marginTop: 12, marginBottom: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  modChip: { paddingHorizontal: 6, paddingVertical: 3, borderRadius: 6 },
  modChipT: { fontSize: 9, fontWeight: '800' },
  rowVal: { fontSize: 13, fontWeight: '600', color: '#0F172A' },
  rowSrc: { fontSize: 10, color: '#64748B', marginTop: 1 },
  btn: { width: 34, height: 34, borderRadius: 10, backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#C7D2FE', justifyContent: 'center', alignItems: 'center', flexDirection: 'row' },
  btnCompact: { width: 24, height: 24, borderRadius: 8 },
  btnT: { fontSize: 9, fontWeight: '800', color: '#4F46E5', marginLeft: 1 },
});
