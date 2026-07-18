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
};

export default function DeciderStoreHome() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [cards, setCards] = useState<Card[]>([]);
  const [cats, setCats] = useState<{ key: string; count: number }[]>([]);
  const [cat, setCat] = useState<string>('all');
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const numCols = width >= 900 ? 3 : width >= 600 ? 2 : 1;

  const load = useCallback(async () => {
    try {
      const params: any = {};
      if (cat !== 'all') params.category = cat;
      if (q.trim()) params.q = q.trim();
      const [r, m] = await Promise.all([
        api.get('/decider-store', { params }),
        api.get('/decider-store/meta'),
      ]);
      setCards(r.data.templates || []);
      setCats(m.data.categories || []);
    } catch {
      /* transient — leave existing */
    } finally { setLoading(false); setRefreshing(false); }
  }, [cat, q]);

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
        <View style={s.cardBadgeRow}>
          <View style={s.catPill}><Text style={s.catPillText}>{c.category}</Text></View>
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
        </View>
        <View style={s.search}>
          <Ionicons name="search" size={16} color="#94A3B8" />
          <TextInput
            style={s.searchInput}
            value={q}
            onChangeText={setQ}
            onSubmitEditing={load}
            placeholder="Search templates…"
            placeholderTextColor="#94A3B8"
            returnKeyType="search"
          />
          {!!q && <TouchableOpacity onPress={() => { setQ(''); }}><Ionicons name="close-circle" size={16} color="#CBD5E1" /></TouchableOpacity>}
        </View>
      </View>

      {/* Category chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.catBar} contentContainerStyle={s.catBarInner}>
        {[{ key: 'all', count: cards.length }, ...cats].map((c) => (
          <TouchableOpacity key={c.key} style={[s.catChip, cat === c.key && s.catChipOn]} onPress={() => setCat(c.key)}>
            <Text style={[s.catChipText, cat === c.key && s.catChipTextOn]}>{c.key === 'all' ? 'All' : c.key}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

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
              {apps.length > 0 && (
                <>
                  <View style={s.sectionHead}>
                    <Ionicons name="search-circle" size={18} color="#4F46E5" />
                    <Text style={s.sectionTitle}>Decider Apps · Finders</Text>
                  </View>
                  <Text style={s.sectionHint}>Set what you want — the app auto-ranks the best matches for you.</Text>
                  <View style={s.gridRow}>{apps.map(renderCard)}</View>
                </>
              )}
              {templates.length > 0 && (
                <>
                  <View style={[s.sectionHead, apps.length > 0 && { marginTop: 22 }]}>
                    <Ionicons name="documents" size={18} color="#0D9488" />
                    <Text style={s.sectionTitle}>Decision Templates</Text>
                  </View>
                  <Text style={s.sectionHint}>Clone a prefilled blueprint and assess the options yourself.</Text>
                  <View style={s.gridRow}>{templates.map(renderCard)}</View>
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
  signInText: { color: '#FFF', fontWeight: '800', fontSize: 12.5 },
  search: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F1F5F9', borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10, marginTop: 12 },
  searchInput: { flex: 1, fontSize: 14, color: '#0F172A', padding: 0 },
  catBar: { backgroundColor: '#FFF', maxHeight: 50, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  catBarInner: { paddingHorizontal: 12, paddingVertical: 8, gap: 8 },
  catChip: { paddingHorizontal: 13, paddingVertical: 7, borderRadius: 16, backgroundColor: '#F1F5F9' },
  catChipOn: { backgroundColor: '#4F46E5' },
  catChipText: { fontSize: 12.5, color: '#475569', fontWeight: '700' },
  catChipTextOn: { color: '#FFF' },
  grid: { padding: 14, maxWidth: 1100, width: '100%', alignSelf: 'center' },
  gridRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, justifyContent: 'flex-start' },
  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 7, marginBottom: 2 },
  sectionTitle: { fontSize: 16, fontWeight: '900', color: '#0F172A' },
  sectionHint: { fontSize: 12, color: '#64748B', marginBottom: 12, marginTop: 2 },
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
