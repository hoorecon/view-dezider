import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator,
  StyleSheet, Platform, RefreshControl, FlatList, Modal, Alert,
} from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack } from '../../src/utils/navigation';

const COLORS = {
  bg: '#0F172A', surface: '#1E293B', surfaceLight: '#334155',
  primary: '#3B82F6', secondary: '#8B5CF6', accent: '#10B981',
  text: '#F8FAFC', textSecondary: '#94A3B8', textMuted: '#64748B',
  border: '#334155', danger: '#EF4444', warning: '#F59E0B',
  gold: '#F59E0B',
};

const TYPE_ICONS: Record<string, string> = {
  PRODUCT: 'cube', SERVICE: 'construct', EVENT: 'calendar',
  PROJECT: 'rocket', PERSON_CONTACT: 'person',
};
const TYPE_COLORS: Record<string, string> = {
  PRODUCT: '#3B82F6', SERVICE: '#10B981', EVENT: '#F59E0B',
  PROJECT: '#8B5CF6', PERSON_CONTACT: '#EC4899',
};

export default function SolutionsStoreScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams();
  const { session } = useAuthStore();

  const [solutions, setSolutions] = useState<any[]>([]);
  const [lifeAreas, setLifeAreas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Filters
  const [selectedArea, setSelectedArea] = useState<string | null>(params.life_area_id as string || null);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [showFilterModal, setShowFilterModal] = useState(false);

  // Location & Language
  const [selectedCountry, setSelectedCountry] = useState('IN');
  const [selectedLanguage, setSelectedLanguage] = useState('en');
  const [countries, setCountries] = useState<any[]>([]);
  const [languages, setLanguages] = useState<any[]>([]);
  const [showLocationModal, setShowLocationModal] = useState(false);

  useEffect(() => {
    // Load config and user prefs
    (async () => {
      try {
        const [cRes, lRes, pRes] = await Promise.all([
          api.get('/solutions-store/config/countries'),
          api.get('/solutions-store/config/languages'),
          api.get('/solutions-store/user-preferences', { headers: { Authorization: `Bearer ${session}` } }).catch(() => null),
        ]);
        setCountries(cRes.data?.countries || []);
        setLanguages(lRes.data?.languages || []);
        if (pRes?.data) {
          setSelectedCountry(pRes.data.country || 'IN');
          setSelectedLanguage(pRes.data.language || 'en');
        }
      } catch (e) {
        console.error('Config load error:', e);
      }
    })();
  }, [session]);

  const saveLocationPrefs = async (country: string, lang: string) => {
    setSelectedCountry(country);
    setSelectedLanguage(lang);
    try {
      await api.put('/solutions-store/user-preferences',
        { country, language: lang },
        { headers: { Authorization: `Bearer ${session}` } }
      );
    } catch (e) { console.error('Save prefs error:', e); }
  };

  const fetchData = useCallback(async () => {
    try {
      const [areasRes, solsRes] = await Promise.all([
        api.get('/hos/life-areas'),
        api.get('/solutions-store/solutions', {
          params: {
            ...(selectedArea ? { life_area_id: selectedArea } : {}),
            ...(selectedType ? { type: selectedType } : {}),
            country: selectedCountry,
            language: selectedLanguage,
          },
          headers: { Authorization: `Bearer ${session}` },
        }),
      ]);
      setLifeAreas(areasRes.data);
      setSolutions(solsRes.data);
    } catch (e) {
      console.error('Fetch error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [session, selectedArea, selectedType, selectedCountry, selectedLanguage]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return fetchData();
    setLoading(true);
    try {
      const res = await api.get('/solutions-store/search', {
        params: { q: searchQuery },
        headers: { Authorization: `Bearer ${session}` },
      });
      setSolutions(res.data.results || []);
    } catch (e) {
      console.error('Search error:', e);
    } finally {
      setLoading(false);
    }
  };

  const renderStarRating = (rating: number | null) => {
    if (!rating) return <Text style={styles.noRating}>No reviews yet</Text>;
    const stars = [];
    for (let i = 1; i <= 5; i++) {
      const filled = rating / 2 >= i;
      const half = rating / 2 >= i - 0.5 && !filled;
      stars.push(
        <Ionicons key={i} name={filled ? 'star' : half ? 'star-half' : 'star-outline'}
          size={14} color={COLORS.gold} />
      );
    }
    return (
      <View style={styles.starRow}>
        {stars}
        <Text style={styles.ratingText}>{rating}/10</Text>
        </View>
    );
  };

  const renderSolutionCard = ({ item }: { item: any }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => router.push({ pathname: '/tools/solution-detail', params: { solution_id: item.solution_id } })}
      activeOpacity={0.7}
    >
      <View style={styles.cardHeader}>
        <View style={[styles.typeBadge, { backgroundColor: TYPE_COLORS[item.type] + '20' }]}>
          <Ionicons name={TYPE_ICONS[item.type] as any || 'ellipse'} size={14} color={TYPE_COLORS[item.type]} />
          <Text style={[styles.typeText, { color: TYPE_COLORS[item.type] }]}>{item.type.replace('_', ' ')}</Text>
        </View>
        {item.is_locked ? (
          <View style={styles.lockBadge}>
            <Ionicons name="lock-closed" size={11} color="#B45309" />
            <Text style={styles.lockText} numberOfLines={1}>
              {item.unlock_skus?.[0]?.name || 'Locked'}
            </Text>
          </View>
        ) : item.is_authorized ? (
          <View style={styles.authorizedBadge}>
            <Ionicons name="shield-checkmark" size={12} color={COLORS.accent} />
            <Text style={styles.authorizedText}>Verified</Text>
          </View>
        ) : null}
      </View>

      <Text style={styles.cardTitle} numberOfLines={2}>{item.name}</Text>
      <Text style={styles.cardDesc} numberOfLines={2}>{item.description}</Text>

      <View style={styles.cardMeta}>
        {item.provider ? (
          <View style={styles.metaItem}>
            <Ionicons name="business-outline" size={12} color={COLORS.textMuted} />
            <Text style={styles.metaText} numberOfLines={1}>{item.provider}</Text>
          </View>
        ) : null}
        {item.price_range ? (
          <View style={styles.metaItem}>
            <Ionicons name="pricetag-outline" size={12} color={COLORS.accent} />
            <Text style={[styles.metaText, { color: COLORS.accent }]}>{item.price_range}</Text>
          </View>
        ) : null}
      </View>

      <View style={styles.cardFooter}>
        {renderStarRating(item.avg_rating)}
        <Text style={styles.reviewCount}>
          {item.review_count || 0} review{item.review_count !== 1 ? 's' : ''}
        </Text>
      </View>

      {item.quantitative_factors?.length > 0 && (
        <View style={styles.factorChips}>
          {item.quantitative_factors.slice(0, 3).map((f: any, i: number) => (
            <View key={i} style={styles.factorChip}>
              <Text style={styles.factorChipText}>{f.factor_name}: {f.value} {f.unit}</Text>
            </View>
          ))}
          {item.quantitative_factors.length > 3 && (
            <Text style={styles.moreFactors}>+{item.quantitative_factors.length - 3} more</Text>
          )}
        </View>
      )}
    </TouchableOpacity>
  );

  const renderTypeFilter = () => (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.typeFilterRow}>
      <TouchableOpacity
        style={[styles.typeFilterBtn, !selectedType && styles.typeFilterActive]}
        onPress={() => setSelectedType(null)}
      >
        <Text style={[styles.typeFilterText, !selectedType && styles.typeFilterTextActive]}>All</Text>
      </TouchableOpacity>
      {['PRODUCT', 'SERVICE', 'EVENT', 'PROJECT', 'PERSON_CONTACT'].map(t => (
        <TouchableOpacity
          key={t}
          style={[styles.typeFilterBtn, selectedType === t && { backgroundColor: TYPE_COLORS[t] + '30', borderColor: TYPE_COLORS[t] }]}
          onPress={() => setSelectedType(selectedType === t ? null : t)}
        >
          <Ionicons name={TYPE_ICONS[t] as any} size={14} color={selectedType === t ? TYPE_COLORS[t] : COLORS.textMuted} />
          <Text style={[styles.typeFilterText, selectedType === t && { color: TYPE_COLORS[t] }]}>
            {t === 'PERSON_CONTACT' ? 'People' : t.charAt(0) + t.slice(1).toLowerCase() + 's'}
          </Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );

  if (loading && !refreshing) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Solutions Store</Text>
          <Text style={styles.headerSubtitle}>{solutions.length} solutions available</Text>
        </View>
        <TouchableOpacity
          onPress={() => router.push('/tools/add-solution')}
          style={styles.addBtn}
        >
          <Ionicons name="add" size={20} color={COLORS.text} />
        </TouchableOpacity>
      </View>

      {/* Location & Language Selector */}
      <TouchableOpacity
        style={styles.locationBar}
        onPress={() => setShowLocationModal(true)}
      >
        <Ionicons name="location" size={14} color={COLORS.primary} />
        <Text style={styles.locationText}>
          {countries.find(c => c.code === selectedCountry)?.flag || '🌍'}{' '}
          {countries.find(c => c.code === selectedCountry)?.name || selectedCountry}
        </Text>
        <View style={styles.locationDivider} />
        <Ionicons name="language" size={14} color={COLORS.secondary} />
        <Text style={styles.locationText}>
          {languages.find(l => l.code === selectedLanguage)?.name || selectedLanguage}
        </Text>
        <Ionicons name="chevron-down" size={14} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Search */}
      <View style={styles.searchRow}>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={18} color={COLORS.textMuted} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search solutions..."
            placeholderTextColor={COLORS.textMuted}
            value={searchQuery}
            onChangeText={setSearchQuery}
            onSubmitEditing={handleSearch}
            returnKeyType="search"
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => { setSearchQuery(''); fetchData(); }}>
              <Ionicons name="close-circle" size={18} color={COLORS.textMuted} />
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Life Area filter */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.areaFilterRow}>
        <TouchableOpacity
          style={[styles.areaChip, !selectedArea && styles.areaChipActive]}
          onPress={() => setSelectedArea(null)}
        >
          <Text style={[styles.areaChipText, !selectedArea && styles.areaChipTextActive]}>All Areas</Text>
        </TouchableOpacity>
        {lifeAreas.map((la: any) => (
          <TouchableOpacity
            key={la.id}
            style={[styles.areaChip, selectedArea === la.id && { backgroundColor: la.color + '30', borderColor: la.color }]}
            onPress={() => setSelectedArea(selectedArea === la.id ? null : la.id)}
          >
            <Ionicons name={(la.icon || 'ellipse') as any} size={12} color={selectedArea === la.id ? la.color : COLORS.textMuted} />
            <Text style={[styles.areaChipText, selectedArea === la.id && { color: la.color }]} numberOfLines={1}>
              {la.name.length > 15 ? la.name.substring(0, 15) + '...' : la.name}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Type filter */}
      {renderTypeFilter()}

      {/* Solutions list */}
      <FlatList
        data={solutions}
        keyExtractor={(item) => item.solution_id}
        renderItem={renderSolutionCard}
        contentContainerStyle={styles.listContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} tintColor={COLORS.primary} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="storefront-outline" size={48} color={COLORS.textMuted} />
            <Text style={styles.emptyText}>No solutions found</Text>
            <Text style={styles.emptySubtext}>Try changing filters or add a new solution</Text>
          </View>
        }
      />

      {/* Location/Language Selector Modal */}
      <Modal visible={showLocationModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Location & Language</Text>
              <TouchableOpacity onPress={() => setShowLocationModal(false)}>
                <Ionicons name="close" size={24} color={COLORS.text} />
              </TouchableOpacity>
            </View>

            <Text style={styles.modalSection}>Country</Text>
            <ScrollView style={{ maxHeight: 200 }}>
              {countries.map(c => (
                <TouchableOpacity key={c.code}
                  style={[styles.locationOption, selectedCountry === c.code && styles.locationOptionActive]}
                  onPress={() => { saveLocationPrefs(c.code, selectedLanguage); }}
                >
                  <Text style={styles.locationFlag}>{c.flag}</Text>
                  <Text style={[styles.locationOptionText, selectedCountry === c.code && { color: COLORS.primary, fontWeight: '700' }]}>
                    {c.name}
                  </Text>
                  {selectedCountry === c.code && <Ionicons name="checkmark-circle" size={18} color={COLORS.primary} />}
                </TouchableOpacity>
              ))}
            </ScrollView>

            <Text style={[styles.modalSection, { marginTop: 16 }]}>Language</Text>
            <ScrollView style={{ maxHeight: 200 }}>
              {languages.map(l => (
                <TouchableOpacity key={l.code}
                  style={[styles.locationOption, selectedLanguage === l.code && styles.locationOptionActive]}
                  onPress={() => { saveLocationPrefs(selectedCountry, l.code); }}
                >
                  <Ionicons name="language" size={16} color={selectedLanguage === l.code ? COLORS.secondary : COLORS.textMuted} />
                  <Text style={[styles.locationOptionText, selectedLanguage === l.code && { color: COLORS.secondary, fontWeight: '700' }]}>
                    {l.name}
                  </Text>
                  {selectedLanguage === l.code && <Ionicons name="checkmark-circle" size={18} color={COLORS.secondary} />}
                </TouchableOpacity>
              ))}
            </ScrollView>

            <TouchableOpacity style={styles.applyBtn}
              onPress={() => { setShowLocationModal(false); fetchData(); }}
            >
              <Text style={styles.applyBtnText}>Apply Filters</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12 },
  backBtn: { padding: 8, marginRight: 8 },
  headerTitle: { fontSize: 20, fontWeight: '700', color: COLORS.text },
  headerSubtitle: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  addBtn: { backgroundColor: COLORS.primary, borderRadius: 20, width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  searchRow: { paddingHorizontal: 16, marginBottom: 8 },
  searchBox: { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.surface, borderRadius: 12, paddingHorizontal: 12, height: 44, borderWidth: 1, borderColor: COLORS.border },
  searchInput: { flex: 1, color: COLORS.text, fontSize: 14, marginLeft: 8 },
  areaFilterRow: { paddingLeft: 16, marginBottom: 6, maxHeight: 36 },
  areaChip: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, borderWidth: 1, borderColor: COLORS.border, marginRight: 8, backgroundColor: COLORS.surface },
  areaChipActive: { backgroundColor: COLORS.primary + '30', borderColor: COLORS.primary },
  areaChipText: { fontSize: 12, color: COLORS.textMuted, marginLeft: 4 },
  areaChipTextActive: { color: COLORS.primary },
  typeFilterRow: { paddingLeft: 16, marginBottom: 8, maxHeight: 36 },
  typeFilterBtn: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, borderWidth: 1, borderColor: COLORS.border, marginRight: 8, backgroundColor: COLORS.surface, gap: 4 },
  typeFilterActive: { backgroundColor: COLORS.primary + '30', borderColor: COLORS.primary },
  typeFilterText: { fontSize: 12, color: COLORS.textMuted },
  typeFilterTextActive: { color: COLORS.primary },
  listContent: { paddingHorizontal: 16, paddingBottom: 100 },
  card: { backgroundColor: COLORS.surface, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  typeBadge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12, gap: 4 },
  typeText: { fontSize: 11, fontWeight: '600', textTransform: 'uppercase' },
  authorizedBadge: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  authorizedText: { fontSize: 11, color: COLORS.accent, fontWeight: '500' },
  lockBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#FEF3C7', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, maxWidth: 150 },
  lockText: { fontSize: 11, color: '#B45309', fontWeight: '700' },
  cardTitle: { fontSize: 16, fontWeight: '700', color: COLORS.text, marginBottom: 4 },
  cardDesc: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18, marginBottom: 8 },
  cardMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 8 },
  metaItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  metaText: { fontSize: 12, color: COLORS.textMuted },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  starRow: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  ratingText: { fontSize: 12, color: COLORS.gold, marginLeft: 4, fontWeight: '600' },
  noRating: { fontSize: 12, color: COLORS.textMuted, fontStyle: 'italic' },
  reviewCount: { fontSize: 11, color: COLORS.textMuted },
  factorChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: COLORS.border },
  factorChip: { backgroundColor: COLORS.bg, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  factorChipText: { fontSize: 11, color: COLORS.textSecondary },
  moreFactors: { fontSize: 11, color: COLORS.primary, alignSelf: 'center' },
  empty: { alignItems: 'center', paddingTop: 60 },
  emptyText: { fontSize: 16, color: COLORS.textSecondary, marginTop: 12 },
  emptySubtext: { fontSize: 13, color: COLORS.textMuted, marginTop: 4 },
  // Location bar
  locationBar: {
    flexDirection: 'row', alignItems: 'center', marginHorizontal: 16, marginBottom: 8,
    backgroundColor: COLORS.surface, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8,
    borderWidth: 1, borderColor: COLORS.border, gap: 6,
  },
  locationText: { fontSize: 12, color: COLORS.textSecondary },
  locationDivider: { width: 1, height: 14, backgroundColor: COLORS.border, marginHorizontal: 4 },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  modalContent: {
    backgroundColor: COLORS.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24,
    padding: 20, maxHeight: '75%',
  },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  modalSection: { fontSize: 14, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 8 },
  locationOption: {
    flexDirection: 'row', alignItems: 'center', paddingVertical: 10, paddingHorizontal: 12,
    borderRadius: 10, gap: 10, marginBottom: 4,
  },
  locationOptionActive: { backgroundColor: COLORS.primary + '15' },
  locationFlag: { fontSize: 18 },
  locationOptionText: { flex: 1, fontSize: 14, color: COLORS.text },
  applyBtn: {
    backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 14,
    alignItems: 'center', marginTop: 16,
  },
  applyBtnText: { color: '#FFF', fontSize: 16, fontWeight: '700' },
});
