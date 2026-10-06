/**
 * MarketingHeader — public navigation.
 * `bar` is the light bar used on legal pages.
 * `pill` is the floating capsule used on the landing and product pages.
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, useWindowDimensions, Image, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../../constants/colors';
import { useAppLogo, useCompany } from '../../contexts/FontFamilyContext';

export type MarketingNavLink = { label: string; href: string };

const accentGradient = GRADIENTS.accent as unknown as readonly [string, string];
/** Same mark the login screen uses when the admin logo has not loaded yet. */
const PROJECT_MARK = 'https://customer-assets.emergentagent.com/job_chapter2-guide/artifacts/acyqe96y_VENTURE%20BUDDHA-SqaureHD.png';

export default function MarketingHeader({
  activeCta = true,
  links = [],
  onJump,
  appearance = 'bar',
  canvas = 'paper',
  overlay = false,
}: {
  activeCta?: boolean;
  links?: MarketingNavLink[];
  onJump?: (id: string) => void;
  appearance?: 'bar' | 'pill' | 'light';
  /** Page color behind a light pill. `ink` is the dark booking page. */
  canvas?: 'paper' | 'ink';
  /** Transparent wrap so the hero background shows behind the pill. */
  overlay?: boolean;
}) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const compact = width < 720;
  const showLinks = links.length > 0 && width >= 1180;
  const logoUri = useAppLogo();
  const company = useCompany();
  const [open, setOpen] = React.useState(false);
  const [markFailed, setMarkFailed] = React.useState(false);
  React.useEffect(() => { setMarkFailed(false); }, [logoUri]);
  const markUri = markFailed ? null : (logoUri || PROJECT_MARK);
  const pill = appearance === 'pill';
  const light = appearance === 'light';
  const floating = pill || light;

  const go = (link: MarketingNavLink) => {
    setOpen(false);
    const hash = link.href.includes('#') ? link.href.split('#')[1] : '';
    const path = link.href.split('#')[0] || '/';
    const homeTarget = path === '/' || path === '' || path === '/index';
    if (hash && homeTarget && onJump) {
      onJump(hash);
      return;
    }
    if (hash && homeTarget) {
      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        window.location.assign(`/#${hash}`);
        return;
      }
      router.push(`/#${hash}` as any);
      return;
    }
    router.push(link.href as any);
  };

  const brand = (
    <TouchableOpacity style={styles.brand} activeOpacity={0.8} onPress={() => router.push('/')}>
      {markUri ? (
        <Image source={{ uri: markUri }} style={styles.markImg} resizeMode="contain" onError={() => setMarkFailed(true)} />
      ) : (
        <LinearGradient colors={accentGradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.mark}>
          <Ionicons name="sparkles" size={16} color="#FFFFFF" />
        </LinearGradient>
      )}
      <Text style={[styles.brandName, pill && styles.brandNameLight]} numberOfLines={1}>{company.product}</Text>
    </TouchableOpacity>
  );

  const nav = showLinks ? (
    <View style={styles.nav}>
      {links.map((link) => (
        <TouchableOpacity
          key={link.href}
          style={styles.navBtn}
          onPress={() => go(link)}
          {...(Platform.OS === 'web' ? { dataSet: { navlink: '1' } } : {})}
        >
          <Text style={[styles.navText, pill && styles.navTextLight, light && styles.navTextInk]}>{link.label}</Text>
        </TouchableOpacity>
      ))}
    </View>
  ) : null;

  const actions = activeCta ? (
    <View style={styles.actions}>
      {!compact && (
        <TouchableOpacity style={styles.ghostBtn} onPress={() => router.push('/auth/login')}>
          <Text style={[styles.ghostBtnText, pill && styles.ghostBtnTextLight, light && styles.navTextInk]}>Sign in</Text>
        </TouchableOpacity>
      )}
      <TouchableOpacity activeOpacity={0.9} onPress={() => {
        if (onJump) { onJump('demo'); return; }
        if (Platform.OS === 'web' && typeof window !== 'undefined') { window.location.assign('/#demo'); return; }
        router.push('/#demo' as any);
      }}>
        <LinearGradient colors={accentGradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.demoBtn}>
          <Text style={styles.demoText}>{compact ? 'Demo' : 'Book a Demo'}</Text>
        </LinearGradient>
      </TouchableOpacity>
      {links.length > 0 && !showLinks && (
        <TouchableOpacity style={[styles.menuBtn, pill && styles.menuBtnLight, light && styles.menuBtnInk]} onPress={() => setOpen((v) => !v)} accessibilityLabel="Open menu">
          <Ionicons name={open ? 'close' : 'menu'} size={18} color={pill ? '#FFFFFF' : COLORS.textPrimary} />
        </TouchableOpacity>
      )}
    </View>
  ) : null;

  const menu = open && !showLinks ? (
    <View style={[styles.menu, pill && styles.menuDark]}>
      {links.map((link) => (
        <TouchableOpacity key={link.href} style={styles.menuItem} onPress={() => go(link)}>
          <Text style={[styles.menuText, pill && styles.menuTextLight]}>{link.label}</Text>
        </TouchableOpacity>
      ))}
      {compact && (
        <TouchableOpacity style={styles.menuItem} onPress={() => { setOpen(false); router.push('/auth/login'); }}>
          <Text style={[styles.menuText, pill && styles.menuTextLight]}>Sign in</Text>
        </TouchableOpacity>
      )}
    </View>
  ) : null;

  if (!floating) {
    return (
      <View style={styles.bar}>
        {brand}
        {nav}
        {actions}
        {menu}
      </View>
    );
  }

  return (
    <View style={[styles.pillWrap, light && (canvas === 'ink' ? styles.lightWrapInk : styles.lightWrap), overlay && styles.pillWrapOverlay]}>
      <View style={[styles.pill, light && styles.lightPill]}>
        {brand}
        {nav}
        {actions}
      </View>
      {menu}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 22, paddingVertical: 12,
    backgroundColor: 'rgba(255,255,255,0.92)',
    borderBottomWidth: 1, borderBottomColor: 'rgba(229,231,235,0.9)',
    ...(Platform.OS === 'web' ? {
      position: 'sticky' as const, top: 0, zIndex: 40,
      backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
    } as any : {}),
  },
  pillWrapOverlay: { backgroundColor: 'transparent', pointerEvents: 'box-none' },
  pillWrap: {
    paddingHorizontal: 16, paddingTop: 14, paddingBottom: 6,
    backgroundColor: '#070B1C', zIndex: 40, position: 'relative',
    ...(Platform.OS === 'web' ? { position: 'sticky' as const, top: 0 } as any : {}),
  },
  pill: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    maxWidth: 1180, width: '100%', alignSelf: 'center',
    backgroundColor: 'rgba(18, 22, 48, 0.92)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)',
    borderRadius: 999, paddingLeft: 16, paddingRight: 10, paddingVertical: 10,
    ...(Platform.OS === 'web' ? { boxShadow: '0 10px 30px rgba(0,0,0,0.28)' } as any : { elevation: 4 }),
  },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 10, flexShrink: 1, paddingRight: 8 },
  mark: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  markImg: { width: 38, height: 38, borderRadius: 10 },
  brandName: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary, letterSpacing: 0.2 },
  brandNameLight: { color: '#FFFFFF' },
  nav: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 0 },
  navBtn: { paddingHorizontal: 9, paddingVertical: 8, borderRadius: 8 },
  navText: { fontSize: 15, fontWeight: '600', color: COLORS.textSecondary },
  navTextLight: { color: 'rgba(255,255,255,0.82)' },
  actions: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  ghostBtn: { paddingHorizontal: 10, paddingVertical: 8, borderRadius: 8 },
  ghostBtnText: { fontSize: 15, fontWeight: '700', color: COLORS.primary },
  ghostBtnTextLight: { color: 'rgba(255,255,255,0.88)' },
  demoBtn: { paddingHorizontal: 16, paddingVertical: 10, borderRadius: 999 },
  demoText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  menuBtn: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  menuBtnLight: { backgroundColor: 'rgba(255,255,255,0.08)' },
  menuBtnInk: { backgroundColor: 'rgba(26,35,126,0.06)' },
  lightWrap: { backgroundColor: '#F6F3FB' },
  lightWrapInk: { backgroundColor: '#070B1C' },
  lightPill: {
    backgroundColor: '#FFFFFF',
    borderColor: 'rgba(26, 35, 126, 0.08)',
    ...(Platform.OS === 'web' ? { boxShadow: '0 10px 30px rgba(26, 35, 126, 0.08)' } as any : {}),
  },
  navTextInk: { color: '#1F2437' },
  menu: {
    position: 'absolute', top: 64, right: 22, minWidth: 220,
    backgroundColor: '#FFFFFF', borderRadius: 16, paddingVertical: 8,
    borderWidth: 1, borderColor: '#EFE8F6', zIndex: 50,
    ...(Platform.OS === 'web' ? { boxShadow: '0 16px 40px rgba(15,23,42,0.12)' } as any : { elevation: 6 }),
  },
  menuDark: {
    backgroundColor: '#14182F', borderColor: 'rgba(255,255,255,0.1)', top: 78, right: 28,
  },
  menuItem: { paddingHorizontal: 16, paddingVertical: 12 },
  menuText: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  menuTextLight: { color: '#FFFFFF', fontWeight: '600' },
});
