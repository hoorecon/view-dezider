import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import { getLifeAreaShort, getLifeAreaIcon } from '../../src/constants/lifeAreas';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, Alert, ActivityIndicator, Linking, Dimensions,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../../src/constants/colors';

import api from '../../src/utils/api';
import TimestampLine from '../../src/components/TimestampLine';
import { safeBack } from '../../src/utils/navigation';

const { width: SCREEN_W } = Dimensions.get('window');

const STATUS_COLORS: Record<string, string> = {
  open: '#6B7280', in_progress: '#3B82F6', done: '#10B981',
  blocked: '#EF4444', cancelled: '#9CA3AF',
};
const STATUS_ICONS: Record<string, string> = {
  open: 'radio-button-off', in_progress: 'time', done: 'checkmark-circle',
  blocked: 'close-circle', cancelled: 'ban',
};
const PRIORITY_COLORS: Record<string, string> = {
  critical: '#EF4444', high: '#F59E0B', medium: '#3B82F6', low: '#6B7280',
};
const SOURCE_LABELS: Record<string, string> = {
  manual: 'Manual', decision: 'My Dezider', solution_finder: 'Solution Finder',
  solution_matrix: 'Solution Matrix', gem: 'GEM Goal',
};
const SOURCE_ICONS: Record<string, string> = {
  manual: 'create', decision: 'analytics', solution_finder: 'search',
  solution_matrix: 'grid', gem: 'flag',
};
// inline life-area maps replaced — use getLifeAreaShort()/getLifeAreaIcon() from src/constants/lifeAreas
// inline life-area maps replaced — use getLifeAreaShort()/getLifeAreaIcon() from src/constants/lifeAreas

const STATUS_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'open', label: 'Open' },
  { key: 'in_progress', label: 'Active' },
  { key: 'done', label: 'Done' },
  { key: 'blocked', label: 'Blocked' },
];

type ViewMode = 'list' | 'board' | 'calendar';

// Get dates for the week view
function getWeekDates(): string[] {
  const dates: string[] = [];
  const today = new Date();
  for (let i = -1; i < 6; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    dates.push(d.toISOString().split('T')[0]);
  }
  return dates;
}

function formatShortDate(dateStr: string): { day: string; weekday: string; isToday: boolean } {
  const d = new Date(dateStr);
  const today = new Date();
  const isToday = d.toISOString().split('T')[0] === today.toISOString().split('T')[0];
  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  return {
    day: d.getDate().toString(),
    weekday: weekdays[d.getDay()],
    isToday,
  };
}

export default function CTTScreen() {
  const router = useRouter();
  const [tasks, setTasks] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [isRoutine, setIsRoutine] = useState<boolean | null>(null);
  const [lifeAreaFilter, setLifeAreaFilter] = useState('');
  const [decisionTypeFilter, setDecisionTypeFilter] = useState('');
  const [aggregating, setAggregating] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const weekDates = getWeekDates();

  const fetchData = async () => {
    try {
      const params = new URLSearchParams();
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (isRoutine === true) params.append('is_routine', 'true');
      if (isRoutine === false) params.append('is_routine', 'false');
      if (lifeAreaFilter) params.append('life_area', lifeAreaFilter);
      if (decisionTypeFilter) params.append('decision_type', decisionTypeFilter);

      const [tasksRes, statsRes] = await Promise.all([
        api.get(`/ctt/tasks?${params}`),
        api.get('/ctt/stats'),
      ]);
      setTasks(tasksRes.data || []);
      setStats(statsRes.data);
    } catch (e) { console.error('CTT fetch error:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => {
    setLoading(true);
    fetchData();
  }, [statusFilter, isRoutine, lifeAreaFilter, decisionTypeFilter]));

  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const handleAggregate = async () => {
    setAggregating(true);
    try {
      const res = await api.post('/ctt/aggregate');
      const count = res.data?.imported || 0;
      showAlert(
        'Import Complete',
        count > 0
          ? `${count} new action items imported from your Decisions, Solution Finders & Matrices`
          : 'No new items to import. All action items are already tracked.',
      );
      if (count > 0) await fetchData();
    } catch (e) { showAlert('Error', 'Failed to aggregate tasks'); }
    finally { setAggregating(false); }
  };

  const handleDelete = (id: string, taskName: string) => {
    showAlert('Delete Task', `Are you sure you want to delete "${taskName}"?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/ctt/tasks/${id}`); fetchData(); }
        catch (e) { showAlert('Error', 'Failed to delete task'); }
      }},
    ]);
  };

  const quickStatus = async (id: string, status: string) => {
    try {
      await api.put(`/ctt/tasks/${id}`, { current_status: status });
      fetchData();
    } catch (e) { showAlert('Error', 'Failed to update status'); }
  };

  const updateDayStatus = async (taskId: string, date: string, currentDayStatus: Record<string, string>) => {
    const statuses = ['', 'done', 'in_progress', 'blocked', 'cancelled'];
    const current = currentDayStatus[date] || '';
    const nextIdx = (statuses.indexOf(current) + 1) % statuses.length;
    const nextStatus = statuses[nextIdx];

    try {
      const newDayStatus = { ...currentDayStatus };
      if (nextStatus) {
        newDayStatus[date] = nextStatus;
      } else {
        delete newDayStatus[date];
      }
      await api.put(`/ctt/tasks/${taskId}/day-status`, nextStatus ? { [date]: nextStatus } : { [date]: '' });
      fetchData();
    } catch (e) { showAlert('Error', 'Failed to update day status'); }
  };

  const openCalendar = async (taskId: string) => {
    try {
      const res = await api.get(`/ctt/tasks/${taskId}/calendar-url`);
      if (res.data?.calendar_url) {
        Linking.openURL(res.data.calendar_url);
      }
    } catch (e) { showAlert('Error', 'Could not open calendar'); }
  };

  const getSourceColor = (source: string) => {
    const colors: Record<string, string> = {
      manual: '#6B7280', decision: '#8E24AA', solution_finder: '#00BCD4',
      solution_matrix: '#E91E63', gem: '#F59E0B',
    };
    return colors[source] || '#6B7280';
  };

  // Group tasks by life area for board view
  const groupedByArea = tasks.reduce((acc: Record<string, any[]>, t: any) => {
    const area = t.life_area || 'unassigned';
    if (!acc[area]) acc[area] = [];
    acc[area].push(t);
    return acc;
  }, {});

  const renderStats = () => {
    if (!stats) return null;
    const items = [
      { label: 'Total', value: stats.total || 0, color: COLORS.primary, icon: 'layers' },
      { label: 'Open', value: stats.by_status?.open || 0, color: '#6B7280', icon: 'radio-button-off' },
      { label: 'Active', value: stats.by_status?.in_progress || 0, color: '#3B82F6', icon: 'time' },
      { label: 'Done', value: stats.by_status?.done || 0, color: '#10B981', icon: 'checkmark-circle' },
      { label: 'Blocked', value: stats.by_status?.blocked || 0, color: '#EF4444', icon: 'close-circle' },
    ];
    return (
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.statsScroll}>
        <View style={s.statsRow}>
          {items.map(st => (
            <View key={st.label} style={[s.statCard, { borderLeftColor: st.color, borderLeftWidth: 3 }]}>
              <Ionicons name={st.icon as any} size={18} color={st.color} />
              <Text style={[s.statNum, { color: st.color }]}>{st.value}</Text>
              <Text style={s.statLabel}>{st.label}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
    );
  };

  const renderFilters = () => (
    <View style={s.filtersContainer}>
      {/* Status filters */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={s.filterRow}>
          {STATUS_FILTERS.map(f => (
            <TouchableOpacity
              key={f.key}
              style={[s.filterChip, statusFilter === f.key && s.filterActive]}
              onPress={() => setStatusFilter(f.key)}
            >
              {f.key !== 'all' && (
                <View style={[s.filterDot, { backgroundColor: STATUS_COLORS[f.key] }]} />
              )}
              <Text style={[s.filterText, statusFilter === f.key && s.filterTextActive]}>
                {f.label}
              </Text>
            </TouchableOpacity>
          ))}

          {/* Routine toggle */}
          <View style={s.filterDivider} />
          {[
            { key: null, label: 'All Types', icon: 'apps' },
            { key: false, label: 'One-time', icon: 'flash' },
            { key: true, label: 'Routine', icon: 'repeat' },
          ].map(item => (
            <TouchableOpacity
              key={String(item.key)}
              style={[s.filterChip, isRoutine === item.key && s.filterActive]}
              onPress={() => setIsRoutine(item.key as boolean | null)}
            >
              <Ionicons
                name={item.icon as any}
                size={12}
                color={isRoutine === item.key ? '#FFF' : COLORS.textMuted}
              />
              <Text style={[s.filterText, isRoutine === item.key && s.filterTextActive]}>
                {item.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {/* Life Area filter */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
        <View style={s.filterRow}>
          <TouchableOpacity
            style={[s.filterChip, !lifeAreaFilter && s.filterActiveSecondary]}
            onPress={() => setLifeAreaFilter('')}
          >
            <Text style={[s.filterText, !lifeAreaFilter && { color: COLORS.primary }]}>All Areas</Text>
          </TouchableOpacity>
          {Object.entries(LIFE_AREA_LABELS).map(([key, label]) => (
            <TouchableOpacity
              key={key}
              style={[s.filterChip, lifeAreaFilter === key && s.filterActiveSecondary]}
              onPress={() => setLifeAreaFilter(lifeAreaFilter === key ? '' : key)}
            >
              <Ionicons
                name={(getLifeAreaIcon(key) || 'ellipse') as any}
                size={12}
                color={lifeAreaFilter === key ? COLORS.primary : COLORS.textMuted}
              />
              <Text style={[s.filterText, lifeAreaFilter === key && { color: COLORS.primary }]}>
                {label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>
    </View>
  );

  const renderDayStatusCell = (task: any, date: string) => {
    const dayStatus = task.day_status || {};
    const status = dayStatus[date];
    const color = status ? STATUS_COLORS[status] || '#D1D5DB' : '#F3F4F6';
    const icon = status === 'done' ? 'checkmark' : status === 'in_progress' ? 'time-outline' :
      status === 'blocked' ? 'close' : status === 'cancelled' ? 'ban-outline' : null;

    return (
      <TouchableOpacity
        key={date}
        style={[s.dayCell, { backgroundColor: status ? color + '20' : '#F9FAFB', borderColor: status ? color : '#E5E7EB' }]}
        onPress={() => updateDayStatus(task.task_id, date, dayStatus)}
      >
        {icon ? (
          <Ionicons name={icon as any} size={12} color={color} />
        ) : (
          <View style={[s.dayEmpty]} />
        )}
      </TouchableOpacity>
    );
  };

  const renderTaskCard = (task: any) => (
    <TouchableOpacity
      key={task.task_id}
      style={s.taskCard}
      onPress={() => router.push({ pathname: '/tools/ctt-task', params: { id: task.task_id } })}
      activeOpacity={0.7}
    >
      {/* Top row: priority + status + source */}
      <View style={s.taskTop}>
        <View style={s.taskTopLeft}>
          <View style={[s.priorityIndicator, { backgroundColor: PRIORITY_COLORS[task.priority] || '#6B7280' }]} />
          <View style={[s.statusPill, { backgroundColor: (STATUS_COLORS[task.current_status] || '#6B7280') + '15' }]}>
            <Ionicons
              name={(STATUS_ICONS[task.current_status] || 'ellipse') as any}
              size={11}
              color={STATUS_COLORS[task.current_status] || '#6B7280'}
            />
            <Text style={[s.statusPillText, { color: STATUS_COLORS[task.current_status] || '#6B7280' }]}>
              {(task.current_status || 'open').replace('_', ' ')}
            </Text>
          </View>
          {task.source_type && task.source_type !== 'manual' && (
            <View style={[s.sourcePill, { backgroundColor: getSourceColor(task.source_type) + '12' }]}>
              <Ionicons name={(SOURCE_ICONS[task.source_type] || 'ellipse') as any} size={10} color={getSourceColor(task.source_type)} />
              <Text style={[s.sourcePillText, { color: getSourceColor(task.source_type) }]}>
                {SOURCE_LABELS[task.source_type] || task.source_type}
              </Text>
            </View>
          )}
          {task.is_routine && (
            <View style={[s.sourcePill, { backgroundColor: '#F59E0B15' }]}>
              <Ionicons name="repeat" size={10} color="#F59E0B" />
              <Text style={[s.sourcePillText, { color: '#F59E0B' }]}>
                {task.frequency || 'Routine'}
              </Text>
            </View>
          )}
        </View>
        <TouchableOpacity
          onPress={() => handleDelete(task.task_id, task.task || 'Untitled')}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Ionicons name="trash-outline" size={16} color={COLORS.textMuted} />
        </TouchableOpacity>
      </View>

      {/* Task name */}
      <Text style={s.taskTitle} numberOfLines={2}>{task.task || 'Untitled Task'}</Text>
      {task.sub_task ? <Text style={s.taskSub} numberOfLines={1}>{task.sub_task}</Text> : null}
      <TimestampLine entity={task} compact />

      {/* Meta info */}
      <View style={s.taskMeta}>
        {task.life_area ? (
          <View style={s.metaTag}>
            <Ionicons name={(getLifeAreaIcon(task.life_area) || 'ellipse') as any} size={10} color={COLORS.primary} />
            <Text style={s.metaTagText}>{getLifeAreaShort(task.life_area) || task.life_area}</Text>
          </View>
        ) : null}
        {task.decision_type ? (
          <View style={[s.metaTag, {
            backgroundColor: task.decision_type === 'problem' ? '#FEE2E2' :
              task.decision_type === 'need' ? '#FEF3C7' : '#D1FAE5'
          }]}>
            <Text style={[s.metaTagText, {
              color: task.decision_type === 'problem' ? '#EF4444' :
                task.decision_type === 'need' ? '#D97706' : '#059669'
            }]}>{task.decision_type}</Text>
          </View>
        ) : null}
        {task.deadline ? (
          <View style={s.metaTag}>
            <Ionicons name="calendar-outline" size={10} color={COLORS.textMuted} />
            <Text style={[s.metaTagText, { color: COLORS.textMuted }]}>{task.deadline}</Text>
          </View>
        ) : null}
        {task.project ? (
          <View style={s.metaTag}>
            <Ionicons name="folder-outline" size={10} color={COLORS.textMuted} />
            <Text style={[s.metaTagText, { color: COLORS.textMuted }]} numberOfLines={1}>{task.project}</Text>
          </View>
        ) : null}
        {task.task_owners?.length > 0 ? (
          <View style={s.metaTag}>
            <Ionicons name="person-outline" size={10} color={COLORS.textMuted} />
            <Text style={[s.metaTagText, { color: COLORS.textMuted }]}>{task.task_owners.join(', ')}</Text>
          </View>
        ) : null}
      </View>

      {/* Day-wise status grid */}
      {viewMode === 'calendar' && (
        <View style={s.dayGridContainer}>
          <Text style={s.dayGridLabel}>Day-wise Status (tap to cycle)</Text>
          <View style={s.dayGrid}>
            {weekDates.map(date => {
              const info = formatShortDate(date);
              return (
                <View key={date} style={s.dayColumn}>
                  <Text style={[s.dayWeekday, info.isToday && s.dayToday]}>{info.weekday}</Text>
                  <Text style={[s.dayNum, info.isToday && s.dayToday]}>{info.day}</Text>
                  {renderDayStatusCell(task, date)}
                </View>
              );
            })}
          </View>
        </View>
      )}

      {/* Quick actions row */}
      <View style={s.quickRow}>
        {['open', 'in_progress', 'done', 'blocked'].map(st => (
          <TouchableOpacity
            key={st}
            style={[
              s.quickBtn,
              task.current_status === st && { backgroundColor: STATUS_COLORS[st], borderColor: STATUS_COLORS[st] }
            ]}
            onPress={() => quickStatus(task.task_id, st)}
          >
            <Ionicons
              name={(STATUS_ICONS[st] || 'ellipse') as any}
              size={12}
              color={task.current_status === st ? '#FFF' : STATUS_COLORS[st]}
            />
            <Text style={[s.quickText, task.current_status === st && { color: '#FFF' }]}>
              {st === 'in_progress' ? 'Active' : st === 'open' ? 'Open' : st === 'done' ? 'Done' : 'Blocked'}
            </Text>
          </TouchableOpacity>
        ))}
        <TouchableOpacity style={s.calBtn} onPress={() => openCalendar(task.task_id)}>
          <Ionicons name="calendar" size={14} color="#FFF" />
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );

  const renderBoardView = () => (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }}>
      <View style={s.boardContainer}>
        {Object.entries(groupedByArea).map(([area, areaTasks]) => (
          <View key={area} style={s.boardColumn}>
            <View style={s.boardColumnHeader}>
              <Ionicons name={(getLifeAreaIcon(area) || 'ellipse') as any} size={16} color={COLORS.primary} />
              <Text style={s.boardColumnTitle}>{getLifeAreaShort(area) || 'Unassigned'}</Text>
              <View style={s.boardCount}>
                <Text style={s.boardCountText}>{(areaTasks as any[]).length}</Text>
              </View>
            </View>
            <ScrollView showsVerticalScrollIndicator={false}>
              {(areaTasks as any[]).map(task => (
                <TouchableOpacity
                  key={task.task_id}
                  style={s.boardCard}
                  onPress={() => router.push({ pathname: '/tools/ctt-task', params: { id: task.task_id } })}
                >
                  <View style={s.boardCardTop}>
                    <View style={[s.priorityDotSmall, { backgroundColor: PRIORITY_COLORS[task.priority] || '#6B7280' }]} />
                    <View style={[s.statusDotSmall, { backgroundColor: STATUS_COLORS[task.current_status] || '#6B7280' }]} />
                  </View>
                  <Text style={s.boardCardTitle} numberOfLines={2}>{task.task || 'Untitled'}</Text>
                  {task.deadline && <Text style={s.boardCardDate}>{task.deadline}</Text>}
                  <TimestampLine entity={task} compact />
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
        ))}
      </View>
    </ScrollView>
  );

  const renderEmptyState = () => (
    <View style={s.empty}>
      <View style={s.emptyIconWrap}>
        <Ionicons name="clipboard-outline" size={48} color={COLORS.textMuted} />
      </View>
      <Text style={s.emptyTitle}>No Tasks Yet</Text>
      <Text style={s.emptySub}>
        Create tasks manually or import action items from your Decisions, Solution Finders & Matrices
      </Text>
      <View style={s.emptyActions}>
        <TouchableOpacity
          style={s.emptyBtn}
          onPress={() => router.push('/tools/ctt-task')}
        >
          <Ionicons name="add-circle" size={18} color="#FFF" />
          <Text style={s.emptyBtnText}>Create Task</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[s.emptyBtn, { backgroundColor: '#4285F4' }]}
          onPress={handleAggregate}
        >
          <Ionicons name="download" size={18} color="#FFF" />
          <Text style={s.emptyBtnText}>Import Items</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      {/* Header */}
      <LinearGradient colors={['#F1F5F9', '#2D5F8B']} style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#1E293B" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Task Tracker (CTT)</Text>
          <Text style={s.headerSub}>
            {stats?.total || 0} tasks | {stats?.by_status?.done || 0} done | {stats?.routine_count || 0} routines
          </Text>
        </View>
        <View style={s.headerActions}>
          <TouchableOpacity
            style={[s.importBtn, aggregating && { opacity: 0.6 }]}
            onPress={handleAggregate}
            disabled={aggregating}
          >
            {aggregating ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <>
                <Ionicons name="download" size={16} color="#FFF" />
                <Text style={s.importText}>Import</Text>
              </>
            )}
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => router.push('/tools/ctt-task')}
            style={s.addBtn}
          >
            <Ionicons name="add" size={22} color="#FFF" />
          </TouchableOpacity>
        </View>
      </LinearGradient>

      {/* Stats */}
      {renderStats()}

      {/* View mode toggle */}
      <View style={s.viewToggleRow}>
        {([
          { key: 'list', icon: 'list', label: 'List' },
          { key: 'board', icon: 'albums', label: 'Board' },
          { key: 'calendar', icon: 'calendar', label: 'Day Grid' },
        ] as const).map(v => (
          <TouchableOpacity
            key={v.key}
            style={[s.viewToggle, viewMode === v.key && s.viewToggleActive]}
            onPress={() => setViewMode(v.key)}
          >
            <Ionicons name={v.icon as any} size={14} color={viewMode === v.key ? '#FFF' : COLORS.textMuted} />
            <Text style={[s.viewToggleText, viewMode === v.key && { color: '#FFF' }]}>{v.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Filters */}
      {renderFilters()}

      {/* Content */}
      {loading ? (
        <View style={s.loadingWrap}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={s.loadingText}>Loading tasks...</Text>
        </View>
      ) : tasks.length === 0 ? (
        <ScrollView
          contentContainerStyle={{ flexGrow: 1 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {renderEmptyState()}
        </ScrollView>
      ) : viewMode === 'board' ? (
        renderBoardView()
      ) : (
        <ScrollView
          style={s.scroll}
          contentContainerStyle={s.scrollContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {tasks.map(renderTaskCard)}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, paddingBottom: 18 },
  backBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(15,23,42,0.06)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#0F172A' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  importBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)' },
  importText: { fontSize: 12, fontWeight: '600', color: '#0F172A' },
  addBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },

  // Stats
  statsScroll: { maxHeight: 80, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  statsRow: { flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 10, gap: 8 },
  statCard: { backgroundColor: COLORS.white, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8, alignItems: 'center', minWidth: 72, borderWidth: 1, borderColor: COLORS.border },
  statNum: { fontSize: 20, fontWeight: '800', marginTop: 2 },
  statLabel: { fontSize: 9, fontWeight: '600', color: COLORS.textMuted, marginTop: 1, textTransform: 'uppercase' },

  // View toggle
  viewToggleRow: { flexDirection: 'row', paddingHorizontal: 16, paddingTop: 10, gap: 6 },
  viewToggle: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  viewToggleActive: { backgroundColor: '#F1F5F9', borderColor: '#F1F5F9' },
  viewToggleText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  // Filters
  filtersContainer: { paddingVertical: 8 },
  filterRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 6 },
  filterChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  filterActive: { backgroundColor: '#F1F5F9', borderColor: '#F1F5F9' },
  filterActiveSecondary: { backgroundColor: COLORS.primary + '12', borderColor: COLORS.primary },
  filterDot: { width: 8, height: 8, borderRadius: 4 },
  filterText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },
  filterTextActive: { color: '#0F172A' },
  filterDivider: { width: 1, height: 20, backgroundColor: COLORS.border, marginHorizontal: 4 },

  // Loading
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { fontSize: 13, color: COLORS.textMuted, marginTop: 8 },

  // Scroll
  scroll: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 32 },

  // Empty
  empty: { alignItems: 'center', paddingTop: 60, paddingHorizontal: 32 },
  emptyIconWrap: { width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.divider, justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  emptyTitle: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary },
  emptySub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  emptyActions: { flexDirection: 'row', gap: 12, marginTop: 24 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 18, paddingVertical: 12, borderRadius: 12, backgroundColor: '#F1F5F9' },
  emptyBtnText: { fontSize: 14, fontWeight: '600', color: '#0F172A' },

  // Task card
  taskCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  taskTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  taskTopLeft: { flexDirection: 'row', alignItems: 'center', gap: 6, flex: 1, flexWrap: 'wrap' },
  priorityIndicator: { width: 4, height: 28, borderRadius: 2 },
  statusPill: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  statusPillText: { fontSize: 10, fontWeight: '700', textTransform: 'capitalize' },
  sourcePill: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 6, paddingVertical: 3, borderRadius: 8 },
  sourcePillText: { fontSize: 9, fontWeight: '600', textTransform: 'capitalize' },
  taskTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginLeft: 8 },
  taskSub: { fontSize: 12, color: COLORS.textSecondary, marginLeft: 8, marginTop: 2 },
  taskMeta: { flexDirection: 'row', gap: 6, marginTop: 8, marginLeft: 8, flexWrap: 'wrap' },
  metaTag: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: COLORS.primary + '10', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  metaTagText: { fontSize: 10, fontWeight: '600', color: COLORS.primary, textTransform: 'capitalize' },

  // Day-wise grid
  dayGridContainer: { marginTop: 10, marginLeft: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: COLORS.divider },
  dayGridLabel: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5 },
  dayGrid: { flexDirection: 'row', gap: 4 },
  dayColumn: { alignItems: 'center', flex: 1 },
  dayWeekday: { fontSize: 9, fontWeight: '600', color: COLORS.textMuted },
  dayNum: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 3 },
  dayToday: { color: '#3B82F6' },
  dayCell: { width: 32, height: 28, borderRadius: 6, borderWidth: 1, justifyContent: 'center', alignItems: 'center' },
  dayEmpty: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#E5E7EB' },

  // Quick actions
  quickRow: { flexDirection: 'row', gap: 5, marginTop: 10, marginLeft: 8, borderTopWidth: 1, borderTopColor: COLORS.divider, paddingTop: 10 },
  quickBtn: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border },
  quickText: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted },
  calBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, backgroundColor: '#4285F4', justifyContent: 'center', alignItems: 'center' },

  // Board view
  boardContainer: { flexDirection: 'row', paddingHorizontal: 12, paddingBottom: 24, gap: 10 },
  boardColumn: { width: SCREEN_W * 0.6, backgroundColor: COLORS.divider, borderRadius: 12, padding: 10, maxHeight: 500 },
  boardColumnHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10, paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  boardColumnTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, flex: 1 },
  boardCount: { backgroundColor: COLORS.primary + '20', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  boardCountText: { fontSize: 11, fontWeight: '700', color: COLORS.primary },
  boardCard: { backgroundColor: COLORS.white, borderRadius: 10, padding: 10, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  boardCardTop: { flexDirection: 'row', gap: 4, marginBottom: 4 },
  priorityDotSmall: { width: 8, height: 8, borderRadius: 4 },
  statusDotSmall: { width: 8, height: 8, borderRadius: 4 },
  boardCardTitle: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  boardCardDate: { fontSize: 10, color: COLORS.textMuted, marginTop: 4 },
});
