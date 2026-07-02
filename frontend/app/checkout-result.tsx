import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../src/constants/colors';
import { pollStripeStatus } from '../src/utils/stripeCheckout';

type Phase = 'checking' | 'completed' | 'pending' | 'cancelled';

export default function CheckoutResult() {
  const router = useRouter();
  const params = useLocalSearchParams<{ stripe_session?: string; stripe_cancelled?: string }>();
  const sessionId = typeof params.stripe_session === 'string' ? params.stripe_session : '';
  const cancelled = params.stripe_cancelled === '1';
  const [phase, setPhase] = useState<Phase>(cancelled ? 'cancelled' : 'checking');

  useEffect(() => {
    if (cancelled || !sessionId) {
      if (!sessionId && !cancelled) setPhase('pending');
      return;
    }
    let alive = true;
    (async () => {
      const status = await pollStripeStatus(sessionId);
      if (!alive) return;
      setPhase(status === 'completed' ? 'completed' : 'pending');
    })();
    return () => { alive = false; };
  }, [sessionId, cancelled]);

  const goBack = () => router.replace('/ai-wallet');

  const cfg = {
    checking: { icon: 'time-outline', color: COLORS.primary, title: 'Confirming your payment…', sub: 'This only takes a moment.' },
    completed: { icon: 'checkmark-circle', color: '#16A34A', title: 'Payment successful 🎉', sub: 'Your purchase has been applied to your account.' },
    pending: { icon: 'hourglass-outline', color: '#D97706', title: 'Payment is processing', sub: 'It may take a minute to reflect. Pull to refresh your wallet shortly.' },
    cancelled: { icon: 'close-circle', color: '#DC2626', title: 'Checkout cancelled', sub: 'No charge was made. You can try again anytime.' },
  }[phase];

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.center}>
        {phase === 'checking' ? (
          <ActivityIndicator size="large" color={COLORS.primary} />
        ) : (
          <Ionicons name={cfg.icon as any} size={72} color={cfg.color} />
        )}
        <Text style={styles.title}>{cfg.title}</Text>
        <Text style={styles.sub}>{cfg.sub}</Text>
        {phase !== 'checking' && (
          <TouchableOpacity style={[styles.btn, { backgroundColor: cfg.color }]} onPress={goBack}>
            <Text style={styles.btnText}>Back to Wallet</Text>
          </TouchableOpacity>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  title: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary, marginTop: 20, textAlign: 'center' },
  sub: { fontSize: 14, color: COLORS.textSecondary, marginTop: 8, textAlign: 'center', lineHeight: 20 },
  btn: { marginTop: 28, paddingVertical: 14, paddingHorizontal: 32, borderRadius: 12, minWidth: 200, alignItems: 'center' },
  btnText: { color: '#FFF', fontSize: 16, fontWeight: '700' },
});
