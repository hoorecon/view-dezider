/**
 * /admin/customer-segments — Customer Segment / Target-Group master.
 *
 * Admin defines the demography/psychography of TG customer profiles.
 * Each segment can:
 *   • Add custom factors (e.g., "Income Range")
 *   • AI-Research a factor's value via /admin/customer-segments/{id}/ai-research
 *   • Map 7-chakra tier subscriptions with multi-country / multi-currency pricing
 *   • Associate market-research module(s)
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, Modal, Switch, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';
import { showAlert } from '../../src/utils/alert';

interface Tier { key: string; order: number; label: string; aspiration: string; color: string; icon: string; monthly_price_inr: number }
interface Factor {
  key: string; label?: string; category: string; value?: string;
  ai_researchable?: boolean; is_custom?: boolean; last_researched_at?: string;
}
interface Pricing {
  tier_key: string; country_code: string; currency: string;
  monthly_price: number; annual_price: number; enabled: boolean;
}
interface Segment {
  segment_id: string; name: string; description?: string; chakra_tier_link?: string | null;
  factors: Factor[]; market_research_module_ids: string[];
  tier_pricings: Pricing[];
}

const COUNTRIES: Array<{code: string; currency: string; symbol: string; name: string}> = [
  { code: 'IN', currency: 'INR', symbol: '₹',  name: 'India' },
  { code: 'US', currency: 'USD', symbol: '$',  name: 'United States' },
  { code: 'GB', currency: 'GBP', symbol: '£',  name: 'United Kingdom' },
  { code: 'EU', currency: 'EUR', symbol: '€',  name: 'Eurozone' },
  { code: 'AE', currency: 'AED', symbol: 'AED',name: 'UAE' },
  { code: 'SG', currency: 'SGD', symbol: 'S$', name: 'Singapore' },
  { code: 'AU', currency: 'AUD', symbol: 'A$', name: 'Australia' },
  { code: 'CA', currency: 'CAD', symbol: 'C$', name: 'Canada' },
];

export default function CustomerSegmentsScreen() {
  const router = useRouter();
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [factorCatalog, setFactorCatalog] = useState<Factor[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Create modal
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newTier, setNewTier] = useState<string>('');

  // Custom factor modal
  const [factorModalSid, setFactorModalSid] = useState<string | null>(null);
  const [factorKey, setFactorKey] = useState('');
  const [factorLabel, setFactorLabel] = useState('');
  const [factorCategory, setFactorCategory] = useState<string>('custom');

  // Pricing modal
  const [pricingModalSid, setPricingModalSid] = useState<string | null>(null);
  const [editingPricings, setEditingPricings] = useState<Pricing[]>([]);

  const load = useCallback(async () => {
    try { setLoading(true);
      const [r1, r2] = await Promise.all([
        api.get('/admin/customer-segments'),
        api.get('/customer-segments/factors'),
      ]);
      setSegments(r1.data.segments || []);
      setTiers(r1.data.tiers || []);
      setFactorCatalog(r2.data.factors || []);
    } catch (e: any) { showAlert('Load failed', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggleExpand = (sid: string) => {
    const n = new Set(expanded);
    n.has(sid) ? n.delete(sid) : n.add(sid);
    setExpanded(n);
  };

  const createSegment = async () => {
    if (!newName.trim()) { showAlert('Required', 'Name required'); return; }
    try { setSaving('create');
      await api.post('/admin/customer-segments', {
        name: newName.trim(),
        description: newDesc.trim(),
        chakra_tier_link: newTier || null,
      });
      setShowCreate(false); setNewName(''); setNewDesc(''); setNewTier('');
      load();
    } catch (e: any) { showAlert('Create failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(null); }
  };

  const deleteSegment = async (sid: string) => {
    try { setSaving(sid);
      await api.delete(`/admin/customer-segments/${sid}`);
      load();
    } catch (e: any) { showAlert('Delete failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(null); }
  };

  const updateFactorValue = async (sid: string, factorKey: string, value: string) => {
    const seg = segments.find(s => s.segment_id === sid);
    if (!seg) return;
    const newFactors = seg.factors.map(f => f.key === factorKey ? { ...f, value } : f);
    // Optimistic UI
    setSegments(segments.map(s => s.segment_id === sid ? { ...s, factors: newFactors } : s));
    try {
      await api.put(`/admin/customer-segments/${sid}`, { factors: newFactors });
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
  };

  const aiResearch = async (sid: string, factorKey: string) => {
    const cellKey = `${sid}:${factorKey}`;
    try { setSaving(cellKey);
      const r = await api.post(`/admin/customer-segments/${sid}/ai-research`, { factor_key: factorKey });
      const seg = segments.find(s => s.segment_id === sid);
      if (seg) {
        const newFactors = seg.factors.map(f => f.key === factorKey ? { ...f, value: r.data.value, last_researched_at: new Date().toISOString() } : f);
        setSegments(segments.map(s => s.segment_id === sid ? { ...s, factors: newFactors } : s));
      }
    } catch (e: any) { showAlert('AI research failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(null); }
  };

  const addCustomFactor = async () => {
    if (!factorModalSid || !factorKey.trim()) return;
    try { setSaving('factor');
      await api.post(`/admin/customer-segments/${factorModalSid}/factor`, {
        key: factorKey.trim().toLowerCase().replace(/\s+/g, '_'),
        label: factorLabel.trim() || factorKey.trim(),
        category: factorCategory,
      });
      setFactorModalSid(null); setFactorKey(''); setFactorLabel(''); setFactorCategory('custom');
      load();
    } catch (e: any) { showAlert('Add failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(null); }
  };

  const removeCustomFactor = async (sid: string, key: string) => {
    try { setSaving(`${sid}:${key}:del`);
      await api.delete(`/admin/customer-segments/${sid}/factor/${key}`);
      load();
    } catch (e: any) { showAlert('Remove failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(null); }
  };

  const openPricing = (sid: string) => {
    const seg = segments.find(s => s.segment_id === sid);
    if (!seg) return;
    setPricingModalSid(sid);
    setEditingPricings([...(seg.tier_pricings || [])]);
  };

  const updatePricing = (idx: number, patch: Partial<Pricing>) => {
    const next = [...editingPricings];
    next[idx] = { ...next[idx], ...patch };
    setEditingPricings(next);
  };

  const addPricingRow = (tier_key: string, country_code: string) => {
    const country = COUNTRIES.find(c => c.code === country_code);
    if (!country) return;
    if (editingPricings.some(p => p.tier_key === tier_key && p.country_code === country_code)) {
      showAlert('Exists', 'Row already exists for this tier + country');
      return;
    }
    setEditingPricings([...editingPricings, {
      tier_key, country_code, currency: country.currency,
      monthly_price: 0, annual_price: 0, enabled: true,
    }]);
  };

  const removePricingRow = (idx: number) => {
    setEditingPricings(editingPricings.filter((_, i) => i !== idx));
  };

  const savePricing = async () => {
    if (!pricingModalSid) return;
    try { setSaving('pricing');
      await api.put(`/admin/customer-segments/${pricingModalSid}/pricing`, { tier_pricings: editingPricings });
      setPricingModalSid(null); setEditingPricings([]);
      load();
    } catch (e: any) { showAlert('Save failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(null); }
  };

  if (loading) return <SafeAreaView style={s.container}><View style={s.center}><ActivityIndicator color={COLORS.primary} /></View></SafeAreaView>;

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
        <View style={{ flex: 1, marginHorizontal: 12 }}>
          <Text style={s.title}>Customer Segments</Text>
          <Text style={s.subtitle}>TG master · demography · psychography · pricing</Text>
        </View>
        <TouchableOpacity onPress={() => setShowCreate(true)} testID="cs-add" style={s.addBtn}>
          <Ionicons name="add" size={18} color="#FFF" /><Text style={s.addBtnText}>New</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={{ padding: 12, paddingBottom: 80 }}>
        {segments.length === 0 ? (
          <View style={s.emptyCard}>
            <Ionicons name="people-outline" size={48} color={COLORS.textMuted} />
            <Text style={s.emptyTitle}>No segments yet</Text>
            <Text style={s.emptySub}>Tap "New" to create your first Target Group profile.</Text>
          </View>
        ) : segments.map(seg => {
          const isOpen = expanded.has(seg.segment_id);
          const tierObj = tiers.find(t => t.key === seg.chakra_tier_link);
          return (
            <View key={seg.segment_id} style={s.segmentCard}>
              <TouchableOpacity onPress={() => toggleExpand(seg.segment_id)} style={s.segmentHeader} testID={`cs-seg-${seg.segment_id}`}>
                <Ionicons name={isOpen ? 'chevron-down' : 'chevron-forward'} size={16} color={COLORS.textMuted} />
                <View style={{ flex: 1 }}>
                  <Text style={s.segmentName}>{seg.name}</Text>
                  {seg.description ? <Text style={s.segmentDesc} numberOfLines={2}>{seg.description}</Text> : null}
                  <View style={s.segmentMeta}>
                    {tierObj ? (
                      <View style={[s.tierChip, { backgroundColor: tierObj.color + '22', borderColor: tierObj.color }]}>
                        <Ionicons name={tierObj.icon as any} size={10} color={tierObj.color} />
                        <Text style={[s.tierChipText, { color: tierObj.color }]}>{tierObj.label}</Text>
                      </View>
                    ) : null}
                    <Text style={s.segmentMetaText}>{seg.factors.length} factors · {seg.tier_pricings.length} pricing rows</Text>
                  </View>
                </View>
                <TouchableOpacity onPress={() => deleteSegment(seg.segment_id)}>
                  <Ionicons name="trash-outline" size={18} color="#DC2626" />
                </TouchableOpacity>
              </TouchableOpacity>

              {isOpen && (
                <View style={s.segmentBody}>
                  {/* Factors table */}
                  <View style={s.sectionHeader}>
                    <Text style={s.sectionTitle}>Factors</Text>
                    <TouchableOpacity
                      onPress={() => { setFactorModalSid(seg.segment_id); setFactorKey(''); setFactorLabel(''); setFactorCategory('custom'); }}
                      style={s.smallBtn}
                      testID={`cs-add-factor-${seg.segment_id}`}
                    >
                      <Ionicons name="add" size={12} color={COLORS.primary} /><Text style={s.smallBtnText}>Custom factor</Text>
                    </TouchableOpacity>
                  </View>

                  {/* Group factors by category */}
                  {['demographic', 'psychographic', 'behavioural', 'firmographic', 'custom'].map(cat => {
                    const inCat = seg.factors.filter(f => (f.category || 'custom') === cat);
                    if (inCat.length === 0) return null;
                    return (
                      <View key={cat} style={s.catBlock}>
                        <Text style={s.catTitle}>{cat.toUpperCase()}</Text>
                        {inCat.map(f => {
                          const cellKey = `${seg.segment_id}:${f.key}`;
                          return (
                            <View key={f.key} style={s.factorRow}>
                              <View style={{ flex: 1.4 }}>
                                <Text style={s.factorLabel}>{f.label || f.key}</Text>
                                <Text style={s.factorKey}>{f.key}</Text>
                              </View>
                              <TextInput
                                value={f.value || ''}
                                onChangeText={(v) => {
                                  setSegments(segments.map(s2 => s2.segment_id === seg.segment_id
                                    ? { ...s2, factors: s2.factors.map(ff => ff.key === f.key ? { ...ff, value: v } : ff) }
                                    : s2));
                                }}
                                onEndEditing={(e) => updateFactorValue(seg.segment_id, f.key, e.nativeEvent.text)}
                                placeholder="Enter value…"
                                placeholderTextColor={COLORS.textMuted}
                                style={s.factorInput}
                                testID={`cs-fv-${seg.segment_id}-${f.key}`}
                              />
                              <TouchableOpacity
                                onPress={() => aiResearch(seg.segment_id, f.key)}
                                disabled={saving === cellKey}
                                style={s.aiBtn}
                                testID={`cs-ai-${seg.segment_id}-${f.key}`}
                              >
                                {saving === cellKey ? <ActivityIndicator size="small" color="#7C3AED" /> :
                                  <><Ionicons name="sparkles" size={11} color="#7C3AED" /><Text style={s.aiBtnText}>AI</Text></>
                                }
                              </TouchableOpacity>
                              {f.is_custom ? (
                                <TouchableOpacity onPress={() => removeCustomFactor(seg.segment_id, f.key)} style={{ marginLeft: 4 }}>
                                  <Ionicons name="close-circle" size={16} color="#DC2626" />
                                </TouchableOpacity>
                              ) : null}
                            </View>
                          );
                        })}
                      </View>
                    );
                  })}

                  {/* Pricing button */}
                  <View style={s.actionsRow}>
                    <TouchableOpacity onPress={() => openPricing(seg.segment_id)} style={s.pricingBtn} testID={`cs-pricing-${seg.segment_id}`}>
                      <Ionicons name="pricetag" size={14} color="#FFF" />
                      <Text style={s.pricingBtnText}>Tier pricing ({seg.tier_pricings.length})</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => router.push('/admin/tier-matrix')} style={s.linkBtn}>
                      <Ionicons name="grid" size={12} color={COLORS.primary} />
                      <Text style={s.linkBtnText}>Open Tier Matrix (features)</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              )}
            </View>
          );
        })}
      </ScrollView>

      {/* Create modal */}
      <Modal visible={showCreate} transparent animationType="slide" onRequestClose={() => setShowCreate(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.sheetHead}>
              <Text style={s.sheetTitle}>New Customer Segment</Text>
              <TouchableOpacity onPress={() => setShowCreate(false)}><Ionicons name="close" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
            </View>
            <Text style={s.fieldLabel}>Name *</Text>
            <TextInput value={newName} onChangeText={setNewName} placeholder="e.g., Tech-savvy Millennial Founder" placeholderTextColor={COLORS.textMuted} style={s.input} testID="cs-new-name" />
            <Text style={s.fieldLabel}>Description</Text>
            <TextInput value={newDesc} onChangeText={setNewDesc} placeholder="Short profile summary" placeholderTextColor={COLORS.textMuted} style={[s.input, { height: 70 }]} multiline />
            <Text style={s.fieldLabel}>Recommended Chakra Tier (optional)</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingVertical: 6 }}>
              {tiers.map(t => (
                <TouchableOpacity
                  key={t.key}
                  onPress={() => setNewTier(newTier === t.key ? '' : t.key)}
                  style={[s.tierPick, { borderColor: t.color }, newTier === t.key && { backgroundColor: t.color + '22' }]}
                >
                  <Ionicons name={t.icon as any} size={11} color={t.color} />
                  <Text style={[s.tierPickText, { color: t.color }]}>{t.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <TouchableOpacity onPress={createSegment} disabled={saving === 'create'} style={s.primaryBtn} testID="cs-new-save">
              {saving === 'create' ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryBtnText}>Create Segment</Text>}
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Custom factor modal */}
      <Modal visible={!!factorModalSid} transparent animationType="slide" onRequestClose={() => setFactorModalSid(null)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.sheetHead}>
              <Text style={s.sheetTitle}>Add custom factor</Text>
              <TouchableOpacity onPress={() => setFactorModalSid(null)}><Ionicons name="close" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
            </View>
            <Text style={s.fieldLabel}>Factor name *</Text>
            <TextInput value={factorKey} onChangeText={setFactorKey} placeholder="e.g., income_range or Pet Owner" placeholderTextColor={COLORS.textMuted} style={s.input} />
            <Text style={s.fieldLabel}>Display label</Text>
            <TextInput value={factorLabel} onChangeText={setFactorLabel} placeholder="e.g., Income Range" placeholderTextColor={COLORS.textMuted} style={s.input} />
            <Text style={s.fieldLabel}>Category</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
              {['demographic','psychographic','behavioural','firmographic','custom'].map(c => (
                <TouchableOpacity key={c} onPress={() => setFactorCategory(c)}
                  style={[s.catChip, factorCategory === c && { backgroundColor: COLORS.primary, borderColor: COLORS.primary }]}>
                  <Text style={[s.catChipText, factorCategory === c && { color: '#FFF' }]}>{c}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TouchableOpacity onPress={addCustomFactor} disabled={saving === 'factor'} style={s.primaryBtn}>
              {saving === 'factor' ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryBtnText}>Add Factor</Text>}
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Pricing modal */}
      <Modal visible={!!pricingModalSid} transparent animationType="slide" onRequestClose={() => setPricingModalSid(null)}>
        <View style={s.overlay}>
          <View style={[s.sheet, { maxHeight: '90%' }]}>
            <View style={s.sheetHead}>
              <Text style={s.sheetTitle}>Tier Pricing · multi-currency</Text>
              <TouchableOpacity onPress={() => setPricingModalSid(null)}><Ionicons name="close" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
            </View>
            <Text style={s.helpText}>Set monthly + annual prices per tier per country. Disable to hide a tier in that geography.</Text>
            <ScrollView style={{ maxHeight: 460 }}>
              {tiers.map(t => {
                const rows = editingPricings
                  .map((p, idx) => ({ p, idx }))
                  .filter(({ p }) => p.tier_key === t.key);
                return (
                  <View key={t.key} style={s.tierBlock}>
                    <View style={[s.tierBlockHead, { backgroundColor: t.color + '15', borderLeftColor: t.color }]}>
                      <Ionicons name={t.icon as any} size={14} color={t.color} />
                      <Text style={[s.tierBlockLabel, { color: t.color }]}>{t.label}</Text>
                      <Text style={s.tierBlockSub}>{t.aspiration}</Text>
                    </View>
                    {rows.map(({ p, idx }) => (
                      <View key={idx} style={s.priceRow}>
                        <View style={{ flex: 1.0 }}>
                          <Text style={s.priceCountry}>{p.country_code} · {p.currency}</Text>
                        </View>
                        <TextInput
                          value={String(p.monthly_price)}
                          onChangeText={(v) => updatePricing(idx, { monthly_price: parseFloat(v) || 0 })}
                          keyboardType="numeric"
                          placeholder="Monthly"
                          placeholderTextColor={COLORS.textMuted}
                          style={s.priceInput}
                        />
                        <TextInput
                          value={String(p.annual_price)}
                          onChangeText={(v) => updatePricing(idx, { annual_price: parseFloat(v) || 0 })}
                          keyboardType="numeric"
                          placeholder="Annual"
                          placeholderTextColor={COLORS.textMuted}
                          style={s.priceInput}
                        />
                        <Switch value={p.enabled} onValueChange={(v) => updatePricing(idx, { enabled: v })}
                          trackColor={{ true: t.color, false: '#D1D5DB' }} />
                        <TouchableOpacity onPress={() => removePricingRow(idx)} style={{ marginLeft: 4 }}>
                          <Ionicons name="close-circle" size={16} color="#DC2626" />
                        </TouchableOpacity>
                      </View>
                    ))}
                    {/* Add country picker */}
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingTop: 4, paddingBottom: 8 }}>
                      {COUNTRIES.filter(c => !rows.some(({p}) => p.country_code === c.code)).map(c => (
                        <TouchableOpacity key={c.code} onPress={() => addPricingRow(t.key, c.code)} style={s.addCountryChip}>
                          <Ionicons name="add" size={10} color={COLORS.primary} />
                          <Text style={s.addCountryText}>{c.code} · {c.symbol}</Text>
                        </TouchableOpacity>
                      ))}
                    </ScrollView>
                  </View>
                );
              })}
            </ScrollView>
            <TouchableOpacity onPress={savePricing} disabled={saving === 'pricing'} style={s.primaryBtn} testID="cs-pricing-save">
              {saving === 'pricing' ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryBtnText}>Save Pricing</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  title: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8 },
  addBtnText: { color: '#FFF', fontSize: 12, fontWeight: '700' },

  emptyCard: { alignItems: 'center', padding: 30, marginTop: 40 },
  emptyTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 10 },
  emptySub: { fontSize: 12, color: COLORS.textMuted, marginTop: 4, textAlign: 'center' },

  segmentCard: { backgroundColor: COLORS.white, borderRadius: 10, marginBottom: 10, overflow: 'hidden', borderWidth: 1, borderColor: COLORS.divider },
  segmentHeader: { flexDirection: 'row', alignItems: 'center', padding: 12, gap: 10 },
  segmentName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  segmentDesc: { fontSize: 11, color: COLORS.textSecondary, marginTop: 2 },
  segmentMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' },
  segmentMetaText: { fontSize: 10, color: COLORS.textMuted },
  tierChip: { flexDirection: 'row', alignItems: 'center', gap: 3, borderWidth: 1, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  tierChipText: { fontSize: 9, fontWeight: '700' },

  segmentBody: { borderTopWidth: 1, borderTopColor: COLORS.divider, padding: 12, backgroundColor: '#FAFAFA' },
  sectionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  sectionTitle: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary, textTransform: 'uppercase', letterSpacing: 0.5 },
  smallBtn: { flexDirection: 'row', alignItems: 'center', gap: 3, borderWidth: 1, borderColor: COLORS.primary, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  smallBtnText: { fontSize: 10, color: COLORS.primary, fontWeight: '700' },

  catBlock: { marginBottom: 10 },
  catTitle: { fontSize: 9, fontWeight: '700', color: COLORS.textMuted, letterSpacing: 0.5, marginBottom: 4 },
  factorRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 4 },
  factorLabel: { fontSize: 11, fontWeight: '600', color: COLORS.textPrimary },
  factorKey: { fontSize: 9, color: COLORS.textMuted, marginTop: 1 },
  factorInput: { flex: 1.6, backgroundColor: '#FFF', borderWidth: 1, borderColor: COLORS.divider, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 6, fontSize: 11, color: COLORS.textPrimary },
  aiBtn: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 6, borderRadius: 6, backgroundColor: '#F5F3FF', borderWidth: 1, borderColor: '#7C3AED' },
  aiBtnText: { fontSize: 10, fontWeight: '700', color: '#7C3AED' },

  actionsRow: { flexDirection: 'row', gap: 8, marginTop: 8 },
  pricingBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8 },
  pricingBtnText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
  linkBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 8, borderWidth: 1, borderColor: COLORS.primary, borderRadius: 8 },
  linkBtnText: { fontSize: 10, color: COLORS.primary, fontWeight: '700' },

  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '85%' },
  sheetHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  fieldLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary, marginTop: 12, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 },
  helpText: { fontSize: 11, color: COLORS.textMuted, marginBottom: 8, lineHeight: 16 },
  input: { backgroundColor: '#F9FAFB', borderWidth: 1, borderColor: COLORS.divider, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary },
  primaryBtn: { backgroundColor: COLORS.primary, borderRadius: 8, paddingVertical: 13, marginTop: 14, alignItems: 'center' },
  primaryBtnText: { color: '#FFF', fontSize: 13, fontWeight: '700' },

  tierPick: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, marginRight: 6 },
  tierPickText: { fontSize: 11, fontWeight: '700' },
  catChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.divider, backgroundColor: '#FFF' },
  catChipText: { fontSize: 11, color: COLORS.textPrimary },

  tierBlock: { marginBottom: 14 },
  tierBlockHead: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 8, borderLeftWidth: 3, borderRadius: 4 },
  tierBlockLabel: { fontSize: 12, fontWeight: '700' },
  tierBlockSub: { fontSize: 10, color: COLORS.textMuted, marginLeft: 4 },
  priceRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 6, paddingHorizontal: 4, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  priceCountry: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary },
  priceInput: { flex: 1, backgroundColor: '#F9FAFB', borderWidth: 1, borderColor: COLORS.divider, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 5, fontSize: 11, color: COLORS.textPrimary, textAlign: 'right' },
  addCountryChip: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, backgroundColor: '#EEF2FF', marginRight: 5 },
  addCountryText: { fontSize: 10, color: COLORS.primary, fontWeight: '700' },
});
