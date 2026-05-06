/**
 * BrandFooter — Tiny "by Earth Dezider" imprint shown on splash, login, /about, footers.
 *
 * Usage:
 *   import { BrandFooter } from '@/src/components/BrandFooter';
 *   <BrandFooter />              // small footer
 *   <BrandFooter variant="hero"/> // big with edition wordmark
 */
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useBrandingStore } from '../store/brandingStore';

interface Props {
  variant?: 'small' | 'hero';
}

export function BrandFooter({ variant = 'small' }: Props) {
  const brand = useBrandingStore(s => s.brand);

  if (variant === 'hero') {
    return (
      <View style={styles.heroWrap}>
        <Text style={[styles.heroBrand, { color: brand.primary_color }]}>{brand.display_name}</Text>
        <Text style={styles.heroBy}>by {brand.master_brand}</Text>
      </View>
    );
  }

  return (
    <View style={styles.smallWrap}>
      <Text style={styles.smallText}>An {brand.master_brand} product</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  smallWrap: { alignItems: 'center', paddingVertical: 12, opacity: 0.7 },
  smallText: { fontSize: 11, color: '#6B7280', fontWeight: '500' },
  heroWrap: { alignItems: 'center', paddingVertical: 24 },
  heroBrand: { fontSize: 26, fontWeight: '800', letterSpacing: 1 },
  heroBy: { fontSize: 11, color: '#6B7280', marginTop: 4, fontWeight: '500' },
});
