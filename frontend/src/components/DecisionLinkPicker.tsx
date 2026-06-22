import React, { useEffect, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, Modal, ScrollView,
  ActivityIndicator, StyleSheet, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import { useDecision } from '../context/DecisionContext';
import api from '../utils/api';
import { showAlert } from '../utils/alert';

type LinkableOption = { id: string; name: string; worth_percentage: number };
type LinkableDecision = {
  id: string; title: string; life_area?: string; module: string;
  options: LinkableOption[]; top_option_id: string | null;
};

type Props = { visible: boolean; onClose: () => void };

/**
 * "Link a Decision" picker — bring another SCORED decision's option result into
 * this decision as a factor (and optionally an option). Two-pane flow:
 *  1) pick a target decision   2) configure option / metric / mode / refresh.
 */
export default function DecisionLinkPicker({ visible, onClose }: Props) {
  const { decision, fetchDecision } = useDecision();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [list, setList] = useState<LinkableDecision[]>([]);
  const [search, setSearch] = useState('');
  const [picked, setPicked] = useState<LinkableDecision | null>(null);

  // config state (pane 2)
  const [optionId, setOptionId] = useState<string | null>(null);
  const [metric, setMetric] = useState<'option_worth' | 'top_score'>('option_worth');
  const [linkMode, setLinkMode] = useState<'factor_only' | 'factor_and_option'>('factor_only');
  const [refresh, setRefresh] = useState<'auto' | 'manual'>('auto');
  const [factorName, setFactorName] = useState('');

  useEffect(() => {
    if (!visible) return;
    setPicked(null); setSearch('');
    setLoading(true);
    api.get(`/decisions/${decision.id}/linkable`)
      .then((r) => setList(r.data?.decisions || []))
      .catch(() => setList([]))
      .finally(() => setLoading(false));
  }, [visible, decision.id]);

  const choose = (d: LinkableDecision) => {
    setPicked(d);
    const top = d.options.find((o) => o.id === d.top_option_id) || d.options[0];
    setOptionId(top?.id || null);
    setMetric('option_worth');
    setLinkMode('factor_only');
    setRefresh('auto');
    setFactorName(top?.name || d.title);
  };

  // keep factor-name in sync with the chosen option (until user edits it)
  const selectOption = (o: LinkableOption) => {
    setOptionId(o.id);
    setFactorName((prev) => {
      const prevOpt = picked?.options.find((x) => x.name === prev);
      return prevOpt || !prev ? o.name : prev;
    });
  };

  const confirm = async () => {
    if (!picked || saving) return;
    if (metric === 'option_worth' && !optionId) {
      showAlert('Pick an option', 'Choose which option from the linked decision to use.');
      return;
    }
    setSaving(true);
    try {
      await api.post(`/decisions/${decision.id}/link-decision`, {
        linked_decision_id: picked.id,
        linked_module: picked.module,
        linked_option_id: optionId,
        metric, refresh, link_mode: linkMode,
        factor_name: factorName.trim() || undefined,
      });
      await fetchDecision();
      onClose();
    } catch (e: any) {
      const code = e?.response?.status;
      const msg = e?.response?.data?.detail
        || (code === 409 ? 'That would create a circular dependency.' : 'Could not link the decision.');
      showAlert(code === 409 ? 'Circular dependency' : 'Link failed', msg);
    } finally {
      setSaving(false);
    }
  };

  const filtered = list.filter((d) =>
    d.title.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.card} testID="decision-link-picker">
          {/* Header */}
          <View style={s.header}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 }}>
              {picked && (
                <TouchableOpacity onPress={() => setPicked(null)} testID="dlp-back" hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                  <Ionicons name="chevron-back" size={22} color={COLORS.text} />
                </TouchableOpacity>
              )}
              <Ionicons name="git-network-outline" size={18} color={COLORS.primary} />
              <Text style={s.title} numberOfLines={1}>
                {picked ? 'Configure dependency' : 'Link a Decision'}
              </Text>
            </View>
            <TouchableOpacity onPress={onClose} testID="dlp-close" hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close" size={22} color={COLORS.textMuted} />
            </TouchableOpacity>
          </View>

          {/* PANE 1 — pick a decision */}
          {!picked && (
            <>
              <TextInput
                style={s.searchInput}
                placeholder="Search your decisions…"
                placeholderTextColor={COLORS.textMuted}
                value={search}
                onChangeText={setSearch}
                testID="dlp-search"
              />
              {loading ? (
                <ActivityIndicator color={COLORS.primary} style={{ marginVertical: 30 }} />
              ) : filtered.length === 0 ? (
                <View style={s.empty}>
                  <Ionicons name="information-circle-outline" size={26} color={COLORS.textMuted} />
                  <Text style={s.emptyText}>
                    No scored decisions to link yet. Complete another decision's assessment (Steps 7–8) first.
                  </Text>
                </View>
              ) : (
                <ScrollView style={{ maxHeight: 320 }} keyboardShouldPersistTaps="handled">
                  {filtered.map((d) => {
                    const top = d.options.find((o) => o.id === d.top_option_id) || d.options[0];
                    return (
                      <TouchableOpacity key={d.id} style={s.row} onPress={() => choose(d)} testID={`dlp-decision-${d.id}`}>
                        <View style={{ flex: 1 }}>
                          <Text style={s.rowTitle} numberOfLines={1}>{d.title}</Text>
                          <Text style={s.rowSub} numberOfLines={1}>
                            {d.life_area ? `${d.life_area} · ` : ''}{d.options.length} option{d.options.length === 1 ? '' : 's'}
                            {top ? ` · top ${top.name} (${top.worth_percentage}%)` : ''}
                          </Text>
                        </View>
                        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              )}
            </>
          )}

          {/* PANE 2 — configure */}
          {picked && (
            <ScrollView style={{ maxHeight: 440 }} keyboardShouldPersistTaps="handled">
              <Text style={s.pickedTitle} numberOfLines={2}>{picked.title}</Text>

              {/* Metric */}
              <Text style={s.label}>Value to bring in</Text>
              <View style={s.segment}>
                {([['option_worth', 'A chosen option %'], ['top_score', 'Top option %']] as const).map(([k, lbl]) => (
                  <TouchableOpacity
                    key={k}
                    style={[s.segBtn, metric === k && s.segBtnActive]}
                    onPress={() => setMetric(k)}
                    testID={`dlp-metric-${k}`}
                  >
                    <Text style={[s.segText, metric === k && s.segTextActive]}>{lbl}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              {/* Option chooser (only when option_worth) */}
              {metric === 'option_worth' && (
                <>
                  <Text style={s.label}>Pick the option (its overall % becomes the factor value)</Text>
                  {picked.options.map((o) => (
                    <TouchableOpacity key={o.id} style={s.optRow} onPress={() => selectOption(o)} testID={`dlp-option-${o.id}`}>
                      <Ionicons
                        name={optionId === o.id ? 'radio-button-on' : 'radio-button-off'}
                        size={20} color={optionId === o.id ? COLORS.primary : COLORS.textMuted}
                      />
                      <Text style={s.optName} numberOfLines={1}>{o.name}</Text>
                      <Text style={s.optPct}>{o.worth_percentage}%</Text>
                    </TouchableOpacity>
                  ))}
                </>
              )}

              {/* Factor name */}
              <Text style={s.label}>Factor name</Text>
              <TextInput
                style={s.searchInput}
                value={factorName}
                onChangeText={setFactorName}
                placeholder="Factor name"
                placeholderTextColor={COLORS.textMuted}
                testID="dlp-factor-name"
              />

              {/* Link mode */}
              <Text style={s.label}>What to add</Text>
              <View style={s.segment}>
                {([['factor_only', 'Only factor'], ['factor_and_option', 'Factor & option']] as const).map(([k, lbl]) => (
                  <TouchableOpacity
                    key={k}
                    style={[s.segBtn, linkMode === k && s.segBtnActive]}
                    onPress={() => setLinkMode(k)}
                    testID={`dlp-mode-${k}`}
                  >
                    <Text style={[s.segText, linkMode === k && s.segTextActive]}>{lbl}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={s.hint}>
                {linkMode === 'factor_only'
                  ? 'Adds a factor (Step 2) with the option % as its expected value.'
                  : 'Also adds an option (Step 6) with its Step-7 cell pre-filled to the %.'}
              </Text>

              {/* Refresh */}
              <Text style={s.label}>Keep value updated</Text>
              <View style={s.segment}>
                {([['auto', 'Automatic'], ['manual', 'Manual']] as const).map(([k, lbl]) => (
                  <TouchableOpacity
                    key={k}
                    style={[s.segBtn, refresh === k && s.segBtnActive]}
                    onPress={() => setRefresh(k)}
                    testID={`dlp-refresh-${k}`}
                  >
                    <Text style={[s.segText, refresh === k && s.segTextActive]}>{lbl}</Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Text style={s.hint}>
                {refresh === 'auto'
                  ? 'Re-pulls the latest value whenever you open this decision.'
                  : 'Stays fixed until you tap the refresh icon on the factor.'}
              </Text>

              <TouchableOpacity style={[s.confirm, saving && { opacity: 0.7 }]} onPress={confirm} disabled={saving} testID="dlp-confirm">
                {saving ? <ActivityIndicator size="small" color="#FFF" /> : <Ionicons name="git-network" size={18} color="#FFF" />}
                <Text style={s.confirmText}>{saving ? 'Linking…' : 'Link decision'}</Text>
              </TouchableOpacity>
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  card: { width: '100%', maxWidth: 460, backgroundColor: COLORS.card || '#FFF', borderRadius: 16, padding: 16,
    ...Platform.select({ web: { maxHeight: '88vh' as any } }) },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, gap: 8 },
  title: { fontSize: 16, fontWeight: '800', color: COLORS.text, flexShrink: 1 },
  searchInput: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10,
    fontSize: 14, color: COLORS.text, marginBottom: 10, backgroundColor: COLORS.background },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: COLORS.border, gap: 8 },
  rowTitle: { fontSize: 14.5, fontWeight: '700', color: COLORS.text },
  rowSub: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  empty: { alignItems: 'center', paddingVertical: 28, gap: 8 },
  emptyText: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', lineHeight: 18, paddingHorizontal: 10 },
  pickedTitle: { fontSize: 15, fontWeight: '800', color: COLORS.text, marginBottom: 6 },
  label: { fontSize: 12.5, fontWeight: '700', color: COLORS.text, marginTop: 14, marginBottom: 6 },
  hint: { fontSize: 11.5, color: COLORS.textMuted, marginTop: 6, lineHeight: 16 },
  segment: { flexDirection: 'row', gap: 8 },
  segBtn: { flex: 1, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center', backgroundColor: COLORS.background },
  segBtnActive: { borderColor: COLORS.primary, backgroundColor: '#F5F3FF' },
  segText: { fontSize: 13, fontWeight: '700', color: COLORS.textMuted },
  segTextActive: { color: COLORS.primary },
  optRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9 },
  optName: { flex: 1, fontSize: 14, color: COLORS.text },
  optPct: { fontSize: 13, fontWeight: '800', color: COLORS.primary },
  confirm: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary,
    borderRadius: 12, paddingVertical: 13, marginTop: 18 },
  confirmText: { color: '#FFF', fontSize: 15, fontWeight: '800' },
});
