import React, { useState, useEffect, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, ActivityIndicator,
  StyleSheet, Alert, Modal, FlatList, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';

const COLORS = {
  bg: '#0F172A', surface: '#1E293B', surfaceLight: '#334155',
  primary: '#3B82F6', secondary: '#8B5CF6', accent: '#10B981',
  text: '#F8FAFC', textSecondary: '#94A3B8', textMuted: '#64748B',
  border: '#334155', danger: '#EF4444', warning: '#F59E0B',
  deoGreen: '#059669', deoBlue: '#2563EB',
};

const TABS = [
  { id: 'import', label: 'Import', icon: 'download' },
  { id: 'api-keys', label: 'API Keys', icon: 'key' },
  { id: 'docs', label: 'API Docs', icon: 'code-slash' },
];

export default function DEOScreen() {
  const router = useRouter();
  const { session } = useAuthStore();
  const [activeTab, setActiveTab] = useState('import');

  // Import state
  const [importUrl, setImportUrl] = useState('');
  const [importContext, setImportContext] = useState('');
  const [importMode, setImportMode] = useState<'ai' | 'manual'>('ai');
  const [scraping, setScraping] = useState(false);
  const [scrapedProducts, setScrapedProducts] = useState<any[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<Set<number>>(new Set());
  const [importing, setImporting] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  // Manual selectors
  const [selectors, setSelectors] = useState({
    container: '.product',
    name: '.product-name, h2, h3',
    description: '.description, .summary',
    price: '.price, .amount',
    rating: '.rating, .stars',
    image_url: 'img',
  });

  // API Keys state
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(false);
  const [showCreateKey, setShowCreateKey] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyPermissions, setNewKeyPermissions] = useState(['full_flow', 'values_api', 'logic_api']);
  const [creatingKey, setCreatingKey] = useState(false);
  const [generatedKey, setGeneratedKey] = useState('');

  // Docs state
  const [sdkInfo, setSdkInfo] = useState<any>(null);

  // Fetch API keys
  const fetchApiKeys = useCallback(async () => {
    setLoadingKeys(true);
    try {
      const res = await api.get('/deo/api-keys', { headers: { Authorization: `Bearer ${session}` } });
      setApiKeys(res.data?.keys || []);
    } catch (e) { console.error(e); }
    finally { setLoadingKeys(false); }
  }, [session]);

  useEffect(() => {
    if (activeTab === 'api-keys') fetchApiKeys();
  }, [activeTab, fetchApiKeys]);

  // === IMPORT HANDLERS ===
  const handleScrape = async () => {
    if (!importUrl.trim()) return showAlert('Required', 'Enter a URL to import from');
    setScraping(true);
    try {
      const body: any = { url: importUrl.trim(), mode: importMode, context: importContext };
      if (importMode === 'manual') body.selectors = selectors;

      const res = await api.post('/deo/scrape-url', body, {
        headers: { Authorization: `Bearer ${session}` },
      });
      const products = res.data?.products || [];
      setScrapedProducts(products);
      setSelectedProducts(new Set(products.map((_: any, i: number) => i)));
      if (products.length > 0) {
        setShowPreview(true);
      } else {
        showAlert('No Products Found', 'The AI couldn\'t extract any products from this URL. Try manual mode or a different page.');
      }
    } catch (e: any) {
      showAlert('Scrape Failed', e?.response?.data?.detail || 'Failed to fetch and analyze URL');
    } finally {
      setScraping(false);
    }
  };

  const handleImport = async () => {
    const selected = scrapedProducts.filter((_, i) => selectedProducts.has(i));
    if (selected.length === 0) return showAlert('Select Products', 'Please select at least one product to import');
    setImporting(true);
    try {
      const res = await api.post('/deo/import', {
        products: selected,
        source_url: importUrl,
        country: 'IN',
        language: 'en',
        visibility: 'PRIVATE',
      }, { headers: { Authorization: `Bearer ${session}` } });
      showAlert('Imported!', `${res.data?.total || 0} solutions imported into your Solutions Store`);
      setShowPreview(false);
      setScrapedProducts([]);
      setImportUrl('');
    } catch (e: any) {
      showAlert('Import Failed', e?.response?.data?.detail || 'Failed to import solutions');
    } finally {
      setImporting(false);
    }
  };

  const toggleProduct = (idx: number) => {
    setSelectedProducts(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  // === API KEY HANDLERS ===
  const handleCreateKey = async () => {
    if (!newKeyName.trim()) return showAlert('Required', 'API key name is required');
    setCreatingKey(true);
    try {
      const res = await api.post('/deo/api-keys', {
        name: newKeyName.trim(),
        permissions: newKeyPermissions,
      }, { headers: { Authorization: `Bearer ${session}` } });
      setGeneratedKey(res.data?.api_key || '');
      fetchApiKeys();
      setNewKeyName('');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to create key');
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevokeKey = (keyId: string, name: string) => {
    showAlert('Revoke Key', `Revoke "${name}"? This cannot be undone.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Revoke', style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/deo/api-keys/${keyId}`, { headers: { Authorization: `Bearer ${session}` } });
            fetchApiKeys();
          } catch (e) { showAlert('Error', 'Failed to revoke key'); }
        },
      },
    ]);
  };

  const copyToClipboard = async (text: string) => {
    await Clipboard.setStringAsync(text);
    showAlert('Copied', 'Copied to clipboard');
  };

  // === DOCS ===
  const fetchDocs = async (apiKey: string) => {
    try {
      const res = await api.get('/deo/public/sdk-info', {
        headers: { 'X-DEO-API-Key': apiKey },
      });
      setSdkInfo(res.data);
    } catch (e) {
      showAlert('Error', 'Failed to fetch API docs. Generate an API key first.');
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>DEO Integration</Text>
          <Text style={styles.headerSubtitle}>Decision Engine Optimization</Text>
        </View>
      </View>

      {/* Tabs */}
      <View style={styles.tabBar}>
        {TABS.map(tab => (
          <TouchableOpacity key={tab.id}
            style={[styles.tab, activeTab === tab.id && styles.tabActive]}
            onPress={() => setActiveTab(tab.id)}
          >
            <Ionicons name={tab.icon as any} size={16}
              color={activeTab === tab.id ? COLORS.primary : COLORS.textMuted} />
            <Text style={[styles.tabText, activeTab === tab.id && styles.tabTextActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>

          {/* === IMPORT TAB === */}
          {activeTab === 'import' && (
            <>
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <Ionicons name="globe" size={20} color={COLORS.deoGreen} />
                  <Text style={styles.cardTitle}>Import from URL</Text>
                </View>
                <Text style={styles.cardDesc}>
                  Paste a product/service page URL. Our AI will extract the data and import it into your Solutions Store with quantitative factors, and qualitative reviews into ReviewNet.
                </Text>

                <Text style={styles.inputLabel}>URL *</Text>
                <TextInput
                  style={styles.input}
                  placeholder="https://example.com/products"
                  placeholderTextColor={COLORS.textMuted}
                  value={importUrl}
                  onChangeText={setImportUrl}
                  autoCapitalize="none"
                  keyboardType="url"
                />

                <Text style={styles.inputLabel}>Context (helps AI extract better)</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g., Health insurance plans in Chennai"
                  placeholderTextColor={COLORS.textMuted}
                  value={importContext}
                  onChangeText={setImportContext}
                />

                {/* Mode selector */}
                <Text style={styles.inputLabel}>Extraction Mode</Text>
                <View style={styles.modeRow}>
                  <TouchableOpacity
                    style={[styles.modeChip, importMode === 'ai' && styles.modeChipActive]}
                    onPress={() => setImportMode('ai')}
                  >
                    <Ionicons name="sparkles" size={14} color={importMode === 'ai' ? '#FFF' : COLORS.textMuted} />
                    <Text style={[styles.modeText, importMode === 'ai' && styles.modeTextActive]}>AI Auto-Extract</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.modeChip, importMode === 'manual' && styles.modeChipActive]}
                    onPress={() => setImportMode('manual')}
                  >
                    <Ionicons name="code" size={14} color={importMode === 'manual' ? '#FFF' : COLORS.textMuted} />
                    <Text style={[styles.modeText, importMode === 'manual' && styles.modeTextActive]}>CSS Selectors</Text>
                  </TouchableOpacity>
                </View>

                {importMode === 'manual' && (
                  <View style={styles.selectorsBox}>
                    {Object.entries(selectors).map(([key, val]) => (
                      <View key={key} style={styles.selectorRow}>
                        <Text style={styles.selectorLabel}>{key}</Text>
                        <TextInput
                          style={styles.selectorInput}
                          value={val}
                          onChangeText={(v) => setSelectors(prev => ({ ...prev, [key]: v }))}
                          placeholderTextColor={COLORS.textMuted}
                        />
                      </View>
                    ))}
                  </View>
                )}

                <TouchableOpacity
                  style={[styles.scrapeBtn, scraping && { opacity: 0.6 }]}
                  onPress={handleScrape}
                  disabled={scraping}
                >
                  {scraping ? (
                    <ActivityIndicator color="#FFF" />
                  ) : (
                    <>
                      <Ionicons name="search" size={18} color="#FFF" />
                      <Text style={styles.scrapeBtnText}>Scrape & Extract</Text>
                    </>
                  )}
                </TouchableOpacity>
              </View>
            </>
          )}

          {/* === API KEYS TAB === */}
          {activeTab === 'api-keys' && (
            <>
              <TouchableOpacity style={styles.createKeyBtn} onPress={() => setShowCreateKey(true)}>
                <Ionicons name="add-circle" size={20} color="#FFF" />
                <Text style={styles.createKeyText}>Generate New API Key</Text>
              </TouchableOpacity>

              {loadingKeys ? (
                <ActivityIndicator color={COLORS.primary} style={{ marginTop: 30 }} />
              ) : apiKeys.length === 0 ? (
                <View style={styles.emptyState}>
                  <Ionicons name="key-outline" size={48} color={COLORS.textMuted} />
                  <Text style={styles.emptyTitle}>No API Keys</Text>
                  <Text style={styles.emptySubtext}>Generate a key to start integrating</Text>
                </View>
              ) : (
                apiKeys.map(key => (
                  <View key={key.key_id} style={styles.keyCard}>
                    <View style={styles.keyCardTop}>
                      <Ionicons name="key" size={16} color={COLORS.primary} />
                      <Text style={styles.keyName}>{key.name}</Text>
                      <TouchableOpacity onPress={() => handleRevokeKey(key.key_id, key.name)}>
                        <Ionicons name="trash-outline" size={16} color={COLORS.danger} />
                      </TouchableOpacity>
                    </View>
                    <Text style={styles.keyPrefix}>{key.key_prefix}...</Text>
                    <View style={styles.keyPerms}>
                      {(key.permissions || []).map((p: string) => (
                        <View key={p} style={styles.permBadge}>
                          <Text style={styles.permText}>{p.replace('_', ' ')}</Text>
                        </View>
                      ))}
                    </View>
                    <View style={styles.keyMeta}>
                      <Text style={styles.keyMetaText}>
                        {key.usage_count || 0} requests · Created {new Date(key.created_at).toLocaleDateString()}
                      </Text>
                      <TouchableOpacity onPress={() => fetchDocs(key.key_prefix)}>
                        <Text style={styles.viewDocsLink}>View Docs</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))
              )}
            </>
          )}

          {/* === DOCS TAB === */}
          {activeTab === 'docs' && (
            <>
              <View style={styles.card}>
                <Text style={styles.cardTitle}>DEO Public API</Text>
                <Text style={styles.cardDesc}>
                  Integrate View Dezider's decision engine into your website or application using our REST API, embeddable Widget, or SDK.
                </Text>
              </View>

              {/* Tier 1: Values API */}
              <View style={styles.docCard}>
                <View style={styles.docBadge}>
                  <Text style={styles.docBadgeText}>GET</Text>
                </View>
                <Text style={styles.docEndpoint}>/api/deo/public/solutions</Text>
                <Text style={styles.docDesc}>
                  Fetch solutions with quantitative & qualitative factor values. Filter by life_area, type, country, language.
                </Text>
                <Text style={styles.docPerm}>Permission: values_api</Text>
              </View>

              {/* Tier 2: Full Flow */}
              <View style={styles.docCard}>
                <View style={[styles.docBadge, { backgroundColor: '#059669' }]}>
                  <Text style={styles.docBadgeText}>POST</Text>
                </View>
                <Text style={styles.docEndpoint}>/api/deo/public/decision-flow</Text>
                <Text style={styles.docDesc}>
                  Full decision flow with predefined solutions from the Store as options. Factors auto-populated. User provides assessment percentages. Returns scored ranking.
                </Text>
                <Text style={styles.docPerm}>Permission: full_flow</Text>
              </View>

              {/* Tier 3: Logic API */}
              <View style={styles.docCard}>
                <View style={[styles.docBadge, { backgroundColor: '#7C3AED' }]}>
                  <Text style={styles.docBadgeText}>POST</Text>
                </View>
                <Text style={styles.docEndpoint}>/api/deo/public/decision-logic</Text>
                <Text style={styles.docDesc}>
                  Use our scoring algorithm with YOUR custom options & factors. Send any option-factor-assessment data. Get ranked results with confidence scoring and gap analysis.
                </Text>
                <Text style={styles.docPerm}>Permission: logic_api</Text>
              </View>

              {/* Widget */}
              <View style={styles.docCard}>
                <View style={[styles.docBadge, { backgroundColor: '#F59E0B' }]}>
                  <Text style={styles.docBadgeText}>WIDGET</Text>
                </View>
                <Text style={styles.docEndpoint}>/api/deo/public/widget</Text>
                <Text style={styles.docDesc}>
                  Embeddable comparison widget. Users select solutions and get instant decision analysis. Add to any site with an iframe.
                </Text>
                <View style={styles.codeBlock}>
                  <Text style={styles.codeText} selectable>
                    {'<iframe src="/api/deo/public/widget?api_key=YOUR_KEY&theme=dark" width="400" height="600"></iframe>'}
                  </Text>
                </View>
              </View>

              {/* Auth */}
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Authentication</Text>
                <Text style={styles.cardDesc}>
                  All public API endpoints require a DEO API key. Pass it via:
                </Text>
                <View style={styles.codeBlock}>
                  <Text style={styles.codeText} selectable>
                    {'Header: X-DEO-API-Key: your_key\nOR\nQuery: ?api_key=your_key'}
                  </Text>
                </View>
                <Text style={[styles.cardDesc, { marginTop: 8 }]}>Rate limit: 1,000 requests/day per key</Text>
              </View>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Scrape Preview Modal */}
      <Modal visible={showPreview} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.modalTitle}>Extracted Products</Text>
                <Text style={styles.modalSubtitle}>{scrapedProducts.length} found · {selectedProducts.size} selected</Text>
              </View>
              <TouchableOpacity onPress={() => setShowPreview(false)}>
                <Ionicons name="close" size={24} color={COLORS.text} />
              </TouchableOpacity>
            </View>

            <FlatList
              data={scrapedProducts}
              keyExtractor={(_, i) => String(i)}
              renderItem={({ item, index }) => {
                const isSelected = selectedProducts.has(index);
                return (
                  <TouchableOpacity
                    style={[styles.productCard, isSelected && styles.productCardSelected]}
                    onPress={() => toggleProduct(index)}
                  >
                    <View style={styles.productCheck}>
                      <Ionicons
                        name={isSelected ? 'checkbox' : 'square-outline'}
                        size={22} color={isSelected ? COLORS.accent : COLORS.textMuted}
                      />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.productName}>{item.name}</Text>
                      <Text style={styles.productDesc} numberOfLines={2}>{item.description}</Text>
                      {item.provider && <Text style={styles.productProvider}>{item.provider} · {item.price_range || ''}</Text>}
                      {item.quantitative_factors?.length > 0 && (
                        <View style={styles.factorRow}>
                          {item.quantitative_factors.slice(0, 3).map((f: any, i: number) => (
                            <View key={i} style={styles.factorPill}>
                              <Text style={styles.factorPillText}>{f.factor_name}: {f.value}{f.unit ? ` ${f.unit}` : ''}</Text>
                            </View>
                          ))}
                        </View>
                      )}
                      {item.qualitative_factors?.length > 0 && (
                        <Text style={styles.qualNote}>{item.qualitative_factors.length} qualitative factors → ReviewNet</Text>
                      )}
                    </View>
                  </TouchableOpacity>
                );
              }}
            />

            <TouchableOpacity
              style={[styles.importBtn, importing && { opacity: 0.6 }]}
              onPress={handleImport}
              disabled={importing || selectedProducts.size === 0}
            >
              {importing ? <ActivityIndicator color="#FFF" /> : (
                <>
                  <Ionicons name="download" size={18} color="#FFF" />
                  <Text style={styles.importBtnText}>Import {selectedProducts.size} to Solutions Store</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Create API Key Modal */}
      <Modal visible={showCreateKey} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { maxHeight: '60%' }]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{generatedKey ? 'API Key Generated!' : 'New API Key'}</Text>
              <TouchableOpacity onPress={() => { setShowCreateKey(false); setGeneratedKey(''); }}>
                <Ionicons name="close" size={24} color={COLORS.text} />
              </TouchableOpacity>
            </View>

            {generatedKey ? (
              <View style={{ alignItems: 'center', paddingVertical: 20 }}>
                <Ionicons name="shield-checkmark" size={48} color={COLORS.accent} />
                <Text style={[styles.inputLabel, { marginTop: 12, textAlign: 'center' }]}>
                  Save this key — it won't be shown again!
                </Text>
                <View style={styles.codeBlock}>
                  <Text style={styles.codeText} selectable numberOfLines={3}>{generatedKey}</Text>
                </View>
                <TouchableOpacity style={styles.copyBtn} onPress={() => copyToClipboard(generatedKey)}>
                  <Ionicons name="copy" size={16} color="#FFF" />
                  <Text style={styles.copyBtnText}>Copy to Clipboard</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <>
                <Text style={styles.inputLabel}>Key Name *</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g., My Website Integration"
                  placeholderTextColor={COLORS.textMuted}
                  value={newKeyName}
                  onChangeText={setNewKeyName}
                />

                <Text style={[styles.inputLabel, { marginTop: 12 }]}>Permissions</Text>
                {['full_flow', 'values_api', 'logic_api'].map(p => (
                  <TouchableOpacity key={p} style={styles.permToggle}
                    onPress={() => {
                      setNewKeyPermissions(prev =>
                        prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
                      );
                    }}
                  >
                    <Ionicons
                      name={newKeyPermissions.includes(p) ? 'checkbox' : 'square-outline'}
                      size={20} color={newKeyPermissions.includes(p) ? COLORS.accent : COLORS.textMuted}
                    />
                    <Text style={styles.permToggleText}>{p.replace(/_/g, ' ').toUpperCase()}</Text>
                  </TouchableOpacity>
                ))}

                <TouchableOpacity
                  style={[styles.scrapeBtn, creatingKey && { opacity: 0.6 }]}
                  onPress={handleCreateKey}
                  disabled={creatingKey}
                >
                  {creatingKey ? <ActivityIndicator color="#FFF" /> : (
                    <>
                      <Ionicons name="key" size={18} color="#FFF" />
                      <Text style={styles.scrapeBtnText}>Generate Key</Text>
                    </>
                  )}
                </TouchableOpacity>
              </>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  backBtn: { marginRight: 12, padding: 4 },
  headerTitle: { fontSize: 20, fontWeight: '700', color: COLORS.text },
  headerSubtitle: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  tabBar: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: COLORS.border },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: COLORS.primary },
  tabText: { fontSize: 13, color: COLORS.textMuted },
  tabTextActive: { color: COLORS.primary, fontWeight: '600' },
  card: { backgroundColor: COLORS.surface, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: COLORS.text },
  cardDesc: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18 },
  inputLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 12, marginBottom: 6 },
  input: { backgroundColor: COLORS.surfaceLight, borderRadius: 10, padding: 12, color: COLORS.text, fontSize: 14, borderWidth: 1, borderColor: COLORS.border },
  modeRow: { flexDirection: 'row', gap: 8 },
  modeChip: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border },
  modeChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  modeText: { fontSize: 13, color: COLORS.textMuted },
  modeTextActive: { color: '#FFF', fontWeight: '600' },
  selectorsBox: { backgroundColor: COLORS.surfaceLight, borderRadius: 10, padding: 10, marginTop: 8, gap: 6 },
  selectorRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  selectorLabel: { width: 80, fontSize: 11, color: COLORS.textMuted, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  selectorInput: { flex: 1, backgroundColor: COLORS.bg, borderRadius: 6, padding: 6, color: COLORS.text, fontSize: 11, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  scrapeBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.deoGreen, borderRadius: 12, paddingVertical: 14, marginTop: 16 },
  scrapeBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  // API Keys
  createKeyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 14, marginBottom: 16 },
  createKeyText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  emptyState: { alignItems: 'center', paddingTop: 40 },
  emptyTitle: { fontSize: 16, color: COLORS.textSecondary, marginTop: 12 },
  emptySubtext: { fontSize: 12, color: COLORS.textMuted, marginTop: 4 },
  keyCard: { backgroundColor: COLORS.surface, borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  keyCardTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  keyName: { flex: 1, fontSize: 15, fontWeight: '600', color: COLORS.text },
  keyPrefix: { fontSize: 12, color: COLORS.textMuted, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', marginTop: 4 },
  keyPerms: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 6 },
  permBadge: { backgroundColor: COLORS.primary + '20', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  permText: { fontSize: 10, color: COLORS.primary, fontWeight: '600', textTransform: 'uppercase' },
  keyMeta: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 },
  keyMetaText: { fontSize: 11, color: COLORS.textMuted },
  viewDocsLink: { fontSize: 12, color: COLORS.primary, fontWeight: '600' },
  // Docs
  docCard: { backgroundColor: COLORS.surface, borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  docBadge: { backgroundColor: COLORS.primary, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, alignSelf: 'flex-start', marginBottom: 6 },
  docBadgeText: { fontSize: 10, fontWeight: '700', color: '#FFF' },
  docEndpoint: { fontSize: 13, fontWeight: '600', color: COLORS.text, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', marginBottom: 4 },
  docDesc: { fontSize: 12, color: COLORS.textSecondary, lineHeight: 17 },
  docPerm: { fontSize: 10, color: COLORS.textMuted, marginTop: 6 },
  codeBlock: { backgroundColor: COLORS.bg, borderRadius: 8, padding: 10, marginTop: 8 },
  codeText: { fontSize: 11, color: COLORS.accent, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace', lineHeight: 16 },
  copyBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: COLORS.primary, paddingHorizontal: 16, paddingVertical: 10, borderRadius: 10, marginTop: 12 },
  copyBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
  permToggle: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8 },
  permToggleText: { fontSize: 14, color: COLORS.textSecondary },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: COLORS.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, maxHeight: '85%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  modalSubtitle: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  // Products
  productCard: { flexDirection: 'row', backgroundColor: COLORS.surfaceLight, borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  productCardSelected: { borderColor: COLORS.accent, backgroundColor: COLORS.accent + '10' },
  productCheck: { marginRight: 10, paddingTop: 2 },
  productName: { fontSize: 14, fontWeight: '600', color: COLORS.text },
  productDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  productProvider: { fontSize: 11, color: COLORS.textMuted, marginTop: 4 },
  factorRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 6 },
  factorPill: { backgroundColor: COLORS.primary + '15', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  factorPillText: { fontSize: 10, color: COLORS.primary },
  qualNote: { fontSize: 10, color: COLORS.accent, marginTop: 4 },
  importBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.accent, borderRadius: 12, paddingVertical: 14, marginTop: 12 },
  importBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
});
