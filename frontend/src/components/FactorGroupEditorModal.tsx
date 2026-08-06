/**
 * FactorGroupEditorModal
 * ─────────────────────────────────────────────────────────────────────────
 * Compact editor for a single Factor's nested group path (max 3 levels).
 *
 *   group_path = ["Cash Transactions", "Cash Deposit"]
 *
 * Used in Step 2 (Define Factors) and Step 7 (Assessment) so users can bucket
 * factors under collapsible sections. Suggestions are pooled from any factor
 * already carrying a group_path — so once a group exists, other factors can
 * be dropped into it with a single tap.
 */
import React, { useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, TextInput, TouchableOpacity, Modal, ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';

interface Factor {
  id: string;
  name: string;
  group_path?: string[];
}

interface Props {
  visible: boolean;
  factor: Factor | null;
  allFactors: Factor[];
  onClose: () => void;
  onSave: (factorId: string, groupPath: string[]) => void;
}

const MAX_LEVELS = 3;

/** Return distinct existing group paths (level=0..2). */
function collectSuggestions(factors: Factor[], level: number, parentPath: string[]): string[] {
  const set = new Set<string>();
  for (const f of factors) {
    const gp = f.group_path || [];
    if (gp.length <= level) continue;
    // Must share the parent prefix.
    let ok = true;
    for (let i = 0; i < parentPath.length; i++) {
      if (gp[i] !== parentPath[i]) { ok = false; break; }
    }
    if (!ok) continue;
    if (gp[level]) set.add(gp[level]);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

export default function FactorGroupEditorModal({ visible, factor, allFactors, onClose, onSave }: Props) {
  const [path, setPath] = useState<string[]>(factor?.group_path || []);
  const [drafts, setDrafts] = useState<string[]>(['', '', '']);

  React.useEffect(() => {
    setPath(factor?.group_path || []);
    setDrafts(['', '', '']);
  }, [factor?.id, visible]);

  const suggestionsPerLevel = useMemo(() => {
    return [0, 1, 2].map((lvl) => collectSuggestions(allFactors, lvl, path.slice(0, lvl)));
  }, [allFactors, path]);

  const setLevel = (lvl: number, value: string) => {
    const next = path.slice(0, lvl);
    if (value) next.push(value);
    setPath(next);
  };
  const commitDraft = (lvl: number) => {
    const v = drafts[lvl].trim();
    if (!v) return;
    setLevel(lvl, v);
    const nd = [...drafts]; nd[lvl] = ''; setDrafts(nd);
  };

  if (!factor) return null;
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.card}>
          <View style={s.head}>
            <Text style={s.title}>Group “{factor.name}”</Text>
            <TouchableOpacity onPress={onClose}><Ionicons name="close" size={22} color="#64748B" /></TouchableOpacity>
          </View>
          <Text style={s.help}>Nest this factor under up to {MAX_LEVELS} levels of groups. Leave blank to keep it un-grouped.</Text>

          <View style={s.pathRow}>
            <Text style={s.pathLabel}>Path</Text>
            <Text style={s.pathValue}>{path.length ? path.join(' › ') : '(un-grouped)'}</Text>
            {path.length > 0 && (
              <TouchableOpacity onPress={() => setPath([])} style={s.clearBtn} testID="fg-clear">
                <Ionicons name="close-circle" size={16} color="#DC2626" />
                <Text style={s.clearText}>Clear</Text>
              </TouchableOpacity>
            )}
          </View>

          <ScrollView style={{ maxHeight: 420 }} contentContainerStyle={{ paddingBottom: 12 }}>
            {[0, 1, 2].map((lvl) => {
              const parent = path.slice(0, lvl);
              const canEdit = lvl === 0 || path.length >= lvl;
              if (!canEdit) return null;
              return (
                <View key={lvl} style={s.levelBox}>
                  <Text style={s.levelHead}>Level {lvl + 1}{lvl === 0 ? ' (root group)' : parent.length ? ` — inside “${parent[parent.length - 1]}”` : ''}</Text>
                  <View style={s.chipRow}>
                    {suggestionsPerLevel[lvl].map((g) => (
                      <TouchableOpacity
                        key={g}
                        style={[s.chip, path[lvl] === g && s.chipOn]}
                        onPress={() => setLevel(lvl, g)}
                        testID={`fg-suggest-${lvl}-${g}`}
                      >
                        <Text style={[s.chipText, path[lvl] === g && s.chipTextOn]}>{g}</Text>
                      </TouchableOpacity>
                    ))}
                    {path[lvl] && !suggestionsPerLevel[lvl].includes(path[lvl]) && (
                      <View style={[s.chip, s.chipOn]}>
                        <Text style={[s.chipText, s.chipTextOn]}>{path[lvl]}</Text>
                      </View>
                    )}
                  </View>
                  <View style={s.newRow}>
                    <TextInput
                      style={s.input}
                      placeholder="Or type a new group name…"
                      placeholderTextColor="#9CA3AF"
                      value={drafts[lvl]}
                      onChangeText={(v) => { const nd = [...drafts]; nd[lvl] = v; setDrafts(nd); }}
                      onSubmitEditing={() => commitDraft(lvl)}
                      testID={`fg-new-${lvl}`}
                    />
                    <TouchableOpacity style={s.addBtn} onPress={() => commitDraft(lvl)}>
                      <Ionicons name="add" size={16} color="#FFF" />
                    </TouchableOpacity>
                  </View>
                </View>
              );
            })}
          </ScrollView>

          <View style={s.btnRow}>
            <TouchableOpacity style={s.cancel} onPress={onClose}><Text style={s.cancelText}>Cancel</Text></TouchableOpacity>
            <TouchableOpacity
              style={s.save}
              onPress={() => { onSave(factor.id, path); onClose(); }}
              testID="fg-save"
            >
              <Text style={s.saveText}>Save</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  card: { backgroundColor: '#FFF', borderRadius: 16, padding: 16, width: '100%', maxWidth: 520 },
  head: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  title: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary, flex: 1 },
  help: { fontSize: 12.5, color: COLORS.textSecondary, marginBottom: 12, lineHeight: 17 },
  pathRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F1F5F9', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, marginBottom: 12 },
  pathLabel: { fontSize: 12, fontWeight: '700', color: '#64748B' },
  pathValue: { flex: 1, fontSize: 13, color: '#0F172A', fontWeight: '600' },
  clearBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  clearText: { fontSize: 12, color: '#DC2626', fontWeight: '700' },
  levelBox: { marginBottom: 12, paddingBottom: 10, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  levelHead: { fontSize: 12, fontWeight: '700', color: COLORS.primary, marginBottom: 6 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 6 },
  chip: { backgroundColor: '#EEF2FF', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6, borderWidth: 1, borderColor: '#C7D2FE' },
  chipOn: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  chipText: { fontSize: 12, color: '#4F46E5', fontWeight: '600' },
  chipTextOn: { color: '#FFF' },
  newRow: { flexDirection: 'row', gap: 6, alignItems: 'center' },
  input: { flex: 1, backgroundColor: '#F8FAFC', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: '#0F172A', borderWidth: 1, borderColor: '#E2E8F0' },
  addBtn: { backgroundColor: COLORS.primary, borderRadius: 8, padding: 8 },
  btnRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  cancel: { flex: 1, backgroundColor: '#F1F5F9', paddingVertical: 12, borderRadius: 10, alignItems: 'center' },
  cancelText: { fontSize: 14, color: '#475569', fontWeight: '700' },
  save: { flex: 1, backgroundColor: COLORS.primary, paddingVertical: 12, borderRadius: 10, alignItems: 'center' },
  saveText: { fontSize: 14, color: '#FFF', fontWeight: '800' },
});
