// FormulaEditorModal — dedicated editor for user-authored dependency
// formulas (June 2026). Renders a full-screen modal with:
//   • the target factor picker (fN with a computed value)
//   • a large TextInput for the expression
//   • factor palette (tap to insert `fN` at the caret)
//   • live-evaluated result against option #1's values (or the user-supplied
//     symbol map)
//   • a scope selector — per-option (default) vs cross-option (shared scalar)
// Persists into decision.formulas via saveDecision.
import React, { useMemo, useState, useCallback } from 'react';
import {
  View,
  Text,
  Modal,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Platform,
  StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import { GradientButton } from './GradientButton';
import { useDecision } from '../context/DecisionContext';
import { evaluate, usedVariables, FormulaError } from '../utils/formulaEval';
import type { DecisionFormula, Factor } from '../types/decision';
import { showAlert } from '../utils/alert';

interface Props {
  visible: boolean;
  onClose: () => void;
}

const nid = () => `fx_${Math.random().toString(36).slice(2, 10)}`;

export default function FormulaEditorModal({ visible, onClose }: Props) {
  const { decision, saveDecision } = useDecision();

  // Formula list state (drafts) — synced on Save
  const initial = (decision.formulas || []) as DecisionFormula[];
  const [formulas, setFormulas] = useState<DecisionFormula[]>(initial);
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [draft, setDraft] = useState<DecisionFormula>({
    id: nid(), target: '', expression: '', scope: 'per_option', description: '',
  });
  const [previewErr, setPreviewErr] = useState<string | null>(null);
  const [previewVal, setPreviewVal] = useState<number | null>(null);

  React.useEffect(() => {
    // Re-hydrate whenever the modal opens (avoid stale drafts).
    if (visible) {
      setFormulas((decision.formulas || []) as DecisionFormula[]);
      setEditingIdx(null);
      setDraft({ id: nid(), target: '', expression: '', scope: 'per_option', description: '' });
      setPreviewErr(null);
      setPreviewVal(null);
    }
  }, [visible, decision.formulas]);

  // Build fN → factor + first-option's assessed value map for live preview.
  const topLevel = useMemo(
    () => (decision.factors as Factor[]).filter((f) => !f.parent_id && f.variable_id),
    [decision.factors],
  );
  const previewSymbols = useMemo(() => {
    const s: Record<string, any> = {};
    const opt = decision.options?.[0];
    topLevel.forEach((f) => {
      if (!f.variable_id) return;
      let val: any = f.expected_value ?? '';
      if (opt) {
        const a = opt.assessments?.find((x) => x.factor_id === f.id);
        if (a) {
          if (a.actual_value !== undefined && a.actual_value !== null) val = a.actual_value;
          else if (a.unit_value !== undefined && a.unit_value !== null && a.unit_value !== '') val = a.unit_value;
        }
      }
      s[f.variable_id] = val;
    });
    return s;
  }, [topLevel, decision.options]);

  const insertVarAtEnd = (v: string) => {
    setDraft((d) => ({ ...d, expression: (d.expression || '') + (d.expression ? ' ' : '') + v }));
    setPreviewErr(null);
  };

  const runPreview = useCallback(() => {
    try {
      const val = evaluate(draft.expression, previewSymbols);
      setPreviewVal(val);
      setPreviewErr(null);
    } catch (e: any) {
      setPreviewErr(e.message || String(e));
      setPreviewVal(null);
    }
  }, [draft.expression, previewSymbols]);

  React.useEffect(() => {
    if (!draft.expression) { setPreviewVal(null); setPreviewErr(null); return; }
    runPreview();
  }, [draft.expression, runPreview]);

  const startNew = () => {
    setEditingIdx(null);
    setDraft({ id: nid(), target: '', expression: '', scope: 'per_option', description: '' });
  };

  const startEdit = (idx: number) => {
    setEditingIdx(idx);
    setDraft({ ...formulas[idx] });
  };

  const removeAt = (idx: number) => {
    const next = formulas.filter((_, i) => i !== idx);
    setFormulas(next);
    if (editingIdx === idx) startNew();
  };

  const saveDraft = () => {
    if (!draft.target) {
      showAlert('Target required', 'Pick which factor this formula computes (its variable id, e.g. f7).');
      return;
    }
    if (!draft.expression || !draft.expression.trim()) {
      showAlert('Expression required', 'Enter a math expression like `f1 * f2 / 100`.');
      return;
    }
    try {
      const dummies: Record<string, number> = {};
      usedVariables(draft.expression).forEach((v) => { dummies[v] = 1; });
      evaluate(draft.expression, dummies);
    } catch (e: any) {
      showAlert('Invalid formula', e.message || 'Please check your expression.');
      return;
    }
    // Deduplicate by target: last-write wins for the same target.
    const next = formulas.filter((f, i) => (editingIdx === i ? false : f.target !== draft.target));
    if (editingIdx !== null) {
      next.splice(editingIdx, 0, { ...draft });
    } else {
      next.push({ ...draft });
    }
    setFormulas(next);
    startNew();
  };

  const commit = async () => {
    await saveDecision({ formulas } as any);
    onClose();
  };

  const varsInDraft = usedVariables(draft.expression);
  const unknownVars = varsInDraft.filter((v) => !previewSymbols.hasOwnProperty(v));

  return (
    <Modal visible={visible} animationType="slide" transparent={false} onRequestClose={onClose}>
      <View style={s.container}>
        {/* Header */}
        <View style={s.header}>
          <Text style={s.headerTitle}>Formulas</Text>
          <TouchableOpacity onPress={onClose} accessibilityLabel="Close formulas editor">
            <Ionicons name="close" size={26} color={COLORS.textPrimary} />
          </TouchableOpacity>
        </View>

        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          <Text style={s.blurb}>
            Compute one factor from others with a math expression. Use variable
            ids like <Text style={{ fontWeight: '700' }}>f1, f2 …</Text>. Supported:
            {' + − × ÷ % ( )'} and <Text style={{ fontWeight: '700' }}>abs, min, max, round</Text>.
          </Text>

          {/* Existing formulas */}
          {formulas.length > 0 && (
            <View style={{ marginBottom: 14 }}>
              <Text style={s.sectionLabel}>Existing formulas</Text>
              {formulas.map((f, idx) => {
                const targetFactor = topLevel.find((t) => t.variable_id === f.target);
                return (
                  <View key={f.id} style={s.formulaRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.formulaHead}>
                        <Text style={{ color: COLORS.primary }}>{f.target}</Text>
                        {targetFactor ? ` · ${targetFactor.name}` : ''}
                        {f.scope === 'cross_option' ? ' · cross-option' : ''}
                      </Text>
                      <Text style={s.formulaExpr}>{f.expression}</Text>
                    </View>
                    <TouchableOpacity onPress={() => startEdit(idx)} style={s.iconBtn} accessibilityLabel={`Edit formula for ${f.target}`}>
                      <Ionicons name="create-outline" size={20} color={COLORS.primary} />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => removeAt(idx)} style={s.iconBtn} accessibilityLabel={`Delete formula for ${f.target}`}>
                      <Ionicons name="trash-outline" size={20} color="#DC2626" />
                    </TouchableOpacity>
                  </View>
                );
              })}
            </View>
          )}

          {/* Editor */}
          <View style={s.editorCard}>
            <Text style={s.sectionLabel}>{editingIdx === null ? 'Add new formula' : `Edit formula for ${draft.target}`}</Text>

            {/* Target picker */}
            <Text style={s.fieldLabel}>Target factor (fN)</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
              {topLevel.length === 0 && (
                <Text style={s.helperText}>No factors have variable ids yet. Add factors on Step 2 first.</Text>
              )}
              {topLevel.map((f) => {
                const on = draft.target === f.variable_id;
                return (
                  <TouchableOpacity
                    key={f.id}
                    onPress={() => setDraft((d) => ({ ...d, target: f.variable_id || '' }))}
                    style={[s.chip, on && s.chipOn]}
                  >
                    <Text style={[s.chipText, on && s.chipTextOn]}>
                      {f.variable_id} · {f.name.length > 24 ? f.name.slice(0, 24) + '…' : f.name}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {/* Expression */}
            <Text style={s.fieldLabel}>Expression</Text>
            <TextInput
              value={draft.expression}
              onChangeText={(t) => setDraft((d) => ({ ...d, expression: t }))}
              placeholder="e.g. f1 * (f2/100) * f3 * (f4/100) * f6 / f5"
              placeholderTextColor={COLORS.textMuted}
              multiline
              numberOfLines={4}
              style={s.exprInput}
              autoCapitalize="none"
              autoCorrect={false}
            />

            {/* Variable palette */}
            <Text style={s.fieldLabel}>Insert variable</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
              {topLevel.map((f) => (
                <TouchableOpacity key={f.id} onPress={() => insertVarAtEnd(f.variable_id || '')} style={s.varChip}>
                  <Text style={s.varChipText}>{f.variable_id}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Scope */}
            <Text style={s.fieldLabel}>Scope</Text>
            <View style={{ flexDirection: 'row', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
              {(['per_option', 'cross_option'] as const).map((mode) => {
                const on = (draft.scope || 'per_option') === mode;
                return (
                  <TouchableOpacity
                    key={mode}
                    onPress={() => setDraft((d) => ({ ...d, scope: mode as any }))}
                    style={[s.chip, on && s.chipOn]}
                  >
                    <Text style={[s.chipText, on && s.chipTextOn]}>
                      {mode === 'per_option' ? 'Per option (default)' : 'Cross-option (shared)'}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            <Text style={[s.helperText, { marginBottom: 12 }]}>
              {(draft.scope || 'per_option') === 'per_option'
                ? 'Computed separately for each option using that option\u2019s own values.'
                : 'Produces one shared value used by all options (for constants that don\u2019t vary per option).'}
            </Text>

            {/* Description */}
            <Text style={s.fieldLabel}>Description (optional)</Text>
            <TextInput
              value={draft.description || ''}
              onChangeText={(t) => setDraft((d) => ({ ...d, description: t }))}
              placeholder="e.g. Viral growth spread over campaign duration"
              placeholderTextColor={COLORS.textMuted}
              style={s.descInput}
            />

            {/* Live preview */}
            <View style={s.previewBox}>
              <Ionicons
                name={previewErr ? 'alert-circle' : 'flash-outline'}
                size={16}
                color={previewErr ? '#DC2626' : '#059669'}
              />
              <View style={{ flex: 1, marginLeft: 8 }}>
                {previewErr ? (
                  <Text style={{ color: '#DC2626', fontSize: 12 }}>{previewErr}</Text>
                ) : previewVal !== null ? (
                  <Text style={{ color: '#065F46', fontSize: 12 }}>
                    Preview using option 1: <Text style={{ fontWeight: '800' }}>{Number.isFinite(previewVal) ? previewVal.toString() : String(previewVal)}</Text>
                  </Text>
                ) : (
                  <Text style={{ color: COLORS.textMuted, fontSize: 12 }}>
                    Type an expression to see a live preview using your first option&apos;s values.
                  </Text>
                )}
              </View>
            </View>

            {unknownVars.length > 0 && (
              <Text style={[s.helperText, { color: '#B45309', marginTop: 6 }]}>
                Unknown variables: {unknownVars.join(', ')} — check factor variable ids on Step 2.
              </Text>
            )}

            <View style={{ flexDirection: 'row', gap: 10, marginTop: 14 }}>
              <TouchableOpacity onPress={startNew} style={s.secondaryBtn}>
                <Text style={s.secondaryText}>{editingIdx === null ? 'Clear' : 'Cancel edit'}</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={saveDraft} style={s.primaryBtn}>
                <Ionicons name={editingIdx === null ? 'add' : 'checkmark'} size={18} color="#FFF" />
                <Text style={s.primaryText}>{editingIdx === null ? 'Add formula' : 'Update formula'}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>

        <View style={s.footer}>
          <TouchableOpacity onPress={onClose} style={s.secondaryBtn}>
            <Text style={s.secondaryText}>Cancel</Text>
          </TouchableOpacity>
          <GradientButton title="Save formulas" onPress={commit} style={{ flex: 1 }} />
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background, paddingTop: Platform.OS === 'ios' ? 40 : 20 },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: COLORS.border,
    backgroundColor: COLORS.white,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  blurb: { fontSize: 13, color: COLORS.textSecondary, marginBottom: 12, lineHeight: 18 },
  sectionLabel: { fontSize: 12, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 8 },
  formulaRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.white, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, marginBottom: 6 },
  formulaHead: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  formulaExpr: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2, fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }) },
  iconBtn: { padding: 6, marginLeft: 4 },
  editorCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: COLORS.border },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 6 },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F8FAFC' },
  chipOn: { backgroundColor: '#EDE7F6', borderColor: COLORS.primary },
  chipText: { fontSize: 12, color: COLORS.textPrimary },
  chipTextOn: { color: COLORS.primary, fontWeight: '700' },
  varChip: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, backgroundColor: '#F1F5F9', borderWidth: 1, borderColor: COLORS.border },
  varChipText: { fontSize: 13, fontWeight: '700', color: COLORS.primary, fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }) },
  exprInput: { minHeight: 90, borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, padding: 12, fontSize: 14, fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }), color: COLORS.textPrimary, backgroundColor: '#F8FAFC', marginBottom: 12, textAlignVertical: 'top' },
  descInput: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, padding: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: '#F8FAFC', marginBottom: 12 },
  previewBox: { flexDirection: 'row', alignItems: 'flex-start', padding: 10, borderRadius: 10, backgroundColor: '#F0FDF4', borderWidth: 1, borderColor: '#BBF7D0' },
  helperText: { fontSize: 11, color: COLORS.textMuted, lineHeight: 15 },
  primaryBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: COLORS.primary, paddingVertical: 12, borderRadius: 10 },
  primaryText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
  secondaryBtn: { paddingVertical: 12, paddingHorizontal: 18, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F8FAFC' },
  secondaryText: { color: COLORS.textPrimary, fontWeight: '700', fontSize: 14 },
  footer: {
    flexDirection: 'row', gap: 10, paddingHorizontal: 16, paddingVertical: 12,
    borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white,
  },
});
