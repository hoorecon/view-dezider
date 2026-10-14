import React, { useCallback, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Linking, Platform } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS, GRADIENTS } from '../src/constants/colors';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { safeBack } from '../src/utils/navigation';
import AppointmentCalendar from '../src/components/AppointmentCalendar';

const DISPLAY_FONT = Platform.OS === 'web' ? 'Fraunces, Georgia, "Times New Roman", serif' : undefined;

function localDateTimeValue(date: Date) {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatAppointment(iso?: string) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

export default function ExpertAppointmentsScreen() {
  const router = useRouter();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [rescheduleId, setRescheduleId] = useState<string | null>(null);
  const [rescheduleLocal, setRescheduleLocal] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const resp = await api.get('/call-sessions', { params: { role: 'expert' } });
      setItems(Array.isArray(resp.data) ? resp.data : []);
    } catch (err) {
      console.error(err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { load(); }, []));

  const cancelAppointment = async (sessionId: string) => {
    try {
      await api.post(`/call-sessions/${sessionId}/cancel`);
      showAlert('Cancelled', 'The appointment was cancelled and both people were notified.');
      load();
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Could not cancel the appointment');
    }
  };

  const saveReschedule = async (sessionId: string, durationMinutes: number) => {
    const when = new Date(rescheduleLocal);
    if (Number.isNaN(when.getTime()) || when.getTime() < Date.now() + 15 * 60 * 1000) {
      showAlert('Pick a later time', 'Appointments must be at least 15 minutes from now.');
      return;
    }
    setSaving(true);
    try {
      await api.post(`/call-sessions/${sessionId}/reschedule`, {
        scheduled_at: when.toISOString(),
        duration_minutes: durationMinutes || 30,
      });
      setRescheduleId(null);
      showAlert('Rescheduled', 'The new time was sent by email and WhatsApp. The join link is unchanged.');
      load();
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Could not reschedule the appointment');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={GRADIENTS.primary} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.white} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.kicker}>Expert</Text>
          <Text style={styles.headerTitle}>Your appointments</Text>
        </View>
      </LinearGradient>
      {loading ? (
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView contentContainerStyle={styles.list}>
          {items.length === 0 ? (
            <Text style={styles.empty}>No upcoming appointments for this expert email.</Text>
          ) : items.map((appt) => {
            const id = appt.id || appt.session_id;
            return (
              <View key={id} style={styles.card}>
                <Text style={styles.name}>{appt.creator_name || 'Client'}</Text>
                <Text style={styles.meta}>{appt.share_context?.decision_title || 'Consultation'}</Text>
                <Text style={styles.meta}>{formatAppointment(appt.scheduled_at)} · {appt.duration_minutes} min</Text>
                {!!appt.google_calendar_link && (
                  <TouchableOpacity onPress={() => Linking.openURL(appt.google_calendar_link)}>
                    <Text style={styles.reschedule}>
                      {appt.google_calendar_synced ? 'Open in Google Calendar' : 'Add to Google Calendar'}
                    </Text>
                  </TouchableOpacity>
                )}
                {rescheduleId === id && (
                  <AppointmentCalendar value={rescheduleLocal} onChange={setRescheduleLocal} />
                )}
                <View style={styles.actions}>
                  {rescheduleId === id ? (
                    <TouchableOpacity disabled={saving} onPress={() => saveReschedule(id, appt.duration_minutes)}>
                      <Text style={styles.reschedule}>{saving ? 'Saving...' : 'Save new time'}</Text>
                    </TouchableOpacity>
                  ) : (
                    <TouchableOpacity onPress={() => {
                      setRescheduleId(id);
                      setRescheduleLocal(localDateTimeValue(new Date(appt.scheduled_at)));
                    }}>
                      <Text style={styles.reschedule}>Reschedule</Text>
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity onPress={() => cancelAppointment(id)}>
                    <Text style={styles.cancel}>Cancel</Text>
                  </TouchableOpacity>
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },
  kicker: { fontSize: 13, fontWeight: '500', color: 'rgba(255,255,255,0.85)' },
  headerTitle: { fontSize: 22, fontWeight: '800', color: COLORS.white, letterSpacing: -0.4, fontFamily: DISPLAY_FONT },
  list: { padding: 16, gap: 12 },
  card: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: COLORS.border, gap: 6 },
  name: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  meta: { fontSize: 13, color: COLORS.textSecondary },
  actions: { flexDirection: 'row', gap: 16, marginTop: 8 },
  reschedule: { color: COLORS.primary, fontWeight: '700', fontSize: 14 },
  cancel: { color: '#DC2626', fontWeight: '700', fontSize: 14 },
  empty: { color: COLORS.textMuted, fontSize: 14, textAlign: 'center', marginTop: 24 },
});
