import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  useAudioRecorder,
  RecordingPresets,
  AudioModule,
  setAudioModeAsync,
} from 'expo-audio';
import api from '../utils/api';

export interface VoiceSavedAudio {
  audio_id: string;
  rel_path: string;
  ext: string;
  size_bytes: number;
  duration_sec?: number;
  credits_charged: number;
  retention_days: number;
  field: string;
}

interface VoiceInputProps {
  /** Backing session id (Conflict-Breaker / EG-Trap session). */
  sessionId: string;
  /** Field name being voiced (e.g. "about", "desired_result"). */
  field: string;
  /** Called when the user picks "Transcribe to text". */
  onTranscribed?: (text: string) => void;
  /** Called when the user picks "Save as audio" and the upload completes. */
  onAudioSaved?: (audio: VoiceSavedAudio) => void;
  /** Disable interactions. */
  disabled?: boolean;
  /** Accent color for the mic button. */
  color?: string;
  /**
   * Endpoint scheme:
   *   - 'eg-trap'         : /emotional-gatekeeper/trap/{sessionId}/voice
   *                          (legacy transcribe-only flow)
   *   - 'conflict-breaker': /conflict-breaker/sessions/{sessionId}/audio/...
   *                          (offers BOTH transcribe & save-audio)
   * Default: 'eg-trap' (legacy auto-transcribe — used by Emotional Gatekeeper).
   */
  module?: 'eg-trap' | 'conflict-breaker';
}

type Phase = 'idle' | 'recording' | 'review' | 'transcribing' | 'saving';

/**
 * VoiceInput
 * ──────────
 * Tap the mic chip to start recording. Tap again to stop. Then the user picks
 * one of two intuitive actions:
 *   📝  Transcribe to Text — runs Whisper, fills the field with English text
 *   💾  Save as Audio       — uploads the raw clip to disk, charges a tiny
 *                              metered storage fee from the AI wallet
 *
 * If `module === 'eg-trap'` the behaviour is locked to legacy auto-transcribe
 * (used by the Emotional Gatekeeper "Trap" screens — unchanged).
 */
export const VoiceInput: React.FC<VoiceInputProps> = ({
  sessionId,
  field,
  onTranscribed,
  onAudioSaved,
  disabled = false,
  color = '#003087',
  module = 'eg-trap',
}) => {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const [phase, setPhase] = useState<Phase>('idle');
  const [pendingUri, setPendingUri] = useState<string | null>(null);
  const [pendingBytes, setPendingBytes] = useState<number>(0);
  const [estimate, setEstimate] = useState<number | null>(null); // credits
  const [estimateDays, setEstimateDays] = useState<number>(90);
  const startMsRef = useRef<number>(0);

  // Clean up any stale audio session when unmounting mid-record.
  useEffect(() => {
    return () => {
      try {
        // best-effort: stop if still recording
        if (phase === 'recording') {
          recorder.stop().catch(() => {});
        }
      } catch {}
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startRecording = async () => {
    try {
      const permission = await AudioModule.requestRecordingPermissionsAsync();
      if (!permission.granted) {
        alert('Microphone permission is required for voice input.');
        return;
      }

      await setAudioModeAsync({
        allowsRecording: true,
        playsInSilentMode: true,
      });

      await recorder.prepareToRecordAsync();
      recorder.record();
      startMsRef.current = Date.now();
      setPendingUri(null);
      setPendingBytes(0);
      setEstimate(null);
      setPhase('recording');
    } catch (err) {
      console.error('Failed to start recording:', err);
      alert('Failed to start recording. Please try again.');
    }
  };

  const stopRecording = async () => {
    try {
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) {
        setPhase('idle');
        alert('Recording failed. Please try again.');
        return;
      }

      // For 'eg-trap' keep the legacy auto-transcribe behaviour.
      if (module === 'eg-trap') {
        await transcribeViaLegacy(uri);
        return;
      }

      // Inspect blob size for estimate (web). On native we approximate via
      // duration × 8KB/sec.
      let bytes = 0;
      try {
        if (Platform.OS === 'web') {
          const blob = await (await fetch(uri)).blob();
          bytes = blob.size;
        } else {
          const elapsed = Math.max(1, (Date.now() - startMsRef.current) / 1000);
          bytes = Math.round(elapsed * 8 * 1024); // 8KB/s rough estimate
        }
      } catch {
        bytes = 0;
      }

      setPendingUri(uri);
      setPendingBytes(bytes);
      setPhase('review');

      if (bytes > 0) {
        try {
          const res = await api.get('/conflict-breaker/audio/estimate', {
            params: { bytes },
          });
          setEstimate(Number(res.data?.credits ?? 0));
          setEstimateDays(Number(res.data?.retention_days ?? 90));
        } catch {}
      }
    } catch (err) {
      console.error('stop recording err', err);
      setPhase('idle');
    }
  };

  // ─── Legacy EG-Trap transcribe flow (unchanged) ─────────────────────────
  const transcribeViaLegacy = async (uri: string) => {
    setPhase('transcribing');
    try {
      const formData = new FormData();
      if (Platform.OS === 'web') {
        const blob = await (await fetch(uri)).blob();
        formData.append('audio', blob, 'recording.webm');
      } else {
        formData.append('audio', {
          uri,
          type: 'audio/webm',
          name: 'recording.webm',
        } as any);
      }
      formData.append('field', field);
      const result = await api.post(
        `/emotional-gatekeeper/trap/${sessionId}/voice`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 45000 },
      );
      if (result.data?.transcribed_text && onTranscribed) {
        onTranscribed(result.data.transcribed_text);
      } else {
        alert('Could not transcribe audio. Please type instead.');
      }
    } catch {
      alert('Transcription failed. Please type instead.');
    } finally {
      setPhase('idle');
    }
  };

  // ─── Conflict-Breaker: Transcribe ───────────────────────────────────────
  const doTranscribe = async () => {
    if (!pendingUri) return;
    setPhase('transcribing');
    try {
      const formData = new FormData();
      if (Platform.OS === 'web') {
        const blob = await (await fetch(pendingUri)).blob();
        formData.append('audio', blob, 'recording.webm');
      } else {
        formData.append('audio', {
          uri: pendingUri,
          type: 'audio/webm',
          name: 'recording.webm',
        } as any);
      }
      formData.append('field', field);
      const result = await api.post(
        `/conflict-breaker/sessions/${sessionId}/audio/transcribe`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 45000 },
      );
      if (result.data?.transcribed_text && onTranscribed) {
        onTranscribed(result.data.transcribed_text);
      } else {
        alert('Empty transcription. Please try again or type instead.');
      }
      resetReview();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Transcription failed.';
      alert(msg);
      setPhase('review');
    }
  };

  // ─── Conflict-Breaker: Save raw audio ───────────────────────────────────
  const doSaveAudio = async () => {
    if (!pendingUri) return;
    setPhase('saving');
    try {
      const elapsed = Math.max(1, (Date.now() - startMsRef.current) / 1000);
      const formData = new FormData();
      if (Platform.OS === 'web') {
        const blob = await (await fetch(pendingUri)).blob();
        formData.append('audio', blob, 'recording.webm');
      } else {
        formData.append('audio', {
          uri: pendingUri,
          type: 'audio/webm',
          name: 'recording.webm',
        } as any);
      }
      formData.append('field', field);
      formData.append('duration_sec', String(Math.round(elapsed)));
      const result = await api.post(
        `/conflict-breaker/sessions/${sessionId}/audio/upload`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 },
      );
      if (result.data?.audio_id && onAudioSaved) {
        onAudioSaved({
          audio_id: result.data.audio_id,
          rel_path: result.data.rel_path,
          ext: result.data.ext,
          size_bytes: result.data.size_bytes,
          duration_sec: result.data.duration_sec,
          credits_charged: result.data.credits_charged,
          retention_days: result.data.retention_days,
          field: result.data.field,
        });
      }
      resetReview();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Audio save failed.';
      alert(msg);
      setPhase('review');
    }
  };

  const resetReview = () => {
    setPendingUri(null);
    setPendingBytes(0);
    setEstimate(null);
    setPhase('idle');
  };

  // ───────────────────────────── render ─────────────────────────────
  if (phase === 'transcribing') {
    return (
      <View style={[styles.statusChip, { borderColor: color }]}>
        <ActivityIndicator size="small" color={color} />
        <Text style={[styles.statusText, { color }]}>Transcribing…</Text>
      </View>
    );
  }
  if (phase === 'saving') {
    return (
      <View style={[styles.statusChip, { borderColor: color }]}>
        <ActivityIndicator size="small" color={color} />
        <Text style={[styles.statusText, { color }]}>Saving audio…</Text>
      </View>
    );
  }

  if (phase === 'review') {
    return (
      <View style={styles.reviewBox}>
        <Text style={styles.reviewLabel}>Recording ready — choose what to do:</Text>
        <View style={styles.reviewBtnRow}>
          <TouchableOpacity
            style={[styles.reviewBtn, styles.reviewTextBtn]}
            onPress={doTranscribe}
            activeOpacity={0.85}>
            <Ionicons name="text" size={16} color="#FFF" />
            <Text style={styles.reviewBtnText}>Transcribe to Text</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.reviewBtn, styles.reviewAudioBtn]}
            onPress={doSaveAudio}
            activeOpacity={0.85}>
            <Ionicons name="save" size={16} color="#FFF" />
            <Text style={styles.reviewBtnText}>
              Save Audio
              {estimate !== null ? `  •  ≈${estimate.toFixed(2)} cr` : ''}
            </Text>
          </TouchableOpacity>
        </View>
        <View style={styles.reviewMetaRow}>
          {pendingBytes > 0 && (
            <Text style={styles.reviewMeta}>
              {(pendingBytes / 1024).toFixed(0)} KB · stored for {estimateDays}d
            </Text>
          )}
          <TouchableOpacity onPress={resetReview} style={styles.reviewDiscard}>
            <Ionicons name="close" size={14} color="#64748B" />
            <Text style={styles.reviewDiscardText}>Discard</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  const isRecording = phase === 'recording';
  return (
    <TouchableOpacity
      style={[
        styles.micChip,
        { borderColor: isRecording ? '#DC2626' : color },
        isRecording && styles.micChipRecording,
        disabled && styles.disabled,
      ]}
      onPress={isRecording ? stopRecording : startRecording}
      disabled={disabled}
      activeOpacity={0.7}>
      <Ionicons
        name={isRecording ? 'stop-circle' : 'mic'}
        size={16}
        color={isRecording ? '#DC2626' : color}
      />
      <Text style={[styles.micChipLabel, { color: isRecording ? '#DC2626' : color }]}>
        {isRecording ? 'Tap to Stop' : 'Voice'}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  micChip: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 16,
    borderWidth: 1.5,
    backgroundColor: '#FFF',
  },
  micChipRecording: {
    backgroundColor: '#FEF2F2',
  },
  micChipLabel: {
    fontSize: 11,
    fontWeight: '700',
  },
  disabled: { opacity: 0.5 },

  statusChip: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 16,
    borderWidth: 1.5,
    backgroundColor: '#FFF',
  },
  statusText: { fontSize: 11, fontWeight: '600' },

  reviewBox: {
    backgroundColor: '#F8FAFC',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#CBD5E1',
    padding: 10,
    marginTop: 6,
  },
  reviewLabel: {
    color: '#0F172A',
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 8,
  },
  reviewBtnRow: { flexDirection: 'row', gap: 8 },
  reviewBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 9,
    borderRadius: 8,
  },
  reviewTextBtn: { backgroundColor: '#003087' },
  reviewAudioBtn: { backgroundColor: '#059669' },
  reviewBtnText: { color: '#FFF', fontSize: 12, fontWeight: '700' },

  reviewMetaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
  },
  reviewMeta: { color: '#64748B', fontSize: 11 },
  reviewDiscard: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  reviewDiscardText: { color: '#64748B', fontSize: 11, fontWeight: '600' },
});

export default VoiceInput;
