import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, Alert, ActivityIndicator, Linking,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#EF4444', high: '#F59E0B', medium: '#3B82F6', low: '#6B7280',
};
const STATUS_COLORS: Record<string, string> = {
  open: '#6B7280', in_progress: '#3B82F6', done: '#10B981', blocked: '#EF4444',
};

function formatDate(dateStr: string): { weekday: string; day: string; month: string; isToday: boolean; isPast: boolean } {
  const d = new Date(dateStr + 'T00:00:00');
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  return {
    weekday: weekdays[d.getDay()],
    day: d.getDate().toString(),
    month: months[d.getMonth()],
    isToday: d.getTime() === today.getTime(),
    isPast: d.getTime() < today.getTime(),
  };
}

export default function CalendarViewScreen() {
  const router = useRouter();
  const [upcoming, setUpcoming] = useState<any[]>([]);
  const [byDate, setByDate] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [daysAhead, setDaysAhead] = useState(30);

  const fetchData = async () => {
    try {
      const res = await api.get(`/calendar/upcoming?days=${daysAhead}`);
      setUpcoming(res.data?.upcoming || []);
      setByDate(res.data?.by_date || {});
    } catch (e) { console.error('Calendar fetch error:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, [daysAhead]));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const handleBatchExport = async () => {
    setExporting(true);
    try {
      const res = await api.post('/calendar/batch-export', {});
      const tasks = res.data?.tasks || [];
      if (tasks.length === 0) {
        showAlert('No Tasks', 'No tasks with deadlines found to export.');
      } else {
        showAlert(
          'Export to Google Calendar',
          `${tasks.length} tasks ready. Each will open in Google Calendar.`,
          [
            { text: 'Cancel', style: 'cancel' },
            {
              text: 'Open First',
              onPress: () => {
                if (tasks[0]?.calendar_url) Linking.openURL(tasks[0].calendar_url);
              },
            },
          ],
        );
      }
    } catch (e) { showAlert('Error', 'Failed to generate calendar links'); }
    finally { setExporting(false); }
  };

  const openTaskCalendar = async (taskId: string) => {
    try {
      const res = await api.get(`/ctt/tasks/${taskId}/calendar-url`);
      if (res.data?.calendar_url) {
        Linking.openURL(res.data.calendar_url);
      }
    } catch (e) { showAlert('Error', 'Failed to generate calendar link'); }
  };

  const sortedDates = Object.keys(byDate).sort();

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#4285F4', '#5B9EF4']} style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Calendar View</Text>
          <Text style={s.headerSub}>{upcoming.length} upcoming tasks in next {daysAhead} days</Text>
        </View>
        <TouchableOpacity
          style={[s.exportBtn, exporting && { opacity: 0.6 }]}
          onPress={handleBatchExport}
          disabled={exporting}
        >
          {exporting ? (
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <>
              <Ionicons name="calendar" size={16} color="#FFF" />
              <Text style={s.exportText}>Export All</Text>
            </>
          )}
        </TouchableOpacity>
      </LinearGradient>

      {/* Time range filter */}
      <View style={s.rangeRow}>
        {[7, 14, 30, 60, 90].map(d => (
          <TouchableOpacity
            key={d}
            style={[s.rangeChip, daysAhead === d && s.rangeActive]}
            onPress={() => setDaysAhead(d)}
          >
            <Text style={[s.rangeText, daysAhead === d && { color: '#FFF' }]}>{d}d</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#4285F4" />
        </View>
      ) : sortedDates.length === 0 ? (
        <ScrollView
          contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', alignItems: 'center', padding: 32 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          <View style={s.emptyIcon}>
            <Ionicons name="calendar-outline" size={48} color={COLORS.textMuted} />
          </View>
          <Text style={s.emptyTitle}>No Upcoming Deadlines</Text>
          <Text style={s.emptySub}>Tasks with deadlines will appear here in a timeline view</Text>
        </ScrollView>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {sortedDates.map(date => {
            const dateInfo = formatDate(date);
            const tasks = byDate[date] || [];
            return (
              <View key={date} style={s.dateGroup}>
                {/* Date header */}
                <View style={s.dateHeader}>
                  <View style={[
                    s.dateBox,
                    dateInfo.isToday && s.dateBoxToday,
                    dateInfo.isPast && s.dateBoxPast,
                  ]}>
                    <Text style={[s.dateWeekday, dateInfo.isToday && { color: '#FFF' }]}>{dateInfo.weekday}</Text>
                    <Text style={[s.dateDay, dateInfo.isToday && { color: '#FFF' }]}>{dateInfo.day}</Text>
                    <Text style={[s.dateMonth, dateInfo.isToday && { color: 'rgba(255,255,255,0.8)' }]}>{dateInfo.month}</Text>
                  </View>
                  <View style={s.dateLine} />
                  <Text style={s.dateCount}>{tasks.length} task{tasks.length > 1 ? 's' : ''}</Text>
                </View>

                {/* Tasks for this date */}
                {tasks.map((task: any) => (
                  <TouchableOpacity
                    key={task.task_id}
                    style={s.taskRow}
                    onPress={() => router.push({ pathname: '/tools/ctt-task', params: { id: task.task_id } })}
                  >
                    <View style={[s.taskDot, { backgroundColor: PRIORITY_COLORS[task.priority] || '#6B7280' }]} />
                    <View style={{ flex: 1 }}>
                      <Text style={s.taskName} numberOfLines={1}>{task.task || 'Untitled'}</Text>
                      <View style={s.taskMetaRow}>
                        <View style={[s.taskStatus, { backgroundColor: (STATUS_COLORS[task.current_status] || '#6B7280') + '15' }]}>
                          <Text style={[s.taskStatusText, { color: STATUS_COLORS[task.current_status] || '#6B7280' }]}>
                            {(task.current_status || 'open').replace('_', ' ')}
                          </Text>
                        </View>
                        {task.project && <Text style={s.taskProject} numberOfLines={1}>{task.project}</Text>}
                      </View>
                    </View>
                    <TouchableOpacity
                      style={s.calIcon}
                      onPress={() => openTaskCalendar(task.task_id)}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    >
                      <Ionicons name="open-outline" size={16} color="#4285F4" />
                    </TouchableOpacity>
                  </TouchableOpacity>
                ))}
              </View>
            );
          })}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, paddingBottom: 18 },
  backBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  exportBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)' },
  exportText: { fontSize: 12, fontWeight: '600', color: '#FFF' },

  rangeRow: { flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 10, gap: 6 },
  rangeChip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  rangeActive: { backgroundColor: '#4285F4', borderColor: '#4285F4' },
  rangeText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },

  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.divider, justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptySub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, lineHeight: 20 },

  dateGroup: { marginBottom: 20 },
  dateHeader: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 8 },
  dateBox: { width: 52, alignItems: 'center', paddingVertical: 6, borderRadius: 10, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  dateBoxToday: { backgroundColor: '#4285F4', borderColor: '#4285F4' },
  dateBoxPast: { opacity: 0.6 },
  dateWeekday: { fontSize: 9, fontWeight: '600', color: COLORS.textMuted, textTransform: 'uppercase' },
  dateDay: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary },
  dateMonth: { fontSize: 9, fontWeight: '600', color: COLORS.textMuted },
  dateLine: { flex: 1, height: 1, backgroundColor: COLORS.border },
  dateCount: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  taskRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, borderRadius: 10, padding: 12, marginBottom: 6, marginLeft: 18, borderWidth: 1, borderColor: COLORS.border },
  taskDot: { width: 8, height: 8, borderRadius: 4 },
  taskName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  taskMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  taskStatus: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  taskStatusText: { fontSize: 10, fontWeight: '600', textTransform: 'capitalize' },
  taskProject: { fontSize: 11, color: COLORS.textMuted },
  calIcon: { padding: 6 },
});
