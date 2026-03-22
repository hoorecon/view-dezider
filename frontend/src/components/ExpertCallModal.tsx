import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
  ScrollView,
  Modal,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { COLORS } from '../constants/colors';

interface Expert {
  id: string;
  name: string;
  email: string;
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
  const [loading, setLoading] = useState(false);
  const [selectedExpert, setSelectedExpert] = useState<Expert | null>(null);
  const [duration, setDuration] = useState('30');
  const [callConfig, setCallConfig] = useState<any>(null);
  const [activeSession, setActiveSession] = useState<any>(null);
  const [timeLeft, setTimeLeft] = useState<number | null>(null);
  const timerRef = useRef<any>(null);

  useEffect(() => {
    if (visible) {
      fetchExperts();
      fetchCallConfig();
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
    try {
      const token = await AsyncStorage.getItem('session_token');
      const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
      const resp = await fetch(`${baseUrl}/api/experts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await resp.json();
      setExperts(data || []);
    } catch (err) {
      console.error('Failed to fetch experts');
    }
  };

  const fetchCallConfig = async () => {
    try {
      const token = await AsyncStorage.getItem('session_token');
      const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
      const resp = await fetch(`${baseUrl}/api/call-config`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await resp.json();
      setCallConfig(data);
      setDuration(String(data.default_duration || 30));
    } catch (err) {
      console.error('Failed to fetch call config');
    }
  };

  const startCall = async () => {
    if (!selectedExpert) {
      Alert.alert('Select Expert', 'Please select an expert to call.');
      return;
    }
    const dur = parseInt(duration) || 30;
    const minDur = callConfig?.min_duration || 5;
    const maxDur = callConfig?.max_duration || 120;
    if (dur < minDur || dur > maxDur) {
      Alert.alert('Invalid Duration', `Duration must be between ${minDur} and ${maxDur} minutes.`);
      return;
    }
    setLoading(true);
    try {
      const token = await AsyncStorage.getItem('session_token');
      const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
      const resp = await fetch(`${baseUrl}/api/call-sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          expert_id: selectedExpert.id,
          decision_id: decisionId,
          step_number: stepNumber,
          step_name: stepName,
          duration_minutes: dur,
          decision_title: decisionTitle,
        }),
      });
      const data = await resp.json();
      if (data.room_url) {
        setActiveSession(data);
        setTimeLeft(dur * 60);
      } else {
        Alert.alert('Error', data.detail || 'Failed to create call session');
      }
    } catch (err) {
      Alert.alert('Error', 'Failed to start call');
    } finally {
      setLoading(false);
    }
  };

  const handleEndCall = async () => {
    if (activeSession) {
      try {
        const token = await AsyncStorage.getItem('session_token');
        const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
        await fetch(`${baseUrl}/api/call-sessions/${activeSession.session_id}/end`, {
          method: 'PUT',
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch (err) {
        console.error('Failed to end session');
      }
    }
    if (timerRef.current) clearInterval(timerRef.current);
    setActiveSession(null);
    setTimeLeft(null);
    Alert.alert('Call Ended', 'The expert consultation session has ended.');
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

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>
                {activeSession ? 'Expert Call Active' : 'Call an Expert'}
              </Text>
              <Text style={styles.subtitle}>Step {stepNumber}: {stepName}</Text>
            </View>
            {!activeSession && (
              <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            )}
          </View>

          {/* Active Call View */}
          {activeSession ? (
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

              {/* Expert Selection */}
              <Text style={styles.sectionTitle}>Select Expert</Text>
              {experts.length === 0 ? (
                <View style={styles.emptyExperts}>
                  <Ionicons name="people-outline" size={32} color={COLORS.textMuted} />
                  <Text style={styles.emptyText}>No experts available</Text>
                  <Text style={styles.emptySubtext}>Admins can add experts in Profile → Authorized Experts</Text>
                </View>
              ) : (
                experts.map((expert) => (
                  <TouchableOpacity
                    key={expert.id}
                    style={[styles.expertCard, selectedExpert?.id === expert.id && styles.expertCardSelected]}
                    onPress={() => setSelectedExpert(expert)}
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
                  {loading ? 'Setting up call...' : 'Start Call'}
                </Text>
              </TouchableOpacity>
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
  sectionTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginTop: 4 },
  emptyExperts: { alignItems: 'center', paddingVertical: 24, gap: 6 },
  emptyText: { fontSize: 14, color: COLORS.textMuted },
  emptySubtext: { fontSize: 11, color: COLORS.textMuted, textAlign: 'center' },
  expertCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, borderWidth: 1.5, borderColor: COLORS.border },
  expertCardSelected: { borderColor: COLORS.primary, backgroundColor: '#F5F3FF' },
  expertDot: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center' },
  expertDotSelected: { backgroundColor: COLORS.primary },
  expertName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  expertSpec: { fontSize: 12, color: COLORS.textMuted },
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
