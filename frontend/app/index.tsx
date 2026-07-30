import React, { useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  ImageBackground, Image, useWindowDimensions, Platform, TextInput,
} from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import * as Linking from 'expo-linking';
import { useAuthStore } from '../src/store/authStore';
import { getPostAuthRoute } from '../src/utils/postAuthRedirect';
import { COLORS, GRADIENTS } from '../src/constants/colors';
import { useCompany } from '../src/contexts/FontFamilyContext';
import MarketingHeader from '../src/components/marketing/MarketingHeader';
import MarketingFooter from '../src/components/marketing/MarketingFooter';
import Seo from '../src/components/Seo';

const HERO_IMG = 'https://images.unsplash.com/photo-1653549893012-b8b4fbe97630?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjd8MHwxfHNlYXJjaHwzfHxhYnN0cmFjdCUyMEFJJTIwdGVjaG5vbG9neXxlbnwwfHx8Ymx1ZXwxNzgwNDk3MjQ0fDA&ixlib=rb-4.1.0&q=85';
const FEATURE_IMG = 'https://images.unsplash.com/photo-1720548168939-0f41625c2906?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA2ODl8MHwxfHNlYXJjaHw0fHxleGVjdXRpdmUlMjBkZWNpc2lvbnxlbnwwfHx8Ymx1ZXwxNzgwNDk3MjQ0fDA&ixlib=rb-4.1.0&q=85';

const FEATURES = [
  { icon: 'git-branch', title: 'My Dezider', desc: 'A guided 10-step engine that scores every option by what truly matters to you.' },
  { icon: 'swap-horizontal', title: 'Pros & Cons', desc: 'Weighted, 8-step pros & cons analysis that removes gut-feel bias.' },
  { icon: 'grid', title: 'SWOT Analysis', desc: 'Map strengths, weaknesses, opportunities & threats into a clear verdict.' },
  { icon: 'sparkles', title: 'AI Insights', desc: 'AI-assisted options, factors and improvement plans — on demand.' },
  { icon: 'checkmark-done-circle', title: 'Action Center', desc: 'Turn any decision into a Who · What · By-when action plan, automatically.' },
  { icon: 'compass', title: 'Life-Area Balance', desc: 'Align choices across health, career, finance, relationships and more.' },
];

const STEPS = [
  { n: '1', icon: 'create', title: 'Frame your choice', desc: 'Capture the decision, the options and the factors that matter.' },
  { n: '2', icon: 'analytics', title: 'Analyze with clarity', desc: 'Weighted scoring, SWOT, MPPS projections and AI insights do the heavy lifting.' },
  { n: '3', icon: 'rocket', title: 'Act with confidence', desc: 'Auto-generate an action plan and track it to completion.' },
];

export default function Index() {
  const router = useRouter();
  const company = useCompany();
  const { isLoading, isAuthenticated, checkAuth, loginWithGoogle } = useAuthStore();
  const { width } = useWindowDimensions();
  const isWide = width >= 900;
  const isMid = width >= 640;
  const featureCols = isWide ? 3 : isMid ? 2 : 1;

  // Rotating headline word (fwdslash.ai-style animated typing effect).
  const rotatingWords = ['Decisions', 'Choices', 'Career Moves', 'Investments', 'Life'];
  const [rotatingIdx, setRotatingIdx] = React.useState(0);
  const [typedWord, setTypedWord] = React.useState('');
  React.useEffect(() => {
    const full = rotatingWords[rotatingIdx];
    let i = 0;
    let deleting = false;
    const tick = () => {
      if (!deleting) {
        i += 1;
        setTypedWord(full.slice(0, i));
        if (i === full.length) { deleting = true; setTimeout(tick, 1600); return; }
      } else {
        i -= 1;
        setTypedWord(full.slice(0, i));
        if (i === 0) { setRotatingIdx((v) => (v + 1) % rotatingWords.length); return; }
      }
      setTimeout(tick, deleting ? 60 : 120);
    };
    const id = setTimeout(tick, 300);
    return () => clearTimeout(id);
  }, [rotatingIdx]);

  const [heroPrompt, setHeroPrompt] = React.useState('');
  const submitHeroPrompt = () => {
    // Route logged-out visitors into signup with the prompt preserved so the
    // first-experience feels product-led (they're already framing a decision).
    const q = heroPrompt.trim();
    router.push(q ? `/auth/register?ref=hero&q=${encodeURIComponent(q)}` : '/auth/register?ref=hero' as any);
  };
  const suggestedPrompts = [
    'Should I quit my job for a startup?',
    'Which phone should I buy under ₹50k?',
    'Should I move to a new city?',
    'Which MBA offer to pick?',
  ];

  // Admin-selectable homepage variant. Defaults to 'modern' if the API is
  // unreachable. Query-string override (?variant=classic) lets admin preview
  // without changing the persisted default.
  const [heroVariant, setHeroVariant] = React.useState<'modern' | 'classic'>('modern');
  React.useEffect(() => {
    // URL override — admin preview link
    if (Platform.OS === 'web') {
      const qp = new URLSearchParams(window.location.search).get('variant');
      if (qp === 'classic' || qp === 'modern') { setHeroVariant(qp); return; }
    }
    fetch((process.env.EXPO_PUBLIC_BACKEND_URL || '') + '/api/home-variant')
      .then((r) => r.json())
      .then((d) => { if (d?.variant === 'classic') setHeroVariant('classic'); })
      .catch(() => { /* keep default */ });
  }, []);

  // ── OAuth deep-link / hash handling (unchanged behaviour) ──
  useEffect(() => {
    const handleDeepLink = async (event: { url: string }) => {
      const url = event.url;
      if (url.includes('session_id=')) {
        const sessionId = url.split('session_id=')[1]?.split('&')[0];
        if (sessionId) {
          try {
            await loginWithGoogle(sessionId);
            router.replace((await getPostAuthRoute()) as any);
          } catch {
            router.replace('/auth/login');
          }
        }
      }
    };
    Linking.getInitialURL().then((url) => { if (url) handleDeepLink({ url }); });
    const subscription = Linking.addEventListener('url', handleDeepLink);
    return () => subscription.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const hash = window.location.hash;
      if (hash.includes('session_id=')) {
        const sessionId = hash.split('session_id=')[1]?.split('&')[0];
        // Strip the callback params from the URL IMMEDIATELY (before any async
        // work) so a refresh/back never replays a consumed OAuth state — this
        // is what produced the "Invalid state parameter" error.
        window.history.replaceState(null, '', window.location.pathname);
        if (sessionId) {
          loginWithGoogle(sessionId).then(async () => {
            router.replace((await getPostAuthRoute()) as any);
          }).catch(() => router.replace('/auth/login'));
          return;
        }
      }
    }
    // Authenticated users skip the landing and go straight to the app.
    if (!isLoading && isAuthenticated) {
      router.replace('/(tabs)');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, isAuthenticated]);

  // While auth is resolving, or for authenticated users mid-redirect → spinner.
  // NOTE: during static web prerender (SSG, no `window`) we must NOT show the
  // spinner — otherwise crawlers (e.g. payment-gateway verification bots) see an
  // empty splash instead of the marketing content. Render the landing on the
  // server; the client keeps the exact same spinner/redirect behaviour.
  const isServerRender = typeof window === 'undefined';
  if (!isServerRender && (isLoading || isAuthenticated)) {
    return (
      <LinearGradient colors={GRADIENTS.primary} style={styles.splash} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
        <ActivityIndicator color={COLORS.white} size="large" />
        <Text style={styles.splashText}>{company.product}</Text>
      </LinearGradient>
    );
  }

  // ── Public landing page ──
  return (
    <View nativeID="jelcosMarketing" style={styles.root}>
      <Seo
        title="JELCOS AI — Make every life choice with clarity & confidence"
        description="JELCOS AI gives you structured decision tools — Dezider, weighted Pros & Cons, SWOT — plus AI insights that turn complex life and work choices into clear, actionable plans."
        path="/"
      />
      <MarketingHeader />
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ flexGrow: 1 }} showsVerticalScrollIndicator>
        {/* HERO — variant chosen by admin via /admin/home-variant */}
        {heroVariant === 'classic' ? (
          <ImageBackground source={{ uri: HERO_IMG }} style={styles.hero} resizeMode="cover">
            <LinearGradient
              colors={['rgba(26,35,126,0.86)', 'rgba(94,53,177,0.88)', 'rgba(142,36,170,0.92)']}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={StyleSheet.absoluteFill as any}
            />
            <View style={[styles.heroInner, { paddingVertical: isWide ? 88 : 56 }]}>
              <View style={styles.eyebrow}>
                <Ionicons name="sparkles" size={13} color="#FFD8F2" />
                <Text style={styles.eyebrowText}>Powered by AI</Text>
              </View>
              <Text style={[styles.h1, { fontSize: isWide ? 48 : isMid ? 38 : 30 }]}>
                Make every life choice with clarity &amp; confidence
              </Text>
              <Text style={styles.heroSub}>
                {company.product} — {company.tagline}. Structured decision tools and AI insights
                that turn complex choices into clear, actionable plans.
              </Text>
              <View style={styles.heroCtas}>
                <TouchableOpacity activeOpacity={0.9} onPress={() => router.push('/auth/register')}>
                  <View style={styles.heroPrimary}>
                    <Text style={styles.heroPrimaryText}>Get started free</Text>
                    <Ionicons name="arrow-forward" size={18} color={COLORS.primary} />
                  </View>
                </TouchableOpacity>
                <TouchableOpacity activeOpacity={0.9} style={styles.heroSecondary} onPress={() => router.push('/auth/login')}>
                  <Text style={styles.heroSecondaryText}>Sign in</Text>
                </TouchableOpacity>
              </View>
              <Text style={styles.heroNote}>No credit card required to begin · Cancel anytime</Text>
            </View>
          </ImageBackground>
        ) : (
        <View style={[styles.hero2, { paddingVertical: isWide ? 96 : 60 }]}>
          {/* Faint graph-paper grid via SVG data URI — evokes "product-y" polish */}
          <View style={styles.hero2Grid as any} pointerEvents="none" />
          <View style={styles.hero2Inner}>
            <View style={styles.pillBadge}>
              <Ionicons name="sparkles" size={13} color="#4F46E5" />
              <Text style={styles.pillBadgeT}>Decision Intelligence for Modern Lives</Text>
            </View>

            <Text style={[styles.hero2H1, { fontSize: isWide ? 76 : isMid ? 54 : 40 }]}>
              Make better{'\n'}
              <Text style={styles.hero2H1Accent}>{typedWord}</Text>
              <Text style={styles.hero2Cursor}>|</Text>
              {' '}in minutes.
            </Text>

            <Text style={[styles.hero2Sub, { fontSize: isWide ? 20 : 16, maxWidth: 780 }]}>
              JELCOS AI gives you structured decision engines — MyDezider, weighted Pros &amp; Cons,
              SWOT, Solution Finder — plus GPT-grade insights that turn any complex life or work
              choice into a clear, actionable plan.
            </Text>

            {/* Chat-like hero input (product-led first touch) */}
            <View style={[styles.hero2Chat, { maxWidth: 760 }]}>
              <View style={styles.hero2ChatIcon}><Ionicons name="chatbubble-ellipses" size={16} color="#4F46E5" /></View>
              <TextInput
                style={styles.hero2ChatInput}
                placeholder="Type any decision you're facing…  e.g. Should I take the ₹35L offer?"
                placeholderTextColor="#94A3B8"
                value={heroPrompt}
                onChangeText={setHeroPrompt}
                onSubmitEditing={submitHeroPrompt}
                returnKeyType="send"
              />
              <TouchableOpacity onPress={submitHeroPrompt} style={styles.hero2ChatSend} accessibilityLabel="Start decision">
                <Ionicons name="arrow-up" size={18} color="#fff" />
              </TouchableOpacity>
            </View>

            {/* Suggested prompt chips */}
            <View style={styles.hero2Chips}>
              {suggestedPrompts.map((p) => (
                <TouchableOpacity key={p} style={styles.hero2Chip} onPress={() => { setHeroPrompt(p); }}>
                  <Text style={styles.hero2ChipT}>{p}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Secondary CTAs */}
            <View style={styles.hero2Ctas}>
              <TouchableOpacity onPress={() => router.push('/auth/register')} style={styles.hero2Primary}>
                <Text style={styles.hero2PrimaryT}>Start Deciding Free</Text>
                <Ionicons name="arrow-forward" size={16} color="#fff" />
              </TouchableOpacity>
              <TouchableOpacity onPress={() => router.push('/quiz')} style={styles.hero2Secondary}>
                <Text style={styles.hero2SecondaryT}>Take the 2-minute Style Quiz</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.hero2Note}>No credit card · Free forever tier · Cancel anytime</Text>
          </View>
        </View>
        )}

        {/* TRUSTED-BY strip (only for modern variant) */}
        {heroVariant === 'modern' && (
        <View style={styles.trustedStrip}>
          <Text style={styles.trustedT}>Trusted by founders, executives and creators across India &amp; the diaspora</Text>
          <View style={styles.trustedLogos}>
            {['Tamilpreneur', 'VEALES', 'Bloom Hub', 'IIM Alumni', 'Chennai Angels'].map((n) => (
              <Text key={n} style={styles.trustedLogo}>{n}</Text>
            ))}
          </View>
        </View>
        )}

        {/* STAT STRIP */}
        <View style={[styles.stats, !isMid && { flexDirection: 'column', gap: 14 }]}>
          {[
            { k: '6+', v: 'Decision frameworks' },
            { k: '10', v: 'Life areas covered' },
            { k: 'AI', v: 'Guided insights' },
            { k: '100%', v: 'Your data, private' },
          ].map((s) => (
            <View key={s.v} style={styles.stat}>
              <Text style={styles.statK}>{s.k}</Text>
              <Text style={styles.statV}>{s.v}</Text>
            </View>
          ))}
        </View>

        {/* FEATURES */}
        <View style={styles.section}>
          <Text style={styles.kicker}>WHAT YOU GET</Text>
          <Text style={styles.h2}>Everything you need to decide well</Text>
          <Text style={styles.lead}>
            A complete toolkit that brings structure, evidence and AI to the decisions that shape your life and work.
          </Text>
          <View style={styles.grid}>
            {FEATURES.map((f) => (
              <View key={f.title} style={[styles.featureCard, { width: `${100 / featureCols - 2}%` }]}>
                <View style={styles.featureIcon}>
                  <Ionicons name={f.icon as any} size={22} color={COLORS.primary} />
                </View>
                <Text style={styles.featureTitle}>{f.title}</Text>
                <Text style={styles.featureDesc}>{f.desc}</Text>
              </View>
            ))}
          </View>
        </View>

        {/* HOW IT WORKS — with feature image */}
        <View style={[styles.section, styles.sectionAlt]}>
          <Text style={styles.kicker}>HOW IT WORKS</Text>
          <Text style={styles.h2}>From dilemma to decision in three steps</Text>
          <View style={[styles.howRow, isWide && { flexDirection: 'row', alignItems: 'center', gap: 36 }]}>
            <View style={{ flex: 1 }}>
              {STEPS.map((s) => (
                <View key={s.n} style={styles.step}>
                  <LinearGradient colors={GRADIENTS.accent} style={styles.stepNum} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
                    <Text style={styles.stepNumText}>{s.n}</Text>
                  </LinearGradient>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.stepTitle}>{s.title}</Text>
                    <Text style={styles.stepDesc}>{s.desc}</Text>
                  </View>
                </View>
              ))}
            </View>
            {isWide && (
              <Image source={{ uri: FEATURE_IMG }} style={styles.howImg} resizeMode="cover" />
            )}
          </View>
        </View>

        {/* PRICING TEASER */}
        <View style={styles.section}>
          <Text style={styles.kicker}>SIMPLE PRICING</Text>
          <Text style={styles.h2}>Start free. Upgrade when you&apos;re ready.</Text>
          <View style={[styles.priceRow, isMid && { flexDirection: 'row', gap: 18 }]}>
            <View style={[styles.priceCard, isMid && { flex: 1 }]}>
              <Ionicons name="infinite" size={24} color={COLORS.primary} />
              <Text style={styles.priceTitle}>Subscription Plans</Text>
              <Text style={styles.priceDesc}>
                Unlock full access to all decision frameworks and AI features, billed monthly or annually. Cancel anytime.
              </Text>
            </View>
            <View style={[styles.priceCard, isMid && { flex: 1 }]}>
              <Ionicons name="flash" size={24} color={COLORS.accent} />
              <Text style={styles.priceTitle}>Pay-as-you-go Credits</Text>
              <Text style={styles.priceDesc}>
                Prefer flexibility? Buy one-time credits and spend them on premium AI actions whenever you need them.
              </Text>
            </View>
          </View>
          <Text style={styles.priceNote}>Secure payments processed by Razorpay.</Text>
        </View>

        {/* CTA BAND */}
        <LinearGradient colors={GRADIENTS.primary} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.ctaBand}>
          <Text style={styles.ctaTitle}>Ready to make your next decision a great one?</Text>
          <Text style={styles.ctaSub}>Join {company.product} and bring clarity to the choices that matter.</Text>
          <TouchableOpacity activeOpacity={0.9} onPress={() => router.push('/auth/register')}>
            <View style={styles.ctaBtn}>
              <Text style={styles.ctaBtnText}>Create your free account</Text>
              <Ionicons name="arrow-forward" size={18} color={COLORS.primary} />
            </View>
          </TouchableOpacity>
        </LinearGradient>

        <MarketingFooter />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#FFFFFF' },
  splash: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16 },
  splashText: { color: '#FFFFFF', fontSize: 18, fontWeight: '800', letterSpacing: 0.5 },

  // Hero
  hero: { width: '100%' },
  heroInner: { paddingHorizontal: 24, maxWidth: 1080, width: '100%', alignSelf: 'center' },
  eyebrow: {
    flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.15)', paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 20, marginBottom: 18,
  },
  eyebrowText: { color: '#FFE6F7', fontSize: 12, fontWeight: '700', letterSpacing: 0.5 },
  h1: { color: '#FFFFFF', fontWeight: '900', lineHeight: undefined, maxWidth: 720, letterSpacing: 0.2 },
  heroSub: { color: 'rgba(255,255,255,0.9)', fontSize: 16, lineHeight: 25, marginTop: 18, maxWidth: 620 },
  heroCtas: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 28 },
  heroPrimary: {
    flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FFFFFF',
    paddingHorizontal: 22, paddingVertical: 14, borderRadius: 12,
  },
  heroPrimaryText: { color: COLORS.primary, fontSize: 15, fontWeight: '800' },
  heroSecondary: {
    paddingHorizontal: 22, paddingVertical: 14, borderRadius: 12,
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.6)',
  },
  heroSecondaryText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  heroNote: { color: 'rgba(255,255,255,0.7)', fontSize: 12.5, marginTop: 18 },

  // Stats
  stats: {
    flexDirection: 'row', justifyContent: 'center', flexWrap: 'wrap', gap: 36,
    paddingVertical: 28, paddingHorizontal: 24, backgroundColor: '#FBFAFE',
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  stat: { alignItems: 'center', minWidth: 120 },
  statK: { fontSize: 28, fontWeight: '900', color: COLORS.primary },
  statV: { fontSize: 13, color: COLORS.textSecondary, marginTop: 2 },

  // Generic section
  section: { paddingHorizontal: 24, paddingVertical: 48, maxWidth: 1080, width: '100%', alignSelf: 'center' },
  sectionAlt: { backgroundColor: '#FBFAFE', maxWidth: undefined, width: '100%' },
  kicker: { fontSize: 12.5, fontWeight: '800', color: COLORS.accent, letterSpacing: 1, textAlign: 'center' },
  h2: { fontSize: 28, fontWeight: '900', color: COLORS.textPrimary, textAlign: 'center', marginTop: 8, lineHeight: 36 },
  lead: { fontSize: 15, lineHeight: 24, color: COLORS.textSecondary, textAlign: 'center', maxWidth: 640, alignSelf: 'center', marginTop: 12 },

  // Features grid
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', gap: 16, marginTop: 32 },
  featureCard: {
    minWidth: 240, flexGrow: 1, backgroundColor: '#FFFFFF', borderRadius: 16, padding: 20,
    borderWidth: 1, borderColor: COLORS.border,
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 6px 20px rgba(15,23,42,0.05)' } as any) : { elevation: 1 }),
  },
  featureIcon: {
    width: 46, height: 46, borderRadius: 12, backgroundColor: '#F0EAF7',
    alignItems: 'center', justifyContent: 'center', marginBottom: 14,
  },
  featureTitle: { fontSize: 16.5, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 6 },
  featureDesc: { fontSize: 13.5, lineHeight: 21, color: COLORS.textSecondary },

  // How it works
  howRow: { marginTop: 28 },
  step: { flexDirection: 'row', gap: 16, marginBottom: 22, alignItems: 'flex-start' },
  stepNum: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  stepNumText: { color: '#FFFFFF', fontSize: 17, fontWeight: '900' },
  stepTitle: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary },
  stepDesc: { fontSize: 14, lineHeight: 22, color: COLORS.textSecondary, marginTop: 3 },
  howImg: { flex: 1, height: 320, borderRadius: 20, minWidth: 320 },

  // Pricing
  priceRow: { marginTop: 30 },
  priceCard: {
    backgroundColor: '#FFFFFF', borderRadius: 16, padding: 24, borderWidth: 1, borderColor: COLORS.border,
    marginBottom: 16,
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 6px 20px rgba(15,23,42,0.05)' } as any) : { elevation: 1 }),
  },
  priceTitle: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary, marginTop: 12, marginBottom: 8 },
  priceDesc: { fontSize: 14, lineHeight: 22, color: COLORS.textSecondary },
  priceNote: { fontSize: 12.5, color: COLORS.textMuted, textAlign: 'center', marginTop: 6 },

  // CTA band
  ctaBand: { paddingHorizontal: 24, paddingVertical: 52, alignItems: 'center' },
  ctaTitle: { fontSize: 26, fontWeight: '900', color: '#FFFFFF', textAlign: 'center', maxWidth: 620, lineHeight: 34 },
  ctaSub: { fontSize: 15, color: 'rgba(255,255,255,0.88)', textAlign: 'center', marginTop: 12, maxWidth: 520 },
  ctaBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#FFFFFF',
    paddingHorizontal: 24, paddingVertical: 15, borderRadius: 12, marginTop: 24,
  },
  ctaBtnText: { color: COLORS.primary, fontSize: 15, fontWeight: '800' },
  // ── HERO 2 (fwdslash.ai-inspired) ──
  hero2: { backgroundColor: '#F8FAFC', paddingHorizontal: 20, overflow: 'hidden', position: 'relative' },
  hero2Grid: {
    position: 'absolute', inset: 0,
    // SVG data-URI grid pattern — 40x40 cells with thin cool-grey lines
    ...(Platform.OS === 'web' ? {
      backgroundImage: 'url("data:image/svg+xml;utf8,<svg xmlns=\\"http://www.w3.org/2000/svg\\" width=\\"40\\" height=\\"40\\"><path d=\\"M40 0H0V40\\" stroke=\\"%23E2E8F0\\" stroke-width=\\"1\\" fill=\\"none\\"/></svg>")',
      backgroundSize: '40px 40px',
      maskImage: 'radial-gradient(ellipse 80% 60% at 50% 30%, black 30%, transparent 90%)',
      WebkitMaskImage: 'radial-gradient(ellipse 80% 60% at 50% 30%, black 30%, transparent 90%)',
    } : {}),
  } as any,
  hero2Inner: { width: '100%', maxWidth: 1120, alignSelf: 'center', alignItems: 'center', zIndex: 2 },
  pillBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, borderWidth: 1, borderColor: '#C7D2FE', backgroundColor: '#FFFFFF' },
  pillBadgeT: { fontSize: 12, fontWeight: '700', color: '#4F46E5', letterSpacing: 0.3 },
  hero2H1: { fontWeight: '900', color: '#0F172A', textAlign: 'center', marginTop: 22, lineHeight: 1.05 * 76 as any, letterSpacing: -1.5 },
  hero2H1Accent: { color: '#4F46E5' },
  hero2Cursor: { color: '#4F46E5', fontWeight: '400', opacity: 0.7 },
  hero2Sub: { fontSize: 18, color: '#475569', textAlign: 'center', marginTop: 18, fontStyle: 'italic', lineHeight: 28 },
  hero2Chat: { flexDirection: 'row', alignItems: 'center', gap: 6, width: '100%', backgroundColor: '#FFFFFF', borderRadius: 999, borderWidth: 1, borderColor: '#E2E8F0', paddingLeft: 14, paddingRight: 6, paddingVertical: 6, marginTop: 30, shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 20, shadowOffset: { width: 0, height: 6 }, elevation: 4 },
  hero2ChatIcon: { padding: 4 },
  hero2ChatInput: { flex: 1, fontSize: 15, color: '#0F172A', paddingVertical: 12 },
  hero2ChatSend: { width: 40, height: 40, borderRadius: 999, backgroundColor: '#4F46E5', alignItems: 'center', justifyContent: 'center' },
  hero2Chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 16, maxWidth: 720 },
  hero2Chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, borderWidth: 1, borderColor: '#E2E8F0', backgroundColor: '#FFFFFF' },
  hero2ChipT: { fontSize: 12, color: '#475569', fontWeight: '600' },
  hero2Ctas: { flexDirection: 'row', flexWrap: 'wrap', gap: 14, marginTop: 30, alignItems: 'center', justifyContent: 'center' },
  hero2Primary: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#0F172A', paddingHorizontal: 22, paddingVertical: 13, borderRadius: 999 },
  hero2PrimaryT: { color: '#fff', fontWeight: '800', fontSize: 14, letterSpacing: 0.3 },
  hero2Secondary: { paddingHorizontal: 18, paddingVertical: 13, borderRadius: 999, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#FFFFFF' },
  hero2SecondaryT: { color: '#334155', fontWeight: '700', fontSize: 14 },
  hero2Note: { fontSize: 12, color: '#64748B', marginTop: 16 },
  trustedStrip: { paddingVertical: 40, paddingHorizontal: 20, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: '#F1F5F9', alignItems: 'center' },
  trustedT: { fontSize: 12, color: '#64748B', fontWeight: '600', textTransform: 'uppercase', letterSpacing: 1.5 },
  trustedLogos: { flexDirection: 'row', flexWrap: 'wrap', gap: 32, justifyContent: 'center', alignItems: 'center', marginTop: 20 },
  trustedLogo: { fontSize: 16, color: '#94A3B8', fontWeight: '800', letterSpacing: 1, opacity: 0.75 },
});
