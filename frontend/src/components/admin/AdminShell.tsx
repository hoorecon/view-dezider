/**
 * AdminShell — responsive sidebar + topbar layout for /admin/* routes.
 *
 * Web (>=768px): persistent left sidebar (240px) + topbar (60px) + content area.
 * Mobile (<768px): hamburger drawer + compact topbar + content full-width.
 */
import React, { useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, Pressable,
  useWindowDimensions, Platform, Modal,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { usePathname, useRouter } from 'expo-router';
import { ADMIN_THEME, ADMIN_NAV, BREAKPOINTS, AdminNavItem, AdminNavSection } from '../../constants/adminTheme';
import { useAuthStore } from '../../store/authStore';

interface AdminShellProps {
  children: React.ReactNode;
  /** Override the page title shown in the topbar (defaults to nav-item label). */
  title?: string;
  /** Optional right-side topbar slot (e.g., New / Refresh / Export buttons). */
  rightSlot?: React.ReactNode;
}

export default function AdminShell({ children, title, rightSlot }: AdminShellProps) {
  const { width } = useWindowDimensions();
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore(s => s.user);
  const logout = useAuthStore(s => s.logout);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isDesktop = width >= BREAKPOINTS.mobile;

  // Find active item for breadcrumbs / title
  const activeItem = useMemo(() => {
    for (const sec of ADMIN_NAV) {
      for (const it of sec.items) {
        if (it.href === pathname || pathname?.startsWith(it.href + '/')) return { sec, it };
      }
    }
    return null;
  }, [pathname]);

  const headerTitle = title || activeItem?.it.label || 'Admin Console';
  const headerSection = activeItem?.sec.label || 'Earth Dezider';

  const Sidebar = (
    <View style={[s.sidebar, !isDesktop && s.sidebarMobile]}>
      {/* Brand block */}
      <View style={s.brandBlock}>
        <View style={s.brandRow}>
          <View style={s.brandLogo}>
            <Ionicons name="planet" size={20} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.brandName}>Earth Dezider</Text>
            <Text style={s.brandSub}>ADMIN CONSOLE</Text>
          </View>
          {!isDesktop && (
            <TouchableOpacity onPress={() => setDrawerOpen(false)} hitSlop={10}>
              <Ionicons name="close" size={20} color={ADMIN_THEME.sidebar.text} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Nav sections */}
      <ScrollView
        style={{ flex: 1 }}
        showsVerticalScrollIndicator={Platform.OS === 'web'}
        contentContainerStyle={{ paddingBottom: 12 }}
      >
        {ADMIN_NAV.map(section => (
          <View key={section.label} style={s.navSection}>
            <Text style={s.navSectionLabel}>{section.label}</Text>
            {section.items.map(item => {
              const isActive =
                pathname === item.href ||
                (item.href !== '/admin' && pathname?.startsWith(item.href));
              return (
                <Pressable
                  key={item.key}
                  onPress={() => { router.push(item.href as any); setDrawerOpen(false); }}
                  style={({ hovered, pressed }: any) => [
                    s.navItem,
                    isActive && s.navItemActive,
                    (hovered || pressed) && !isActive && s.navItemHover,
                  ]}
                  testID={`admin-nav-${item.key}`}
                >
                  <Ionicons
                    name={item.icon as any}
                    size={16}
                    color={isActive ? ADMIN_THEME.sidebar.textActive : ADMIN_THEME.sidebar.text}
                  />
                  <Text style={[s.navItemText, isActive && s.navItemTextActive]} numberOfLines={1}>
                    {item.label}
                  </Text>
                  {item.badge ? (
                    <View style={s.navBadge}><Text style={s.navBadgeText}>{item.badge}</Text></View>
                  ) : null}
                  {isActive && <View style={s.navActiveBar} />}
                </Pressable>
              );
            })}
          </View>
        ))}
      </ScrollView>

      {/* User block (bottom) */}
      <View style={s.userBlock}>
        <View style={s.userAvatar}>
          <Text style={s.userAvatarText}>{(user?.name || user?.email || 'A')[0].toUpperCase()}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.userName} numberOfLines={1}>{user?.name || 'Admin'}</Text>
          <View style={s.userMeta}>
            <View style={s.roleBadge}>
              <Ionicons name="shield-checkmark" size={9} color="#A78BFA" />
              <Text style={s.roleBadgeText}>{(user?.role || 'admin').toUpperCase()}</Text>
            </View>
          </View>
        </View>
        <TouchableOpacity
          onPress={() => { setDrawerOpen(false); router.replace('/' as any); }}
          hitSlop={8}
          style={s.userActionBtn}
          accessibilityLabel="Switch to user view"
        >
          <Ionicons name="swap-horizontal" size={14} color={ADMIN_THEME.sidebar.text} />
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => logout()}
          hitSlop={8}
          style={s.userActionBtn}
          accessibilityLabel="Logout"
        >
          <Ionicons name="log-out-outline" size={14} color={ADMIN_THEME.sidebar.text} />
          {isDesktop && <Text style={s.userActionLabel}>Logout</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );

  const Topbar = (
    <View style={s.topbar}>
      {!isDesktop && (
        <TouchableOpacity onPress={() => setDrawerOpen(true)} hitSlop={8} style={{ marginRight: 12 }}>
          <Ionicons name="menu" size={22} color={ADMIN_THEME.topbar.text} />
        </TouchableOpacity>
      )}
      <View style={{ flex: 1, minWidth: 0 }}>
        <View style={s.breadcrumbs}>
          <Text style={s.breadcrumbMuted}>{headerSection}</Text>
          <Ionicons name="chevron-forward" size={11} color={ADMIN_THEME.topbar.textMuted} style={{ marginHorizontal: 4 }} />
          <Text style={s.breadcrumbActive} numberOfLines={1}>{headerTitle}</Text>
        </View>
      </View>
      {rightSlot}
      <View style={s.topbarRight}>
        <TouchableOpacity style={s.topbarIconBtn} onPress={() => router.replace('/' as any)}>
          <Ionicons name="open-outline" size={16} color={ADMIN_THEME.topbar.text} />
          {isDesktop && <Text style={s.topbarBtnText}>User View</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );

  // Mobile drawer modal
  const MobileDrawer = !isDesktop && drawerOpen ? (
    <Modal visible transparent animationType="slide" onRequestClose={() => setDrawerOpen(false)}>
      <View style={s.drawerOverlay}>
        <View style={s.drawerContent}>{Sidebar}</View>
        <Pressable style={s.drawerBackdrop} onPress={() => setDrawerOpen(false)} />
      </View>
    </Modal>
  ) : null;

  return (
    <View style={s.root}>
      {isDesktop && Sidebar}
      <View style={[s.main, isDesktop && { marginLeft: ADMIN_THEME.sidebar.width }]}>
        {Topbar}
        <ScrollView
          style={s.scroll}
          contentContainerStyle={[s.scrollContent, isDesktop && { paddingHorizontal: ADMIN_THEME.content.padding }]}
        >
          <View style={[s.contentInner, isDesktop && { maxWidth: ADMIN_THEME.content.maxWidth }]}>
            {children}
          </View>
        </ScrollView>
      </View>
      {MobileDrawer}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: ADMIN_THEME.content.bg, flexDirection: 'row' },
  main: { flex: 1, minWidth: 0 },
  scroll: { flex: 1 },
  scrollContent: { paddingVertical: ADMIN_THEME.content.padding, paddingHorizontal: 12 },
  contentInner: { width: '100%', alignSelf: 'center' },

  // Sidebar
  sidebar: {
    width: ADMIN_THEME.sidebar.width,
    backgroundColor: ADMIN_THEME.sidebar.bg,
    borderRightWidth: 1,
    borderRightColor: ADMIN_THEME.sidebar.border,
    height: '100%',
    position: Platform.OS === 'web' ? ('fixed' as any) : 'absolute',
    top: 0, left: 0, bottom: 0,
    flexDirection: 'column',
  },
  sidebarMobile: { position: 'relative', height: '100%' },

  brandBlock: { padding: 16, borderBottomWidth: 1, borderBottomColor: ADMIN_THEME.sidebar.border },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  brandLogo: { width: 32, height: 32, borderRadius: 8, backgroundColor: ADMIN_THEME.semantic.primary, alignItems: 'center', justifyContent: 'center' },
  brandName: { color: '#F8FAFC', fontSize: 14, fontWeight: '700' },
  brandSub: { color: ADMIN_THEME.sidebar.sectionLabel, fontSize: 9, fontWeight: '700', letterSpacing: 1, marginTop: 2 },

  navSection: { paddingHorizontal: 12, paddingTop: 18 },
  navSectionLabel: { fontSize: 10, color: ADMIN_THEME.sidebar.sectionLabel, fontWeight: '700', letterSpacing: 0.8, paddingHorizontal: 8, paddingBottom: 6, textTransform: 'uppercase' },
  navItem: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 6, marginBottom: 1 },
  navItemHover: { backgroundColor: ADMIN_THEME.sidebar.bgHover },
  navItemActive: { backgroundColor: ADMIN_THEME.sidebar.bgActive },
  navItemText: { color: ADMIN_THEME.sidebar.text, fontSize: 13, fontWeight: '500', flex: 1 },
  navItemTextActive: { color: ADMIN_THEME.sidebar.textActive, fontWeight: '600' },
  navActiveBar: { width: 3, height: 16, backgroundColor: ADMIN_THEME.semantic.primary, borderRadius: 2, position: 'absolute', left: 0 },
  navBadge: { backgroundColor: ADMIN_THEME.semantic.primary, paddingHorizontal: 6, paddingVertical: 1, borderRadius: 8, minWidth: 18, alignItems: 'center' },
  navBadgeText: { color: '#FFF', fontSize: 9, fontWeight: '700' },

  userBlock: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderTopWidth: 1, borderTopColor: ADMIN_THEME.sidebar.border, backgroundColor: '#0A1020' },
  userAvatar: { width: 30, height: 30, borderRadius: 15, backgroundColor: ADMIN_THEME.semantic.primary, alignItems: 'center', justifyContent: 'center' },
  userAvatarText: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  userName: { color: '#F8FAFC', fontSize: 12, fontWeight: '600' },
  userMeta: { flexDirection: 'row', marginTop: 3 },
  roleBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: 'rgba(124,58,237,0.16)', paddingHorizontal: 5, paddingVertical: 2, borderRadius: 4 },
  roleBadgeText: { color: '#C4B5FD', fontSize: 8, fontWeight: '700', letterSpacing: 0.4 },
  userActionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    padding: 6,
    borderRadius: 6,
  },
  userActionLabel: {
    fontSize: 11,
    fontWeight: '600',
    color: '#CBD5E1',
    marginLeft: 2,
  },

  // Topbar
  topbar: {
    flexDirection: 'row', alignItems: 'center',
    height: ADMIN_THEME.topbar.height,
    backgroundColor: ADMIN_THEME.topbar.bg,
    borderBottomWidth: 1, borderBottomColor: ADMIN_THEME.topbar.border,
    paddingHorizontal: 18, gap: 12,
    position: Platform.OS === 'web' ? ('sticky' as any) : 'relative',
    top: 0, zIndex: 10,
  },
  breadcrumbs: { flexDirection: 'row', alignItems: 'center' },
  breadcrumbMuted: { color: ADMIN_THEME.topbar.textMuted, fontSize: 12, fontWeight: '600' },
  breadcrumbActive: { color: ADMIN_THEME.topbar.text, fontSize: 14, fontWeight: '700' },
  topbarRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  topbarIconBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, borderWidth: 1, borderColor: ADMIN_THEME.topbar.border },
  topbarBtnText: { color: ADMIN_THEME.topbar.text, fontSize: 12, fontWeight: '600' },

  // Mobile drawer
  drawerOverlay: { flex: 1, flexDirection: 'row' },
  drawerContent: { width: 280, height: '100%' },
  drawerBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)' },
});
