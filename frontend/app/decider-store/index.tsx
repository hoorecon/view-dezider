/**
 * /decider-store — The Decider Store (public storefront).
 *
 * Browsable WITHOUT login (route is whitelisted in app/_layout.tsx). Users tap a
 * template to view details and clone it into a prefilled MyDezider decision.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, RefreshControl, useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';

type Card = {
  template_id: string; title: string; subtitle?: string; description?: string;
  category?: string; decision_type?: string; cover_icon?: string; cover_color?: string;
  pricing_type?: string; price_paise?: number; currency?: string; kind?: string;
  allowed_clone_modes?: string[]; factor_count?: number; option_count?: number;
  install_count?: number; creator_name?: string;
  publisher_type?: 'individual' | 'expert' | 'organization';
  life_area?: string;
  applicable_org_types?: string[];
  rating_avg?: number;
  rating_count?: number;
};

type Facets = {
  life_areas: string[];
  org_types: string[];
  publisher_types: Array<{ key: string; label: string; count: number }>;
};

const PUBLISHER_TYPE_LABEL: Record<string, string> = {
  individual: 'Individual', expert: 'Expert', organization: 'Organization',
};

export default function DeciderStoreHome() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [cards, setCards] = useState<Card[]>([]);
  const [cats, setCats] = useState<{ key: string; count: number }[]>([]);
  const [cat, setCat] = useState<string>('all');
  const [q, setQ] = useState('');
  const [tab, setTab] = useState<'app' | 'template'>('app');
  const [facets, setFacets] = useState<Facets>({ life_areas: [], org_types: [], publisher_types: [] });
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [f, setF] = useState<{ life_area?: string; org_types: string[]; publisher_type?: string;
    min_factors?: string; max_factors?: string; min_options?: string; max_options?: string;
    is_free?: boolean | null; publisher_name?: string; min_rating?: string; min_ratings_count?: string; }>(
    { org_types: [], is_free: null }
  );
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const numCols = width >= 900 ? 3 : width >= 600 ? 2 : 1;

  const load = useCallback(async () => {
    try {
      const params: any = { kind: tab };
      if (cat !== 'all') params.category = cat;
      if (q.trim()) params.q = q.trim();
      if (f.life_area) params.life_area = f.life_area;
      if (f.org_types.length) params.org_types = f.org_types.join(',');
      if (f.publisher_type) params.publisher_type = f.publisher_type;
      if (f.min_factors) params.min_factors = Number(f.min_factors);
      if (f.max_factors) params.max_factors = Number(f.max_factors);
      if (f.min_options) params.min_options = Number(f.min_options);
      if (f.max_options) params.max_options = Number(f.max_options);
      if (f.is_free === true) params.is_free = true;
      if (f.is_free === false) params.is_free = false;
      if (f.publisher_name) params.publisher_name = f.publisher_name;
      if (f.min_rating) params.min_rating = Number(f.min_rating);
      if (f.min_ratings_count) params.min_ratings_count = Number(f.min_ratings_count);
      const [r, m, fx] = await Promise.all([
        api.get('/decider-store', { params }),
        api.get('/decider-store/meta'),
        api.get('/decider-store/facets').catch(() => ({ data: { life_areas: [], org_types: [], publisher_types: [] } })),
      ]);
      setCards(r.data.templates || []);
      setCats(m.data.categories || []);
      setFacets(fx.data as Facets);
    } catch {
      /* transient — leave existing */
    } finally { setLoading(false); setRefreshing(false); }
  }, [cat, q, tab, f]);

  useEffect(() => { load(); }, [load]);

  const price = (c: Card) =>
    c.pricing_type === 'paid' && (c.price_paise || 0) > 0
      ? `${c.currency === 'INR' ? '₹' : '$'}${((c.price_paise || 0) / 100).toFixed(0)}`
      : 'Free';

  const renderCard = (c: Card) => {
    const isApp = c.kind === 'app';
    return (
      <TouchableOpacity
        key={c.template_id}
        style={[s.card, { width: numCols === 1 ? '100%' : `${100 / numCols - 2}%` }]}
        activeOpacity={0.85}
        onPress={() => router.push(`/decider-store/${c.template_id}`)}
      >
        <View style={[s.cardCover, { backgroundColor: (c.cover_color || '#4F46E5') + '18' }]}>
          <Ionicons name={(c.cover_icon || 'grid') as any} size={26} color={c.cover_color || '#4F46E5'} />
          <View style={[s.priceTag, { backgroundColor: price(c) === 'Free' ? '#DCFCE7' : '#FEF3C7' }]}>
            <Text style={[s.priceTagText, { color: price(c) === 'Free' ? '#166534' : '#B45309' }]}>{price(c)}</Text>
          </View>
          {isApp && (
            <View style={s.finderTag}>
              <Ionicons name="search" size={10} color="#FFF" />
              <Text style={s.finderTagText}>FINDER</Text>
            </View>
          )}
        </View>
        <Text style={s.cardTitle} numberOfLines={2}>{c.title}</Text>
        {!!c.subtitle && <Text style={s.cardSub} numberOfLines={2}>{c.subtitle}</Text>}
        <View style={s.cardMeta}>
          <Text style={s.cardMetaText}>📊 {c.factor_count || 0}</Text>
          <Text style={s.cardMetaText}>🧩 {c.option_count || 0}</Text>
          <Text style={s.cardMetaText}>⬇️ {c.install_count || 0}</Text>
        </View>
        {/* Play-Store-style aggregate rating (Usefulness · Affordability · Accuracy) */}
        <View style={s.ratingRow}>
          {[1, 2, 3, 4, 5].map((i) => (
            <Ionicons key={i}
              name={(c.rating_avg || 0) >= i - 0.25 ? 'star' : (c.rating_avg || 0) >= i - 0.75 ? 'star-half' : 'star-outline'}
              size={12} color="#F59E0B" />
          ))}
          <Text style={s.ratingTxt}>
            {(c.rating_count || 0) > 0 ? `${(c.rating_avg || 0).toFixed(1)} · ${c.rating_count}` : 'No ratings yet'}
          </Text>
        </View>
        <View style={s.cardBadgeRow}>
          <View style={s.catPill}><Text style={s.catPillText}>{c.category}</Text></View>
          {c.publisher_type && (
            <View style={[s.catPill, { backgroundColor: '#E0E7FF' }]}>
              <Text style={[s.catPillText, { color: '#4338CA' }]}>{PUBLISHER_TYPE_LABEL[c.publisher_type] || c.publisher_type}</Text>
            </View>
          )}
        </View>
      </TouchableOpacity>
    );
  };

  const apps = cards.filter((c) => c.kind === 'app');
  const templates = cards.filter((c) => c.kind !== 'app');

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      {/* Hero */}
      <View style={s.hero}>
        <View style={s.heroRow}>
          <View style={s.brandBadge}><Ionicons name="storefront" size={18} color="#FFF" /></View>
          <View style={{ flex: 1 }}>
            <Text style={s.heroTitle}>The Decider Store</Text>
            <Text style={s.heroTag}>Clone expert-built decision blueprints in one tap.</Text>
          </View>
          {!isAuthenticated && (
            <TouchableOpacity style={s.signIn} onPress={() => router.push('/auth/login')}>
              <Text style={s.signInText}>Sign in</Text>
            </TouchableOpacity>
          )}
          {isAuthenticated && (
            <View style={s.heroLinks}>
              <TouchableOpacity style={s.heroLink} onPress={() => router.push('/admaker-studio' as any)}>
                <Ionicons name="megaphone" size={13} color="#FDE68A" />
                <Text style={s.heroLinkText}>AdMaker</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.heroLink} onPress={() => router.push('/adtaker-portal' as any)}>
                <Ionicons name="globe" size={13} color="#BAE6FD" />
                <Text style={s.heroLinkText}>Publisher</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      </View>

      {/* 2-tab bar — Decider Apps / Decision Templates (independent filters) */}
      <View style={s.tabBar}>
        <TouchableOpacity style={[s.tabBtn, tab === 'app' && s.tabBtnOn]} onPress={() => setTab('app')}>
          <Ionicons name="cube" size={15} color={tab === 'app' ? '#FFF' : '#4F46E5'} />
          <Text style={[s.tabTxt, tab === 'app' && s.tabTxtOn]}>Decider Apps · Finders</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.tabBtn, tab === 'template' && s.tabBtnOn]} onPress={() => setTab('template')}>
          <Ionicons name="document-text" size={15} color={tab === 'template' ? '#FFF' : '#4F46E5'} />
          <Text style={[s.tabTxt, tab === 'template' && s.tabTxtOn]}>Decision Templates</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.filterBtn} onPress={() => setFiltersOpen(!filtersOpen)}>
          <Ionicons name="options" size={16} color="#4F46E5" />
          <Text style={s.filterBtnTxt}>Filters</Text>
        </TouchableOpacity>
      </View>

      {/* Search — scoped to the active tab so the placeholder & results always
          match what the visitor is browsing. Sits INSIDE the tab body (below
          the tab bar) instead of above it. */}
      <View style={s.searchWrap}>
        <View style={s.search}>
          <Ionicons name="search" size={16} color="#94A3B8" />
          <TextInput
            style={s.searchInput}
            value={q}
            onChangeText={setQ}
            onSubmitEditing={load}
            placeholder={tab === 'app' ? 'Search Decider Apps…' : 'Search Decision Templates…'}
            placeholderTextColor="#94A3B8"
            returnKeyType="search"
          />
          {!!q && <TouchableOpacity onPress={() => { setQ(''); }}><Ionicons name="close-circle" size={16} color="#CBD5E1" /></TouchableOpacity>}
        </View>
      </View>

      {/* Filter drawer (collapsible) */}
      {filtersOpen && (
        <View style={s.filterPanel}>
          <View style={s.fRow}>
            <Text style={s.fLabel}>Life area</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
              <TouchableOpacity style={[s.fChip, !f.life_area && s.fChipOn]} onPress={() => setF({ ...f, life_area: undefined })}>
                <Text style={[s.fChipTxt, !f.life_area && s.fChipTxtOn]}>All</Text>
              </TouchableOpacity>
              {facets.life_areas.map((la) => (
                <TouchableOpacity key={la} style={[s.fChip, f.life_area === la && s.fChipOn]} onPress={() => setF({ ...f, life_area: la })}>
                  <Text style={[s.fChipTxt, f.life_area === la && s.fChipTxtOn]}>{la}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>
          <View style={s.fRow}>
            <Text style={s.fLabel}>Applicable org type(s)</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
              {facets.org_types.map((ot) => {
                const on = f.org_types.includes(ot);
                return (
                  <TouchableOpacity key={ot} style={[s.fChip, on && s.fChipOn]}
                    onPress={() => setF({ ...f, org_types: on ? f.org_types.filter((x) => x !== ot) : [...f.org_types, ot] })}>
                    <Text style={[s.fChipTxt, on && s.fChipTxtOn]}>{ot.replace(/_/g, ' ')}</Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
          <View style={s.fRow}>
            <Text style={s.fLabel}>Publisher type</Text>
            <View style={{ flexDirection: 'row', gap: 6 }}>
              <TouchableOpacity style={[s.fChip, !f.publisher_type && s.fChipOn]} onPress={() => setF({ ...f, publisher_type: undefined })}>
                <Text style={[s.fChipTxt, !f.publisher_type && s.fChipTxtOn]}>Any</Text>
              </TouchableOpacity>
              {facets.publisher_types.map((p) => (
                <TouchableOpacity key={p.key} style={[s.fChip, f.publisher_type === p.key && s.fChipOn]} onPress={() => setF({ ...f, publisher_type: p.key })}>
                  <Text style={[s.fChipTxt, f.publisher_type === p.key && s.fChipTxtOn]}>{p.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          <View style={[s.fRow, { flexDirection: 'row', gap: 8 }]}>
            <View style={{ flex: 1 }}>
              <Text style={s.fLabel}>Factors (≥ / ≤)</Text>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <TextInput style={s.fNum} keyboardType="numeric" placeholder="min" placeholderTextColor="#94A3B8"
                  value={f.min_factors || ''} onChangeText={(v) => setF({ ...f, min_factors: v.replace(/\D/g, '') })} />
                <TextInput style={s.fNum} keyboardType="numeric" placeholder="max" placeholderTextColor="#94A3B8"
                  value={f.max_factors || ''} onChangeText={(v) => setF({ ...f, max_factors: v.replace(/\D/g, '') })} />
              </View>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.fLabel}>Options (≥ / ≤)</Text>
              <View style={{ flexDirection: 'row', gap: 6 }}>
                <TextInput style={s.fNum} keyboardType="numeric" placeholder="min" placeholderTextColor="#94A3B8"
                  value={f.min_options || ''} onChangeText={(v) => setF({ ...f, min_options: v.replace(/\D/g, '') })} />
                <TextInput style={s.fNum} keyboardType="numeric" placeholder="max" placeholderTextColor="#94A3B8"
                  value={f.max_options || ''} onChangeText={(v) => setF({ ...f, max_options: v.replace(/\D/g, '') })} />
              </View>
            </View>
          </View>
          <View style={s.fRow}>
            <Text style={s.fLabel}>Price</Text>
            <View style={{ flexDirection: 'row', gap: 6 }}>
              {[
                { k: null, lbl: 'Any' },
                { k: true, lbl: 'Free only' },
                { k: false, lbl: 'Paid only' },
              ].map((o: any) => (
                <TouchableOpacity key={String(o.k)} style={[s.fChip, f.is_free === o.k && s.fChipOn]}
                  onPress={() => setF({ ...f, is_free: o.k })}>
                  <Text style={[s.fChipTxt, f.is_free === o.k && s.fChipTxtOn]}>{o.lbl}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
          <View style={[s.fRow, { flexDirection: 'row', gap: 8 }]}>
            <View style={{ flex: 1 }}>
              <Text style={s.fLabel}>Publisher name</Text>
              <TextInput style={s.fNum} placeholder="Search…" placeholderTextColor="#94A3B8"
                value={f.publisher_name || ''} onChangeText={(v) => setF({ ...f, publisher_name: v })} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.fLabel}>Min avg rating</Text>
              <TextInput style={s.fNum} keyboardType="decimal-pad" placeholder="e.g. 4.0" placeholderTextColor="#94A3B8"
                value={f.min_rating || ''} onChangeText={(v) => setF({ ...f, min_rating: v })} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.fLabel}>Min # ratings</Text>
              <TextInput style={s.fNum} keyboardType="numeric" placeholder="e.g. 10" placeholderTextColor="#94A3B8"
                value={f.min_ratings_count || ''} onChangeText={(v) => setF({ ...f, min_ratings_count: v.replace(/\D/g, '') })} />
            </View>
          </View>
          <View style={{ flexDirection: 'row', gap: 8, justifyContent: 'flex-end', marginTop: 6 }}>
            <TouchableOpacity onPress={() => setF({ org_types: [], is_free: null })} style={[s.fApplyBtn, { backgroundColor: '#F1F5F9' }]}>
              <Text style={[s.fApplyTxt, { color: '#475569' }]}>Clear</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => { setFiltersOpen(false); load(); }} style={s.fApplyBtn}>
              <Text style={s.fApplyTxt}>Apply</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {/* Category chips (per-tab) — wrap onto multiple rows on desktop so
          long labels like "Talent & Team" aren't clipped; keep horizontally
          scrollable on narrow (mobile) viewports. */}
      {width >= 640 ? (
        <View style={[s.catBar, s.catBarWrap]}>
          {[{ key: 'all', count: cards.length }, ...cats].map((c) => (
            <TouchableOpacity key={c.key} style={[s.catChip, cat === c.key && s.catChipOn]} onPress={() => setCat(c.key)}>
              <Text style={[s.catChipText, cat === c.key && s.catChipTextOn]}>{c.key === 'all' ? 'All' : c.key}</Text>
            </TouchableOpacity>
          ))}
        </View>
      ) : (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.catBar} contentContainerStyle={s.catBarInner}>
          {[{ key: 'all', count: cards.length }, ...cats].map((c) => (
            <TouchableOpacity key={c.key} style={[s.catChip, cat === c.key && s.catChipOn]} onPress={() => setCat(c.key)}>
              <Text style={[s.catChipText, cat === c.key && s.catChipTextOn]}>{c.key === 'all' ? 'All' : c.key}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {loading ? (
        <ActivityIndicator color="#4F46E5" style={{ marginTop: 40 }} />
      ) : (
        <ScrollView
          contentContainerStyle={s.grid}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        >
          {cards.length === 0 ? (
            <Text style={s.empty}>No templates yet. Check back soon.</Text>
          ) : (
            <>
              {tab === 'app' && (
                <>
                  <View style={s.sectionHead}>
                    <Ionicons name="search-circle" size={18} color="#4F46E5" />
                    <Text style={s.sectionTitle}>Decider Apps · Finders</Text>
                    <View style={s.countPill}><Text style={s.countText}>{apps.length}</Text></View>
                  </View>
                  <Text style={s.sectionHint}>Set what you want — the app auto-ranks the best matches for you.</Text>
                  {apps.length > 0
                    ? <View style={s.gridRow}>{apps.map(renderCard)}</View>
                    : <Text style={s.sectionEmpty}>No Decider Apps in this view yet.</Text>}
                </>
              )}

              {tab === 'template' && (
                <>
                  <View style={s.sectionHead}>
                    <Ionicons name="documents" size={18} color="#0D9488" />
                    <Text style={s.sectionTitle}>Decision Templates</Text>
                    <View style={[s.countPill, { backgroundColor: '#CCFBF1' }]}><Text style={[s.countText, { color: '#0D9488' }]}>{templates.length}</Text></View>
                  </View>
                  <Text style={s.sectionHint}>Clone a prefilled blueprint and assess the options yourself.</Text>
                  {templates.length > 0
                    ? <View style={s.gridRow}>{templates.map(renderCard)}</View>
                    : <Text style={s.sectionEmpty}>No decision templates in this view yet.</Text>}
                </>
              )}
            </>
          )}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  hero: { backgroundColor: '#FFF', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  heroRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  brandBadge: { width: 38, height: 38, borderRadius: 11, backgroundColor: '#4F46E5', alignItems: 'center', justifyContent: 'center' },
  heroTitle: { fontSize: 20, fontWeight: '900', color: '#0F172A' },
  heroTag: { fontSize: 12.5, color: '#64748B', marginTop: 1 },
  signIn: { backgroundColor: '#4F46E5', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10 },
  heroLinks: { flexDirection: 'row', gap: 6 },
  heroLink: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: 'rgba(255,255,255,0.14)', paddingHorizontal: 10, paddingVertical: 7, borderRadius: 999 },
  heroLinkText: { color: '#FFF', fontSize: 11.5, fontWeight: '800' },
  signInText: { color: '#FFF', fontWeight: '800', fontSize: 12.5 },
  search: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F1F5F9', borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10 },
  searchWrap: { paddingHorizontal: 12, paddingTop: 4, paddingBottom: 8, backgroundColor: '#F8FAFC' },
  searchInput: { flex: 1, fontSize: 14, color: '#0F172A', padding: 0 },
  catBar: { backgroundColor: '#FFF', minHeight: 56, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  catBarInner: { paddingHorizontal: 12, paddingVertical: 10, gap: 8, alignItems: 'center' },
  catBarWrap: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12, paddingVertical: 10, gap: 8, alignItems: 'center' },
  catChip: { paddingHorizontal: 13, paddingVertical: 7, borderRadius: 16, backgroundColor: '#F1F5F9', flexShrink: 0 },
  catChipOn: { backgroundColor: '#4F46E5' },
  catChipText: { fontSize: 12.5, color: '#475569', fontWeight: '700' },
  catChipTextOn: { color: '#FFF' },
  tabBar: { flexDirection: 'row', gap: 6, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: '#F8FAFC', alignItems: 'center' },
  tabBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: '#C7D2FE', flex: 1, justifyContent: 'center' },
  tabBtnOn: { backgroundColor: '#4F46E5', borderColor: '#4F46E5' },
  tabTxt: { color: '#4F46E5', fontSize: 12, fontWeight: '800' },
  tabTxtOn: { color: '#FFF' },
  filterBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 20, borderWidth: 1, borderColor: '#C7D2FE', backgroundColor: '#FFF' },
  filterBtnTxt: { fontSize: 12, fontWeight: '700', color: '#4F46E5' },
  filterPanel: { backgroundColor: '#FFF', padding: 12, borderBottomWidth: 1, borderBottomColor: '#E5E7EB', gap: 4 },
  fRow: { paddingVertical: 4 },
  fLabel: { fontSize: 10, fontWeight: '800', color: '#64748B', letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 4 },
  fChip: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12, backgroundColor: '#F1F5F9', flexShrink: 0 },
  fChipOn: { backgroundColor: '#4F46E5' },
  fChipTxt: { fontSize: 11, color: '#334155', fontWeight: '700' },
  fChipTxtOn: { color: '#FFF' },
  fNum: { flex: 1, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 6, fontSize: 12, color: '#0F172A' },
  fApplyBtn: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, backgroundColor: '#4F46E5' },
  fApplyTxt: { color: '#FFF', fontWeight: '800', fontSize: 12 },
  ratingRow: { flexDirection: 'row', alignItems: 'center', gap: 2, marginTop: 4, marginBottom: 2 },
  ratingTxt: { fontSize: 10, color: '#64748B', marginLeft: 4, fontWeight: '700' },
  grid: { padding: 14, maxWidth: 1100, width: '100%', alignSelf: 'center' },
  gridRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, justifyContent: 'flex-start' },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 7, marginBottom: 2 },
  sectionTitle: { fontSize: 16, fontWeight: '900', color: '#0F172A' },
  countPill: { backgroundColor: '#EEF2FF', minWidth: 22, paddingHorizontal: 7, paddingVertical: 1, borderRadius: 10, alignItems: 'center' },
  countText: { fontSize: 12, fontWeight: '800', color: '#4F46E5' },
  sectionHint: { fontSize: 12, color: '#64748B', marginBottom: 12, marginTop: 2 },
  sectionEmpty: { fontSize: 12.5, color: '#94A3B8', fontStyle: 'italic', paddingVertical: 10 },
  finderTag: { position: 'absolute', top: 8, left: 8, flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: '#4F46E5', paddingHorizontal: 7, paddingVertical: 3, borderRadius: 8 },
  finderTagText: { fontSize: 9.5, fontWeight: '900', color: '#FFF', letterSpacing: 0.4 },
  empty: { textAlign: 'center', color: '#94A3B8', marginTop: 40 },
  card: { backgroundColor: '#FFF', borderRadius: 16, padding: 12, borderWidth: 1, borderColor: '#E2E8F0' },
  cardCover: { height: 84, borderRadius: 12, alignItems: 'center', justifyContent: 'center', marginBottom: 10, position: 'relative' },
  priceTag: { position: 'absolute', top: 8, right: 8, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  priceTagText: { fontSize: 10.5, fontWeight: '800' },
  cardTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A' },
  cardSub: { fontSize: 12, color: '#64748B', marginTop: 3 },
  cardMeta: { flexDirection: 'row', gap: 12, marginTop: 10 },
  cardMetaText: { fontSize: 12, color: '#475569' },
  cardBadgeRow: { flexDirection: 'row', marginTop: 10 },
  catPill: { backgroundColor: '#EEF2FF', paddingHorizontal: 9, paddingVertical: 3, borderRadius: 8 },
  catPillText: { fontSize: 10.5, color: '#4F46E5', fontWeight: '700' },
});
