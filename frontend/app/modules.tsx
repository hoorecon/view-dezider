/**
 * Public modules page — the product catalog grouped the same way as the app.
 */
import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, useWindowDimensions, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../src/constants/colors';
import { useCompany } from '../src/contexts/FontFamilyContext';
import MarketingHeader from '../src/components/marketing/MarketingHeader';
import MarketingFooter from '../src/components/marketing/MarketingFooter';
import { MARKETING_NAV } from '../src/components/marketing/marketingNav';
import Seo from '../src/components/Seo';
import { DEFAULT_LAYOUT, TILE_META } from '../src/config/dashboardTiles';

const SKIP = new Set(['inbox', 'notifications', 'analytics', 'subscription', 'my_earnings']);
const accentGradient = GRADIENTS.accent as unknown as readonly [string, string];

export default function ModulesPage() {
  const router = useRouter();
  const company = useCompany();
  const { width } = useWindowDimensions();
  const cols = width >= 1020 ? 3 : width >= 720 ? 2 : 1;
  const basis = cols === 3 ? '31.5%' : cols === 2 ? '47.5%' : '100%';

  const groups = DEFAULT_LAYOUT.map((section) => ({
    ...section,
    tiles: section.tiles.filter((id) => TILE_META[id] && !SKIP.has(id)),
  })).filter((section) => section.tiles.length > 0);

  return (
    <View nativeID="jelcosMarketing" style={styles.root}>
      <Seo
        title={`Modules · ${company.product}`}
        description={`${company.product} modules for decisions, goals, life areas and follow-through — My Dezider, Pros & Cons, SWOT, Action Center and more.`}
        path="/modules"
      />
      <MarketingHeader appearance="pill" links={MARKETING_NAV} />
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ flexGrow: 1 }} showsVerticalScrollIndicator>
        <View style={styles.hero}>
          <Text style={styles.kicker}>MODULES</Text>
          <Text style={styles.h1}>Every module in {company.product}</Text>
          <Text style={styles.lead}>
            The same product groups you get after you sign in. Start free, then open the module that matches the decision in front of you.
          </Text>
          <TouchableOpacity activeOpacity={0.9} onPress={() => router.push('/auth/register')} style={{ marginTop: 22 }}>
            <LinearGradient colors={accentGradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.cta}>
              <Text style={styles.ctaText}>Get started free</Text>
              <Ionicons name="arrow-forward" size={16} color="#FFFFFF" />
            </LinearGradient>
          </TouchableOpacity>
        </View>

        {groups.map((section) => (
          <View key={section.id} style={styles.group}>
            <Text style={styles.groupTitle}>{section.name}</Text>
            <View style={styles.grid}>
              {section.tiles.map((id) => {
                const tile = TILE_META[id];
                return (
                  <View key={id} style={[styles.card, { flexBasis: basis }]}>
                    <View style={styles.iconWell}>
                      <Ionicons name={tile.icon as any} size={18} color={COLORS.primary} />
                    </View>
                    <Text style={styles.cardTitle}>{tile.title}</Text>
                    <Text style={styles.cardDesc}>{tile.subtitle}</Text>
                  </View>
                );
              })}
            </View>
          </View>
        ))}
        <MarketingFooter />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#070B1C' },
  hero: { paddingHorizontal: 24, paddingTop: 36, paddingBottom: 40, width: '100%', maxWidth: 1120, alignSelf: 'center' },
  kicker: { fontSize: 12, fontWeight: '800', color: '#F9A8D4', letterSpacing: 1.4 },
  h1: { fontSize: 40, fontWeight: '800', color: '#FFFFFF', letterSpacing: -0.8, marginTop: 10, lineHeight: 48 },
  lead: { fontSize: 16, lineHeight: 26, color: 'rgba(255,255,255,0.75)', marginTop: 12, maxWidth: 640 },
  cta: { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', paddingHorizontal: 18, paddingVertical: 12, borderRadius: 999 },
  ctaText: { color: '#FFFFFF', fontWeight: '800', fontSize: 14 },
  group: { backgroundColor: '#FFFFFF', paddingHorizontal: 24, paddingVertical: 28 },
  groupTitle: { fontSize: 22, fontWeight: '800', color: '#16132A', maxWidth: 1120, width: '100%', alignSelf: 'center', letterSpacing: -0.3 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, marginTop: 16, maxWidth: 1120, width: '100%', alignSelf: 'center' },
  card: {
    flexGrow: 1, minWidth: 220, backgroundColor: '#FFFFFF', borderRadius: 16, padding: 18,
    borderWidth: 1, borderColor: '#EFE8F6',
    ...(Platform.OS === 'web' ? { boxShadow: '0 10px 24px rgba(26, 35, 126, 0.05)' } as any : { elevation: 1 }),
  },
  iconWell: { width: 40, height: 40, borderRadius: 12, backgroundColor: '#F6EEF8', alignItems: 'center', justifyContent: 'center', marginBottom: 12 },
  cardTitle: { fontSize: 16, fontWeight: '800', color: '#16132A', marginBottom: 4 },
  cardDesc: { fontSize: 13.5, lineHeight: 20, color: COLORS.textSecondary },
});
