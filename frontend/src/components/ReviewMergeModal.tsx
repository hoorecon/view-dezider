import React, { useState, useEffect, useCallback } from 'react';
import {
  Modal, View, Text, TouchableOpacity, StyleSheet, ScrollView,
  ActivityIndicator, TextInput,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import { showAlert } from '../utils/alert';
import api from '../utils/api';

interface ReviewMergeModalProps {
  visible: boolean;
  onClose: () => void;
  shareId: string | null;
  /** When true, auto-runs AI Auto-Merge as soon as contributions load. */
  autoAi?: boolean;
  /** Called after a successful manual / AI merge so the host can refresh. */
  onMerged?: () => void;
}

interface Contribution {
  user_id: string;
  name: string;
  email?: string;
  sme?: boolean;
  sme_domains?: string[];
  capability?: string | null;
  resources?: any;
  data?: any;
  note?: string;
  submitted_at?: string;
}

interface ReviewData {
  module: string;
  step_number: number;
  merge_mode: string;
  status: string;
  decision_title?: string;
  owner?: any;
  contributions: Contribution[];
  merge_history?: MergeEntry[];
}

interface MergeEntry {
  at?: string;
  by?: string;
  method?: string;
  credits?: number | null;
  contributor?: string | null;
  merge_mode?: string;
  contributors_count?: number;
}

const METHOD_LABEL: Record<string, string> = {
  ai: 'AI Auto-Merge', ai_edited: 'AI Auto-Merge (edited)',
  manual_adopt: 'Adopted a contributor', weighted: 'Weighted merge', manual: 'Manual merge',
};

const fmtWhen = (iso?: string) => {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); }
  catch { return iso.slice(0, 16).replace('T', ' '); }
};

/** Render an arbitrary step-data object as a readable key/value preview. */
const DataPreview: React.FC<{ data: any }> = ({ data }) => {
  const [showRaw, setShowRaw] = useState(false);
  if (data === null || data === undefined) {
    return <Text style={s.dim}>No structured input.</Text>;
  }
  const entries = typeof data === 'object' && !Array.isArray(data)
    ? Object.entries(data).filter(([k]) => !['_id', 'id', 'entry_id', 'user_id', 'contribution_clone', 'created_at', 'updated_at'].includes(k))
    : [['value', data]];
  return (
    <View>
      {entries.slice(0, 14).map(([k, v]) => {
        let display: string;
        if (Array.isArray(v)) {
          const names = v.map((it: any) => (it && (it.name || it.text || it.title || it.label)) || '').filter(Boolean);
          display = names.length ? `${v.length}: ${names.slice(0, 4).join(', ')}${names.length > 4 ? '…' : ''}` : `${v.length} item(s)`;
        } else if (v && typeof v === 'object') {
          display = `{${Object.keys(v).slice(0, 4).join(', ')}}`;
        } else {
          display = String(v ?? '');
        }
        if (!display) return null;
        return (
          <View key={k} style={s.kvRow}>
            <Text style={s.kvKey} numberOfLines={1}>{k}</Text>
            <Text style={s.kvVal} numberOfLines={3}>{display}</Text>
          </View>
        );
      })}
      <TouchableOpacity onPress={() => setShowRaw(v => !v)} style={{ marginTop: 4 }}>
        <Text style={s.rawToggle}>{showRaw ? 'Hide raw' : 'View raw JSON'}</Text>
      </TouchableOpacity>
      {showRaw && <Text style={s.rawJson}>{JSON.stringify(data, null, 2).slice(0, 4000)}</Text>}
    </View>
  );
};

export const ReviewMergeModal: React.FC<ReviewMergeModalProps> = ({
  visible, onClose, shareId, autoAi, onMerged,
}) => {
  const [loading, setLoading] = useState(true);
  const [review, setReview] = useState<ReviewData | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiProposal, setAiProposal] = useState<any>(null);
  const [aiRationale, setAiRationale] = useState('');
  const [aiCharged, setAiCharged] = useState<number | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedJson, setEditedJson] = useState('');
  const [applying, setApplying] = useState(false);

  const fetchReview = useCallback(async () => {
    if (!shareId) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/shared-steps/${shareId}/review`);
      setReview(data);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not load contributions');
    } finally {
      setLoading(false);
    }
  }, [shareId]);

  useEffect(() => {
    if (visible && shareId) {
      setAiProposal(null); setAiRationale(''); setAiCharged(null);
      setEditMode(false); setEditedJson('');
      fetchReview();
    }
  }, [visible, shareId, fetchReview]);

  const runAiMerge = async () => {
    if (!shareId) return;
    setAiBusy(true);
    try {
      const { data } = await api.post(`/shared-steps/${shareId}/ai-merge`, {});
      setAiProposal(data.proposal ?? null);
      setAiRationale(data.rationale || '');
      setAiCharged(typeof data.charged === 'number' ? data.charged : null);
      setEditedJson(JSON.stringify(data.proposal ?? {}, null, 2));
    } catch (e: any) {
      showAlert('AI Merge failed', e?.response?.data?.detail || 'Could not run AI merge');
    } finally {
      setAiBusy(false);
    }
  };

  const applyMerged = async (merged: any, method: string, credits?: number, contributor?: string) => {
    if (!shareId) return;
    if (!merged || (typeof merged === 'object' && Object.keys(merged).length === 0)) {
      showAlert('Nothing to apply', 'No merged fields to write.');
      return;
    }
    setApplying(true);
    try {
      await api.post(`/shared-steps/${shareId}/apply`, { merged, method, credits: credits ?? 0, contributor });
      showAlert('Merged ✓', 'The merged version has been applied to your flow. Contributor inputs are kept for reference.');
      onMerged?.();
      await fetchReview();
      setAiProposal(null); setEditMode(false);
    } catch (e: any) {
      showAlert('Apply failed', e?.response?.data?.detail || 'Could not apply the merge');
    } finally {
      setApplying(false);
    }
  };

  const applyAiSuggested = () => {
    if (editMode) {
      let parsed: any;
      try { parsed = JSON.parse(editedJson); }
      catch { showAlert('Invalid JSON', 'Please fix the JSON before applying.'); return; }
      applyMerged(parsed, 'ai_edited', aiCharged ?? 0);
    } else {
      applyMerged(aiProposal, 'ai', aiCharged ?? 0);
    }
  };

  const weightedMerge = async () => {
    if (!shareId) return;
    setApplying(true);
    try {
      const { data } = await api.post(`/shared-steps/${shareId}/merge`, { merge_mode: review?.merge_mode || 'equal' });
      showAlert('Merged ✓', data?.message || 'Contributions merged with your weighting.');
      onMerged?.();
      await fetchReview();
    } catch (e: any) {
      showAlert('Merge failed', e?.response?.data?.detail || 'Could not merge');
    } finally {
      setApplying(false);
    }
  };

  // Auto-run AI merge when opened via the "AI Review & Auto-Merge" button.
  const autoRanRef = React.useRef(false);
  useEffect(() => { if (!visible) autoRanRef.current = false; }, [visible]);
  useEffect(() => {
    if (visible && autoAi && review && review.contributions.length > 0
        && !aiProposal && !aiBusy && !autoRanRef.current) {
      autoRanRef.current = true;
      runAiMerge();
    }
  }, [visible, autoAi, review, aiProposal, aiBusy]);

  const isDecision = review?.module === 'decision';
  const merged = review?.status === 'merged';

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.card}>
          <View style={s.header}>
            <View style={{ flex: 1 }}>
              <Text style={s.title}>Review &amp; Merge</Text>
              <Text style={s.subtitle} numberOfLines={1}>
                {review ? `Step ${review.step_number} · ${review.contributions.length} contributor(s)` : 'Loading…'}
              </Text>
            </View>
            {merged && (
              <View style={s.mergedPill}><Ionicons name="git-merge" size={12} color="#7C3AED" /><Text style={s.mergedPillTxt}>Merged</Text></View>
            )}
            <TouchableOpacity onPress={onClose} style={s.closeBtn} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close" size={22} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>

          {loading ? (
            <View style={s.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
          ) : !review ? (
            <View style={s.center}><Text style={s.dim}>No data.</Text></View>
          ) : (
            <ScrollView style={s.body} contentContainerStyle={{ paddingBottom: 28 }}>
              {merged && (
                <View style={s.infoBanner}>
                  <Ionicons name="information-circle" size={16} color="#7C3AED" />
                  <Text style={s.infoBannerTxt}>This step is merged. You can still review each contributor input below, and re-merge if needed.</Text>
                </View>
              )}

              {(review.merge_history?.length || 0) > 0 && (
                <View style={s.histCard}>
                  <Text style={[s.sectionLabel, { marginTop: 0 }]}>Merge history</Text>
                  {review.merge_history!.slice().reverse().map((h, i) => (
                    <View key={i} style={s.histRow}>
                      <Ionicons
                        name={h.method?.startsWith('ai') ? 'sparkles' : h.method === 'weighted' ? 'git-merge' : 'checkmark-done'}
                        size={14} color={h.method?.startsWith('ai') ? '#7C3AED' : COLORS.textSecondary}
                      />
                      <View style={{ flex: 1 }}>
                        <Text style={s.histTitle}>
                          {METHOD_LABEL[h.method || 'manual'] || h.method}
                          {h.contributor ? ` · ${h.contributor}` : ''}
                          {h.merge_mode ? ` · ${h.merge_mode}` : ''}
                        </Text>
                        <Text style={s.histMeta}>
                          {fmtWhen(h.at)}{h.by ? ` · by ${h.by}` : ''}{(h.credits ?? 0) > 0 ? ` · ${h.credits} credits` : ''}
                        </Text>
                      </View>
                    </View>
                  ))}
                </View>
              )}

              {/* Owner's own input */}
              <Text style={s.sectionLabel}>Your input</Text>
              <View style={[s.inputCard, { borderColor: COLORS.primary + '40' }]}>
                <View style={s.inputCardHead}>
                  <View style={[s.avatar, { backgroundColor: COLORS.primary }]}><Ionicons name="person" size={13} color="#FFF" /></View>
                  <Text style={s.inputName}>You (owner)</Text>
                </View>
                <DataPreview data={review.owner} />
              </View>

              {/* Each contributor */}
              <Text style={s.sectionLabel}>Contributors</Text>
              {review.contributions.length === 0 && <Text style={s.dim}>No contributions submitted yet.</Text>}
              {review.contributions.map((c) => (
                <View key={c.user_id} style={s.inputCard}>
                  <View style={s.inputCardHead}>
                    <View style={[s.avatar, c.sme && { backgroundColor: '#6366F1' }]}>
                      {c.sme ? <Ionicons name="shield-checkmark" size={13} color="#FFF" />
                        : <Text style={s.avatarTxt}>{(c.name || '?')[0].toUpperCase()}</Text>}
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.inputName}>{c.name}{c.sme ? '  · SME' : ''}</Text>
                      {!!c.capability && <Text style={s.capability}>{c.capability}</Text>}
                    </View>
                  </View>
                  {!!c.note && <Text style={s.note}>{`“${c.note}”`}</Text>}
                  <DataPreview data={c.data} />
                  {!isDecision && (
                    <TouchableOpacity
                      style={s.adoptBtn} disabled={applying}
                      onPress={() => applyMerged(c.data, 'manual_adopt', 0, c.name)}
                      testID={`adopt-${c.user_id}`}
                    >
                      <Ionicons name="checkmark-done" size={14} color="#0F766E" />
                      <Text style={s.adoptTxt}>Adopt this version</Text>
                    </TouchableOpacity>
                  )}
                </View>
              ))}

              {/* ── Merge actions ── */}
              {review.contributions.length > 0 && (
                <>
                  <Text style={s.sectionLabel}>Merge</Text>

                  {/* AI Auto-Merge */}
                  <View style={s.aiCard}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <Ionicons name="sparkles" size={16} color="#7C3AED" />
                      <Text style={s.aiTitle}>AI Review &amp; Auto-Merge</Text>
                    </View>
                    <Text style={s.aiHint}>
                      AI consolidates all inputs, weighting by your merge mode ({review.merge_mode}) plus each contributor SME status, capability and resources. Advisory — you approve before applying.
                    </Text>
                    {!aiProposal && (
                      <TouchableOpacity style={s.aiBtn} onPress={runAiMerge} disabled={aiBusy} testID="ai-merge-run">
                        {aiBusy ? <ActivityIndicator color="#FFF" size="small" /> : (
                          <><Ionicons name="sparkles" size={15} color="#FFF" /><Text style={s.aiBtnTxt}>Run AI Auto-Merge</Text></>
                        )}
                      </TouchableOpacity>
                    )}
                    {aiProposal !== null && (
                      <View style={{ marginTop: 10 }}>
                        {!!aiRationale && (
                          <View style={s.rationaleBox}>
                            <Text style={s.rationaleLabel}>Why this merge</Text>
                            <Text style={s.rationaleTxt}>{aiRationale}</Text>
                          </View>
                        )}
                        {aiCharged != null && <Text style={s.charged}>AI cost: {aiCharged} credits</Text>}
                        <Text style={[s.sectionLabel, { marginTop: 8 }]}>Proposed merge</Text>
                        {editMode ? (
                          <TextInput
                            style={s.jsonInput} multiline value={editedJson}
                            onChangeText={setEditedJson} autoCapitalize="none"
                            testID="ai-merge-edit"
                          />
                        ) : (
                          <View style={[s.inputCard, { borderColor: '#DDD6FE' }]}><DataPreview data={aiProposal} /></View>
                        )}
                        <View style={s.aiActionRow}>
                          <TouchableOpacity style={s.editToggle} onPress={() => setEditMode(v => !v)}>
                            <Ionicons name={editMode ? 'eye-outline' : 'create-outline'} size={14} color={COLORS.primary} />
                            <Text style={s.editToggleTxt}>{editMode ? 'Preview' : 'Edit before applying'}</Text>
                          </TouchableOpacity>
                          <TouchableOpacity style={s.regenBtn} onPress={runAiMerge} disabled={aiBusy}>
                            <Ionicons name="refresh" size={14} color={COLORS.textSecondary} />
                            <Text style={s.regenTxt}>Regenerate</Text>
                          </TouchableOpacity>
                        </View>
                        <TouchableOpacity style={s.applyBtn} onPress={applyAiSuggested} disabled={applying} testID="ai-merge-apply">
                          {applying ? <ActivityIndicator color="#FFF" size="small" /> : (
                            <><Ionicons name="checkmark-circle" size={16} color="#FFF" /><Text style={s.applyTxt}>Apply {editMode ? 'my edited version' : 'as AI suggested'}</Text></>
                          )}
                        </TouchableOpacity>
                      </View>
                    )}
                  </View>

                  {/* Decision-only weighted numeric merge */}
                  {isDecision && (
                    <TouchableOpacity style={s.weightedBtn} onPress={weightedMerge} disabled={applying} testID="weighted-merge">
                      <Ionicons name="git-merge-outline" size={15} color="#FFF" />
                      <Text style={s.weightedTxt}>Weighted merge ({review.merge_mode})</Text>
                    </TouchableOpacity>
                  )}
                </>
              )}
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
};

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  card: { backgroundColor: COLORS.white, borderRadius: 22, width: '100%', maxWidth: 520, maxHeight: '90%', alignSelf: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  title: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary },
  subtitle: { fontSize: 12.5, color: COLORS.textSecondary, marginTop: 2 },
  closeBtn: { width: 34, height: 34, borderRadius: 17, backgroundColor: COLORS.background, justifyContent: 'center', alignItems: 'center' },
  mergedPill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#EDE9FE', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12 },
  mergedPillTxt: { fontSize: 11, fontWeight: '700', color: '#7C3AED' },
  center: { padding: 40, alignItems: 'center' },
  body: { paddingHorizontal: 16, paddingTop: 12 },
  infoBanner: { flexDirection: 'row', gap: 8, backgroundColor: '#F5F3FF', borderRadius: 10, padding: 10, marginBottom: 12 },
  infoBannerTxt: { flex: 1, fontSize: 12, color: '#5B21B6', lineHeight: 16 },
  sectionLabel: { fontSize: 12, fontWeight: '800', color: COLORS.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginTop: 8, marginBottom: 8 },
  inputCard: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 12, padding: 12, marginBottom: 10, backgroundColor: COLORS.white },
  inputCardHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  avatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: COLORS.textMuted, alignItems: 'center', justifyContent: 'center' },
  avatarTxt: { fontSize: 13, fontWeight: '700', color: '#FFF' },
  inputName: { fontSize: 13.5, fontWeight: '700', color: COLORS.textPrimary },
  capability: { fontSize: 11, color: '#6366F1', fontWeight: '600', marginTop: 1 },
  note: { fontSize: 12.5, fontStyle: 'italic', color: COLORS.textSecondary, marginBottom: 8 },
  dim: { fontSize: 12.5, color: COLORS.textMuted },
  kvRow: { flexDirection: 'row', gap: 8, paddingVertical: 3, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  kvKey: { width: 110, fontSize: 11.5, fontWeight: '700', color: COLORS.textSecondary },
  kvVal: { flex: 1, fontSize: 12, color: COLORS.textPrimary },
  rawToggle: { fontSize: 11.5, color: COLORS.primary, fontWeight: '700' },
  rawJson: { fontSize: 10.5, color: '#475569', fontFamily: 'monospace', backgroundColor: '#F8FAFC', borderRadius: 8, padding: 8, marginTop: 6 },
  adoptBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#CCFBF1', borderRadius: 10, paddingVertical: 8, marginTop: 8 },
  adoptTxt: { fontSize: 12.5, fontWeight: '700', color: '#0F766E' },
  aiCard: { borderWidth: 1, borderColor: '#DDD6FE', borderRadius: 14, padding: 12, backgroundColor: '#FAF5FF', marginBottom: 12 },
  aiTitle: { fontSize: 14.5, fontWeight: '800', color: '#5B21B6' },
  aiHint: { fontSize: 11.5, color: '#6D28D9', lineHeight: 16, marginBottom: 10 },
  aiBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#7C3AED', borderRadius: 12, paddingVertical: 12 },
  aiBtnTxt: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  rationaleBox: { backgroundColor: '#FFF', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#EDE9FE', marginBottom: 8 },
  rationaleLabel: { fontSize: 11, fontWeight: '800', color: '#7C3AED', textTransform: 'uppercase', marginBottom: 3 },
  rationaleTxt: { fontSize: 12.5, color: '#4C1D95', lineHeight: 17 },
  charged: { fontSize: 11.5, color: '#6D28D9', fontWeight: '700', marginBottom: 2 },
  jsonInput: { borderWidth: 1, borderColor: '#DDD6FE', borderRadius: 10, padding: 10, fontSize: 11, fontFamily: 'monospace', color: '#1F2937', minHeight: 160, textAlignVertical: 'top', backgroundColor: '#FFF' },
  aiActionRow: { flexDirection: 'row', justifyContent: 'space-between', marginVertical: 10 },
  editToggle: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  editToggleTxt: { fontSize: 12, fontWeight: '700', color: COLORS.primary },
  regenBtn: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  regenTxt: { fontSize: 12, fontWeight: '700', color: COLORS.textSecondary },
  applyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#16A34A', borderRadius: 12, paddingVertical: 12 },
  applyTxt: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  weightedBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 12, marginBottom: 16 },
  weightedTxt: { fontSize: 13.5, fontWeight: '700', color: '#FFF' },
  histCard: { borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 12, padding: 12, backgroundColor: '#F8FAFC', marginBottom: 12 },
  histRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, paddingVertical: 5, borderTopWidth: 1, borderTopColor: '#EEF2F7' },
  histTitle: { fontSize: 12.5, fontWeight: '700', color: COLORS.textPrimary },
  histMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
});

export default ReviewMergeModal;
