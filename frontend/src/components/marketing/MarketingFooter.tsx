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
import { MARKETING_NAV } from './marketingNav';
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

        <View style={[styles.col, twoCol && { flex: 0.8 }]}>
          <Text style={styles.colHead}>EXPLORE</Text>
          {MARKETING_NAV.map((link) => (
            <TouchableOpacity
              key={link.href}
              style={styles.exploreRow}
              onPress={() => {
                if (Platform.OS === 'web' && typeof window !== 'undefined') {
                  window.location.assign(link.href);
                  return;
                }
                router.push(link.href as any);
              }}
            >
              <Text
                style={styles.exploreLink}
                accessibilityRole="link"
                {...(Platform.OS === 'web' ? ({ href: link.href } as any) : {})}
              >
                {link.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Legal links */}
        <View style={[styles.col, twoCol && { flex: 1 }]}>
          <Text style={styles.colHead}>LEGAL</Text>
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
          <Text style={styles.colHead}>MERCHANT</Text>
          <Text style={styles.mKey}>Legal name</Text>
          <Text style={styles.mVal}>{company.legalName}</Text>
          <Text style={styles.mKey}>Website</Text>
          <Text accessibilityRole="link" {...(Platform.OS === 'web' ? ({ href: company.websiteUrl, hrefAttrs: { target: '_blank', rel: 'noopener noreferrer' } } as any) : {})} style={styles.mLink}>{company.website}</Text>
          <Text style={styles.mKey}>Email</Text>
          <Text style={styles.mVal}>{company.email}</Text>
          <Text style={styles.mKey}>Phone</Text>
          <Text style={styles.mVal}>{company.phone}</Text>
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
  footer: { backgroundColor: '#0A1A4F', paddingTop: 56 },
  inner: { paddingHorizontal: 28, paddingBottom: 28, maxWidth: 1120, width: '100%', alignSelf: 'center' },
  innerRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 28 },
  col: { marginBottom: 28, minWidth: 200 },
  brand: { fontSize: 28, fontWeight: '800', color: '#FFFFFF', letterSpacing: -0.6 },
  footerLogo: { width: 44, height: 44, borderRadius: 10, marginBottom: 12 },
  tagline: { fontSize: 14, fontWeight: '400', color: 'rgba(255,255,255,0.62)', marginTop: 8, marginBottom: 16, lineHeight: 22, maxWidth: 320 },
  legalName: { fontSize: 13, fontWeight: '700', color: '#F48FB1', marginBottom: 8, letterSpacing: 0.3 },
  addr: { fontSize: 13, fontWeight: '400', color: 'rgba(255,255,255,0.55)', lineHeight: 20 },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  contactLink: { fontSize: 13, color: '#C7C9E6' },
  colHead: { fontSize: 11, fontWeight: '700', color: '#F48FB1', marginBottom: 14, letterSpacing: 2.4 },
  exploreRow: { paddingVertical: 7 },
  exploreLink: { fontSize: 15, fontWeight: '600', color: '#FFFFFF' },
  linkRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 6 },
  link: { fontSize: 15, fontWeight: '500', color: '#FFFFFF' },
  mKey: { fontSize: 11, fontWeight: '700', color: 'rgba(255,255,255,0.45)', letterSpacing: 1.2, textTransform: 'uppercase', marginTop: 10 },
  mVal: { fontSize: 15, fontWeight: '600', color: '#FFFFFF', marginTop: 2 },
  mLink: { fontSize: 15, fontWeight: '600', color: '#E1BEE7', marginTop: 2 },
  bottomBar: { borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.08)', paddingVertical: 18, paddingHorizontal: 24, alignItems: 'center' },
  copy: { fontSize: 12, fontWeight: '500', color: 'rgba(255,255,255,0.45)', textAlign: 'center', letterSpacing: 0.3 },
});
