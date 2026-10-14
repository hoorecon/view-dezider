import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  ScrollView,
  Modal,
  Linking,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import api from '../utils/api';
import { showAlert } from '../utils/alert';
import AppointmentCalendar from './AppointmentCalendar';

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

function nextBookableSlot() {
  const date = new Date(Date.now() + 20 * 60 * 1000);
  const remainder = date.getMinutes() % 30;
  if (remainder !== 0) date.setMinutes(date.getMinutes() + (30 - remainder));
  date.setSeconds(0, 0);
  const minutes = date.getHours() * 60 + date.getMinutes();
  if (minutes < 8 * 60) date.setHours(8, 0, 0, 0);
  if (minutes > 23 * 60 + 30) {
    date.setDate(date.getDate() + 1);
    date.setHours(8, 0, 0, 0);
  }
  return localDateTimeValue(date);
}

function meetingStatus(row: any) {
  const when = row?.scheduled_at ? new Date(row.scheduled_at).getTime() : 0;
  if (row?.status === 'scheduled' && row?.is_scheduled && when > Date.now()) return 'upcoming';
  if (row?.status === 'cancelled') return 'Cancelled';
  if (row?.status === 'ended') return 'Completed';
  if (row?.status === 'expired') return 'Expired';
  if (row?.status === 'active') return 'Live';
  return 'Past';
}

interface Expert {
  id: string;
  name: string;
  email: string;
  phone?: string;
  whatsapp?: string;
  specialization: string;
  is_active: boolean;
}

interface ExpertCallModalProps {
  visible: boolean;
  onClose: () => void;
  decisionId: string;
  decisionTitle: string;
  stepNumber: number;
  stepName: string;
}

export default function ExpertCallModal({
  visible,
  onClose,
  decisionId,
  decisionTitle,
  stepNumber,
  stepName,
}: ExpertCallModalProps) {
  const [experts, setExperts] = useState<Expert[]>([]);
  const [expertsLoading, setExpertsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedExpert, setSelectedExpert] = useState<Expert | null>(null);
  const [expertPhone, setExpertPhone] = useState('');
  const [expertEmail, setExpertEmail] = useState('');
  const [duration, setDuration] = useState('30');
  const [callConfig, setCallConfig] = useState<any>(null);
  const [activeSession, setActiveSession] = useState<any>(null);
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const [meetingMode, setMeetingMode] = useState<'now' | 'appointment'>('now');
  const [panel, setPanel] = useState<'new' | 'history'>('new');
  const [appointmentLocal, setAppointmentLocal] = useState(nextBookableSlot);
  const [appointments, setAppointments] = useState<any[]>([]);
  const [rescheduleId, setRescheduleId] = useState<string | null>(null);
  const [rescheduleLocal, setRescheduleLocal] = useState('');
  const timerRef = useRef<any>(null);

  useEffect(() => {
    if (visible) {
      setSearchQuery('');
      setPanel('new');
      fetchExperts();
      fetchCallConfig();
      fetchAppointments();
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [visible]);

  useEffect(() => {
    if (activeSession && timeLeft !== null && timeLeft > 0) {
      timerRef.current = setInterval(() => {
        setTimeLeft(prev => {
          if (prev === null || prev <= 1) {
            clearInterval(timerRef.current);
            handleEndCall();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timerRef.current);
    }
  }, [activeSession]);

  const fetchExperts = async () => {
    setExpertsLoading(true);
    try {
      const [lRes, pRes] = await Promise.allSettled([
        api.get('/experts'),
        api.get('/platform-experts'),
      ]);

      const legacy = lRes.status === 'fulfilled'
        ? (Array.isArray(lRes.value.data) ? lRes.value.data : lRes.value.data?.items || [])
        : [];
      const platform = pRes.status === 'fulfilled'
        ? (pRes.value.data?.items || (Array.isArray(pRes.value.data) ? pRes.value.data : []))
        : [];

      const merged: Expert[] = [];
      const seen = new Set<string>();

      [...legacy, ...platform].forEach((e: any) => {
        const id = e.id || e.expert_id;
        const org = (Array.isArray(e.organizations) ? e.organizations : []).find(
          (o: any) => o?.whatsapp || o?.mobile || o?.contact_email
        );
        const email = (e.email || org?.contact_email || '').toLowerCase();
        const phone = e.whatsapp || e.phone || e.mobile || org?.whatsapp || org?.mobile || '';
        const key = id || email;
        if (!key || seen.has(key)) return;
        if (e.is_active === false) return;
        seen.add(key);
        merged.push({
          id,
          name: e.name || 'Unnamed Expert',
          email: e.email || org?.contact_email || '',
          phone,
          whatsapp: phone,
          specialization: e.specialization || e.expert_type || (Array.isArray(e.specializations) ? e.specializations.join(', ') : '') || '',
          is_active: e.is_active !== false,
        });
      });

      setExperts(merged);
    } catch (err) {
      console.error('Failed to fetch experts', err);
      setExperts([]);
    } finally {
      setExpertsLoading(false);
    }
  };

  const fetchCallConfig = async () => {
    try {
      const resp = await api.get('/call-config');
      const data = resp.data || {};
      setCallConfig(data);
      if (data.default_duration) {
        setDuration(String(data.default_duration));
      }
    } catch (err) {
      console.error('Failed to fetch call config', err);
    }
  };

  const fetchAppointments = async () => {
    if (!decisionId) return;
    try {
      const resp = await api.get('/call-sessions', { params: { decision_id: decisionId } });
      const rows = Array.isArray(resp.data) ? resp.data : [];
      setAppointments(rows);
    } catch (err) {
      console.error('Failed to fetch appointments', err);
    }
  };

  const startCall = async () => {
    if (!selectedExpert) {
      showAlert('Select Expert', 'Please select an expert to call.');
      return;
    }
    const dur = parseInt(duration) || 30;
    const minDur = callConfig?.min_duration || 5;
    const maxDur = callConfig?.max_duration || 120;
    if (dur < minDur || dur > maxDur) {
      showAlert('Invalid Duration', `Duration must be between ${minDur} and ${maxDur} minutes.`);
      return;
    }
    let scheduledAt: string | undefined;
    if (meetingMode === 'appointment') {
      const when = new Date(appointmentLocal);
      if (Number.isNaN(when.getTime()) || when.getTime() < Date.now() + 15 * 60 * 1000) {
        showAlert('Pick a later time', 'Appointments must be at least 15 minutes from now.');
        return;
      }
      scheduledAt = when.toISOString();
    }
    setLoading(true);
    try {
      const resp = await api.post('/call-sessions', {
        expert_id: selectedExpert.id,
        expert_name: selectedExpert.name,
        expert_email: expertEmail || selectedExpert.email,
        expert_phone: expertPhone || selectedExpert.whatsapp || selectedExpert.phone,
        decision_id: decisionId,
        step_number: stepNumber,
        step_name: stepName,
        duration_minutes: dur,
        decision_title: decisionTitle,
        ...(scheduledAt ? { scheduled_at: scheduledAt } : {}),
      });
      const data = resp.data;
      if (data?.room_url) {
        setActiveSession(data);
        setTimeLeft(data.is_scheduled ? null : dur * 60);
        if (data.is_scheduled) fetchAppointments();
      } else {
        showAlert('Error', data?.detail || 'Failed to create call session');
      }
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Failed to start call');
    } finally {
      setLoading(false);
    }
  };

  const cancelAppointment = async (sessionId: string) => {
    try {
      await api.post(`/call-sessions/${sessionId}/cancel`);
      showAlert('Cancelled', 'The appointment was cancelled and the expert was notified.');
      fetchAppointments();
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Could not cancel the appointment');
    }
  };

  const saveReschedule = async (sessionId: string, currentDuration: number) => {
    const when = new Date(rescheduleLocal);
    if (Number.isNaN(when.getTime()) || when.getTime() < Date.now() + 15 * 60 * 1000) {
      showAlert('Pick a later time', 'Appointments must be at least 15 minutes from now.');
      return;
    }
    setLoading(true);
    try {
      await api.post(`/call-sessions/${sessionId}/reschedule`, {
        scheduled_at: when.toISOString(),
        duration_minutes: currentDuration || parseInt(duration, 10) || 30,
      });
      setRescheduleId(null);
      showAlert('Rescheduled', 'The new time was sent to the expert by email and WhatsApp. The join link is unchanged.');
      fetchAppointments();
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Could not reschedule the appointment');
    } finally {
      setLoading(false);
    }
  };

  const handleEndCall = async () => {
    if (activeSession) {
      try {
        const sessionId = activeSession.session_id || activeSession.id;
        await api.put(`/call-sessions/${sessionId}/end`);
      } catch (err) {
        console.error('Failed to end session', err);
      }
    }
    if (timerRef.current) clearInterval(timerRef.current);
    setActiveSession(null);
    setTimeLeft(null);
    showAlert('Call Ended', 'The expert consultation session has ended.');
  };

  const openCallInBrowser = () => {
    if (activeSession?.room_url && typeof window !== 'undefined') {
      window.open(activeSession.room_url, '_blank', 'noopener,noreferrer');
    }
  };

  const formatTime = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const isUrgent = timeLeft !== null && timeLeft < 120; // Less than 2 min

  const filteredExperts = experts.filter(e => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      (e.name && e.name.toLowerCase().includes(q)) ||
      (e.specialization && e.specialization.toLowerCase().includes(q)) ||
      (e.email && e.email.toLowerCase().includes(q))
    );
  });

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>
                {activeSession?.is_scheduled ? 'Appointment booked' : activeSession ? 'Expert Call Active' : 'Call an Expert'}
              </Text>
              <Text style={styles.subtitle}>Step {stepNumber}: {stepName}</Text>
            </View>
            {(!activeSession || activeSession.is_scheduled) && (
              <TouchableOpacity onPress={() => { setActiveSession(null); setTimeLeft(null); onClose(); }} style={styles.closeBtn}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            )}
          </View>

          {/* Active Call View */}
          {activeSession?.is_scheduled ? (
            <View style={styles.activeCallContainer}>
              <View style={styles.timerCard}>
                <Ionicons name="calendar-outline" size={24} color={COLORS.primary} />
                <Text style={[styles.timerText, { fontSize: 18 }]}>{formatAppointment(activeSession.scheduled_at)}</Text>
                <Text style={styles.timerLabel}>{activeSession.duration_minutes} min · same join link</Text>
              </View>
              <View style={styles.expertInfoCard}>
                <View style={styles.expertAvatar}>
                  <Ionicons name="person" size={24} color="#FFF" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.expertNameLarge}>{activeSession.expert_name || selectedExpert?.name}</Text>
                  <Text style={styles.expertSpecLarge}>Appointment notice sent</Text>
                </View>
              </View>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                {activeSession.notified_email && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#DCFCE7', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 }}>
                    <Ionicons name="checkmark-circle" size={14} color="#16A34A" />
                    <Text style={{ fontSize: 11, fontWeight: '600', color: '#16A34A' }}>Email Sent</Text>
                  </View>
                )}
                {activeSession.notified_whatsapp && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#DCFCE7', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 }}>
                    <Ionicons name="logo-whatsapp" size={14} color="#16A34A" />
                    <Text style={{ fontSize: 11, fontWeight: '600', color: '#16A34A' }}>WhatsApp Sent</Text>
                  </View>
                )}
              </View>
              {!!activeSession.google_calendar_link && (
                <TouchableOpacity
                  style={[styles.openBrowserBtn, { backgroundColor: '#1A73E8' }]}
                  onPress={() => {
                    if (typeof window !== 'undefined') window.open(activeSession.google_calendar_link, '_blank', 'noopener,noreferrer');
                  }}
                >
                  <Ionicons name="calendar-outline" size={18} color="#FFF" />
                  <Text style={styles.openBrowserBtnText}>
                    {activeSession.google_calendar_synced ? 'Open in Google Calendar' : 'Add to Google Calendar'}
                  </Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity style={styles.openBrowserBtn} onPress={openCallInBrowser}>
                <Ionicons name="open-outline" size={18} color="#FFF" />
                <Text style={styles.openBrowserBtnText}>Open meeting link</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.startCallBtn, { marginTop: 8 }]} onPress={() => { setActiveSession(null); fetchAppointments(); }}>
                <Text style={styles.startCallBtnText}>Done</Text>
              </TouchableOpacity>
            </View>
          ) : activeSession ? (
            <View style={styles.activeCallContainer}>
              {/* Timer */}
              <View style={[styles.timerCard, isUrgent && styles.timerCardUrgent]}>
                <Ionicons name="time-outline" size={24} color={isUrgent ? '#EF4444' : COLORS.primary} />
                <Text style={[styles.timerText, isUrgent && styles.timerTextUrgent]}>
                  {timeLeft !== null ? formatTime(timeLeft) : '--:--'}
                </Text>
                <Text style={styles.timerLabel}>remaining</Text>
              </View>

              {/* Expert info */}
              <View style={styles.expertInfoCard}>
                <View style={styles.expertAvatar}>
                  <Ionicons name="person" size={24} color="#FFF" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.expertNameLarge}>{selectedExpert?.name}</Text>
                  <Text style={styles.expertSpecLarge}>{selectedExpert?.specialization}</Text>
                </View>
                <View style={styles.callStatusBadge}>
                  <View style={styles.callStatusDot} />
                  <Text style={styles.callStatusText}>Live</Text>
                </View>
              </View>

              {/* Notification delivery badges */}
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                {activeSession.notified_email && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#DCFCE7', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 }}>
                    <Ionicons name="checkmark-circle" size={14} color="#16A34A" />
                    <Text style={{ fontSize: 11, fontWeight: '600', color: '#16A34A' }}>Email Sent</Text>
                  </View>
                )}
                {activeSession.notified_whatsapp && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#DCFCE7', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 }}>
                    <Ionicons name="logo-whatsapp" size={14} color="#16A34A" />
                    <Text style={{ fontSize: 11, fontWeight: '600', color: '#16A34A' }}>WhatsApp Sent</Text>
                  </View>
                )}
                {!activeSession.notified_email && !activeSession.notified_whatsapp && (
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#FEF3C7', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10 }}>
                    <Ionicons name="warning-outline" size={14} color="#D97706" />
                    <Text style={{ fontSize: 11, fontWeight: '600', color: '#D97706' }}>No contact info — share link manually</Text>
                  </View>
                )}
              </View>

              {/* Context shared */}
              <View style={styles.sharedContextCard}>
                <Ionicons name="document-text-outline" size={16} color={COLORS.primary} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.sharedContextTitle}>Shared Context</Text>
                  <Text style={styles.sharedContextText}>{decisionTitle} — Step {stepNumber}</Text>
                </View>
                <View style={styles.screenShareBadge}>
                  <Ionicons name="desktop-outline" size={12} color="#16A34A" />
                  <Text style={styles.screenShareText}>Screen Share</Text>
                </View>
              </View>

              {/* Open in browser button */}
              <TouchableOpacity style={styles.openBrowserBtn} onPress={openCallInBrowser}>
                <Ionicons name="open-outline" size={18} color="#FFF" />
                <Text style={styles.openBrowserBtnText}>Open Video Call in Browser</Text>
              </TouchableOpacity>
              <Text style={{ fontSize: 11, color: COLORS.textMuted, textAlign: 'center', marginTop: 4 }}>
                Join with audio, video & screen sharing enabled
              </Text>

              {/* WhatsApp Share Button */}
              {(activeSession.expert_phone || expertPhone) && (
                <TouchableOpacity
                  style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#25D366', borderRadius: 12, paddingVertical: 12 }}
                  onPress={() => {
                    const phone = (activeSession.expert_phone || expertPhone || '').replace(/[^0-9]/g, '');
                    const msg = `Hi ${selectedExpert?.name || 'Expert'},\n\nYour JELCOS AI consultation meeting is ready!\n\n🔗 Join here: ${activeSession.room_url}\n\nNo download needed — opens directly in your browser.`;
                    const url = `https://wa.me/${phone}?text=${encodeURIComponent(msg)}`;
                    if (typeof window !== 'undefined') window.open(url, '_blank');
                    else Linking.openURL(url).catch(() => {});
                  }}
                >
                  <Ionicons name="logo-whatsapp" size={18} color="#FFF" />
                  <Text style={{ fontSize: 14, fontWeight: '700', color: '#FFF' }}>Share via WhatsApp</Text>
                </TouchableOpacity>
              )}

              {/* End Call */}
              <TouchableOpacity style={styles.endCallBtn} onPress={handleEndCall}>
                <Ionicons name="call" size={20} color="#FFF" />
                <Text style={styles.endCallBtnText}>End Call</Text>
              </TouchableOpacity>
            </View>
          ) : (
            /* Setup View */
            <ScrollView contentContainerStyle={styles.setupContainer}>
              {/* Decision context */}
              <View style={styles.contextBanner}>
                <Ionicons name="information-circle" size={16} color={COLORS.primary} />
                <Text style={styles.contextBannerText}>
                  Consulting about: {decisionTitle}
                </Text>
              </View>

              <View style={styles.tabRow}>
                <TouchableOpacity
                  style={[styles.tab, panel === 'new' && styles.tabActive]}
                  onPress={() => setPanel('new')}
                >
                  <Text style={[styles.tabText, panel === 'new' && styles.tabTextActive]}>New meeting</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.tab, panel === 'history' && styles.tabActive]}
                  onPress={() => setPanel('history')}
                >
                  <Text style={[styles.tabText, panel === 'history' && styles.tabTextActive]}>
                    Meeting history{appointments.length ? ` (${appointments.length})` : ''}
                  </Text>
                </TouchableOpacity>
              </View>

              {panel === 'history' ? (
                appointments.length === 0 ? (
                  <Text style={styles.emptySubtext}>No meetings for this decision yet.</Text>
                ) : (
                  <>
                    {appointments.some((row) => meetingStatus(row) === 'upcoming') && (
                      <Text style={styles.sectionTitle}>Upcoming</Text>
                    )}
                    {appointments.filter((row) => meetingStatus(row) === 'upcoming').map((appt) => (
                      <View key={appt.id || appt.session_id} style={styles.expertCard}>
                        <View style={{ flex: 1, gap: 4 }}>
                          <Text style={styles.expertName}>{appt.expert_name}</Text>
                          <Text style={styles.expertSpec}>{formatAppointment(appt.scheduled_at)} · {appt.duration_minutes} min</Text>
                          {rescheduleId === (appt.id || appt.session_id) && (
                            <AppointmentCalendar value={rescheduleLocal} onChange={setRescheduleLocal} />
                          )}
                          <View style={{ flexDirection: 'row', gap: 8, marginTop: 4 }}>
                            {rescheduleId === (appt.id || appt.session_id) ? (
                              <TouchableOpacity onPress={() => saveReschedule(appt.id || appt.session_id, appt.duration_minutes)}>
                                <Text style={{ color: COLORS.primary, fontWeight: '700', fontSize: 13 }}>Save new time</Text>
                              </TouchableOpacity>
                            ) : (
                              <TouchableOpacity onPress={() => {
                                setRescheduleId(appt.id || appt.session_id);
                                setRescheduleLocal(localDateTimeValue(new Date(appt.scheduled_at)));
                              }}>
                                <Text style={{ color: COLORS.primary, fontWeight: '700', fontSize: 13 }}>Reschedule</Text>
                              </TouchableOpacity>
                            )}
                            <TouchableOpacity onPress={() => cancelAppointment(appt.id || appt.session_id)}>
                              <Text style={{ color: COLORS.error, fontWeight: '700', fontSize: 13 }}>Cancel</Text>
                            </TouchableOpacity>
                          </View>
                        </View>
                      </View>
                    ))}
                    {appointments.some((row) => meetingStatus(row) !== 'upcoming') && (
                      <Text style={styles.sectionTitle}>Earlier</Text>
                    )}
                    {appointments.filter((row) => meetingStatus(row) !== 'upcoming').map((appt) => (
                      <View key={`history-${appt.id || appt.session_id}`} style={styles.expertCard}>
                        <View style={{ flex: 1, gap: 4 }}>
                          <Text style={styles.expertName}>{appt.expert_name || 'Expert'}</Text>
                          <Text style={styles.expertSpec}>
                            {formatAppointment(appt.scheduled_at || appt.created_at)} · {appt.duration_minutes || 30} min
                          </Text>
                          <View style={[styles.historyPill, appt.status === 'cancelled' && styles.historyPillCancelled, appt.status === 'ended' && styles.historyPillDone]}>
                            <Text style={[styles.historyPillText, appt.status === 'cancelled' && styles.historyPillTextCancelled, appt.status === 'ended' && styles.historyPillTextDone]}>
                              {meetingStatus(appt)}
                            </Text>
                          </View>
                        </View>
                      </View>
                    ))}
                  </>
                )
              ) : (
              <>
              <Text style={styles.sectionTitle}>Meeting type</Text>
              <View style={styles.durationRow}>
                <TouchableOpacity
                  style={[styles.durationChip, meetingMode === 'now' && styles.durationChipActive]}
                  onPress={() => setMeetingMode('now')}
                >
                  <Text style={[styles.durationChipText, meetingMode === 'now' && styles.durationChipTextActive]}>Start now</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.durationChip, meetingMode === 'appointment' && styles.durationChipActive]}
                  onPress={() => setMeetingMode('appointment')}
                >
                  <Text style={[styles.durationChipText, meetingMode === 'appointment' && styles.durationChipTextActive]}>Book appointment</Text>
                </TouchableOpacity>
              </View>
              {meetingMode === 'appointment' && (
                <AppointmentCalendar
                  value={appointmentLocal}
                  onChange={setAppointmentLocal}
                  bookedDates={appointments
                    .filter((row) => meetingStatus(row) === 'upcoming' && row.scheduled_at)
                    .map((row) => localDateTimeValue(new Date(row.scheduled_at)).slice(0, 10))}
                />
              )}

              {/* Expert Selection */}
              <View style={styles.sectionHeaderRow}>
                <Text style={styles.sectionTitle}>Select Expert</Text>
                {experts.length > 0 && (
                  <Text style={styles.expertCountBadge}>{filteredExperts.length} available</Text>
                )}
              </View>

              {experts.length > 3 && (
                <View style={styles.searchWrap}>
                  <Ionicons name="search" size={16} color={COLORS.textMuted} />
                  <TextInput
                    style={styles.searchInput}
                    placeholder="Search by name or specialization..."
                    placeholderTextColor={COLORS.textMuted}
                    value={searchQuery}
                    onChangeText={setSearchQuery}
                  />
                  {searchQuery.length > 0 && (
                    <TouchableOpacity onPress={() => setSearchQuery('')} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                      <Ionicons name="close-circle" size={16} color={COLORS.textMuted} />
                    </TouchableOpacity>
                  )}
                </View>
              )}

              {expertsLoading ? (
                <View style={styles.loadingExperts}>
                  <ActivityIndicator size="small" color={COLORS.primary} />
                  <Text style={styles.loadingText}>Loading experts...</Text>
                </View>
              ) : filteredExperts.length === 0 ? (
                <View style={styles.emptyExperts}>
                  <Ionicons name="people-outline" size={32} color={COLORS.textMuted} />
                  <Text style={styles.emptyText}>
                    {searchQuery.trim() ? `No experts matching "${searchQuery}"` : 'No experts available'}
                  </Text>
                  <Text style={styles.emptySubtext}>
                    {searchQuery.trim()
                      ? 'Try another search term'
                      : 'Admins can add experts in Profile → Authorized Experts'}
                  </Text>
                </View>
              ) : (
                filteredExperts.map((expert) => (
                  <TouchableOpacity
                    key={expert.id}
                    style={[styles.expertCard, selectedExpert?.id === expert.id && styles.expertCardSelected]}
                    onPress={() => {
                      setSelectedExpert(expert);
                      setExpertPhone(expert.whatsapp || expert.phone || '');
                      setExpertEmail(expert.email || '');
                    }}
                  >
                    <View style={[styles.expertDot, selectedExpert?.id === expert.id && styles.expertDotSelected]}>
                      {selectedExpert?.id === expert.id ? (
                        <Ionicons name="checkmark" size={14} color="#FFF" />
                      ) : (
                        <Ionicons name="person-outline" size={14} color={COLORS.textMuted} />
                      )}
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.expertName}>{expert.name}</Text>
                      <Text style={styles.expertSpec}>{expert.specialization || expert.email}</Text>
                    </View>
                  </TouchableOpacity>
                ))
              )}

              {/* Duration */}
              <Text style={styles.sectionTitle}>Call Duration</Text>
              <View style={styles.durationRow}>
                {[15, 30, 45, 60].map((d) => (
                  <TouchableOpacity
                    key={d}
                    style={[styles.durationChip, duration === String(d) && styles.durationChipActive]}
                    onPress={() => setDuration(String(d))}
                  >
                    <Text style={[styles.durationChipText, duration === String(d) && styles.durationChipTextActive]}>
                      {d} min
                    </Text>
                  </TouchableOpacity>
                ))}
                <View style={styles.customDurationWrap}>
                  <TextInput
                    style={styles.customDurationInput}
                    value={duration}
                    onChangeText={setDuration}
                    keyboardType="numeric"
                    maxLength={3}
                  />
                  <Text style={styles.customDurationLabel}>min</Text>
                </View>
              </View>
              {callConfig && (
                <Text style={styles.durationHint}>
                  {callConfig.min_duration}-{callConfig.max_duration} min allowed by admin
                </Text>
              )}

              {/* Features */}
              <View style={styles.featuresRow}>
                <View style={styles.featureChip}>
                  <Ionicons name="videocam" size={14} color={COLORS.primary} />
                  <Text style={styles.featureText}>Video</Text>
                </View>
                <View style={styles.featureChip}>
                  <Ionicons name="mic" size={14} color={COLORS.primary} />
                  <Text style={styles.featureText}>Audio</Text>
                </View>
                <View style={styles.featureChip}>
                  <Ionicons name="desktop-outline" size={14} color={COLORS.primary} />
                  <Text style={styles.featureText}>Screen Share</Text>
                </View>
                <View style={styles.featureChip}>
                  <Ionicons name="time-outline" size={14} color={COLORS.primary} />
                  <Text style={styles.featureText}>Auto-End</Text>
                </View>
              </View>

              {/* Expert Contact — for WhatsApp & Email notifications */}
              {selectedExpert && (
                <View style={{ gap: 8, marginTop: 4 }}>
                  <Text style={styles.sectionTitle}>Expert Notification Details</Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 }}>
                    <Ionicons name="logo-whatsapp" size={16} color="#25D366" />
                    <TextInput
                      style={{ flex: 1, fontSize: 13, color: COLORS.textPrimary, padding: 0 }}
                      placeholder="WhatsApp number (e.g. 919876543210)"
                      placeholderTextColor={COLORS.textMuted}
                      value={expertPhone}
                      onChangeText={setExpertPhone}
                      keyboardType="phone-pad"
                    />
                  </View>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8 }}>
                    <Ionicons name="mail-outline" size={16} color={COLORS.primary} />
                    <TextInput
                      style={{ flex: 1, fontSize: 13, color: COLORS.textPrimary, padding: 0 }}
                      placeholder="Expert email"
                      placeholderTextColor={COLORS.textMuted}
                      value={expertEmail}
                      onChangeText={setExpertEmail}
                      keyboardType="email-address"
                      autoCapitalize="none"
                    />
                  </View>
                  <Text style={{ fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic' }}>
                    Meeting link, date & joining instructions will be sent automatically to the expert via email and WhatsApp.
                  </Text>
                </View>
              )}

              {/* Start Call Button */}
              <TouchableOpacity
                style={[styles.startCallBtn, (!selectedExpert || loading) && styles.startCallBtnDisabled]}
                onPress={startCall}
                disabled={!selectedExpert || loading}
              >
                {loading ? (
                  <ActivityIndicator size="small" color="#FFF" />
                ) : (
                  <Ionicons name="videocam" size={22} color="#FFF" />
                )}
                <Text style={styles.startCallBtnText}>
                  {loading ? 'Setting up...' : meetingMode === 'appointment' ? 'Book appointment' : 'Start Call'}
                </Text>
              </TouchableOpacity>
              </>
              )}
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  container: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '90%' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  title: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 12, color: COLORS.textMuted },
  closeBtn: { padding: 4 },
  // Active call
  activeCallContainer: { padding: 20, gap: 16 },
  timerCard: { alignItems: 'center', backgroundColor: '#F5F3FF', borderRadius: 16, paddingVertical: 20, gap: 4 },
  timerCardUrgent: { backgroundColor: '#FEE2E2' },
  timerText: { fontSize: 40, fontWeight: '800', color: COLORS.primary, fontVariant: ['tabular-nums'] },
  timerTextUrgent: { color: '#EF4444' },
  timerLabel: { fontSize: 12, color: COLORS.textMuted },
  expertInfoCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#F8FAFC', borderRadius: 12, padding: 14 },
  expertAvatar: { width: 44, height: 44, borderRadius: 22, backgroundColor: COLORS.primary, alignItems: 'center', justifyContent: 'center' },
  expertNameLarge: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  expertSpecLarge: { fontSize: 12, color: COLORS.textMuted },
  callStatusBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, backgroundColor: '#DCFCE7', borderRadius: 10 },
  callStatusDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#16A34A' },
  callStatusText: { fontSize: 11, fontWeight: '600', color: '#16A34A' },
  sharedContextCard: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F5F3FF', borderRadius: 10, padding: 12 },
  sharedContextTitle: { fontSize: 11, fontWeight: '600', color: COLORS.primary },
  sharedContextText: { fontSize: 12, color: COLORS.textSecondary },
  screenShareBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#DCFCE7', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  screenShareText: { fontSize: 10, fontWeight: '600', color: '#16A34A' },
  openBrowserBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#3B82F6', borderRadius: 12, paddingVertical: 14 },
  openBrowserBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  endCallBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#EF4444', borderRadius: 12, paddingVertical: 14 },
  endCallBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  // Setup
  setupContainer: { padding: 16, paddingBottom: 32, gap: 12 },
  contextBanner: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F5F3FF', borderRadius: 10, padding: 12 },
  contextBannerText: { fontSize: 13, color: COLORS.primary, fontWeight: '500', flex: 1 },
  sectionHeaderRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: '#16132A', letterSpacing: -0.3, fontFamily: DISPLAY_FONT },
  historyPill: { alignSelf: 'flex-start', backgroundColor: '#F5F3FF', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3 },
  historyPillCancelled: { backgroundColor: '#FEE2E2' },
  historyPillDone: { backgroundColor: '#D1FAE5' },
  historyPillText: { fontSize: 11, fontWeight: '700', color: COLORS.primary },
  historyPillTextCancelled: { color: COLORS.error },
  historyPillTextDone: { color: '#047857' },
  expertCountBadge: { fontSize: 12, fontWeight: '600', color: COLORS.primary, backgroundColor: '#F5F3FF', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  searchWrap: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, gap: 8 },
  searchInput: { flex: 1, fontSize: 13, color: COLORS.textPrimary, padding: 0 },
  loadingExperts: { alignItems: 'center', paddingVertical: 24, gap: 8 },
  loadingText: { fontSize: 12, color: COLORS.textMuted },
  emptyExperts: { alignItems: 'center', paddingVertical: 24, gap: 6 },
  emptyText: { fontSize: 14, color: COLORS.textMuted },
  emptySubtext: { fontSize: 11, color: COLORS.textMuted, textAlign: 'center' },
  expertCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, borderWidth: 1.5, borderColor: COLORS.border },
  expertCardSelected: { borderColor: COLORS.primary, backgroundColor: '#F5F3FF' },
  expertDot: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center' },
  expertDotSelected: { backgroundColor: COLORS.primary },
  expertName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  expertSpec: { fontSize: 12, color: COLORS.textMuted },
  tabRow: { flexDirection: 'row', gap: 8 },
  tab: { flex: 1, alignItems: 'center', paddingVertical: 10, borderRadius: 12, backgroundColor: '#F1F5F9', borderWidth: 1.5, borderColor: COLORS.border },
  tabActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  tabText: { fontSize: 13, fontWeight: '700', color: COLORS.textSecondary },
  tabTextActive: { color: COLORS.white },
  durationRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  durationChip: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 10, backgroundColor: '#F1F5F9', borderWidth: 1.5, borderColor: COLORS.border },
  durationChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  durationChipText: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  durationChipTextActive: { color: '#FFF' },
  customDurationWrap: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  customDurationInput: { width: 50, height: 38, borderWidth: 1.5, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 8, fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, textAlign: 'center' },
  customDurationLabel: { fontSize: 12, color: COLORS.textMuted },
  durationHint: { fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic' },
  featuresRow: { flexDirection: 'row', gap: 8, justifyContent: 'center' },
  featureChip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#F5F3FF', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 10 },
  featureText: { fontSize: 11, fontWeight: '600', color: COLORS.primary },
  startCallBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#16A34A', borderRadius: 14, paddingVertical: 16, marginTop: 4 },
  startCallBtnDisabled: { backgroundColor: '#94A3B8' },
  startCallBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
