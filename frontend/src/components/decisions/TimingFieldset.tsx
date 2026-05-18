/**
 * TimingFieldset — deadline + impact-horizon picker.
 *
 * Used in PRR, Solution Finder, and Conflict Breaker create forms.
 * Renders deadline date input + horizon value/unit selector +
 * grey-text reference presets (Life Partner 30-40 yrs, etc.).
 */
import React, { useMemo } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { useAuthStore } from '../../store/authStore';
import { formatLocalized, getDefaultDateFormat, addDaysISO } from '../../utils/dateLocalize';

export type HorizonUnit = 'days' | 'weeks' | 'months' | 'years';

export interface TimingValue {
  deadline_date: string | null;
  impact_horizon_value: number;
  impact_horizon_unit: HorizonUnit;
}

interface Props {
  value: TimingValue;
  onChange: (next: TimingValue) => void;
  /** Show suggestion chips below */
  showPresets?: boolean;
  /** Compact 1-line layout (for inline use) */
  compact?: boolean;
}

const HORIZON_PRESETS: Array<{ label: string; value: number; unit: HorizonUnit; hint: string }> = [
  { label: 'Quick',           value: 1,  unit: 'weeks',  hint: '< 1 month impact' },
  { label: 'Project',         value: 3,  unit: 'months', hint: '1-3 months' },
  { label: 'Career Move',     value: 10, unit: 'years',  hint: '5-15 years' },
  { label: 'Business Partner',value: 22, unit: 'years',  hint: '15-30 years' },
  { label: 'Life Partner',    value: 35, unit: 'years',  hint: '30-40 years' },
  { label: 'Investment',      value: 6,  unit: 'years',  hint: '3-10 years' },
];

const UNITS: HorizonUnit[] = ['days', 'weeks', 'months', 'years'];

export default function TimingFieldset({ value, onChange, showPresets = true, compact = false }: Props) {
  const user = useAuthStore(s => s.user);
  const dateFormat = useMemo(() => getDefaultDateFormat(user as any), [user]);
  const minDate = new Date().toISOString().slice(0, 10);

  return (
    <View style={[s.wrap, compact && s.wrapCompact]}>
      {!compact && <Text style={s.legend}>Timing</Text>}
      <View style={s.row}>
        <View style={{ flex: 1.1 }}>
          <Text style={s.fieldLabel}>Deadline to complete</Text>
          {Platform.OS === 'web' ? (
            <input
              type="date"
              value={value.deadline_date || ''}
              min={minDate}
              onChange={(e: any) => onChange({ ...value, deadline_date: e.target.value || null })}
              style={s.dateInputWeb as any}
              data-testid="timing-deadline-input"
            />
          ) : (
            <TextInput
              style={s.input}
              value={value.deadline_date || ''}
              onChangeText={(t) => onChange({ ...value, deadline_date: t })}
              placeholder="YYYY-MM-DD"
              placeholderTextColor={COLORS.textMuted}
              testID="timing-deadline-input"
            />
          )}
          {value.deadline_date && (
            <Text style={s.fieldHint}>{formatLocalized(value.deadline_date, dateFormat)}</Text>
          )}
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.fieldLabel}>Impact horizon</Text>
          <View style={s.horizonRow}>
            <TextInput
              style={[s.input, { flex: 0.6 }]}
              value={String(value.impact_horizon_value || '')}
              onChangeText={(t) => onChange({ ...value, impact_horizon_value: parseInt(t) || 0 })}
              placeholder="7"
              keyboardType="numeric"
              placeholderTextColor={COLORS.textMuted}
              testID="timing-horizon-value"
            />
            <View style={s.unitGroup}>
              {UNITS.map(u => {
                const active = value.impact_horizon_unit === u;
                return (
                  <TouchableOpacity
                    key={u}
                    onPress={() => onChange({ ...value, impact_horizon_unit: u })}
                    style={[s.unitChip, active && s.unitChipActive]}
                    testID={`timing-horizon-unit-${u}`}
                  >
                    <Text style={[s.unitChipText, active && s.unitChipTextActive]}>{u}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>
        </View>
      </View>

      {showPresets && (
        <View style={s.presetWrap}>
          <Text style={s.presetLegend}>Reference (tap to apply):</Text>
          <View style={s.presetChips}>
            {HORIZON_PRESETS.map(p => (
              <TouchableOpacity
                key={p.label}
                onPress={() => onChange({ ...value, impact_horizon_value: p.value, impact_horizon_unit: p.unit })}
                style={s.presetChip}
                testID={`timing-preset-${p.label.replace(/\s+/g,'-').toLowerCase()}`}
              >
                <Text style={s.presetChipText}>{p.label}</Text>
                <Text style={s.presetChipHint}>{p.hint}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={s.quickDeadlines}>
            <Text style={s.presetLegend}>Quick deadlines:</Text>
            {[
              { l: 'Today',  d: 0 },
              { l: '+3d',    d: 3 },
              { l: '+1w',    d: 7 },
              { l: '+1mo',   d: 30 },
              { l: '+3mo',   d: 90 },
            ].map(q => (
              <TouchableOpacity
                key={q.l}
                onPress={() => onChange({ ...value, deadline_date: addDaysISO(q.d) })}
                style={s.quickChip}
                testID={`timing-deadline-${q.l.toLowerCase().replace('+','plus-')}`}
              >
                <Ionicons name="time-outline" size={10} color={COLORS.textSecondary} />
                <Text style={s.quickChipText}>{q.l}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { backgroundColor: COLORS.white, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: COLORS.border, marginVertical: 8 },
  wrapCompact: { padding: 8 },
  legend: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary, textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 8 },
  row: { flexDirection: 'row', gap: 12 },
  fieldLabel: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 4 },
  fieldHint: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },
  input: { backgroundColor: '#F9FAFB', borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary },
  dateInputWeb: { backgroundColor: '#F9FAFB', borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, padding: 8, fontSize: 13, color: COLORS.textPrimary, width: '100%', fontFamily: 'inherit' },
  horizonRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 6 },
  unitGroup: { flex: 1, flexDirection: 'row', flexWrap: 'wrap', gap: 4 },
  unitChip: { paddingHorizontal: 8, paddingVertical: 6, borderRadius: 4, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F9FAFB' },
  unitChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  unitChipText: { fontSize: 10, fontWeight: '600', color: COLORS.textSecondary, textTransform: 'lowercase' },
  unitChipTextActive: { color: '#FFF' },

  presetWrap: { marginTop: 10 },
  presetLegend: { fontSize: 9, fontWeight: '600', color: COLORS.textMuted, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 },
  presetChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 8 },
  presetChip: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 4, backgroundColor: '#F1F5F9' },
  presetChipText: { fontSize: 10, fontWeight: '700', color: COLORS.textSecondary },
  presetChipHint: { fontSize: 9, color: COLORS.textMuted, marginTop: 1 },

  quickDeadlines: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 4 },
  quickChip: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 6, paddingVertical: 3, borderRadius: 4, backgroundColor: '#EEF2FF' },
  quickChipText: { fontSize: 10, fontWeight: '600', color: COLORS.primary },
});
