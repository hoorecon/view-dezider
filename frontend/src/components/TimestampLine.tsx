/**
 * TimestampLine — one-line "Created/Updated · 2h ago · 5 Jun, 06:51 PM"
 * Drops into any list card.
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { bestTimestamp, formatAbsolute, formatRelative } from '../utils/datetime';

interface Props {
  /** Either pass `entity` (we'll pick the best timestamp) … */
  entity?: any;
  /** … or pass explicit values directly. */
  createdAt?: any;
  updatedAt?: any;
  /** When true (default), shows both relative + absolute. */
  showAbsolute?: boolean;
  /** Compact variant — smaller font, no icon. */
  compact?: boolean;
  /** Override colour. */
  color?: string;
}

export default function TimestampLine({
  entity, createdAt, updatedAt,
  showAbsolute = true, compact = false, color,
}: Props) {
  let ts: any = null;
  let label: 'updated' | 'created' | null = null;
  if (entity) {
    const r = bestTimestamp(entity);
    ts = r.ts; label = r.label;
  } else if (updatedAt || createdAt) {
    if (updatedAt && createdAt) {
      const ud = new Date(updatedAt).getTime();
      const cd = new Date(createdAt).getTime();
      if (ud - cd > 60_000) { ts = updatedAt; label = 'updated'; }
      else { ts = createdAt; label = 'created'; }
    } else if (createdAt) { ts = createdAt; label = 'created'; }
    else { ts = updatedAt; label = 'updated'; }
  }
  if (!ts) return null;

  const rel = formatRelative(ts);
  const abs = formatAbsolute(ts);
  const c = color || '#64748B';
  const txt = label === 'updated' ? 'Updated' : 'Created';

  return (
    <View style={[s.row, compact && { marginTop: 2 }]}>
      {!compact && (
        <Ionicons name={label === 'updated' ? 'refresh' : 'time-outline'} size={10} color={c} />
      )}
      <Text style={[s.text, compact && s.compactText, { color: c }]} numberOfLines={1}>
        {txt} · {rel}
        {showAbsolute && rel !== abs ? ` · ${abs}` : ''}
      </Text>
    </View>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  text: { fontSize: 10, fontWeight: '500' },
  compactText: { fontSize: 9 },
});
