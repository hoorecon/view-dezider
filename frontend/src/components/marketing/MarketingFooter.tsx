/**
 * MarketingFooter — shared footer for public pages with company info
 * and links to all legal/policy pages (required for payment-gateway review).
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, useWindowDimensions, Image, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { COLORS } from '../../constants/colors';
import { LEGAL_LINKS } from '../../constants/company';
import { useCompanyName, useAppLogo, useCompany } from '../../contexts/FontFamilyContext';

export default function MarketingFooter() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const twoCol = width >= 760;
  const companyName = useCompanyName();
  const logoUri = useAppLogo();
  const company = useCompany();

  return (
    <View style={styles.footer}>
      <View style={[styles.inner, twoCol && styles.innerRow]}>
        {/* Company block */}
        <View style={[styles.col, twoCol && { flex: 1.4, paddingRight: 24 }]}>
          {logoUri ? <Image source={{ uri: logoUri }} style={styles.footerLogo} resizeMode="contain" /> : null}
          <Text style={styles.brand}>{company.product}</Text>
          <Text style={styles.tagline}>{company.tagline}</Text>
          <Text style={styles.legalName}>{companyName}</Text>
          {company.addressLines.map((l, i) => (
            <Text key={i} style={styles.addr}>{l}</Text>
          ))}
        </View>

        {/* Legal links */}
        <View style={[styles.col, twoCol && { flex: 1 }]}>
          <Text style={styles.colHead}>Legal & Policies</Text>
          {LEGAL_LINKS.map((link) => (
            <TouchableOpacity key={link.route} style={styles.linkRow} onPress={() => router.push(link.route as any)}>
              <Ionicons name="chevron-forward" size={12} color={COLORS.primary} />
              <Text
                style={styles.link}
                accessibilityRole="link"
                {...(Platform.OS === 'web' ? ({ href: link.route } as any) : {})}
              >
                {link.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Merchant details (payment-gateway compliance) */}
        <View style={[styles.col, twoCol && { flex: 1.2 }]}>
          <Text style={styles.colHead}>Merchant Details</Text>
          <Text style={styles.mRow}><Text style={styles.mKey}>Merchant Legal Name: </Text>{company.legalName}</Text>
          <Text style={styles.mRow}>
            <Text style={styles.mKey}>Merchant Website: </Text>
            <Text accessibilityRole="link" {...(Platform.OS === 'web' ? ({ href: company.websiteUrl } as any) : {})} style={styles.mLink}>{company.websiteUrl}</Text>
          </Text>
          <Text style={styles.mRow}><Text style={styles.mKey}>Support Email: </Text>{company.email}</Text>
          <Text style={styles.mRow}><Text style={styles.mKey}>Support Phone: </Text>{company.phone}</Text>
        </View>
      </View>

      <View style={styles.bottomBar}>
        <Text style={styles.copy}>
          © {new Date().getFullYear()} {companyName}. All rights reserved.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  footer: { backgroundColor: '#0F1024', paddingTop: 36 },
  inner: { paddingHorizontal: 24, paddingBottom: 24 },
  innerRow: { flexDirection: 'row', flexWrap: 'wrap' },
  col: { marginBottom: 24 },
  brand: { fontSize: 20, fontWeight: '900', color: '#FFFFFF', letterSpacing: 0.4 },
  footerLogo: { width: 120, height: 44, marginBottom: 10 },
  tagline: { fontSize: 12, color: '#A9ABC9', marginTop: 4, marginBottom: 14, lineHeight: 18 },
  legalName: { fontSize: 13, fontWeight: '700', color: '#E2E3F0', marginBottom: 6 },
  addr: { fontSize: 12, color: '#8E90B0', lineHeight: 18 },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  contactLink: { fontSize: 12.5, color: '#C7C9E6' },
  colHead: { fontSize: 13, fontWeight: '800', color: '#FFFFFF', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 0.6 },
  linkRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 7 },
  link: { fontSize: 13.5, color: '#C7C9E6' },
  mRow: { fontSize: 12.5, color: '#A9ABC9', lineHeight: 20, marginBottom: 4 },
  mKey: { color: '#E2E3F0', fontWeight: '700' },
  mLink: { color: '#C7C9E6', textDecorationLine: 'underline' },
  bottomBar: { borderTopWidth: 1, borderTopColor: '#22243F', paddingVertical: 16, paddingHorizontal: 24, alignItems: 'center' },
  copy: { fontSize: 11.5, color: '#7E80A0', textAlign: 'center' },
});
