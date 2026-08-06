/**
 * FactorGroups — small utility for grouping factors by their `group_path`
 * (nested up to 3 levels) and rendering collapsible section headers.
 *
 * Used by Step 2 (Define Factors) and Step 7 (Assessment).
 * Steps 3/4/5/6 treat factors as a flat list and do NOT call this module.
 */
import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';

export interface GroupableFactor {
  id: string;
  name: string;
  parent_id?: string;
  group_path?: string[];
  order?: number;
}

interface GroupNode<F extends GroupableFactor> {
  key: string;
  label: string;
  depth: number;   // 0 = root, 1 = sub, 2 = sub-sub
  factors: F[];    // factors that terminate exactly at this depth
  children: GroupNode<F>[];
}

/** Build a nested tree of groups from an array of factors. Groups are
 *  discovered from `group_path[]` (up to 3 levels). Factors with no
 *  group_path are put in the sentinel "" root under `ungrouped`. */
export function buildFactorTree<F extends GroupableFactor>(factors: F[]): {
  groups: GroupNode<F>[];
  ungrouped: F[];
} {
  const groups: GroupNode<F>[] = [];
  const ungrouped: F[] = [];
  const findOrCreate = (parent: GroupNode<F>[], label: string, depth: number, key: string): GroupNode<F> => {
    let n = parent.find((g) => g.label === label);
    if (!n) {
      n = { key, label, depth, factors: [], children: [] };
      parent.push(n);
    }
    return n;
  };
  for (const f of factors) {
    const gp = f.group_path || [];
    if (!gp.length) { ungrouped.push(f); continue; }
    // Walk the path up to 3 levels.
    let cursor: GroupNode<F>[] = groups;
    let node: GroupNode<F> | null = null;
    for (let i = 0; i < Math.min(gp.length, 3); i++) {
      const key = gp.slice(0, i + 1).join(' › ');
      node = findOrCreate(cursor, gp[i], i, key);
      cursor = node.children;
    }
    if (node) node.factors.push(f);
    else ungrouped.push(f);
  }
  return { groups, ungrouped };
}

/** Recursively render a factor tree with expand/collapse.
 *
 *  Caller supplies:
 *    - `renderFactor(factor)`: React node for one factor row
 *    - `initialCollapsed?`: default state (default expanded)
 */
export function FactorTreeSections<F extends GroupableFactor>({
  factors,
  renderFactor,
  initialCollapsed = false,
  testIdPrefix = 'fg',
}: {
  factors: F[];
  renderFactor: (f: F) => React.ReactNode;
  initialCollapsed?: boolean;
  testIdPrefix?: string;
}) {
  const { groups, ungrouped } = buildFactorTree(factors);
  if (!groups.length) return <>{factors.map((f) => renderFactor(f))}</>;
  return (
    <>
      {groups.map((g) => (
        <GroupSection key={g.key} node={g} renderFactor={renderFactor} initialCollapsed={initialCollapsed} testIdPrefix={testIdPrefix} />
      ))}
      {ungrouped.length > 0 && (
        <GroupSection
          key="__ungrouped__"
          node={{ key: '__ungrouped__', label: 'Ungrouped', depth: 0, factors: ungrouped, children: [] }}
          renderFactor={renderFactor}
          initialCollapsed={initialCollapsed}
          testIdPrefix={testIdPrefix}
          softHeader
        />
      )}
    </>
  );
}

function GroupSection<F extends GroupableFactor>({
  node, renderFactor, initialCollapsed, testIdPrefix, softHeader,
}: {
  node: GroupNode<F>;
  renderFactor: (f: F) => React.ReactNode;
  initialCollapsed: boolean;
  testIdPrefix: string;
  softHeader?: boolean;
}) {
  const [open, setOpen] = useState(!initialCollapsed);
  const depthStyle = [styles.header, node.depth === 1 && styles.headerL1, node.depth === 2 && styles.headerL2, softHeader && styles.headerSoft];
  const count = countLeafFactors(node);
  return (
    <View style={{ marginBottom: 8 }}>
      <TouchableOpacity
        onPress={() => setOpen(!open)}
        style={depthStyle}
        testID={`${testIdPrefix}-toggle-${node.key}`}
        accessibilityLabel={`Toggle group ${node.label}`}
      >
        <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={16} color={softHeader ? '#94A3B8' : COLORS.primary} />
        <Text style={[styles.headerText, softHeader && styles.headerTextSoft]} numberOfLines={1}>
          {node.label}
        </Text>
        <View style={[styles.countPill, softHeader && styles.countPillSoft]}>
          <Text style={[styles.countText, softHeader && styles.countTextSoft]}>{count}</Text>
        </View>
      </TouchableOpacity>
      {open && (
        <View style={[styles.body, node.depth > 0 && { paddingLeft: 12 }]}>
          {node.children.map((c) => (
            <GroupSection key={c.key} node={c} renderFactor={renderFactor} initialCollapsed={initialCollapsed} testIdPrefix={testIdPrefix} />
          ))}
          {node.factors.map((f) => renderFactor(f))}
        </View>
      )}
    </View>
  );
}

function countLeafFactors<F extends GroupableFactor>(n: GroupNode<F>): number {
  let s = n.factors.length;
  for (const c of n.children) s += countLeafFactors(c);
  return s;
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 12, paddingVertical: 10,
    backgroundColor: '#EEF2FF', borderRadius: 10,
    borderLeftWidth: 3, borderLeftColor: COLORS.primary,
    marginBottom: 4,
  },
  headerL1: { backgroundColor: '#F5F3FF', borderLeftColor: '#8B5CF6' },
  headerL2: { backgroundColor: '#FAF5FF', borderLeftColor: '#C084FC' },
  headerSoft: { backgroundColor: '#F8FAFC', borderLeftColor: '#CBD5E1' },
  headerText: { flex: 1, fontSize: 13.5, fontWeight: '800', color: COLORS.primary },
  headerTextSoft: { color: '#64748B' },
  countPill: { backgroundColor: '#FFF', borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2, borderWidth: 1, borderColor: '#C7D2FE' },
  countPillSoft: { borderColor: '#E2E8F0' },
  countText: { fontSize: 11, fontWeight: '700', color: COLORS.primary },
  countTextSoft: { color: '#64748B' },
  body: { marginTop: 2 },
});
