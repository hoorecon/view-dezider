/**
 * MetricsEditor — collects multiple structured metrics for the Goal Setter's
 * "Measurable" section. Each metric row captures:
 *   - Name, Unit, Type (Quantitative / Qualitative)
 *   - Operator (>=, <=, =, >, <)
 *   - Target value
 *   - Set By (default "Self", with contacts auto-suggest)
 *   - Owner's Role (optional)
 *
 * Patterned after the Dezider "Define Factor's Expected Value" step.
 */
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import api from '../utils/api';

export interface GoalMetric {
  id: string;
  name: string;
  unit: string;
  type: 'quantitative' | 'qualitative';
  operator: string; // >= <= = > <
  target_value: string;
  set_by: string;       // default "Self"
  set_by_contact_id?: string;
  owner_role?: string;  // optional
}

interface Props {
  value: GoalMetric[];
  onChange: (v: GoalMetric[]) => void;
}

const OPERATORS = ['>=', '<=', '=', '>', '<'];

function makeBlankMetric(): GoalMetric {
  return {
    id: `m_${Date.now().toString(36)}_${Math.floor(Math.random() * 9999)}`,
    name: '',
    unit: '',
    type: 'quantitative',
    operator: '>=',
    target_value: '',
    set_by: 'Self',
    owner_role: '',
  };
}

export default function MetricsEditor({ value, onChange }: Props) {
  const metrics = Array.isArray(value) ? value : [];

  const addMetric = () => onChange([...metrics, makeBlankMetric()]);
  const removeMetric = (id: string) => onChange(metrics.filter(m => m.id !== id));
  const updateMetric = (id: string, patch: Partial<GoalMetric>) =>
    onChange(metrics.map(m => (m.id === id ? { ...m, ...patch } : m)));

  if (metrics.length === 0) {
    return (
      <View style={styles.emptyWrap}>
        <Text style={styles.emptyHint}>
          No metrics yet. Add quantifiable measures so you can track progress objectively.
        </Text>
        <TouchableOpacity style={styles.addBtnPrimary} onPress={addMetric}>
          <Ionicons name="add-circle" size={16} color="#FFF" />
          <Text style={styles.addBtnPrimaryText}>Add First Metric</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View>
      {metrics.map((m, idx) => (
        <MetricRow
          key={m.id}
          index={idx}
          metric={m}
          onChange={(patch) => updateMetric(m.id, patch)}
          onRemove={() => removeMetric(m.id)}
        />
      ))}
      <TouchableOpacity style={styles.addBtnGhost} onPress={addMetric}>
        <Ionicons name="add" size={14} color={COLORS.primary} />
        <Text style={styles.addBtnGhostText}>Add another metric</Text>
      </TouchableOpacity>
    </View>
  );
}

function MetricRow({
  index,
  metric,
  onChange,
  onRemove,
}: {
  index: number;
  metric: GoalMetric;
  onChange: (patch: Partial<GoalMetric>) => void;
  onRemove: () => void;
}) {
  return (
    <View style={styles.row}>
      <View style={styles.rowHead}>
        <View style={styles.rowBadge}><Text style={styles.rowBadgeText}>#{index + 1}</Text></View>
        <TouchableOpacity onPress={onRemove} style={styles.removeBtn} accessibilityLabel="Remove metric">
          <Ionicons name="trash-outline" size={16} color={COLORS.error} />
        </TouchableOpacity>
      </View>

      {/* Name */}
      <Text style={styles.label}>Metric Name *</Text>
      <TextInput
        style={styles.input}
        value={metric.name}
        onChangeText={(t) => onChange({ name: t })}
        placeholder="e.g., Monthly Recurring Revenue"
        placeholderTextColor={COLORS.textMuted}
      />

      {/* Type segmented */}
      <Text style={styles.label}>Metric Type</Text>
      <View style={styles.segment}>
        {(['quantitative', 'qualitative'] as const).map(t => (
          <TouchableOpacity
            key={t}
            style={[styles.segmentBtn, metric.type === t && styles.segmentActive]}
            onPress={() => onChange({ type: t })}
          >
            <Text style={[styles.segmentText, metric.type === t && { color: '#FFF' }]}>
              {t === 'quantitative' ? 'Quantitative' : 'Qualitative'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Operator + Target + Unit row */}
      <View style={{ flexDirection: 'row', gap: 8, marginTop: 6 }}>
        <View style={{ width: 90 }}>
          <Text style={styles.label}>Operator</Text>
          <View style={styles.opGroup}>
            {OPERATORS.map(op => (
              <TouchableOpacity
                key={op}
                style={[styles.opBtn, metric.operator === op && styles.opBtnActive]}
                onPress={() => onChange({ operator: op })}
              >
                <Text style={[styles.opBtnText, metric.operator === op && { color: '#FFF' }]}>{op}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.label}>{metric.type === 'qualitative' ? 'Target State' : 'Target Value'}</Text>
          <TextInput
            style={styles.input}
            value={metric.target_value}
            onChangeText={(t) => onChange({ target_value: t })}
            placeholder={metric.type === 'qualitative' ? 'e.g., Excellent' : 'e.g., 120000'}
            placeholderTextColor={COLORS.textMuted}
            keyboardType={metric.type === 'qualitative' ? 'default' : 'numeric'}
          />
        </View>
        <View style={{ width: 90 }}>
          <Text style={styles.label}>Unit</Text>
          <TextInput
            style={styles.input}
            value={metric.unit}
            onChangeText={(t) => onChange({ unit: t })}
            placeholder={metric.type === 'qualitative' ? 'rating' : '₹ / hrs / kg'}
            placeholderTextColor={COLORS.textMuted}
          />
        </View>
      </View>

      {/* Set By — with contacts auto-suggest */}
      <Text style={styles.label}>Metric Set By</Text>
      <ContactPicker
        value={metric.set_by}
        onChange={(name, contactId) => onChange({ set_by: name, set_by_contact_id: contactId })}
      />

      {/* Owner Role optional */}
      <Text style={styles.label}>Metric Owner's Role <Text style={styles.opt}>(optional)</Text></Text>
      <TextInput
        style={styles.input}
        value={metric.owner_role || ''}
        onChangeText={(t) => onChange({ owner_role: t })}
        placeholder="e.g., Manager, Coach, Doctor"
        placeholderTextColor={COLORS.textMuted}
      />
    </View>
  );
}

/* ── Contacts auto-suggest picker ───────────────────────────────────── */
function ContactPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (name: string, contactId?: string) => void;
}) {
  const [query, setQuery] = useState(value || 'Self');
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);

  useEffect(() => { setQuery(value || 'Self'); }, [value]);

  useEffect(() => {
    if (!open) return;
    if (query === 'Self') { setResults([]); return; }
    let cancelled = false;
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await api.get('/contacts', { params: { search: query, limit: 6 } });
        if (!cancelled) setResults(res.data?.contacts || []);
      } catch (e) {
        if (!cancelled) setResults([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => { cancelled = true; clearTimeout(t); };
  }, [query, open]);

  const choose = (name: string, contactId?: string) => {
    setQuery(name);
    onChange(name, contactId);
    setOpen(false);
  };

  return (
    <View style={{ position: 'relative', zIndex: 2 }}>
      <View style={{ flexDirection: 'row', gap: 6 }}>
        <TextInput
          style={[styles.input, { flex: 1 }]}
          value={query}
          onChangeText={(t) => { setQuery(t); onChange(t); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder="Self or type a contact name"
          placeholderTextColor={COLORS.textMuted}
        />
        {query !== 'Self' && (
          <TouchableOpacity style={styles.resetBtn} onPress={() => choose('Self')}>
            <Text style={styles.resetBtnText}>Self</Text>
          </TouchableOpacity>
        )}
      </View>
      {open && query !== 'Self' && (results.length > 0 || loading) && (
        <View style={styles.suggestBox}>
          {loading && (
            <View style={styles.suggestRow}>
              <ActivityIndicator size="small" color={COLORS.primary} />
              <Text style={styles.suggestHint}>Searching contacts…</Text>
            </View>
          )}
          {results.map((c) => (
            <TouchableOpacity
              key={c.contact_id || c.id || c.name}
              style={styles.suggestRow}
              onPress={() => choose(c.name, c.contact_id || c.id)}
            >
              <Ionicons name="person-circle-outline" size={18} color={COLORS.primary} />
              <View style={{ flex: 1 }}>
                <Text style={styles.suggestName}>{c.name}</Text>
                {(c.profession || c.organization) && (
                  <Text style={styles.suggestSub}>
                    {[c.profession, c.organization].filter(Boolean).join(' · ')}
                  </Text>
                )}
              </View>
            </TouchableOpacity>
          ))}
          {!loading && results.length === 0 && (
            <View style={styles.suggestRow}>
              <Text style={styles.suggestHint}>No matches — name will be saved as plain text</Text>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  emptyWrap: {
    padding: 14,
    backgroundColor: '#F8FAFC',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    borderStyle: Platform.OS === 'web' ? ('dashed' as any) : 'solid',
    alignItems: 'center',
    gap: 8,
  },
  emptyHint: { fontSize: 12, color: COLORS.textMuted, textAlign: 'center' },
  addBtnPrimary: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#10B981', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8,
  },
  addBtnPrimaryText: { color: '#FFF', fontWeight: '700', fontSize: 13 },
  addBtnGhost: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    justifyContent: 'center',
    paddingVertical: 8, marginTop: 4,
    borderRadius: 8, borderWidth: 1, borderColor: COLORS.primary, borderStyle: 'dashed',
  },
  addBtnGhostText: { color: COLORS.primary, fontWeight: '600', fontSize: 12 },
  row: {
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    marginBottom: 8,
  },
  rowHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  rowBadge: { backgroundColor: '#DCFCE7', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  rowBadgeText: { color: '#16A34A', fontWeight: '700', fontSize: 11 },
  removeBtn: { padding: 6 },
  label: { fontSize: 11, color: COLORS.textMuted, marginTop: 6, marginBottom: 4, fontWeight: '600' },
  opt: { color: COLORS.textMuted, fontWeight: '400' },
  input: {
    borderWidth: 1,
    borderColor: '#E2E8F0',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    color: COLORS.textPrimary,
    backgroundColor: '#FFFFFF',
  },
  segment: { flexDirection: 'row', gap: 6 },
  segmentBtn: { flex: 1, paddingVertical: 7, alignItems: 'center', borderRadius: 8, backgroundColor: '#F1F5F9' },
  segmentActive: { backgroundColor: '#10B981' },
  segmentText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },
  opGroup: { flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  opBtn: { minWidth: 26, paddingHorizontal: 4, paddingVertical: 6, borderRadius: 6, backgroundColor: '#F1F5F9', alignItems: 'center' },
  opBtnActive: { backgroundColor: '#10B981' },
  opBtnText: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary },
  resetBtn: { paddingHorizontal: 10, paddingVertical: 6, backgroundColor: '#F1F5F9', borderRadius: 8, justifyContent: 'center' },
  resetBtnText: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary },

  // Suggestions dropdown
  suggestBox: {
    position: 'absolute',
    top: 42,
    left: 0,
    right: 0,
    backgroundColor: '#FFF',
    borderWidth: 1,
    borderColor: '#E2E8F0',
    borderRadius: 8,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowOffset: { width: 0, height: 2 },
    shadowRadius: 6,
    elevation: 6,
    zIndex: 100,
    maxHeight: 220,
  },
  suggestRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  suggestName: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  suggestSub: { fontSize: 11, color: COLORS.textMuted },
  suggestHint: { fontSize: 11, color: COLORS.textMuted },
});
