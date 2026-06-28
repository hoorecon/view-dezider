import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Modal, TextInput, Platform, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { COLORS } from '../../constants/colors';
import api from '../../utils/api';
import { showAlert } from '../../utils/alert';

interface Meta {
  life_areas: { id: string; name: string; icon: string; color: string }[];
  sub_types: { id: string; name: string; color: string; icon: string }[];
  levels: { level: number; key: string; label: string; horizon: string; requires_life_area?: boolean; requires_sub_type?: boolean }[];
  horizons: { id: string; name: string }[];
}

interface LG {
  goal_id: string;
  title: string;
  description?: string;
  lg_mode: 'timeline' | 'tree';
  lg_level?: number | null;
  parent_id?: string | null;
  horizon?: string | null;
  life_area?: string;
  sub_type?: string | null;
  status?: string;
  progress_percent?: number;
  target_date?: string | null;
}

type FormState = {
  goal_id?: string;       // set when editing
  mode: 'timeline' | 'tree';
  level?: number;
  parent_id?: string | null;
  parent_title?: string;
  title: string;
  description: string;
  horizon: string;
  life_area: string;
  sub_type: string;
  target_date: string;
};

const emptyForm = (mode: 'timeline' | 'tree'): FormState => ({
  mode, title: '', description: '', horizon: '', life_area: '', sub_type: '', target_date: '',
});

export default function LifeGoalsPanel() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isWide = width >= 768;
  const [meta, setMeta] = useState<Meta | null>(null);
  const [mode, setMode] = useState<'timeline' | 'tree'>('timeline');
  const [goals, setGoals] = useState<LG[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const [modalOpen, setModalOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm('timeline'));
  const [saving, setSaving] = useState(false);

  const areaCfg = (id?: string | null) => meta?.life_areas.find((a) => a.id === id);
  const subCfg = (id?: string | null) => meta?.sub_types.find((s) => s.id === id);
  const levelCfg = (lvl?: number | null) => meta?.levels.find((l) => l.level === lvl);

  const load = useCallback(async () => {
    try {
      const [m, list] = await Promise.all([
        meta ? Promise.resolve({ data: meta }) : api.get('/life-goals/meta'),
        api.get('/life-goals', { params: { mode } }),
      ]);
      if (!meta) setMeta(m.data);
      setGoals(list.data || []);
    } catch (e) {
      console.error('life-goals load', e);
    } finally {
      setLoading(false);
    }
  }, [mode, meta]);

  useEffect(() => { setLoading(true); load(); }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Modal openers ──
  const openTimelineAdd = (lifeArea?: string) => {
    setForm({ ...emptyForm('timeline'), life_area: lifeArea || '' });
    setModalOpen(true);
  };
  const openTreeAdd = (level: number, parent?: LG) => {
    setForm({
      ...emptyForm('tree'),
      level,
      parent_id: parent?.goal_id || null,
      parent_title: parent?.title,
      life_area: parent?.life_area || '',
    });
    setModalOpen(true);
  };
  const openEdit = (g: LG) => {
    setForm({
      goal_id: g.goal_id,
      mode: g.lg_mode,
      level: g.lg_level || undefined,
      parent_id: g.parent_id || null,
      title: g.title || '',
      description: g.description || '',
      horizon: g.horizon || '',
      life_area: g.life_area || '',
      sub_type: g.sub_type || '',
      target_date: g.target_date || '',
    });
    setModalOpen(true);
  };

  const requiresArea = form.mode === 'timeline' || form.level === 5;
  const requiresSub = form.level === 6;

  const handleSave = async () => {
    if (!form.title.trim()) return showAlert('Title required', 'Give this goal a title.');
    if (requiresArea && !form.life_area)
      return showAlert('Life Area required', 'Pick a Life Area for this goal.');
    if (requiresSub && !form.sub_type)
      return showAlert('Sub-type required', 'A Quarterly (L6) goal must be mapped to a sub-type.');
    if (form.mode === 'timeline' && !form.horizon)
      return showAlert('Timeline required', 'Choose a target horizon.');

    setSaving(true);
    try {
      const payload: any = {
        mode: form.mode,
        title: form.title.trim(),
        description: form.description.trim(),
        life_area: form.life_area || undefined,
        sub_type: form.sub_type || undefined,
        target_date: form.target_date.trim() || undefined,
      };
      if (form.mode === 'timeline') payload.horizon = form.horizon;
      else { payload.level = form.level; payload.parent_id = form.parent_id; }

      if (form.goal_id) await api.put(`/life-goals/${form.goal_id}`, payload);
      else await api.post('/life-goals', payload);
      setModalOpen(false);
      await load();
    } catch (e: any) {
      showAlert('Could not save', e?.response?.data?.detail || 'Try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (g: LG) => {
    const isTree = g.lg_mode === 'tree';
    showAlert(
      'Delete goal',
      isTree ? 'This deletes the goal and ALL goals nested under it. Continue?' : 'Delete this goal?',
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Delete', style: 'destructive', onPress: async () => {
          try { await api.delete(`/life-goals/${g.goal_id}`); await load(); }
          catch { showAlert('Error', 'Could not delete.'); }
        } },
      ],
    );
  };

  // ── Renderers ──
  const renderProgress = (pct?: number) => {
    const p = Math.max(0, Math.min(100, pct || 0));
    return (
      <View style={s.progressWrap}>
        <View style={[s.progressFill, { width: `${p}%` }]} />
      </View>
    );
  };

  const renderTimeline = () => {
    const areas = meta?.life_areas || [];
    return (
      <>
        {areas.map((area) => {
          const items = goals.filter((g) => g.life_area === area.id);
          return (
            <View key={area.id} style={s.areaBlock}>
              <View style={s.areaHead}>
                <View style={[s.areaIcon, { backgroundColor: area.color + '20' }]}>
                  <Ionicons name={area.icon as any} size={16} color={area.color} />
                </View>
                <Text style={s.areaName}>{area.name}</Text>
                <Text style={s.areaCount}>{items.length}</Text>
                <TouchableOpacity style={s.addMini} onPress={() => openTimelineAdd(area.id)} testID={`lg-add-${area.id}`}>
                  <Ionicons name="add" size={16} color={COLORS.primary} />
                </TouchableOpacity>
              </View>
              {items.map((g) => {
                const h = meta?.horizons.find((x) => x.id === g.horizon);
                const st = subCfg(g.sub_type);
                return (
                  <TouchableOpacity key={g.goal_id} style={s.goalCard} onPress={() => openEdit(g)} activeOpacity={0.8}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.goalTitle} numberOfLines={2}>{g.title}</Text>
                      <View style={s.chipsRow}>
                        {h && <View style={[s.tag, { backgroundColor: '#EEF2FF' }]}><Text style={[s.tagTxt, { color: '#4338CA' }]}>{h.name}</Text></View>}
                        {st && <View style={[s.tag, { backgroundColor: st.color + '20' }]}><Text style={[s.tagTxt, { color: st.color }]}>{st.name}</Text></View>}
                      </View>
                      {renderProgress(g.progress_percent)}
                    </View>
                    <TouchableOpacity hitSlop={8} onPress={() => handleDelete(g)}>
                      <Ionicons name="trash-outline" size={16} color="#EF4444" />
                    </TouchableOpacity>
                  </TouchableOpacity>
                );
              })}
              {items.length === 0 && <Text style={s.emptyMini}>No goals yet — tap + to add one.</Text>}
            </View>
          );
        })}
      </>
    );
  };

  const renderTreeNode = (node: LG, depth: number): React.ReactNode => {
    const children = goals.filter((g) => g.parent_id === node.goal_id);
    const lvl = levelCfg(node.lg_level);
    const isCollapsed = collapsed[node.goal_id];
    const st = subCfg(node.sub_type);
    const area = areaCfg(node.life_area);
    return (
      <View key={node.goal_id} style={{ marginLeft: depth * 12 }}>
        <View style={[s.treeCard, { borderLeftColor: st?.color || area?.color || COLORS.primary }]}>
          {children.length > 0 ? (
            <TouchableOpacity hitSlop={8} onPress={() => setCollapsed((c) => ({ ...c, [node.goal_id]: !c[node.goal_id] }))}>
              <Ionicons name={isCollapsed ? 'chevron-forward' : 'chevron-down'} size={16} color="#94A3B8" />
            </TouchableOpacity>
          ) : <View style={{ width: 16 }} />}
          <View style={{ flex: 1, marginLeft: 6 }}>
            <View style={s.lvlRow}>
              <View style={s.lvlBadge}><Text style={s.lvlBadgeTxt}>L{node.lg_level}</Text></View>
              <Text style={s.lvlLabel}>{lvl?.label}</Text>
            </View>
            <Text style={s.goalTitle} numberOfLines={2}>{node.title}</Text>
            <View style={s.chipsRow}>
              {area && <View style={[s.tag, { backgroundColor: area.color + '20' }]}><Text style={[s.tagTxt, { color: area.color }]}>{area.name}</Text></View>}
              {st && <View style={[s.tag, { backgroundColor: st.color + '20' }]}><Text style={[s.tagTxt, { color: st.color }]}>{st.name}</Text></View>}
            </View>
          </View>
          <View style={s.treeActions}>
            {(node.lg_level || 1) < 7 && (
              <TouchableOpacity hitSlop={8} onPress={() => openTreeAdd((node.lg_level || 1) + 1, node)} testID={`lg-add-child-${node.goal_id}`}>
                <Ionicons name="add-circle-outline" size={18} color={COLORS.primary} />
              </TouchableOpacity>
            )}
            <TouchableOpacity hitSlop={8} onPress={() => openEdit(node)}>
              <Ionicons name="pencil" size={15} color="#6B7280" />
            </TouchableOpacity>
            <TouchableOpacity hitSlop={8} onPress={() => handleDelete(node)}>
              <Ionicons name="trash-outline" size={15} color="#EF4444" />
            </TouchableOpacity>
          </View>
        </View>
        {!isCollapsed && children.map((c) => renderTreeNode(c, depth + 1))}
      </View>
    );
  };

  const renderTree = () => {
    const roots = goals.filter((g) => g.lg_level === 1);
    return (
      <>
        <TouchableOpacity style={s.addL1} onPress={() => openTreeAdd(1)} testID="lg-add-overall">
          <Ionicons name="add" size={18} color="#FFF" />
          <Text style={s.addL1Txt}>Add Overall Life Goal (L1)</Text>
        </TouchableOpacity>
        {roots.length === 0 ? (
          <View style={s.emptyState}>
            <Ionicons name="git-branch-outline" size={42} color="#CBD5E1" />
            <Text style={s.emptyTxt}>Start your 7-level plan</Text>
            <Text style={s.emptySub}>L1 Overall → 10yr → 5yr → 3yr → 1yr (area) → Quarterly (sub-type) → Monthly</Text>
          </View>
        ) : roots.map((r) => renderTreeNode(r, 0))}
      </>
    );
  };

  // ── Modal ──
  const renderModal = () => {
    const lvl = levelCfg(form.level);
    const heading = form.goal_id
      ? 'Edit Goal'
      : form.mode === 'timeline'
        ? 'New Life-Area Goal'
        : `New ${lvl?.label || 'Goal'}${form.parent_title ? ` · under "${form.parent_title}"` : ''}`;
    return (
      <Modal visible={modalOpen} transparent animationType={isWide ? 'fade' : 'slide'} onRequestClose={() => setModalOpen(false)}>
        <View style={isWide ? s.ovWide : s.ov}>
          <View style={isWide ? s.sheetWide : s.sheet}>
            <View style={s.sheetHead}>
              <Text style={s.sheetTitle} numberOfLines={2}>{heading}</Text>
              <TouchableOpacity onPress={() => setModalOpen(false)}><Ionicons name="close" size={24} color="#6B7280" /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 460 }} showsVerticalScrollIndicator={false}>
              <Text style={s.label}>Title *</Text>
              <TextInput style={s.input} value={form.title} onChangeText={(t) => setForm({ ...form, title: t })}
                placeholder="What do you want to achieve?" placeholderTextColor="#9CA3AF" testID="lg-title" />

              <Text style={s.label}>Description</Text>
              <TextInput style={[s.input, { height: 70, textAlignVertical: 'top' }]} multiline
                value={form.description} onChangeText={(t) => setForm({ ...form, description: t })}
                placeholder="Optional details…" placeholderTextColor="#9CA3AF" />

              {form.mode === 'timeline' && (
                <>
                  <Text style={s.label}>Target horizon *</Text>
                  <View style={s.wrapRow}>
                    {meta?.horizons.map((h) => (
                      <TouchableOpacity key={h.id} style={[s.pick, form.horizon === h.id && s.pickOn]} onPress={() => setForm({ ...form, horizon: h.id })}>
                        <Text style={[s.pickTxt, form.horizon === h.id && s.pickTxtOn]}>{h.name}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </>
              )}

              {requiresArea && (
                <>
                  <Text style={s.label}>Life Area *</Text>
                  <View style={s.wrapRow}>
                    {meta?.life_areas.map((a) => (
                      <TouchableOpacity key={a.id} style={[s.pick, form.life_area === a.id && { backgroundColor: a.color, borderColor: a.color }]} onPress={() => setForm({ ...form, life_area: a.id })}>
                        <Text style={[s.pickTxt, form.life_area === a.id && s.pickTxtOn]}>{a.name}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </>
              )}

              {(form.mode === 'timeline' || requiresSub) && (
                <>
                  <Text style={s.label}>Sub-type {requiresSub ? '*' : '(optional)'}</Text>
                  <View style={s.wrapRow}>
                    {meta?.sub_types.map((st) => (
                      <TouchableOpacity key={st.id} style={[s.pick, form.sub_type === st.id && { backgroundColor: st.color, borderColor: st.color }]} onPress={() => setForm({ ...form, sub_type: form.sub_type === st.id ? '' : st.id })}>
                        <Ionicons name={st.icon as any} size={13} color={form.sub_type === st.id ? '#FFF' : st.color} />
                        <Text style={[s.pickTxt, { marginLeft: 4 }, form.sub_type === st.id && s.pickTxtOn]}>{st.name}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </>
              )}

              <Text style={s.label}>Target date (optional)</Text>
              <TextInput style={s.input} value={form.target_date} onChangeText={(t) => setForm({ ...form, target_date: t })}
                placeholder="YYYY-MM-DD" placeholderTextColor="#9CA3AF" />
            </ScrollView>
            <TouchableOpacity style={[s.saveBtn, saving && { opacity: 0.6 }]} onPress={handleSave} disabled={saving} testID="lg-save">
              {saving ? <ActivityIndicator color="#FFF" /> : <Text style={s.saveTxt}>{form.goal_id ? 'Update' : 'Save'}</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    );
  };

  if (loading) return <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />;

  return (
    <View>
      {/* Mode toggle */}
      <View style={s.modeTabs}>
        <TouchableOpacity style={[s.modeTab, mode === 'timeline' && s.modeTabOn]} onPress={() => setMode('timeline')} testID="lg-mode-timeline">
          <Ionicons name="calendar-outline" size={14} color={mode === 'timeline' ? '#4338CA' : '#64748B'} />
          <Text style={[s.modeTxt, mode === 'timeline' && s.modeTxtOn]}>By Life Area</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.modeTab, mode === 'tree' && s.modeTabOn]} onPress={() => setMode('tree')} testID="lg-mode-tree">
          <Ionicons name="git-branch-outline" size={14} color={mode === 'tree' ? '#4338CA' : '#64748B'} />
          <Text style={[s.modeTxt, mode === 'tree' && s.modeTxtOn]}>7-Level Tree</Text>
        </TouchableOpacity>
      </View>

      <Text style={s.hint}>
        {mode === 'timeline'
          ? 'Set goals per Life Area with a target horizon. Saved in GEM (Goal Execution Manager).'
          : 'Build a strict hierarchy: L1 Overall → 10yr → 5yr → 3yr → 1yr (Life Area) → Quarterly (sub-type) → Monthly.'}
      </Text>

      {mode === 'timeline' ? renderTimeline() : renderTree()}

      <TouchableOpacity style={s.gemLink} onPress={() => router.push('/tools/gem' as any)}>
        <Ionicons name="open-outline" size={14} color={COLORS.primary} />
        <Text style={s.gemLinkTxt}>Open Goal Execution Manager (GEM)</Text>
      </TouchableOpacity>

      {renderModal()}
    </View>
  );
}

const s = StyleSheet.create({
  modeTabs: { flexDirection: 'row', gap: 8, backgroundColor: '#EEF2FF', borderRadius: 12, padding: 4, marginBottom: 10 },
  modeTab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 9, borderRadius: 9 },
  modeTabOn: { backgroundColor: '#FFFFFF' },
  modeTxt: { fontSize: 13, fontWeight: '700', color: '#64748B' },
  modeTxtOn: { color: '#4338CA' },
  hint: { fontSize: 11.5, color: '#94A3B8', lineHeight: 16, marginBottom: 14 },

  areaBlock: { marginBottom: 14 },
  areaHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  areaIcon: { width: 28, height: 28, borderRadius: 8, justifyContent: 'center', alignItems: 'center' },
  areaName: { flex: 1, fontSize: 14, fontWeight: '700', color: '#0F172A' },
  areaCount: { fontSize: 12, fontWeight: '700', color: '#94A3B8' },
  addMini: { width: 28, height: 28, borderRadius: 8, backgroundColor: '#EEF2FF', justifyContent: 'center', alignItems: 'center' },
  emptyMini: { fontSize: 12, color: '#CBD5E1', fontStyle: 'italic', marginLeft: 4 },

  goalCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFFFFF', borderRadius: 12, padding: 12, marginBottom: 8 },
  goalTitle: { fontSize: 14, fontWeight: '600', color: '#0F172A' },
  chipsRow: { flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' },
  tag: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  tagTxt: { fontSize: 10.5, fontWeight: '700' },
  progressWrap: { height: 5, borderRadius: 3, backgroundColor: '#E2E8F0', marginTop: 8, overflow: 'hidden' },
  progressFill: { height: 5, borderRadius: 3, backgroundColor: '#10B981' },

  addL1: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 12, marginBottom: 14 },
  addL1Txt: { color: '#FFF', fontSize: 14, fontWeight: '700' },
  treeCard: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#FFFFFF', borderRadius: 12, padding: 12, marginBottom: 8, borderLeftWidth: 4 },
  lvlRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 3 },
  lvlBadge: { backgroundColor: '#EEF2FF', borderRadius: 5, paddingHorizontal: 6, paddingVertical: 1 },
  lvlBadgeTxt: { fontSize: 10, fontWeight: '800', color: '#4338CA' },
  lvlLabel: { fontSize: 10.5, fontWeight: '700', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: 0.3 },
  treeActions: { flexDirection: 'row', alignItems: 'center', gap: 10, marginLeft: 6 },

  emptyState: { alignItems: 'center', paddingVertical: 30 },
  emptyTxt: { fontSize: 15, fontWeight: '700', color: '#64748B', marginTop: 10 },
  emptySub: { fontSize: 11.5, color: '#94A3B8', marginTop: 4, textAlign: 'center', paddingHorizontal: 20, lineHeight: 16 },

  gemLink: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 8, paddingVertical: 10 },
  gemLinkTxt: { color: COLORS.primary, fontSize: 13, fontWeight: '700' },

  // modal
  ov: { flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', justifyContent: 'flex-end' },
  ovWide: { flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  sheet: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '88%' },
  sheetWide: { backgroundColor: '#FFFFFF', borderRadius: 18, padding: 24, maxWidth: 520, width: '100%', maxHeight: '88%' },
  sheetHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14, gap: 12 },
  sheetTitle: { flex: 1, fontSize: 17, fontWeight: '700', color: '#0F172A' },
  label: { fontSize: 12, fontWeight: '700', color: '#475569', marginBottom: 6, marginTop: 10, textTransform: 'uppercase', letterSpacing: 0.4 },
  input: { backgroundColor: '#F8FAFC', borderRadius: 10, borderWidth: 1, borderColor: '#E5E7EB', color: '#0F172A', paddingHorizontal: 12, paddingVertical: 10, fontSize: 14 },
  wrapRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pick: { flexDirection: 'row', alignItems: 'center', borderRadius: 8, borderWidth: 1.5, borderColor: '#E5E7EB', paddingHorizontal: 12, paddingVertical: 7, backgroundColor: '#FFF' },
  pickOn: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  pickTxt: { fontSize: 12.5, fontWeight: '600', color: '#475569' },
  pickTxtOn: { color: '#FFF' },
  saveBtn: { backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 16 },
  saveTxt: { color: '#FFF', fontSize: 16, fontWeight: '700' },
});
