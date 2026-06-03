/**
 * Contact Us — public page with company contact details and a quick
 * "email us" action. Linked from the landing page and footer.
 */
import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Linking, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../src/constants/colors';
import { COMPANY } from '../src/constants/company';
import MarketingHeader from '../src/components/marketing/MarketingHeader';
import MarketingFooter from '../src/components/marketing/MarketingFooter';

export default function ContactPage() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const cardWidth = Math.min(width - 32, 760);

  const Row = ({ icon, label, value, onPress }: { icon: any; label: string; value: string; onPress?: () => void }) => (
    <TouchableOpacity activeOpacity={onPress ? 0.6 : 1} onPress={onPress} style={styles.row}>
      <View style={styles.rowIcon}>
        <Ionicons name={icon} size={18} color={COLORS.primary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={[styles.rowValue, onPress && { color: COLORS.primary }]}>{value}</Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.root}>
      <MarketingHeader />
      <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.content} showsVerticalScrollIndicator>
        <View style={[styles.body, { width: cardWidth }]}>
          <TouchableOpacity style={styles.back} onPress={() => router.push('/')}>
            <Ionicons name="arrow-back" size={16} color={COLORS.primary} />
            <Text style={styles.backText}>Back to Home</Text>
          </TouchableOpacity>

          <Text style={styles.title}>Contact Us</Text>
          <Text style={styles.subtitle}>
            We'd love to hear from you. Reach the {COMPANY.product} team at {COMPANY.legalName} using the details below.
          </Text>

          <View style={styles.card}>
            <Row
              icon="business"
              label="Registered Office"
              value={COMPANY.addressLines.join('\n')}
            />
            <Row
              icon="call"
              label="Phone"
              value={COMPANY.phone}
              onPress={() => Linking.openURL(`tel:${COMPANY.phoneDial}`)}
            />
            <Row
              icon="mail"
              label="Email"
              value={COMPANY.email}
              onPress={() => Linking.openURL(`mailto:${COMPANY.email}`)}
            />
            <Row
              icon="globe"
              label="Website"
              value={COMPANY.website}
              onPress={() => Linking.openURL(COMPANY.websiteUrl)}
            />
          </View>

          <TouchableOpacity activeOpacity={0.85} onPress={() => Linking.openURL(`mailto:${COMPANY.email}`)}>
            <LinearGradient colors={GRADIENTS.accent} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.cta}>
              <Ionicons name="mail-outline" size={18} color="#FFFFFF" />
              <Text style={styles.ctaText}>Email our team</Text>
            </LinearGradient>
          </TouchableOpacity>

          <Text style={styles.hours}>Support hours: Monday–Friday, 10:00 AM – 6:00 PM IST</Text>
        </View>

        <MarketingFooter />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { alignItems: 'center', paddingTop: 28 },
  body: { paddingBottom: 48 },
  back: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 18 },
  backText: { fontSize: 14, fontWeight: '700', color: COLORS.primary },
  title: { fontSize: 30, fontWeight: '900', color: COLORS.textPrimary },
  subtitle: { fontSize: 15, lineHeight: 23, color: COLORS.textSecondary, marginTop: 10, marginBottom: 24 },
  card: { borderRadius: 16, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FBFBFD', overflow: 'hidden' },
  row: { flexDirection: 'row', gap: 14, alignItems: 'flex-start', padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  rowIcon: { width: 38, height: 38, borderRadius: 10, backgroundColor: '#F0EAF7', alignItems: 'center', justifyContent: 'center' },
  rowLabel: { fontSize: 12, fontWeight: '700', color: COLORS.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  rowValue: { fontSize: 14.5, color: COLORS.textPrimary, marginTop: 3, lineHeight: 21 },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 15, borderRadius: 12, marginTop: 22 },
  ctaText: { fontSize: 15, fontWeight: '800', color: '#FFFFFF' },
  hours: { fontSize: 12.5, color: COLORS.textMuted, marginTop: 16, textAlign: 'center' },
});
