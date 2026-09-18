/**
 * /tools/eft — Alias & redirect route to /tools/eg-eft.
 *
 * Redirects legacy links or direct URL entries for /tools/eft to /tools/eg-eft,
 * preserving any query parameters (such as sessionId, return_to, etc.).
 */
import React, { useEffect } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { COLORS } from '../../src/constants/colors';

export default function EftRedirect() {
  const router = useRouter();
  const params = useLocalSearchParams<Record<string, string>>();

  useEffect(() => {
    const keys = Object.keys(params);
    let target = '/tools/eg-eft';
    if (keys.length > 0) {
      const qs = keys
        .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(String(params[k]))}`)
        .join('&');
      target += `?${qs}`;
    }
    router.replace(target as any);
  }, [params, router]);

  return (
    <SafeAreaView style={styles.bg}>
      <View style={styles.center}>
        <ActivityIndicator size="large" color={COLORS.primary} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  bg: { flex: 1, backgroundColor: COLORS.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
