/**
 * LegalShell — consistent layout for legal/policy pages.
 * Renders the marketing header, a readable content column with sections,
 * a "Last updated" stamp and the shared footer. Scrollable on all platforms.
 */
import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, useWindowDimensions, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { COLORS } from '../../constants/colors';
import { COMPANY, LegalDoc } from '../../constants/company';
import MarketingHeader from './MarketingHeader';
import MarketingFooter from './MarketingFooter';

export default function LegalShell({ doc }: { doc: LegalDoc }) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const contentWidth = Math.min(width - 32, 820);

  return (
    <View nativeID="jelcosMarketing" style={styles.root}>
      <MarketingHeader />
      <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator>
        <View style={[styles.body, { width: contentWidth }]}>
          <TouchableOpacity style={styles.back} onPress={() => router.push('/')}>
            <Ionicons name="arrow-back" size={16} color={COLORS.primary} />
            <Text style={styles.backText}>Back to Home</Text>
          </TouchableOpacity>

          <Text style={styles.title}>{doc.title}</Text>
          <Text style={styles.updated}>Last updated: {COMPANY.lastUpdated}</Text>

          {!!doc.intro && <Text style={styles.intro}>{doc.intro}</Text>}

          {doc.sections.map((sec, i) => (
            <View key={i} style={styles.section}>
              {!!sec.heading && <Text style={styles.heading}>{sec.heading}</Text>}
              {(sec.paragraphs || []).map((p, j) => (
                <Text key={j} style={styles.paragraph}>{p}</Text>
              ))}
              {(sec.bullets || []).map((b, j) => (
                <View key={j} style={styles.bulletRow}>
                  <View style={styles.dot} />
                  <Text style={styles.bulletText}>{b}</Text>
                </View>
              ))}
            </View>
          ))}

          <View style={styles.entityCard}>
            <Text style={styles.entityName}>{COMPANY.legalName}</Text>
            {COMPANY.addressLines.map((l, i) => (
              <Text key={i} style={styles.entityLine}>{l}</Text>
            ))}
            <Text style={styles.entityLine}>Phone: {COMPANY.phone}</Text>
            <Text style={styles.entityLine}>Email: {COMPANY.email}</Text>
            <Text style={styles.entityLine}>Website: {COMPANY.website}</Text>
          </View>
        </View>

        <MarketingFooter />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#FFFFFF' },
  scroll: { flex: 1 },
  scrollContent: { alignItems: 'center', paddingTop: 28 },
  body: { paddingBottom: 48 },
  back: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 18 },
  backText: { fontSize: 14, fontWeight: '700', color: COLORS.primary },
  title: { fontSize: 30, fontWeight: '900', color: COLORS.textPrimary, letterSpacing: 0.2 },
  updated: { fontSize: 12.5, color: COLORS.textMuted, marginTop: 6, marginBottom: 20 },
  intro: { fontSize: 15, lineHeight: 24, color: COLORS.textSecondary, marginBottom: 8 },
  section: { marginTop: 22 },
  heading: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 8 },
  paragraph: { fontSize: 14.5, lineHeight: 23, color: COLORS.textSecondary, marginBottom: 8 },
  bulletRow: { flexDirection: 'row', gap: 10, marginBottom: 7, paddingRight: 4 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: COLORS.accent, marginTop: 8 },
  bulletText: { flex: 1, fontSize: 14.5, lineHeight: 23, color: COLORS.textSecondary },
  entityCard: {
    marginTop: 34, padding: 18, borderRadius: 14, backgroundColor: '#F7F7FB',
    borderWidth: 1, borderColor: COLORS.border,
  },
  entityName: { fontSize: 15, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 8 },
  entityLine: { fontSize: 13, lineHeight: 20, color: COLORS.textSecondary },
});
