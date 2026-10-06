/**
 * Case studies — worked examples of decisions scored in the product.
 * Sample layouts, not client results.
 */
import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, useWindowDimensions, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../src/constants/colors';
import { useCompany } from '../src/contexts/FontFamilyContext';
import MarketingHeader from '../src/components/marketing/MarketingHeader';
import { MARKETING_NAV } from '../src/components/marketing/marketingNav';
import MarketingFooter from '../src/components/marketing/MarketingFooter';
import Seo from '../src/components/Seo';

const CASES: {
  kicker: string;
  title: string;
  body: string;
  metric: string;
  metricLabel: string;
  colors: readonly [string, string];
  motif: 'bars' | 'rings' | 'blocks';
}[] = [
  {
    kicker: 'WORKED EXAMPLE · CAREER',
    title: 'A new role, scored against staying',
    body: 'Income was the loud part. Once family and location sat on the same scale, “Stay and grow” led.',
    metric: '72%',
    metricLabel: 'SAMPLE WORTH',
    colors: ['#1A237E', '#7B1FA2'],
    motif: 'bars',
  },
  {
    kicker: 'WORKED EXAMPLE · A PURCHASE',
    title: 'A phone shortlist under ₹50k',
    body: 'The factors you set outrank the loudest ad. The shortlist gets a worth, not a slogan.',
    metric: '1 list',
    metricLabel: 'YOUR FACTORS',
    colors: ['#E91E63', '#5E35B1'],
    motif: 'rings',
  },
  {
    kicker: 'WORKED EXAMPLE · A MOVE',
    title: 'A city change in one decision',
    body: 'Health, career, finance and relationships stay in one score instead of four separate notes.',
    metric: '4',
    metricLabel: 'LIFE AREAS',
    colors: ['#4A148C', '#00ACC1'],
    motif: 'blocks',
  },
];

function Art({ colors, motif }: { colors: readonly [string, string]; motif: 'bars' | 'rings' | 'blocks' }) {
  return (
    <LinearGradient colors={colors as unknown as readonly [string, string]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.art}>
      {motif === 'bars' && (
        <>
          <View style={[styles.shape, { width: 54, height: 140, left: 28, bottom: 24, backgroundColor: 'rgba(255,255,255,0.18)' }]} />
          <View style={[styles.shape, { width: 54, height: 96, left: 96, bottom: 24, backgroundColor: 'rgba(255,255,255,0.28)' }]} />
          <View style={[styles.shape, { width: 54, height: 180, left: 164, bottom: 24, backgroundColor: 'rgba(255,255,255,0.14)' }]} />
        </>
      )}
      {motif === 'rings' && (
        <>
          <View style={styles.ring} />
          <View style={styles.ringInner} />
        </>
      )}
      {motif === 'blocks' && (
        <>
          <View style={[styles.block, { width: 120, height: 120, top: 28, left: 24, backgroundColor: 'rgba(255,255,255,0.16)' }]} />
          <View style={[styles.block, { width: 86, height: 86, bottom: 28, right: 28, backgroundColor: 'rgba(255,255,255,0.22)' }]} />
          <View style={[styles.block, { width: 48, height: 48, top: 48, right: 48, borderRadius: 24, backgroundColor: 'rgba(255,255,255,0.3)' }]} />
        </>
      )}
    </LinearGradient>
  );
}

export default function CaseStudiesPage() {
  const router = useRouter();
  const company = useCompany();
  const { width } = useWindowDimensions();
  const two = width >= 1080;
  const split = width >= 720;

  return (
    <View nativeID="jelcosMarketing" style={styles.root}>
      <Seo
        title={`Case Studies · ${company.product}`}
        description={`Worked examples of decisions scored in ${company.product}: a career choice, a purchase and a move. Sample layouts, not client results.`}
        path="/case-studies"
      />
      <MarketingHeader appearance="light" links={MARKETING_NAV} />
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ flexGrow: 1 }} showsVerticalScrollIndicator>
        <View style={styles.hero}>
          <View style={{ flex: 1, minWidth: 280 }}>
            <Text style={styles.h1}>
              Worked examples.{'\n'}
              <Text style={styles.h1Accent}>A score you can explain.</Text>
            </Text>
          </View>
          <TouchableOpacity activeOpacity={0.9} onPress={() => { if (typeof window !== 'undefined') window.location.assign('/#demo'); }} style={styles.deckBtn}>
            <Text style={styles.deckText}>Book a walkthrough</Text>
            <Ionicons name="arrow-forward" size={16} color={COLORS.primaryDark} />
          </TouchableOpacity>
        </View>

        <Text style={styles.note}>
          Sample layouts of decisions you can run in {company.product}. They are not client results.
        </Text>

        <View style={styles.grid}>
          {CASES.map((item, index) => (
            <View key={item.title} style={[styles.card, two && index < 2 && styles.cardHalf, (index === 2 || !two) && styles.cardFull, split && styles.cardWide]}>
              <View style={[styles.artWrap, split && styles.artWrapWide]}>
                <Art colors={item.colors} motif={item.motif} />
              </View>
              <View style={styles.copy}>
                <Text style={styles.kicker}>{item.kicker}</Text>
                <Text style={styles.title}>{item.title}</Text>
                <Text style={styles.body}>{item.body}</Text>
                <View style={styles.metricRow}>
                  <View>
                    <Text style={styles.metric}>{item.metric}</Text>
                    <Text style={styles.metricLabel}>{item.metricLabel}</Text>
                  </View>
                  <TouchableOpacity style={styles.arrow} onPress={() => router.push('/auth/register')} accessibilityLabel="Start with this kind of decision">
                    <Ionicons name="arrow-forward" size={18} color="#1F2437" />
                  </TouchableOpacity>
                </View>
              </View>
            </View>
          ))}
        </View>
        <MarketingFooter />
      </ScrollView>
    </View>
  );
}

const shadow = Platform.OS === 'web'
  ? { boxShadow: '0 18px 40px rgba(26, 35, 126, 0.08)' } as any
  : { elevation: 3 };

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F6F3FB' },
  hero: {
    width: '100%', maxWidth: 1120, alignSelf: 'center',
    paddingHorizontal: 24, paddingTop: 28, paddingBottom: 8,
    flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-end', gap: 18,
  },
  h1: { fontSize: 52, lineHeight: 58, fontWeight: '800', color: '#12141F', letterSpacing: -1.4 },
  h1Accent: Platform.OS === 'web' ? {
    color: '#7C4DFF',
    backgroundImage: 'linear-gradient(100deg, #E91E63 0%, #8E24AA 55%, #5C6BC0 100%)',
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  } as any : { color: '#8E24AA' },
  deckBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#FFFFFF', borderRadius: 999, paddingHorizontal: 18, paddingVertical: 12,
    borderWidth: 1, borderColor: 'rgba(26,35,126,0.08)', marginBottom: 8,
  },
  deckText: { fontSize: 14, fontWeight: '700', color: COLORS.primaryDark },
  note: {
    width: '100%', maxWidth: 1120, alignSelf: 'center',
    paddingHorizontal: 24, marginTop: 8, marginBottom: 8,
    fontSize: 14, color: '#6B7280',
  },
  grid: {
    width: '100%', maxWidth: 1120, alignSelf: 'center',
    paddingHorizontal: 24, paddingTop: 12, paddingBottom: 48,
    flexDirection: 'row', flexWrap: 'wrap', gap: 18,
  },
  card: {
    backgroundColor: '#FFFFFF', borderRadius: 28, overflow: 'hidden',
    flexDirection: 'column', ...shadow,
  },
  cardHalf: { flexBasis: '48%', flexGrow: 1 },
  cardFull: { flexBasis: '100%' },
  cardWide: { flexDirection: 'row' },
  artWrap: { height: 200, width: '100%' },
  artWrapWide: { width: '42%', height: 'auto', minHeight: 240 },
  art: { flex: 1, position: 'relative', overflow: 'hidden' },
  shape: { position: 'absolute', borderRadius: 16 },
  ring: {
    position: 'absolute', width: 220, height: 220, borderRadius: 110,
    borderWidth: 28, borderColor: 'rgba(255,255,255,0.2)', top: -30, right: -20,
  },
  ringInner: {
    position: 'absolute', width: 90, height: 90, borderRadius: 45,
    backgroundColor: 'rgba(255,255,255,0.22)', bottom: 28, left: 28,
  },
  block: { position: 'absolute', borderRadius: 22 },
  copy: { flex: 1, padding: 22, justifyContent: 'center' },
  kicker: { fontSize: 11, fontWeight: '800', letterSpacing: 1.1, color: '#8E24AA' },
  title: { fontSize: 22, lineHeight: 28, fontWeight: '800', color: '#12141F', marginTop: 10, letterSpacing: -0.4 },
  body: { fontSize: 14.5, lineHeight: 22, color: '#5C6378', marginTop: 8 },
  metricRow: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', marginTop: 18 },
  metric: { fontSize: 36, fontWeight: '800', color: '#8E24AA', letterSpacing: -1 },
  metricLabel: { fontSize: 11, fontWeight: '800', letterSpacing: 1, color: '#9AA0B4', marginTop: 2 },
  arrow: {
    width: 40, height: 40, borderRadius: 20, borderWidth: 1, borderColor: '#E7E3F0',
    alignItems: 'center', justifyContent: 'center',
  },
});
