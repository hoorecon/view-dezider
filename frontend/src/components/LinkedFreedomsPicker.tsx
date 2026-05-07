/**
 * <LinkedFreedomsPicker> — reusable multi-select chip row for tagging an
 * entity (PNA goal / CTT task / lifestyle routine / daily entry / etc.) with
 * one or more LDC freedom keys.
 *
 * Auto-fetches the user's current LDC list (via /api/ldc/me) so the chips
 * always reflect the user's personalised order + custom freedoms.
 *
 * Usage:
 *   const [linked, setLinked] = useState<string[]>(item?.linked_freedoms || []);
 *   <LinkedFreedomsPicker value={linked} onChange={setLinked} />
 *
 * On save, include `linked_freedoms: linked` in your PUT/POST body. Backend
 * persists as a string[] field on the entity. Time Dezider's allocator
 * already reads this field for /time-allocation/suggestions.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../utils/api';
import { COLORS } from '../constants/colors';

interface Props {
  value: string[];
  onChange: (next: string[]) => void;
  label?: string;
  helper?: string;
  max?: number;
  testIDPrefix?: string;
  compact?: boolean;
}

interface Freedom { key: string; label: string; rank: number; color?: string; icon?: string; pinned_this_week?: boolean }

export function LinkedFreedomsPicker({
  value, onChange,
  label = 'LDC freedoms this serves',
  helper = 'Pick the freedoms this item advances. Time Dezider uses these to prioritise your week.',
  max = 5,
  testIDPrefix = 'lfp',
  compact = false,
}: Props) {
  const [freedoms, setFreedoms] = useState<Freedom[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api.get('/ldc/me');
        if (alive) setFreedoms(r.data?.compass?.freedoms || []);
      } catch { /* user has no LDC yet — keep empty */ }
      finally { if (alive) setLoading(false); }
    })();
    return () => { alive = false; };
  }, []);

  const toggle = (k: string) => {
    if (value.includes(k)) {
      onChange(value.filter(x => x !== k));
    } else {
      if (value.length >= max) return;
      onChange([...value, k]);
    }
  };

  if (loading) {
    return (
      <View style={[s.wrap, compact && { paddingVertical: 4 }]}>
        <ActivityIndicator size="small" color={COLORS.textMuted} />
      </View>
    );
  }

  if (freedoms.length === 0) {
    return (
      <View style={[s.wrap, compact && { paddingVertical: 4 }]}>
        <Text style={s.label}>{label}</Text>
        <Text style={s.emptyHelper}>Set up your Life Directions Compass first to enable freedom tagging.</Text>
      </View>
    );
  }

  return (
    <View style={[s.wrap, compact && { paddingVertical: 4 }]}>
      {!compact && <Text style={s.label}>{label}</Text>}
      {!compact && !!helper && <Text style={s.helper}>{helper}</Text>}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingVertical: compact ? 4 : 6 }}>
        {freedoms.map(f => {
          const selected = value.includes(f.key);
          const color = f.color || COLORS.primary;
          return (
            <TouchableOpacity
              key={f.key}
              testID={`${testIDPrefix}-${f.key}`}
              onPress={() => toggle(f.key)}
              style={[
                s.chip,
                selected && { backgroundColor: color + '22', borderColor: color },
                f.pinned_this_week && { borderWidth: 2 },
              ]}
            >
              {f.icon && <Ionicons name={f.icon as any} size={12} color={selected ? color : COLORS.textMuted} />}
              <Text style={[s.chipText, selected && { color, fontWeight: '700' }]}>
                {f.label.replace(' Freedom', '')}
              </Text>
              <Text style={[s.rankBadge, selected && { color, opacity: 1 }]}>#{f.rank}</Text>
              {f.pinned_this_week && <Text style={[s.pinBadge, { color }]}>📌</Text>}
            </TouchableOpacity>
          );
        })}
      </ScrollView>
      {value.length > 0 && !compact && (
        <Text style={s.selectedHelper}>
          {value.length} selected · {value.length >= max ? `max ${max} reached` : `up to ${max - value.length} more`}
        </Text>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { paddingVertical: 8 },
  label: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 2 },
  helper: { fontSize: 11, color: COLORS.textMuted, marginBottom: 4, lineHeight: 15 },
  emptyHelper: { fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic' },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 6,
    borderRadius: 14, borderWidth: 1, borderColor: COLORS.border,
    backgroundColor: '#FAFAFA',
  },
  chipText: { fontSize: 11, color: COLORS.textSecondary },
  rankBadge: { fontSize: 9, color: COLORS.textMuted, fontWeight: '700', marginLeft: 2, opacity: 0.7 },
  pinBadge: { fontSize: 10, marginLeft: 2 },
  selectedHelper: { fontSize: 10, color: COLORS.textMuted, marginTop: 4, fontStyle: 'italic' },
});
