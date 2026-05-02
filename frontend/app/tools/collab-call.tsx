import React, { useState, useEffect, useRef, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator,
  Platform, Linking, Dimensions,
} from 'react-native';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

// Conditionally import WebView for native platforms
let WebView: any = null;
if (Platform.OS !== 'web') {
  try {
    WebView = require('react-native-webview').default;
  } catch (e) {}
}

export default function CollabCallScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const sessionId = params.sessionId as string;

  const [loading, setLoading] = useState(true);
  const [callData, setCallData] = useState<any>(null);
  const [sessionData, setSessionData] = useState<any>(null);
  const [showParticipants, setShowParticipants] = useState(false);
  const [screenSharing, setScreenSharing] = useState(false);
  const [ending, setEnding] = useState(false);
  const pollRef = useRef<any>(null);

  const startOrGetCall = async () => {
    try {
      const [callRes, sessionRes] = await Promise.all([
        api.post(`/collaboration/sessions/${sessionId}/start-call`),
        api.get(`/collaboration/sessions/${sessionId}`).catch(() => ({ data: null })),
      ]);
      setCallData(callRes.data);
      setSessionData(sessionRes.data);

      // Also register as joined
      await api.post(`/collaboration/sessions/${sessionId}/join-call`).catch(() => {});
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to start call');
      router.back();
    } finally {
      setLoading(false);
    }
  };

  const pollCallStatus = async () => {
    try {
      const res = await api.get(`/collaboration/sessions/${sessionId}/call-status`);
      if (res.data?.has_call) {
        setCallData((prev: any) => ({
          ...prev,
          participants_joined: res.data.participants_joined,
          screen_sharing_by: res.data.screen_sharing_by,
          status: res.data.status,
        }));
        if (res.data.status === 'ended') {
          showAlert('Call Ended', 'The host has ended the call.');
          router.back();
        }
      }
    } catch (e) {}
  };

  useEffect(() => {
    startOrGetCall();
    pollRef.current = setInterval(pollCallStatus, 8000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleEndCall = async () => {
    setEnding(true);
    try {
      await api.post(`/collaboration/sessions/${sessionId}/end-call`);
      showAlert('Call Ended', 'The video call has been ended for all participants.');
      router.back();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to end call');
    } finally {
      setEnding(false);
    }
  };

  const handleScreenShare = async () => {
    const newState = !screenSharing;
    try {
      await api.post(`/collaboration/sessions/${sessionId}/screen-share`, { sharing: newState });
      setScreenSharing(newState);
    } catch (e) {}
  };

  const openInBrowser = () => {
    if (callData?.room_url) Linking.openURL(callData.room_url);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#059669" />
          <Text style={styles.loadingText}>Starting video call...</Text>
          <Text style={styles.loadingHint}>Connecting to Jitsi Meet</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!callData) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <Ionicons name="videocam-off" size={48} color="#DC2626" />
          <Text style={styles.loadingText}>Unable to start call</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => router.back()}>
            <Text style={styles.retryBtnText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const jitsiUrl = callData.room_url
    ? `${callData.room_url}#config.prejoinPageEnabled=false&config.startWithAudioMuted=false&config.startWithVideoMuted=false&config.toolbarButtons=["microphone","camera","desktop","chat","raisehand","participants-pane","tileview","hangup"]&interfaceConfig.TOOLBAR_BUTTONS=["microphone","camera","desktop","chat","raisehand","participants-pane","tileview","hangup"]&interfaceConfig.SHOW_JITSI_WATERMARK=false&interfaceConfig.SHOW_BRAND_WATERMARK=false`
    : '';

  const participantCount = callData.participants_joined?.length || 0;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Top Bar */}
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} style={styles.topBtn}>
          <Ionicons name="arrow-back" size={20} color="#FFF" />
        </TouchableOpacity>

        <View style={styles.topInfo}>
          <View style={styles.liveDot} />
          <Text style={styles.topTitle} numberOfLines={1}>
            {sessionData?.title || 'Live Session'}
          </Text>
        </View>

        <TouchableOpacity style={styles.topBtn} onPress={() => setShowParticipants(!showParticipants)}>
          <Ionicons name="people" size={18} color="#FFF" />
          <View style={styles.participantCount}>
            <Text style={styles.participantCountText}>{participantCount}</Text>
          </View>
        </TouchableOpacity>
      </View>

      {/* Participants Panel */}
      {showParticipants && (
        <View style={styles.participantsPanel}>
          <Text style={styles.panelTitle}>Participants ({participantCount})</Text>
          {(callData.participants_joined || []).map((p: any, i: number) => (
            <View key={i} style={styles.participantRow}>
              <View style={styles.participantAvatar}>
                <Text style={styles.participantAvatarText}>{(p.name || '?')[0].toUpperCase()}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.participantName}>{p.name}</Text>
                <Text style={styles.participantRole}>{p.role === 'host' ? 'Host' : 'Participant'}</Text>
              </View>
              {p.role === 'host' && <Ionicons name="star" size={14} color="#F59E0B" />}
            </View>
          ))}
          {callData.screen_sharing_by && (
            <View style={styles.sharingInfo}>
              <Ionicons name="laptop" size={14} color="#3B82F6" />
              <Text style={styles.sharingText}>{callData.screen_sharing_by} is sharing screen</Text>
            </View>
          )}
        </View>
      )}

      {/* Session Context Banner */}
      {sessionData && (
        <View style={styles.contextBanner}>
          <Ionicons name="git-network" size={14} color="#7C3AED" />
          <Text style={styles.contextText} numberOfLines={1}>
            {sessionData.decision_mode?.name || 'Collaboration'} • {sessionData.module_type?.replace('_', ' ')} • {(sessionData.participants || []).length} invited
          </Text>
          {sessionData.mode_config_override && (
            <View style={styles.overrideBadge}>
              <Text style={styles.overrideBadgeText}>Custom Config</Text>
            </View>
          )}
        </View>
      )}

      {/* Video Area */}
      <View style={styles.videoContainer}>
        {Platform.OS === 'web' ? (
          // Web: Use iframe
          <View style={styles.webVideoWrapper}>
            <iframe
              src={jitsiUrl}
              style={{ width: '100%', height: '100%', border: 'none', borderRadius: 8 } as any}
              allow="camera; microphone; display-capture; autoplay; clipboard-write"
              allowFullScreen
            />
          </View>
        ) : WebView ? (
          // Native: Use WebView
          <WebView
            source={{ uri: jitsiUrl }}
            style={styles.webview}
            javaScriptEnabled
            domStorageEnabled
            mediaPlaybackRequiresUserAction={false}
            allowsInlineMediaPlayback
            allowsFullscreenVideo
            startInLoadingState
            renderLoading={() => (
              <View style={styles.webviewLoading}>
                <ActivityIndicator size="large" color="#059669" />
                <Text style={styles.loadingHint}>Loading Jitsi Meet...</Text>
              </View>
            )}
          />
        ) : (
          // Fallback: Open in browser
          <View style={styles.fallbackContainer}>
            <Ionicons name="videocam" size={64} color="#059669" />
            <Text style={styles.fallbackTitle}>Video Call Ready</Text>
            <Text style={styles.fallbackDesc}>
              Room: {callData.room_id}
            </Text>
            <TouchableOpacity style={styles.openBrowserBtn} onPress={openInBrowser}>
              <Ionicons name="open-outline" size={18} color="#FFF" />
              <Text style={styles.openBrowserText}>Open in Browser</Text>
            </TouchableOpacity>
            <Text style={styles.fallbackHint}>
              Share this link with participants:{'\n'}{callData.room_url}
            </Text>
          </View>
        )}
      </View>

      {/* Bottom Controls */}
      <View style={styles.bottomControls}>
        <TouchableOpacity style={[styles.controlBtn, screenSharing && styles.controlBtnActive]}
          onPress={handleScreenShare}>
          <Ionicons name="laptop-outline" size={20} color={screenSharing ? '#FFF' : '#374151'} />
          <Text style={[styles.controlLabel, screenSharing && { color: '#FFF' }]}>
            {screenSharing ? 'Stop Share' : 'Share Screen'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.controlBtn} onPress={openInBrowser}>
          <Ionicons name="open-outline" size={20} color="#374151" />
          <Text style={styles.controlLabel}>Browser</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.controlBtn}
          onPress={() => setShowParticipants(!showParticipants)}>
          <Ionicons name="people-outline" size={20} color="#374151" />
          <Text style={styles.controlLabel}>People</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.controlBtn, styles.endCallBtn]}
          onPress={handleEndCall} disabled={ending}>
          {ending ? <ActivityIndicator color="#FFF" size="small" /> : (
            <>
              <Ionicons name="call" size={20} color="#FFF" style={{ transform: [{ rotate: '135deg' }] }} />
              <Text style={[styles.controlLabel, { color: '#FFF' }]}>End</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111827' },

  // Loading
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  loadingHint: { fontSize: 12, color: '#9CA3AF' },
  retryBtn: { paddingHorizontal: 24, paddingVertical: 10, borderRadius: 8, backgroundColor: '#374151', marginTop: 12 },
  retryBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },

  // Top Bar
  topBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 8, backgroundColor: '#1F2937', gap: 8 },
  topBtn: { width: 36, height: 36, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.1)', justifyContent: 'center', alignItems: 'center' },
  topInfo: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 8 },
  liveDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#EF4444' },
  topTitle: { fontSize: 14, fontWeight: '700', color: '#FFF', flex: 1 },
  participantCount: { position: 'absolute', top: -4, right: -4, backgroundColor: '#059669', borderRadius: 8, minWidth: 16, height: 16, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 4 },
  participantCountText: { fontSize: 9, fontWeight: '800', color: '#FFF' },

  // Participants Panel
  participantsPanel: { backgroundColor: '#1F2937', paddingHorizontal: 16, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: '#374151' },
  panelTitle: { fontSize: 13, fontWeight: '700', color: '#D1D5DB', marginBottom: 8 },
  participantRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 },
  participantAvatar: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#7C3AED', justifyContent: 'center', alignItems: 'center' },
  participantAvatarText: { fontSize: 11, fontWeight: '700', color: '#FFF' },
  participantName: { fontSize: 12, fontWeight: '600', color: '#E5E7EB' },
  participantRole: { fontSize: 10, color: '#9CA3AF' },
  sharingInfo: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, padding: 8, backgroundColor: '#172554', borderRadius: 8 },
  sharingText: { fontSize: 11, color: '#93C5FD' },

  // Context Banner
  contextBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingVertical: 8, backgroundColor: '#F5F3FF' },
  contextText: { fontSize: 11, color: '#7C3AED', flex: 1, fontWeight: '500' },
  overrideBadge: { backgroundColor: '#EDE9FE', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  overrideBadgeText: { fontSize: 9, fontWeight: '600', color: '#7C3AED' },

  // Video
  videoContainer: { flex: 1, backgroundColor: '#000' },
  webVideoWrapper: { flex: 1, overflow: 'hidden' },
  webview: { flex: 1 },
  webviewLoading: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, justifyContent: 'center', alignItems: 'center', backgroundColor: '#111827' },

  // Fallback
  fallbackContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, gap: 12 },
  fallbackTitle: { fontSize: 20, fontWeight: '800', color: '#FFF' },
  fallbackDesc: { fontSize: 13, color: '#9CA3AF' },
  openBrowserBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#059669', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 12, marginTop: 8 },
  openBrowserText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  fallbackHint: { fontSize: 11, color: '#6B7280', textAlign: 'center', marginTop: 12, lineHeight: 18 },

  // Bottom Controls
  bottomControls: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around', paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#1F2937', borderTopWidth: 1, borderTopColor: '#374151' },
  controlBtn: { alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8, paddingHorizontal: 14, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.08)' },
  controlBtnActive: { backgroundColor: '#3B82F6' },
  controlLabel: { fontSize: 10, fontWeight: '600', color: '#9CA3AF' },
  endCallBtn: { backgroundColor: '#DC2626', paddingHorizontal: 20 },
});
