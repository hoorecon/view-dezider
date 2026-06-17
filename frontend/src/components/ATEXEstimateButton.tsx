/**
 * ATEXEstimateButton
 * Drop-in button for CTT / Lifestyle Dezider / Lifestyle Designer create forms
 * to invoke the ATEX Effort Estimation calculator and receive the computed Final
 * Timeline back via expo-router params.
 */
import React from 'react';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

interface Props {
  source: 'ctt' | 'lifestyle_dezider' | 'lifestyle_designer' | 'six_legs' | 'goal_setter';
  ref_id?: string;
  title?: string;
  compact?: boolean;
}

export default function ATEXEstimateButton({ source, ref_id, title, compact = false }: Props) {
  const router = useRouter();
  const onPress = () => {
    router.push({
      pathname: '/tools/atex',
      params: { source, ref_id: ref_id || '', title: title || '' },
    } as any);
  };
  return (
    <TouchableOpacity style={[s.btn, compact && s.btnCompact]} onPress={onPress}>
      <Ionicons name="calculator" size={compact ? 12 : 14} color="#FFF" />
      <Text style={[s.txt, compact && { fontSize: 11 }]}>{compact ? 'ATEX' : 'Estimate effort (ATEX)'}</Text>
    </TouchableOpacity>
  );
}

const s = StyleSheet.create({
  btn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#7C3AED', borderRadius: 8, paddingVertical: 8, paddingHorizontal: 12, alignSelf: 'flex-start' },
  btnCompact: { paddingVertical: 4, paddingHorizontal: 8, borderRadius: 6 },
  txt: { color: '#FFF', fontWeight: '700', fontSize: 12 },
});
