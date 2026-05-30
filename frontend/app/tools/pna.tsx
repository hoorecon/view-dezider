import React, { useState, useCallback, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Modal, TextInput,
  KeyboardAvoidingView, Platform, useWindowDimensions,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import TimestampLine from '../../src/components/TimestampLine';

const CAT_CFG: Record<string, { color: string; icon: string; label: string }> = {
  problem:    { color: '#EF4444', icon: 'alert-circle',  label: 'Problem' },
  need:       { color: '#F59E0B', icon: 'bulb',          label: 'Need' },
  aspiration: { color: '#10B981', icon: 'rocket',        label: 'Aspiration' },
};

const STATUS_CFG: Record<string, { color: string; label: string }> = {
  open:        { color: '#3B82F6', label: 'Open' },
  in_progress: { color: '#F59E0B', label: 'In Progress' },
  resolved:    { color: '#10B981', label: 'Resolved' },
  deferred:    { color: '#6B7280', label: 'Deferred' },
  converted:   { color: '#8B5CF6', label: 'Converted' },
};

const PRIORITIES = ['critical', 'high', 'medium', 'low'];
const PRI_COLORS: Record<string, string> = {
  critical: '#DC2626', high: '#F59E0B', medium: '#3B82F6', low: '#6B7280',
};

export default function PNAScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboard, setDashboard] = useState<any>(null);
  const [viewMode, setViewMode] = useState<'overview' | 'area'>('overview');
  const [selectedArea, setSelectedArea] = useState<string>('');
  const [areaDetail, setAreaDetail] = useState<any>(null);
  const [areaLoading, setAreaLoading] = useState(false);

  // Add/Edit modal
  const [showModal, setShowModal] = useState(false);
  const [editItem, setEditItem] = useState<any>(null);
  const [form, setForm] = useState({
    title: '', description: '', category: 'need', priority: 'medium',
    life_area: '', impact_score: 5, urgency_score: 5,
    action_plan: '', target_date: '',
    linked_goal_id: '' as string,
    linked_goal_title: '' as string,
  });
  const [saving, setSaving] = useState(false);
  const [gemGoals, setGemGoals] = useState<Array<{ goal_id: string; title: string; life_area?: string; project_status?: string; goal_type?: string }>>([]);
  const [showGemPicker, setShowGemPicker] = useState(false);
  const [creatingGoal, setCreatingGoal] = useState(false);
  // Bug 3: when ON, picker shows ALL the user's GEM goals (not only the current life area).
  const [showAllAreas, setShowAllAreas] = useState(false);
  // Bug 4 (Option A — defer-create): stash the would-be GEM payload locally and
  // create it only when the PNA item is saved, so cancelling produces no orphan.
  const [pendingGemGoal, setPendingGemGoal] = useState<null | {
    title: string; description: string; life_area: string; priority: string;
    goal_type: string; project_status: string; status: string;
  }>(null);
  // Bug 1: keep raw text while user is editing so they can type "8" without
  // the value clamping to 1 or 10 mid-keystroke. Clamp on blur and on save.
  const [impactRaw, setImpactRaw] = useState('5');
  const [urgencyRaw, setUrgencyRaw] = useState('5');
  const { width: winWidth } = useWindowDimensions();
  const isWide = winWidth >= 768;

  const fetchDashboard = async () => {
    try {
      const res = await api.get('/pna/dashboard');
      setDashboard(res.data);
    } catch (e) { console.error('PNA dashboard error:', e); }
    finally { setLoading(false); }
  };

  const fetchAreaDetail = async (areaId: string) => {
    setAreaLoading(true);
    try {
      const res = await api.get(`/pna/areas/${areaId}`);
      setAreaDetail(res.data);
    } catch (e) { console.error('Area detail error:', e); }
    finally { setAreaLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchDashboard(); }, []));

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchDashboard();
    if (viewMode === 'area' && selectedArea) await fetchAreaDetail(selectedArea);
    setRefreshing(false);
  };

  const openArea = (areaId: string) => {
    setSelectedArea(areaId);
    setViewMode('area');
    fetchAreaDetail(areaId);
  };

  const openAddModal = (category: string = 'need', areaId?: string) => {
    setEditItem(null);
    setForm({
      title: '', description: '', category,
      priority: 'medium', life_area: areaId || selectedArea || '',
      impact_score: 5, urgency_score: 5, action_plan: '', target_date: '',
      linked_goal_id: '', linked_goal_title: '',
    });
    setImpactRaw('5');
    setUrgencyRaw('5');
    setPendingGemGoal(null);
    setShowGemPicker(false);
    setShowAllAreas(false);
    setShowModal(true);
    fetchGemGoals(areaId || selectedArea || '');
  };

  const openEditModal = (item: any) => {
    setEditItem(item);
    setForm({
      title: item.title || '', description: item.description || '',
      category: item.category || 'need', priority: item.priority || 'medium',
      life_area: item.life_area || '', impact_score: item.impact_score || 5,
      urgency_score: item.urgency_score || 5,
      action_plan: item.action_plan || '', target_date: item.target_date || '',
      linked_goal_id: item.linked_goal_id || '',
      linked_goal_title: item.linked_goal_title || '',
    });
    setImpactRaw(String(item.impact_score || 5));
    setUrgencyRaw(String(item.urgency_score || 5));
    setPendingGemGoal(null);
    setShowGemPicker(false);
    setShowAllAreas(false);
    setShowModal(true);
    fetchGemGoals(item.life_area || '');
  };

  // Bug 3: when `showAllAreas` is true, drop the life_area filter so the picker
  // can never be "empty" when an existing GEM goal lives under a slightly
  // different life_area slug (legacy data).
  const fetchGemGoals = async (lifeArea: string) => {
    try {
      const params: any = {};
      if (lifeArea && !showAllAreas) params.life_area = lifeArea;
      const res = await api.get('/gem/goals', { params });
      setGemGoals(res.data || []);
    } catch (e) {
      setGemGoals([]);
    }
  };

  // Re-fetch whenever the "Show all areas" toggle changes (only while modal open)
  useEffect(() => {
    if (showModal) fetchGemGoals(form.life_area);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showAllAreas]);

  // Bug 4 (Option A): "Create in GEM" stashes the payload locally and shows a
  // queued badge. The actual POST happens inside handleSave so cancelling the
  // PNA modal produces no orphan GEM record.
  const handleCreateGemGoal = async () => {
    if (!form.title.trim()) {
      return showAlert('Title required', 'Add a title for the PNA item first — the same will seed the new GEM goal.');
    }
    if (!form.life_area) {
      return showAlert('Life area required', 'Pick a life area first.');
    }
    const payload = {
      title: form.title,
      description: form.description || `Auto-created from PNA item: ${form.title}`,
      life_area: form.life_area,
      priority: form.priority,
      goal_type: form.category, // problem | need | aspiration
      project_status: 'open',
      status: 'active',
    };
    setPendingGemGoal(payload);
    // Use a sentinel id so the linked-row UI renders; we'll swap it for the
    // real goal_id at save time.
    setForm(prev => ({ ...prev, linked_goal_id: '__pending__', linked_goal_title: form.title }));
    showAlert('GEM goal queued', `Will be created in GEM when you save this PNA item — no orphan if you cancel.`);
  };

  const openLinkedGoal = () => {
    if (!form.linked_goal_id) return;
    // Close PNA modal first so navigation isn't stacked on top of it
    setShowModal(false);
    setTimeout(() => {
      router.push(`/tools/gem-goal?id=${form.linked_goal_id}` as any);
    }, 80);
  };

  const unlinkGoal = () => {
    setForm(prev => ({ ...prev, linked_goal_id: '', linked_goal_title: '' }));
    setPendingGemGoal(null);
  };

  const pickGoal = (goal: { goal_id: string; title: string }) => {
    setForm(prev => ({ ...prev, linked_goal_id: goal.goal_id, linked_goal_title: goal.title }));
    setPendingGemGoal(null); // user picked an existing one — drop any queued stub
    setShowGemPicker(false);
  };

  const handleSave = async () => {
    if (!form.title.trim()) return showAlert('Error', 'Title is required');
    if (!form.life_area) return showAlert('Error', 'Life area is required');
    // Bug 1: final clamp from the raw text right before save.
    const clamp = (s: string) => {
      const n = parseInt(s, 10);
      return isNaN(n) ? 5 : Math.min(10, Math.max(1, n));
    };
    const impact = clamp(impactRaw);
    const urgency = clamp(urgencyRaw);
    setSaving(true);
    try {
      // Bug 4 (Option A): if user clicked "Create in GEM" earlier we have a
      // pending payload — POST it now (atomic with PNA save) and capture the
      // real goal_id. If this POST fails we abort BEFORE saving the PNA so the
      // user can retry without an orphan.
      let linked_goal_id = form.linked_goal_id;
      let linked_goal_title = form.linked_goal_title;
      if (pendingGemGoal) {
        try {
          const gres = await api.post('/gem/goals', pendingGemGoal);
          linked_goal_id = gres.data.goal_id;
          linked_goal_title = gres.data.title;
        } catch (ge: any) {
          setSaving(false);
          return showAlert('Could not create GEM goal',
            ge?.response?.data?.detail || 'Try again or unlink the goal first.');
        }
      }
      // Sentinel safety net — never persist '__pending__' to the DB.
      if (linked_goal_id === '__pending__') {
        linked_goal_id = '';
        linked_goal_title = '';
      }
      const payload = {
        ...form,
        impact_score: impact,
        urgency_score: urgency,
        linked_goal_id,
        linked_goal_title,
      };
      if (editItem) {
        await api.put(`/pna/items/${editItem.item_id}`, payload);
      } else {
        await api.post('/pna/items', payload);
      }
      setPendingGemGoal(null);
      setShowModal(false);
      fetchDashboard();
      if (viewMode === 'area' && selectedArea) fetchAreaDetail(selectedArea);
    } catch (e) { showAlert('Error', 'Failed to save'); }
    finally { setSaving(false); }
  };

  // Closing the modal (X / backdrop) — drop any queued GEM stub so it never
  // leaks into a future open.
  const closeModal = () => {
    setPendingGemGoal(null);
    setShowGemPicker(false);
    setShowModal(false);
  };

  const handleDelete = (itemId: string) => {
    showAlert('Delete', 'Delete this PNA item?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try {
          await api.delete(`/pna/items/${itemId}`);
          fetchDashboard();
          if (viewMode === 'area' && selectedArea) fetchAreaDetail(selectedArea);
        } catch (e) { showAlert('Error', 'Failed to delete'); }
      }},
    ]);
  };

  const handleStatusChange = async (itemId: string, newStatus: string) => {
    try {
      await api.put(`/pna/items/${itemId}`, { status: newStatus });
      fetchDashboard();
      if (viewMode === 'area' && selectedArea) fetchAreaDetail(selectedArea);
    } catch (e) { showAlert('Error', 'Failed to update status'); }
  };

  const handleConvert = (itemId: string, to: 'decision' | 'goal') => {
    const label = to === 'decision' ? 'Decision (My Dezider)' : 'Goal (GEM)';
    showAlert('Convert', `Convert this item to a ${label}?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Convert', onPress: async () => {
        try {
          await api.post(`/pna/items/${itemId}/convert-to-${to}`, {});
          showAlert('Success', `Converted to ${label}`);
          fetchDashboard();
          if (viewMode === 'area' && selectedArea) fetchAreaDetail(selectedArea);
        } catch (e) { showAlert('Error', 'Failed to convert'); }
      }},
    ]);
  };

  // ─── RENDER ────────────────────────────────────────────

  const renderOverview = () => {
    if (!dashboard) return null;
    const { by_category, total, open_critical, area_summaries, recent } = dashboard;

    return (
      <>
        {/* Summary Cards */}
        <View style={s.summaryRow}>
          <View style={[s.summaryCard, { borderLeftColor: '#EF4444' }]}>
            <Ionicons name="alert-circle" size={20} color="#EF4444" />
            <Text style={s.summaryNum}>{by_category?.problem || 0}</Text>
            <Text style={s.summaryLabel}>Problems</Text>
          </View>
          <View style={[s.summaryCard, { borderLeftColor: '#F59E0B' }]}>
            <Ionicons name="bulb" size={20} color="#F59E0B" />
            <Text style={s.summaryNum}>{by_category?.need || 0}</Text>
            <Text style={s.summaryLabel}>Needs</Text>
          </View>
          <View style={[s.summaryCard, { borderLeftColor: '#10B981' }]}>
            <Ionicons name="rocket" size={20} color="#10B981" />
            <Text style={s.summaryNum}>{by_category?.aspiration || 0}</Text>
            <Text style={s.summaryLabel}>Aspirations</Text>
          </View>
        </View>

        {open_critical > 0 && (
          <View style={s.alertBanner}>
            <Ionicons name="warning" size={18} color="#FFF" />
            <Text style={s.alertText}>{open_critical} critical/high priority open items</Text>
          </View>
        )}

        {/* Life Areas Grid */}
        <Text style={s.sectionTitle}>Life Areas ({total} items)</Text>
        {(area_summaries || []).map((area: any) => (
          <TouchableOpacity
            key={area.area_id}
            style={s.areaRow}
            onPress={() => openArea(area.area_id)}
            activeOpacity={0.7}
          >
            <View style={[s.areaIconWrap, { backgroundColor: area.color + '20' }]}>
              <Ionicons name={area.icon as any} size={22} color={area.color} />
            </View>
            <View style={{ flex: 1, marginLeft: 12 }}>
              <Text style={s.areaName}>{area.area_name}</Text>
              <View style={s.areaCountsRow}>
                {area.problem > 0 && (
                  <View style={[s.countBadge, { backgroundColor: '#FEE2E2' }]}>
                    <Text style={[s.countText, { color: '#DC2626' }]}>P:{area.problem}</Text>
                  </View>
                )}
                {area.need > 0 && (
                  <View style={[s.countBadge, { backgroundColor: '#FEF3C7' }]}>
                    <Text style={[s.countText, { color: '#D97706' }]}>N:{area.need}</Text>
                  </View>
                )}
                {area.aspiration > 0 && (
                  <View style={[s.countBadge, { backgroundColor: '#D1FAE5' }]}>
                    <Text style={[s.countText, { color: '#059669' }]}>A:{area.aspiration}</Text>
                  </View>
                )}
                {area.total === 0 && <Text style={s.emptyText}>No items yet</Text>}
              </View>
            </View>
            <Text style={s.areaTotal}>{area.total}</Text>
            <Ionicons name="chevron-forward" size={18} color="#9CA3AF" />
          </TouchableOpacity>
        ))}

        {/* Recent Items */}
        {(recent || []).length > 0 && (
          <>
            <Text style={s.sectionTitle}>Recent Activity</Text>
            {recent.map((item: any) => renderItemCard(item))}
          </>
        )}
      </>
    );
  };

  const renderAreaView = () => {
    if (areaLoading) return <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />;
    if (!areaDetail) return null;
    const { area, problems, needs, aspirations, open_count, resolved_count } = areaDetail;

    return (
      <>
        {/* Area Header */}
        <View style={[s.areaHeader, { backgroundColor: area.color + '15' }]}>
          <View style={s.areaHeaderRow}>
            <Ionicons name={area.icon as any} size={28} color={area.color} />
            <View style={{ marginLeft: 12, flex: 1 }}>
              <Text style={s.areaHeaderTitle}>{area.name}</Text>
              <Text style={s.areaHeaderSub}>{open_count} open · {resolved_count} resolved</Text>
            </View>
          </View>
          <View style={s.addBtnRow}>
            {(['problem', 'need', 'aspiration'] as const).map((cat) => (
              <TouchableOpacity
                key={cat}
                style={[s.addCatBtn, { backgroundColor: CAT_CFG[cat].color }]}
                onPress={() => openAddModal(cat, area.id)}
              >
                <Ionicons name="add" size={16} color="#FFF" />
                <Text style={s.addCatText}>+ {CAT_CFG[cat].label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Problems */}
        {problems.length > 0 && (
          <>
            <Text style={[s.catSectionTitle, { color: '#EF4444' }]}>Problems ({problems.length})</Text>
            {problems.map((item: any) => renderItemCard(item))}
          </>
        )}

        {/* Needs */}
        {needs.length > 0 && (
          <>
            <Text style={[s.catSectionTitle, { color: '#F59E0B' }]}>Needs ({needs.length})</Text>
            {needs.map((item: any) => renderItemCard(item))}
          </>
        )}

        {/* Aspirations */}
        {aspirations.length > 0 && (
          <>
            <Text style={[s.catSectionTitle, { color: '#10B981' }]}>Aspirations ({aspirations.length})</Text>
            {aspirations.map((item: any) => renderItemCard(item))}
          </>
        )}

        {problems.length === 0 && needs.length === 0 && aspirations.length === 0 && (
          <View style={s.emptyState}>
            <Ionicons name="layers-outline" size={48} color="#9CA3AF" />
            <Text style={s.emptyStateText}>No items in this area yet</Text>
            <Text style={s.emptyStateSub}>Add your Problems, Needs, or Aspirations</Text>
          </View>
        )}
      </>
    );
  };

  const renderItemCard = (item: any) => {
    const cat = CAT_CFG[item.category] || CAT_CFG.need;
    const st = STATUS_CFG[item.status] || STATUS_CFG.open;
    const priColor = PRI_COLORS[item.priority] || '#6B7280';

    return (
      <View key={item.item_id} style={s.itemCard}>
        <View style={s.itemHeader}>
          <View style={[s.catDot, { backgroundColor: cat.color }]} />
          <Text style={s.itemTitle} numberOfLines={2}>{item.title}</Text>
        </View>
        <TimestampLine entity={item} compact />
        {item.description ? (
          <Text style={s.itemDesc} numberOfLines={2}>{item.description}</Text>
        ) : null}
        <View style={s.itemMetaRow}>
          <View style={[s.statusBadge, { backgroundColor: st.color + '20' }]}>
            <Text style={[s.statusText, { color: st.color }]}>{st.label}</Text>
          </View>
          <View style={[s.priBadge, { backgroundColor: priColor + '20' }]}>
            <Text style={[s.priText, { color: priColor }]}>{item.priority}</Text>
          </View>
          {item.impact_score > 7 && (
            <View style={[s.scoreBadge, { backgroundColor: '#FEE2E2' }]}>
              <Text style={[s.scoreText, { color: '#DC2626' }]}>Impact: {item.impact_score}</Text>
            </View>
          )}
        </View>
        <View style={s.itemActions}>
          {item.status === 'open' && (
            <TouchableOpacity style={s.actBtn} onPress={() => handleStatusChange(item.item_id, 'in_progress')}>
              <Ionicons name="play" size={14} color="#3B82F6" />
              <Text style={[s.actText, { color: '#3B82F6' }]}>Start</Text>
            </TouchableOpacity>
          )}
          {item.status === 'in_progress' && (
            <TouchableOpacity style={s.actBtn} onPress={() => handleStatusChange(item.item_id, 'resolved')}>
              <Ionicons name="checkmark-circle" size={14} color="#10B981" />
              <Text style={[s.actText, { color: '#10B981' }]}>Resolve</Text>
            </TouchableOpacity>
          )}
          {item.status !== 'converted' && (
            <>
              <TouchableOpacity style={s.actBtn} onPress={() => handleConvert(item.item_id, 'decision')}>
                <Ionicons name="git-branch" size={14} color="#8B5CF6" />
                <Text style={[s.actText, { color: '#8B5CF6' }]}>Decision</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.actBtn} onPress={() => handleConvert(item.item_id, 'goal')}>
                <Ionicons name="flag" size={14} color="#059669" />
                <Text style={[s.actText, { color: '#059669' }]}>Goal</Text>
              </TouchableOpacity>
            </>
          )}
          <TouchableOpacity style={s.actBtn} onPress={() => openEditModal(item)}>
            <Ionicons name="pencil" size={14} color="#6B7280" />
          </TouchableOpacity>
          <TouchableOpacity style={s.actBtn} onPress={() => handleDelete(item.item_id)}>
            <Ionicons name="trash" size={14} color="#EF4444" />
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const renderFormModal = () => (
    <Modal visible={showModal} animationType={isWide ? 'fade' : 'slide'} transparent>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={isWide ? s.modalOverlayWide : s.modalOverlay}
      >
        <View style={isWide ? s.modalContentWide : s.modalContent}>
          <View style={s.modalHeader}>
            <Text style={s.modalTitle}>{editItem ? 'Edit Item' : 'New PNA Item'}</Text>
            <TouchableOpacity onPress={closeModal}>
              <Ionicons name="close" size={24} color="#6B7280" />
            </TouchableOpacity>
          </View>

          <ScrollView style={{ maxHeight: 500 }} showsVerticalScrollIndicator={false}>
            {/* Category Selector */}
            <Text style={s.fieldLabel}>Category</Text>
            <View style={s.catSelector}>
              {(['problem', 'need', 'aspiration'] as const).map((cat) => (
                <TouchableOpacity
                  key={cat}
                  style={[
                    s.catOption,
                    form.category === cat && { backgroundColor: CAT_CFG[cat].color, borderColor: CAT_CFG[cat].color },
                  ]}
                  onPress={() => setForm({ ...form, category: cat })}
                >
                  <Ionicons name={CAT_CFG[cat].icon as any} size={16}
                    color={form.category === cat ? '#FFF' : CAT_CFG[cat].color} />
                  <Text style={[s.catOptText, form.category === cat && { color: '#FFF' }]}>
                    {CAT_CFG[cat].label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Life Area Selector (if not in area view) */}
            {!form.life_area && (
              <>
                <Text style={s.fieldLabel}>Life Area *</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 12 }}>
                  {dashboard?.area_summaries?.map((a: any) => (
                    <TouchableOpacity
                      key={a.area_id}
                      style={[s.areaChip, form.life_area === a.area_id && { backgroundColor: a.color, borderColor: a.color }]}
                      onPress={() => setForm({ ...form, life_area: a.area_id })}
                    >
                      <Text style={[s.areaChipText, form.life_area === a.area_id && { color: '#FFF' }]}>
                        {a.area_name}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </>
            )}

            <Text style={s.fieldLabel}>Title *</Text>
            <TextInput
              style={s.input} placeholder="What's the problem, need, or aspiration?"
              value={form.title} onChangeText={(t) => setForm({ ...form, title: t })}
              placeholderTextColor="#9CA3AF"
            />

            <Text style={s.fieldLabel}>Description</Text>
            <TextInput
              style={[s.input, { height: 80, textAlignVertical: 'top' }]}
              multiline placeholder="Details..."
              value={form.description} onChangeText={(t) => setForm({ ...form, description: t })}
              placeholderTextColor="#9CA3AF"
            />

            {/* Priority */}
            <Text style={s.fieldLabel}>Priority</Text>
            <View style={s.priRow}>
              {PRIORITIES.map((p) => (
                <TouchableOpacity
                  key={p}
                  style={[s.priOption, form.priority === p && { backgroundColor: PRI_COLORS[p], borderColor: PRI_COLORS[p] }]}
                  onPress={() => setForm({ ...form, priority: p })}
                >
                  <Text style={[s.priOptText, form.priority === p && { color: '#FFF' }]}>
                    {p.charAt(0).toUpperCase() + p.slice(1)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Impact & Urgency */}
            <View style={s.scoreRow}>
              <View style={{ flex: 1, marginRight: 8 }}>
                <Text style={s.fieldLabel}>Impact (1-10)</Text>
                <TextInput
                  style={s.input}
                  keyboardType="numeric"
                  value={impactRaw}
                  onChangeText={(t) => setImpactRaw(t.replace(/[^0-9]/g, '').slice(0, 2))}
                  onBlur={() => {
                    const n = parseInt(impactRaw, 10);
                    const clamped = isNaN(n) ? 5 : Math.min(10, Math.max(1, n));
                    setImpactRaw(String(clamped));
                    setForm({ ...form, impact_score: clamped });
                  }}
                  placeholderTextColor="#9CA3AF"
                  placeholder="1-10"
                />
              </View>
              <View style={{ flex: 1, marginLeft: 8 }}>
                <Text style={s.fieldLabel}>Urgency (1-10)</Text>
                <TextInput
                  style={s.input}
                  keyboardType="numeric"
                  value={urgencyRaw}
                  onChangeText={(t) => setUrgencyRaw(t.replace(/[^0-9]/g, '').slice(0, 2))}
                  onBlur={() => {
                    const n = parseInt(urgencyRaw, 10);
                    const clamped = isNaN(n) ? 5 : Math.min(10, Math.max(1, n));
                    setUrgencyRaw(String(clamped));
                    setForm({ ...form, urgency_score: clamped });
                  }}
                  placeholderTextColor="#9CA3AF"
                  placeholder="1-10"
                />
              </View>
            </View>

            <Text style={s.fieldLabel}>Linked GEM Goal</Text>
            {form.linked_goal_id && (
              <View style={s.gemLinkedRow}>
                <Ionicons name="flag" size={16} color={pendingGemGoal ? '#F59E0B' : '#7C3AED'} />
                <Text style={s.gemLinkedText} numberOfLines={2}>
                  {form.linked_goal_title || `Goal ${form.linked_goal_id.slice(0, 8)}`}
                  {pendingGemGoal ? '  ·  queued' : ''}
                </Text>
                {!pendingGemGoal && (
                  <TouchableOpacity onPress={openLinkedGoal} hitSlop={6}>
                    <Ionicons name="open-outline" size={16} color="#7C3AED" />
                  </TouchableOpacity>
                )}
                <TouchableOpacity onPress={unlinkGoal} hitSlop={6}>
                  <Ionicons name="close-circle" size={16} color="#94A3B8" />
                </TouchableOpacity>
              </View>
            )}
            {/* Backlog fix: keep the "Browse GEM" CTA visible even when a stub
                is queued, so the user can swap to an existing goal in ONE click
                (pickGoal() discards the queued stub — no orphan). The "Create
                in GEM" button is hidden when a stub is already queued. */}
            {(!form.linked_goal_id || pendingGemGoal) && (
              <View style={s.gemActions}>
                <TouchableOpacity style={s.gemBtnGhost} onPress={() => setShowGemPicker(v => !v)}>
                  <Ionicons name="link" size={14} color="#7C3AED" />
                  <Text style={s.gemBtnGhostText}>
                    {showGemPicker
                      ? 'Hide list'
                      : pendingGemGoal
                        ? `Pick existing instead (${gemGoals.length})`
                        : `Browse GEM (${gemGoals.length} available)`}
                  </Text>
                </TouchableOpacity>
                {!pendingGemGoal && (
                  <TouchableOpacity
                    style={[s.gemBtnPrimary, creatingGoal && { opacity: 0.6 }]}
                    onPress={handleCreateGemGoal}
                    disabled={creatingGoal}
                  >
                    {creatingGoal
                      ? <ActivityIndicator size="small" color="#FFF" />
                      : <><Ionicons name="add-circle" size={14} color="#FFF" /><Text style={s.gemBtnPrimaryText}>Create in GEM</Text></>}
                  </TouchableOpacity>
                )}
              </View>
            )}
            {showGemPicker && (!form.linked_goal_id || pendingGemGoal) && (
              <View style={s.gemPicker}>
                {/* Bug 3: small header + "Show all areas" toggle so the user can
                    always find an existing GEM goal even when life_area slugs
                    are mismatched in older data. */}
                <View style={s.gemPickerHeader}>
                  <Text style={s.gemPickerHeaderText} numberOfLines={1}>
                    {showAllAreas ? 'All life areas' : `Filter: ${form.life_area || '(none)'}`}
                  </Text>
                  <TouchableOpacity onPress={() => setShowAllAreas(v => !v)} hitSlop={6}>
                    <Text style={s.gemPickerToggle}>
                      {showAllAreas ? 'Filter to current area' : 'Show all areas'}
                    </Text>
                  </TouchableOpacity>
                </View>
                {gemGoals.length === 0 ? (
                  <Text style={s.gemEmpty}>
                    {showAllAreas
                      ? 'You have no GEM goals yet. Tap "Create in GEM" to start one.'
                      : 'No GEM goals in this life area. Tap "Show all areas" above or "Create in GEM".'}
                  </Text>
                ) : (
                  gemGoals.slice(0, 20).map(g => (
                    <TouchableOpacity key={g.goal_id} style={s.gemPickItem} onPress={() => pickGoal(g)}>
                      <Ionicons name="flag-outline" size={14} color="#7C3AED" />
                      <View style={{ flex: 1 }}>
                        <Text style={s.gemPickText} numberOfLines={1}>{g.title}</Text>
                        {(g.life_area || g.goal_type) ? (
                          <Text style={s.gemPickMeta} numberOfLines={1}>
                            {[g.life_area, g.goal_type].filter(Boolean).join(' · ')}
                          </Text>
                        ) : null}
                      </View>
                      {g.project_status ? <Text style={s.gemPickStatus}>{g.project_status}</Text> : null}
                    </TouchableOpacity>
                  ))
                )}
              </View>
            )}
            <Text style={s.gemHint}>
              {pendingGemGoal
                ? `New GEM goal is queued — it will be created when you tap ${editItem ? 'Update' : 'Save'} (no orphan if you cancel).`
                : `Goal Execution Manager tracks the work needed to address this ${CAT_CFG[form.category]?.label?.toLowerCase() || 'item'}.`}
            </Text>
          </ScrollView>

          <TouchableOpacity
            style={[s.saveBtn, saving && { opacity: 0.6 }]}
            onPress={handleSave} disabled={saving}
          >
            {saving ? <ActivityIndicator color="#FFF" /> : (
              <Text style={s.saveBtnText}>{editItem ? 'Update' : 'Save'}</Text>
            )}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );

  if (loading) {
    return (
      <SafeAreaView style={s.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container}>
      <ScrollView
        contentContainerStyle={{ padding: 16, paddingBottom: 120 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Header */}
        <View style={s.header}>
          <TouchableOpacity onPress={() => {
            if (viewMode === 'area') { setViewMode('overview'); } else { router.back(); }
          }}>
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <Text style={s.headerTitle}>
            {viewMode === 'area' ? (areaDetail?.area?.name || 'Area') : 'PNA Framework'}
          </Text>
          <TouchableOpacity onPress={() => openAddModal()}>
            <Ionicons name="add-circle" size={28} color="#FFF" />
          </TouchableOpacity>
        </View>

        <LinearGradient colors={['#FFFFFF', '#F8FAFC']} style={s.heroBanner}>
          <Ionicons name="layers" size={32} color="#818CF8" />
          <View style={{ marginLeft: 12, flex: 1 }}>
            <Text style={s.heroTitle}>Problems · Needs · Aspirations</Text>
            <Text style={s.heroSub}>Map your life across 10 areas. Track, resolve, and convert to actions.</Text>
          </View>
        </LinearGradient>

        {viewMode === 'overview' ? renderOverview() : renderAreaView()}
      </ScrollView>

      {renderFormModal()}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  headerTitle: { color: '#0F172A', fontSize: 18, fontWeight: '700', flex: 1, marginLeft: 12 },
  heroBanner: { borderRadius: 16, padding: 16, flexDirection: 'row', alignItems: 'center', marginBottom: 20 },
  heroTitle: { color: '#0F172A', fontSize: 16, fontWeight: '700' },
  heroSub: { color: '#94A3B8', fontSize: 12, marginTop: 4 },

  // Summary
  summaryRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  summaryCard: { flex: 1, backgroundColor: '#FFFFFF', borderRadius: 12, padding: 12, alignItems: 'center', borderLeftWidth: 3 },
  summaryNum: { color: '#0F172A', fontSize: 22, fontWeight: '700', marginTop: 4 },
  summaryLabel: { color: '#94A3B8', fontSize: 11, marginTop: 2 },

  alertBanner: { backgroundColor: '#DC2626', borderRadius: 10, padding: 10, flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 16 },
  alertText: { color: '#0F172A', fontSize: 13, fontWeight: '600' },

  // Section
  sectionTitle: { color: '#0F172A', fontSize: 16, fontWeight: '700', marginBottom: 12, marginTop: 8 },

  // Area rows
  areaRow: { backgroundColor: '#FFFFFF', borderRadius: 12, padding: 14, flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  areaIconWrap: { width: 42, height: 42, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  areaName: { color: '#0F172A', fontSize: 14, fontWeight: '600' },
  areaCountsRow: { flexDirection: 'row', gap: 6, marginTop: 4, flexWrap: 'wrap' },
  countBadge: { borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  countText: { fontSize: 11, fontWeight: '600' },
  areaTotal: { color: '#94A3B8', fontSize: 16, fontWeight: '700', marginRight: 8 },
  emptyText: { color: '#6B7280', fontSize: 11, fontStyle: 'italic' },

  // Area header
  areaHeader: { borderRadius: 16, padding: 16, marginBottom: 16 },
  areaHeaderRow: { flexDirection: 'row', alignItems: 'center' },
  areaHeaderTitle: { color: '#0F172A', fontSize: 18, fontWeight: '700' },
  areaHeaderSub: { color: '#94A3B8', fontSize: 12, marginTop: 2 },
  addBtnRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  addCatBtn: { flexDirection: 'row', alignItems: 'center', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, gap: 4 },
  addCatText: { color: '#0F172A', fontSize: 12, fontWeight: '600' },

  catSectionTitle: { fontSize: 15, fontWeight: '700', marginTop: 12, marginBottom: 8 },

  // Item Card
  itemCard: { backgroundColor: '#FFFFFF', borderRadius: 12, padding: 14, marginBottom: 8 },
  itemHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  catDot: { width: 10, height: 10, borderRadius: 5, marginTop: 4 },
  itemTitle: { color: '#0F172A', fontSize: 14, fontWeight: '600', flex: 1 },
  itemDesc: { color: '#94A3B8', fontSize: 12, marginTop: 6, marginLeft: 18 },
  itemMetaRow: { flexDirection: 'row', gap: 6, marginTop: 8, marginLeft: 18, flexWrap: 'wrap' },
  statusBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  statusText: { fontSize: 11, fontWeight: '600' },
  priBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  priText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  scoreBadge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  scoreText: { fontSize: 11, fontWeight: '600' },
  itemActions: { flexDirection: 'row', gap: 10, marginTop: 10, marginLeft: 18, flexWrap: 'wrap' },
  actBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 4, paddingHorizontal: 6, borderRadius: 6, backgroundColor: '#F8FAFC' },
  actText: { fontSize: 11, fontWeight: '600' },

  // Empty state
  emptyState: { alignItems: 'center', paddingVertical: 40 },
  emptyStateText: { color: '#9CA3AF', fontSize: 16, fontWeight: '600', marginTop: 12 },
  emptyStateSub: { color: '#6B7280', fontSize: 13, marginTop: 4 },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', justifyContent: 'flex-end' },
  modalOverlayWide: { flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  modalContent: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '85%' },
  modalContentWide: { backgroundColor: '#FFFFFF', borderRadius: 18, padding: 24, maxWidth: 560, width: '100%', maxHeight: '88%', shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 24, shadowOffset: { width: 0, height: 8 }, elevation: 8 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { color: '#0F172A', fontSize: 18, fontWeight: '700' },
  fieldLabel: { color: '#475569', fontSize: 12, fontWeight: '700', marginBottom: 6, marginTop: 8, textTransform: 'uppercase', letterSpacing: 0.4 },
  input: { backgroundColor: '#F8FAFC', borderRadius: 10, borderWidth: 1, borderColor: '#E5E7EB', color: '#0F172A', paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, marginBottom: 4 },

  // GEM Goal linker (replaces Action Plan)
  gemLinkedRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F5F3FF', borderColor: '#DDD6FE', borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, marginBottom: 4 },
  gemLinkedText: { flex: 1, color: '#5B21B6', fontSize: 13, fontWeight: '600' },
  gemActions: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  gemBtnGhost: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1, borderColor: '#DDD6FE', backgroundColor: '#F5F3FF', borderRadius: 10, paddingVertical: 10 },
  gemBtnGhostText: { color: '#7C3AED', fontSize: 13, fontWeight: '700' },
  gemBtnPrimary: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#7C3AED', borderRadius: 10, paddingVertical: 10 },
  gemBtnPrimaryText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  gemPicker: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 8, marginTop: 6, gap: 4, maxHeight: 240 },
  gemPickerHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 6, paddingVertical: 4, marginBottom: 2 },
  gemPickerHeaderText: { flex: 1, fontSize: 10, fontWeight: '700', color: '#64748B', textTransform: 'uppercase', letterSpacing: 0.5 },
  gemPickerToggle: { fontSize: 11, color: '#7C3AED', fontWeight: '700' },
  gemPickItem: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 8, backgroundColor: '#FFF' },
  gemPickText: { color: '#0F172A', fontSize: 13 },
  gemPickMeta: { color: '#64748B', fontSize: 10, marginTop: 1, textTransform: 'capitalize' },
  gemPickStatus: { fontSize: 10, color: '#7C3AED', fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  gemEmpty: { color: '#94A3B8', fontSize: 12, padding: 8, fontStyle: 'italic' },
  gemHint: { color: '#94A3B8', fontSize: 11, marginTop: 6, lineHeight: 16 },

  catSelector: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  catOption: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderRadius: 10, borderWidth: 1.5, borderColor: '#E5E7EB', paddingVertical: 8 },
  catOptText: { fontSize: 12, fontWeight: '600', color: '#475569' },

  priRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  priOption: { flex: 1, borderRadius: 8, borderWidth: 1.5, borderColor: '#E5E7EB', paddingVertical: 6, alignItems: 'center' },
  priOptText: { fontSize: 12, fontWeight: '600', color: '#475569' },

  areaChip: { borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB', paddingHorizontal: 12, paddingVertical: 6, marginRight: 8 },
  areaChipText: { color: '#475569', fontSize: 12, fontWeight: '500' },

  scoreRow: { flexDirection: 'row' },

  saveBtn: { backgroundColor: '#7C3AED', borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 16 },
  saveBtnText: { color: '#FFFFFF', fontSize: 16, fontWeight: '700' },
});
