import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, ActivityIndicator, Alert,
  StyleSheet, RefreshControl, Modal, TextInput, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Linking from 'expo-linking';
import * as WebBrowser from 'expo-web-browser';
import Constants from 'expo-constants';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';

const COLORS = {
  bg: '#0F172A', surface: '#1E293B', surfaceLight: '#334155',
  primary: '#3B82F6', secondary: '#8B5CF6', accent: '#10B981',
  text: '#F8FAFC', textSecondary: '#94A3B8', textMuted: '#64748B',
  border: '#334155', danger: '#EF4444', warning: '#F59E0B',
  calendarBlue: '#4285F4', calendarGreen: '#0F9D58',
};

export default function GoogleCalendarScreen() {
  const router = useRouter();
  const { session } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [connected, setConnected] = useState(false);
  const [googleEmail, setGoogleEmail] = useState('');
  const [events, setEvents] = useState<any[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);

  // New event form
  const [newEvent, setNewEvent] = useState({
    summary: '', description: '', location: '',
    date: '', startTime: '09:00', endTime: '10:00',
    all_day: false,
  });

  const checkConnection = useCallback(async () => {
    try {
      const res = await api.get('/oauth/calendar/status', {
        headers: { Authorization: `Bearer ${session}` },
      });
      setConnected(res.data?.connected || false);
      setGoogleEmail(res.data?.google_email || '');
      if (res.data?.connected) {
        await fetchEvents();
      }
    } catch (e) {
      console.error('Calendar status check error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [session]);

  const fetchEvents = async () => {
    try {
      const res = await api.get('/google-calendar/events', {
        params: { days: 30 },
        headers: { Authorization: `Bearer ${session}` },
      });
      setEvents(res.data?.events || []);
    } catch (e: any) {
      if (e?.response?.status === 401) {
        setConnected(false);
      }
    }
  };

  useEffect(() => { checkConnection(); }, [checkConnection]);

  const handleConnect = async () => {
    try {
      const res = await api.get('/oauth/calendar/start', {
        headers: { Authorization: `Bearer ${session}` },
      });
      const authUrl = res.data?.authorization_url;
      if (authUrl) {
        // Open in system browser for OAuth
        if (Platform.OS === 'web') {
          window.open(authUrl, '_self');
        } else {
          await WebBrowser.openBrowserAsync(authUrl);
          // After returning, re-check connection
          setTimeout(() => checkConnection(), 2000);
        }
      }
    } catch (e) {
      Alert.alert('Error', 'Failed to start Google Calendar connection');
    }
  };

  const handleDisconnect = () => {
    Alert.alert(
      'Disconnect Calendar',
      'Are you sure you want to disconnect your Google Calendar?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Disconnect', style: 'destructive',
          onPress: async () => {
            try {
              await api.delete('/oauth/calendar/disconnect', {
                headers: { Authorization: `Bearer ${session}` },
              });
              setConnected(false);
              setGoogleEmail('');
              setEvents([]);
            } catch (e) {
              Alert.alert('Error', 'Failed to disconnect calendar');
            }
          },
        },
      ]
    );
  };

  const handleCreateEvent = async () => {
    if (!newEvent.summary.trim()) return Alert.alert('Required', 'Event title is required');
    if (!newEvent.date) return Alert.alert('Required', 'Date is required');

    setCreating(true);
    try {
      const start = newEvent.all_day
        ? newEvent.date
        : `${newEvent.date}T${newEvent.startTime}:00`;
      const end = newEvent.all_day
        ? newEvent.date
        : `${newEvent.date}T${newEvent.endTime}:00`;

      await api.post('/google-calendar/events', {
        summary: newEvent.summary,
        description: newEvent.description,
        location: newEvent.location,
        start, end,
        all_day: newEvent.all_day,
        timezone: 'Asia/Kolkata',
      }, { headers: { Authorization: `Bearer ${session}` } });

      Alert.alert('Success', 'Event added to Google Calendar!');
      setShowCreateModal(false);
      setNewEvent({ summary: '', description: '', location: '', date: '', startTime: '09:00', endTime: '10:00', all_day: false });
      fetchEvents();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail || 'Failed to create event');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteEvent = (eventId: string, title: string) => {
    Alert.alert('Delete Event', `Remove "${title}" from your calendar?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/google-calendar/events/${eventId}`, {
              headers: { Authorization: `Bearer ${session}` },
            });
            setEvents(prev => prev.filter(e => e.id !== eventId));
          } catch (e) {
            Alert.alert('Error', 'Failed to delete event');
          }
        },
      },
    ]);
  };

  const formatEventTime = (start: string, end: string) => {
    if (!start) return '';
    try {
      const s = new Date(start);
      const e = end ? new Date(end) : null;
      const dateStr = s.toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' });
      if (start.length <= 10) return `${dateStr} (All Day)`;
      const timeStr = s.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
      const endStr = e ? e.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '';
      return `${dateStr} · ${timeStr}${endStr ? ` - ${endStr}` : ''}`;
    } catch {
      return start;
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.calendarBlue} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Google Calendar</Text>
          <Text style={styles.headerSubtitle}>
            {connected ? `Connected · ${googleEmail}` : 'Sync your tasks & events'}
          </Text>
        </View>
        {connected && (
          <TouchableOpacity onPress={() => setShowCreateModal(true)} style={styles.addBtn}>
            <Ionicons name="add" size={22} color="#FFF" />
          </TouchableOpacity>
        )}
      </View>

      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
        refreshControl={
          <RefreshControl refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); checkConnection(); }}
            tintColor={COLORS.calendarBlue} />
        }
      >
        {!connected ? (
          /* Not Connected State */
          <View style={styles.connectCard}>
            <View style={styles.googleLogo}>
              <Ionicons name="calendar" size={48} color={COLORS.calendarBlue} />
            </View>
            <Text style={styles.connectTitle}>Connect Google Calendar</Text>
            <Text style={styles.connectDesc}>
              Sync your CTT action items, decision deadlines, and goals directly to your Google Calendar. Never miss a task.
            </Text>

            <View style={styles.featureList}>
              {[
                { icon: 'sync', text: 'Sync CTT tasks as calendar events' },
                { icon: 'notifications', text: 'Get reminders before deadlines' },
                { icon: 'calendar', text: 'View all events in one place' },
                { icon: 'shield-checkmark', text: 'Secure OAuth2 connection' },
              ].map((f, i) => (
                <View key={i} style={styles.featureItem}>
                  <Ionicons name={f.icon as any} size={18} color={COLORS.calendarGreen} />
                  <Text style={styles.featureText}>{f.text}</Text>
                </View>
              ))}
            </View>

            <TouchableOpacity style={styles.connectBtn} onPress={handleConnect}>
              <Ionicons name="logo-google" size={20} color="#FFF" />
              <Text style={styles.connectBtnText}>Connect with Google</Text>
            </TouchableOpacity>
          </View>
        ) : (
          /* Connected State - Show Events */
          <>
            {/* Connection info */}
            <View style={styles.connectedBar}>
              <View style={styles.connectedDot} />
              <Text style={styles.connectedText}>Connected: {googleEmail}</Text>
              <TouchableOpacity onPress={handleDisconnect}>
                <Ionicons name="unlink" size={18} color={COLORS.danger} />
              </TouchableOpacity>
            </View>

            <Text style={styles.sectionTitle}>
              Upcoming Events ({events.length})
            </Text>

            {events.length === 0 ? (
              <View style={styles.emptyEvents}>
                <Ionicons name="calendar-outline" size={48} color={COLORS.textMuted} />
                <Text style={styles.emptyText}>No upcoming events</Text>
                <Text style={styles.emptySubtext}>Create events or sync CTT tasks</Text>
              </View>
            ) : (
              events.map((event) => (
                <View key={event.id} style={styles.eventCard}>
                  <View style={styles.eventTimeline}>
                    <View style={styles.eventDot} />
                    <View style={styles.eventLine} />
                  </View>
                  <View style={styles.eventContent}>
                    <Text style={styles.eventTitle} numberOfLines={1}>{event.summary}</Text>
                    <Text style={styles.eventTime}>
                      {formatEventTime(event.start, event.end)}
                    </Text>
                    {event.location ? (
                      <View style={styles.eventMetaRow}>
                        <Ionicons name="location-outline" size={12} color={COLORS.textMuted} />
                        <Text style={styles.eventMeta} numberOfLines={1}>{event.location}</Text>
                      </View>
                    ) : null}
                    {event.description && event.description.includes('[CTT]') && (
                      <View style={styles.cttBadge}>
                        <Ionicons name="clipboard" size={10} color={COLORS.calendarGreen} />
                        <Text style={styles.cttBadgeText}>CTT Task</Text>
                      </View>
                    )}
                  </View>
                  <TouchableOpacity
                    style={styles.eventDeleteBtn}
                    onPress={() => handleDeleteEvent(event.id, event.summary)}
                  >
                    <Ionicons name="trash-outline" size={16} color={COLORS.danger} />
                  </TouchableOpacity>
                </View>
              ))
            )}
          </>
        )}
      </ScrollView>

      {/* Create Event Modal */}
      <Modal visible={showCreateModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>New Calendar Event</Text>
              <TouchableOpacity onPress={() => setShowCreateModal(false)}>
                <Ionicons name="close" size={24} color={COLORS.text} />
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false}>
              <Text style={styles.inputLabel}>Title *</Text>
              <TextInput
                style={styles.input}
                placeholder="Event title"
                placeholderTextColor={COLORS.textMuted}
                value={newEvent.summary}
                onChangeText={(v) => setNewEvent(p => ({ ...p, summary: v }))}
              />

              <Text style={styles.inputLabel}>Date * (YYYY-MM-DD)</Text>
              <TextInput
                style={styles.input}
                placeholder="2026-03-01"
                placeholderTextColor={COLORS.textMuted}
                value={newEvent.date}
                onChangeText={(v) => setNewEvent(p => ({ ...p, date: v }))}
              />

              <TouchableOpacity
                style={styles.allDayToggle}
                onPress={() => setNewEvent(p => ({ ...p, all_day: !p.all_day }))}
              >
                <Ionicons
                  name={newEvent.all_day ? 'checkbox' : 'square-outline'}
                  size={22} color={COLORS.primary}
                />
                <Text style={styles.allDayText}>All-day event</Text>
              </TouchableOpacity>

              {!newEvent.all_day && (
                <View style={styles.timeRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.inputLabel}>Start Time (HH:MM)</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="09:00"
                      placeholderTextColor={COLORS.textMuted}
                      value={newEvent.startTime}
                      onChangeText={(v) => setNewEvent(p => ({ ...p, startTime: v }))}
                    />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.inputLabel}>End Time (HH:MM)</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="10:00"
                      placeholderTextColor={COLORS.textMuted}
                      value={newEvent.endTime}
                      onChangeText={(v) => setNewEvent(p => ({ ...p, endTime: v }))}
                    />
                  </View>
                </View>
              )}

              <Text style={styles.inputLabel}>Description</Text>
              <TextInput
                style={[styles.input, { minHeight: 80, textAlignVertical: 'top' }]}
                placeholder="Event details..."
                placeholderTextColor={COLORS.textMuted}
                value={newEvent.description}
                onChangeText={(v) => setNewEvent(p => ({ ...p, description: v }))}
                multiline
              />

              <Text style={styles.inputLabel}>Location</Text>
              <TextInput
                style={styles.input}
                placeholder="Event location"
                placeholderTextColor={COLORS.textMuted}
                value={newEvent.location}
                onChangeText={(v) => setNewEvent(p => ({ ...p, location: v }))}
              />

              <TouchableOpacity
                style={[styles.createBtn, creating && { opacity: 0.6 }]}
                onPress={handleCreateEvent}
                disabled={creating}
              >
                {creating ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <>
                    <Ionicons name="calendar" size={18} color="#FFF" />
                    <Text style={styles.createBtnText}>Add to Calendar</Text>
                  </>
                )}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', padding: 16,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  backBtn: { marginRight: 12, padding: 4 },
  headerTitle: { fontSize: 20, fontWeight: '700', color: COLORS.text },
  headerSubtitle: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  addBtn: {
    backgroundColor: COLORS.calendarBlue, width: 36, height: 36, borderRadius: 18,
    alignItems: 'center', justifyContent: 'center',
  },
  // Connect card
  connectCard: {
    backgroundColor: COLORS.surface, borderRadius: 20, padding: 24,
    alignItems: 'center', borderWidth: 1, borderColor: COLORS.border,
  },
  googleLogo: {
    width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.calendarBlue + '15',
    alignItems: 'center', justifyContent: 'center', marginBottom: 16,
  },
  connectTitle: { fontSize: 22, fontWeight: '700', color: COLORS.text, marginBottom: 8 },
  connectDesc: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', lineHeight: 20, marginBottom: 20 },
  featureList: { width: '100%', marginBottom: 24, gap: 10 },
  featureItem: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  featureText: { fontSize: 14, color: COLORS.textSecondary },
  connectBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: COLORS.calendarBlue, paddingVertical: 14, paddingHorizontal: 28,
    borderRadius: 14,
  },
  connectBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  // Connected bar
  connectedBar: {
    flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: COLORS.surface,
    padding: 12, borderRadius: 12, marginBottom: 16,
    borderWidth: 1, borderColor: COLORS.calendarGreen + '40',
  },
  connectedDot: {
    width: 8, height: 8, borderRadius: 4, backgroundColor: COLORS.calendarGreen,
  },
  connectedText: { flex: 1, fontSize: 13, color: COLORS.textSecondary },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: COLORS.text, marginBottom: 12 },
  emptyEvents: { alignItems: 'center', paddingTop: 40 },
  emptyText: { fontSize: 16, color: COLORS.textSecondary, marginTop: 12 },
  emptySubtext: { fontSize: 13, color: COLORS.textMuted, marginTop: 4 },
  // Event cards
  eventCard: {
    flexDirection: 'row', marginBottom: 2, paddingVertical: 10,
  },
  eventTimeline: { width: 24, alignItems: 'center' },
  eventDot: {
    width: 10, height: 10, borderRadius: 5, backgroundColor: COLORS.calendarBlue,
    marginTop: 4,
  },
  eventLine: { width: 2, flex: 1, backgroundColor: COLORS.border, marginTop: 2 },
  eventContent: { flex: 1, paddingLeft: 10, paddingBottom: 8 },
  eventTitle: { fontSize: 15, fontWeight: '600', color: COLORS.text, marginBottom: 2 },
  eventTime: { fontSize: 12, color: COLORS.calendarBlue },
  eventMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 2 },
  eventMeta: { fontSize: 11, color: COLORS.textMuted },
  cttBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4,
    backgroundColor: COLORS.calendarGreen + '15', paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: 6, alignSelf: 'flex-start',
  },
  cttBadgeText: { fontSize: 10, fontWeight: '600', color: COLORS.calendarGreen },
  eventDeleteBtn: { padding: 8, alignSelf: 'flex-start' },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  modalContent: {
    backgroundColor: COLORS.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24,
    padding: 20, maxHeight: '85%',
  },
  modalHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  inputLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 6, marginTop: 12 },
  input: {
    backgroundColor: COLORS.surfaceLight, borderRadius: 10, padding: 12,
    color: COLORS.text, fontSize: 14, borderWidth: 1, borderColor: COLORS.border,
  },
  allDayToggle: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12 },
  allDayText: { fontSize: 14, color: COLORS.textSecondary },
  timeRow: { flexDirection: 'row', gap: 12 },
  createBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: COLORS.calendarBlue, borderRadius: 12, paddingVertical: 14, marginTop: 24, marginBottom: 20,
  },
  createBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
