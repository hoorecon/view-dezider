/* Pros & Cons wizard — leaf presentational components (extracted). */
import React, { useState, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, Modal, ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LMH_VALUES, NUMERIC_OPERATORS, TEXT_OPERATORS } from '../../utils/decisionHelpers';
import { Factor, OptionT, Cell } from './types';
import { COLORS } from './constants';
import { styles, pcMeta, pcAssess, pcWeightStyles } from './styles';

export const DebouncedInput = React.forwardRef<any, {
  value: string;
  onSave: (val: string) => void;
  placeholder?: string;
  placeholderTextColor?: string;
  keyboardType?: any;
  style?: any;
  editable?: boolean;
  multiline?: boolean;
  debounceMs?: number;
}>(function DebouncedInput(
  { value, onSave, placeholder, placeholderTextColor, keyboardType, style, editable, multiline, debounceMs = 600 },
  ref,
) {
  const [local, setLocal] = useState<string>(value ?? '');
  const lastSavedRef = useRef<string>(value ?? '');
  const localRef = useRef<string>(value ?? '');
  const timerRef = useRef<any>(null);
  const onSaveRef = useRef(onSave);
  React.useEffect(() => { onSaveRef.current = onSave; }, [onSave]);

  // Sync from outside (e.g., reload from server) — only when value really
  // changes and the user isn't mid-typing into something else for THIS prop.
  React.useEffect(() => {
    const incoming = value ?? '';
    if (incoming !== lastSavedRef.current && incoming !== localRef.current) {
      setLocal(incoming);
      localRef.current = incoming;
      lastSavedRef.current = incoming;
    }
  }, [value]);

  // Debounced save while typing
  const onChange = (text: string) => {
    setLocal(text);
    localRef.current = text;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      if (localRef.current !== lastSavedRef.current) {
        lastSavedRef.current = localRef.current;
        try { onSaveRef.current(localRef.current); } catch { /* swallow */ }
      }
    }, debounceMs);
  };

  // Flush helper — used by onBlur and unmount cleanup
  const flush = () => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    if (localRef.current !== lastSavedRef.current) {
      lastSavedRef.current = localRef.current;
      try { onSaveRef.current(localRef.current); } catch { /* swallow */ }
    }
  };

  // Flush on unmount (covers Step 7 → Step 8 transition before blur fires)
  React.useEffect(() => () => flush(), []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <TextInput
      ref={ref as any}
      style={style}
      value={local}
      onChangeText={onChange}
      onBlur={flush}
      placeholder={placeholder}
      placeholderTextColor={placeholderTextColor}
      keyboardType={keyboardType}
      editable={editable !== false}
      multiline={multiline}
    />
  );
});

export function NextBack({ onBack, onNext }: { onBack: (() => void) | null; onNext: (() => void) | null }) {
  return (
    <View style={styles.navBar}>
      <TouchableOpacity style={[styles.navBtn, !onBack && { opacity: 0.3 }]} onPress={() => onBack?.()} disabled={!onBack}>
        <Ionicons name="chevron-back" size={18} color={COLORS.text} />
        <Text style={styles.navBtnText}>Back</Text>
      </TouchableOpacity>
      {onNext ? (
        <TouchableOpacity style={styles.navBtnPrimary} onPress={() => onNext()}>
          <Text style={[styles.navBtnText, { color: '#fff' }]}>Next</Text>
          <Ionicons name="chevron-forward" size={18} color="#fff" />
        </TouchableOpacity>
      ) : (
        <View />
      )}
    </View>
  );
}

export function FactorGroupRow({ factor, parentName, candidateChildren, onAddChild, onCreateChild, onPromote, onToggleDuplicate }: {
  factor: Factor;
  /** Concrete parent name to render in the "↳ under X" caption. Null when
   *  this row is itself a top-level factor. Used to remove the previous
   *  "grouped under a main factor above" ambiguity. */
  parentName: string | null;
  candidateChildren: Factor[];
  onAddChild: (childId: string) => void;
  onCreateChild: (name: string) => Promise<void> | void;
  onPromote: () => void;
  onToggleDuplicate: () => void;
}) {
  const [open, setOpen] = useState(false);
  // Local state for the inline "create new sub-factor" text input.
  // We keep this local to the row so each parent has its own draft and
  // typing into one row doesn't leak into another.
  const [newSubName, setNewSubName] = useState('');
  const [creating, setCreating] = useState(false);

  const isSubFactor = !!factor.parent_id;
  const isDuplicate = !!factor.is_duplicate;
  // Visual treatment ladder:
  //   duplicate  → strongest mute (light gray + strikethrough)
  //   sub-factor → medium mute (gray tag, no original P/C color)
  //   active     → normal (P/C/D coloured tag)
  const muted = isDuplicate || isSubFactor;
  const tagBg = isDuplicate || isSubFactor
    ? '#94A3B8'
    : (factor.source === 'direct' ? COLORS.direct : factor.source === 'pro' ? COLORS.pro : COLORS.con);
  const tagLetter = isDuplicate ? '–' : (factor.source === 'direct' ? 'D' : factor.source === 'pro' ? 'P' : 'C');

  return (
    <View style={[
      styles.factorRow,
      isSubFactor && styles.factorRowSub,
      isSubFactor && { marginLeft: 24 },              // visible indent for child rows
      isDuplicate && styles.factorRowDuplicate,
    ]}>
      <View style={[styles.sourceTag, { backgroundColor: tagBg }]}>
        <Text style={styles.sourceTagText}>{tagLetter}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[
          styles.factorName,
          muted && { color: COLORS.textDim },
          isDuplicate && { textDecorationLine: 'line-through' as any },
        ]}>{factor.name}</Text>
        {isSubFactor && (
          <Text style={[styles.factorMeta, { color: COLORS.textDim }]}>
            ↳ sub-factor of <Text style={{ fontWeight: '700', color: COLORS.text }}>“{parentName || 'unknown'}”</Text>
          </Text>
        )}
        {isDuplicate && (
          <Text style={[styles.factorMeta, { color: COLORS.warn }]}>
            Marked as duplicate · hidden from Step 5 onward
          </Text>
        )}
      </View>

      {/* Action button depends on what type of row this is:
          • top-level active factor → "Add sub-factor…" (this factor becomes the PARENT)
          • already-a-sub-factor    → "Promote out"     (clear its parent_id, back to top-level)
          • duplicate              → no group action at all */}
      {!isDuplicate && !isSubFactor && (
        <TouchableOpacity
          onPress={() => setOpen(o => !o)}
          style={styles.linkBtn}
          accessibilityLabel="Add another factor as a sub-factor under this one"
        >
          <Text style={styles.linkBtnText}>+ Sub-factor</Text>
        </TouchableOpacity>
      )}
      {!isDuplicate && isSubFactor && (
        <TouchableOpacity
          onPress={onPromote}
          style={[styles.linkBtn, styles.linkBtnMuted]}
          accessibilityLabel="Promote out — make this a top-level factor again"
        >
          <Text style={styles.linkBtnText}>Promote out</Text>
        </TouchableOpacity>
      )}

      {/* Toggle Duplicate — labeled pill replacing the old destructive delete. */}
      <TouchableOpacity
        onPress={onToggleDuplicate}
        style={[
          styles.dupBtn,
          isDuplicate ? styles.dupBtnRestore : styles.dupBtnMark,
        ]}
        accessibilityLabel={isDuplicate ? 'Restore — un-mark as duplicate' : 'Mark as duplicate (soft remove)'}
      >
        <Ionicons
          name={isDuplicate ? 'arrow-undo-outline' : 'remove-circle-outline'}
          size={13}
          color={isDuplicate ? COLORS.ok : '#B45309'}
        />
        <Text style={[
          styles.dupBtnText,
          { color: isDuplicate ? COLORS.ok : '#B45309' },
        ]}>
          {isDuplicate ? 'Restore' : 'Duplicate'}
        </Text>
      </TouchableOpacity>

      {open && !isDuplicate && !isSubFactor && (
        <View style={{ width: '100%', marginTop: 8 }}>
          <Text style={styles.parentPickerLabel}>
            Add a sub-factor <Text style={{ fontWeight: '800', color: COLORS.text }}>UNDER “{factor.name}”</Text>
          </Text>

          {/* ── Path A: Create a brand-new sub-factor by typing its name ── */}
          <Text style={[styles.factorMeta, { color: COLORS.textDim, marginTop: 6, marginBottom: 4 }]}>
            ✏️  Type a new sub-factor name
          </Text>
          <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
            <TextInput
              style={[styles.input, { flex: 1, minWidth: 0, marginBottom: 0 }]}
              placeholder={`e.g. a sub-aspect of “${factor.name}”`}
              placeholderTextColor={COLORS.textDim}
              value={newSubName}
              onChangeText={setNewSubName}
              editable={!creating}
              returnKeyType="done"
              onSubmitEditing={async () => {
                if (!newSubName.trim() || creating) return;
                setCreating(true);
                try {
                  await onCreateChild(newSubName);
                  setNewSubName('');
                  setOpen(false);
                } finally { setCreating(false); }
              }}
            />
            <TouchableOpacity
              style={[
                styles.linkBtn,
                { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
                (!newSubName.trim() || creating) && { opacity: 0.5 },
              ]}
              disabled={!newSubName.trim() || creating}
              onPress={async () => {
                setCreating(true);
                try {
                  await onCreateChild(newSubName);
                  setNewSubName('');
                  setOpen(false);
                } finally { setCreating(false); }
              }}
              accessibilityLabel="Create new sub-factor under this factor"
            >
              <Text style={[styles.linkBtnText, { color: '#fff' }]}>
                {creating ? 'Adding…' : 'Add'}
              </Text>
            </TouchableOpacity>
          </View>

          {/* ── Path B: Move an EXISTING top-level factor under this one ── */}
          {candidateChildren.length > 0 && (
            <>
              <Text style={[styles.factorMeta, { color: COLORS.textDim, marginTop: 10, marginBottom: 4 }]}>
                ↳ …or pick an existing top-level factor to nest under it
              </Text>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                {candidateChildren.map(c => (
                  <TouchableOpacity
                    key={c.id}
                    style={styles.parentChip}
                    onPress={() => { onAddChild(c.id); setOpen(false); }}
                    {...({ title: c.name } as any)}
                  >
                    <Text style={styles.parentChipText} numberOfLines={1} {...({ title: c.name } as any)}>{c.name}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </>
          )}
        </View>
      )}
    </View>
  );
}

const DATA_SOURCE_TYPES = [
  { value: 'manual', label: 'Manual entry', icon: 'create-outline', hint: 'You enter the actual value yourself during assessment.' },
  { value: 'webhook', label: 'Webhook / API', icon: 'globe-outline', hint: 'Pull the value from a REST endpoint.' },
  { value: 'web_surf', label: 'Web Surf', icon: 'search-outline', hint: 'AI searches the web for the value.' },
  { value: 'ai_llm', label: 'AI / LLM', icon: 'sparkles-outline', hint: 'AI infers the value from a prompt.' },
];

/** Per-factor metadata: Type (Quant/Qual) + Expected + Unit + Operator + Data Source.
 *  Shown in Step 5 "Review & Refine Expectations" for every factor & sub-factor. */
export function FactorMetaControls({ factor, onPatch, onOpenDataSource }: {
  factor: Factor;
  onPatch: (factorId: string, patch: any) => void;
  onOpenDataSource: (factor: Factor) => void;
}) {
  const isQuant = (factor.data_type || 'numeric') === 'numeric';
  const operators = isQuant ? NUMERIC_OPERATORS : TEXT_OPERATORS;
  const dsType = factor.data_source?.type;
  const dsLabel = DATA_SOURCE_TYPES.find(d => d.value === dsType)?.label;
  return (
    <View style={pcMeta.wrap}>
      <View style={pcMeta.row}>
        <Text style={pcMeta.label}>Type</Text>
        <View style={pcMeta.toggle}>
          <TouchableOpacity
            style={[pcMeta.toggleBtn, isQuant && pcMeta.toggleQuant]}
            onPress={() => onPatch(factor.id, { data_type: 'numeric' })}
            testID={`pc-type-quant-${factor.id}`}
          >
            <Text style={[pcMeta.toggleText, isQuant && pcMeta.toggleTextOn]}>Quantitative</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[pcMeta.toggleBtn, !isQuant && pcMeta.toggleQual]}
            onPress={() => onPatch(factor.id, { data_type: 'text' })}
            testID={`pc-type-qual-${factor.id}`}
          >
            <Text style={[pcMeta.toggleText, !isQuant && pcMeta.toggleTextOn]}>Qualitative</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={pcMeta.row}>
        <Text style={pcMeta.label}>Operator</Text>
        <View style={pcMeta.opWrap}>
          {operators.map(op => {
            const active = factor.operator === op.value;
            return (
              <TouchableOpacity
                key={op.value}
                style={[pcMeta.opChip, active && pcMeta.opChipActive]}
                onPress={() => onPatch(factor.id, { operator: active ? null : op.value })}
              >
                <Text style={[pcMeta.opText, active && pcMeta.toggleTextOn]}>{op.label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </View>

      <View style={pcMeta.row}>
        <Text style={pcMeta.label}>Expected</Text>
        <DebouncedInput
          style={pcMeta.input}
          value={factor.expected_value != null ? String(factor.expected_value) : ''}
          placeholder={isQuant ? 'e.g., 1000' : 'e.g., Excellent'}
          placeholderTextColor={COLORS.textDim}
          onSave={(t) => onPatch(factor.id, { expected_value: t.trim() || null })}
        />
        {isQuant && (
          <DebouncedInput
            style={[pcMeta.input, { maxWidth: 84 }]}
            value={factor.unit || ''}
            placeholder="unit"
            placeholderTextColor={COLORS.textDim}
            onSave={(t) => onPatch(factor.id, { unit: t.trim() || null })}
          />
        )}
      </View>

      <TouchableOpacity style={pcMeta.dsBtn} onPress={() => onOpenDataSource(factor)} testID={`pc-ds-${factor.id}`}>
        <Ionicons name="cloud-download-outline" size={14} color="#7C3AED" />
        <Text style={pcMeta.dsBtnText}>{dsLabel ? `Data source: ${dsLabel}` : 'Set data source (optional)'}</Text>
        <Ionicons name="chevron-forward" size={14} color="#7C3AED" />
      </TouchableOpacity>
    </View>
  );
}

/** Full-parity Auto-Fetch configuration modal (Webhook/API, Web Surf, AI/LLM). */
export function DataSourceModal({ factor, onClose, onSave }: {
  factor: Factor | null;
  onClose: () => void;
  onSave: (factorId: string, data_source: any) => void;
}) {
  const [type, setType] = useState<string>(factor?.data_source?.type || 'manual');
  const [cfg, setCfg] = useState<Record<string, any>>(factor?.data_source?.config || {});
  React.useEffect(() => {
    setType(factor?.data_source?.type || 'manual');
    setCfg(factor?.data_source?.config || {});
  }, [factor?.id]);
  if (!factor) return null;
  const setField = (k: string, v: string) => setCfg(prev => ({ ...prev, [k]: v }));
  return (
    <Modal visible={!!factor} animationType="slide" transparent onRequestClose={onClose}>
      <View style={pcMeta.modalOverlay}>
        <View style={pcMeta.modalCard}>
          <View style={pcMeta.modalHead}>
            <Text style={pcMeta.modalTitle}>Auto-Fetch Configuration</Text>
            <TouchableOpacity onPress={onClose}><Ionicons name="close" size={22} color={COLORS.text} /></TouchableOpacity>
          </View>
          <ScrollView style={{ maxHeight: 420 }}>
            {DATA_SOURCE_TYPES.map(d => (
              <TouchableOpacity key={d.value} style={[pcMeta.dsOpt, type === d.value && pcMeta.dsOptOn]} onPress={() => setType(d.value)}>
                <Ionicons name={d.icon as any} size={18} color={type === d.value ? '#7C3AED' : COLORS.textDim} />
                <View style={{ flex: 1 }}>
                  <Text style={[pcMeta.dsOptLabel, type === d.value && { color: '#7C3AED' }]}>{d.label}</Text>
                  <Text style={pcMeta.dsOptHint}>{d.hint}</Text>
                </View>
                {type === d.value && <Ionicons name="checkmark-circle" size={18} color="#7C3AED" />}
              </TouchableOpacity>
            ))}

            {type === 'webhook' && (
              <View style={pcMeta.cfgBox}>
                <Text style={pcMeta.cfgLabel}>Endpoint URL</Text>
                <TextInput style={pcMeta.cfgInput} value={cfg.url || ''} onChangeText={(v) => setField('url', v)} placeholder="https://api.example.com/value" placeholderTextColor={COLORS.textDim} autoCapitalize="none" />
                <Text style={pcMeta.cfgLabel}>JSON path (optional)</Text>
                <TextInput style={pcMeta.cfgInput} value={cfg.json_path || ''} onChangeText={(v) => setField('json_path', v)} placeholder="data.price" placeholderTextColor={COLORS.textDim} autoCapitalize="none" />
                <Text style={pcMeta.cfgLabel}>Auth header (optional)</Text>
                <TextInput style={pcMeta.cfgInput} value={cfg.auth_header || ''} onChangeText={(v) => setField('auth_header', v)} placeholder="Bearer ..." placeholderTextColor={COLORS.textDim} autoCapitalize="none" />
              </View>
            )}
            {type === 'web_surf' && (
              <View style={pcMeta.cfgBox}>
                <Text style={pcMeta.cfgLabel}>Search query</Text>
                <TextInput style={[pcMeta.cfgInput, { height: 64 }]} multiline value={cfg.query || ''} onChangeText={(v) => setField('query', v)} placeholder="e.g., average resale value of <option> in 2025" placeholderTextColor={COLORS.textDim} />
              </View>
            )}
            {type === 'ai_llm' && (
              <View style={pcMeta.cfgBox}>
                <Text style={pcMeta.cfgLabel}>AI prompt</Text>
                <TextInput style={[pcMeta.cfgInput, { height: 80 }]} multiline value={cfg.prompt || ''} onChangeText={(v) => setField('prompt', v)} placeholder="Describe what value the AI should infer for this factor." placeholderTextColor={COLORS.textDim} />
              </View>
            )}
          </ScrollView>
          <TouchableOpacity
            style={pcMeta.saveBtn}
            onPress={() => onSave(factor.id, { type, config: type === 'manual' ? {} : cfg })}
            testID="pc-ds-save"
          >
            <Text style={pcMeta.saveBtnText}>Save data source</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

export function FactorTreeNode({
  factor,
  childrenList,
  displayNameOf,
  hasRenameOf,
  originalNameOf,
  onRename,
  onRevertName,
  onSetWeight,
  onAddSubFactor,
  onPatchFactor,
  onOpenDataSource,
  onDeleteFactor,
}: {
  factor: Factor;
  childrenList: Factor[];
  /** Returns the name to display (display_name || name when step >= 5) */
  displayNameOf: (f: Factor) => string;
  /** True when display_name differs from name (i.e., this row is renamed) */
  hasRenameOf: (f: Factor) => boolean;
  /** Returns the original (Step-1) name to show as "Originally: …" hint */
  originalNameOf: (f: Factor) => string;
  /** Persist a rename via PUT display_name */
  onRename: (factorId: string, newDisplayName: string) => void | Promise<void>;
  /** Clear the rename — PUT display_name=null. Reverts to original `name`. */
  onRevertName: (factorId: string) => void | Promise<void>;
  /** Persist a sub-factor weight via PUT weight */
  onSetWeight: (factorId: string, weight: number) => void | Promise<void>;
  /** Create a new sub-factor under this parent */
  onAddSubFactor: (parentId: string) => void | Promise<void>;
  /** Persist a factor metadata patch (type/expected/unit/operator/data_source) */
  onPatchFactor: (factorId: string, patch: any) => void | Promise<void>;
  /** Open the Data Source modal for a factor */
  onOpenDataSource: (factor: Factor) => void;
  /** Delete a factor (with confirm). Only offered for custom sub-factors. */
  onDeleteFactor: (factor: Factor) => void;
}) {
  const [open, setOpen] = useState(true);
  const [wInputs, setWInputs] = useState<Record<string, string>>({});
  const hasSubs = childrenList.length > 0;
  const weightTotal = childrenList.reduce((s, c) => s + (Number(c.weight) || 0), 0);

  const commitWeight = (childId: string) => {
    const raw = (wInputs[childId] ?? '').trim();
    if (raw === '') return;
    const clamped = Math.min(100, Math.max(0, parseInt(raw, 10) || 0));
    onSetWeight(childId, clamped);
  };

  const splitEvenly = () => {
    if (childrenList.length === 0) return;
    const base = Math.floor(100 / childrenList.length);
    const remainder = 100 - base * childrenList.length;
    childrenList.forEach((c, i) => onSetWeight(c.id, base + (i < remainder ? 1 : 0)));
    setWInputs({});
  };

  return (
    <View style={styles.treeNode}>
      <View style={styles.treeHead}>
        <TouchableOpacity onPress={() => setOpen(o => !o)} style={{ marginRight: 4 }}>
          <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={18} color={COLORS.textDim} />
        </TouchableOpacity>
        <RenamableFactorRow
          factor={factor}
          displayNameOf={displayNameOf}
          hasRenameOf={hasRenameOf}
          originalNameOf={originalNameOf}
          onRename={onRename}
          onRevertName={onRevertName}
        />
        {hasSubs ? (
          <View style={[pcWeightStyles.totalBadge, weightTotal === 100 && pcWeightStyles.totalOk, weightTotal > 100 && pcWeightStyles.totalOver]}>
            <Text style={[pcWeightStyles.totalText, weightTotal === 100 && { color: '#fff' }, weightTotal > 100 && { color: '#fff' }]}>{weightTotal}%</Text>
          </View>
        ) : (
          <Text style={styles.factorMeta}>leaf</Text>
        )}
      </View>

      {open && (
        <View style={{ marginTop: 6 }}>
          {/* Main factor metadata (Type / Expected / Unit / Operator / Data Source) */}
          <FactorMetaControls factor={factor} onPatch={onPatchFactor} onOpenDataSource={onOpenDataSource} />

          {/* Add sub-factor */}
          <TouchableOpacity style={pcMeta.addSubBtn} onPress={() => onAddSubFactor(factor.id)} testID={`pc-addsub-${factor.id}`}>
            <Ionicons name="add-circle-outline" size={15} color="#15803D" />
            <Text style={pcMeta.addSubText}>Add sub-factor</Text>
          </TouchableOpacity>

          {hasSubs && (
            <View style={{ marginTop: 8 }}>
              <View style={pcWeightStyles.splitRow}>
                <Text style={pcWeightStyles.weightHint}>
                  {weightTotal === 100
                    ? 'Weightage split is balanced (100%).'
                    : weightTotal > 100
                      ? `Over by ${weightTotal - 100}%. Adjust or split evenly — weights are normalised.`
                      : `${100 - weightTotal}% unallocated. Optional — weights are normalised on scoring.`}
                </Text>
                <TouchableOpacity onPress={splitEvenly} style={pcWeightStyles.splitBtn} testID={`pc-split-${factor.id}`} accessibilityLabel="Split weightage evenly">
                  <Ionicons name="git-compare-outline" size={13} color="#7C3AED" />
                  <Text style={pcWeightStyles.splitBtnText}>Split evenly</Text>
                </TouchableOpacity>
              </View>

              {childrenList.map(c => (
                <View key={c.id} style={pcWeightStyles.subBlock}>
                  <View style={styles.treeChild}>
                    <View style={[styles.sourceTag, { backgroundColor: c.source === 'pro' ? COLORS.pro : c.source === 'con' ? COLORS.con : COLORS.direct }]}>
                      <Text style={styles.sourceTagText}>{c.source === 'direct' ? 'D' : c.source === 'pro' ? 'P' : 'C'}</Text>
                    </View>
                    <RenamableFactorRow
                      factor={c}
                      displayNameOf={displayNameOf}
                      hasRenameOf={hasRenameOf}
                      originalNameOf={originalNameOf}
                      onRename={onRename}
                      onRevertName={onRevertName}
                    />
                    <View style={pcWeightStyles.weightWrap}>
                      <TextInput
                        style={pcWeightStyles.weightInput}
                        value={wInputs[c.id] !== undefined ? wInputs[c.id] : (c.weight ? String(c.weight) : '')}
                        onChangeText={(v) => setWInputs({ ...wInputs, [c.id]: v.replace(/[^0-9]/g, '') })}
                        onBlur={() => commitWeight(c.id)}
                        keyboardType="number-pad"
                        placeholder="0"
                        placeholderTextColor={COLORS.textDim}
                        testID={`pc-subweight-${c.id}`}
                      />
                      <Text style={pcWeightStyles.weightPct}>%</Text>
                    </View>
                    {/* Delete — only for custom (directly-added) sub-factors, not
                        sub-factors promoted from pros/cons */}
                    {c.source === 'direct' && (
                      <TouchableOpacity
                        onPress={() => onDeleteFactor(c)}
                        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                        style={{ marginLeft: 6 }}
                        testID={`pc-delsub-${c.id}`}
                        accessibilityLabel="Delete sub-factor"
                      >
                        <Ionicons name="trash-outline" size={16} color={COLORS.con} />
                      </TouchableOpacity>
                    )}
                  </View>
                  {/* Sub-factor metadata */}
                  <FactorMetaControls factor={c} onPatch={onPatchFactor} onOpenDataSource={onOpenDataSource} />
                </View>
              ))}
            </View>
          )}
        </View>
      )}
    </View>
  );
}

/**
 * Inline-editable single-row factor name with pencil icon.
 *
 * Click pencil → row becomes a TextInput + Save / Cancel / Revert buttons.
 *   - "Save" PUTs display_name (only takes effect Step 5+)
 *   - "Revert" PUTs display_name=null and falls back to original `name`
 *   - The original (Step-1) name is shown as a subtle hint under the row
 *     ONLY when a rename is active, so the user remembers what it used
 *     to be called.
 */
export function RenamableFactorRow({
  factor,
  displayNameOf,
  hasRenameOf,
  originalNameOf,
  onRename,
  onRevertName,
}: {
  factor: Factor;
  displayNameOf: (f: Factor) => string;
  hasRenameOf: (f: Factor) => boolean;
  originalNameOf: (f: Factor) => string;
  onRename: (factorId: string, newDisplayName: string) => void | Promise<void>;
  onRevertName: (factorId: string) => void | Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(displayNameOf(factor));
  const [busy, setBusy] = useState(false);

  const startEdit = () => {
    setDraft(displayNameOf(factor));
    setEditing(true);
  };

  const save = async () => {
    const trimmed = draft.trim();
    if (!trimmed) return;
    if (trimmed === displayNameOf(factor)) { setEditing(false); return; }
    setBusy(true);
    try {
      await onRename(factor.id, trimmed);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  const revert = async () => {
    setBusy(true);
    try {
      await onRevertName(factor.id);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
          <TextInput
            style={[styles.input, { flex: 1, marginBottom: 0 }]}
            value={draft}
            onChangeText={setDraft}
            placeholder="Rename factor"
            placeholderTextColor={COLORS.textDim}
            autoFocus
            editable={!busy}
            returnKeyType="done"
            onSubmitEditing={save}
          />
          <TouchableOpacity
            style={[styles.miniBtn, (!draft.trim() || busy) && { opacity: 0.5 }]}
            disabled={!draft.trim() || busy}
            onPress={save}
            accessibilityLabel="Save factor rename"
          >
            <Text style={{ color: '#fff', fontWeight: '700', fontSize: 12 }}>
              {busy ? '…' : 'Save'}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.miniBtn, { backgroundColor: '#EEE' }]}
            onPress={() => setEditing(false)}
            disabled={busy}
            accessibilityLabel="Cancel rename"
          >
            <Text style={{ color: COLORS.text, fontWeight: '700', fontSize: 12 }}>Cancel</Text>
          </TouchableOpacity>
        </View>
        {hasRenameOf(factor) && (
          <TouchableOpacity onPress={revert} disabled={busy} style={{ marginTop: 6, alignSelf: 'flex-start' }}>
            <Text style={[styles.factorMeta, { color: COLORS.primary, textDecorationLine: 'underline' }]}>
              ↺ Revert to original: “{originalNameOf(factor)}”
            </Text>
          </TouchableOpacity>
        )}
      </View>
    );
  }

  return (
    <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <View style={{ flex: 1 }}>
        <Text style={[styles.factorName, { flex: 1 }]} numberOfLines={2}>
          {displayNameOf(factor)}
        </Text>
        {hasRenameOf(factor) && (
          <Text style={[styles.factorMeta, { color: COLORS.textDim, fontStyle: 'italic' }]}>
            Originally: “{originalNameOf(factor)}”
          </Text>
        )}
      </View>
      <TouchableOpacity
        onPress={startEdit}
        style={{ padding: 6 }}
        accessibilityLabel="Rename this factor"
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name="pencil-outline" size={16} color={COLORS.primary} />
      </TouchableOpacity>
    </View>
  );
}

export function FactorAssessmentCard({ factor, factorIndex, options, cells, displayName, subs, subDisplayNameOf, subHasRenameOf, subOriginalNameOf, onFactorUpdate, onCellUpdate }: {
  factor: Factor; factorIndex?: number; options: OptionT[]; cells: Record<string, Record<string, Cell>>;
  /** Pre-computed display label (display_name || name). */
  displayName?: string;
  /** Read-only sub-factor display props (Step 8 — sub-factors visible context, not rated). */
  subs?: Factor[];
  subDisplayNameOf?: (f: Factor) => string;
  subHasRenameOf?: (f: Factor) => boolean;
  subOriginalNameOf?: (f: Factor) => string;
  onFactorUpdate: (p: any) => void; onCellUpdate: (oid: string, p: any) => void;
}) {
  return (
    <View style={styles.factorCard}>
      <View style={styles.factorCardHeader}>
        <Text style={styles.rankBadge}>Factor #{factorIndex ?? factor.priority_rank}</Text>
        <Text style={[styles.factorName, { flex: 1 }]}>{displayName || factor.name}</Text>
      </View>

      {/* Type & Improvable */}
      <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', marginVertical: 6 }}>
        {(['subjective', 'objective'] as const).map(t => (
          <TouchableOpacity key={t} style={[styles.tinyChip, factor.factor_type === t && styles.tinyChipOn]}
            onPress={() => onFactorUpdate({ factor_type: t })}>
            <Text style={[styles.tinyChipText, factor.factor_type === t && { color: '#fff' }]}>{t[0].toUpperCase() + t.slice(1)}</Text>
          </TouchableOpacity>
        ))}
        {(['n', 'y', 'y_bf'] as const).map(im => (
          <TouchableOpacity key={im} style={[styles.tinyChip, factor.improvable === im && styles.tinyChipOn]}
            onPress={() => onFactorUpdate({ improvable: im })}>
            <Text style={[styles.tinyChipText, factor.improvable === im && { color: '#fff' }]}>
              {im === 'n' ? 'Not improvable' : im === 'y' ? 'Improvable' : 'Improvable (self)'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Expectations / market */}
      <View style={{ flexDirection: 'row', gap: 6 }}>
        <TextInput style={[styles.inputSm, { flex: 1 }]} placeholder="My Expectation"
          defaultValue={factor.my_expectation || ''}
          onEndEditing={e => onFactorUpdate({ my_expectation: e.nativeEvent.text })} />
        <TextInput style={[styles.inputSm, { flex: 1 }]} placeholder="Others' Expectation"
          defaultValue={factor.others_expectations || ''}
          onEndEditing={e => onFactorUpdate({ others_expectations: e.nativeEvent.text })} />
        <TextInput style={[styles.inputSm, { flex: 1 }]} placeholder="Market Standard"
          defaultValue={factor.market_standard || ''}
          onEndEditing={e => onFactorUpdate({ market_standard: e.nativeEvent.text })} />
      </View>

      {/* Gap & rating */}
      <View style={{ flexDirection: 'row', gap: 6, marginTop: 6, alignItems: 'center' }}>
        <Text style={styles.cellLabel}>Std</Text>
        <TextInput style={[styles.inputSm, { width: 56 }]} keyboardType="number-pad"
          defaultValue={String(factor.std_rating)}
          onEndEditing={e => onFactorUpdate({ std_rating: parseInt(e.nativeEvent.text, 10) || 0 })} />
        <Text style={styles.cellLabel}>Gap %</Text>
        <TextInput style={[styles.inputSm, { width: 56 }]} keyboardType="decimal-pad"
          defaultValue={String(factor.realistic_gap_pct ?? 0)}
          onEndEditing={e => onFactorUpdate({ realistic_gap_pct: parseFloat(e.nativeEvent.text) || 0 })} />
        <Text style={styles.cellLabel}>Realistic</Text>
        <Text style={[styles.cellValue, { width: 40 }]}>{factor.realistic_rating ?? factor.std_rating}</Text>
      </View>

      {/* Per-option Improvement % (Case-2 input — DELTA in percentage points).
          - User enters a SIGNED delta on top of Step 7's Assess %.
              +20  → option will be 20pp BETTER post-improvement
              −10  → option will be 10pp WORSE post-improvement
               0  → no change (falls back to Step 7 value).
          - Green border + ▲ if positive, Red border + ▼ if negative, gray dash if zero/empty.
          - Allowed range: −100 to +100 (with 1-decimal precision).
          - Uses DebouncedInput so values persist on every keystroke (600ms
            debounce + flush on blur/unmount). This fixes the bug where
            clicking "Recompute" without first blurring the input caused
            the typed value to be lost. */}
      {options.map(o => {
        const c = (cells[o.id] || {})[factor.id] || { assessment_pct: 0, improvement_pct: 0, satisfaction_pct: 0, cell_value: 0, satisfaction_value: 0 };
        const baseline = Number(c.assessment_pct) || 0;
        const delta = Number(c.improvement_pct) || 0;
        const effective = Math.max(0, Math.min(100, baseline + delta));
        const isPos = delta > 0.05;
        const isNeg = delta < -0.05;
        const sign = isPos ? '+' : '';
        const trendColor = isPos ? COLORS.ok : isNeg ? COLORS.con : COLORS.textDim;
        const trendIcon = isPos ? '▲' : isNeg ? '▼' : '–';
        const bgTint = isPos ? '#ECFDF5' : isNeg ? '#FEF2F2' : '#FFFFFF';
        return (
          <View key={o.id} style={styles.assessRow}>
            <Text style={styles.assessOpt}>{o.name}</Text>
            <TextInput style={[styles.inputSm, { width: 80 }]} placeholder="Actual"
              defaultValue={c.actual_value || ''}
              onEndEditing={e => onCellUpdate(o.id, { actual_value: e.nativeEvent.text })} />
            <Text style={styles.cellLabel}>Improvement %</Text>
            <DebouncedInput
              value={delta === 0 ? '' : String(delta)}
              placeholder="0"
              keyboardType="numbers-and-punctuation"
              style={[
                styles.inputSm,
                { width: 64, backgroundColor: bgTint, color: trendColor, fontWeight: '700' },
                isPos && { borderColor: COLORS.ok, borderWidth: 1.5 },
                isNeg && { borderColor: COLORS.con, borderWidth: 1.5 },
              ]}
              onSave={(text) => {
                const t = text.trim();
                if (t === '' || t === '-' || t === '+') {
                  onCellUpdate(o.id, { improvement_pct: 0 });
                  return;
                }
                let v = parseFloat(t);
                if (Number.isNaN(v)) v = 0;
                // Clamp to ±100 and round to 1 decimal
                v = Math.max(-100, Math.min(100, v));
                v = Math.round(v * 10) / 10;
                onCellUpdate(o.id, { improvement_pct: v });
              }}
            />
            <Text style={[styles.cellValue, { color: trendColor, fontWeight: '700' }]}>
              {trendIcon} {sign}{Math.abs(delta) < 0.05 ? '0' : delta.toFixed(1)} → {effective.toFixed(0)}
            </Text>
          </View>
        );
      })}

      {/* Step 8 — sub-factors shown read-only inside the parent card,
          serving as context for the user while they rate the parent. */}
      {subs && subs.length > 0 && (
        <SubFactorReadOnlyList
          subs={subs}
          displayNameOf={subDisplayNameOf || ((f) => f.name)}
          hasRenameOf={subHasRenameOf || (() => false)}
          originalNameOf={subOriginalNameOf || ((f) => f.name)}
          defaultOpen={false}
          label="Sub-factors (rated together with parent)"
        />
      )}
    </View>
  );
}

/**
 * Reusable accordion for Step 6 (Mandatory/Optional) — and any other place
 * where only MAIN factors should expose controls but the user still wants
 * the ability to peek at their sub-factors for context.
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────────────┐
 *   │ ▸  Factor name (from displayNameOf)             [A] [B] etc. │
 *   └──────────────────────────────────────────────────────────────┘
 *   (expanded)
 *   ↳ Sub-factor 1
 *   ↳ Sub-factor 2
 *
 * Children passed in via `children` slot are the action controls
 * (e.g. the A/B buttons in Step 6). They sit on the right of the row.
 */
export function MainFactorWithSubs({
  factor,
  subs,
  displayNameOf,
  hasRenameOf,
  originalNameOf,
  children,
}: {
  factor: Factor;
  subs: Factor[];
  displayNameOf: (f: Factor) => string;
  hasRenameOf: (f: Factor) => boolean;
  originalNameOf: (f: Factor) => string;
  children?: React.ReactNode;
}) {
  // Default to COLLAPSED so the page looks tidy at first glance —
  // exactly what the user asked for ("hidden by default, expandable").
  const [open, setOpen] = useState(false);
  const hasSubs = subs.length > 0;
  return (
    <View style={styles.factorCard}>
      <View style={styles.factorRow}>
        {hasSubs ? (
          <TouchableOpacity
            onPress={() => setOpen(o => !o)}
            style={{ marginRight: 4, padding: 4 }}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            accessibilityLabel={open ? 'Collapse sub-factors' : 'Expand sub-factors'}
          >
            <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={18} color={COLORS.textDim} />
          </TouchableOpacity>
        ) : (
          <View style={{ width: 26 }} />
        )}
        <View style={{ flex: 1 }}>
          <Text style={styles.factorName} numberOfLines={2}>{displayNameOf(factor)}</Text>
          {hasRenameOf(factor) && (
            <Text style={[styles.factorMeta, { color: COLORS.textDim, fontStyle: 'italic' }]}>
              Originally: “{originalNameOf(factor)}”
            </Text>
          )}
          {hasSubs && (
            <Text style={[styles.factorMeta, { color: COLORS.textDim }]}>
              {subs.length} sub-factor{subs.length === 1 ? '' : 's'} · inherits this factor’s classification
            </Text>
          )}
        </View>
        {children}
      </View>
      {open && hasSubs && (
        <View style={{ paddingLeft: 32, paddingTop: 6 }}>
          {subs.map(s => (
            <View key={s.id} style={[styles.subFactorReadRow]}>
              <View style={[styles.sourceTag, { backgroundColor: s.source === 'pro' ? COLORS.pro : s.source === 'con' ? COLORS.con : COLORS.direct }]}>
                <Text style={styles.sourceTagText}>{s.source === 'direct' ? 'D' : s.source === 'pro' ? 'P' : 'C'}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.factorName} numberOfLines={2}>{displayNameOf(s)}</Text>
                {hasRenameOf(s) && (
                  <Text style={[styles.factorMeta, { color: COLORS.textDim, fontStyle: 'italic' }]}>
                    Originally: “{originalNameOf(s)}”
                  </Text>
                )}
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

/**
 * Step 7 — EDITABLE sub-factor accordion (collapsed by default).
 *
 * Each expanded sub-factor renders its own mini-card with:
 *   - Expected value + Unit (saved to factor.expected_value / factor.unit)
 *   - Per-option: Actual value (saved to cell.actual_value), Assess %
 *     (saved to cell.assessment_pct).
 *
 * IMPORTANT: per the wizard contract, sub-factor cells are CAPTURED but DO
 * NOT contribute to the option score — the backend aggregator filters them
 * out (see compute_option_rollups → scoring_factors). They're collected
 * purely as decision-support context for the user.
 */
export function SubFactorEditableList({
  subs,
  options,
  assessments,
  displayNameOf,
  hasRenameOf,
  originalNameOf,
  onFactorPatch,
  onCellPatch,
  onAIAssess,
  aiBusy,
}: {
  subs: Factor[];
  options: OptionT[];
  assessments: Record<string, Record<string, Cell>>;
  displayNameOf: (f: Factor) => string;
  hasRenameOf: (f: Factor) => boolean;
  originalNameOf: (f: Factor) => string;
  onFactorPatch: (factorId: string, patch: any) => void;
  onCellPatch: (optionId: string, factorId: string, patch: any) => void;
  onAIAssess: (optionId: string, factorId: string, actual?: string) => void;
  aiBusy: Record<string, boolean>;
}) {
  const [open, setOpen] = useState(false);
  if (!subs || subs.length === 0) return null;
  return (
    <View style={{ marginTop: 10, paddingTop: 8, borderTopWidth: 1, borderTopColor: COLORS.border }}>
      <TouchableOpacity
        onPress={() => setOpen(o => !o)}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
        accessibilityLabel={open ? 'Collapse sub-factors' : 'Expand sub-factors'}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={16} color={COLORS.textDim} />
        <Text style={[styles.factorMeta, { color: COLORS.textDim, fontWeight: '600' }]}>
          Sub-factors ({subs.length}) — rate & weight; rolls up into this factor
        </Text>
      </TouchableOpacity>
      {open && (
        <View style={{ paddingLeft: 14, paddingTop: 6, gap: 12 }}>
          {subs.map(s => (
            <View key={s.id} style={styles.subFactorEditCard}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <View style={[styles.sourceTag, { backgroundColor: s.source === 'pro' ? COLORS.pro : s.source === 'con' ? COLORS.con : COLORS.direct }]}>
                  <Text style={styles.sourceTagText}>{s.source === 'direct' ? 'D' : s.source === 'pro' ? 'P' : 'C'}</Text>
                </View>
                <Text style={[styles.factorName, { flex: 1 }]} numberOfLines={2}>{displayNameOf(s)}</Text>
                {s.weight ? (
                  <View style={pcWeightStyles.totalBadge}>
                    <Text style={pcWeightStyles.totalText}>wt {s.weight}%</Text>
                  </View>
                ) : null}
              </View>
              {hasRenameOf(s) && (
                <Text style={[styles.factorMeta, { color: COLORS.textDim, fontStyle: 'italic' }]}>
                  Originally: “{originalNameOf(s)}”
                </Text>
              )}
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                <Text style={styles.cellLabel}>Expected</Text>
                <DebouncedInput
                  style={[styles.inputSm, { width: 88 }]}
                  placeholder="optional"
                  placeholderTextColor={COLORS.textDim}
                  value={s.expected_value || ''}
                  onSave={(text) => onFactorPatch(s.id, { expected_value: text || null })}
                />
                <Text style={styles.cellLabel}>Unit</Text>
                <DebouncedInput
                  style={[styles.inputSm, { width: 64 }]}
                  placeholder="e.g., hr"
                  placeholderTextColor={COLORS.textDim}
                  value={s.unit || ''}
                  onSave={(text) => onFactorPatch(s.id, { unit: text || null })}
                />
              </View>
              {options.map(o => {
                const cell = (assessments[o.id] || {})[s.id] || { assessment_pct: 0, cell_value: 0, actual_value: '' };
                return (
                  <View key={o.id} style={[styles.assessRow, { flexWrap: 'wrap' }]}>
                    <Text style={styles.assessOpt}>{o.name}</Text>
                    <Text style={styles.cellLabel}>Actual</Text>
                    <DebouncedInput
                      style={[styles.inputSm, { width: 80 }]}
                      placeholder="value"
                      placeholderTextColor={COLORS.textDim}
                      value={cell.actual_value || ''}
                      onSave={(text) => onCellPatch(o.id, s.id, { actual_value: text })}
                    />
                    {s.unit ? <Text style={[styles.cellLabel, { color: COLORS.textDim }]}>{s.unit}</Text> : null}
                    <LmhAiButtons
                      current={Number(cell.assessment_pct ?? 0)}
                      onPick={(p) => onCellPatch(o.id, s.id, { assessment_pct: p })}
                      onAI={() => onAIAssess(o.id, s.id, cell.actual_value || '')}
                      busy={!!aiBusy[`${o.id}_${s.id}`]}
                    />
                    <Text style={styles.cellLabel}>Custom %</Text>
                    <DebouncedInput
                      style={[styles.inputSm, { width: 56 }]}
                      keyboardType="number-pad"
                      value={String(cell.assessment_pct ?? 0)}
                      onSave={(text) => onCellPatch(o.id, s.id, { assessment_pct: Math.max(0, Math.min(100, parseInt(text, 10) || 0)) })}
                    />
                    <Text style={[styles.cellValue, { color: COLORS.textDim }]}>
                      {s.weight ? `× ${s.weight}%` : 'equal wt'}
                    </Text>
                  </View>
                );
              })}
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

/**
 * Compact, COLLAPSED-by-default list of sub-factors for embedding inside
 * a parent's card (Steps 7 & 8). Sub-factors are read-only — the user
 * rates / prioritises at the parent level for now.
 */
export function SubFactorReadOnlyList({
  subs,
  displayNameOf,
  hasRenameOf,
  originalNameOf,
  defaultOpen = false,
  label,
}: {
  subs: Factor[];
  displayNameOf: (f: Factor) => string;
  hasRenameOf: (f: Factor) => boolean;
  originalNameOf: (f: Factor) => string;
  defaultOpen?: boolean;
  label?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!subs || subs.length === 0) return null;
  return (
    <View style={{ marginTop: 10, paddingTop: 8, borderTopWidth: 1, borderTopColor: COLORS.border }}>
      <TouchableOpacity
        onPress={() => setOpen(o => !o)}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}
        accessibilityLabel={open ? 'Collapse sub-factors' : 'Expand sub-factors'}
      >
        <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={16} color={COLORS.textDim} />
        <Text style={[styles.factorMeta, { color: COLORS.textDim, fontWeight: '600' }]}>
          {label || `Sub-factors (${subs.length})`}
        </Text>
      </TouchableOpacity>
      {open && (
        <View style={{ paddingLeft: 22, paddingTop: 6 }}>
          {subs.map(s => (
            <View key={s.id} style={[styles.subFactorReadRow]}>
              <View style={[styles.sourceTag, { backgroundColor: s.source === 'pro' ? COLORS.pro : s.source === 'con' ? COLORS.con : COLORS.direct }]}>
                <Text style={styles.sourceTagText}>{s.source === 'direct' ? 'D' : s.source === 'pro' ? 'P' : 'C'}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.factorName} numberOfLines={2}>{displayNameOf(s)}</Text>
                {hasRenameOf(s) && (
                  <Text style={[styles.factorMeta, { color: COLORS.textDim, fontStyle: 'italic' }]}>
                    Originally: “{originalNameOf(s)}”
                  </Text>
                )}
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

/**
 * L / M / H + AI satisfaction controls (parity with My Dezider). Pairs with a
 * Custom % input that the caller renders separately. `current` highlights the
 * active L/M/H chip; `onAI` triggers backend LLM assessment.
 */
export function LmhAiButtons({ current, onPick, onAI, busy }: {
  current: number;
  onPick: (pct: number) => void;
  onAI: () => void;
  busy?: boolean;
}) {
  return (
    <View style={pcAssess.row}>
      {(['L', 'M', 'H'] as const).map(k => {
        const v = LMH_VALUES[k];
        const active = Number(current) === v.percentage;
        return (
          <TouchableOpacity
            key={k}
            onPress={() => onPick(v.percentage)}
            style={[pcAssess.lmh, active && { backgroundColor: v.color, borderColor: v.color }]}
            accessibilityLabel={`${v.label} satisfaction`}
          >
            <Text style={[pcAssess.lmhText, active && { color: '#fff' }]}>{k}</Text>
          </TouchableOpacity>
        );
      })}
      <TouchableOpacity onPress={onAI} disabled={busy} style={pcAssess.aiBtn} accessibilityLabel="AI assess satisfaction">
        {busy ? <ActivityIndicator size="small" color="#7C3AED" /> : (
          <>
            <Ionicons name="sparkles" size={12} color="#7C3AED" />
            <Text style={pcAssess.aiText}>AI</Text>
          </>
        )}
      </TouchableOpacity>
    </View>
  );
}
