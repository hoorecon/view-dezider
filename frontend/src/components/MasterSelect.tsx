/**
 * MasterSelect — searchable single/multi select backed by the /masters API.
 *
 * - mode="single": stores a string value (e.g. religion, caste, occupation)
 * - mode="multi":  stores a string[] (e.g. languages, skills, drives, traits)
 * - allowFreeType (default true): if the typed text matches no option, the user
 *   can add it as a custom value (preselect existing OR type your own).
 * - parent: filters options (used for Caste → filtered by selected Religion).
 *
 * Options are fetched once per type/parent and filtered client-side.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../utils/api';

type Props = {
  type: string;
  mode?: 'single' | 'multi';
  value: any;
  onChange: (v: any) => void;
  parent?: string | null;
  placeholder?: string;
  allowFreeType?: boolean;
  maxVisible?: number;
};

export default function MasterSelect({
  type,
  mode = 'single',
  value,
  onChange,
  parent = null,
  placeholder = 'Search or type…',
  allowFreeType = true,
  maxVisible = 14,
}: Props) {
  const [options, setOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [focused, setFocused] = useState(false);

  const selectedArr: string[] = mode === 'multi'
    ? (Array.isArray(value) ? value : [])
    : (value ? [String(value)] : []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        let url = `/masters/${type}?limit=2000`;
        if (parent) url += `&parent=${encodeURIComponent(parent)}`;
        const res = await api.get(url);
        if (!cancelled) setOptions((res.data.items || []).map((i: any) => i.value));
      } catch (e) {
        if (!cancelled) setOptions([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [type, parent]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = q ? options.filter(o => o.toLowerCase().includes(q)) : options;
    // de-dupe against already selected for multi
    const avail = mode === 'multi' ? base.filter(o => !selectedArr.includes(o)) : base;
    return avail.slice(0, maxVisible);
  }, [query, options, selectedArr, mode, maxVisible]);

  const exactExists = useMemo(() => {
    const q = query.trim().toLowerCase();
    return !!q && options.some(o => o.toLowerCase() === q);
  }, [query, options]);

  const pick = (v: string) => {
    if (mode === 'multi') {
      const cur = Array.isArray(value) ? value : [];
      if (!cur.includes(v)) onChange([...cur, v]);
      setQuery('');
    } else {
      onChange(v);
      setQuery('');
      setFocused(false);
    }
  };

  const removeSelected = (v: string) => {
    if (mode === 'multi') {
      onChange((Array.isArray(value) ? value : []).filter((x: string) => x !== v));
    } else {
      onChange('');
    }
  };

  const showAddFreeType =
    allowFreeType && query.trim().length > 0 && !exactExists &&
    !(mode === 'multi' && selectedArr.includes(query.trim()));

  const showList = focused || query.trim().length > 0;

  return (
    <View style={styles.wrap}>
      {/* Selected chips */}
      {selectedArr.length > 0 && (
        <View style={styles.selectedRow}>
          {selectedArr.map((v) => (
            <View key={v} style={styles.selectedChip}>
              <Text style={styles.selectedChipText}>{v}</Text>
              <TouchableOpacity onPress={() => removeSelected(v)} hitSlop={{top:8,bottom:8,left:8,right:8}}>
                <Ionicons name="close-circle" size={16} color="#FFFFFFcc" />
              </TouchableOpacity>
            </View>
          ))}
        </View>
      )}

      {/* Search input (hidden for single-select once a value is chosen, unless re-editing) */}
      {(mode === 'multi' || selectedArr.length === 0 || focused) && (
        <View style={styles.inputRow}>
          <Ionicons name="search" size={16} color="#94A3B8" />
          <TextInput
            style={styles.input}
            placeholder={placeholder}
            placeholderTextColor="#94A3B8"
            value={query}
            onChangeText={setQuery}
            onFocus={() => setFocused(true)}
            autoCapitalize="words"
          />
          {loading && <ActivityIndicator size="small" color="#94A3B8" />}
        </View>
      )}

      {/* Options dropdown */}
      {showList && (
        <View style={styles.optionsBox}>
          {showAddFreeType && (
            <TouchableOpacity style={styles.addRow} onPress={() => pick(query.trim())}>
              <Ionicons name="add-circle" size={16} color="#6366F1" />
              <Text style={styles.addRowText}>Add “{query.trim()}”</Text>
            </TouchableOpacity>
          )}
          {filtered.map((o) => (
            <TouchableOpacity key={o} style={styles.optionRow} onPress={() => pick(o)}>
              <Text style={styles.optionText}>{o}</Text>
            </TouchableOpacity>
          ))}
          {!loading && filtered.length === 0 && !showAddFreeType && (
            <Text style={styles.emptyText}>No matches</Text>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 8 },
  selectedRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 6 },
  selectedChip: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#6366F1', paddingVertical: 6, paddingHorizontal: 10, borderRadius: 16 },
  selectedChipText: { color: '#FFF', fontSize: 12, fontWeight: '600' },
  inputRow: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8, paddingHorizontal: 10, backgroundColor: '#F8FAFC' },
  input: { flex: 1, paddingVertical: 9, fontSize: 14, color: '#0F172A' },
  optionsBox: { borderWidth: 1, borderColor: '#E2E8F0', borderTopWidth: 0, borderBottomLeftRadius: 8, borderBottomRightRadius: 8, backgroundColor: '#FFF', maxHeight: 220 },
  optionRow: { paddingVertical: 9, paddingHorizontal: 12, borderTopWidth: 1, borderTopColor: '#F1F5F9' },
  optionText: { fontSize: 13, color: '#334155' },
  addRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 9, paddingHorizontal: 12, backgroundColor: '#EEF2FF' },
  addRowText: { fontSize: 13, color: '#6366F1', fontWeight: '600' },
  emptyText: { fontSize: 12, color: '#94A3B8', padding: 12 },
});
