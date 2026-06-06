import React, { useEffect } from 'react';
import { Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { COLORS } from '../constants/colors';
import { useAiWalletStore } from '../store/aiWalletStore';

interface Props {
  // when true, refetches the balance whenever it mounts (use on assess screens)
  autoRefresh?: boolean;
  compact?: boolean;
}

/**
 * Small inline chip that shows the user's AI-credits balance. Tapping it opens
 * the AI Wallet screen. Colour reflects how low the balance is.
 */
export const AiCreditsBadge: React.FC<Props> = ({ autoRefresh = false, compact = false }) => {
  const router = useRouter();
  const { balance, loaded, loading, refresh } = useAiWalletStore();

  useEffect(() => {
    if (autoRefresh || !loaded) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const empty = balance <= 0;
  const low = balance > 0 && balance < 3;
  const tint = empty ? COLORS.error : low ? COLORS.warning : COLORS.primary;

  return (
    <TouchableOpacity
      onPress={() => router.push('/ai-wallet' as any)}
      activeOpacity={0.8}
      style={[styles.chip, { borderColor: tint }, compact && styles.chipCompact]}
    >
      <Ionicons name="sparkles" size={compact ? 12 : 14} color={tint} />
      {loading && !loaded ? (
        <ActivityIndicator size="small" color={tint} style={{ marginLeft: 4 }} />
      ) : (
        <Text style={[styles.text, { color: tint }, compact && { fontSize: 11 }]}>
          {balance.toFixed(balance < 10 ? 1 : 0)} {compact ? '' : 'AI credits'}
        </Text>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: COLORS.white,
    gap: 4,
  },
  chipCompact: { paddingHorizontal: 8, paddingVertical: 3 },
  text: { fontSize: 12, fontWeight: '700' },
});

export default AiCreditsBadge;
