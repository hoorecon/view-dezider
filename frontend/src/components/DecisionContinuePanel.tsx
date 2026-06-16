import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

interface DecisionContinuePanelProps {
  sourceModule: string;
  sourceDecisionId: string;
  title?: string;
  contextSummary?: string;
  /** Optional list of explicit modules to surface; defaults to all 8. */
  modules?: ContinueModuleKey[];
}

export type ContinueModuleKey =
  | 'instant-dezider' | 'my-dezider' | 'pros-cons' | 'solution-finder' | 'swot'
  | 'life-360' | 'gem' | 'goal-setter';

const MODULE_META: Record<ContinueModuleKey, { label: string; icon: any; color: string; route: string }> = {
  'instant-dezider':  { label: 'Instant Dezider', icon: 'flash', color: '#F59E0B', route: '/tools/instant-dezider' },
  'my-dezider':       { label: 'MyDezider',       icon: 'create', color: '#0EA5E9', route: '/tools/my-dezider' },
  'pros-cons':        { label: 'Pros & Cons',     icon: 'git-compare', color: '#6366F1', route: '/tools/pros-cons' },
  'solution-finder':  { label: 'Solution Finder', icon: 'bulb', color: '#A78BFA', route: '/tools/solution-finder' },
  'swot':             { label: 'SWOT Analysis',   icon: 'grid', color: '#EC4899', route: '/tools/swot' },
  'life-360':         { label: 'My Life 360',     icon: 'compass', color: '#10B981', route: '/tools/life-360' },
  'gem':              { label: 'GEM',             icon: 'sparkles', color: '#F97316', route: '/tools/gem' },
  'goal-setter':      { label: 'Goal Setter',     icon: 'rocket', color: '#3B82F6', route: '/tools/goal-setter' },
};

/**
 * Final-step CTA panel: lets the user (or any contributor) continue their work
 * in any other Decision Kickstarter / Life 360 / GEM / Goal Setter module with
 * the current context prefilled. Same target may be opened multiple times.
 */
export const DecisionContinuePanel: React.FC<DecisionContinuePanelProps> = ({
  sourceModule, sourceDecisionId, title, contextSummary, modules,
}) => {
  const router = useRouter();
  const list: ContinueModuleKey[] = modules || [
    'instant-dezider', 'my-dezider', 'pros-cons', 'solution-finder', 'swot',
    'life-360', 'gem', 'goal-setter',
  ];

  const handleOpen = (key: ContinueModuleKey) => {
    const meta = MODULE_META[key];
    const params: Record<string, string> = {
      source_module: sourceModule,
      source_decision_id: sourceDecisionId,
    };
    if (title) params.prefill_title = title;
    if (contextSummary) params.prefill_context = contextSummary;
    const qs = Object.entries(params).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&');
    router.push(`${meta.route}?${qs}` as any);
  };

  return (
    <View style={s.wrap}>
      <View style={s.headerRow}>
        <Ionicons name="arrow-redo" size={18} color="#0F172A" />
        <Text style={s.header}>Continue this decision in another module</Text>
      </View>
      <Text style={s.help}>
        Carry the context forward. The selected module opens with your title &amp;
        summary prefilled — you can open as many as you need.
      </Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 4 }}>
        {list.map(k => {
          const meta = MODULE_META[k];
          return (
            <TouchableOpacity key={k} style={[s.card, { borderColor: meta.color }]} onPress={() => handleOpen(k)}>
              <View style={[s.cardIcon, { backgroundColor: meta.color + '22' }]}>
                <Ionicons name={meta.icon} size={20} color={meta.color} />
              </View>
              <Text style={s.cardLabel} numberOfLines={2}>{meta.label}</Text>
              <Ionicons name="chevron-forward" size={14} color="#94A3B8" />
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
};

const s = StyleSheet.create({
  wrap: { backgroundColor: '#F8FAFC', borderRadius: 14, padding: 14, marginTop: 20, borderWidth: 1, borderColor: '#E2E8F0' },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  header: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  help: { fontSize: 12, color: '#64748B', marginBottom: 10 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FFF', borderWidth: 1, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, minWidth: 170 },
  cardIcon: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  cardLabel: { fontSize: 13, fontWeight: '700', color: '#0F172A', flex: 1 },
});

export default DecisionContinuePanel;
