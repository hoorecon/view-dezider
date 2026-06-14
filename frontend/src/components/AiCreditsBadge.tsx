/**
 * AiCreditsBadge — wallet balance pill rendered in screen headers everywhere
 * an AI action can be triggered (AIM, Outlet, Step 2 modals, Deep Import,
 * Top of /ai-wallet, etc.).
 *
 * v2 (Wave-5 visibility fix):
 *   • Always renders the balance in BIG bold text — `412.6 cr` / `-412.6 cr`
 *     instead of the previous cramped sparkles-only chip that hid the
 *     minus sign and the unit suffix.
 *   • Colour-coded against severity: 🟣 healthy, 🟠 low (<lowThreshold),
 *     🔴 negative/empty.
 *   • The "Top up" affordance is now a SEPARATE button next to the pill
 *     so users see both the balance and the action at the same time.
 *   • `compact` retains the old single-line chip for places that genuinely
 *     can't host two affordances.
 */
import React, { useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { COLORS } from '../constants/colors';
import { useAiWalletStore } from '../store/aiWalletStore';

interface Props {
  autoRefresh?: boolean;
  compact?: boolean;
  lowThreshold?: number;
}

export const AiCreditsBadge: React.FC<Props> = ({ autoRefresh = false, compact = false, lowThreshold }) => {
  const router = useRouter();
  const { balance, loaded, loading, refresh } = useAiWalletStore();

  useEffect(() => {
    if (autoRefresh || !loaded) refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const threshold = lowThreshold && lowThreshold > 0 ? lowThreshold : 50;
  const empty = balance <= 0;
  const low = balance > 0 && balance < threshold;
  const tint = empty ? '#DC2626' : low ? '#D97706' : COLORS.primary;
  const bg = empty ? '#FEF2F2' : low ? '#FEF3C7' : '#F5F3FF';

  // Compact mode keeps the legacy single-chip look (used inside dense rows).
  if (compact) {
    return (
      <TouchableOpacity
        testID="ai-credits-badge-compact"
        onPress={() => router.push('/ai-wallet' as any)}
        activeOpacity={0.8}
        style={[styles.chipCompact, { borderColor: tint, backgroundColor: bg }]}
      >
        <Ionicons name="sparkles" size={12} color={tint} />
        {loading && !loaded
          ? <ActivityIndicator size="small" color={tint} />
          : <Text style={[styles.compactText, { color: tint }]}>{balance.toFixed(balance < 10 ? 1 : 0)}</Text>}
      </TouchableOpacity>
    );
  }

  return (
    <View style={styles.wrap} testID="ai-credits-badge-wrap">
      <TouchableOpacity
        testID="ai-credits-badge"
        onPress={() => router.push('/ai-wallet' as any)}
        activeOpacity={0.8}
        style={[styles.pill, { borderColor: tint, backgroundColor: bg }]}
      >
        <Ionicons name="sparkles" size={15} color={tint} />
        {loading && !loaded ? (
          <ActivityIndicator size="small" color={tint} style={{ marginLeft: 6 }} />
        ) : (
          <Text style={[styles.pillText, { color: tint }]} numberOfLines={1}>
            {balance.toFixed(balance < 10 ? 1 : 0)} cr
          </Text>
        )}
      </TouchableOpacity>
      {(empty || low) && !loading && (
        <TouchableOpacity
          testID="ai-credits-topup-btn"
          onPress={() => router.push('/ai-wallet' as any)}
          activeOpacity={0.85}
          style={[styles.topupBtn, { backgroundColor: tint }]}
        >
          <Ionicons name="flash" size={11} color="#FFF" />
          <Text style={styles.topupText}>Top up</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  pill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    borderWidth: 1.5, borderRadius: 999,
    paddingHorizontal: 12, paddingVertical: 6,
    minWidth: 72, justifyContent: 'center',
  },
  pillText: { fontSize: 13.5, fontWeight: '800', letterSpacing: 0.2 },
  topupBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999,
  },
  topupText: { color: '#FFF', fontSize: 11.5, fontWeight: '800' },
  chipCompact: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    borderWidth: 1, borderRadius: 999,
    paddingHorizontal: 8, paddingVertical: 3,
  },
  compactText: { fontSize: 11, fontWeight: '800' },
});

export default AiCreditsBadge;
