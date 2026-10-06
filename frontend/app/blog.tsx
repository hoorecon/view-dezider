/**
 * Blog — short original notes on how the product scores a choice.
 */
import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, useWindowDimensions, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../src/constants/colors';
import { useCompany } from '../src/contexts/FontFamilyContext';
import MarketingHeader from '../src/components/marketing/MarketingHeader';
import MarketingFooter from '../src/components/marketing/MarketingFooter';
import { MARKETING_NAV } from '../src/components/marketing/marketingNav';
import Seo from '../src/components/Seo';

const POSTS: {
  category: string;
  title: string;
  dek: string;
  body: string;
  minutes: string;
  colors: readonly [string, string];
}[] = [
  {
    category: 'SCORE',
    title: 'A score is clearer than a gut feeling',
    dek: 'My Dezider walks a choice through ten steps and ranks options by the weights you set.',
    body: 'When a decision sits in your head, the loudest factor usually wins. A Dezider makes the factors explicit, gives each one a weight, and shows a worth for every option. You can still disagree with the ranking. You can see why it came out that way.',
    minutes: '4 min read',
    colors: ['#E91E63', '#7E57C2'],
  },
  {
    category: 'PROS & CONS',
    title: 'Pros and cons, after the bias is named',
    dek: 'An 8-step pros and cons pass is there so the list is weighted, not just long.',
    body: 'A flat list of pros and cons treats every line as equal. The weighted pass asks which points actually matter, then uses that to reach a verdict you can explain to someone else.',
    minutes: '3 min read',
    colors: ['#1A237E', '#8E24AA'],
  },
  {
    category: 'ACTION PLAN',
    title: 'The decision is not finished at the verdict',
    dek: 'Action Center turns the result into who does what, and by when.',
    body: 'A clear winner still stalls if nobody owns the next step. After the score, SWOT or the pros and cons, the action plan names the person, the task and the date so the choice leaves the page.',
    minutes: '3 min read',
    colors: ['#4A148C', '#26C6DA'],
  },
];

function Cover({ colors, index }: { colors: readonly [string, string]; index: number }) {
  return (
    <LinearGradient colors={colors as unknown as readonly [string, string]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.cover}>
      <View style={[styles.blob, index === 0 && styles.blobA, index === 1 && styles.blobB, index === 2 && styles.blobC]} />
      <View style={[styles.blobSmall, index === 1 && { left: 24, bottom: 18 }]} />
    </LinearGradient>
  );
}

export default function BlogPage() {
  const company = useCompany();
  const { width } = useWindowDimensions();
  const cols = width >= 1020 ? 3 : width >= 720 ? 2 : 1;
  const basis = cols === 3 ? '31.5%' : cols === 2 ? '47%' : '100%';
  const [open, setOpen] = React.useState<string | null>(null);

  return (
    <View nativeID="jelcosMarketing" style={styles.root}>
      <Seo
        title={`Blog · ${company.product}`}
        description={`Notes on deciding with ${company.product}: weighted scores, pros and cons, and action plans.`}
        path="/blog"
      />
      <MarketingHeader appearance="light" links={MARKETING_NAV} />
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ flexGrow: 1 }} showsVerticalScrollIndicator>
        <View style={styles.hero}>
          <Text style={styles.h1}>
            Notes on a choice{'\n'}
            <Text style={styles.h1Accent}>that has a score</Text>
          </Text>
          <Text style={styles.lead}>Short writing on the modules in {company.product}. Open a card to read it.</Text>
        </View>
        <View style={styles.grid}>
          {POSTS.map((post, index) => {
            const expanded = open === post.title;
            return (
              <TouchableOpacity
                key={post.title}
                activeOpacity={0.92}
                onPress={() => setOpen(expanded ? null : post.title)}
                style={[styles.card, { flexBasis: basis }]}
              >
                <Cover colors={post.colors} index={index} />
                <View style={styles.cardBody}>
                  <Text style={styles.category}>{post.category}</Text>
                  <Text style={styles.title}>{post.title}</Text>
                  <Text style={styles.dek}>{post.dek}</Text>
                  {expanded ? <Text style={styles.body}>{post.body}</Text> : null}
                  <View style={styles.foot}>
                    <Text style={styles.minutes}>{post.minutes}</Text>
                    <Ionicons name={expanded ? 'remove' : 'arrow-forward'} size={16} color="#1F2437" />
                  </View>
                </View>
              </TouchableOpacity>
            );
          })}
        </View>
        <MarketingFooter />
      </ScrollView>
    </View>
  );
}

const shadow = Platform.OS === 'web'
  ? { boxShadow: '0 16px 36px rgba(26, 35, 126, 0.08)' } as any
  : { elevation: 2 };

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F6F3FB' },
  hero: { width: '100%', maxWidth: 1120, alignSelf: 'center', paddingHorizontal: 24, paddingTop: 36, paddingBottom: 8 },
  h1: { fontSize: 48, lineHeight: 54, fontWeight: '800', color: '#12141F', letterSpacing: -1.3, maxWidth: 720 },
  h1Accent: Platform.OS === 'web' ? {
    color: '#E91E63',
    backgroundImage: 'linear-gradient(100deg, #E91E63 0%, #AB47BC 50%, #5C6BC0 100%)',
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  } as any : { color: '#E91E63' },
  lead: { fontSize: 16, lineHeight: 24, color: '#5C6378', marginTop: 14, maxWidth: 520 },
  grid: {
    width: '100%', maxWidth: 1120, alignSelf: 'center',
    paddingHorizontal: 24, paddingTop: 28, paddingBottom: 56,
    flexDirection: 'row', flexWrap: 'wrap', gap: 18, alignItems: 'flex-start',
  },
  card: { backgroundColor: '#FFFFFF', borderRadius: 24, overflow: 'hidden', flexGrow: 1, ...shadow },
  cover: { height: 168, position: 'relative', overflow: 'hidden' },
  blob: { position: 'absolute', width: 180, height: 180, borderRadius: 90, backgroundColor: 'rgba(255,255,255,0.18)', top: -40, right: -20 },
  blobA: { width: 140, height: 220, borderRadius: 28, top: 20, right: 30, transform: [{ rotate: '18deg' }] },
  blobB: { width: 160, height: 160, borderRadius: 80, top: -20, left: 40, backgroundColor: 'rgba(255,255,255,0.16)' },
  blobC: { width: 120, height: 120, borderRadius: 24, bottom: -20, left: 36, top: undefined },
  blobSmall: { position: 'absolute', width: 48, height: 48, borderRadius: 24, backgroundColor: 'rgba(255,255,255,0.28)', right: 28, bottom: 16 },
  cardBody: { padding: 20 },
  category: { fontSize: 11, fontWeight: '800', letterSpacing: 1.1, color: '#8E24AA' },
  title: { fontSize: 20, lineHeight: 26, fontWeight: '800', color: '#12141F', marginTop: 10, letterSpacing: -0.3 },
  dek: { fontSize: 14.5, lineHeight: 22, color: COLORS.primaryDark, marginTop: 8, fontWeight: '600' },
  body: { fontSize: 14.5, lineHeight: 23, color: '#5C6378', marginTop: 10 },
  foot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 16 },
  minutes: { fontSize: 12, fontWeight: '700', color: '#9AA0B4', letterSpacing: 0.4 },
});
