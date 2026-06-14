/**
 * <VentToOutletsBanner /> — the "Need to vent first?" bypass-rider for
 * every Emotional Gatekeeper sub-module (Emotional Reception, Breaking
 * the Trap, Breaking the Loop, Breaking Limitations).
 *
 * Behaviour (per user spec):
 *  • Always visible at the top of the screen as a SKIPPABLE option.
 *  • After 5 minutes of stillness on the screen, a softer auto-prompt
 *    surfaces beneath the banner with the same CTA.
 *  • If the user came in via Solution Finder (`return_to` param), the
 *    Outlets Advisor preserves that return context so the user can chain
 *    back to Step 3 from there.
 *
 * Wiring — drop the component near the top of every EG sub-module:
 *    <VentToOutletsBanner returnTo={searchParams.return_to} returnId={searchParams.return_id} />
 */
import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

interface Props {
  /** Where the parent flow originated — propagated to Outlets Advisor so
   * the user can chain back ("solution-finder" → Step 3 by default). */
  returnTo?: string;
  returnId?: string;
  /** Auto-prompt delay in ms. Defaults to 5 min per user spec. */
  autoPromptMs?: number;
}

export default function VentToOutletsBanner({ returnTo, returnId, autoPromptMs = 5 * 60 * 1000 }: Props) {
  const router = useRouter();
  const [autoVisible, setAutoVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setAutoVisible(true), autoPromptMs);
    return () => clearTimeout(t);
  }, [autoPromptMs]);

  const goVent = () => {
    const qp = new URLSearchParams();
    if (returnTo) qp.set('return_to', returnTo);
    if (returnId) qp.set('return_id', returnId);
    const qs = qp.toString();
    router.push(`/tools/eg-advisor${qs ? `?${qs}` : ''}` as any);
  };

  return (
    <View>
      <TouchableOpacity style={s.banner} onPress={goVent} testID="vent-to-outlets-btn">
        <View style={s.iconWrap}>
          <Ionicons name="leaf" size={16} color="#047857" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>Need to vent first?</Text>
          <Text style={s.subtitle}>Effective Outlets Advisor · skippable</Text>
        </View>
        <Ionicons name="chevron-forward" size={16} color="#047857" />
      </TouchableOpacity>

      {autoVisible && (
        <View style={s.autoPrompt} testID="vent-auto-prompt">
          <Ionicons name="time-outline" size={13} color="#047857" />
          <Text style={s.autoText}>
            Still here after 5 min? Try a short outlet practice — you can come right back.
          </Text>
          <TouchableOpacity onPress={goVent} style={s.autoBtn} testID="vent-auto-btn">
            <Text style={s.autoBtnText}>Try outlets</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  banner: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingHorizontal: 12, paddingVertical: 10,
    backgroundColor: '#ECFDF5', borderRadius: 12,
    borderWidth: 1, borderColor: '#A7F3D0',
    marginHorizontal: 16, marginVertical: 10,
  },
  iconWrap: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: '#D1FAE5',
    alignItems: 'center', justifyContent: 'center',
  },
  title: { fontSize: 13, fontWeight: '700', color: '#065F46' },
  subtitle: { fontSize: 11, color: '#047857', marginTop: 1 },

  autoPrompt: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 12, paddingVertical: 8,
    backgroundColor: '#F0FDF4', borderRadius: 10,
    borderWidth: 1, borderColor: '#BBF7D0',
    marginHorizontal: 16, marginBottom: 10,
  },
  autoText: { flex: 1, fontSize: 11, color: '#065F46', lineHeight: 15 },
  autoBtn: { paddingHorizontal: 10, paddingVertical: 5, backgroundColor: '#047857', borderRadius: 8 },
  autoBtnText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
});
