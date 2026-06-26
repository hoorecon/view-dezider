import React, { useEffect, useRef, useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, StyleSheet,
  ActivityIndicator, useWindowDimensions, Platform,
} from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import DraggableFlatList, { RenderItemParams } from 'react-native-draggable-flatlist';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';

interface Props {
  visible: boolean;
  factors: string[];
  options: string[];
  busy?: boolean;
  primary?: string;
  onCancel: () => void;
  onConfirm: (factors: string[], options: string[]) => void;
}

type Item = { id: string; name: string };
let _seq = 0;
const toItems = (arr: string[]): Item[] =>
  arr.filter(s => s != null).map(name => ({ id: `it_${_seq++}`, name }));

/**
 * Review-before-merge for AI-conversation imports (ChatGPT / Claude).
 * Lists the detected OPTIONS (drag to reorder — the order is kept in Step 6, so
 * the most-preferred option can be placed first) and FACTORS, each renamable or
 * removable, before anything is written into the decision.
 */
export default function ImportReviewModal({
  visible, factors, options, busy, primary = COLORS.primary, onCancel, onConfirm,
}: Props) {
  const [opts, setOpts] = useState<Item[]>([]);
  const [facs, setFacs] = useState<Item[]>([]);
  const { height: vh } = useWindowDimensions();
  const didInit = useRef(false);

  useEffect(() => {
    if (visible && !didInit.current) {
      setOpts(toItems(options));
      setFacs(toItems(factors));
      didInit.current = true;
    }
    if (!visible) didInit.current = false;
  }, [visible, options, factors]);

  const setOptName = (id: string, name: string) =>
    setOpts(prev => prev.map(o => (o.id === id ? { ...o, name } : o)));
  const setFacName = (id: string, name: string) =>
    setFacs(prev => prev.map(f => (f.id === id ? { ...f, name } : f)));

  const total = [...opts, ...facs].filter(i => i.name.trim()).length;
  const handleConfirm = () => {
    if (busy || total < 1) return;
    onConfirm(
      facs.map(f => f.name.trim()).filter(Boolean),
      opts.map(o => o.name.trim()).filter(Boolean),
    );
  };

  const renderOption = ({ item, getIndex, drag, isActive }: RenderItemParams<Item>) => {
    const idx = getIndex() ?? 0;
    return (
      <View style={[styles.row, isActive && styles.rowActive]} testID={`review-option-row-${idx}`}>
        <TouchableOpacity
          testID={`review-option-drag-${idx}`}
          onPressIn={drag}
          onLongPress={drag}
          disabled={!!busy}
          hitSlop={{ top: 8, bottom: 8, left: 6, right: 6 }}
          style={styles.dragHandle}
        >
          <Ionicons name="reorder-three" size={22} color={COLORS.textMuted} />
        </TouchableOpacity>
        <View style={[styles.rank, { backgroundColor: primary }]}>
          <Text style={styles.rankText}>{idx + 1}</Text>
        </View>
        <TextInput
          testID={`review-option-input-${idx}`}
          style={styles.input}
          value={item.name}
          onChangeText={t => setOptName(item.id, t)}
          placeholder="Option name"
          placeholderTextColor="#9CA3AF"
        />
        <TouchableOpacity
          testID={`review-option-remove-${idx}`}
          onPress={() => setOpts(prev => prev.filter(o => o.id !== item.id))}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          style={styles.removeBtn}
        >
          <Ionicons name="close-circle" size={20} color={COLORS.textMuted} />
        </TouchableOpacity>
      </View>
    );
  };

  const Header = (
    <View>
      <Text style={styles.sub}>
        We read these from your conversation. Rename, remove, or drag options to set their order
        (the first option is treated as most preferred in Step 6), then add them.
      </Text>
      <Text style={styles.sectionLabel}>Options ({opts.length}) · drag to reorder</Text>
      {opts.length === 0 && <Text style={styles.empty}>No options detected.</Text>}
    </View>
  );

  const Footer = (
    <View>
      <TouchableOpacity testID="review-add-option" style={styles.addRow}
        onPress={() => setOpts(prev => [...prev, ...toItems([''])])}>
        <Ionicons name="add" size={16} color={primary} />
        <Text style={[styles.addText, { color: primary }]}>Add an option</Text>
      </TouchableOpacity>

      <Text style={[styles.sectionLabel, { marginTop: 14 }]}>Factors ({facs.length})</Text>
      {facs.length === 0 && <Text style={styles.empty}>No factors detected.</Text>}
      {facs.map((f, i) => (
        <View style={styles.row} key={f.id}>
          <View style={styles.dragHandlePlaceholder} />
          <TextInput
            testID={`review-factor-input-${i}`}
            style={styles.input}
            value={f.name}
            onChangeText={t => setFacName(f.id, t)}
            placeholder="Factor name"
            placeholderTextColor="#9CA3AF"
          />
          <TouchableOpacity
            testID={`review-factor-remove-${i}`}
            onPress={() => setFacs(prev => prev.filter(x => x.id !== f.id))}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            style={styles.removeBtn}
          >
            <Ionicons name="close-circle" size={20} color={COLORS.textMuted} />
          </TouchableOpacity>
        </View>
      ))}
      <TouchableOpacity testID="review-add-factor" style={styles.addRow}
        onPress={() => setFacs(prev => [...prev, ...toItems([''])])}>
        <Ionicons name="add" size={16} color={primary} />
        <Text style={[styles.addText, { color: primary }]}>Add a factor</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <GestureHandlerRootView style={styles.overlay}>
        <View style={[styles.card, { maxHeight: Math.min(vh - 40, vh * 0.9) }]} testID="import-review-modal">
          <View style={styles.header}>
            <Ionicons name="create-outline" size={22} color={primary} />
            <Text style={styles.title}>Review before adding</Text>
            <TouchableOpacity testID="import-review-close" onPress={onCancel} style={styles.closeBtn}>
              <Ionicons name="close" size={22} color={COLORS.textMuted} />
            </TouchableOpacity>
          </View>

          <DraggableFlatList
            data={opts}
            keyExtractor={(it) => it.id}
            renderItem={renderOption}
            onDragEnd={({ data }) => setOpts(data)}
            ListHeaderComponent={Header}
            ListFooterComponent={Footer}
            activationDistance={Platform.OS === 'web' ? 1 : 8}
            containerStyle={{ maxHeight: vh * 0.6 }}
            showsVerticalScrollIndicator={false}
          />

          <View style={styles.footer}>
            <TouchableOpacity testID="import-review-cancel" style={styles.cancelBtn} onPress={onCancel} disabled={busy}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="import-review-confirm"
              style={[styles.confirmBtn, { backgroundColor: primary }, (total < 1 || busy) && { opacity: 0.5 }]}
              onPress={handleConfirm}
              disabled={total < 1 || !!busy}
            >
              {busy ? <ActivityIndicator color="#fff" size="small" /> : (
                <><Ionicons name="checkmark" size={15} color="#fff" />
                  <Text style={styles.confirmText}>Add {total} to decision</Text></>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </GestureHandlerRootView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  card: { width: '100%', maxWidth: 560, backgroundColor: '#fff', borderRadius: 18, padding: 18,
    ...Platform.select({ web: { boxShadow: '0 10px 40px rgba(0,0,0,0.2)' }, default: { elevation: 8 } }) },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  title: { flex: 1, fontSize: 17, fontWeight: '700', color: '#0F172A', marginLeft: 6 },
  closeBtn: { padding: 4 },
  sub: { fontSize: 12.5, color: COLORS.textSecondary, marginTop: 6, marginBottom: 6, lineHeight: 18 },
  sectionLabel: { fontSize: 12, fontWeight: '800', color: '#334155', textTransform: 'uppercase', letterSpacing: 0.4, marginTop: 4, marginBottom: 6 },
  empty: { fontSize: 12.5, color: COLORS.textMuted, fontStyle: 'italic', marginBottom: 4 },
  row: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 6 },
  rowActive: { opacity: 0.92, backgroundColor: '#EFF6FF', borderRadius: 10 },
  dragHandle: { paddingHorizontal: 2, paddingVertical: 4 },
  dragHandlePlaceholder: { width: 26 },
  rank: { width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  rankText: { color: '#fff', fontSize: 11, fontWeight: '800' },
  input: { flex: 1, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12,
    paddingVertical: Platform.OS === 'ios' ? 11 : 8, fontSize: 14, color: '#0F172A', backgroundColor: '#F8FAFC' },
  removeBtn: { padding: 2 },
  addRow: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 6 },
  addText: { fontSize: 13, fontWeight: '700' },
  footer: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 12 },
  cancelBtn: { paddingVertical: 11, paddingHorizontal: 18, borderRadius: 10, backgroundColor: '#F1F5F9' },
  cancelText: { fontSize: 14, fontWeight: '700', color: '#475569' },
  confirmBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 11, paddingHorizontal: 18, borderRadius: 10 },
  confirmText: { fontSize: 14, fontWeight: '800', color: '#fff' },
});
