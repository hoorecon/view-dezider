import React, { useEffect, useRef, useState, useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Linking, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../utils/api';

/**
 * Floating "Join session" pill shown to a contributor while they edit a
 * Live-Sync shared step. Self-contained: given the shareId it resolves the
 * share's session_mode + room URL, sends a presence heartbeat every ~20s and
 * shows the live "active now" count. Renders nothing for async shares.
 */
export default function LiveSessionPill({ shareId }: { shareId?: string | null }) {
  const [room, setRoom] = useState<string | null>(null);
  const [isLive, setIsLive] = useState(false);
  const [active, setActive] = useState(0);
  const [collapsed, setCollapsed] = useState(false);
  const timer = useRef<any>(null);

  const beat = useCallback(async () => {
    if (!shareId) return;
    try {
      await api.post(`/shared-steps/${shareId}/presence`, {});
      const { data } = await api.get(`/shared-steps/${shareId}/presence`);
      setActive(data?.count || 0);
    } catch { /* best-effort */ }
  }, [shareId]);

  useEffect(() => {
    let mounted = true;
    if (!shareId) return;
    (async () => {
      try {
        const { data } = await api.get(`/shared-steps/${shareId}/access`);
        if (!mounted) return;
        if (data?.session_mode === 'live_sync' && data?.call_room_url) {
          setIsLive(true);
          setRoom(data.call_room_url);
          beat();
          timer.current = setInterval(beat, 20000);
        }
      } catch { /* not a live share / no access */ }
    })();
    return () => { mounted = false; if (timer.current) clearInterval(timer.current); };
  }, [shareId, beat]);

  if (!isLive || !room) return null;

  const join = () => {
    if (Platform.OS === 'web') { window.open(room!, '_blank'); }
    else { Linking.openURL(room!); }
  };

  if (collapsed) {
    return (
      <TouchableOpacity style={s.fab} onPress={() => setCollapsed(false)} testID="live-pill-fab">
        <Ionicons name="videocam" size={20} color="#FFF" />
        {active > 0 && <View style={s.fabDot}><Text style={s.fabDotTxt}>{active}</Text></View>}
      </TouchableOpacity>
    );
  }

  return (
    <View style={s.pill} testID="live-session-pill">
      <View style={s.dot} />
      <View style={{ flex: 1 }}>
        <Text style={s.title}>Live session</Text>
        <Text style={s.sub}>{active > 0 ? `${active} active now` : 'No one active yet'}</Text>
      </View>
      <TouchableOpacity style={s.joinBtn} onPress={join} testID="join-session-btn">
        <Ionicons name="videocam" size={15} color="#FFF" />
        <Text style={s.joinTxt}>Join</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={() => setCollapsed(true)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
        <Ionicons name="chevron-down" size={18} color="#065F46" />
      </TouchableOpacity>
    </View>
  );
}

const s = StyleSheet.create({
  pill: {
    position: 'absolute', left: 12, right: 12, bottom: 18,
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#ECFDF5', borderColor: '#6EE7B7', borderWidth: 1,
    borderRadius: 16, paddingVertical: 10, paddingHorizontal: 14,
    shadowColor: '#000', shadowOpacity: 0.12, shadowRadius: 12, shadowOffset: { width: 0, height: 4 }, elevation: 6,
    maxWidth: 520, alignSelf: 'center', width: '100%',
  },
  dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#16A34A' },
  title: { fontSize: 13.5, fontWeight: '800', color: '#065F46' },
  sub: { fontSize: 11.5, color: '#059669', marginTop: 1 },
  joinBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#059669', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 14 },
  joinTxt: { color: '#FFF', fontSize: 13, fontWeight: '800' },
  fab: {
    position: 'absolute', right: 16, bottom: 24, width: 52, height: 52, borderRadius: 26,
    backgroundColor: '#059669', alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 10, shadowOffset: { width: 0, height: 4 }, elevation: 6,
  },
  fabDot: { position: 'absolute', top: -2, right: -2, minWidth: 18, height: 18, borderRadius: 9, backgroundColor: '#DC2626', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4 },
  fabDotTxt: { color: '#FFF', fontSize: 10, fontWeight: '800' },
});
