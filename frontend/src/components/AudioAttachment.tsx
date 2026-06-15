import React, { useEffect, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAudioPlayer, useAudioPlayerStatus, setAudioModeAsync } from 'expo-audio';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../utils/api';

export interface AudioAttachmentMeta {
  audio_id: string;
  field?: string;
  ext: string;
  size_bytes: number;
  duration_sec?: number;
  credits_charged?: number;
  retention_days?: number;
  created_at?: string;
}

interface Props {
  audio: AudioAttachmentMeta;
  /** Called after a successful delete. */
  onDeleted?: (audio_id: string) => void;
}

/**
 * AudioAttachment
 * ───────────────
 * Compact chip that shows a saved voice clip with play/pause + size + delete.
 * Audio is private (auth-gated) so we fetch the bytes via axios (Bearer token)
 * then hand the player a blob: URL on web / data URI on native.
 */
export const AudioAttachment: React.FC<Props> = ({ audio, onDeleted }) => {
  const [uri, setUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    let createdObjectUrl: string | null = null;

    (async () => {
      try {
        const token = await AsyncStorage.getItem('session_token');
        const apiUrl = (process.env.EXPO_PUBLIC_BACKEND_URL || '') + '/api';
        const res = await fetch(`${apiUrl}/conflict-breaker/audio/${audio.audio_id}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        createdObjectUrl = URL.createObjectURL(blob);
        if (mountedRef.current) {
          setUri(createdObjectUrl);
          setError(null);
        }
      } catch (err: any) {
        if (mountedRef.current) setError(err?.message || 'Failed to load');
      } finally {
        if (mountedRef.current) setLoading(false);
      }
    })();

    return () => {
      mountedRef.current = false;
      if (createdObjectUrl) {
        try { URL.revokeObjectURL(createdObjectUrl); } catch { /* noop */ }
      }
    };
  }, [audio.audio_id]);

  const player = useAudioPlayer(uri ? { uri } : null);
  const pstatus = useAudioPlayerStatus(player);
  const playing = !!pstatus?.playing;

  useEffect(() => {
    if (pstatus?.didJustFinish) {
      try { player.seekTo(0); player.pause(); } catch { /* noop */ }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pstatus?.didJustFinish]);

  const togglePlay = async () => {
    if (!uri) return;
    try {
      await setAudioModeAsync({ playsInSilentMode: true });
      if (playing) player.pause();
      else player.play();
    } catch (err) {
      console.error('audio play error', err);
    }
  };

  const handleDelete = async () => {
    if (deleting) return;
    setDeleting(true);
    try {
      await api.delete(`/conflict-breaker/audio/${audio.audio_id}`);
      onDeleted?.(audio.audio_id);
    } catch {
      setDeleting(false);
    }
  };

  const sizeKb = Math.round((audio.size_bytes || 0) / 1024);
  const dur = Math.round(audio.duration_sec || 0);

  if (error) {
    return (
      <View style={[styles.chip, styles.chipError]}>
        <Ionicons name="alert-circle" size={14} color="#DC2626" />
        <Text style={styles.chipErrorText}>Audio unavailable</Text>
        <TouchableOpacity onPress={handleDelete} style={styles.delBtn}>
          <Ionicons name="trash" size={13} color="#64748B" />
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.chip}>
      <TouchableOpacity
        style={styles.playBtn}
        onPress={togglePlay}
        disabled={loading || !uri}
        activeOpacity={0.7}>
        {loading
          ? <ActivityIndicator size="small" color="#003087" />
          : <Ionicons name={playing ? 'pause' : 'play'} size={14} color="#003087" />}
      </TouchableOpacity>
      <View style={styles.meta}>
        <Text style={styles.metaTitle}>Voice clip</Text>
        <Text style={styles.metaSub}>
          {dur > 0 ? `${dur}s · ` : ''}{sizeKb} KB
          {audio.credits_charged ? `  ·  ${audio.credits_charged.toFixed(2)} cr` : ''}
        </Text>
      </View>
      <TouchableOpacity onPress={handleDelete} style={styles.delBtn} disabled={deleting}>
        {deleting
          ? <ActivityIndicator size="small" color="#64748B" />
          : <Ionicons name="trash-outline" size={14} color="#64748B" />}
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#EEF4FF',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#BFD7FF',
    paddingHorizontal: 8,
    paddingVertical: 6,
    marginTop: 6,
  },
  chipError: { backgroundColor: '#FEF2F2', borderColor: '#FCA5A5' },
  chipErrorText: { color: '#DC2626', fontSize: 11, fontWeight: '600', flex: 1 },
  playBtn: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: '#FFF', borderWidth: 1, borderColor: '#BFD7FF',
    justifyContent: 'center', alignItems: 'center',
  },
  meta: { flex: 1 },
  metaTitle: { color: '#0F172A', fontSize: 12, fontWeight: '700' },
  metaSub: { color: '#64748B', fontSize: 10, marginTop: 1 },
  delBtn: { padding: 4 },
});

export default AudioAttachment;
