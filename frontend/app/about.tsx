import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { COLORS } from '../src/constants/colors';
import { useCompany } from '../src/contexts/FontFamilyContext';
import MarketingHeader from '../src/components/marketing/MarketingHeader';
import MarketingFooter from '../src/components/marketing/MarketingFooter';
import { MARKETING_NAV } from '../src/components/marketing/marketingNav';
import Seo from '../src/components/Seo';

export default function AboutPage() {
  const company = useCompany();
  return (
    <View nativeID="jelcosMarketing" style={styles.root}>
      <Seo
        title={`About · ${company.product}`}
        description={`${company.product} is ${company.tagline}. Operated by ${company.legalName}.`}
        path="/about"
      />
      <MarketingHeader appearance="pill" links={MARKETING_NAV} />
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ flexGrow: 1 }} showsVerticalScrollIndicator>
        <View style={styles.hero}>
          <Text style={styles.kicker}>ABOUT</Text>
          <Text style={styles.h1}>{company.product}</Text>
          <Text style={styles.lead}>{company.tagline}</Text>
        </View>
        <View style={styles.sheet}>
        <View style={styles.body}>
          <Text style={styles.p}>
            {company.product} is a decision-making platform. You frame a choice, score the options by what matters to you, and leave with an action plan. AI insights are available when you ask for options, factors or an improvement plan.
          </Text>
          <Text style={styles.p}>{company.description}</Text>
          <Text style={styles.h2}>Who operates it</Text>
          <Text style={styles.p}>{company.legalName}</Text>
          {company.addressLines.map((line) => (
            <Text key={line} style={styles.addr}>{line}</Text>
          ))}
          <Text style={[styles.p, { marginTop: 16 }]}>Support: {company.email} · {company.phone}</Text>
          <Text style={styles.p}>Hours: {company.supportHours}</Text>
        </View>
        </View>
        <MarketingFooter />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0A1A4F' },
  hero: { paddingHorizontal: 24, paddingTop: 36, paddingBottom: 32, width: '100%', maxWidth: 1120, alignSelf: 'center' },
  kicker: { fontSize: 12, fontWeight: '800', color: '#F9A8D4', letterSpacing: 1.4 },
  h1: { fontSize: 40, fontWeight: '800', color: '#FFFFFF', marginTop: 8, letterSpacing: -0.6 },
  lead: { fontSize: 16, lineHeight: 26, color: 'rgba(255,255,255,0.75)', marginTop: 10 },
  sheet: { backgroundColor: '#FFFFFF', width: '100%' },
  body: { paddingHorizontal: 24, paddingVertical: 36, width: '100%', maxWidth: 1120, alignSelf: 'center' },
  h2: { fontSize: 22, fontWeight: '800', color: '#16132A', marginTop: 8, marginBottom: 8, maxWidth: 760 },
  p: { fontSize: 15.5, lineHeight: 25, color: COLORS.textSecondary, maxWidth: 760, marginBottom: 14 },
  addr: { fontSize: 15, lineHeight: 22, color: '#374151', maxWidth: 760 },
});
