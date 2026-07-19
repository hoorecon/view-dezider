import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { useDecision } from '../../context/DecisionContext';
import type { Factor } from '../../types/decision';
import { NUMERIC_OPERATORS } from '../../utils/decisionHelpers';

/**
 * Dynamic UI-object renderer for a "value-mode" main factor (template v2).
 *
 * • checkbox / listbox → multi-select of the factor's VALUE children
 * • radio / dropdown   → single-select
 * A ticked value reveals an optional "Suitability ≥ X%" refiner (pre-filled
 * from the template's Default Operator / Default Expected, user-overridable).
 * DEPENDENT children appear only when their linked value is ticked.
 * No 100% split rule applies here.
 */
interface Props {
  factor: Factor;
  subs: Factor[];
  configMode: boolean;
  renderCriteria: (factor: Factor, indent?: boolean) => React.ReactNode;
}

const isSelected = (f: Factor) =>
  f.expected_value !== undefined && f.expected_value !== null && String(f.expected_value).trim() !== '';

const defExpected = (f: Factor): number => {
  const n = parseFloat(String(f.default_expected ?? ''));
  return Number.isFinite(n) ? n : 1; // no default → "any suitability" (≥ 1%)
};

export default function FactorValueUI({ factor, subs, configMode, renderCriteria }: Props) {
  const { decision, saveDecision, updateFactor, removeFactor } = useDecision();
  const [expDrafts, setExpDrafts] = useState<{ [id: string]: string }>({});
  const [newValueName, setNewValueName] = useState('');
  const [ddOpen, setDdOpen] = useState(false);

  const valueSubs = subs.filter((s) => s.role === 'value');
  const depSubs = subs.filter((s) => s.role === 'dependent');
  const otherSubs = subs.filter((s) => s.role !== 'value' && s.role !== 'dependent');
  const multi = factor.ui_object === 'checkbox' || factor.ui_object === 'listbox';
  const selected = valueSubs.filter(isSelected);
  const selectedNames = selected.map((s) => s.name.trim().toLowerCase());

  const selectValue = (sub: Factor) => {
    updateFactor(sub.id, {
      expected_value: defExpected(sub),
      operator: sub.default_operator || '>=',
      data_type: 'numeric',
      unit: sub.unit || '%',
    });
  };

  const clearFactorIds = (ids: string[], factors: Factor[]) =>
    factors.map((f) => (ids.includes(f.id)
      ? { ...f, expected_value: undefined, operator: undefined }
      : f));

  const deselectValue = (sub: Factor) => {
    // Also clear dependents revealed by this value.
    const depIds = depSubs
      .filter((d) => (d.linked_value || '').trim().toLowerCase() === sub.name.trim().toLowerCase())
      .map((d) => d.id);
    saveDecision({ factors: clearFactorIds([sub.id, ...depIds], decision!.factors) });
  };

  const pickSingle = (sub: Factor) => {
    // radio/dropdown: clear all sibling values (+ their dependents), set this one
    const otherIds = valueSubs.filter((v) => v.id !== sub.id).map((v) => v.id);
    const depIds = depSubs
      .filter((d) => d.linked_value && d.linked_value.trim().toLowerCase() !== sub.name.trim().toLowerCase())
      .map((d) => d.id);
    const factors = clearFactorIds([...otherIds, ...depIds], decision!.factors).map((f) =>
      f.id === sub.id
        ? { ...f, expected_value: defExpected(sub), operator: sub.default_operator || '>=', data_type: 'numeric' as const, unit: sub.unit || '%' }
        : f);
    saveDecision({ factors });
    setDdOpen(false);
  };

  const toggleValue = (sub: Factor) => {
    if (isSelected(sub)) {
      if (multi) deselectValue(sub);
      else saveDecision({ factors: clearFactorIds([sub.id, ...depSubs.map((d) => d.id)], decision!.factors) });
    } else if (multi) {
      selectValue(sub);
    } else {
      pickSingle(sub);
    }
  };

  const commitExpected = (sub: Factor) => {
    const raw = (expDrafts[sub.id] ?? '').trim();
    const n = parseFloat(raw);
    updateFactor(sub.id, { expected_value: Number.isFinite(n) ? n : 0 });
    const next = { ...expDrafts };
    delete next[sub.id];
    setExpDrafts(next);
  };

  const addValue = () => {
    const name = newValueName.trim();
    if (!name) return;
    const nv: Factor = {
      id: `sf_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      name,
      category: factor.category || 'secondary',
      rating: 0,
      order: subs.length,
      parent_id: factor.id,
      weight: 0,
      role: 'value',
      default_operator: '>=',
      data_type: 'numeric',
      unit: '%',
    };
    saveDecision({ factors: [...decision!.factors, nv] });
    setNewValueName('');
  };

  const refiner = (sub: Factor) => (
    <View style={st.refinerRow}>
      <Text style={st.refinerLabel}>Suitability</Text>
      <View style={st.opChips}>
        {NUMERIC_OPERATORS.map((op: any) => (
          <TouchableOpacity
            key={op.value}
            style={[st.opChip, sub.operator === op.value && st.opChipActive]}
            onPress={() => updateFactor(sub.id, { operator: op.value })}
          >
            <Text style={[st.opChipText, sub.operator === op.value && st.opChipTextActive]}>{op.label}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <TextInput
        style={st.refinerInput}
        keyboardType="numeric"
        value={expDrafts[sub.id] !== undefined ? expDrafts[sub.id] : String(sub.expected_value ?? '')}
        onChangeText={(v) => setExpDrafts({ ...expDrafts, [sub.id]: v.replace(/[^0-9.]/g, '') })}
        onBlur={() => commitExpected(sub)}
        placeholder={String(defExpected(sub))}
        placeholderTextColor={COLORS.textMuted}
        testID={`fv-refiner-${sub.id}`}
      />
      <Text style={st.refinerUnit}>%</Text>
    </View>
  );

  const valueRow = (sub: Factor) => {
    const on = isSelected(sub);
    const icon = multi
      ? (on ? 'checkbox' : 'square-outline')
      : (on ? 'radio-button-on' : 'radio-button-off');
    return (
      <View key={sub.id} style={[st.valueBlock, on && st.valueBlockOn]}>
        <TouchableOpacity style={st.valueRow} onPress={() => toggleValue(sub)} testID={`fv-value-${sub.id}`} activeOpacity={0.75}>
          <Ionicons name={icon as any} size={20} color={on ? COLORS.primary : '#94A3B8'} />
          <Text style={[st.valueName, on && st.valueNameOn]}>{sub.name}</Text>
          {on && (
            <View style={st.previewBadge}>
              <Text style={st.previewBadgeText}>{sub.operator || '≥'} {String(sub.expected_value)}%</Text>
            </View>
          )}
          {configMode && (
            <TouchableOpacity onPress={() => removeFactor(sub.id)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
              <Ionicons name="close-circle" size={17} color={COLORS.error} />
            </TouchableOpacity>
          )}
        </TouchableOpacity>
        {on && refiner(sub)}
      </View>
    );
  };

  return (
    <View style={st.wrap}>
      <View style={st.headRow}>
        <Ionicons
          name={multi ? 'checkbox-outline' : factor.ui_object === 'radio' ? 'radio-button-on-outline' : 'chevron-down-circle-outline'}
          size={13} color={COLORS.primary}
        />
        <Text style={st.headText}>
          {multi ? 'Select all that apply' : 'Select one'} · each pick gets an optional Suitability % refiner (editable)
        </Text>
      </View>

      {/* Dropdown = collapsed field; checkbox/radio/listbox = full list */}
      {factor.ui_object === 'dropdown' && !ddOpen ? (
        <TouchableOpacity style={st.ddField} onPress={() => setDdOpen(true)} testID={`fv-dd-${factor.id}`}>
          <Text style={selected.length ? st.ddValue : st.ddPlaceholder}>
            {selected.length ? selected[0].name : 'Tap to choose…'}
          </Text>
          <Ionicons name="chevron-down" size={16} color={COLORS.textSecondary} />
        </TouchableOpacity>
      ) : (
        <View>{valueSubs.map(valueRow)}</View>
      )}
      {factor.ui_object === 'dropdown' && !ddOpen && selected.map((s) => (
        <View key={s.id} style={[st.valueBlock, st.valueBlockOn]}>{refiner(s)}</View>
      ))}

      {/* Dependent refiners — appear when their linked value is ticked */}
      {depSubs.map((dep) => {
        const link = (dep.linked_value || '').trim().toLowerCase();
        const visible = !link || selectedNames.includes(link);
        if (!visible) return null;
        return (
          <View key={dep.id} style={st.depBlock}>
            <View style={st.depHead}>
              <Ionicons name="options-outline" size={13} color="#B45309" />
              <Text style={st.depName}>{dep.name}</Text>
              <Text style={st.depTag}>optional{dep.linked_value ? ` · with ${dep.linked_value}` : ''}</Text>
              {configMode && (
                <TouchableOpacity onPress={() => removeFactor(dep.id)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
                  <Ionicons name="close-circle" size={16} color={COLORS.error} />
                </TouchableOpacity>
              )}
            </View>
            {(dep.default_operator || dep.default_expected != null) && !isSelected(dep) && (
              <Text style={st.depHint}>Suggested: {dep.default_operator || '≥'} {String(dep.default_expected ?? '')}</Text>
            )}
            {renderCriteria(dep, true)}
          </View>
        );
      })}

      {/* Classic sub-role leftovers (rare in value-mode) — plain criteria, no split */}
      {otherSubs.map((s) => (
        <View key={s.id} style={st.depBlock}>
          <View style={st.depHead}>
            <View style={st.dot} />
            <Text style={st.depName}>{s.name}</Text>
          </View>
          {renderCriteria(s, true)}
        </View>
      ))}

      {configMode && (
        <View style={st.addRow}>
          <TextInput
            style={st.addInput}
            placeholder="Add a value (e.g. Corporate)…"
            placeholderTextColor={COLORS.textMuted}
            value={newValueName}
            onChangeText={setNewValueName}
            onSubmitEditing={addValue}
            testID={`fv-add-value-${factor.id}`}
          />
          <TouchableOpacity style={st.addBtn} onPress={addValue}>
            <Ionicons name="add" size={18} color="#FFF" />
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { marginTop: 6 },
  headRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 8 },
  headText: { flex: 1, fontSize: 11, color: COLORS.textMuted, lineHeight: 15 },
  valueBlock: {
    borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10,
    paddingVertical: 8, paddingHorizontal: 10, marginBottom: 6, backgroundColor: '#FFF',
  },
  valueBlockOn: { borderColor: '#C4B5FD', backgroundColor: '#FAF5FF' },
  valueRow: { flexDirection: 'row', alignItems: 'center', gap: 9, minHeight: 28 },
  valueName: { flex: 1, fontSize: 13.5, fontWeight: '600', color: COLORS.textSecondary },
  valueNameOn: { color: '#4C1D95', fontWeight: '700' },
  previewBadge: {
    backgroundColor: '#EDE9FE', borderRadius: 7, paddingHorizontal: 7, paddingVertical: 3, marginRight: 4,
  },
  previewBadgeText: { fontSize: 11, fontWeight: '700', color: '#6D28D9' },
  refinerRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, flexWrap: 'wrap' },
  refinerLabel: { fontSize: 11.5, fontWeight: '700', color: '#7C3AED' },
  opChips: { flexDirection: 'row', gap: 4 },
  opChip: {
    paddingHorizontal: 8, paddingVertical: 5, borderRadius: 7,
    borderWidth: 1, borderColor: '#E2E8F0', backgroundColor: '#FFF',
  },
  opChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  opChipText: { fontSize: 12, fontWeight: '700', color: COLORS.textSecondary },
  opChipTextActive: { color: '#FFF' },
  refinerInput: {
    minWidth: 58, borderWidth: 1, borderColor: '#DDD6FE', borderRadius: 8,
    paddingHorizontal: 9, paddingVertical: 6, fontSize: 13, color: '#1E293B', backgroundColor: '#FFF',
  },
  refinerUnit: { fontSize: 12.5, fontWeight: '700', color: COLORS.textMuted },
  ddField: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 11, backgroundColor: '#FFF', marginBottom: 6,
  },
  ddValue: { fontSize: 13.5, fontWeight: '700', color: '#1E293B' },
  ddPlaceholder: { fontSize: 13.5, color: COLORS.textMuted },
  depBlock: {
    borderWidth: 1, borderColor: '#FDE68A', borderRadius: 10, backgroundColor: '#FFFBEB',
    paddingVertical: 8, paddingHorizontal: 10, marginBottom: 6, marginTop: 2,
  },
  depHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  depName: { fontSize: 12.5, fontWeight: '700', color: '#92400E', flexShrink: 1 },
  depTag: { flex: 1, fontSize: 10.5, color: '#B45309', fontStyle: 'italic' },
  depHint: { fontSize: 11, color: '#B45309', marginTop: 3, marginLeft: 19 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#94A3B8' },
  addRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  addInput: {
    flex: 1, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 9, fontSize: 13, color: '#1E293B', backgroundColor: '#FFF',
  },
  addBtn: {
    backgroundColor: COLORS.primary, borderRadius: 10, width: 38, height: 38,
    alignItems: 'center', justifyContent: 'center',
  },
});
