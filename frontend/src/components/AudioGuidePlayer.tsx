import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { useAudioPlayer, useAudioPlayerStatus, setAudioModeAsync } from 'expo-audio';
import { Ionicons } from '@expo/vector-icons';

interface AudioGuidePlayerProps {
  uri: string;
  title: string;
  color?: string;
  compact?: boolean;
}

export const AudioGuidePlayer: React.FC<AudioGuidePlayerProps> = ({
  uri, title, color = '#0EA5E9', compact = false,
}) => {
  const player = useAudioPlayer(uri ? { uri } : null);
  const pstatus = useAudioPlayerStatus(player);
  const [intentPlay, setIntentPlay] = useState(false);

  const playing = !!pstatus?.playing;
  const isLoaded = !!pstatus?.isLoaded;
  const position = (pstatus?.currentTime ?? 0) * 1000;   // seconds → millis for formatTime
  const duration = (pstatus?.duration ?? 0) * 1000;
  const status: 'idle' | 'loading' | 'playing' | 'paused' =
    playing ? 'playing' : (intentPlay && !isLoaded ? 'loading' : 'idle');

  useEffect(() => {
    if (pstatus?.didJustFinish) {
      try { player.seekTo(0); player.pause(); } catch { /* noop */ }
      setIntentPlay(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pstatus?.didJustFinish]);

  const formatTime = (millis: number) => {
    const totalSecs = Math.floor((millis || 0) / 1000);
    const m = Math.floor(totalSecs / 60);
    const s = totalSecs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const handlePress = async () => {
    try {
      await setAudioModeAsync({ playsInSilentMode: true });
      if (playing) { player.pause(); setIntentPlay(false); }
      else { setIntentPlay(true); player.play(); }
    } catch (err) {
      console.error('Audio error:', err);
      setIntentPlay(false);
    }
  };

  const progress = duration > 0 ? position / duration : 0;

  if (compact) {
    return (
      <TouchableOpacity style={[cs.compactBtn, { borderColor: color }]} onPress={handlePress}>
        {status === 'loading' ? (
          <ActivityIndicator size="small" color={color} />
        ) : (
          <Ionicons
            name={status === 'playing' ? 'pause' : 'play'}
            size={16}
            color={color}
          />
        )}
        <Text style={[cs.compactText, { color }]} numberOfLines={1}>{title}</Text>
        {status === 'playing' && (
          <Text style={[cs.compactTime, { color }]}>{formatTime(position)}</Text>
        )}
      </TouchableOpacity>
    );
  }

  return (
    <View style={[cs.container, { borderColor: color + '40' }]}>
      <View style={cs.row}>
        <TouchableOpacity
          style={[cs.playBtn, { backgroundColor: color }]}
          onPress={handlePress}
        >
          {status === 'loading' ? (
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <Ionicons
              name={status === 'playing' ? 'pause' : 'play'}
              size={20}
              color="#FFF"
            />
          )}
        </TouchableOpacity>
        <View style={cs.info}>
          <Text style={cs.title} numberOfLines={1}>{title}</Text>
          <View style={cs.progressBg}>
            <View style={[cs.progressFill, { width: `${progress * 100}%`, backgroundColor: color }]} />
          </View>
          <View style={cs.timeRow}>
            <Text style={cs.time}>{formatTime(position)}</Text>
            <Text style={cs.time}>{formatTime(duration)}</Text>
          </View>
        </View>
      </View>
    </View>
  );
};

const cs = StyleSheet.create({
  container: {
    backgroundColor: '#FFF', borderRadius: 12, padding: 12,
    borderWidth: 1, marginTop: 10,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  playBtn: {
    width: 44, height: 44, borderRadius: 22,
    justifyContent: 'center', alignItems: 'center',
  },
  info: { flex: 1 },
  title: { fontSize: 13, fontWeight: '700', color: '#1F2937', marginBottom: 6 },
  progressBg: { height: 4, backgroundColor: '#E5E7EB', borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: 4, borderRadius: 2 },
  timeRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  time: { fontSize: 10, color: '#9CA3AF' },
  compactBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 8, paddingHorizontal: 12,
    borderRadius: 20, borderWidth: 1.5, backgroundColor: '#FFF',
  },
  compactText: { fontSize: 12, fontWeight: '600', flex: 1 },
  compactTime: { fontSize: 10 },
});
