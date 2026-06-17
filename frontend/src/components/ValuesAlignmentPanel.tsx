/**
 * ValuesAlignmentPanel
 * Inline panel for Decision Kickstarters (esp. Solution Finder) to record which
 * Values are APPLIED vs VIOLATED. Violation requires a reason.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, TextInput, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../utils/api';

interface Item { principle_id: string; principle_name: string; reason?: string; }
interface Props {
  values_applied: Item[];
  values_violated: Item[];
  onChange: (next: { values_applied: Item[]; values_violated: Item[] }) => void;
  compact?: boolean;
}

export default function ValuesAlignmentPanel({ values_applied = [], values_violated = [], onChange, compact = false }: Props) {
  const [principles, setPrinciples] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState(!compact);
  const [violReason, setViolReason] = useState<Record<string, string>>({});

  useEffect(() => {
    (async () => {
      setBusy(true);
      try { const { data } = await api.get('/values/principles'); setPrinciples(data?.principles || []); }
      finally { setBusy(false); }
    })();
  }, []);

  const isApplied = (id: string) => values_applied.some(v => v.principle_id === id);
  const isViolated = (id: string) => values_violated.some(v => v.principle_id === id);

  const toggleApplied = (p: any) => {
    if (isViolated(p.id)) return; // mutually exclusive
    const next = isApplied(p.id)
      ? values_applied.filter(v => v.principle_id !== p.id)
      : [...values_applied, { principle_id: p.id, principle_name: p.name }];
    onChange({ values_applied: next, values_violated });
  };

  const toggleViolated = (p: any) => {
    if (isApplied(p.id)) return; // mutually exclusive
    if (isViolated(p.id)) {
      onChange({ values_applied, values_violated: values_violated.filter(v => v.principle_id !== p.id) });
      return;
    }
    const reason = (violReason[p.id] || '').trim();
    if (!reason) {
      // require reason — open the inline reason field
      setViolReason(r => ({ ...r, [p.id]: '' }));
      return;
    }
    onChange({ values_applied, values_violated: [...values_violated, { principle_id: p.id, principle_name: p.name, reason }] });
  };

  const updReason = (pid: string, txt: string) => setViolReason(r => ({ ...r, [pid]: txt }));

  const appliedCount = values_applied.length;
  const violatedCount = values_violated.length;

  return (
    <View style={s.wrap}>
      <TouchableOpacity style={s.headerRow} onPress={() => setExpanded(e => !e)}>
        <Ionicons name="shield-checkmark" size={16} color="#003087" />
        <Text style={s.title}>Values Alignment</Text>
        <View style={s.countsRow}>
          <View style={[s.countPill, { backgroundColor: '#DCFCE7' }]}><Ionicons name="checkmark" size={10} color="#166534" /><Text style={[s.countPillText, { color: '#166534' }]}>{appliedCount} applied</Text></View>
          <View style={[s.countPill, { backgroundColor: '#FEE2E2' }]}><Ionicons name="warning" size={10} color="#991B1B" /><Text style={[s.countPillText, { color: '#991B1B' }]}>{violatedCount} violated</Text></View>
        </View>
        <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={16} color="#64748B" />
      </TouchableOpacity>

      {expanded && (busy ? <ActivityIndicator /> : (
        <ScrollView style={{ maxHeight: 320 }}>
          {principles.map((p) => {
            const a = isApplied(p.id), v = isViolated(p.id);
            const showReason = !v && (p.id in violReason);
            return (
              <View key={p.id} style={s.principleRow}>
                <View style={{ flex: 1 }}>
                  <Text style={s.pName}>{p.order}. {p.name}</Text>
                  {p.short ? <Text style={s.pShort}>{p.short}</Text> : null}
                  {showReason && (
                    <View style={{ marginTop: 6 }}>
                      <Text style={s.reasonLbl}>Reason for violation (required) *</Text>
                      <TextInput style={s.reasonInp} value={violReason[p.id] || ''} onChangeText={(v2) => updReason(p.id, v2)} placeholder="Why is this being violated?" placeholderTextColor="#94A3B8" multiline />
                      <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
                        <TouchableOpacity style={s.confirmViol} onPress={() => toggleViolated(p)}><Text style={s.confirmViolText}>Confirm Violation</Text></TouchableOpacity>
                        <TouchableOpacity style={s.cancelViol} onPress={() => { setViolReason(r => { const c = { ...r }; delete c[p.id]; return c; }); }}><Text style={s.cancelViolText}>Cancel</Text></TouchableOpacity>
                      </View>
                    </View>
                  )}
                </View>
                <View style={{ flexDirection: 'row', gap: 4 }}>
                  <TouchableOpacity style={[s.actBtn, a && { backgroundColor: '#10B981', borderColor: '#10B981' }]} onPress={() => toggleApplied(p)} disabled={v}>
                    <Ionicons name="checkmark" size={12} color={a ? '#FFF' : '#10B981'} />
                  </TouchableOpacity>
                  <TouchableOpacity style={[s.actBtn, v && { backgroundColor: '#EF4444', borderColor: '#EF4444' }]} onPress={() => toggleViolated(p)} disabled={a}>
                    <Ionicons name="warning" size={12} color={v ? '#FFF' : '#EF4444'} />
                  </TouchableOpacity>
                </View>
              </View>
            );
          })}
          {principles.length === 0 && <Text style={{ color: '#64748B', fontSize: 11, padding: 8, fontStyle: 'italic' }}>No principles configured.</Text>}
        </ScrollView>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { backgroundColor: '#FFF', borderRadius: 12, borderWidth: 1, borderColor: '#E2E8F0', overflow: 'hidden' },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12 },
  title: { flex: 1, fontSize: 13, fontWeight: '800', color: '#003087' },
  countsRow: { flexDirection: 'row', gap: 4 },
  countPill: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  countPillText: { fontSize: 10, fontWeight: '800' },
  principleRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, paddingHorizontal: 12, paddingVertical: 8, borderTopWidth: 1, borderColor: '#F1F5F9' },
  pName: { fontSize: 12, fontWeight: '700', color: '#0F172A' },
  pShort: { fontSize: 11, color: '#64748B', marginTop: 1 },
  actBtn: { width: 28, height: 28, borderRadius: 14, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFF', borderColor: '#CBD5E1' },
  reasonLbl: { fontSize: 10, fontWeight: '700', color: '#991B1B', marginBottom: 4 },
  reasonInp: { backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA', borderRadius: 6, padding: 6, fontSize: 11, color: '#0F172A', minHeight: 40, textAlignVertical: 'top' },
  confirmViol: { flex: 1, backgroundColor: '#EF4444', borderRadius: 6, padding: 6, alignItems: 'center' },
  confirmViolText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
  cancelViol: { flex: 1, backgroundColor: '#F1F5F9', borderRadius: 6, padding: 6, alignItems: 'center' },
  cancelViolText: { color: '#475569', fontSize: 11, fontWeight: '700' },
});
