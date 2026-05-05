/**
 * /admin/review-net  — Admin Moderation Queue + Rules Editor
 *
 * Two tabs:
 *   • Queue  — pending reviews → approve / reject
 *   • Rules  — auto-publish rules CRUD
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  TextInput,
  Modal,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../src/utils/api';
import { COLORS } from '../../../src/constants/colors';
import { showAlert } from '../../../src/utils/alert';

type Tab = 'queue' | 'rules';

interface ReviewDoc {
  review_id: string;
  solution_name?: string;
  reviewer_name?: string;
  reviewer_segment: string;
  reviewer_subsegment?: string;
  factor_ratings: Record<string, number>;
  overall_rating: number;
  title?: string;
  comment?: string;
  is_verified_buyer?: boolean;
  status: string;
  created_at: string;
}

interface Rule {
  rule_id: string;
  name: string;
  description?: string;
  conditions: Array<{ field: string; op: string; value: any }>;
  action: 'AUTO_APPROVE' | 'HOLD_FOR_ADMIN' | 'AUTO_REJECT';
  priority: number;
  is_active: boolean;
}

const RULE_FIELDS = [
  { id: 'overall_min', label: 'Overall avg ≥', type: 'number' },
  { id: 'overall_max', label: 'Overall avg ≤', type: 'number' },
  { id: 'rating_min', label: 'Every rating ≥', type: 'number' },
  { id: 'rating_max', label: 'Every rating ≤', type: 'number' },
  { id: 'comment_max_length', label: 'Comment length ≤', type: 'number' },
  { id: 'is_verified_buyer', label: 'Verified buyer', type: 'bool' },
  { id: 'reviewer_min_prior_approved', label: 'Reviewer prior approved ≥', type: 'number' },
  { id: 'comment_contains_blocklist', label: 'Blocked words (comma-sep)', type: 'csv' },
];


export default function AdminReviewNetScreen() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>('queue');

  // ---- Queue ----
  const [queue, setQueue] = useState<ReviewDoc[]>([]);
  const [loadingQueue, setLoadingQueue] = useState(false);

  const loadQueue = useCallback(async () => {
    try {
      setLoadingQueue(true);
      const res = await api.get('/review-net/admin/moderation-queue?status=pending');
      setQueue(res.data?.items || []);
    } catch (e: any) {
      showAlert('Queue error', e?.response?.data?.detail || e.message);
    } finally {
      setLoadingQueue(false);
    }
  }, []);

  const moderate = async (review: ReviewDoc, decision: 'approve' | 'reject') => {
    try {
      await api.post(`/review-net/admin/moderate/${review.review_id}`, { decision });
      showAlert('Done', `${decision === 'approve' ? 'Approved' : 'Rejected'}: ${review.title || review.comment?.slice(0, 30) || review.review_id}`);
      loadQueue();
    } catch (e: any) {
      showAlert('Action failed', e?.response?.data?.detail || e.message);
    }
  };

  // ---- Rules ----
  const [rules, setRules] = useState<Rule[]>([]);
  const [loadingRules, setLoadingRules] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [draftName, setDraftName] = useState('');
  const [draftPriority, setDraftPriority] = useState('100');
  const [draftAction, setDraftAction] = useState<'AUTO_APPROVE' | 'HOLD_FOR_ADMIN' | 'AUTO_REJECT'>('AUTO_APPROVE');
  const [draftConditions, setDraftConditions] = useState<Array<{ field: string; op: string; value: any }>>([]);
  const [busy, setBusy] = useState(false);

  const loadRules = useCallback(async () => {
    try {
      setLoadingRules(true);
      const res = await api.get('/review-net/admin/rules');
      setRules(res.data?.items || []);
    } catch (e: any) {
      showAlert('Rules error', e?.response?.data?.detail || e.message);
    } finally {
      setLoadingRules(false);
    }
  }, []);

  useEffect(() => { loadQueue(); }, [loadQueue]);
  useEffect(() => { if (tab === 'rules') loadRules(); }, [tab, loadRules]);

  const addCondition = () => {
    setDraftConditions(prev => [...prev, { field: 'overall_min', op: 'gte', value: 3 }]);
  };

  const updateCondition = (i: number, key: 'field' | 'value', val: any) => {
    setDraftConditions(prev => prev.map((c, idx) => idx === i ? { ...c, [key]: val } : c));
  };

  const removeCondition = (i: number) => {
    setDraftConditions(prev => prev.filter((_, idx) => idx !== i));
  };

  const submitRule = async () => {
    if (!draftName.trim()) return showAlert('Required', 'Enter a name');
    if (draftConditions.length === 0) return showAlert('Required', 'Add at least one condition');
    try {
      setBusy(true);
      const conditions = draftConditions.map(c => {
        const f = RULE_FIELDS.find(x => x.id === c.field);
        let value: any = c.value;
        if (f?.type === 'number') value = Number(c.value);
        if (f?.type === 'bool') value = c.value === true || c.value === 'true';
        if (f?.type === 'csv') {
          value = String(c.value || '').split(',').map(s => s.trim()).filter(Boolean);
        }
        const op = f?.id === 'overall_min' || f?.id === 'rating_min' || f?.id === 'reviewer_min_prior_approved' ? 'gte'
          : f?.id === 'overall_max' || f?.id === 'rating_max' || f?.id === 'comment_max_length' ? 'lte'
          : f?.id === 'comment_contains_blocklist' ? 'in'
          : 'eq';
        return { field: c.field, op, value };
      });
      await api.post('/review-net/admin/rules', {
        name: draftName,
        priority: parseInt(draftPriority, 10) || 100,
        action: draftAction,
        conditions,
      });
      showAlert('Created', `Rule "${draftName}" saved`);
      setShowCreate(false);
      setDraftName(''); setDraftPriority('100'); setDraftConditions([]); setDraftAction('AUTO_APPROVE');
      loadRules();
    } catch (e: any) {
      showAlert('Create failed', e?.response?.data?.detail || e.message);
    } finally {
      setBusy(false);
    }
  };

  const toggleRule = async (r: Rule) => {
    try {
      await api.put(`/review-net/admin/rules/${r.rule_id}`, { is_active: !r.is_active });
      loadRules();
    } catch (e: any) {
      showAlert('Toggle failed', e?.response?.data?.detail || e.message);
    }
  };

  const deleteRule = async (r: Rule) => {
    showAlert('Delete rule?', `Delete "${r.name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/review-net/admin/rules/${r.rule_id}`);
            loadRules();
          } catch (e: any) {
            showAlert('Delete failed', e?.response?.data?.detail || e.message);
          }
        },
      },
    ]);
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>ReviewNet · Admin</Text>
        <View style={{ width: 22 }} />
      </View>

      <View style={styles.tabs}>
        <TouchableOpacity onPress={() => setTab('queue')} style={[styles.tab, tab === 'queue' && styles.tabActive]}>
          <Text style={[styles.tabText, tab === 'queue' && styles.tabTextActive]}>Queue ({queue.length})</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setTab('rules')} style={[styles.tab, tab === 'rules' && styles.tabActive]}>
          <Text style={[styles.tabText, tab === 'rules' && styles.tabTextActive]}>Rules ({rules.length})</Text>
        </TouchableOpacity>
      </View>

      {/* QUEUE TAB */}
      {tab === 'queue' && (
        <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 60 }}>
          {loadingQueue ? <ActivityIndicator color={COLORS.primary} /> :
           queue.length === 0 ? (
            <View style={styles.empty}><Ionicons name="checkmark-circle" size={32} color={COLORS.success} />
              <Text style={{ color: COLORS.textMuted, marginTop: 8 }}>Queue is empty</Text>
            </View>
          ) : queue.map(rv => (
            <View key={rv.review_id} style={styles.reviewCard}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <Text style={{ flex: 1, color: COLORS.textPrimary, fontWeight: '700' }} numberOfLines={1}>
                  {rv.solution_name}
                </Text>
                <View style={{ backgroundColor: COLORS.primary + '22', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 }}>
                  <Text style={{ color: COLORS.primary, fontSize: 11, fontWeight: '700' }}>{rv.overall_rating}/5</Text>
                </View>
              </View>
              <Text style={{ color: COLORS.textSecondary, fontSize: 12 }}>
                {rv.reviewer_name} · {rv.reviewer_segment}{rv.reviewer_subsegment ? ` (${rv.reviewer_subsegment})` : ''}
                {rv.is_verified_buyer ? ' · ✓ verified' : ''}
              </Text>
              {rv.title ? <Text style={[styles.reviewBody, { fontWeight: '700' }]}>{rv.title}</Text> : null}
              {rv.comment ? <Text style={styles.reviewBody}>{rv.comment}</Text> : null}
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                <TouchableOpacity testID={`mod-reject-${rv.review_id}`} style={[styles.actionBtn, { backgroundColor: COLORS.error }]} onPress={() => moderate(rv, 'reject')}>
                  <Ionicons name="close" size={14} color="#FFF" />
                  <Text style={styles.actionBtnText}>Reject</Text>
                </TouchableOpacity>
                <TouchableOpacity testID={`mod-approve-${rv.review_id}`} style={[styles.actionBtn, { backgroundColor: COLORS.success }]} onPress={() => moderate(rv, 'approve')}>
                  <Ionicons name="checkmark" size={14} color="#FFF" />
                  <Text style={styles.actionBtnText}>Approve</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </ScrollView>
      )}

      {/* RULES TAB */}
      {tab === 'rules' && (
        <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 60 }}>
          <TouchableOpacity testID="rules-add" style={styles.bigPrimary} onPress={() => setShowCreate(true)}>
            <Ionicons name="add" size={18} color="#FFF" />
            <Text style={{ color: '#FFF', fontSize: 14, fontWeight: '700', marginLeft: 6 }}>New auto-publish rule</Text>
          </TouchableOpacity>

          {loadingRules ? <ActivityIndicator color={COLORS.primary} /> : rules.length === 0 ? (
            <View style={styles.empty}>
              <Ionicons name="albums-outline" size={32} color={COLORS.textMuted} />
              <Text style={{ color: COLORS.textMuted, marginTop: 8 }}>No rules yet — pre-moderation only.</Text>
            </View>
          ) : rules.map(r => (
            <View key={r.rule_id} style={styles.ruleCard}>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                <Text style={{ color: COLORS.textPrimary, fontWeight: '700', flex: 1 }} numberOfLines={1}>
                  {r.name}
                </Text>
                <View style={[styles.actionPill, {
                  backgroundColor: r.action === 'AUTO_APPROVE' ? '#10B98122' : r.action === 'AUTO_REJECT' ? '#EF444422' : '#F59E0B22',
                }]}>
                  <Text style={[styles.actionPillText, {
                    color: r.action === 'AUTO_APPROVE' ? '#059669' : r.action === 'AUTO_REJECT' ? '#DC2626' : '#D97706',
                  }]}>{r.action.replace('_', ' ').toLowerCase()}</Text>
                </View>
              </View>
              <Text style={{ color: COLORS.textMuted, fontSize: 11, marginTop: 4 }}>
                priority {r.priority} · {r.conditions.length} condition{r.conditions.length === 1 ? '' : 's'}
              </Text>
              {r.conditions.map((c, i) => (
                <Text key={i} style={{ color: COLORS.textSecondary, fontSize: 12, marginTop: 2 }}>
                  • {RULE_FIELDS.find(x => x.id === c.field)?.label || c.field} = {Array.isArray(c.value) ? c.value.join(', ') : String(c.value)}
                </Text>
              ))}
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
                <TouchableOpacity onPress={() => toggleRule(r)} style={[styles.smallBtn, { backgroundColor: r.is_active ? '#F59E0B' : COLORS.success }]}>
                  <Text style={styles.smallBtnText}>{r.is_active ? 'Pause' : 'Resume'}</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => deleteRule(r)} style={[styles.smallBtn, { backgroundColor: COLORS.error }]}>
                  <Text style={styles.smallBtnText}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </ScrollView>
      )}

      {/* CREATE RULE MODAL */}
      <Modal visible={showCreate} transparent animationType="slide" onRequestClose={() => setShowCreate(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.overlay}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>New rule</Text>
            <ScrollView>
              <Text style={styles.fieldLabel}>Name *</Text>
              <TextInput style={styles.input} value={draftName} onChangeText={setDraftName} placeholder="e.g. Verified buyers fast-track" placeholderTextColor={COLORS.textMuted} />

              <Text style={styles.fieldLabel}>Priority (lower runs first)</Text>
              <TextInput style={styles.input} value={draftPriority} onChangeText={setDraftPriority} keyboardType="numeric" placeholder="100" placeholderTextColor={COLORS.textMuted} />

              <Text style={styles.fieldLabel}>Action when ALL conditions match</Text>
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
                {(['AUTO_APPROVE', 'HOLD_FOR_ADMIN', 'AUTO_REJECT'] as const).map(a => (
                  <TouchableOpacity key={a} onPress={() => setDraftAction(a)} style={[
                    { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
                    draftAction === a && { backgroundColor: COLORS.primary + '22', borderColor: COLORS.primary },
                  ]}>
                    <Text style={[{ fontSize: 11, color: COLORS.textSecondary, fontWeight: '600' }, draftAction === a && { color: COLORS.primary }]}>
                      {a.replace('_', ' ').toLowerCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={[styles.fieldLabel, { marginTop: 12 }]}>Conditions (ALL must match)</Text>
              {draftConditions.map((c, i) => {
                const f = RULE_FIELDS.find(x => x.id === c.field);
                return (
                  <View key={i} style={{ marginTop: 8, padding: 8, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8 }}>
                    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
                      {RULE_FIELDS.map(field => (
                        <TouchableOpacity key={field.id} onPress={() => updateCondition(i, 'field', field.id)} style={[
                          { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F9FAFB' },
                          c.field === field.id && { backgroundColor: COLORS.primary + '20', borderColor: COLORS.primary },
                        ]}>
                          <Text style={[{ fontSize: 10, color: COLORS.textSecondary }, c.field === field.id && { color: COLORS.primary, fontWeight: '700' }]}>{field.label}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                    {f?.type === 'bool' ? (
                      <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
                        {[true, false].map(b => (
                          <TouchableOpacity key={String(b)} onPress={() => updateCondition(i, 'value', b)} style={[
                            { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6, borderWidth: 1, borderColor: COLORS.border },
                            c.value === b && { backgroundColor: COLORS.primary + '20', borderColor: COLORS.primary },
                          ]}><Text style={{ fontSize: 12 }}>{b ? 'true' : 'false'}</Text></TouchableOpacity>
                        ))}
                      </View>
                    ) : (
                      <TextInput
                        style={[styles.input, { marginTop: 6 }]}
                        value={String(c.value ?? '')}
                        onChangeText={v => updateCondition(i, 'value', v)}
                        placeholder={f?.type === 'csv' ? 'scam, fraud, fake' : '3'}
                        placeholderTextColor={COLORS.textMuted}
                        keyboardType={f?.type === 'number' ? 'numeric' : 'default'}
                      />
                    )}
                    <TouchableOpacity onPress={() => removeCondition(i)} style={{ marginTop: 6, alignSelf: 'flex-end' }}>
                      <Text style={{ color: COLORS.error, fontSize: 12 }}>Remove</Text>
                    </TouchableOpacity>
                  </View>
                );
              })}
              <TouchableOpacity onPress={addCondition} style={[styles.smallBtn, { backgroundColor: COLORS.primary, marginTop: 8, alignSelf: 'flex-start' }]}>
                <Text style={styles.smallBtnText}>+ Add condition</Text>
              </TouchableOpacity>

              <View style={{ flexDirection: 'row', gap: 8, marginTop: 16, marginBottom: 12 }}>
                <TouchableOpacity style={[styles.smallBtn, { backgroundColor: '#94A3B8', flex: 1 }]} onPress={() => setShowCreate(false)}>
                  <Text style={styles.smallBtnText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[styles.smallBtn, { backgroundColor: COLORS.primary, flex: 1, opacity: busy ? 0.6 : 1 }]} disabled={busy} onPress={submitRule}>
                  {busy ? <ActivityIndicator color="#FFF" /> : <Text style={styles.smallBtnText}>Save rule</Text>}
                </TouchableOpacity>
              </View>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 12, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  tabs: { flexDirection: 'row', backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: COLORS.primary },
  tabText: { fontSize: 13, color: COLORS.textSecondary, fontWeight: '500' },
  tabTextActive: { color: COLORS.primary, fontWeight: '700' },
  empty: { alignItems: 'center', padding: 40 },
  reviewCard: { backgroundColor: COLORS.white, borderRadius: 10, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  reviewBody: { color: COLORS.textPrimary, fontSize: 13, marginTop: 6, lineHeight: 18 },
  actionBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 4 },
  actionBtnText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  bigPrimary: { backgroundColor: COLORS.primary, padding: 12, borderRadius: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  ruleCard: { backgroundColor: COLORS.white, borderRadius: 10, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  actionPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  actionPillText: { fontSize: 10, fontWeight: '700' },
  smallBtn: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  smallBtnText: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '85%' },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 8 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },
});
