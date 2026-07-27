/**
 * PassableValuePicker — the generic "Inter Modules Connector".
 * Enlarged frame + filters: Module (MyDezider / Pros & Cons / Solution Finder),
 * Area of Life, Date Range (7 / 30 / 90 / all days) — in addition to the
 * search box. Each row shows the source decision title so users can locate
 * the decision first, then pick the exact value (Option Name, Case-1 Worth %,
 * MPPS %, P&C Score %, SMART Goal).
 *
 * Web tooltip: renders "Inter Modules Connector" via the DOM `title=`
 * attribute so hovering the ⇄ icon on desktop shows the label; on native it
 * degrades to `accessibilityLabel` which screen readers announce.
 *
 * Usage:
 *   <InsertFromModulesButton accept="text" onPick={(it) => setValue(it.value)} />
 */
import React, { useState, useEffect, useMemo } from 'react';
import {
  View, Text, StyleSheet, Modal, TouchableOpacity, TextInput,
  ScrollView, ActivityIndicator, Platform,
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
  life_area?: string;
  updated_at?: string;
  decision_title?: string;
};

const MODULE_COLORS: Record<string, string> = {
  MYDEZIDER: '#8E24AA', PROS_CONS: '#0D9488', SOLUTION_FINDER: '#4F46E5',
};
const MODULE_LABELS: Record<string, string> = {
  MYDEZIDER: 'MyDezider', PROS_CONS: 'Pros & Cons', SOLUTION_FINDER: 'Solution Finder',
};
const MODULES_ALL: Array<keyof typeof MODULE_LABELS> = ['MYDEZIDER', 'PROS_CONS', 'SOLUTION_FINDER'];
const DATE_OPTIONS: Array<{ id: string; label: string; days: number | null }> = [
  { id: 'all', label: 'All time', days: null },
  { id: '7', label: 'Last 7 days', days: 7 },
  { id: '30', label: 'Last 30 days', days: 30 },
  { id: '90', label: 'Last 90 days', days: 90 },
];

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
  const [lifeAreas, setLifeAreas] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState('');
  const [modules, setModules] = useState<Set<string>>(new Set());   // empty = all
  const [area, setArea] = useState<string>('');                     // ''  = all
  const [dateRange, setDateRange] = useState<string>('all');
  const [showFilters, setShowFilters] = useState(true);

  useEffect(() => {
    if (!visible) return;
    setLoading(true);
    api.get('/integrations/passable-values')
      .then((r) => {
        setItems(r.data?.values || []);
        setLifeAreas(r.data?.life_areas || []);
      })
      .catch(() => { setItems([]); setLifeAreas([]); })
      .finally(() => setLoading(false));
  }, [visible]);

  const filtered = useMemo(() => {
    let list = items;
    if (accept !== 'all') list = list.filter((i) => i.kind === accept);
    if (modules.size > 0) list = list.filter((i) => modules.has(i.module));
    if (area) list = list.filter((i) => (i.life_area || '') === area);
    const dr = DATE_OPTIONS.find((d) => d.id === dateRange);
    if (dr?.days) {
      const cutoff = Date.now() - dr.days * 24 * 60 * 60 * 1000;
      list = list.filter((i) => {
        const t = i.updated_at ? Date.parse(i.updated_at) : NaN;
        return isNaN(t) ? true : t >= cutoff;
      });
    }
    const t = q.trim().toLowerCase();
    if (t) list = list.filter((i) =>
      (i.value + ' ' + i.source + ' ' + i.category + ' ' + (i.decision_title || '') + ' ' + (i.life_area || ''))
        .toLowerCase().includes(t)
    );
    return list;
  }, [items, accept, modules, area, dateRange, q]);

  const grouped = useMemo(() => {
    // First locate the decision, THEN show its values under it — per the user's
    // requirement "First locate the decision / solution finder → then map its
    // corresponding values (Option Name, Case-1 Worth %, MPPS % etc.)".
    const g: Record<string, PassableValue[]> = {};
    filtered.forEach((i) => {
      const k = `${MODULE_LABELS[i.module] || i.module} · ${i.decision_title || i.source}`;
      (g[k] = g[k] || []).push(i);
    });
    return g;
  }, [filtered]);

  const toggleModule = (m: string) => {
    const n = new Set(modules);
    if (n.has(m)) n.delete(m); else n.add(m);
    setModules(n);
  };

  const clearFilters = () => { setModules(new Set()); setArea(''); setDateRange('all'); setQ(''); };
  const activeFilterCount =
    (modules.size ? 1 : 0) + (area ? 1 : 0) + (dateRange !== 'all' ? 1 : 0) + (q ? 1 : 0);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.head}>
            <Ionicons name="swap-horizontal" size={20} color="#4F46E5" />
            <Text style={s.title}>{title || 'Inter Modules Connector'}</Text>
            <TouchableOpacity onPress={onClose} accessibilityLabel="Close">
              <Ionicons name="close" size={22} color="#475569" />
            </TouchableOpacity>
          </View>
          <Text style={s.hint}>
            Live values from MyDezider (Step 10), Pros &amp; Cons (Step 8) and Solution Finder SMART Goals.
          </Text>

          <View style={s.searchRow}>
            <Ionicons name="search" size={14} color="#94A3B8" />
            <TextInput style={s.searchInput} value={q} onChangeText={setQ} placeholder="Search values, decisions, life-areas…" placeholderTextColor="#94A3B8" />
          </View>

          <View style={s.filterHead}>
            <TouchableOpacity onPress={() => setShowFilters((v) => !v)} style={s.filterHeadBtn}>
              <Ionicons name="options-outline" size={14} color="#4F46E5" />
              <Text style={s.filterHeadT}>Filters{activeFilterCount ? ` · ${activeFilterCount}` : ''}</Text>
              <Ionicons name={showFilters ? 'chevron-up' : 'chevron-down'} size={14} color="#4F46E5" />
            </TouchableOpacity>
            {activeFilterCount > 0 && (
              <TouchableOpacity onPress={clearFilters} accessibilityLabel="Clear filters">
                <Text style={s.clearT}>Clear</Text>
              </TouchableOpacity>
            )}
          </View>

          {showFilters && (
            <View style={s.filterBlock}>
              <Text style={s.filterLabel}>Module</Text>
              <View style={s.chipRow}>
                {MODULES_ALL.map((m) => {
                  const on = modules.has(m);
                  return (
                    <TouchableOpacity key={m} onPress={() => toggleModule(m)}
                      style={[s.chip, on && { backgroundColor: MODULE_COLORS[m] + '22', borderColor: MODULE_COLORS[m] }]}>
                      <Text style={[s.chipT, on && { color: MODULE_COLORS[m] }]}>{MODULE_LABELS[m]}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              {lifeAreas.length > 0 && (
                <>
                  <Text style={s.filterLabel}>Area of Life</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                    <View style={s.chipRow}>
                      <TouchableOpacity onPress={() => setArea('')} style={[s.chip, !area && s.chipOn]}>
                        <Text style={[s.chipT, !area && s.chipTOn]}>All</Text>
                      </TouchableOpacity>
                      {lifeAreas.map((a) => (
                        <TouchableOpacity key={a} onPress={() => setArea(a === area ? '' : a)} style={[s.chip, area === a && s.chipOn]}>
                          <Text style={[s.chipT, area === a && s.chipTOn]} numberOfLines={1}>{a}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </ScrollView>
                </>
              )}

              <Text style={s.filterLabel}>Date Range</Text>
              <View style={s.chipRow}>
                {DATE_OPTIONS.map((d) => (
                  <TouchableOpacity key={d.id} onPress={() => setDateRange(d.id)} style={[s.chip, dateRange === d.id && s.chipOn]}>
                    <Text style={[s.chipT, dateRange === d.id && s.chipTOn]}>{d.label}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}

          {loading ? <ActivityIndicator color="#4F46E5" style={{ marginVertical: 30 }} /> : (
            <ScrollView style={s.list}>
              {Object.keys(grouped).length === 0 && (
                <Text style={s.empty}>No values match your filters — try clearing filters, or complete a MyDezider decision, Pros &amp; Cons analysis or Solution Finder goal first.</Text>
              )}
              {Object.entries(grouped).map(([decisionKey, list]) => (
                <View key={decisionKey} style={s.groupBlock}>
                  <Text style={s.decTitle} numberOfLines={1}>{decisionKey}</Text>
                  {list.map((it, idx) => (
                    <TouchableOpacity key={`${decisionKey}-${idx}`} style={s.row} onPress={() => { onPick(it); onClose(); }}>
                      <View style={[s.modChip, { backgroundColor: (MODULE_COLORS[it.module] || '#64748B') + '18' }]}>
                        <Text style={[s.modChipT, { color: MODULE_COLORS[it.module] || '#64748B' }]}>
                          {it.module === 'MYDEZIDER' ? 'MyD' : it.module === 'PROS_CONS' ? 'P&C' : 'SF'}
                        </Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.rowCat} numberOfLines={1}>{it.category}</Text>
                        <Text style={s.rowVal} numberOfLines={2}>{it.kind === 'percent' ? `${it.value}%` : it.value}</Text>
                        {!!it.life_area && <Text style={s.rowMeta} numberOfLines={1}>{it.life_area}</Text>}
                      </View>
                      {!!it.link && (
                        <TouchableOpacity hitSlop={8} onPress={(e: any) => { e?.stopPropagation?.(); onClose(); router.push(it.link as any); }} accessibilityLabel="Open source">
                          <Ionicons name="open-outline" size={18} color="#4F46E5" />
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
  // Attach the DOM `title` attribute on web so hovering the ⇄ icon shows the
  // "Inter Modules Connector" tooltip in the browser. On native, this prop is
  // ignored and `accessibilityLabel` continues to serve screen readers.
  const webTitleProp: any = Platform.OS === 'web' ? { title: 'Inter Modules Connector' } : {};
  return (
    <>
      <TouchableOpacity
        style={[s.btn, compact && s.btnCompact]}
        onPress={() => setOpen(true)}
        accessibilityLabel="Inter Modules Connector"
        {...webTitleProp}
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
  sheet: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 18, maxWidth: 820, width: '100%', alignSelf: 'center', height: '88%' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { flex: 1, fontSize: 17, fontWeight: '800', color: '#0F172A' },
  hint: { fontSize: 12, color: '#64748B', marginTop: 4, lineHeight: 16 },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingHorizontal: 10, marginTop: 12 },
  searchInput: { flex: 1, paddingVertical: 10, fontSize: 13, color: '#0F172A' },
  filterHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 },
  filterHeadBtn: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  filterHeadT: { fontSize: 12, fontWeight: '700', color: '#4F46E5' },
  clearT: { fontSize: 12, color: '#DC2626', fontWeight: '600' },
  filterBlock: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  filterLabel: { fontSize: 10, fontWeight: '800', color: '#64748B', textTransform: 'uppercase', marginTop: 8, marginBottom: 4 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC' },
  chipOn: { backgroundColor: '#EEF2FF', borderColor: '#4F46E5' },
  chipT: { fontSize: 11, color: '#475569', fontWeight: '600' },
  chipTOn: { color: '#4F46E5' },
  list: { flex: 1, marginTop: 6 },
  empty: { fontSize: 12, color: '#64748B', textAlign: 'center', marginVertical: 24, lineHeight: 18 },
  groupBlock: { marginTop: 10, backgroundColor: '#FAFAFC', borderRadius: 10, padding: 8 },
  decTitle: { fontSize: 12, fontWeight: '800', color: '#0F172A', marginBottom: 4 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderTopWidth: 1, borderTopColor: '#EEF2F7' },
  modChip: { paddingHorizontal: 7, paddingVertical: 3, borderRadius: 6, minWidth: 34, alignItems: 'center' },
  modChipT: { fontSize: 9, fontWeight: '800' },
  rowCat: { fontSize: 10, fontWeight: '700', color: '#64748B', textTransform: 'uppercase' },
  rowVal: { fontSize: 13, fontWeight: '600', color: '#0F172A', marginTop: 1 },
  rowMeta: { fontSize: 10, color: '#94A3B8', marginTop: 1 },
  btn: { width: 34, height: 34, borderRadius: 10, backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#C7D2FE', justifyContent: 'center', alignItems: 'center', flexDirection: 'row' },
  btnCompact: { width: 24, height: 24, borderRadius: 8 },
  btnT: { fontSize: 9, fontWeight: '800', color: '#4F46E5', marginLeft: 1 },
});
