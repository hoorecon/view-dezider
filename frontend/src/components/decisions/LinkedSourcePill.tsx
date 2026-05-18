/**
 * LinkedSourcePill — display badge for a decision that was linked-from another.
 *
 * Tap navigates to the source decision's result page.
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { COLORS } from '../../constants/colors';

interface Props {
  decision_id?: string | null;
  module?: string | null;
  option_label?: string | null;
  score_pct?: number | null;
  title?: string | null;
  compact?: boolean;
  onRemove?: () => void;
}

const ROUTE_MAP: Record<string, (id: string) => string> = {
  prr:              (id) => `/prr/${id}`,
  solution_finder:  (id) => `/tools/solution-finder/${id}`,
  conflict_breaker: (id) => `/tools/conflict-breaker/${id}`,
  solution_matrix:  (id) => `/tools/solution-matrix/${id}`,
};

const LABEL_MAP: Record<string, string> = {
  prr:              'My Dezider',
  solution_finder:  'Solution Finder',
  conflict_breaker: 'Conflict Breaker',
  solution_matrix:  'Solution Matrix',
};

export default function LinkedSourcePill({ decision_id, module, option_label, score_pct, title, compact, onRemove }: Props) {
  const router = useRouter();
  if (!decision_id || !module) return null;
  const navigate = () => {
    const builder = ROUTE_MAP[module];
    if (builder) router.push(builder(decision_id) as any);
  };
  const moduleLabel = LABEL_MAP[module] || module;

  return (
    <View style={[s.wrap, compact && s.wrapCompact]} testID="linked-source-pill">
      <Ionicons name="link" size={12} color={COLORS.primary} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <TouchableOpacity onPress={navigate} hitSlop={6}>
          <Text style={s.label} numberOfLines={1}>
            Linked from {moduleLabel}{title ? `: ${title}` : ''}
          </Text>
        </TouchableOpacity>
        {(option_label || typeof score_pct === 'number') && (
          <Text style={s.meta} numberOfLines={1}>
            {option_label || ''}{option_label && typeof score_pct === 'number' ? ' · ' : ''}
            {typeof score_pct === 'number' ? `${Math.round(score_pct)}%` : ''}
          </Text>
        )}
      </View>
      <TouchableOpacity onPress={navigate} hitSlop={6} testID="linked-source-open">
        <Ionicons name="open-outline" size={13} color={COLORS.primary} />
      </TouchableOpacity>
      {onRemove && (
        <TouchableOpacity onPress={onRemove} hitSlop={6} testID="linked-source-remove">
          <Ionicons name="close-circle" size={14} color={COLORS.danger || '#DC2626'} />
        </TouchableOpacity>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#C7D2FE', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, marginVertical: 6 },
  wrapCompact: { paddingVertical: 4, paddingHorizontal: 6 },
  label: { fontSize: 12, fontWeight: '700', color: COLORS.primary },
  meta: { fontSize: 10, color: COLORS.textSecondary, marginTop: 1 },
});
