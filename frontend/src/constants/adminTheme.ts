/**
 * Admin design tokens — separate from mobile COLORS.
 * Inspired by Tata Neu (super-app shell) + Groww (clarity) + Linear (density).
 */
export const ADMIN_THEME = {
  // Sidebar (slate-950 → cool dark with subtle warmth)
  sidebar: {
    bg: '#0B1220',
    bgHover: '#111A2E',
    bgActive: '#1E293B',
    border: '#1E293B',
    text: '#94A3B8',
    textActive: '#F8FAFC',
    accent: '#7C3AED',
    sectionLabel: '#475569',
    width: 240,
    widthCollapsed: 64,
  },
  // Topbar
  topbar: {
    bg: '#FFFFFF',
    border: '#E2E8F0',
    text: '#0F172A',
    textMuted: '#64748B',
    height: 60,
  },
  // Content area
  content: {
    bg: '#F8FAFC',
    cardBg: '#FFFFFF',
    cardBorder: '#E2E8F0',
    cardBorderHover: '#CBD5E1',
    maxWidth: 1280,
    padding: 24,
    gap: 20,
  },
  // Typography scale
  type: {
    display: { size: 32, weight: '800' as const, lineHeight: 40, letterSpacing: -0.5 },
    h1:      { size: 24, weight: '800' as const, lineHeight: 32, letterSpacing: -0.3 },
    h2:      { size: 18, weight: '700' as const, lineHeight: 26 },
    h3:      { size: 15, weight: '700' as const, lineHeight: 22 },
    body:    { size: 14, weight: '500' as const, lineHeight: 22 },
    bodyStrong: { size: 14, weight: '700' as const, lineHeight: 22 },
    small:   { size: 12, weight: '500' as const, lineHeight: 18 },
    label:   { size: 11, weight: '700' as const, lineHeight: 16, letterSpacing: 0.5 },
    mono:    { size: 12, weight: '500' as const, lineHeight: 18 },
  },
  // Semantic
  semantic: {
    primary: '#7C3AED',
    primarySoft: '#F5F3FF',
    success: '#059669',
    successSoft: '#D1FAE5',
    warn: '#D97706',
    warnSoft: '#FEF3C7',
    danger: '#DC2626',
    dangerSoft: '#FEE2E2',
    info: '#2563EB',
    infoSoft: '#DBEAFE',
    text: '#0F172A',
    textSecondary: '#475569',
    textMuted: '#94A3B8',
    divider: '#E2E8F0',
  },
  // Spacing rhythm
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  // Radii
  radius: { sm: 4, md: 8, lg: 12, xl: 16 },
  // Shadows (web-style, low elevation)
  shadow: {
    card:  '0 1px 2px rgba(15,23,42,0.04), 0 1px 3px rgba(15,23,42,0.06)',
    raise: '0 4px 12px rgba(15,23,42,0.08), 0 2px 4px rgba(15,23,42,0.04)',
  },
};

export const BREAKPOINTS = {
  mobile: 768,
  tablet: 1024,
  desktop: 1280,
};

export type AdminNavItem = {
  key: string;
  label: string;
  icon: string;
  href: string;
  badge?: string | number;
};

export type AdminNavSection = {
  label: string;
  items: AdminNavItem[];
};

export const ADMIN_NAV: AdminNavSection[] = [
  {
    label: 'Overview',
    items: [
      { key: 'home',     label: 'Dashboard',         icon: 'grid',                 href: '/admin' },
      { key: 'audit',    label: 'Audit Trail',       icon: 'time',                 href: '/admin/audit-trail' },
      { key: 'incident', label: 'Incident Response', icon: 'alert-circle',         href: '/admin/incident-response' },
    ],
  },
  {
    label: 'People & Access',
    items: [
      { key: 'org',      label: 'Org Members',       icon: 'people',               href: '/admin/org-members' },
      { key: 'experts',  label: 'Experts',           icon: 'star',                 href: '/admin/experts' },
      { key: 'approvals',label: 'Pending Approvals', icon: 'checkmark-circle',     href: '/admin/pending-approvals' },
      { key: 'acm',      label: 'Access Control',    icon: 'shield-checkmark',     href: '/admin/acm' },
    ],
  },
  {
    label: 'Subscriptions & GTM',
    items: [
      { key: 'tier',     label: 'Tier Matrix',       icon: 'apps',                 href: '/admin/tier-matrix' },
      { key: 'segments', label: 'Customer Segments', icon: 'people-circle',        href: '/admin/customer-segments' },
      { key: 'pricing',  label: 'Pricing Page',      icon: 'pricetag',             href: '/pricing' },
    ],
  },
  {
    label: 'Content & Tools',
    items: [
      { key: 'modes',    label: 'Decision Modes',    icon: 'options',              href: '/admin/decision-modes' },
      { key: 'tmpl',     label: 'Templates',         icon: 'document-text',        href: '/admin/templates' },
      { key: 'social',   label: 'Social Learning',   icon: 'school',               href: '/admin/social-learning-admin' },
      { key: 'review',   label: 'ReviewNet',         icon: 'thumbs-up',            href: '/admin/review-net' },
    ],
  },
  {
    label: 'System',
    items: [
      { key: 'docs',     label: 'Admin Docs',        icon: 'library',              href: '/admin/docs' },
      { key: 'settings', label: 'Settings',          icon: 'settings',             href: '/admin/settings' },
    ],
  },
];

export const isAdminRole = (role?: string): boolean => {
  if (!role) return false;
  const r = role.toLowerCase();
  return r === 'admin' || r === 'super_admin' || r === 'co_admin';
};
