import React, { useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Image,
  useWindowDimensions, Platform, TextInput,
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
import { MARKETING_NAV } from '../src/components/marketing/marketingNav';
import MarketingFooter from '../src/components/marketing/MarketingFooter';
import Seo from '../src/components/Seo';
import DemoBooking from '../src/components/marketing/DemoBooking';
import JelcosLoader from '../src/components/marketing/JelcosLoader';
import { DEFAULT_LAYOUT, TILE_META } from '../src/config/dashboardTiles';

const FEATURES = [
  { icon: 'git-branch' as const, title: 'My Dezider', desc: 'A guided 10-step engine that scores every option by what truly matters to you.' },
  { icon: 'swap-horizontal' as const, title: 'Pros & Cons', desc: 'Weighted, 8-step pros & cons analysis that removes gut-feel bias.' },
  { icon: 'grid' as const, title: 'SWOT Analysis', desc: 'Map strengths, weaknesses, opportunities & threats into a clear verdict.' },
  { icon: 'sparkles' as const, title: 'AI Insights', desc: 'AI-assisted options, factors and improvement plans — on demand.' },
  { icon: 'checkmark-done-circle' as const, title: 'Action Center', desc: 'Turn any decision into a Who · What · By-when action plan, automatically.' },
  { icon: 'compass' as const, title: 'Life-Area Balance', desc: 'Align choices across health, career, finance, relationships and more.' },
];

const STEPS = [
  { n: 'frame', icon: 'create-outline', title: 'Frame your choice', desc: 'Capture the decision, the options and the factors that matter.' },
  { n: 'analyze', icon: 'analytics-outline', title: 'Analyze with clarity', desc: 'Weighted scoring, SWOT, MPPS projections and AI insights do the heavy lifting.' },
  { n: 'act', icon: 'rocket-outline', title: 'Act with confidence', desc: 'Auto-generate an action plan and track it to completion.' },
] as const;

const DISPLAY_FONT = Platform.OS === 'web' ? 'Georgia, "Times New Roman", serif' : undefined;

type ModVariant = 'gradient' | 'dark' | 'outline' | 'row' | 'chip';
const MODULE_VARIANT: Record<string, ModVariant> = {
  self_discovery: 'gradient',
  decision_kickstarters: 'dark',
  problem_solvers: 'outline',
  goals_manifestation: 'gradient',
  execute_track: 'row',
  reflection_awareness: 'chip',
  collaboration_mgmt: 'dark',
  solution_space: 'outline',
  more_tools: 'chip',
};

const PROBLEMS = [
  { icon: 'pulse' as const, title: 'Gut-feel bias', desc: 'The loudest instinct wins when nothing is weighed. A structured pass gives you a score you can explain.', fix: 'Weighted Pros & Cons' },
  { icon: 'options' as const, title: 'Factors on different scales', desc: 'Health, career, finance and relationships rarely sit in the same note. They belong in one decision.', fix: 'MyDezider' },
  { icon: 'flag' as const, title: 'A verdict with nowhere to go', desc: 'Choosing is only half the work. The useful outcome is who does what, and by when.', fix: 'Action Tracker' },
];
const SCATTERED = [
  { label: 'Health', top: 6, left: 4, rot: '-6deg' },
  { label: 'Career', top: 0, left: 44, rot: '4deg' },
  { label: 'Finance', top: 40, left: 22, rot: '-2deg' },
  { label: 'Family', top: 44, left: 62, rot: '7deg' },
];

const AI_PARTS = [
  { k: 'Options', v: 'AI-assisted paths when you want more than the ones already on the table.' },
  { k: 'Factors', v: 'Help naming what the decision is actually about, before you score it.' },
  { k: 'Improvement plans', v: 'A way to strengthen a weak option, on demand — not instead of your judgment.' },
];

const CASES = [
  { title: 'A career choice', line: 'Should I take the new role?', result: 'Once family and location sat on the same scale as income, “Stay and grow” led at 72%.' },
  { title: 'A purchase', line: 'Which phone should I buy under ₹50k?', result: 'The shortlist is scored on the factors you set, so the loudest ad does not pick the winner.' },
  { title: 'A move', line: 'Should I move to a new city?', result: 'Health, career, finance and relationships stay in one decision instead of four separate notes.' },
];

const NOTES: { k: string; title: string; body: string; more: string; minutes: string; colors: readonly [string, string]; image: number }[] = [
  { k: 'SCORE', title: 'A score is clearer than a gut feeling', body: 'My Dezider walks a choice through ten steps and ranks options by the weights you set.', more: 'A gut feeling is fast but hard to explain, even to yourself. When each option is rated on the same factors, and each factor carries a weight you chose, the ranking shows its working. If the result surprises you, change a weight and see what moves.', minutes: '4 min read', colors: ['#E91E63', '#7E57C2'], image: require('../assets/images/blog-score.jpg') },
  { k: 'PROS & CONS', title: 'Pros and cons, after the bias is named', body: 'An 8-step pros and cons pass is there so the list is weighted, not just long.', more: 'A long list of pros can still lose to one serious con. Weighting each item stops the side with more bullet points from winning by volume, and naming the bias up front makes it easier to notice when it creeps back in.', minutes: '3 min read', colors: ['#1A237E', '#8E24AA'], image: require('../assets/images/blog-pros.jpg') },
  { k: 'ACTION PLAN', title: 'The decision is not finished at the verdict', body: 'Action Center turns the result into who does what, and by when.', more: 'Most decisions stall after the choice is made. Turning the winning option into owned tasks with dates keeps the momentum, and tracking them shows whether the decision is actually being carried out.', minutes: '3 min read', colors: ['#4A148C', '#26C6DA'], image: require('../assets/images/blog-action.jpg') },
];

const MODULE_SKIP = new Set(['inbox', 'notifications', 'analytics', 'subscription', 'my_earnings']);

const FAQS = [
  { q: 'What is JELCOS AI?', a: 'JELCOS AI is a decision system. You frame a choice, score the options by what matters to you, and leave with a plan. AI insights are there when you ask for options, factors or an improvement plan.' },
  { q: 'What do I get when I start?', a: 'You can begin without a credit card. Subscription plans and pay-as-you-go credits are there when you want more. Cancel anytime.' },
  { q: 'Does the AI decide for me?', a: 'No. AI Insights suggests options, factors and improvement plans when you ask. The score follows the weights you set.' },
  { q: 'What is My Dezider?', a: 'My Dezider is the 10-step decision. You name the choice, the options and the factors, set weights, and see a worth for every option.' },
  { q: 'How is Pros & Cons different from a flat list?', a: 'A flat list treats every line as equal. The 8-step Pros & Cons pass asks which points matter, then uses that to reach a verdict you can explain.' },
  { q: 'What does SWOT do here?', a: 'SWOT maps strengths, weaknesses, opportunities and threats for the choice in front of you, then folds them into the same kind of clear verdict.' },
  { q: 'What is the Action Center?', a: 'After the score, Action Center turns the result into who does what, and by when, so the decision does not stall on the page.' },
  { q: 'What are life areas?', a: 'Health, career, finance, relationships and more can sit in one decision, so a move or a new role is not split across four notes.' },
  { q: 'Is my data private?', a: 'Yes. Your decisions stay in your account. They are not sold and they are not shared.' },
  { q: 'Can I use it for work and for life?', a: 'Yes. The same modules cover a career choice, a purchase, a goal, a team decision or a personal change.' },
  { q: 'How do I book a demo?', a: 'Use Book a Demo on this page. Tell us which modules you want to see. We reply from the support address and walk through them with you.' },
  { q: 'How do payments work?', a: 'You can start free. When you want more, subscription plans and pay-as-you-go credits are available. Payments are processed by Razorpay.' },
];

const SUGGESTED = [
  'Should I quit my job for a startup?',
  'Which phone should I buy under ₹50k?',
  'Should I move to a new city?',
  'Which MBA offer to pick?',
];

const accentGradient = GRADIENTS.accent as unknown as readonly [string, string];
const brandGradient = GRADIENTS.primary as unknown as readonly [string, string, string];

export default function Index() {
  const router = useRouter();
  const company = useCompany();
  const { isLoading, isAuthenticated, loginWithGoogle } = useAuthStore();
  const { width } = useWindowDimensions();
  const isWide = width >= 1020;
  const isMid = width >= 720;
  const featureCols = isWide ? 3 : isMid ? 2 : 1;

  const [heroPrompt, setHeroPrompt] = React.useState('');
  const [moduleGroup, setModuleGroup] = React.useState('all');
  const [blogOpen, setBlogOpen] = React.useState<string | null>(null);
  const [faqOpen, setFaqOpen] = React.useState(0);
  const [showLoader, setShowLoader] = React.useState(Platform.OS === 'web');
  const [loaderMounted, setLoaderMounted] = React.useState(Platform.OS === 'web');
  const scrollRef = React.useRef<ScrollView>(null);
  const offsets = React.useRef<Record<string, number>>({});

  const jump = (id: string) => {
    if (Platform.OS === 'web' && typeof document !== 'undefined') {
      const el = document.getElementById(id);
      if (!el) return false;
      let scroller: HTMLElement | null = el.parentElement;
      while (scroller) {
        const style = window.getComputedStyle(scroller);
        if (/(auto|scroll)/.test(style.overflowY) && scroller.scrollHeight > scroller.clientHeight + 8) break;
        scroller = scroller.parentElement;
      }
      if (!scroller) return false;
      const top = Math.max(0, el.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop - 110);
      scroller.scrollTop = top;
      if (window.location.hash !== `#${id}`) window.history.replaceState(null, '', `#${id}`);
      return scroller.scrollTop > 40;
    }
    const y = offsets.current[id];
    if (typeof y === 'number') {
      scrollRef.current?.scrollTo({ y: Math.max(0, y - 110), animated: true });
      return true;
    }
    return false;
  };

  const remember = (id: string) => (e: { nativeEvent: { layout: { y: number } } }) => {
    offsets.current[id] = e.nativeEvent.layout.y;
  };

  const submitHeroPrompt = () => {
    const q = heroPrompt.trim();
    router.push(q ? `/auth/register?ref=hero&q=${encodeURIComponent(q)}` : '/auth/register?ref=hero' as any);
  };

  useEffect(() => {
    if (!showLoader) return;
    let unmount: ReturnType<typeof setTimeout>;
    const timer = setTimeout(() => {
      setShowLoader(false);
      unmount = setTimeout(() => setLoaderMounted(false), 320);
      const id = (typeof window !== 'undefined' && window.location.hash || '').replace('#', '');
      if (id) setTimeout(() => jump(id), 60);
    }, 550);
    return () => { clearTimeout(timer); clearTimeout(unmount); };
  }, [showLoader]);

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    const id = 'jelcos-landing-motion';
    if (document.getElementById(id)) return;
    const font = document.createElement('link');
    font.rel = 'stylesheet';
    font.href = 'https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500..800;1,9..144,500..800&display=swap';
    document.head.appendChild(font);
    const style = document.createElement('style');
    style.id = id;
    style.textContent = `
      #jelcosMarketing [data-display="1"], #jelcosMarketing [data-display="1"] span {
        font-family: 'Fraunces', Georgia, 'Times New Roman', serif;
      }
      @keyframes jelcosRise {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: none; }
      }
      @keyframes jelcosBar {
        from { transform: scaleX(0); }
        to { transform: scaleX(1); }
      }
      #jelcosHero { animation: jelcosRise 0.7s ease both; }
      #jelcosMarketing [data-lift="1"] {
        transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
      }
      #jelcosMarketing [data-lift="1"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 18px 40px rgba(26, 35, 126, 0.09);
        border-color: #E4D6F2;
      }
      #jelcosMarketing [data-navlink="1"]:hover * {
        color: #FFFFFF;
      }
      #jelcosMarketing [data-bar="1"] {
        transform-origin: left center;
        animation: jelcosBar 0.9s cubic-bezier(.2,.7,.2,1) both;
      }
        #problem, #product, #features, #how, #modules, #insights, #case-studies, #faq, #blog, #about, #demo {
        scroll-margin-top: 120px;
      }
      @media (prefers-reduced-motion: reduce) {
        #jelcosHero, #jelcosMarketing [data-bar="1"] { animation: none; }
        #jelcosMarketing [data-lift="1"] { transition: none; }
      }
    `;
    document.head.appendChild(style);
  }, []);

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;
    let timer = 0;
    const run = () => {
      const id = (window.location.hash || '').replace('#', '');
      if (!id) return;
      let tries = 0;
      const tick = () => {
        if (jump(id)) return;
        if (tries < 40) {
          tries += 1;
          timer = window.setTimeout(tick, 150);
        }
      };
      tick();
    };
    run();
    window.addEventListener('hashchange', run);
    return () => {
      window.removeEventListener('hashchange', run);
      window.clearTimeout(timer);
    };
    // jump reads the live DOM; hash is the trigger
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      const hash = window.location.hash || '';
      const search = window.location.search || '';
      const combined = `${hash}${hash && search ? '&' : ''}${search}`;
      const sessionIdMatch = combined.match(/session_?id=([^&#]+)/i);
      const sessionId = sessionIdMatch ? sessionIdMatch[1] : '';
      if (sessionId) {
        window.history.replaceState(null, '', window.location.pathname);
        loginWithGoogle(sessionId).then(async () => {
          router.replace((await getPostAuthRoute()) as any);
        }).catch(() => router.replace('/auth/login'));
        return;
      }
    }
    if (!isLoading && isAuthenticated) {
      router.replace('/(tabs)');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, isAuthenticated]);

  const isServerRender = typeof window === 'undefined';
  if (!isServerRender && (isLoading || isAuthenticated)) {
    return (
      <View style={{ flex: 1 }}><JelcosLoader /></View>
    );
  }

  const cardBasis = featureCols === 3 ? '31.5%' : featureCols === 2 ? '47.5%' : '100%';
  const h1Size = isWide ? 68 : isMid ? 50 : 36;
  const titleStyle = [styles.h2, { fontSize: isWide ? 46 : isMid ? 36 : 30, lineHeight: isWide ? 54 : isMid ? 44 : 38 }];
  const sectionStyle = [styles.section, { paddingVertical: isWide ? 108 : 68 }];

  return (
    <View nativeID="jelcosMarketing" style={styles.root}>
      <Seo
        title="JELCOS AI — Make every life choice with clarity & confidence"
        description="JELCOS AI gives you structured decision tools — Dezider, weighted Pros & Cons, SWOT — plus AI insights that turn complex life and work choices into clear, actionable plans."
        path="/"
      />
      {loaderMounted && <View style={styles.loaderCover} pointerEvents={showLoader ? 'auto' : 'none'}><JelcosLoader visible={showLoader} /></View>}
      <View style={styles.headerFloat}>
        <MarketingHeader
          appearance="pill"
          overlay
          links={MARKETING_NAV}
          onJump={jump}
        />
      </View>
      <ScrollView
        ref={scrollRef}
        style={styles.scroller}
        contentContainerStyle={{ flexGrow: 1 }}
        showsVerticalScrollIndicator
      >
        <View nativeID="jelcosHero" style={styles.hero}>
          <View style={styles.orbA} />
          <View style={styles.orbB} />
          <View style={[styles.heroGrid, isWide && styles.heroGridWide]}>
            <View style={[styles.heroCopy, isWide && styles.heroCopyWide]}>
              <View style={styles.eyebrow}>
                <Ionicons name="sparkles" size={13} color={COLORS.primary} />
                <Text style={styles.eyebrowText}>Powered by AI</Text>
              </View>
              <Text style={[styles.h1, { fontSize: h1Size, lineHeight: Math.round(h1Size * 1.08) }]}>
                Make every life choice{'\n'}
                <Text style={styles.h1Accent}>with clarity & confidence</Text>
              </Text>
              <Text style={styles.heroSub}>
                {company.product} — {company.tagline}. Structured decision tools and AI insights
                that turn complex choices into clear, actionable plans.
              </Text>
              <View style={styles.heroCtas}>
                <TouchableOpacity activeOpacity={0.9} onPress={() => router.push('/auth/register')}>
                  <LinearGradient colors={accentGradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.heroPrimary}>
                    <Text style={styles.heroPrimaryText}>Get started free</Text>
                    <Ionicons name="arrow-forward" size={18} color="#FFFFFF" />
                  </LinearGradient>
                </TouchableOpacity>
                <TouchableOpacity activeOpacity={0.9} style={styles.heroSecondary} onPress={() => jump('demo')}>
                  <Text style={styles.heroSecondaryText}>Book a Demo</Text>
                </TouchableOpacity>
              </View>
              <Text style={styles.heroNote}>No credit card required to begin · Cancel anytime</Text>

              <View style={styles.prompt}>
                <Ionicons name="chatbubble-ellipses-outline" size={18} color={COLORS.primary} />
                <TextInput
                  style={styles.promptInput}
                  placeholder="What decision are you facing?"
                  placeholderTextColor="#94A3B8"
                  value={heroPrompt}
                  onChangeText={setHeroPrompt}
                  onSubmitEditing={submitHeroPrompt}
                  returnKeyType="send"
                />
                <TouchableOpacity onPress={submitHeroPrompt} accessibilityLabel="Start with this decision">
                  <LinearGradient colors={accentGradient} style={styles.promptSend} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
                    <Ionicons name="arrow-up" size={16} color="#FFFFFF" />
                  </LinearGradient>
                </TouchableOpacity>
              </View>
              <View style={isWide ? styles.chips : styles.chipsStack}>
                {SUGGESTED.map((p) => (
                  <TouchableOpacity key={p} style={[styles.chip, !isWide && styles.chipStack]} onPress={() => setHeroPrompt(p)}>
                    <Text style={styles.chipText}>{p}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            <View style={[styles.previewWrap, isWide && styles.previewWrapWide]}>
              <GlassStats />
            </View>
          </View>
        </View>

        <View nativeID="problem" onLayout={remember('problem')} style={sectionStyle}>
          <View style={[styles.stuckWrap, isWide && styles.stuckWrapWide]}>
            <View style={[styles.stuckIntro, isWide && { flex: 0.85, paddingTop: 8 }]}>
              <View style={styles.stuckTag}>
                <View style={styles.stuckTagDot} />
                <Text style={styles.stuckTagText}>THE STUCK POINT</Text>
              </View>
              <Text {...displayProp} style={[styles.stuckTitle, { fontSize: isWide ? 50 : isMid ? 42 : 34, lineHeight: isWide ? 58 : isMid ? 50 : 42 }]}>
                Complex choices rarely fail for{' '}
                <Text style={styles.stuckTitleAccent}>lack of options.</Text>
              </Text>
              <Text style={styles.stuckLead}>
                They stall when gut feel, scattered advice and competing priorities never get weighed on the same scale.
              </Text>
              <View style={styles.stuckQuote}>
                <Text {...displayProp} style={styles.stuckQuoteMark}>“</Text>
                <Text {...displayProp} style={styles.stuckQuoteText}>Three options, ten opinions and no way to compare them. That is where most decisions wait.</Text>
              </View>
            </View>

            <View style={[styles.bento, isWide && { flex: 1.25 }]}>
              <View style={[styles.bentoDark, isMid && { flex: 1 }]} {...liftProp}>
                <View style={styles.bentoDarkGlow} />
                <View style={styles.bentoIconLight}>
                  <Ionicons name={PROBLEMS[0].icon} size={18} color="#F48FB1" />
                </View>
                <Text {...displayProp} style={styles.bentoQuote}>“I just had a feeling about it.”</Text>
                <Text style={styles.bentoDarkTitle}>{PROBLEMS[0].title}</Text>
                <Text style={styles.bentoDarkDesc}>{PROBLEMS[0].desc}</Text>
                <View style={styles.meter}>
                  <View style={styles.meterRow}>
                    <Text style={styles.meterLabel}>Instinct</Text>
                    <View style={styles.meterTrack}><View style={[styles.meterFill, { width: '86%', backgroundColor: '#E91E63' }]} /></View>
                  </View>
                  <View style={styles.meterRow}>
                    <Text style={styles.meterLabel}>Evidence</Text>
                    <View style={styles.meterTrack}><View style={[styles.meterFill, { width: '18%', backgroundColor: '#9FA8DA' }]} /></View>
                  </View>
                </View>
                <View style={styles.fixPillDark}>
                  <Ionicons name="sparkles" size={12} color="#F48FB1" />
                  <Text style={styles.fixPillDarkText}>Fix: {PROBLEMS[0].fix}</Text>
                </View>
              </View>

              <View style={[styles.bentoCol, isMid && { flex: 1 }]}>
                <LinearGradient colors={['#E91E63', '#8E24AA']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.bentoGrad} {...liftProp}>
                  <View style={styles.scatter}>
                    {SCATTERED.map((s) => (
                      <View key={s.label} style={[styles.scatterChip, { top: s.top, left: `${s.left}%` as any, transform: [{ rotate: s.rot }] }]}>
                        <Text style={styles.scatterText}>{s.label}</Text>
                      </View>
                    ))}
                  </View>
                  <Text {...displayProp} style={styles.bentoGradTitle}>{PROBLEMS[1].title}</Text>
                  <Text style={styles.bentoGradDesc}>{PROBLEMS[1].desc}</Text>
                  <Text style={styles.fixLinkLight}>Fix: {PROBLEMS[1].fix}  →</Text>
                </LinearGradient>

                <View style={styles.bentoDash} {...liftProp}>
                  <View style={styles.bentoDashHead}>
                    <Text style={styles.bentoDashTitle}>{PROBLEMS[2].title}</Text>
                    <Ionicons name={PROBLEMS[2].icon} size={18} color="#1A237E" />
                  </View>
                  <Text style={styles.bentoDashDesc}>{PROBLEMS[2].desc}</Text>
                  <View style={styles.todo}>
                    {['Decision made', 'Owner assigned', 'Deadline set'].map((t, i) => (
                      <View key={t} style={styles.todoRow}>
                        <Ionicons name={i === 0 ? 'checkmark-circle' : 'ellipse-outline'} size={16} color={i === 0 ? '#2E7D32' : '#B0A8C4'} />
                        <Text style={[styles.todoText, i > 0 && styles.todoMissing]}>{t}{i > 0 ? ' · missing' : ''}</Text>
                      </View>
                    ))}
                  </View>
                  <Text style={styles.fixLinkNavy}>Fix: {PROBLEMS[2].fix}  →</Text>
                </View>
              </View>
            </View>
          </View>
        </View>

        <View nativeID="how" onLayout={remember('how')} style={[sectionStyle, styles.sectionAlt]}>
          <View style={styles.sectionInner}>
            <View style={[styles.stuckTag, { alignSelf: 'center' }]}>
              <View style={styles.stuckTagDot} />
              <Text style={styles.stuckTagText}>HOW IT WORKS</Text>
            </View>
            <Text {...displayProp} style={[styles.stuckTitle, styles.howTitle, { fontSize: isWide ? 50 : isMid ? 42 : 34, lineHeight: isWide ? 58 : isMid ? 50 : 42 }]}>
              From dilemma to <Text style={styles.stuckTitleAccent}>decision,</Text> in three moves.
            </Text>
            <Text style={[styles.stuckLead, { textAlign: 'center', alignSelf: 'center', maxWidth: 560 }]}>
              No blank page and no guesswork. Frame it, weigh it, then turn the verdict into a plan you can track.
            </Text>

            {isWide && (
              <View style={styles.rail}>
                <LinearGradient colors={['#E91E63', '#8E24AA', '#1A237E']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.railLine} />
                {STEPS.map((s, i) => (
                  <View key={s.n} style={styles.railStop}>
                    <View style={[styles.railDot, { borderColor: ['#E91E63', '#8E24AA', '#1A237E'][i] }]}>
                      <Ionicons name={s.icon} size={16} color={['#E91E63', '#8E24AA', '#1A237E'][i]} />
                    </View>
                  </View>
                ))}
              </View>
            )}

            <View style={[styles.stepRow, isWide && styles.stepRowWide, isWide && { marginTop: 18 }]}>
              <View style={[styles.howLight, isWide && { flex: 1 }]} {...liftProp}>
                <Text {...displayProp} style={[styles.howPhase, { color: '#E91E63' }]}>Frame.</Text>
                <Text style={styles.howTitleSm}>{STEPS[0].title}</Text>
                <Text style={styles.cardDesc}>{STEPS[0].desc}</Text>
                <View style={styles.mockBox}>
                  <View style={styles.mockInput}>
                    <Ionicons name="help-circle-outline" size={15} color="#8E24AA" />
                    <Text style={styles.mockInputText} numberOfLines={1}>Should I take the new role?</Text>
                  </View>
                  <View style={styles.mockChips}>
                    {['Stay', 'Switch', 'Sabbatical'].map((o) => (
                      <View key={o} style={styles.mockChipPink}><Text style={styles.mockChipPinkText}>{o}</Text></View>
                    ))}
                  </View>
                  <View style={styles.mockChips}>
                    {['Income', 'Growth', 'Family'].map((o) => (
                      <View key={o} style={styles.mockChipGhost}><Text style={styles.mockChipGhostText}>{o}</Text></View>
                    ))}
                  </View>
                </View>
              </View>

              <View style={[styles.howDark, isWide && { flex: 1 }]} {...liftProp}>
                <View style={styles.howDarkGlow} />
                <Text {...displayProp} style={[styles.howPhase, { color: '#CE93D8' }]}>Analyze.</Text>
                <Text style={[styles.howTitleSm, { color: '#FFFFFF' }]}>{STEPS[1].title}</Text>
                <Text style={[styles.cardDesc, { color: 'rgba(255,255,255,0.68)' }]}>{STEPS[1].desc}</Text>
                <View style={styles.scoreBox}>
                  {[
                    { label: 'Stay and grow', v: 72, c: '#E91E63' },
                    { label: 'Join the startup', v: 64, c: '#CE93D8' },
                    { label: 'Take a sabbatical', v: 41, c: '#9FA8DA' },
                  ].map((o) => (
                    <View key={o.label} style={{ gap: 6 }}>
                      <View style={styles.scoreHead}>
                        <Text style={styles.scoreLabel}>{o.label}</Text>
                        <Text style={styles.scoreVal}>{o.v}%</Text>
                      </View>
                      <View style={styles.meterTrack}><View style={[styles.meterFill, { width: `${o.v}%` as any, backgroundColor: o.c }]} /></View>
                    </View>
                  ))}
                  <Text style={styles.scoreNote}>Illustrative scores</Text>
                </View>
              </View>

              <LinearGradient colors={['#8E24AA', '#1A237E']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.howGrad, isWide && { flex: 1 }]} {...liftProp}>
                <Text {...displayProp} style={[styles.howPhase, { color: '#F8BBD0' }]}>Act.</Text>
                <Text style={[styles.howTitleSm, { color: '#FFFFFF' }]}>{STEPS[2].title}</Text>
                <Text style={[styles.cardDesc, { color: 'rgba(255,255,255,0.8)' }]}>{STEPS[2].desc}</Text>
                <View style={styles.planBox}>
                  {[
                    { t: 'Talk to your manager', w: 'This week', done: true },
                    { t: 'Review the offer terms', w: 'This week', done: true },
                    { t: 'Give your answer', w: 'Next week', done: false },
                  ].map((p) => (
                    <View key={p.t} style={styles.planRow}>
                      <Ionicons name={p.done ? 'checkmark-circle' : 'ellipse-outline'} size={17} color={p.done ? '#F8BBD0' : 'rgba(255,255,255,0.5)'} />
                      <Text style={styles.planText} numberOfLines={1}>{p.t}</Text>
                      <Text style={styles.planWhen}>{p.w}</Text>
                    </View>
                  ))}
                </View>
              </LinearGradient>
            </View>
          </View>
        </View>

        <View nativeID="product" onLayout={remember('product')} style={sectionStyle}>
          <View style={[styles.stuckWrap, isWide && styles.stuckWrapWide, isWide && { alignItems: 'center' }]}>
            <View style={[isWide && { flex: 0.85 }]}>
              <View style={styles.stuckTag}>
                <View style={styles.stuckTagDot} />
                <Text style={styles.stuckTagText}>THE PRODUCT</Text>
              </View>
              <Text {...displayProp} style={[styles.stuckTitle, { fontSize: isWide ? 50 : isMid ? 42 : 34, lineHeight: isWide ? 58 : isMid ? 50 : 42 }]}>
                A decision <Text style={styles.stuckTitleAccent}>system,</Text> not a blank chat.
              </Text>
              <Text style={styles.stuckLead}>
                {company.product} brings structure first. You name the choice, the options and the factors.
                Scoring follows what you value. AI assists when you ask.
              </Text>
              <View style={styles.vsBox}>
                <View style={styles.vsRow}>
                  <View style={[styles.vsIcon, { backgroundColor: '#F3E5F5' }]}><Ionicons name="close" size={14} color="#9C93B3" /></View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.vsLabel}>A blank chat</Text>
                    <Text style={styles.vsText}>One long answer you are asked to trust.</Text>
                  </View>
                </View>
                <View style={styles.vsDivider} />
                <View style={styles.vsRow}>
                  <LinearGradient colors={['#E91E63', '#8E24AA']} style={styles.vsIcon}><Ionicons name="checkmark" size={14} color="#FFFFFF" /></LinearGradient>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.vsLabel, { color: '#8E24AA' }]}>{company.product}</Text>
                    <Text style={[styles.vsText, { color: '#16132A' }]}>Scored options, your weights, a plan you can track.</Text>
                  </View>
                </View>
              </View>
            </View>

            <View style={[styles.prodStack, isWide && { flex: 1.2 }]}>
              <View style={styles.appWin} {...liftProp}>
                <View style={styles.appWinGlow} />
                <View style={styles.appWinBar}>
                  {['#FF5F57', '#FEBC2E', '#28C840'].map((c) => <View key={c} style={[styles.appWinDot, { backgroundColor: c }]} />)}
                  <Text style={styles.appWinName}>{FEATURES[0].title}</Text>
                </View>
                <View style={styles.appWinBody}>
                  <Text {...displayProp} style={styles.appWinTitle}>{FEATURES[0].title}</Text>
                  <Text style={styles.appWinDesc}>{FEATURES[0].desc}</Text>
                  <View style={styles.segRow}>
                    {Array.from({ length: 10 }, (_, i) => (
                      <View key={i} style={[styles.seg, { backgroundColor: i < 6 ? ['#E91E63', '#C2185B', '#AD1457', '#9C27B0', '#8E24AA', '#7B1FA2'][i] : 'rgba(255,255,255,0.12)' }]} />
                    ))}
                  </View>
                  <Text style={styles.segNote}>Guided steps · progress saved as you go</Text>
                </View>
              </View>

              <View style={[styles.prodPair, isMid && { flexDirection: 'row' }]}>
                <View style={[styles.pcCard, isMid && { flex: 1 }]} {...liftProp}>
                  <View style={styles.pcHead}>
                    <Ionicons name={FEATURES[1].icon} size={16} color="#8E24AA" />
                    <Text {...displayProp} style={styles.pcTitle}>{FEATURES[1].title}</Text>
                  </View>
                  <Text style={styles.pcDesc}>{FEATURES[1].desc}</Text>
                  <View style={styles.pcCols}>
                    <View style={[styles.pcCol, { backgroundColor: '#E8F5E9' }]}>
                      <Text style={[styles.pcColHead, { color: '#2E7D32' }]}>PROS</Text>
                      {['Growth', 'Pay'].map((t) => <Text key={t} style={styles.pcItem}>+ {t}</Text>)}
                    </View>
                    <View style={[styles.pcCol, { backgroundColor: '#FCE4EC' }]}>
                      <Text style={[styles.pcColHead, { color: '#C2185B' }]}>CONS</Text>
                      {['Commute', 'Risk'].map((t) => <Text key={t} style={styles.pcItem}>− {t}</Text>)}
                    </View>
                  </View>
                  <View style={styles.pcFoot}>
                    <Ionicons name="scale-outline" size={14} color="#8E24AA" />
                    <Text style={styles.pcFootText}>Every item carries the weight you give it</Text>
                  </View>
                </View>

                <LinearGradient colors={['#1A237E', '#8E24AA']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.swotCard, isMid && { flex: 1 }]} {...liftProp}>
                  <View style={styles.pcHead}>
                    <Ionicons name={FEATURES[2].icon} size={16} color="#F8BBD0" />
                    <Text {...displayProp} style={[styles.pcTitle, { color: '#FFFFFF' }]}>{FEATURES[2].title}</Text>
                  </View>
                  <Text style={[styles.pcDesc, { color: 'rgba(255,255,255,0.75)' }]}>{FEATURES[2].desc}</Text>
                  <View style={styles.swotGrid}>
                    {['Strengths', 'Weaknesses', 'Opportunities', 'Threats'].map((t) => (
                      <View key={t} style={styles.swotTile}>
                        <Text {...displayProp} style={styles.swotLetter}>{t[0]}</Text>
                        <Text style={styles.swotWord}>{t}</Text>
                      </View>
                    ))}
                  </View>
                </LinearGradient>
              </View>
            </View>
          </View>
        </View>

        <View nativeID="features" onLayout={remember('features')} style={[sectionStyle, styles.sectionAlt]}>
          <View style={styles.sectionInner}>
            <View style={[styles.stuckTag, { alignSelf: 'center' }]}>
              <View style={styles.stuckTagDot} />
              <Text style={styles.stuckTagText}>WHAT YOU GET</Text>
            </View>
            <Text {...displayProp} style={[styles.stuckTitle, styles.howTitle, { fontSize: isWide ? 50 : isMid ? 42 : 34, lineHeight: isWide ? 58 : isMid ? 50 : 42 }]}>
              Everything you need to <Text style={styles.stuckTitleAccent}>decide well.</Text>
            </Text>
            <Text style={[styles.stuckLead, { textAlign: 'center', alignSelf: 'center', maxWidth: 580 }]}>
              A complete toolkit that brings structure, evidence and AI to the decisions that shape your life and work.
            </Text>

            <View style={styles.kit}>
              <View style={[styles.kitRow, isMid && { flexDirection: 'row' }]}>
                <LinearGradient colors={['#E91E63', '#8E24AA']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.kitHero, isMid && { flex: 2 }]} {...liftProp}>
                  <View style={styles.kitHeroMark}><Ionicons name={FEATURES[0].icon} size={170} color="rgba(255,255,255,0.12)" /></View>
                  <View style={styles.modTagLight}><Text style={styles.modTagLightText}>The core engine</Text></View>
                  <Text {...displayProp} style={styles.kitHeroTitle}>{FEATURES[0].title}</Text>
                  <Text style={styles.kitHeroDesc}>{FEATURES[0].desc}</Text>
                </LinearGradient>
                <View style={[styles.kitWhite, isMid && { flex: 1 }]} {...liftProp}>
                  <View style={[styles.kitIcon, { backgroundColor: '#F3E5F5' }]}><Ionicons name={FEATURES[1].icon} size={18} color="#8E24AA" /></View>
                  <Text {...displayProp} style={styles.kitTitle}>{FEATURES[1].title}</Text>
                  <Text style={styles.cardDesc}>{FEATURES[1].desc}</Text>
                  <View style={styles.balance}>
                    <View style={[styles.balanceSide, { backgroundColor: '#E8F5E9' }]}><Text style={[styles.balanceSign, { color: '#2E7D32' }]}>+</Text></View>
                    <View style={styles.balanceBeam} />
                    <View style={[styles.balanceSide, { backgroundColor: '#FCE4EC' }]}><Text style={[styles.balanceSign, { color: '#C2185B' }]}>−</Text></View>
                  </View>
                </View>
              </View>

              <View style={[styles.kitRow, isMid && { flexDirection: 'row' }]}>
                <View style={[styles.kitDash, isMid && { flex: 1 }]} {...liftProp}>
                  <View style={styles.kitSwot}>
                    {['S', 'W', 'O', 'T'].map((l, i) => (
                      <View key={l} style={[styles.kitSwotCell, { backgroundColor: ['#FCE4EC', '#F3E5F5', '#EDE7F6', '#E8EAF6'][i] }]}>
                        <Text {...displayProp} style={[styles.kitSwotLetter, { color: ['#E91E63', '#8E24AA', '#5E35B1', '#1A237E'][i] }]}>{l}</Text>
                      </View>
                    ))}
                  </View>
                  <Text {...displayProp} style={styles.kitTitle}>{FEATURES[2].title}</Text>
                  <Text style={styles.cardDesc}>{FEATURES[2].desc}</Text>
                </View>

                <View style={[styles.kitDark, isMid && { flex: 1 }]} {...liftProp}>
                  <View style={styles.kitDarkGlow} />
                  <View style={[styles.kitIcon, { backgroundColor: 'rgba(255,255,255,0.08)' }]}><Ionicons name={FEATURES[3].icon} size={18} color="#F48FB1" /></View>
                  <Text {...displayProp} style={[styles.kitTitle, { color: '#FFFFFF' }]}>{FEATURES[3].title}</Text>
                  <Text style={[styles.cardDesc, { color: 'rgba(255,255,255,0.68)' }]}>{FEATURES[3].desc}</Text>
                  <View style={styles.askPill}>
                    <Ionicons name="sparkles" size={13} color="#F48FB1" />
                    <Text style={styles.askText}>Suggest more options</Text>
                  </View>
                </View>

                <View style={[styles.kitNavy, isMid && { flex: 1 }]} {...liftProp}>
                  <View style={[styles.kitIcon, { backgroundColor: 'rgba(255,255,255,0.1)' }]}><Ionicons name={FEATURES[4].icon} size={18} color="#C5CAE9" /></View>
                  <Text {...displayProp} style={[styles.kitTitle, { color: '#FFFFFF' }]}>{FEATURES[4].title}</Text>
                  <Text style={[styles.cardDesc, { color: 'rgba(255,255,255,0.72)' }]}>{FEATURES[4].desc}</Text>
                  <View style={styles.wwbRow}>
                    {['Who', 'What', 'By when'].map((t) => (
                      <View key={t} style={styles.wwbPill}><Text style={styles.wwbText}>{t}</Text></View>
                    ))}
                  </View>
                </View>
              </View>

              <View style={[styles.kitWide, isMid && { flexDirection: 'row', alignItems: 'center' }]} {...liftProp}>
                <View style={[{ gap: 6 }, isMid && { flex: 1 }]}>
                  <View style={styles.pcHead}>
                    <Ionicons name={FEATURES[5].icon} size={18} color="#E91E63" />
                    <Text {...displayProp} style={styles.kitTitleInline}>{FEATURES[5].title}</Text>
                  </View>
                  <Text style={styles.cardDesc}>{FEATURES[5].desc}</Text>
                </View>
                <View style={[styles.areaChips, isMid && { flex: 1.3, justifyContent: 'flex-end' }]}>
                  {[
                    { t: 'Health', i: 'heart' }, { t: 'Career', i: 'briefcase' }, { t: 'Finance', i: 'wallet' },
                    { t: 'Relationships', i: 'people' }, { t: 'Learning', i: 'school' }, { t: 'Purpose', i: 'leaf' },
                  ].map((a, idx) => {
                    const c = ['#E91E63', '#8E24AA', '#5E35B1', '#1A237E', '#AB47BC', '#C2185B'][idx];
                    return (
                      <View key={a.t} style={[styles.areaChip, { borderColor: c + '40', backgroundColor: c + '0F' }]}>
                        <Ionicons name={a.i as any} size={13} color={c} />
                        <Text style={[styles.areaChipText, { color: c }]}>{a.t}</Text>
                      </View>
                    );
                  })}
                </View>
              </View>
            </View>
          </View>
        </View>

        <View nativeID="insights" onLayout={remember('insights')} style={sectionStyle}>
          <View style={styles.sectionInner}>
            <View style={[styles.stuckTag, { alignSelf: 'center' }]}>
              <View style={styles.stuckTagDot} />
              <Text style={styles.stuckTagText}>WHY IT HOLDS</Text>
            </View>
            <Text {...displayProp} style={[styles.stuckTitle, styles.howTitle, { maxWidth: 900, fontSize: isWide ? 50 : isMid ? 42 : 34, lineHeight: isWide ? 58 : isMid ? 50 : 42 }]}>
              Your weights. An <Text style={styles.stuckTitleAccent}>assist</Text> when you want one. A plan after.
            </Text>

            <View style={[styles.stepRow, isWide && styles.stepRowWide, { marginTop: 44 }]}>
              <View style={[styles.whyWhite, isWide && { flex: 1 }]} {...liftProp}>
                <Text style={[styles.whyKicker, { color: '#E91E63' }]}>YOU DECIDE WHAT MATTERS</Text>
                <Text {...displayProp} style={styles.whyTitle}>Your weights.</Text>
                <Text style={styles.cardDesc}>Scores follow the factors you set and how much each one counts. Nothing is ranked behind your back.</Text>
                <View style={styles.weightBox}>
                  {[
                    { t: 'Income', w: 4, c: '#E91E63' },
                    { t: 'Growth', w: 3, c: '#8E24AA' },
                    { t: 'Family time', w: 5, c: '#1A237E' },
                  ].map((f) => (
                    <View key={f.t} style={styles.weightRow}>
                      <Text style={styles.weightLabel}>{f.t}</Text>
                      <View style={styles.weightDots}>
                        {Array.from({ length: 5 }, (_, i) => (
                          <View key={i} style={[styles.weightDot, { backgroundColor: i < f.w ? f.c : '#EEE6F4' }]} />
                        ))}
                      </View>
                    </View>
                  ))}
                </View>
                <View style={styles.privateRow}>
                  <Ionicons name="shield-checkmark" size={16} color="#8E24AA" />
                  <Text style={styles.privateText}>100% your data, private</Text>
                </View>
              </View>

              <View style={[styles.whyDark, isWide && { flex: 1.15 }]} {...liftProp}>
                <View style={styles.kitDarkGlow} />
                <Text style={[styles.whyKicker, { color: '#F48FB1' }]}>AI INSIGHTS, ON DEMAND</Text>
                <Text {...displayProp} style={[styles.whyTitle, { color: '#FFFFFF' }]}>An assist when you want one.</Text>
                <Text style={[styles.cardDesc, { color: 'rgba(255,255,255,0.68)' }]}>When you ask, not in place of the score you set.</Text>
                <View style={{ gap: 10, marginTop: 18 }}>
                  {AI_PARTS.map((p) => (
                    <View key={p.k} style={styles.aiRow}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.aiRowKey}>{p.k}</Text>
                        <Text style={styles.aiRowVal}>{p.v}</Text>
                      </View>
                      <View style={styles.toggle}><View style={styles.toggleKnob} /></View>
                    </View>
                  ))}
                </View>
                <Text style={styles.toggleNote}>Off until you switch it on</Text>
              </View>

              <LinearGradient colors={['#E91E63', '#8E24AA']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.whyGrad, isWide && { flex: 1 }]} {...liftProp}>
                <Text style={[styles.whyKicker, { color: '#FFFFFF', opacity: 0.85 }]}>FROM VERDICT TO ACTION</Text>
                <Text {...displayProp} style={[styles.whyTitle, { color: '#FFFFFF' }]}>A plan after.</Text>
                <Text style={[styles.cardDesc, { color: 'rgba(255,255,255,0.85)' }]}>The chosen option becomes tasks with an owner and a deadline, tracked to done.</Text>
                <View style={styles.timeline}>
                  {[
                    { t: 'Decide', d: 'Verdict locked in', i: 'checkmark' },
                    { t: 'Assign', d: 'Who does what', i: 'person' },
                    { t: 'Track', d: 'By when, to done', i: 'flag' },
                  ].map((s, idx, arr) => (
                    <View key={s.t} style={styles.tlRow}>
                      <View style={{ alignItems: 'center' }}>
                        <View style={styles.tlDot}><Ionicons name={s.i as any} size={13} color="#8E24AA" /></View>
                        {idx < arr.length - 1 && <View style={styles.tlLine} />}
                      </View>
                      <View style={{ flex: 1, paddingBottom: idx < arr.length - 1 ? 14 : 0 }}>
                        <Text style={styles.tlTitle}>{s.t}</Text>
                        <Text style={styles.tlDesc}>{s.d}</Text>
                      </View>
                    </View>
                  ))}
                </View>
              </LinearGradient>
            </View>
          </View>
        </View>

        <View nativeID="modules" onLayout={remember('modules')} style={sectionStyle}>
          <View style={styles.sectionInner}>
            <Text style={styles.kicker}>MODULES</Text>
            <Text style={titleStyle}>Every module in {company.product}</Text>
            <Text style={styles.lead}>The same groups you open after you sign in. Pick a group, or see them all.</Text>
            <View style={styles.filters}>
              <TouchableOpacity style={[styles.filterChip, moduleGroup === 'all' && styles.filterChipOn]} onPress={() => setModuleGroup('all')}>
                <Text style={[styles.filterText, moduleGroup === 'all' && styles.filterTextOn]}>All modules</Text>
              </TouchableOpacity>
              {DEFAULT_LAYOUT.map((section) => {
                const count = section.tiles.filter((id) => TILE_META[id] && !MODULE_SKIP.has(id)).length;
                if (!count) return null;
                const on = moduleGroup === section.id;
                return (
                  <TouchableOpacity key={section.id} style={[styles.filterChip, on && styles.filterChipOn]} onPress={() => setModuleGroup(section.id)}>
                    <Text style={[styles.filterText, on && styles.filterTextOn]}>{section.name}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            {DEFAULT_LAYOUT.map((section) => {
              const tiles = section.tiles.filter((id) => TILE_META[id] && !MODULE_SKIP.has(id));
              if (!tiles.length || (moduleGroup !== 'all' && moduleGroup !== section.id)) return null;
              const variant = MODULE_VARIANT[section.id] || 'outline';
              const half = isWide ? '48%' : '100%';
              const cols = !isWide && !isMid ? 1 : !isWide || tiles.length === 2 || tiles.length === 4 ? 2 : 3;
              const third: any = cols === 1 ? '100%'
                : Platform.OS === 'web' ? `calc((100% - ${(cols - 1) * 16}px) / ${cols})`
                : cols === 2 ? '47.5%' : '31.5%';
              return (
                <View key={section.id} style={styles.modGroup}>
                  <View style={styles.groupHead}>
                    <Text style={styles.groupLabel}>{section.name}</Text>
                    <Text style={styles.groupCount}>{tiles.length} {tiles.length === 1 ? 'module' : 'modules'}</Text>
                  </View>
                  <View style={styles.grid}>
                    {tiles.map((id) => {
                      const tile = TILE_META[id];
                      const tone = tile.gradient?.[0] || COLORS.primary;
                      const tone2 = tile.gradient?.[1] || tone;
                      const icon = tile.icon as any;
                      if (variant === 'gradient') {
                        return (
                          <LinearGradient key={id} colors={[tone, tone2] as unknown as readonly [string, string]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.modGrad, { flexBasis: half }]} {...liftProp}>
                            <View style={styles.modGradWatermark}>
                              <Ionicons name={icon} size={150} color="rgba(255,255,255,0.12)" />
                            </View>
                            <View style={styles.modTagLight}><Text style={styles.modTagLightText}>{section.name}</Text></View>
                            <Text {...displayProp} style={styles.modGradTitle}>{tile.title}</Text>
                            <Text style={styles.modGradSub}>{tile.subtitle}</Text>
                            <View style={styles.modGradCta}>
                              <Text style={styles.modGradCtaText}>Explore module</Text>
                              <Ionicons name="arrow-forward" size={14} color="#FFFFFF" />
                            </View>
                          </LinearGradient>
                        );
                      }
                      if (variant === 'dark') {
                        return (
                          <View key={id} style={[styles.modDark, { flexBasis: third, maxWidth: isWide || isMid ? third : '100%' }]} {...liftProp}>
                            <View style={[styles.modDarkGlow, { backgroundColor: tone }]} />
                            <View style={styles.modDarkTop}>
                              <View style={[styles.modDarkIcon, { borderColor: tone + '80' }]}>
                                <Ionicons name={icon} size={20} color={tone2} />
                              </View>
                              <View style={styles.modArrowDark}>
                                <Ionicons name="arrow-up-outline" size={15} color="#FFFFFF" style={{ transform: [{ rotate: '45deg' }] }} />
                              </View>
                            </View>
                            <Text style={styles.modDarkTitle}>{tile.title}</Text>
                            <Text style={styles.modDarkSub}>{tile.subtitle}</Text>
                          </View>
                        );
                      }
                      if (variant === 'row') {
                        return (
                          <View key={id} style={[styles.modRow, { flexBasis: half }]} {...liftProp}>
                            <LinearGradient colors={[tone, tone2] as unknown as readonly [string, string]} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.modRowIcon}>
                              <Ionicons name={icon} size={22} color="#FFFFFF" />
                            </LinearGradient>
                            <View style={{ flex: 1 }}>
                              <Text {...displayProp} style={styles.modRowTitle}>{tile.title}</Text>
                              <Text style={styles.cardDesc} numberOfLines={2}>{tile.subtitle}</Text>
                            </View>
                            <View style={[styles.modRowArrow, { backgroundColor: tone + '14' }]}>
                              <Ionicons name="chevron-forward" size={18} color={tone} />
                            </View>
                          </View>
                        );
                      }
                      if (variant === 'chip') {
                        return (
                          <View key={id} style={[styles.modChip, { flexBasis: third, maxWidth: isWide || isMid ? third : '100%' }]} {...liftProp}>
                            <View style={[styles.modChipDot, { backgroundColor: tone + '1A' }]}>
                              <Ionicons name={icon} size={16} color={tone} />
                            </View>
                            <View style={{ flex: 1 }}>
                              <Text style={styles.modChipTitle}>{tile.title}</Text>
                              <Text style={styles.modChipSub} numberOfLines={1}>{tile.subtitle}</Text>
                            </View>
                            <Ionicons name="arrow-forward" size={15} color={tone} />
                          </View>
                        );
                      }
                      return (
                        <View key={id} style={[styles.modOutline, { flexBasis: third, maxWidth: isWide || isMid ? third : '100%' }]} {...liftProp}>
                          <LinearGradient colors={[tone + '26', tone + '00'] as unknown as readonly [string, string]} start={{ x: 1, y: 0 }} end={{ x: 0.2, y: 0.8 }} style={styles.modOutlineWash} />
                          <View style={[styles.modOutlineIcon, { backgroundColor: tone }]}>
                            <Ionicons name={icon} size={18} color="#FFFFFF" />
                          </View>
                          <Text {...displayProp} style={styles.modOutlineTitle}>{tile.title}</Text>
                          <Text style={styles.cardDesc}>{tile.subtitle}</Text>
                          <View style={styles.modOutlineFoot}>
                            <Text style={[styles.modOutlineLink, { color: tone }]}>Learn more</Text>
                            <Ionicons name="arrow-forward" size={14} color={tone} />
                          </View>
                        </View>
                      );
                    })}
                  </View>
                </View>
              );
            })}
          </View>
        </View>

        <View nativeID="case-studies" onLayout={remember('case-studies')} style={[sectionStyle, styles.sectionAlt]}>
          <View style={styles.sectionInner}>
            <View style={[styles.stuckTag, { alignSelf: 'center' }]}>
              <View style={styles.stuckTagDot} />
              <Text style={styles.stuckTagText}>CASE STUDIES</Text>
            </View>
            <Text {...displayProp} style={[styles.stuckTitle, styles.howTitle, { fontSize: isWide ? 50 : isMid ? 42 : 34, lineHeight: isWide ? 58 : isMid ? 50 : 42 }]}>
              Worked examples, with a <Text style={styles.stuckTitleAccent}>score you can explain.</Text>
            </Text>
            <Text style={[styles.stuckLead, { textAlign: 'center', alignSelf: 'center', maxWidth: 560 }]}>
              Sample layouts of how {company.product} scores a decision. Not client claims.
            </Text>

            <View style={[styles.caseWrap, isWide && { flexDirection: 'row' }]}>
              <View style={[styles.caseDark, isWide && { flex: 1.15 }]} {...liftProp}>
                <View style={styles.appWinGlow} />
                <View style={styles.caseHead}>
                  <View style={styles.casePillDark}><Text style={styles.casePillDarkText}>{CASES[0].title}</Text></View>
                  <Text style={styles.caseSampleDark}>Sample</Text>
                </View>
                <Text {...displayProp} style={[styles.caseQDark, isWide && { fontSize: 46, lineHeight: 54, marginTop: 24 }]}>“{CASES[0].line}”</Text>
                <Text style={[styles.cardDesc, { color: 'rgba(255,255,255,0.68)', fontSize: 15.5, lineHeight: 25 }]}>{CASES[0].result}</Text>
                <View style={[styles.scoreBox, isWide && { marginTop: 'auto' }]}>
                  {[
                    { label: 'Stay and grow', v: 72, c: '#E91E63', top: true },
                    { label: 'Join the startup', v: 64, c: '#CE93D8' },
                    { label: 'Take a sabbatical', v: 41, c: '#9FA8DA' },
                  ].map((o) => (
                    <View key={o.label} style={{ gap: 6 }}>
                      <View style={styles.scoreHead}>
                        <Text style={styles.scoreLabel}>{o.label}{o.top ? '  ★' : ''}</Text>
                        <Text style={styles.scoreVal}>{o.v}%</Text>
                      </View>
                      <View style={styles.meterTrack}><View style={[styles.meterFill, { width: `${o.v}%` as any, backgroundColor: o.c }]} /></View>
                    </View>
                  ))}
                </View>
                <Text style={styles.caseBuilt}>Built with MyDezider</Text>
              </View>

              <View style={[styles.caseCol, isWide && { flex: 1 }]}>
                <View style={styles.caseWhite} {...liftProp}>
                  <View style={styles.caseHead}>
                    <View style={[styles.casePill, { backgroundColor: '#F3E5F5' }]}><Text style={[styles.casePillText, { color: '#8E24AA' }]}>{CASES[1].title}</Text></View>
                    <Text style={styles.caseSample}>Sample</Text>
                  </View>
                  <Text {...displayProp} style={styles.caseQ}>{CASES[1].line}</Text>
                  <Text style={styles.cardDesc}>{CASES[1].result}</Text>
                  <View style={styles.shortlist}>
                    {[
                      { n: 'Phone A', tags: ['Camera', 'Battery'], pick: true },
                      { n: 'Phone B', tags: ['Price'] },
                      { n: 'Phone C', tags: ['Display'] },
                    ].map((p) => (
                      <View key={p.n} style={[styles.shortRow, p.pick && styles.shortRowPick]}>
                        <Ionicons name="phone-portrait-outline" size={15} color={p.pick ? '#E91E63' : '#8E85A3'} />
                        <Text style={styles.shortName}>{p.n}</Text>
                        <View style={{ flexDirection: 'row', gap: 4, flex: 1 }}>
                          {p.tags.map((t) => <View key={t} style={styles.shortTag}><Text style={styles.shortTagText}>{t}</Text></View>)}
                        </View>
                        {p.pick && <View style={styles.pickBadge}><Text style={styles.pickBadgeText}>Top pick</Text></View>}
                      </View>
                    ))}
                  </View>
                </View>

                <LinearGradient colors={['#8E24AA', '#1A237E']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.caseGrad} {...liftProp}>
                  <View style={styles.caseHead}>
                    <View style={styles.casePillDark}><Text style={styles.casePillDarkText}>{CASES[2].title}</Text></View>
                    <Text style={styles.caseSampleDark}>Sample</Text>
                  </View>
                  <Text {...displayProp} style={[styles.caseQ, { color: '#FFFFFF' }]}>{CASES[2].line}</Text>
                  <Text style={[styles.cardDesc, { color: 'rgba(255,255,255,0.8)' }]}>{CASES[2].result}</Text>
                  <View style={styles.mergeRow}>
                    {[{ t: 'Health', i: 'heart' }, { t: 'Career', i: 'briefcase' }, { t: 'Finance', i: 'wallet' }, { t: 'Relationships', i: 'people' }].map((a) => (
                      <View key={a.t} style={styles.mergeChip}>
                        <Ionicons name={a.i as any} size={12} color="#F8BBD0" />
                        <Text style={styles.mergeText}>{a.t}</Text>
                      </View>
                    ))}
                    <Ionicons name="arrow-forward" size={14} color="rgba(255,255,255,0.7)" />
                    <View style={styles.mergeOne}><Text style={styles.mergeOneText}>One decision</Text></View>
                  </View>
                </LinearGradient>
              </View>
            </View>
          </View>
        </View>

        <View nativeID="faq" onLayout={remember('faq')} style={sectionStyle}>
          <Text style={styles.kicker}>FAQ</Text>
          <Text style={titleStyle}>Questions before you start</Text>
          <View style={styles.faqList}>
            {FAQS.map((item, i) => {
              const open = faqOpen === i;
              return (
                <TouchableOpacity key={item.q} activeOpacity={0.85} onPress={() => setFaqOpen(open ? -1 : i)} style={[styles.faqItem, i > 0 && styles.faqDivider]}>
                  <View style={styles.faqHead}>
                    <Text style={styles.faqQ}>{item.q}</Text>
                    <Ionicons name={open ? 'chevron-up' : 'chevron-down'} size={18} color="#6B7280" />
                  </View>
                  {open ? <Text style={styles.faqA}>{item.a}</Text> : null}
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        <View nativeID="blog" onLayout={remember('blog')} style={sectionStyle}>
          <View style={styles.sectionInner}>
            <View style={[styles.stuckTag, { alignSelf: 'center' }]}>
              <View style={styles.stuckTagDot} />
              <Text style={styles.stuckTagText}>BLOG</Text>
            </View>
            <Text {...displayProp} style={[styles.stuckTitle, styles.howTitle, { fontSize: isWide ? 50 : isMid ? 42 : 34, lineHeight: isWide ? 58 : isMid ? 50 : 42 }]}>
              Notes on a choice that <Text style={styles.stuckTitleAccent}>has a score.</Text>
            </Text>
            <Text style={[styles.stuckLead, { textAlign: 'center', alignSelf: 'center' }]}>Short writing on the modules. Open a note to read it.</Text>

            <View style={[styles.blogWrap, isWide && { flexDirection: 'row' }]}>
              {(() => {
                const note = NOTES[0];
                const open = blogOpen === note.title;
                return (
                  <TouchableOpacity activeOpacity={0.95} onPress={() => setBlogOpen(open ? null : note.title)} style={[styles.blogFeature, isWide && { flex: 1.15 }]} {...liftProp}>
                    <Image source={note.image} style={StyleSheet.absoluteFillObject as any} resizeMode="cover" />
                    <LinearGradient colors={['rgba(16,14,38,0.05)', 'rgba(16,14,38,0.55)', 'rgba(16,14,38,0.96)']} locations={[0, 0.45, 1]} style={StyleSheet.absoluteFillObject} />
                    <View style={styles.blogFeatureTop}>
                      <View style={styles.casePillDark}><Text style={styles.casePillDarkText}>{note.k}</Text></View>
                      <Text style={styles.blogFeatureTime}>{note.minutes}</Text>
                    </View>
                    <View style={styles.blogFeatureBody}>
                      <Text style={styles.blogFeatureLabel}>FEATURED NOTE</Text>
                      <Text {...displayProp} style={[styles.blogFeatureTitle, isWide && { fontSize: 38, lineHeight: 44 }]}>{note.title}</Text>
                      <Text style={styles.blogFeatureDesc}>{note.body}</Text>
                      {open && <Text style={styles.blogFeatureMore}>{note.more}</Text>}
                      <View style={styles.blogReadLight}>
                        <Text style={styles.blogReadLightText}>{open ? 'Close note' : 'Read note'}</Text>
                        <Ionicons name={open ? 'remove' : 'arrow-forward'} size={14} color="#16132A" />
                      </View>
                    </View>
                  </TouchableOpacity>
                );
              })()}

              <View style={[styles.blogCol, isWide && { flex: 1 }]}>
                {NOTES.slice(1).map((note, i) => {
                  const open = blogOpen === note.title;
                  const dark = i === 1;
                  return (
                    <TouchableOpacity key={note.title} activeOpacity={0.95} onPress={() => setBlogOpen(open ? null : note.title)} style={[dark ? styles.blogRowDark : styles.blogRow, isMid && { flexDirection: 'row' }]} {...liftProp}>
                      <View style={[styles.blogThumb, isMid && { width: 170, height: 'auto' as any, alignSelf: 'stretch' }]}>
                        <Image source={note.image} style={StyleSheet.absoluteFillObject as any} resizeMode="cover" />
                      </View>
                      <View style={styles.blogRowBody}>
                        <View style={styles.caseHead}>
                          <View style={[styles.casePill, { backgroundColor: dark ? 'rgba(255,255,255,0.12)' : '#F3E5F5' }]}>
                            <Text style={[styles.casePillText, { color: dark ? '#FFFFFF' : '#8E24AA' }]}>{note.k}</Text>
                          </View>
                          <Text style={dark ? styles.caseSampleDark : styles.caseSample}>{note.minutes}</Text>
                        </View>
                        <Text {...displayProp} style={[styles.blogRowTitle, dark && { color: '#FFFFFF' }]}>{note.title}</Text>
                        <Text style={[styles.cardDesc, dark && { color: 'rgba(255,255,255,0.7)' }]}>{note.body}</Text>
                        {open && <Text style={[styles.blogRowMore, dark && { color: 'rgba(255,255,255,0.85)', borderLeftColor: '#F48FB1' }]}>{note.more}</Text>}
                        <View style={styles.blogReadRow}>
                          <Text style={[styles.blogReadText, dark && { color: '#F48FB1' }]}>{open ? 'Close note' : 'Read note'}</Text>
                          <Ionicons name={open ? 'remove' : 'arrow-forward'} size={14} color={dark ? '#F48FB1' : '#E91E63'} />
                        </View>
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>
          </View>
        </View>

        <View nativeID="about" onLayout={remember('about')} style={[sectionStyle, styles.sectionAlt]}>
          <View style={styles.sectionInner}>
            <View style={[styles.stuckWrap, isWide && styles.stuckWrapWide]}>
              <View style={[isWide && { flex: 0.9, paddingTop: 8 }]}>
                <View style={styles.stuckTag}>
                  <View style={styles.stuckTagDot} />
                  <Text style={styles.stuckTagText}>ABOUT</Text>
                </View>
                <Text {...displayProp} style={[styles.stuckTitle, { fontSize: isWide ? 50 : isMid ? 42 : 34, lineHeight: isWide ? 58 : isMid ? 50 : 42 }]}>
                  The decision <Text style={styles.stuckTitleAccent}>system,</Text> and the team behind it.
                </Text>
                <Text style={styles.stuckLead}>
                  {company.product} is {company.tagline}{/[.!?]$/.test((company.tagline || '').trim()) ? '' : '.'} You frame a choice, score it, and leave with a plan.
                </Text>
                <View style={styles.principles}>
                  {['Structured tools first.', 'AI insights only when you ask.', 'The score follows the weights you set.'].map((p, i) => (
                    <View key={p} style={styles.principleRow}>
                      <View style={[styles.principleMark, { backgroundColor: ['#E91E63', '#8E24AA', '#1A237E'][i] }]} />
                      <Text {...displayProp} style={styles.principleText}>{p}</Text>
                    </View>
                  ))}
                </View>
              </View>

              <View style={[styles.aboutStack, isWide && { flex: 1.1 }]}>
                <View style={styles.aboutDark} {...liftProp}>
                  <View style={styles.appWinGlow} />
                  <Text style={[styles.whyKicker, { color: '#F48FB1' }]}>THE PRODUCT</Text>
                  <Text {...displayProp} style={styles.aboutProduct}>{company.product}</Text>
                  <Text style={styles.aboutTagline}>{company.tagline}</Text>
                </View>

                <View style={[styles.aboutPair, isMid && { flexDirection: 'row' }]}>
                  <View style={[styles.aboutWhite, isMid && { flex: 1 }]} {...liftProp}>
                    <View style={[styles.kitIcon, { backgroundColor: '#F3E5F5' }]}><Ionicons name="business" size={18} color="#8E24AA" /></View>
                    <Text style={[styles.whyKicker, { color: '#8E24AA' }]}>THE COMPANY</Text>
                    <Text {...displayProp} style={styles.aboutCompany}>{company.legalName}</Text>
                    <Text style={styles.aboutAddress}>{company.addressLines.join(' ')}</Text>
                  </View>

                  <LinearGradient colors={['#E91E63', '#8E24AA', '#1A237E']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={[styles.aboutGrad, isMid && { flex: 1 }]} {...liftProp}>
                    <Text style={[styles.whyKicker, { color: '#FFFFFF', opacity: 0.85 }]}>REACH US</Text>
                    <Text {...displayProp} style={styles.aboutReachTitle}>Talk to a person.</Text>
                    <View style={{ gap: 10, marginTop: 14 }}>
                      <TouchableOpacity style={styles.reachRow} onPress={() => Linking.openURL(`mailto:${company.email}`)}>
                        <View style={styles.reachIcon}><Ionicons name="mail" size={14} color="#8E24AA" /></View>
                        <Text style={styles.reachText} numberOfLines={1}>{company.email}</Text>
                      </TouchableOpacity>
                      {!!company.phone && (
                        <TouchableOpacity style={styles.reachRow} onPress={() => Linking.openURL(`tel:${company.phone.replace(/[^\d+]/g, '')}`)}>
                          <View style={styles.reachIcon}><Ionicons name="call" size={14} color="#8E24AA" /></View>
                          <Text style={styles.reachText}>{company.phone}</Text>
                        </TouchableOpacity>
                      )}
                      {!!company.supportHours && (
                        <View style={styles.reachRow}>
                          <View style={styles.reachIcon}><Ionicons name="time" size={14} color="#8E24AA" /></View>
                          <Text style={styles.reachText}>{company.supportHours}</Text>
                        </View>
                      )}
                    </View>
                  </LinearGradient>
                </View>
              </View>
            </View>
          </View>
        </View>

        <View onLayout={remember('demo')} collapsable={false}>
          <DemoBooking />
        </View>

        <MarketingFooter />
      </ScrollView>
    </View>
  );
}

function GlassStats() {
  const rows = [
    { k: '6+', label: 'Decision frameworks', sub: 'My Dezider, Pros & Cons, SWOT and more' },
    { k: '10', label: 'Life areas covered', sub: 'Health, career, finance, relationships and more' },
    { k: '100%', label: 'Your data, private', sub: 'Decisions stay in your account' },
  ];
  return (
    <View style={{ gap: 14, width: '100%' }}>
      {rows.map((row) => (
        <View key={row.label} style={styles.glass}>
          <Text style={styles.glassLabel}>{row.label}</Text>
          <Text style={styles.glassValue}>{row.k}</Text>
          <Text style={styles.glassSub}>{row.sub}</Text>
        </View>
      ))}
    </View>
  );
}

const liftProp = Platform.OS === 'web' ? { dataSet: { lift: '1' } } : {};
const displayProp: any = Platform.OS === 'web' ? { dataSet: { display: '1' } } : {};

const cardShadow = Platform.OS === 'web'
  ? { boxShadow: '0 18px 50px rgba(88, 28, 135, 0.08)' } as any
  : { elevation: 2 };

const styles = StyleSheet.create({
  root: {
    flex: 1, width: '100%', backgroundColor: '#070B1C', overflow: 'hidden',
    ...(Platform.OS === 'web' ? { height: '100vh' } : {}),
  },
  scroller: { flex: 1, width: '100%', ...(Platform.OS === 'web' ? { maxHeight: '100%' } : {}) },
  headerFloat: {
    position: 'absolute', top: 0, left: 0, right: 0, zIndex: 50, pointerEvents: 'box-none',
    ...(Platform.OS === 'web' ? { position: 'fixed' as const, width: '100%' } : {}),
  },
  loaderCover: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 80,
  },
  splashText: { color: '#FFFFFF', fontSize: 18, fontWeight: '800', letterSpacing: 0.4 },

  hero: {
    position: 'relative',
    overflow: 'hidden',
    backgroundColor: '#070B1C',
    paddingHorizontal: 24,
    paddingTop: 128,
    paddingBottom: 96,
  },
  orbA: {
    position: 'absolute', width: 520, height: 520, borderRadius: 260,
    backgroundColor: 'rgba(142,36,170,0.45)', top: -160, right: -40,
    pointerEvents: 'none',
    ...(Platform.OS === 'web' ? { filter: 'blur(40px)' } as any : {}),
  },
  orbB: {
    position: 'absolute', width: 380, height: 380, borderRadius: 190,
    backgroundColor: 'rgba(233,30,99,0.28)', bottom: -40, left: -80,
    pointerEvents: 'none',
    ...(Platform.OS === 'web' ? { filter: 'blur(36px)' } as any : {}),
  },
  heroGrid: { width: '100%', maxWidth: 1160, alignSelf: 'center', gap: 36, zIndex: 1 },
  heroGridWide: { flexDirection: 'row', alignItems: 'center', gap: 48 },
  heroCopy: { minWidth: 0, width: '100%' },
  heroCopyWide: { flex: 1.15, width: undefined },
  eyebrow: {
    flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
    backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.14)',
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, marginBottom: 18,
  },
  eyebrowText: { color: '#F3E8FF', fontSize: 12, fontWeight: '700', letterSpacing: 0.6 },
  h1: { color: '#FFFFFF', fontWeight: '800', letterSpacing: -1.4, maxWidth: 640 },
  h1Accent: Platform.OS === 'web' ? {
    color: '#C4B5FD',
    backgroundImage: 'linear-gradient(100deg, #F9A8D4 0%, #C4B5FD 48%, #93C5FD 100%)',
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  } as any : { color: '#C4B5FD' },
  heroSub: { color: 'rgba(255,255,255,0.78)', fontSize: 17, lineHeight: 27, marginTop: 18, maxWidth: 560 },
  heroCtas: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 28, alignItems: 'center' },
  heroPrimary: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 22, paddingVertical: 14, borderRadius: 999,
  },
  heroPrimaryText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  heroSecondary: {
    paddingHorizontal: 20, paddingVertical: 13, borderRadius: 999,
    borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.28)', backgroundColor: 'rgba(255,255,255,0.06)',
  },
  heroSecondaryText: { color: '#FFFFFF', fontSize: 15, fontWeight: '700' },
  heroNote: { color: 'rgba(255,255,255,0.62)', fontSize: 13, marginTop: 14 },

  prompt: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    marginTop: 26, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14,
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.14)', paddingLeft: 14, paddingRight: 6, paddingVertical: 6,
    maxWidth: 560,
  },
  promptInput: { flex: 1, fontSize: 15, color: '#FFFFFF', paddingVertical: 10 },
  promptSend: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 14, maxWidth: 560 },
  chipsStack: { marginTop: 14, alignItems: 'flex-start', maxWidth: 560, alignSelf: 'stretch' },
  chipStack: { marginBottom: 8 },
  chip: {
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.14)',
  },
  chipText: { fontSize: 12.5, color: 'rgba(255,255,255,0.86)', fontWeight: '600' },
  glass: {
    borderRadius: 22, paddingHorizontal: 22, paddingVertical: 18,
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.16)',
    ...(Platform.OS === 'web' ? { backdropFilter: 'blur(16px)' } as any : {}),
  },
  glassLabel: { fontSize: 11, fontWeight: '700', letterSpacing: 1.1, color: 'rgba(255,255,255,0.62)', textTransform: 'uppercase' },
  glassValue: { fontSize: 42, fontWeight: '800', color: '#FFFFFF', letterSpacing: -0.8, marginTop: 4 },
  glassSub: { fontSize: 15, lineHeight: 20, color: 'rgba(255,255,255,0.7)', marginTop: 2 },

  previewWrap: { width: '100%', maxWidth: 420, alignSelf: 'stretch', marginTop: 8 },
  previewWrapWide: { flex: 1, marginTop: 0, width: undefined },
  preview: {
    backgroundColor: '#FFFFFF', borderRadius: 20, borderWidth: 1, borderColor: '#EFE8F6',
    padding: 22, overflow: 'hidden', ...cardShadow,
  },
  previewAccent: { position: 'absolute', top: 0, left: 0, right: 0, height: 4 },
  previewHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  previewKicker: { fontSize: 12, fontWeight: '700', letterSpacing: 0.6, color: COLORS.primary, textTransform: 'uppercase' },
  previewPill: { backgroundColor: '#F6EEF8', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999 },
  previewPillText: { fontSize: 11, fontWeight: '700', color: COLORS.primaryDark },
  previewTitle: { fontSize: 20, fontWeight: '800', color: '#16132A', marginTop: 12, letterSpacing: -0.3 },
  barMeta: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  barName: { fontSize: 14, fontWeight: '700', color: '#1F2937' },
  barWorth: { fontSize: 14, fontWeight: '800' },
  barTrack: { height: 8, borderRadius: 99, backgroundColor: '#F3EEF7', overflow: 'hidden' },
  barFill: { height: 8, borderRadius: 99 },
  factorRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 18 },
  factorChip: { backgroundColor: '#F7F5FB', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  factorText: { fontSize: 12, fontWeight: '600', color: '#5B5470' },
  previewFoot: { fontSize: 12, lineHeight: 18, color: COLORS.textMuted, marginTop: 16 },

  statBar: {
    flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center',
    gap: 8, paddingVertical: 22, paddingHorizontal: 20,
    backgroundColor: '#FFFFFF', borderBottomWidth: 1, borderBottomColor: '#F0ECF5',
  },
  stat: { alignItems: 'center', minWidth: 140, paddingHorizontal: 18, paddingVertical: 8 },
  statRule: { borderLeftWidth: 1, borderLeftColor: '#F0ECF5' },
  statK: { fontSize: 26, fontWeight: '800', color: COLORS.primary, letterSpacing: -0.4 },
  statV: { fontSize: 13, color: COLORS.textSecondary, marginTop: 2 },

  section: { paddingHorizontal: 28, paddingVertical: 96, backgroundColor: '#F3E5F5' },
  sectionAlt: { backgroundColor: '#F3E5F5' },
  sectionInner: { width: '100%', maxWidth: 1120, alignSelf: 'center' },
  kicker: {
    fontSize: 12, fontWeight: '800', color: '#E91E63', letterSpacing: 1.8,
    textAlign: 'center',
  },
  h2: {
    fontSize: 44, fontWeight: '800', color: '#12141F', textAlign: 'center',
    marginTop: 12, letterSpacing: -1.1, lineHeight: 52, maxWidth: 820, alignSelf: 'center',
  },
  h2Left: { textAlign: 'left', alignSelf: 'flex-start' },
  lead: {
    fontSize: 16, lineHeight: 26, color: COLORS.textSecondary, textAlign: 'center',
    maxWidth: 640, alignSelf: 'center', marginTop: 14,
  },
  leadLeft: { textAlign: 'left', alignSelf: 'flex-start', marginLeft: 0 },

  grid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 16, marginTop: 36,
    width: '100%', maxWidth: 1120, alignSelf: 'center',
  },
  card: {
    flexGrow: 1, minWidth: 240, backgroundColor: '#FFFFFF', borderRadius: 24,
    padding: 24, borderWidth: 1, borderColor: '#EFE6F6', ...cardShadow,
  },
  iconWell: {
    width: 44, height: 44, borderRadius: 12, backgroundColor: '#F6EEF8',
    alignItems: 'center', justifyContent: 'center', marginBottom: 14,
  },
  cardTitle: { fontSize: 17, fontWeight: '800', color: '#16132A', marginBottom: 6, letterSpacing: -0.2 },
  cardDesc: { fontSize: 14.5, lineHeight: 23, color: COLORS.textSecondary },
  cardAccent: { borderTopWidth: 4 },
  cardTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  bigNum: { fontSize: 28, fontWeight: '800', letterSpacing: -0.6 },
  cardKicker: { fontSize: 11, fontWeight: '800', letterSpacing: 1, color: '#8E24AA', textTransform: 'uppercase' },
  modCard: { minHeight: 180 },
  noteCard: { backgroundColor: '#FFFFFF', borderRadius: 24, overflow: 'hidden', flexGrow: 1, ...cardShadow },
  noteCover: { height: 168, overflow: 'hidden' },
  noteImage: { width: '100%', height: '100%' },
  noteCoverNum: { color: '#FFFFFF', fontSize: 32, fontWeight: '800' },
  noteSplit: { flexDirection: 'row', backgroundColor: '#FFFFFF', borderRadius: 24, overflow: 'hidden', flexGrow: 1, ...cardShadow },
  noteRail: { width: 72, alignItems: 'center', justifyContent: 'center' },
  noteRailNum: { color: '#FFFFFF', fontSize: 22, fontWeight: '800' },
  noteFooterBar: { paddingVertical: 10, paddingHorizontal: 18 },
  noteFooterText: { color: '#FFFFFF', fontSize: 11, fontWeight: '800', letterSpacing: 1.1 },
  noteBlob: { position: 'absolute', width: 140, height: 200, borderRadius: 28, backgroundColor: 'rgba(255,255,255,0.2)', top: 16, right: 24, transform: [{ rotate: '16deg' }] },
  noteBlobMid: { width: 150, height: 150, borderRadius: 80, top: -24, left: 28, right: undefined },
  noteBlobLast: { width: 110, height: 110, borderRadius: 24, top: 28, left: 24, right: undefined, transform: [] },
  noteBody: { padding: 18 },
  noteFoot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 14 },
  noteTime: { fontSize: 12, fontWeight: '700', color: '#9AA0B4', letterSpacing: 0.4 },
  groupLabel: { fontSize: 13, fontWeight: '800', letterSpacing: 1.1, color: '#5E35B1', textTransform: 'uppercase' },
  groupHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  groupCount: { fontSize: 12, fontWeight: '700', color: '#9AA0B4' },
  modGroup: { marginTop: 32, width: '100%', maxWidth: 1120, alignSelf: 'center' },
  modFeature: { backgroundColor: '#FFFFFF', borderRadius: 22, overflow: 'hidden', flexGrow: 1, borderWidth: 1, borderColor: '#EFE8F6', ...cardShadow },
  modFeatureHead: { height: 92, paddingHorizontal: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  modFeatureNum: { color: 'rgba(255,255,255,0.9)', fontSize: 28, fontWeight: '800' },
  modWide: {
    flexDirection: 'row', alignItems: 'center', gap: 14, flexGrow: 1,
    backgroundColor: '#FFFFFF', borderRadius: 18, padding: 16,
    borderWidth: 1, borderColor: '#EFE8F6', ...cardShadow,
  },
  modWideIcon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  modChip: {
    flexDirection: 'row', alignItems: 'center', gap: 12, flexGrow: 1,
    backgroundColor: '#FFFFFF', borderRadius: 999, paddingLeft: 8, paddingRight: 18, paddingVertical: 8,
    borderWidth: 1, borderColor: '#E9DDF3',
  },
  modChipDot: { width: 38, height: 38, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  modDot: { width: 10, height: 10, borderRadius: 5 },
  modChipTitle: { fontSize: 14, fontWeight: '700', color: '#16132A' },
  modChipSub: { fontSize: 12, color: COLORS.textSecondary, marginTop: 1 },

  stuckWrap: { width: '100%', maxWidth: 1120, alignSelf: 'center', gap: 36 },
  stuckWrapWide: { flexDirection: 'row', alignItems: 'flex-start', gap: 48 },
  stuckIntro: {},
  stuckTag: {
    flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start',
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#F3C6D8',
  },
  stuckTagDot: { width: 7, height: 7, borderRadius: 99, backgroundColor: '#E91E63' },
  stuckTagText: { fontSize: 11, fontWeight: '800', letterSpacing: 1.6, color: '#E91E63' },
  stuckTitle: { fontFamily: DISPLAY_FONT, fontWeight: '700', color: '#16132A', marginTop: 18, letterSpacing: -0.8 },
  stuckTitleAccent: {
    fontStyle: 'italic', color: '#8E24AA',
    ...(Platform.OS === 'web' ? ({
      backgroundImage: 'linear-gradient(95deg, #E91E63, #8E24AA 55%, #1A237E)',
      backgroundClip: 'text', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
    } as any) : {}),
  },
  stuckLead: { fontSize: 16.5, lineHeight: 27, color: '#5B5470', marginTop: 18, maxWidth: 460 },
  stuckQuote: { flexDirection: 'row', gap: 10, marginTop: 28, paddingLeft: 16, borderLeftWidth: 3, borderLeftColor: '#E91E63', maxWidth: 440 },
  stuckQuoteMark: { fontFamily: DISPLAY_FONT, fontSize: 44, lineHeight: 44, color: '#E91E63', marginTop: -6 },
  stuckQuoteText: { flex: 1, fontFamily: DISPLAY_FONT, fontStyle: 'italic', fontSize: 18, lineHeight: 28, color: '#3A3350' },

  howTitle: { textAlign: 'center', alignSelf: 'center', maxWidth: 820 },
  rail: { width: '100%', maxWidth: 1120, alignSelf: 'center', flexDirection: 'row', marginTop: 44, height: 40, alignItems: 'center' },
  railLine: { position: 'absolute', left: '16.6%', right: '16.6%', height: 2, borderRadius: 99, opacity: 0.6 },
  railStop: { flex: 1, alignItems: 'center' },
  railDot: { width: 40, height: 40, borderRadius: 999, borderWidth: 2, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  howPhase: { fontFamily: DISPLAY_FONT, fontStyle: 'italic', fontWeight: '700', fontSize: 40, lineHeight: 46, letterSpacing: -0.8 },
  howTitleSm: { fontSize: 16, fontWeight: '800', color: '#16132A', marginTop: 10, marginBottom: 6 },
  howLight: { backgroundColor: '#FFFFFF', borderRadius: 28, padding: 26, borderWidth: 1, borderColor: '#EFE3F6', ...cardShadow },
  howDark: {
    backgroundColor: '#100E26', borderRadius: 28, padding: 26, overflow: 'hidden',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(16,14,38,0.3)' } as any) : {}),
  },
  howDarkGlow: {
    position: 'absolute', width: 200, height: 200, borderRadius: 999, bottom: -90, left: -60, backgroundColor: '#8E24AA', opacity: 0.4,
    ...(Platform.OS === 'web' ? ({ filter: 'blur(60px)' } as any) : {}),
  },
  howGrad: {
    borderRadius: 28, padding: 26, overflow: 'hidden',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(26,35,126,0.28)' } as any) : {}),
  },
  mockBox: { marginTop: 20, padding: 14, borderRadius: 18, backgroundColor: '#FAF5FC', borderWidth: 1, borderColor: '#F0E4F7', gap: 10 },
  mockInput: {
    flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 10,
    borderRadius: 12, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E9DCF2',
  },
  mockInputText: { flex: 1, fontSize: 13, fontWeight: '600', color: '#16132A' },
  mockChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  mockChipPink: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, backgroundColor: '#E91E63' },
  mockChipPinkText: { color: '#FFFFFF', fontSize: 11.5, fontWeight: '700' },
  mockChipGhost: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, borderWidth: 1, borderColor: '#D9C3EA', backgroundColor: '#FFFFFF' },
  mockChipGhostText: { color: '#6A1B9A', fontSize: 11.5, fontWeight: '700' },
  scoreBox: { marginTop: 20, padding: 16, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.05)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)', gap: 12 },
  scoreHead: { flexDirection: 'row', justifyContent: 'space-between' },
  scoreLabel: { fontSize: 12.5, fontWeight: '600', color: 'rgba(255,255,255,0.8)' },
  scoreVal: { fontSize: 12.5, fontWeight: '800', color: '#FFFFFF' },
  scoreNote: { fontSize: 10.5, color: 'rgba(255,255,255,0.4)', letterSpacing: 0.4 },
  planBox: { marginTop: 20, padding: 14, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.1)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.18)', gap: 12 },
  planRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  planText: { flex: 1, color: '#FFFFFF', fontSize: 13, fontWeight: '600' },
  planWhen: { color: 'rgba(255,255,255,0.6)', fontSize: 11, fontWeight: '700' },

  vsBox: { marginTop: 28, borderRadius: 20, padding: 16, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EDE1F5', maxWidth: 460, ...cardShadow },
  vsRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  vsIcon: { width: 28, height: 28, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  vsLabel: { fontSize: 11, fontWeight: '800', letterSpacing: 1.2, color: '#9C93B3', textTransform: 'uppercase' },
  vsText: { fontSize: 14, color: '#9C93B3', marginTop: 2 },
  vsDivider: { height: 1, backgroundColor: '#F1E8F7', marginVertical: 12, marginLeft: 40 },
  prodStack: { gap: 16 },
  appWin: {
    borderRadius: 24, overflow: 'hidden', backgroundColor: '#100E26',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(16,14,38,0.3)' } as any) : {}),
  },
  appWinGlow: {
    position: 'absolute', width: 260, height: 260, borderRadius: 999, top: -120, right: -60, backgroundColor: '#E91E63', opacity: 0.3,
    ...(Platform.OS === 'web' ? ({ filter: 'blur(70px)' } as any) : {}),
  },
  appWinBar: { flexDirection: 'row', alignItems: 'center', gap: 7, paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.07)' },
  appWinDot: { width: 10, height: 10, borderRadius: 99 },
  appWinName: { marginLeft: 10, color: 'rgba(255,255,255,0.45)', fontSize: 12, fontWeight: '600' },
  appWinBody: { padding: 24 },
  appWinTitle: { color: '#FFFFFF', fontSize: 30, lineHeight: 36, fontWeight: '700', letterSpacing: -0.5 },
  appWinDesc: { color: 'rgba(255,255,255,0.7)', fontSize: 14.5, lineHeight: 23, marginTop: 6, maxWidth: 440 },
  segRow: { flexDirection: 'row', gap: 5, marginTop: 20 },
  seg: { flex: 1, height: 8, borderRadius: 99 },
  segNote: { color: 'rgba(255,255,255,0.45)', fontSize: 11.5, marginTop: 10, letterSpacing: 0.3 },
  prodPair: { gap: 16 },
  pcCard: { borderRadius: 24, padding: 20, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EDE1F5', ...cardShadow },
  pcHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pcTitle: { fontSize: 21, fontWeight: '700', color: '#16132A', letterSpacing: -0.3 },
  pcDesc: { fontSize: 13.5, lineHeight: 21, color: '#5B5470', marginTop: 6 },
  pcCols: { flexDirection: 'row', gap: 8, marginTop: 14 },
  pcCol: { flex: 1, borderRadius: 14, padding: 12, gap: 4 },
  pcColHead: { fontSize: 10.5, fontWeight: '800', letterSpacing: 1.2, marginBottom: 2 },
  pcItem: { fontSize: 13, fontWeight: '600', color: '#16132A' },
  pcFoot: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 'auto', paddingTop: 14 },
  pcFootText: { fontSize: 12, fontWeight: '600', color: '#6A1B9A' },
  swotCard: { borderRadius: 24, padding: 20, overflow: 'hidden' },
  swotGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 14 },
  swotTile: {
    flexBasis: '47%', flexGrow: 1, borderRadius: 14, paddingVertical: 10, paddingHorizontal: 12,
    backgroundColor: 'rgba(255,255,255,0.1)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.16)',
  },
  swotLetter: { color: '#F8BBD0', fontSize: 22, lineHeight: 24, fontWeight: '700', fontStyle: 'italic' },
  swotWord: { color: 'rgba(255,255,255,0.8)', fontSize: 11.5, fontWeight: '600', marginTop: 2 },

  kit: { width: '100%', maxWidth: 1120, alignSelf: 'center', marginTop: 44, gap: 16 },
  kitRow: { gap: 16 },
  kitHero: {
    borderRadius: 28, padding: 30, minHeight: 250, overflow: 'hidden', justifyContent: 'flex-end',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(142,36,170,0.3)' } as any) : {}),
  },
  kitHeroMark: { position: 'absolute', right: -10, top: -20 },
  kitHeroTitle: { color: '#FFFFFF', fontSize: 40, lineHeight: 46, fontWeight: '700', marginTop: 'auto', paddingTop: 50, letterSpacing: -0.8 },
  kitHeroDesc: { color: 'rgba(255,255,255,0.88)', fontSize: 16, lineHeight: 25, marginTop: 8, maxWidth: 440 },
  kitWhite: { borderRadius: 28, padding: 24, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EDE1F5', ...cardShadow },
  kitIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 16 },
  kitTitle: { fontSize: 23, lineHeight: 29, fontWeight: '700', color: '#16132A', marginBottom: 6, letterSpacing: -0.3 },
  kitTitleInline: { fontSize: 23, lineHeight: 29, fontWeight: '700', color: '#16132A', letterSpacing: -0.3 },
  balance: { flexDirection: 'row', alignItems: 'center', marginTop: 'auto', paddingTop: 18 },
  balanceSide: { width: 40, height: 40, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  balanceSign: { fontSize: 20, fontWeight: '800' },
  balanceBeam: { flex: 1, height: 2, backgroundColor: '#E1D3EE', marginHorizontal: 8, transform: [{ rotate: '-4deg' }] },
  kitDash: { borderRadius: 28, padding: 24, backgroundColor: '#FFFFFF', borderWidth: 1.5, borderStyle: 'dashed', borderColor: '#C9B6E0' },
  kitSwot: { flexDirection: 'row', gap: 6, marginBottom: 16 },
  kitSwotCell: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  kitSwotLetter: { fontSize: 20, fontWeight: '700', fontStyle: 'italic' },
  kitDark: {
    borderRadius: 28, padding: 24, overflow: 'hidden', backgroundColor: '#100E26',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(16,14,38,0.28)' } as any) : {}),
  },
  kitDarkGlow: {
    position: 'absolute', width: 200, height: 200, borderRadius: 999, top: -90, right: -60, backgroundColor: '#E91E63', opacity: 0.35,
    ...(Platform.OS === 'web' ? ({ filter: 'blur(60px)' } as any) : {}),
  },
  askPill: {
    flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', marginTop: 18,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1, borderColor: 'rgba(244,143,177,0.35)',
  },
  askText: { color: '#FFFFFF', fontSize: 12.5, fontWeight: '700' },
  kitNavy: { borderRadius: 28, padding: 24, backgroundColor: '#1A237E', overflow: 'hidden' },
  wwbRow: { flexDirection: 'row', gap: 6, marginTop: 'auto', paddingTop: 16 },
  wwbPill: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.12)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.2)' },
  wwbText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
  kitWide: { borderRadius: 28, padding: 24, gap: 18, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EDE1F5', ...cardShadow },
  areaChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  areaChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, borderWidth: 1 },
  areaChipText: { fontSize: 12.5, fontWeight: '700' },

  whyKicker: { fontSize: 11, fontWeight: '800', letterSpacing: 1.5, marginBottom: 10 },
  whyTitle: { fontSize: 30, lineHeight: 36, fontWeight: '700', color: '#16132A', letterSpacing: -0.5, marginBottom: 8 },
  whyWhite: { borderRadius: 28, padding: 26, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EDE1F5', ...cardShadow },
  whyDark: {
    borderRadius: 28, padding: 26, overflow: 'hidden', backgroundColor: '#100E26',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(16,14,38,0.3)' } as any) : {}),
  },
  whyGrad: {
    borderRadius: 28, padding: 26, overflow: 'hidden',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(142,36,170,0.28)' } as any) : {}),
  },
  weightBox: { marginTop: 18, padding: 14, borderRadius: 18, backgroundColor: '#FAF5FC', borderWidth: 1, borderColor: '#F0E4F7', gap: 12 },
  weightRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  weightLabel: { fontSize: 13, fontWeight: '700', color: '#16132A' },
  weightDots: { flexDirection: 'row', gap: 5 },
  weightDot: { width: 18, height: 8, borderRadius: 99 },
  aiRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.05)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  aiRowKey: { color: '#FFFFFF', fontSize: 13.5, fontWeight: '800' },
  aiRowVal: { color: 'rgba(255,255,255,0.6)', fontSize: 12.5, lineHeight: 18, marginTop: 2 },
  toggle: { width: 38, height: 22, borderRadius: 99, backgroundColor: 'rgba(255,255,255,0.14)', padding: 3 },
  toggleKnob: { width: 16, height: 16, borderRadius: 99, backgroundColor: 'rgba(255,255,255,0.75)' },
  toggleNote: { color: 'rgba(255,255,255,0.45)', fontSize: 11.5, marginTop: 12, letterSpacing: 0.3 },
  timeline: { marginTop: 20, padding: 16, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.12)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.2)' },
  tlRow: { flexDirection: 'row', gap: 12 },
  tlDot: { width: 26, height: 26, borderRadius: 999, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  tlLine: { width: 2, flex: 1, backgroundColor: 'rgba(255,255,255,0.35)', marginVertical: 3 },
  tlTitle: { color: '#FFFFFF', fontSize: 14, fontWeight: '800' },
  tlDesc: { color: 'rgba(255,255,255,0.75)', fontSize: 12.5, marginTop: 1 },

  caseWrap: { width: '100%', maxWidth: 1120, alignSelf: 'center', marginTop: 44, gap: 16 },
  caseCol: { gap: 16 },
  caseHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 },
  casePill: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 999 },
  casePillText: { fontSize: 11, fontWeight: '800', letterSpacing: 1.1, textTransform: 'uppercase' },
  casePillDark: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.12)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)' },
  casePillDarkText: { fontSize: 11, fontWeight: '800', letterSpacing: 1.1, color: '#FFFFFF', textTransform: 'uppercase' },
  caseSample: { fontSize: 11, fontWeight: '700', color: '#9C93B3', fontStyle: 'italic' },
  caseSampleDark: { fontSize: 11, fontWeight: '700', color: 'rgba(255,255,255,0.5)', fontStyle: 'italic' },
  caseDark: {
    borderRadius: 28, padding: 28, overflow: 'hidden', backgroundColor: '#100E26',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(16,14,38,0.3)' } as any) : {}),
  },
  caseQDark: { fontSize: 34, lineHeight: 42, fontWeight: '700', fontStyle: 'italic', color: '#FFFFFF', letterSpacing: -0.6, marginBottom: 10 },
  caseBuilt: { color: '#F48FB1', fontSize: 12.5, fontWeight: '800', marginTop: 18, letterSpacing: 0.3 },
  caseWhite: { borderRadius: 28, padding: 24, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EDE1F5', ...cardShadow },
  caseQ: { fontSize: 23, lineHeight: 29, fontWeight: '700', color: '#16132A', letterSpacing: -0.3, marginBottom: 6 },
  shortlist: { marginTop: 16, gap: 8 },
  shortRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12, paddingVertical: 9, borderRadius: 12, backgroundColor: '#FAF5FC', borderWidth: 1, borderColor: '#F0E4F7' },
  shortRowPick: { backgroundColor: '#FFF0F5', borderColor: '#F8BBD0' },
  shortName: { fontSize: 13, fontWeight: '800', color: '#16132A', width: 62 },
  shortTag: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E6D8F0' },
  shortTagText: { fontSize: 10.5, fontWeight: '700', color: '#6A1B9A' },
  pickBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, backgroundColor: '#E91E63' },
  pickBadgeText: { color: '#FFFFFF', fontSize: 10.5, fontWeight: '800' },
  caseGrad: { borderRadius: 28, padding: 24, overflow: 'hidden' },
  mergeRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginTop: 16 },
  mergeChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 9, paddingVertical: 5, borderRadius: 999, backgroundColor: 'rgba(255,255,255,0.12)' },
  mergeText: { color: '#FFFFFF', fontSize: 11.5, fontWeight: '700' },
  mergeOne: { paddingHorizontal: 11, paddingVertical: 5, borderRadius: 999, backgroundColor: '#FFFFFF' },
  mergeOneText: { color: '#8E24AA', fontSize: 11.5, fontWeight: '800' },

  principles: { marginTop: 28, gap: 14 },
  principleRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  principleMark: { width: 22, height: 3, borderRadius: 99 },
  principleText: { flex: 1, fontSize: 20, lineHeight: 27, fontStyle: 'italic', fontWeight: '600', color: '#2A2440' },
  aboutStack: { gap: 16 },
  aboutPair: { gap: 16 },
  aboutDark: {
    borderRadius: 28, padding: 28, overflow: 'hidden', backgroundColor: '#100E26',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(16,14,38,0.3)' } as any) : {}),
  },
  aboutProduct: { color: '#FFFFFF', fontSize: 44, lineHeight: 50, fontWeight: '700', letterSpacing: -1 },
  aboutTagline: { color: 'rgba(255,255,255,0.7)', fontSize: 15, lineHeight: 23, marginTop: 8, maxWidth: 440 },
  aboutWhite: { borderRadius: 28, padding: 24, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EDE1F5', ...cardShadow },
  aboutCompany: { fontSize: 21, lineHeight: 27, fontWeight: '700', color: '#16132A', letterSpacing: -0.3 },
  aboutAddress: { fontSize: 13, lineHeight: 20, color: '#5B5470', marginTop: 8 },
  aboutGrad: {
    borderRadius: 28, padding: 24, overflow: 'hidden',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(142,36,170,0.28)' } as any) : {}),
  },
  aboutReachTitle: { color: '#FFFFFF', fontSize: 26, lineHeight: 32, fontWeight: '700', fontStyle: 'italic', letterSpacing: -0.4 },
  reachRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.12)' },
  reachIcon: { width: 26, height: 26, borderRadius: 999, backgroundColor: '#FFFFFF', alignItems: 'center', justifyContent: 'center' },
  reachText: { flex: 1, color: '#FFFFFF', fontSize: 13, fontWeight: '600' },

  blogWrap: { width: '100%', maxWidth: 1120, alignSelf: 'center', marginTop: 44, gap: 16 },
  blogCol: { gap: 16 },
  blogFeature: {
    borderRadius: 28, overflow: 'hidden', minHeight: 460, padding: 26, justifyContent: 'space-between', backgroundColor: '#100E26',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(16,14,38,0.3)' } as any) : {}),
  },
  blogFeatureTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  blogFeatureTime: { color: 'rgba(255,255,255,0.8)', fontSize: 12, fontWeight: '700' },
  blogFeatureBody: { marginTop: 120 },
  blogFeatureLabel: { color: '#F48FB1', fontSize: 11, fontWeight: '800', letterSpacing: 1.6, marginBottom: 10 },
  blogFeatureTitle: { color: '#FFFFFF', fontSize: 30, lineHeight: 36, fontWeight: '700', letterSpacing: -0.6 },
  blogFeatureDesc: { color: 'rgba(255,255,255,0.8)', fontSize: 15, lineHeight: 24, marginTop: 10, maxWidth: 460 },
  blogFeatureMore: { color: 'rgba(255,255,255,0.9)', fontSize: 14.5, lineHeight: 23, marginTop: 12, paddingLeft: 12, borderLeftWidth: 2, borderLeftColor: '#F48FB1' },
  blogReadLight: { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', marginTop: 18, paddingHorizontal: 16, paddingVertical: 9, borderRadius: 999, backgroundColor: '#FFFFFF' },
  blogReadLightText: { color: '#16132A', fontSize: 13, fontWeight: '800' },
  blogRow: { borderRadius: 24, overflow: 'hidden', backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EDE1F5', ...cardShadow },
  blogRowDark: {
    borderRadius: 24, overflow: 'hidden', backgroundColor: '#100E26',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 24px 60px rgba(16,14,38,0.28)' } as any) : {}),
  },
  blogThumb: { height: 160, overflow: 'hidden' },
  blogRowBody: { flex: 1, padding: 20 },
  blogRowTitle: { fontSize: 21, lineHeight: 27, fontWeight: '700', color: '#16132A', letterSpacing: -0.3, marginBottom: 6 },
  blogRowMore: { fontSize: 13.5, lineHeight: 21, color: '#3A3350', marginTop: 10, paddingLeft: 10, borderLeftWidth: 2, borderLeftColor: '#E91E63' },
  blogReadRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 14 },
  blogReadText: { color: '#E91E63', fontSize: 13, fontWeight: '800' },

  bento: { gap: 16, flexDirection: 'row', flexWrap: 'wrap' },
  bentoCol: { gap: 16, flexGrow: 1, flexBasis: 280 },
  bentoDark: {
    flexGrow: 1, flexBasis: 280, borderRadius: 28, padding: 26, overflow: 'hidden', backgroundColor: '#100E26',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 30px 70px rgba(16,14,38,0.35)' } as any) : {}),
  },
  bentoDarkGlow: {
    position: 'absolute', width: 220, height: 220, borderRadius: 999, top: -80, right: -70, backgroundColor: '#E91E63', opacity: 0.35,
    ...(Platform.OS === 'web' ? ({ filter: 'blur(60px)' } as any) : {}),
  },
  bentoIconLight: {
    width: 42, height: 42, borderRadius: 14, alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(244,143,177,0.35)',
  },
  bentoQuote: { fontFamily: DISPLAY_FONT, fontStyle: 'italic', fontSize: 34, lineHeight: 42, color: '#FFFFFF', marginTop: 40, letterSpacing: -0.5 },
  bentoDarkTitle: { fontSize: 12, fontWeight: '800', letterSpacing: 1.6, color: '#F48FB1', textTransform: 'uppercase', marginTop: 18 },
  bentoDarkDesc: { fontSize: 14.5, lineHeight: 23, color: 'rgba(255,255,255,0.68)', marginTop: 8 },
  meter: { marginTop: 'auto', paddingTop: 28, gap: 12 },
  meterRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  meterLabel: { width: 64, fontSize: 12, fontWeight: '700', color: 'rgba(255,255,255,0.6)' },
  meterTrack: { flex: 1, height: 6, borderRadius: 99, backgroundColor: 'rgba(255,255,255,0.08)', overflow: 'hidden' },
  meterFill: { height: 6, borderRadius: 99 },
  fixPillDark: {
    flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', marginTop: 24,
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, backgroundColor: 'rgba(233,30,99,0.14)', borderWidth: 1, borderColor: 'rgba(233,30,99,0.35)',
  },
  fixPillDarkText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },

  bentoGrad: { borderRadius: 28, padding: 24, overflow: 'hidden' },
  scatter: { height: 82, marginBottom: 14 },
  scatterChip: {
    position: 'absolute', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.18)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.35)',
  },
  scatterText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
  bentoGradTitle: { fontFamily: DISPLAY_FONT, fontSize: 24, lineHeight: 30, fontWeight: '700', color: '#FFFFFF' },
  bentoGradDesc: { fontSize: 14, lineHeight: 22, color: 'rgba(255,255,255,0.85)', marginTop: 8 },
  fixLinkLight: { color: '#FFFFFF', fontSize: 13, fontWeight: '800', marginTop: 16, letterSpacing: 0.3 },

  bentoDash: {
    borderRadius: 28, padding: 24, backgroundColor: '#FFFFFF', borderWidth: 1.5, borderStyle: 'dashed', borderColor: '#B9A6D6',
  },
  bentoDashHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 },
  bentoDashTitle: { flex: 1, fontSize: 19, lineHeight: 25, fontWeight: '800', color: '#1A237E', letterSpacing: -0.3 },
  bentoDashDesc: { fontSize: 14, lineHeight: 22, color: '#5B5470', marginTop: 8 },
  todo: { marginTop: 16, gap: 8 },
  todoRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  todoText: { fontSize: 13.5, fontWeight: '600', color: '#16132A' },
  todoMissing: { color: '#9C93B3', fontStyle: 'italic' },
  fixLinkNavy: { color: '#1A237E', fontSize: 13, fontWeight: '800', marginTop: 16, letterSpacing: 0.3 },

  modGrad: {
    flexGrow: 1, borderRadius: 28, padding: 30, minHeight: 250, overflow: 'hidden', justifyContent: 'flex-end',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 24px 60px rgba(26,35,126,0.22)' } as any) : {}),
  },
  modGradWatermark: { position: 'absolute', right: -18, top: -14 },
  modTagLight: {
    alignSelf: 'flex-start', paddingHorizontal: 12, paddingVertical: 5, borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.18)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.3)', marginBottom: 'auto',
  },
  modTagLightText: { color: '#FFFFFF', fontSize: 11, fontWeight: '700', letterSpacing: 1.2, textTransform: 'uppercase' },
  modGradTitle: { color: '#FFFFFF', fontSize: 32, lineHeight: 38, fontWeight: '700', fontFamily: DISPLAY_FONT, marginTop: 56, letterSpacing: -0.4 },
  modGradSub: { color: 'rgba(255,255,255,0.86)', fontSize: 15, lineHeight: 22, marginTop: 8, maxWidth: 380 },
  modGradCta: {
    flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', marginTop: 20,
    paddingHorizontal: 16, paddingVertical: 9, borderRadius: 999, backgroundColor: 'rgba(10,8,30,0.28)',
  },
  modGradCtaText: { color: '#FFFFFF', fontSize: 13, fontWeight: '700' },

  modDark: {
    flexGrow: 1, borderRadius: 24, padding: 24, minHeight: 210, overflow: 'hidden',
    backgroundColor: '#12102E', borderWidth: 1, borderColor: 'rgba(255,255,255,0.08)',
  },
  modDarkGlow: {
    position: 'absolute', width: 180, height: 180, borderRadius: 999, top: -70, right: -50, opacity: 0.35,
    ...(Platform.OS === 'web' ? ({ filter: 'blur(50px)' } as any) : {}),
  },
  modDarkTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'auto' },
  modDarkIcon: { width: 46, height: 46, borderRadius: 14, borderWidth: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.04)' },
  modArrowDark: { width: 34, height: 34, borderRadius: 999, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.1)' },
  modDarkTitle: { color: '#FFFFFF', fontSize: 21, fontWeight: '800', marginTop: 40, letterSpacing: -0.3 },
  modDarkSub: { color: 'rgba(255,255,255,0.62)', fontSize: 14, lineHeight: 21, marginTop: 6 },

  modRow: {
    flexDirection: 'row', alignItems: 'center', gap: 16, flexGrow: 1,
    backgroundColor: '#FFFFFF', borderRadius: 20, padding: 16, borderWidth: 1, borderColor: '#EDE3F5', ...cardShadow,
  },
  modRowIcon: { width: 56, height: 56, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  modRowTitle: { fontSize: 18, fontWeight: '700', color: '#16132A', fontFamily: DISPLAY_FONT, marginBottom: 3 },
  modRowArrow: { width: 38, height: 38, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },

  modOutline: {
    flexGrow: 1, borderRadius: 24, padding: 24, minHeight: 220, overflow: 'hidden',
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#EADFF3', ...cardShadow,
  },
  modOutlineWash: { position: 'absolute', top: 0, right: 0, width: '70%', height: '70%' },
  modOutlineIcon: { width: 42, height: 42, borderRadius: 999, alignItems: 'center', justifyContent: 'center', marginBottom: 22 },
  modOutlineTitle: { fontSize: 24, lineHeight: 30, fontWeight: '700', color: '#16132A', fontFamily: DISPLAY_FONT, marginBottom: 8, letterSpacing: -0.3 },
  modOutlineFoot: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 'auto', paddingTop: 18 },
  modOutlineLink: { fontSize: 13, fontWeight: '800', letterSpacing: 0.3 },
  filters: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 22, justifyContent: 'center', maxWidth: 1120, alignSelf: 'center' },
  filterChip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#E4D4F0' },
  filterChipOn: { backgroundColor: '#8E24AA', borderColor: '#8E24AA' },
  filterText: { fontSize: 13, fontWeight: '700', color: '#5E35B1' },
  filterTextOn: { color: '#FFFFFF' },

  stepRow: { marginTop: 36, gap: 16, width: '100%', maxWidth: 1120, alignSelf: 'center' },
  stepRowWide: { flexDirection: 'row' },
  stepCard: {
    backgroundColor: '#FFFFFF', borderRadius: 24, padding: 26,
    borderWidth: 1, borderColor: '#EFE6F6', ...cardShadow,
  },
  stepNum: { fontSize: 13, fontWeight: '800', color: COLORS.primary, letterSpacing: 1, marginBottom: 12 },
  stepBadge: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  stepBadgeText: { color: '#FFFFFF', fontSize: 14, fontWeight: '800' },

  productRow: { width: '100%', maxWidth: 1120, alignSelf: 'center', gap: 28 },
  productRowWide: { flexDirection: 'row', alignItems: 'center', gap: 48 },
  engineRow: {
    flexDirection: 'row', gap: 14, alignItems: 'flex-start',
    backgroundColor: '#FFFFFF', borderRadius: 20, padding: 18,
    borderWidth: 1, borderColor: '#EFE8F6', ...cardShadow,
  },

  privateRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16 },
  privateText: { fontSize: 14, fontWeight: '700', color: '#16132A' },

  priceRow: { marginTop: 32, gap: 16, width: '100%', maxWidth: 860, alignSelf: 'center' },
  priceRowWide: { flexDirection: 'row' },
  priceCard: { padding: 26 },
  priceNote: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', marginTop: 16 },
  faqList: {
    width: '100%', maxWidth: 860, alignSelf: 'center', marginTop: 28,
    backgroundColor: '#FFFFFF', borderRadius: 24, borderWidth: 1, borderColor: '#EFE6F6',
    overflow: 'hidden', ...cardShadow,
  },
  faqItem: { paddingHorizontal: 22, paddingVertical: 18 },
  faqDivider: { borderTopWidth: 1, borderTopColor: '#F0E8F6' },
  faqHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 16 },
  faqQ: { flex: 1, fontSize: 16, fontWeight: '700', color: '#16132A', lineHeight: 24 },
  faqA: { fontSize: 15, lineHeight: 24, color: '#5C6378', marginTop: 10, paddingRight: 28 },

  ctaBand: { backgroundColor: '#F3E5F5', paddingHorizontal: 24, paddingTop: 24, paddingBottom: 72, alignItems: 'center' },
  ctaCard: {
    width: '100%', maxWidth: 760, backgroundColor: '#14102A', borderRadius: 28,
    paddingHorizontal: 36, paddingVertical: 48, alignItems: 'center',
    ...(Platform.OS === 'web' ? { boxShadow: '0 24px 60px rgba(26, 35, 126, 0.18)' } as any : { elevation: 4 }),
  },
  ctaKicker: { color: '#F48FB1', fontSize: 12, fontWeight: '700', letterSpacing: 3.2 },
  ctaTitle: { color: '#FFFFFF', fontSize: 22, fontWeight: '500', textAlign: 'center', marginTop: 16, letterSpacing: 0.2 },
  ctaAccent: { color: '#FFFFFF', fontSize: 40, fontWeight: '800', textAlign: 'center', marginTop: 6, letterSpacing: -1.2, lineHeight: 46 },
  ctaSub: { color: 'rgba(255,255,255,0.72)', fontSize: 16, fontWeight: '400', textAlign: 'center', marginTop: 14, maxWidth: 480, lineHeight: 26 },
  ctaBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 22, paddingVertical: 14, borderRadius: 999, marginTop: 26,
  },
  ctaBtnText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
});
