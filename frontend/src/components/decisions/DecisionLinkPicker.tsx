/**
 * DecisionLinkPicker — modal picker for linking this decision to a prior
 * completed decision (across PRR / Solution Finder / Conflict Breaker).
 *
 * Consumes GET /api/decisions/linkable which returns a unified list.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, Modal, ScrollView, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import api from '../../utils/api';

export interface LinkableDecision {
  decision_id: string;
  module: 'prr' | 'solution_finder' | 'conflict_breaker' | 'solution_matrix';
  title: string;
  selected_option_label?: string | null;
  score_pct?: number | null;
  finalized_at?: string | null;
}

export interface LinkSelection {
  linked_from_decision_id: string;
  linked_from_module: string;
  linked_from_option_label?: string | null;
  linked_from_score_pct?: number | null;
  title?: string;
}

interface Props {
  visible: boolean;
  onClose: () => void;
  onSelect: (sel: LinkSelection) => void;
}

const MODULE_META: Record<string, { label: string; icon: string; color: string; route: string }> = {
  prr:               { label: 'My Dezider',      icon: 'compass',      color: '#7C3AED', route: '/prr' },
  solution_finder:   { label: 'Solution Finder', icon: 'bulb',         color: '#10B981', route: '/tools/solution-finder' },
  conflict_breaker:  { label: 'Conflict Breaker',icon: 'flash',        color: '#F59E0B', route: '/tools/conflict-breaker' },
  solution_matrix:   { label: 'Solution Matrix', icon: 'grid',         color: '#0EA5E9', route: '/tools/solution-matrix' },
};

export default function DecisionLinkPicker({ visible, onClose, onSelect }: Props) {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<LinkableDecision[]>([]);
  const [query, setQuery] = useState('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get('/decision-links/sources');
      setItems(r.data?.items || []);
    } catch {
      setItems([]);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (visible) load(); }, [visible, load]);

  const filtered = items.filter(it =>
    !query || it.title.toLowerCase().includes(query.toLowerCase()) ||
    (it.selected_option_label || '').toLowerCase().includes(query.toLowerCase())
  );

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.head}>
            <Text style={s.title}>Link from a previous decision</Text>
            <TouchableOpacity onPress={onClose} hitSlop={8}><Ionicons name="close" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
          </View>
          <Text style={s.help}>Pick a finalized decision. Its selected option + score% will auto-populate as a factor in this new decision.</Text>

          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search by title or option..."
            placeholderTextColor={COLORS.textMuted}
            style={s.search}
          />

          {loading ? (
            <View style={s.center}><ActivityIndicator color={COLORS.primary} /></View>
          ) : filtered.length === 0 ? (
            <View style={s.center}>
              <Ionicons name="link-outline" size={32} color={COLORS.textMuted} />
              <Text style={s.emptyText}>No finalized decisions yet to link from.</Text>
            </View>
          ) : (
            <ScrollView style={{ maxHeight: 420 }}>
              {filtered.map(it => {
                const meta = MODULE_META[it.module] || MODULE_META.prr;
                return (
                  <TouchableOpacity
                    key={`${it.module}-${it.decision_id}`}
                    style={s.item}
                    onPress={() => {
                      onSelect({
                        linked_from_decision_id: it.decision_id,
                        linked_from_module: it.module,
                        linked_from_option_label: it.selected_option_label || null,
                        linked_from_score_pct: it.score_pct ?? null,
                        title: it.title,
                      });
                      onClose();
                    }}
                    testID={`linkable-${it.module}-${it.decision_id}`}
                  >
                    <View style={[s.itemIcon, { backgroundColor: meta.color + '22' }]}>
                      <Ionicons name={meta.icon as any} size={14} color={meta.color} />
                    </View>
                    <View style={{ flex: 1, minWidth: 0 }}>
                      <Text style={s.itemTitle} numberOfLines={1}>{it.title || '(untitled)'}</Text>
                      <View style={s.itemMeta}>
                        <Text style={[s.modBadge, { color: meta.color }]}>{meta.label}</Text>
                        {it.selected_option_label ? <Text style={s.optTxt}>· {it.selected_option_label}</Text> : null}
                        {typeof it.score_pct === 'number' ? <Text style={s.scoreTxt}>· {Math.round(it.score_pct)}%</Text> : null}
                      </View>
                    </View>
                    <Ionicons name="chevron-forward" size={14} color={COLORS.textMuted} />
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '85%' },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  title: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  help: { fontSize: 11, color: COLORS.textMuted, marginTop: 4, marginBottom: 10, lineHeight: 16 },
  search: { backgroundColor: '#F9FAFB', borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 9, fontSize: 13, marginBottom: 8 },
  center: { alignItems: 'center', padding: 30 },
  emptyText: { fontSize: 12, color: COLORS.textMuted, marginTop: 8 },
  item: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  itemIcon: { width: 28, height: 28, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  itemTitle: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  itemMeta: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', marginTop: 2 },
  modBadge: { fontSize: 10, fontWeight: '700' },
  optTxt: { fontSize: 10, color: COLORS.textSecondary, marginLeft: 4 },
  scoreTxt: { fontSize: 10, fontWeight: '700', color: COLORS.primary, marginLeft: 4 },
});
