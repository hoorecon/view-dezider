import React from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import { LIFE_AREAS, getLifeArea } from '../constants/lifeAreas';

/** Canonical decision-type labels (mirrors backend _DECISION_TYPE_LABELS). */
export const DECISION_TYPE_LABELS: Record<string, string> = {
  need: 'Need',
  want: 'Want',
  problem: 'Problem',
  aspiration: 'Aspiration',
  product_purchase: 'Product Purchase',
  standard: 'Standard',
  lifestyle_analyzer: 'Lifestyle Analyzer',
};

export function decisionTypeLabel(code?: string | null): string {
  if (!code) return '';
  const key = String(code).replace(/^dt_/, '');
  return DECISION_TYPE_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export type DateRangeKey = 'all' | '7d' | '30d' | '90d' | 'year';

export const DATE_RANGES: { key: DateRangeKey; label: string }[] = [
  { key: 'all', label: 'All time' },
  { key: '7d', label: 'Last 7 days' },
  { key: '30d', label: 'Last 30 days' },
  { key: '90d', label: 'Last 90 days' },
  { key: 'year', label: 'This year' },
];

/** Returns true if `iso` falls within the selected preset range. */
export function withinDateRange(iso: string | null | undefined, range: DateRangeKey): boolean {
  if (range === 'all') return true;
  if (!iso) return false;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return false;
  const now = new Date();
  if (range === 'year') return d.getFullYear() === now.getFullYear();
  const days = range === '7d' ? 7 : range === '30d' ? 30 : 90;
  const cutoff = now.getTime() - days * 24 * 60 * 60 * 1000;
  return d.getTime() >= cutoff;
}

interface Props {
  search: string;
  onSearch: (v: string) => void;
  dateRange: DateRangeKey;
  onDateRange: (v: DateRangeKey) => void;
  lifeArea: string | null;
  onLifeArea: (v: string | null) => void;
  decisionType: string | null;
  onDecisionType: (v: string | null) => void;
  /** Restrict the life-area & decision-type chips to those actually present. */
  availableLifeAreas?: string[];
  availableDecisionTypes?: string[];
  searchPlaceholder?: string;
}

export default function ListFilterBar({
  search, onSearch, dateRange, onDateRange,
  lifeArea, onLifeArea, decisionType, onDecisionType,
  availableLifeAreas, availableDecisionTypes, searchPlaceholder,
}: Props) {
  const laList = (availableLifeAreas && availableLifeAreas.length)
    ? LIFE_AREAS.filter((a) => availableLifeAreas.includes(a.id))
    : [];
  const dtList = availableDecisionTypes || [];

  return (
    <View style={s.wrap}>
      {/* Search */}
      <View style={s.searchBox}>
        <Ionicons name="search" size={16} color={COLORS.textMuted} />
        <TextInput
          testID="list-filter-search"
          style={s.searchInput}
          placeholder={searchPlaceholder || 'Search by title…'}
          placeholderTextColor={COLORS.textMuted}
          value={search}
          onChangeText={onSearch}
          autoCapitalize="none"
          returnKeyType="search"
          clearButtonMode="while-editing"
        />
        {search.length > 0 && Platform.OS !== 'ios' && (
          <TouchableOpacity onPress={() => onSearch('')} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Ionicons name="close-circle" size={16} color={COLORS.textMuted} />
          </TouchableOpacity>
        )}
      </View>

      {/* Date range */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.row}>
        <Ionicons name="calendar-outline" size={15} color={COLORS.textMuted} style={{ marginRight: 4, alignSelf: 'center' }} />
        {DATE_RANGES.map((r) => {
          const active = dateRange === r.key;
          return (
            <TouchableOpacity
              key={r.key}
              style={[s.chip, active && s.chipActive]}
              onPress={() => onDateRange(r.key)}
              activeOpacity={0.8}
            >
              <Text style={[s.chipTxt, active && s.chipTxtActive]}>{r.label}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* Life area */}
      {laList.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.row}>
          <TouchableOpacity style={[s.chip, !lifeArea && s.chipActive]} onPress={() => onLifeArea(null)} activeOpacity={0.8}>
            <Text style={[s.chipTxt, !lifeArea && s.chipTxtActive]}>All areas</Text>
          </TouchableOpacity>
          {laList.map((a) => {
            const active = lifeArea === a.id;
            return (
              <TouchableOpacity
                key={a.id}
                style={[s.chip, active && { backgroundColor: a.color, borderColor: a.color }]}
                onPress={() => onLifeArea(active ? null : a.id)}
                activeOpacity={0.8}
              >
                <Ionicons name={a.icon as any} size={12} color={active ? '#fff' : a.color} />
                <Text style={[s.chipTxt, active ? { color: '#fff' } : { color: a.color }]}>{a.short}</Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      )}

      {/* Decision type */}
      {dtList.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.row}>
          <TouchableOpacity style={[s.chip, !decisionType && s.chipActive]} onPress={() => onDecisionType(null)} activeOpacity={0.8}>
            <Text style={[s.chipTxt, !decisionType && s.chipTxtActive]}>All types</Text>
          </TouchableOpacity>
          {dtList.map((dt) => {
            const active = decisionType === dt;
            return (
              <TouchableOpacity
                key={dt}
                style={[s.chip, active && s.chipActive]}
                onPress={() => onDecisionType(active ? null : dt)}
                activeOpacity={0.8}
              >
                <Text style={[s.chipTxt, active && s.chipTxtActive]}>{decisionTypeLabel(dt)}</Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { gap: 8, marginBottom: 6 },
  searchBox: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border,
    borderRadius: 12, paddingHorizontal: 12, paddingVertical: Platform.OS === 'ios' ? 10 : 6,
  },
  searchInput: { flex: 1, fontSize: 14, color: COLORS.textPrimary, padding: 0 },
  row: { flexDirection: 'row', gap: 8, paddingVertical: 2 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16,
    borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: COLORS.white,
  },
  chipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  chipTxt: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  chipTxtActive: { color: '#fff' },
});
