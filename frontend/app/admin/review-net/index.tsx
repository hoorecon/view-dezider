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
  Switch,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../src/utils/api';
import { COLORS } from '../../../src/constants/colors';
import { showAlert } from '../../../src/utils/alert';
import { safeBack } from '../../../src/utils/navigation';

type Tab = 'queue' | 'rules' | 'analytics' | 'settings';

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

  // ---- Analytics ----
  const [analytics, setAnalytics] = useState<any>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  const loadAnalytics = useCallback(async () => {
    try {
      setLoadingAnalytics(true);
      const res = await api.get('/review-net/admin/rules/analytics');
      setAnalytics(res.data || null);
    } catch (e: any) {
      showAlert('Analytics error', e?.response?.data?.detail || e.message);
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  // ---- Settings (notifications config) ----
  const [settings, setSettings] = useState<any>(null);
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);

  const loadSettings = useCallback(async () => {
    try {
      setLoadingSettings(true);
      const res = await api.get('/review-net/admin/notifications-config');
      setSettings(res.data);
    } catch (e: any) {
      showAlert('Settings error', e?.response?.data?.detail || e.message);
    } finally {
      setLoadingSettings(false);
    }
  }, []);

  const saveSettings = async (patch: any) => {
    try {
      setSavingSettings(true);
      const res = await api.put('/review-net/admin/notifications-config', { ...settings, ...patch });
      setSettings(res.data);
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || e.message);
    } finally {
      setSavingSettings(false);
    }
  };

  // ---- CSV import / export ----
  const exportCsv = async () => {
    try {
      const backend = process.env.EXPO_PUBLIC_BACKEND_URL || '';
      const url = `${backend}/api/review-net/admin/reviews/export.csv`;
      // Re-issue with current bearer; fetch + Blob to keep auth header
      const tokenRes = await api.get('/auth/me');
      void tokenRes;
      const res = await api.get('/review-net/admin/reviews/export.csv', { responseType: 'blob' as any });
      if (Platform.OS === 'web') {
        // browser download
        const blob = new Blob([res.data], { type: 'text/csv' });
        const dlUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = dlUrl; a.download = `reviewnet_export_${Date.now()}.csv`;
        a.click(); URL.revokeObjectURL(dlUrl);
        showAlert('Export ready', 'CSV download triggered.');
      } else {
        // native: dump first 500 chars
        const text = typeof res.data === 'string' ? res.data : '(binary; download via web)';
        showAlert('Export', text.slice(0, 500));
      }
      console.log('[csv-export] url:', url);
    } catch (e: any) {
      showAlert('Export failed', e?.response?.data?.detail || e.message);
    }
  };

  const importCsv = async (dryRun: boolean) => {
    if (Platform.OS !== 'web') {
      return showAlert('Import', 'CSV import is currently web-only — open the admin in a browser to use it.');
    }
    // Web: trigger a hidden file input
    const input = document.createElement('input');
    input.type = 'file'; input.accept = '.csv,text/csv';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const fd = new FormData();
      fd.append('file', file);
      try {
        const res = await api.post(
          `/review-net/admin/reviews/import?dry_run=${dryRun}`,
          fd,
          { headers: { 'Content-Type': 'multipart/form-data' } },
        );
        const d = res.data;
        const lines = [
          dryRun ? 'DRY RUN' : 'IMPORT',
          `rows total: ${d.rows_total}`,
          `accepted: ${d.rows_accepted}`,
          `skipped: ${d.rows_skipped}`,
          d.errors?.length ? `\nFirst errors:\n${d.errors.slice(0, 3).map((e: any) => `· row ${e.row}: ${e.error}`).join('\n')}` : '',
        ].filter(Boolean).join('\n');
        showAlert(dryRun ? 'Dry run complete' : 'Import complete', lines);
        if (!dryRun) loadQueue();
      } catch (e: any) {
        showAlert('Import failed', e?.response?.data?.detail || e.message);
      }
    };
    input.click();
  };

  useEffect(() => { loadQueue(); }, [loadQueue]);
  useEffect(() => { if (tab === 'rules') loadRules(); }, [tab, loadRules]);
  useEffect(() => { if (tab === 'analytics') loadAnalytics(); }, [tab, loadAnalytics]);
  useEffect(() => { if (tab === 'settings') loadSettings(); }, [tab, loadSettings]);

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
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
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
        <TouchableOpacity testID="rn-analytics-tab" onPress={() => setTab('analytics')} style={[styles.tab, tab === 'analytics' && styles.tabActive]}>
          <Text style={[styles.tabText, tab === 'analytics' && styles.tabTextActive]}>Analytics</Text>
        </TouchableOpacity>
        <TouchableOpacity testID="rn-settings-tab" onPress={() => setTab('settings')} style={[styles.tab, tab === 'settings' && styles.tabActive]}>
          <Text style={[styles.tabText, tab === 'settings' && styles.tabTextActive]}>Settings</Text>
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
          <View style={{ flexDirection: 'row', gap: 8, marginBottom: 10 }}>
            <TouchableOpacity testID="rn-export-csv" style={[styles.smallBtn, { backgroundColor: '#0F766E', flex: 1, paddingVertical: 10 }]} onPress={exportCsv}>
              <Text style={styles.smallBtnText}>↓ Export CSV</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.smallBtn, { backgroundColor: '#7C3AED', flex: 1, paddingVertical: 10 }]} onPress={() => importCsv(true)}>
              <Text style={styles.smallBtnText}>↑ Import (dry-run)</Text>
            </TouchableOpacity>
            <TouchableOpacity testID="rn-import-csv" style={[styles.smallBtn, { backgroundColor: COLORS.primary, flex: 1, paddingVertical: 10 }]} onPress={() => importCsv(false)}>
              <Text style={styles.smallBtnText}>↑ Import</Text>
            </TouchableOpacity>
          </View>
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

      {/* ANALYTICS TAB */}
      {tab === 'analytics' && (
        <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 60 }}>
          {loadingAnalytics ? <ActivityIndicator color={COLORS.primary} /> : !analytics ? (
            <View style={styles.empty}><Text style={{ color: COLORS.textMuted }}>No data</Text></View>
          ) : (
            <>
              {/* Top KPIs */}
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
                <View style={[styles.kpiCard, { backgroundColor: '#1E3A8A22' }]}>
                  <Text style={[styles.kpiNum, { color: '#1E3A8A' }]}>{analytics.global.total_reviews}</Text>
                  <Text style={styles.kpiLabel}>Total reviews</Text>
                </View>
                <View style={[styles.kpiCard, { backgroundColor: '#10B98122' }]}>
                  <Text style={[styles.kpiNum, { color: '#059669' }]}>{analytics.global.auto_rate_pct}%</Text>
                  <Text style={styles.kpiLabel}>Auto-handled</Text>
                </View>
                <View style={[styles.kpiCard, { backgroundColor: '#F59E0B22' }]}>
                  <Text style={[styles.kpiNum, { color: '#D97706' }]}>{analytics.global.pending}</Text>
                  <Text style={styles.kpiLabel}>Pending</Text>
                </View>
                <View style={[styles.kpiCard, { backgroundColor: '#EF444422' }]}>
                  <Text style={[styles.kpiNum, { color: '#DC2626' }]}>{analytics.global.rejected}</Text>
                  <Text style={styles.kpiLabel}>Rejected</Text>
                </View>
              </View>

              {/* Status distribution bar */}
              <Text style={styles.sectionH}>Status mix</Text>
              {(() => {
                const t = analytics.global.total_reviews || 1;
                const seg = (label: string, n: number, color: string) => (
                  <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
                    <Text style={{ width: 110, fontSize: 12, color: COLORS.textSecondary }}>{label}</Text>
                    <View style={{ flex: 1, height: 8, backgroundColor: '#F1F5F9', borderRadius: 4, overflow: 'hidden' }}>
                      <View style={{ width: `${(n / t) * 100}%`, height: 8, backgroundColor: color }} />
                    </View>
                    <Text style={{ width: 32, textAlign: 'right', fontSize: 12, color: COLORS.textPrimary, fontWeight: '600' }}>{n}</Text>
                  </View>
                );
                return (
                  <View style={styles.cardBlock}>
                    {seg('auto_approved', analytics.global.auto_approved, '#10B981')}
                    {seg('approved (manual)', analytics.global.approved, '#3B82F6')}
                    {seg('pending', analytics.global.pending, '#F59E0B')}
                    {seg('rejected', analytics.global.rejected, '#EF4444')}
                  </View>
                );
              })()}

              {/* Per-rule rollup */}
              <Text style={styles.sectionH}>Per-rule performance</Text>
              {analytics.rules.length === 0 ? (
                <View style={styles.cardBlock}>
                  <Text style={{ color: COLORS.textMuted, fontSize: 12 }}>No rules configured yet — every review is held for admin.</Text>
                </View>
              ) : analytics.rules.map((r: any) => (
                <View key={r.rule_id} style={styles.cardBlock}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                    <Text style={{ fontWeight: '700', color: COLORS.textPrimary, flex: 1 }} numberOfLines={1}>{r.name}</Text>
                    <View style={[styles.actionPill, {
                      backgroundColor: r.action === 'AUTO_APPROVE' ? '#10B98122' : r.action === 'AUTO_REJECT' ? '#EF444422' : '#F59E0B22',
                    }]}>
                      <Text style={[styles.actionPillText, {
                        color: r.action === 'AUTO_APPROVE' ? '#059669' : r.action === 'AUTO_REJECT' ? '#DC2626' : '#D97706',
                      }]}>{r.action.replace('_', ' ').toLowerCase()}</Text>
                    </View>
                  </View>
                  <Text style={{ color: COLORS.textMuted, fontSize: 11, marginTop: 2 }}>
                    priority {r.priority} · {r.is_active ? 'active' : 'paused'} · {r.conditions_count} condition(s)
                  </Text>
                  <View style={{ flexDirection: 'row', gap: 14, marginTop: 8 }}>
                    <View><Text style={styles.statN}>{r.match_count}</Text><Text style={styles.statL}>total matches</Text></View>
                    <View><Text style={[styles.statN, { color: '#059669' }]}>{r.auto_approved}</Text><Text style={styles.statL}>approved</Text></View>
                    <View><Text style={[styles.statN, { color: '#DC2626' }]}>{r.auto_rejected}</Text><Text style={styles.statL}>rejected</Text></View>
                    <View><Text style={[styles.statN, { color: '#D97706' }]}>{r.held}</Text><Text style={styles.statL}>held</Text></View>
                  </View>
                  {r.last_matched_at && (
                    <Text style={{ color: COLORS.textMuted, fontSize: 10, marginTop: 6 }}>
                      Last matched: {new Date(r.last_matched_at).toLocaleString()}
                    </Text>
                  )}
                </View>
              ))}

              {/* Reviews flagged with rule (deeper attribution) */}
              {analytics.reviews_by_matched_rule?.length > 0 && (
                <>
                  <Text style={styles.sectionH}>Reviews attributed to rule</Text>
                  <View style={styles.cardBlock}>
                    {analytics.reviews_by_matched_rule.map((r: any, i: number) => (
                      <View key={i} style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: i < analytics.reviews_by_matched_rule.length - 1 ? 1 : 0, borderBottomColor: '#F1F5F9' }}>
                        <Text style={{ flex: 1, color: COLORS.textPrimary, fontSize: 13 }} numberOfLines={1}>{r.rule_name}</Text>
                        <Text style={{ fontSize: 13, fontWeight: '700', color: COLORS.primary }}>{r.review_count}</Text>
                      </View>
                    ))}
                  </View>
                </>
              )}

              {/* Last 7 days trend */}
              {analytics.last_7_days?.length > 0 && (
                <>
                  <Text style={styles.sectionH}>Last 7 days</Text>
                  <View style={styles.cardBlock}>
                    {analytics.last_7_days.map((d: any) => {
                      const total = d.pending + d.auto_approved + d.approved + d.rejected;
                      return (
                        <View key={d.day} style={{ marginBottom: 6 }}>
                          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 2 }}>
                            <Text style={{ fontSize: 11, color: COLORS.textSecondary }}>{d.day}</Text>
                            <Text style={{ fontSize: 11, color: COLORS.textPrimary, fontWeight: '600' }}>{total}</Text>
                          </View>
                          <View style={{ flexDirection: 'row', height: 6, borderRadius: 3, overflow: 'hidden', backgroundColor: '#F1F5F9' }}>
                            {d.auto_approved > 0 && <View style={{ flex: d.auto_approved, backgroundColor: '#10B981' }} />}
                            {d.approved > 0 && <View style={{ flex: d.approved, backgroundColor: '#3B82F6' }} />}
                            {d.pending > 0 && <View style={{ flex: d.pending, backgroundColor: '#F59E0B' }} />}
                            {d.rejected > 0 && <View style={{ flex: d.rejected, backgroundColor: '#EF4444' }} />}
                          </View>
                        </View>
                      );
                    })}
                  </View>
                </>
              )}
            </>
          )}
        </ScrollView>
      )}

      {/* SETTINGS TAB — Notifications config (in-app / email / push) */}
      {tab === 'settings' && (
        <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 60 }}>
          {loadingSettings || !settings ? <ActivityIndicator color={COLORS.primary} /> : (
            <>
              {/* In-app */}
              <View style={styles.settingCard}>
                <View style={styles.settingRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.settingTitle}>In-app notifications</Text>
                    <Text style={styles.settingHint}>Always recommended. No external API needed.</Text>
                  </View>
                  <Switch
                    value={!!settings.in_app_enabled}
                    onValueChange={v => saveSettings({ in_app_enabled: v })}
                    disabled={savingSettings}
                  />
                </View>
              </View>

              {/* Email */}
              <View style={styles.settingCard}>
                <View style={styles.settingRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.settingTitle}>Email notifications</Text>
                    <Text style={styles.settingHint}>
                      Auto-disabled if creds missing. {settings.email_api_key_set ? '✓ creds set' : '✗ creds not set'}
                    </Text>
                  </View>
                  <Switch
                    value={!!settings.email_enabled}
                    onValueChange={v => saveSettings({ email_enabled: v })}
                    disabled={savingSettings}
                  />
                </View>
                <Text style={styles.fieldLabel}>Provider</Text>
                <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
                  {(['sendgrid', 'smtp'] as const).map(p => (
                    <TouchableOpacity key={p} style={[
                      { flex: 1, paddingVertical: 8, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
                      settings.email_provider === p && { backgroundColor: COLORS.primary + '20', borderColor: COLORS.primary },
                    ]} onPress={() => saveSettings({ email_provider: p })}>
                      <Text style={[{ fontSize: 11, color: COLORS.textSecondary }, settings.email_provider === p && { color: COLORS.primary, fontWeight: '700' }]}>{p}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <Text style={styles.fieldLabel}>From address</Text>
                <TextInput
                  style={styles.input}
                  value={settings.email_from_address || ''}
                  onChangeText={v => setSettings({ ...settings, email_from_address: v })}
                  onBlur={() => saveSettings({ email_from_address: settings.email_from_address })}
                  placeholder="no-reply@viewdezider.app" placeholderTextColor={COLORS.textMuted}
                  autoCapitalize="none" keyboardType="email-address"
                />
                {settings.email_provider === 'sendgrid' ? (
                  <>
                    <Text style={styles.fieldLabel}>SendGrid API key</Text>
                    <TextInput
                      style={styles.input}
                      placeholder={settings.email_api_key_set ? '•••configured•••' : 'SG.xxxxx…'}
                      placeholderTextColor={COLORS.textMuted}
                      onSubmitEditing={(e: any) => saveSettings({ email_api_key: e.nativeEvent.text })}
                      secureTextEntry autoCapitalize="none"
                    />
                  </>
                ) : settings.email_provider === 'smtp' ? (
                  <>
                    <Text style={styles.fieldLabel}>SMTP host</Text>
                    <TextInput style={styles.input} value={settings.smtp_host || ''}
                      onChangeText={v => setSettings({ ...settings, smtp_host: v })}
                      onBlur={() => saveSettings({ smtp_host: settings.smtp_host })}
                      placeholder="smtp.gmail.com" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" />
                    <Text style={styles.fieldLabel}>SMTP port</Text>
                    <TextInput style={styles.input} value={String(settings.smtp_port || 587)}
                      onChangeText={v => setSettings({ ...settings, smtp_port: v })}
                      onBlur={() => saveSettings({ smtp_port: settings.smtp_port })}
                      keyboardType="numeric" />
                    <Text style={styles.fieldLabel}>SMTP user</Text>
                    <TextInput style={styles.input} value={settings.smtp_user || ''}
                      onChangeText={v => setSettings({ ...settings, smtp_user: v })}
                      onBlur={() => saveSettings({ smtp_user: settings.smtp_user })}
                      placeholder="bot@example.com" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" />
                    <Text style={styles.fieldLabel}>SMTP password</Text>
                    <TextInput
                      style={styles.input}
                      placeholder={settings.email_api_key_set ? '•••configured•••' : '••••••••'}
                      placeholderTextColor={COLORS.textMuted}
                      onSubmitEditing={(e: any) => saveSettings({ smtp_password: e.nativeEvent.text })}
                      secureTextEntry autoCapitalize="none"
                    />
                  </>
                ) : null}
              </View>

              {/* Push */}
              <View style={styles.settingCard}>
                <View style={styles.settingRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.settingTitle}>Push notifications</Text>
                    <Text style={styles.settingHint}>
                      {settings.push_credentials_set ? '✓ creds set' : settings.push_provider === 'expo' ? 'Expo Push needs no API key' : '✗ creds not set'}
                    </Text>
                  </View>
                  <Switch
                    value={!!settings.push_enabled}
                    onValueChange={v => saveSettings({ push_enabled: v })}
                    disabled={savingSettings}
                  />
                </View>
                <Text style={styles.fieldLabel}>Provider</Text>
                <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
                  {(['expo', 'fcm'] as const).map(p => (
                    <TouchableOpacity key={p} style={[
                      { flex: 1, paddingVertical: 8, borderRadius: 8, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
                      settings.push_provider === p && { backgroundColor: COLORS.primary + '20', borderColor: COLORS.primary },
                    ]} onPress={() => saveSettings({ push_provider: p })}>
                      <Text style={[{ fontSize: 11, color: COLORS.textSecondary }, settings.push_provider === p && { color: COLORS.primary, fontWeight: '700' }]}>{p === 'fcm' ? 'FCM (Android/iOS)' : 'Expo Push'}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
                {settings.push_provider === 'fcm' && (
                  <>
                    <Text style={styles.fieldLabel}>FCM server key</Text>
                    <TextInput
                      style={styles.input}
                      placeholder={settings.push_credentials_set ? '•••configured•••' : 'AAA…'}
                      placeholderTextColor={COLORS.textMuted}
                      onSubmitEditing={(e: any) => saveSettings({ push_server_key: e.nativeEvent.text })}
                      secureTextEntry autoCapitalize="none"
                    />
                  </>
                )}
              </View>

              <Text style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 8, textAlign: 'center' }}>
                Channels with missing credentials are auto-disabled on save. In-app channel is always free.
              </Text>
            </>
          )}
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

  // analytics
  kpiCard: { width: '48%', padding: 14, borderRadius: 12 },
  kpiNum: { fontSize: 24, fontWeight: '800' },
  kpiLabel: { fontSize: 11, color: COLORS.textSecondary, marginTop: 2 },
  cardBlock: { backgroundColor: COLORS.white, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 10 },
  sectionH: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginTop: 8, marginBottom: 6 },
  statN: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary },
  statL: { fontSize: 9, color: COLORS.textMuted, marginTop: 1 },
  // settings tab
  settingCard: { backgroundColor: COLORS.white, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 },
  settingRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  settingTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  settingHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
});
