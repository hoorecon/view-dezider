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
  // when the balance drops below this many credits, the chip turns amber and
  // shows a "Top up" nudge. Pass the cost of the next AI action on the screen.
  lowThreshold?: number;
}

/**
 * Small inline chip that shows the user's AI-credits balance. Tapping it opens
 * the AI Wallet screen. Colour reflects how low the balance is — and when the
 * balance can't cover the next AI action (lowThreshold) it shows a "Top up" nudge.
 */
export const AiCreditsBadge: React.FC<Props> = ({ autoRefresh = false, compact = false, lowThreshold }) => {
  const router = useRouter();
  const { balance, loaded, loading, refresh } = useAiWalletStore();

  useEffect(() => {
    if (autoRefresh || !loaded) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const threshold = lowThreshold && lowThreshold > 0 ? lowThreshold : 3;
  const empty = balance <= 0;
  const low = balance > 0 && balance < threshold;
  const nudge = empty || low;
  const tint = empty ? COLORS.error : low ? COLORS.warning : COLORS.primary;

  return (
    <TouchableOpacity
      onPress={() => router.push('/ai-wallet' as any)}
      activeOpacity={0.8}
      style={[styles.chip, { borderColor: tint }, nudge && { backgroundColor: tint + '14' }, compact && styles.chipCompact]}
    >
      <Ionicons name="sparkles" size={compact ? 12 : 14} color={tint} />
      {loading && !loaded ? (
        <ActivityIndicator size="small" color={tint} style={{ marginLeft: 4 }} />
      ) : (
        <Text style={[styles.text, { color: tint }, compact && { fontSize: 11 }]}>
          {balance.toFixed(balance < 10 ? 1 : 0)}{compact ? '' : ' AI credits'}
          {nudge ? ' · Top up' : ''}
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
