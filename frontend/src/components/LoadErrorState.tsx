/**
 * LoadErrorState — friendly "couldn't load" panel with a Retry button.
 *
 * Used by list screens (Solution Box, Pros & Cons, Solution Finder) so a
 * transient network/API failure shows an explicit retry instead of rendering
 * as a misleading "empty account".
 */
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';

interface Props {
  onRetry: () => void;
  message?: string;
}

export default function LoadErrorState({ onRetry, message }: Props) {
  return (
    <View style={styles.wrap} testID="load-error-state">
      <View style={styles.iconWrap}>
        <Ionicons name="cloud-offline-outline" size={42} color="#D97706" />
      </View>
      <Text style={styles.title}>Couldn&apos;t load your data</Text>
      <Text style={styles.text}>
        {message ||
          'Looks like a temporary connection hiccup — your data is safe on the server. Please retry.'}
      </Text>
      <TouchableOpacity style={styles.btn} onPress={onRetry} testID="load-error-retry" accessibilityLabel="Retry loading">
        <Ionicons name="refresh" size={18} color="#FFF" />
        <Text style={styles.btnText}>Retry</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', paddingVertical: 48, paddingHorizontal: 32, gap: 10 },
  iconWrap: {
    width: 72, height: 72, borderRadius: 36,
    backgroundColor: '#FFFBEB', borderWidth: 1, borderColor: '#FDE68A',
    justifyContent: 'center', alignItems: 'center', marginBottom: 4,
  },
  title: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  text: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', lineHeight: 19 },
  btn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: COLORS.primary, paddingHorizontal: 24, paddingVertical: 12,
    borderRadius: 12, marginTop: 8, minHeight: 44,
  },
  btnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
});
