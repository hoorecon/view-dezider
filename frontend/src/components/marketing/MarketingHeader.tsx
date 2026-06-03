/**
 * MarketingHeader — top navigation bar for public pages (landing + legal).
 * Brand mark on the left, Sign in / Get started on the right.
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, useWindowDimensions, Image } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../../constants/colors';
import { COMPANY } from '../../constants/company';
import { useAppLogo } from '../../contexts/FontFamilyContext';

export default function MarketingHeader({ activeCta = true }: { activeCta?: boolean }) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const compact = width < 640;
  const logoUri = useAppLogo();

  return (
    <View style={styles.bar}>
      <TouchableOpacity
        style={styles.brand}
        activeOpacity={0.8}
        onPress={() => router.push('/')}
      >
        {logoUri ? (
          <Image source={{ uri: logoUri }} style={styles.markImg} resizeMode="contain" />
        ) : (
          <LinearGradient colors={GRADIENTS.accent} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.mark}>
            <Ionicons name="sparkles" size={18} color="#FFFFFF" />
          </LinearGradient>
        )}
        <View style={styles.brandTextWrap}>
          <Text style={styles.brandName}>{COMPANY.product}</Text>
          {!compact && <Text style={styles.brandSub} numberOfLines={2}>{COMPANY.tagline}</Text>}
        </View>
      </TouchableOpacity>

      {activeCta && (
        <View style={styles.actions}>
          <TouchableOpacity style={styles.ghostBtn} onPress={() => router.push('/auth/login')}>
            <Text style={styles.ghostBtnText}>Sign in</Text>
          </TouchableOpacity>
          <TouchableOpacity activeOpacity={0.85} onPress={() => router.push('/auth/register')}>
            <LinearGradient colors={GRADIENTS.accent} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.primaryBtn}>
              <Text style={styles.primaryBtnText}>{compact ? 'Start' : 'Get started'}</Text>
            </LinearGradient>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingVertical: 14,
    backgroundColor: '#FFFFFF', borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10, flexShrink: 1, paddingRight: 12 },
  brandTextWrap: { flexShrink: 1, maxWidth: 360 },
  mark: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  markImg: { width: 40, height: 40, borderRadius: 10 },
  brandName: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary, letterSpacing: 0.3 },
  brandSub: { fontSize: 10, color: COLORS.textMuted, marginTop: 1, lineHeight: 13 },
  actions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  ghostBtn: { paddingHorizontal: 14, paddingVertical: 9, borderRadius: 10 },
  ghostBtnText: { fontSize: 14, fontWeight: '700', color: COLORS.primary },
  primaryBtn: { paddingHorizontal: 18, paddingVertical: 10, borderRadius: 10 },
  primaryBtnText: { fontSize: 14, fontWeight: '800', color: '#FFFFFF' },
});
