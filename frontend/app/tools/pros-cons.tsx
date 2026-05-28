/**
 * /tools/pros-cons — legacy simple Pros & Cons route.
 *
 * The simple two-column Pros & Cons mode has been retired (user request:
 * "remove the normal one, keep only 8-Step Pros & Cons"). This file now
 * serves as a thin redirect to the unified 8-Step Pros & Cons wizard so
 * any old bookmarks / shared links continue to work — preserving the
 * `id` query param so an in-flight analysis opens on the correct doc.
 */
import React, { useEffect } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { COLORS } from '../../src/constants/colors';

export default function ProsConsRedirect() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string; module?: string }>();

  useEffect(() => {
    const qs: string[] = [];
    if (params.id)     qs.push(`id=${encodeURIComponent(String(params.id))}`);
    qs.push(`module=${encodeURIComponent(String(params.module || 'pros-cons'))}`);
    router.replace(`/tools/pros-cons-wizard?${qs.join('&')}` as any);
  }, [params.id, params.module, router]);

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
