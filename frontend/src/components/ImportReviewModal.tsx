import React, { useEffect, useState } from 'react';
import {
  Modal, View, Text, TextInput, TouchableOpacity, ScrollView,
  StyleSheet, ActivityIndicator, useWindowDimensions, Platform,
} from 'react-native';
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

/**
 * Review-before-merge for AI-conversation imports (ChatGPT / Claude / Gemini).
 * Lists the detected OPTIONS and FACTORS so the user can rename or remove any
 * item in one tap before they are written into the decision (Step 2/6).
 */
export default function ImportReviewModal({
  visible, factors, options, busy, primary = COLORS.primary, onCancel, onConfirm,
}: Props) {
  const [opts, setOpts] = useState<string[]>([]);
  const [facs, setFacs] = useState<string[]>([]);
  const { height: vh } = useWindowDimensions();

  useEffect(() => {
    if (visible) {
      setOpts(options.filter(Boolean));
      setFacs(factors.filter(Boolean));
    }
  }, [visible, options, factors]);

  const editRow = (
    list: string[], setList: (v: string[]) => void, idx: number,
    val: string, testPrefix: string,
  ) => (
    <View style={styles.row} key={`${testPrefix}-${idx}`}>
      <TextInput
        testID={`${testPrefix}-input-${idx}`}
        style={styles.input}
        value={val}
        onChangeText={t => { const c = [...list]; c[idx] = t; setList(c); }}
        placeholder="Name"
        placeholderTextColor="#9CA3AF"
      />
      <TouchableOpacity
        testID={`${testPrefix}-remove-${idx}`}
        onPress={() => setList(list.filter((_, i) => i !== idx))}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        style={styles.removeBtn}
      >
        <Ionicons name="close-circle" size={20} color={COLORS.textMuted} />
      </TouchableOpacity>
    </View>
  );

  const total = opts.filter(s => s.trim()).length + facs.filter(s => s.trim()).length;
  const handleConfirm = () => {
    if (busy || total < 1) return;
    onConfirm(facs.map(s => s.trim()).filter(Boolean), opts.map(s => s.trim()).filter(Boolean));
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={styles.overlay}>
        <View style={[styles.card, { maxHeight: Math.min(vh - 40, vh * 0.9) }]} testID="import-review-modal">
          <View style={styles.header}>
            <Ionicons name="create-outline" size={22} color={primary} />
            <Text style={styles.title}>Review before adding</Text>
            <TouchableOpacity testID="import-review-close" onPress={onCancel} style={styles.closeBtn}>
              <Ionicons name="close" size={22} color={COLORS.textMuted} />
            </TouchableOpacity>
          </View>
          <Text style={styles.sub}>
            We read these from your conversation. Rename or remove any item, then add them to your decision.
          </Text>

          <ScrollView style={{ maxHeight: vh * 0.55 }} showsVerticalScrollIndicator={false}>
            <Text style={styles.sectionLabel}>Options ({opts.length})</Text>
            {opts.length === 0 && <Text style={styles.empty}>No options detected.</Text>}
            {opts.map((v, i) => editRow(opts, setOpts, i, v, 'review-option'))}
            <TouchableOpacity testID="review-add-option" style={styles.addRow} onPress={() => setOpts([...opts, ''])}>
              <Ionicons name="add" size={16} color={primary} />
              <Text style={[styles.addText, { color: primary }]}>Add an option</Text>
            </TouchableOpacity>

            <Text style={[styles.sectionLabel, { marginTop: 14 }]}>Factors ({facs.length})</Text>
            {facs.length === 0 && <Text style={styles.empty}>No factors detected.</Text>}
            {facs.map((v, i) => editRow(facs, setFacs, i, v, 'review-factor'))}
            <TouchableOpacity testID="review-add-factor" style={styles.addRow} onPress={() => setFacs([...facs, ''])}>
              <Ionicons name="add" size={16} color={primary} />
              <Text style={[styles.addText, { color: primary }]}>Add a factor</Text>
            </TouchableOpacity>
          </ScrollView>

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
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  card: { width: '100%', maxWidth: 560, backgroundColor: '#fff', borderRadius: 18, padding: 18,
    ...Platform.select({ web: { boxShadow: '0 10px 40px rgba(0,0,0,0.2)' }, default: { elevation: 8 } }) },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { flex: 1, fontSize: 17, fontWeight: '700', color: '#0F172A', marginLeft: 6 },
  closeBtn: { padding: 4 },
  sub: { fontSize: 12.5, color: COLORS.textSecondary, marginTop: 8, marginBottom: 6, lineHeight: 18 },
  sectionLabel: { fontSize: 12, fontWeight: '800', color: '#334155', textTransform: 'uppercase', letterSpacing: 0.4, marginTop: 8, marginBottom: 6 },
  empty: { fontSize: 12.5, color: COLORS.textMuted, fontStyle: 'italic', marginBottom: 4 },
  row: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  input: { flex: 1, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12,
    paddingVertical: Platform.OS === 'ios' ? 11 : 8, fontSize: 14, color: '#0F172A', backgroundColor: '#F8FAFC' },
  removeBtn: { padding: 2 },
  addRow: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 6 },
  addText: { fontSize: 13, fontWeight: '700' },
  footer: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 14 },
  cancelBtn: { paddingVertical: 11, paddingHorizontal: 18, borderRadius: 10, backgroundColor: '#F1F5F9' },
  cancelText: { fontSize: 14, fontWeight: '700', color: '#475569' },
  confirmBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 11, paddingHorizontal: 18, borderRadius: 10 },
  confirmText: { fontSize: 14, fontWeight: '800', color: '#fff' },
});
