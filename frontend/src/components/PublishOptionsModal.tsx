/**
 * PublishOptionsModal — Epic Phase 3B/3C
 *
 * Publish a COMPLETED decider's Option values:
 *   • Quantitative factors -> Solutions Store (cash on paid use)
 *   • Qualitative factors  -> ReviewNet (karma)
 * with a FREE / Paid toggle and a live "expected earnings" preview powered by
 * /catalog/payout/preview. Store publishing is gated to Completed (100%) flows.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import { showAlert } from '../utils/alert';
import api from '../utils/api';

const SOLUTION_TYPES = ['PRODUCT', 'SERVICE', 'EVENT', 'PROJECT', 'PERSON_CONTACT'];

type Props = {
  visible: boolean;
  decisionId: string;
  decisionName?: string;
  onClose: () => void;
  onPublished?: () => void;
};

type Source = {
  is_completed: boolean;
  name?: string;
  progress_pct?: number;
  catalog_node_id?: string | null;
  factors: { id: string; name: string; unit?: string; default_kind: string }[];
  options: { id: string; name: string }[];
};

export default function PublishOptionsModal({ visible, decisionId, decisionName, onClose, onPublished }: Props) {
  const [loading, setLoading] = useState(true);
  const [src, setSrc] = useState<Source | null>(null);
  const [factorTypes, setFactorTypes] = useState<Record<string, 'quantitative' | 'qualitative'>>({});
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [factorSelected, setFactorSelected] = useState<Record<string, boolean>>({});
  const [monetization, setMonetization] = useState<'free' | 'paid'>('free');
  const [solType, setSolType] = useState('PRODUCT');
  const [publishing, setPublishing] = useState(false);
  const [preview, setPreview] = useState<{ cash?: number; karmaFree?: number } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setPreview(null);
    try {
      const { data } = await api.get(`/option-publish/source/${decisionId}`);
      setSrc(data);
      const ft: Record<string, 'quantitative' | 'qualitative'> = {};
      (data.factors || []).forEach((f: any) => (ft[f.id] = (f.default_kind === 'qualitative' ? 'qualitative' : 'quantitative')));
      setFactorTypes(ft);
      const fsel: Record<string, boolean> = {};
      (data.factors || []).forEach((f: any) => (fsel[f.id] = true));
      setFactorSelected(fsel);
      const sel: Record<string, boolean> = {};
      (data.options || []).forEach((o: any) => (sel[o.id] = true));
      setSelected(sel);
      // live earnings preview (sample: 4 stars, 1500 ratings for cash; 5 stars free karma)
      if (data.is_completed) {
        try {
          const node = data.catalog_node_id || null;
          const [paid, free] = await Promise.all([
            api.post('/catalog/payout/preview', { node_id: node, usage_type: 'solution_store_paid', avg_rating: 4, num_ratings: 1500 }),
            api.post('/catalog/payout/preview', { node_id: node, usage_type: 'solution_store_free', star_rating: 5 }),
          ]);
          setPreview({ cash: paid.data?.cash_payout, karmaFree: free.data?.karma });
        } catch { /* preview is best-effort */ }
      }
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to load decision');
      onClose();
    } finally {
      setLoading(false);
    }
  }, [decisionId, onClose]);

  useEffect(() => {
    if (visible) {
      setMonetization('free');
      setSolType('PRODUCT');
      load();
    }
  }, [visible, load]);

  const includedIds = (src?.factors || []).filter((f) => factorSelected[f.id] !== false).map((f) => f.id);
  const quantCount = includedIds.filter((id) => (factorTypes[id] || 'quantitative') === 'quantitative').length;
  const qualCount = includedIds.filter((id) => factorTypes[id] === 'qualitative').length;
  const selectedCount = Object.values(selected).filter(Boolean).length;
  const canPublish = src?.is_completed && quantCount >= 1 && selectedCount >= 1 && !publishing;

  const doPublish = async () => {
    if (quantCount < 1) {
      showAlert('Keep one Quantitative', 'At least one factor must stay Quantitative to publish to the Store.');
      return;
    }
    if (selectedCount < 1) {
      showAlert('Pick an option', 'Select at least one option to publish.');
      return;
    }
    setPublishing(true);
    try {
      const option_ids = Object.keys(selected).filter((k) => selected[k]);
      const { data } = await api.post('/option-publish/publish', {
        decision_id: decisionId,
        option_ids,
        factor_ids: includedIds,
        factor_types: factorTypes,
        monetization,
        solution_type: solType,
        catalog_node_id: src?.catalog_node_id || undefined,
      });
      showAlert(
        'Published 🎉',
        `${data.published_count} option(s) published to the Store` +
          (qualCount ? ` · ${qualCount} qualitative factor(s) opened for ReviewNet` : '') +
          `. Earns ${data.reward_kind === 'cash' ? 'Cash on paid use' : 'Karma'}.`,
      );
      if (onPublished) { onPublished(); } else { onClose(); }
    } catch (e: any) {
      showAlert('Publish failed', e.response?.data?.detail || 'Could not publish');
    } finally {
      setPublishing(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>Publish to Store</Text>
              {!!(src?.name || decisionName) && <Text style={styles.subtitle} numberOfLines={1}>{src?.name || decisionName}</Text>}
            </View>
            <TouchableOpacity onPress={onClose} testID="publish-close">
              <Ionicons name="close" size={24} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>

          {loading ? (
            <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
          ) : !src?.is_completed ? (
            <View style={styles.gateBox}>
              <Ionicons name="lock-closed" size={34} color={COLORS.textMuted} />
              <Text style={styles.gateTitle}>Completed flows only</Text>
              <Text style={styles.gateText}>
                Publishing to the Solution Store is allowed only from a Completed (100%) flow.
                {typeof src?.progress_pct === 'number' ? ` This flow is at ${src.progress_pct}%.` : ''}
              </Text>
              <TouchableOpacity style={styles.gateBtn} onPress={onClose}>
                <Text style={styles.gateBtnText}>Got it</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <>
              <ScrollView contentContainerStyle={{ padding: 16 }} showsVerticalScrollIndicator={false}>
                {/* Solution type */}
                <Text style={styles.sectionLabel}>Listing type</Text>
                <View style={styles.chipRow}>
                  {SOLUTION_TYPES.map((t) => (
                    <TouchableOpacity
                      key={t}
                      style={[styles.typeChip, solType === t && styles.typeChipActive]}
                      onPress={() => setSolType(t)}
                      testID={`publish-type-${t}`}
                    >
                      <Text style={[styles.typeChipText, solType === t && { color: '#FFF' }]}>{t.replace('_', ' ')}</Text>
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Factor classification */}
                <Text style={styles.sectionLabel}>Categorize Factors</Text>
                <Text style={styles.hint}>Quantitative → Solution Store · Qualitative → ReviewNet (rated for Karma Points)</Text>
                {(src.factors || []).map((f) => {
                  const kind = factorTypes[f.id] || 'quantitative';
                  const on = factorSelected[f.id] !== false;
                  return (
                    <View key={f.id} style={styles.factorBlock}>
                      <TouchableOpacity
                        style={styles.factorHead}
                        onPress={() => setFactorSelected({ ...factorSelected, [f.id]: !on })}
                        testID={`factor-select-${f.id}`}
                      >
                        <Ionicons name={on ? 'checkbox' : 'square-outline'} size={20} color={on ? COLORS.primary : COLORS.textMuted} />
                        <Text style={[styles.factorName, !on && { color: COLORS.textMuted }]} numberOfLines={1}>
                          {f.name}{f.unit ? ` (${f.unit})` : ''}
                        </Text>
                      </TouchableOpacity>
                      {on && (
                        <View style={styles.segmentFull}>
                          {(['quantitative', 'qualitative'] as const).map((k) => (
                            <TouchableOpacity
                              key={k}
                              style={[styles.segBtnFull, kind === k && styles.segBtnActive]}
                              onPress={() => setFactorTypes({ ...factorTypes, [f.id]: k })}
                              testID={`factor-${f.id}-${k}`}
                            >
                              <Text style={[styles.segTextFull, kind === k && { color: '#FFF' }]}>
                                {k === 'quantitative' ? 'Quantitative' : 'Qualitative'}
                              </Text>
                            </TouchableOpacity>
                          ))}
                        </View>
                      )}
                    </View>
                  );
                })}
                {quantCount < 1 && (
                  <Text style={styles.warn}>Keep at least one factor Quantitative to publish to the Store.</Text>
                )}

                {/* Options */}
                <Text style={styles.sectionLabel}>Options to publish ({selectedCount}/{src.options.length})</Text>
                {(src.options || []).map((o) => (
                  <TouchableOpacity
                    key={o.id}
                    style={styles.optRow}
                    onPress={() => setSelected({ ...selected, [o.id]: !selected[o.id] })}
                    testID={`publish-option-${o.id}`}
                  >
                    <Ionicons
                      name={selected[o.id] ? 'checkbox' : 'square-outline'}
                      size={20}
                      color={selected[o.id] ? COLORS.primary : COLORS.textMuted}
                    />
                    <Text style={styles.optName} numberOfLines={1}>{o.name}</Text>
                  </TouchableOpacity>
                ))}

                {/* Monetization */}
                <Text style={styles.sectionLabel}>Monetization</Text>
                <View style={styles.monetRow}>
                  {(['free', 'paid'] as const).map((m) => (
                    <TouchableOpacity
                      key={m}
                      style={[styles.monetCard, monetization === m && styles.monetCardActive]}
                      onPress={() => setMonetization(m)}
                      testID={`publish-monet-${m}`}
                    >
                      <Ionicons
                        name={m === 'free' ? 'sparkles-outline' : 'cash-outline'}
                        size={18}
                        color={monetization === m ? COLORS.primary : COLORS.textMuted}
                      />
                      <Text style={[styles.monetTitle, monetization === m && { color: COLORS.primary }]}>
                        {m === 'free' ? 'Free (Karma Points)' : 'Paid (Cash)'}
                      </Text>
                      <Text style={styles.monetDesc}>
                        {m === 'free' ? 'Earn Karma on every use' : 'Cash once free quota is used; Karma before that'}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Earnings preview */}
                {preview && (
                  <View style={styles.previewCard}>
                    <Text style={styles.previewTitle}>Expected earnings</Text>
                    {monetization === 'paid' && (
                      <View style={styles.previewRow}>
                        <Ionicons name="cash-outline" size={15} color={COLORS.success} />
                        <Text style={styles.previewText}>
                          ~₹{preview.cash ?? '—'} per paid use <Text style={styles.previewMuted}>(at 4★, 1500 ratings)</Text>
                        </Text>
                      </View>
                    )}
                    <View style={styles.previewRow}>
                      <Ionicons name="sparkles-outline" size={15} color={COLORS.primary} />
                      <Text style={styles.previewText}>
                        +{preview.karmaFree ?? '—'} Karma per free use <Text style={styles.previewMuted}>(at 5★)</Text>
                      </Text>
                    </View>
                    <Text style={styles.previewFoot}>Final amounts follow the admin Catalog L0–L3 payout config.</Text>
                  </View>
                )}
              </ScrollView>

              <View style={styles.footer}>
                <TouchableOpacity style={styles.cancelBtn} onPress={onClose}>
                  <Text style={styles.cancelText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.publishBtn, !canPublish && { opacity: 0.5 }]}
                  onPress={doPublish}
                  disabled={!canPublish}
                  testID="publish-submit"
                >
                  {publishing
                    ? <ActivityIndicator color="#FFF" />
                    : <Text style={styles.publishText}>Publish {selectedCount} option{selectedCount === 1 ? '' : 's'}</Text>}
                </TouchableOpacity>
              </View>
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18,
    maxHeight: '92%', width: '100%', maxWidth: 560, alignSelf: 'center',
  },
  header: {
    flexDirection: 'row', alignItems: 'center', padding: 16,
    borderBottomWidth: 1, borderBottomColor: COLORS.divider,
  },
  title: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  center: { padding: 50, alignItems: 'center', justifyContent: 'center' },

  gateBox: { padding: 28, alignItems: 'center', gap: 8 },
  gateTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 6 },
  gateText: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', lineHeight: 19 },
  gateBtn: { marginTop: 14, backgroundColor: COLORS.primary, paddingHorizontal: 24, paddingVertical: 11, borderRadius: 10 },
  gateBtnText: { color: '#FFF', fontWeight: '700' },

  sectionLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginTop: 16, marginBottom: 8 },
  hint: { fontSize: 11, color: COLORS.textMuted, marginBottom: 8 },
  warn: { fontSize: 12, color: COLORS.error, marginTop: 6 },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  typeChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.surface },
  typeChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  typeChipText: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },

  factorRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 7, gap: 10 },
  factorBlock: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  factorHead: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  factorName: { flex: 1, fontSize: 14, color: COLORS.textPrimary },
  segment: { flexDirection: 'row', borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, overflow: 'hidden' },
  segmentFull: { flexDirection: 'row', marginTop: 8, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, overflow: 'hidden' },
  segBtn: { paddingHorizontal: 12, paddingVertical: 6, backgroundColor: COLORS.surface },
  segBtnFull: { flex: 1, paddingVertical: 8, alignItems: 'center', backgroundColor: COLORS.surface },
  segBtnActive: { backgroundColor: COLORS.primary },
  segText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  segTextFull: { fontSize: 13, fontWeight: '700', color: COLORS.textSecondary },

  optRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 },
  optName: { flex: 1, fontSize: 14, color: COLORS.textPrimary },

  monetRow: { flexDirection: 'row', gap: 10 },
  monetCard: { flex: 1, padding: 12, borderRadius: 12, borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: COLORS.surface, gap: 4 },
  monetCardActive: { borderColor: COLORS.primary, backgroundColor: '#F8F5FC' },
  monetTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  monetDesc: { fontSize: 11, color: COLORS.textSecondary, lineHeight: 15 },

  previewCard: { marginTop: 16, padding: 12, borderRadius: 12, backgroundColor: '#F0FBF4', borderWidth: 1, borderColor: '#CDEFD9', gap: 6 },
  previewTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  previewRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  previewText: { fontSize: 13, color: COLORS.textPrimary },
  previewMuted: { fontSize: 11, color: COLORS.textMuted },
  previewFoot: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },

  footer: { flexDirection: 'row', gap: 10, padding: 16, borderTopWidth: 1, borderTopColor: COLORS.divider },
  cancelBtn: { paddingHorizontal: 18, paddingVertical: 13, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center', justifyContent: 'center' },
  cancelText: { color: COLORS.textSecondary, fontWeight: '600' },
  publishBtn: { flex: 1, backgroundColor: COLORS.primary, borderRadius: 10, paddingVertical: 13, alignItems: 'center', justifyContent: 'center' },
  publishText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
});
