import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl, Share, Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';

type DocType = 'prd' | 'srs' | 'regression_tests' | 'uat_cases' | 'api_catalog';

interface DocData {
  doc_type: string;
  content: string | null;
  generated_at: string | null;
  generated_by?: string;
}

interface ApiEndpoint {
  method: string;
  path: string;
  summary: string;
  description: string;
  tags: string[];
  category: string;
  channels: string[];
  parameters: any[];
  request_sample: any;
  response_sample: any;
  requires_auth: boolean;
}

interface ApiCatalog {
  total_endpoints: number;
  endpoints: ApiEndpoint[];
  generated_at: string;
}

const TABS: { key: DocType; label: string; icon: string; color: string }[] = [
  { key: 'api_catalog', label: 'API Docs', icon: 'code-slash', color: '#6366F1' },
  { key: 'prd', label: 'PRD', icon: 'document-text', color: '#059669' },
  { key: 'srs', label: 'SRS', icon: 'construct', color: '#2563EB' },
  { key: 'regression_tests', label: 'Regression', icon: 'bug', color: '#DC2626' },
  { key: 'uat_cases', label: 'UAT', icon: 'checkmark-done-circle', color: '#D97706' },
];

const METHOD_COLORS: Record<string, string> = {
  GET: '#10B981',
  POST: '#3B82F6',
  PUT: '#F59E0B',
  DELETE: '#EF4444',
  PATCH: '#8B5CF6',
};

const CHANNEL_COLORS: Record<string, { bg: string; text: string }> = {
  internal: { bg: '#EFF6FF', text: '#2563EB' },
  chatbot: { bg: '#F0FDF4', text: '#059669' },
  ivr: { bg: '#FFF7ED', text: '#D97706' },
  partner: { bg: '#FAF5FF', text: '#7C3AED' },
};

export default function AdminDocsScreen() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<DocType>('api_catalog');
  const [docs, setDocs] = useState<Record<string, DocData>>({});
  const [apiCatalog, setApiCatalog] = useState<ApiCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingDoc, setRefreshingDoc] = useState<string | null>(null);
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [channelFilter, setChannelFilter] = useState<string | null>(null);
  const [expandedEndpoints, setExpandedEndpoints] = useState<Set<string>>(new Set());
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [exportingPostman, setExportingPostman] = useState(false);

  const fetchDocs = async () => {
    try {
      const [prd, srs, tests, uat] = await Promise.all([
        api.get('/admin/docs/prd').catch(() => ({ data: { doc_type: 'prd', content: null, generated_at: null } })),
        api.get('/admin/docs/srs').catch(() => ({ data: { doc_type: 'srs', content: null, generated_at: null } })),
        api.get('/admin/docs/regression_tests').catch(() => ({ data: { doc_type: 'regression_tests', content: null, generated_at: null } })),
        api.get('/admin/docs/uat_cases').catch(() => ({ data: { doc_type: 'uat_cases', content: null, generated_at: null } })),
      ]);
      setDocs({
        prd: prd.data,
        srs: srs.data,
        regression_tests: tests.data,
        uat_cases: uat.data,
      });
    } catch (err) {
      console.error('Error fetching docs:', err);
    }
  };

  const fetchApiCatalog = async () => {
    try {
      const url = channelFilter ? `/admin/docs/api-catalog?channel=${channelFilter}` : '/admin/docs/api-catalog';
      const res = await api.get(url);
      setApiCatalog(res.data);
    } catch (err) {
      console.error('Error fetching API catalog:', err);
    }
  };

  const fetchAll = async () => {
    setLoading(true);
    await Promise.all([fetchDocs(), fetchApiCatalog()]);
    setLoading(false);
  };

  useFocusEffect(useCallback(() => { fetchAll(); }, []));

  // Re-fetch catalog when channel filter changes
  React.useEffect(() => {
    fetchApiCatalog();
  }, [channelFilter]);

  const handleRefreshDoc = async (docType: string) => {
    setRefreshingDoc(docType);
    try {
      const res = await api.post(`/admin/docs/refresh/${docType}`);
      setDocs(prev => ({ ...prev, [docType]: res.data }));
      showAlert('Generated', `${docType.toUpperCase().replace('_', ' ')} has been regenerated successfully.`);
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to generate document');
    } finally {
      setRefreshingDoc(null);
    }
  };

  const handleRefreshAll = async () => {
    setRefreshingAll(true);
    try {
      await api.post('/admin/docs/refresh-all');
      await fetchDocs();
      showAlert('All Documents Generated', 'PRD, SRS, Regression Tests, and UAT Cases have been regenerated.');
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to regenerate all');
    } finally {
      setRefreshingAll(false);
    }
  };

  const handleExportPostman = async () => {
    setExportingPostman(true);
    try {
      const res = await api.get('/admin/docs/postman-collection');
      const jsonStr = JSON.stringify(res.data, null, 2);

      if (Platform.OS === 'web') {
        // Web: trigger download via blob
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'ViewDezider_API_Collection.json';
        a.click();
        URL.revokeObjectURL(url);
        showAlert('Exported', 'Postman Collection downloaded successfully.');
      } else {
        // Native: save to file system and share
        const fileUri = FileSystem.documentDirectory + 'ViewDezider_API_Collection.json';
        await FileSystem.writeAsStringAsync(fileUri, jsonStr);
        const canShare = await Sharing.isAvailableAsync();
        if (canShare) {
          await Sharing.shareAsync(fileUri, {
            mimeType: 'application/json',
            dialogTitle: 'Export Postman Collection',
            UTI: 'public.json',
          });
        } else {
          showAlert('Saved', `Collection saved to: ${fileUri}`);
        }
      }
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to export Postman collection');
    } finally {
      setExportingPostman(false);
    }
  };

  const toggleEndpoint = (key: string) => {
    setExpandedEndpoints(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const toggleCategory = (cat: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  };

  const formatDate = (d: string | null) => {
    if (!d) return 'Never';
    return new Date(d).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  // Group endpoints by category
  const groupedEndpoints = React.useMemo(() => {
    if (!apiCatalog) return {};
    const groups: Record<string, ApiEndpoint[]> = {};
    for (const ep of apiCatalog.endpoints) {
      if (!groups[ep.category]) groups[ep.category] = [];
      groups[ep.category].push(ep);
    }
    return groups;
  }, [apiCatalog]);

  const renderMarkdown = (content: string) => {
    // Simple markdown renderer — split into lines and style headers/lists/code
    const lines = content.split('\n');
    return lines.map((line, idx) => {
      const trimmed = line;
      if (trimmed.startsWith('# ')) {
        return <Text key={idx} style={styles.mdH1}>{trimmed.replace('# ', '')}</Text>;
      }
      if (trimmed.startsWith('## ')) {
        return <Text key={idx} style={styles.mdH2}>{trimmed.replace('## ', '')}</Text>;
      }
      if (trimmed.startsWith('### ')) {
        return <Text key={idx} style={styles.mdH3}>{trimmed.replace('### ', '')}</Text>;
      }
      if (trimmed.startsWith('#### ')) {
        return <Text key={idx} style={styles.mdH4}>{trimmed.replace('#### ', '')}</Text>;
      }
      if (trimmed.startsWith('**') && trimmed.endsWith('**')) {
        return <Text key={idx} style={styles.mdBold}>{trimmed.replace(/\*\*/g, '')}</Text>;
      }
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        return (
          <View key={idx} style={styles.mdListItem}>
            <Text style={styles.mdBullet}>•</Text>
            <Text style={styles.mdListText}>{trimmed.slice(2)}</Text>
          </View>
        );
      }
      if (/^\d+\.\s/.test(trimmed)) {
        const num = trimmed.match(/^(\d+)\.\s/)?.[1] || '';
        const text = trimmed.replace(/^\d+\.\s/, '');
        return (
          <View key={idx} style={styles.mdListItem}>
            <Text style={styles.mdNum}>{num}.</Text>
            <Text style={styles.mdListText}>{text}</Text>
          </View>
        );
      }
      if (trimmed.startsWith('```')) {
        return null; // Skip code fences
      }
      if (trimmed.startsWith('> ')) {
        return (
          <View key={idx} style={styles.mdBlockquote}>
            <Text style={styles.mdBlockquoteText}>{trimmed.slice(2)}</Text>
          </View>
        );
      }
      if (trimmed === '---' || trimmed === '***') {
        return <View key={idx} style={styles.mdHr} />;
      }
      if (trimmed.trim() === '') {
        return <View key={idx} style={{ height: 6 }} />;
      }
      return <Text key={idx} style={styles.mdText}>{trimmed}</Text>;
    });
  };

  // ========== RENDER API CATALOG ==========
  const renderApiCatalog = () => (
    <View>
      {/* Postman Export Button */}
      <TouchableOpacity
        style={[styles.postmanExportBtn, exportingPostman && { opacity: 0.5 }]}
        onPress={handleExportPostman}
        disabled={exportingPostman}
      >
        {exportingPostman ? (
          <ActivityIndicator color="#FFF" size="small" />
        ) : (
          <>
            <Ionicons name="download-outline" size={18} color="#FFF" />
            <View style={{ flex: 1 }}>
              <Text style={styles.postmanExportTitle}>Export Postman Collection</Text>
              <Text style={styles.postmanExportSub}>Download v2.1 JSON with all endpoints</Text>
            </View>
            <Ionicons name="arrow-forward" size={16} color="rgba(255,255,255,0.7)" />
          </>
        )}
      </TouchableOpacity>

      {/* Channel Filters */}
      <View style={styles.channelFilters}>
        <TouchableOpacity
          style={[styles.channelChip, !channelFilter && styles.channelChipActive]}
          onPress={() => setChannelFilter(null)}
        >
          <Text style={[styles.channelChipText, !channelFilter && { color: '#FFF' }]}>All ({apiCatalog?.total_endpoints || 0})</Text>
        </TouchableOpacity>
        {['internal', 'chatbot', 'ivr', 'partner'].map(ch => (
          <TouchableOpacity
            key={ch}
            style={[
              styles.channelChip,
              channelFilter === ch && { backgroundColor: CHANNEL_COLORS[ch].text },
            ]}
            onPress={() => setChannelFilter(channelFilter === ch ? null : ch)}
          >
            <Text style={[
              styles.channelChipText,
              channelFilter === ch && { color: '#FFF' },
            ]}>
              {ch === 'internal' ? '📱 App' : ch === 'chatbot' ? '🤖 Chatbot' : ch === 'ivr' ? '📞 IVR' : '🤝 Partner'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Endpoint Categories */}
      {Object.entries(groupedEndpoints).map(([category, endpoints]) => {
        const isExpanded = expandedCategories.has(category);
        return (
          <View key={category} style={styles.categorySection}>
            <TouchableOpacity
              style={styles.categoryHeader}
              onPress={() => toggleCategory(category)}
            >
              <View style={styles.categoryLeft}>
                <Ionicons
                  name={isExpanded ? 'chevron-down' : 'chevron-forward'}
                  size={16}
                  color={COLORS.textSecondary}
                />
                <Text style={styles.categoryTitle}>{category}</Text>
              </View>
              <View style={styles.categoryBadge}>
                <Text style={styles.categoryBadgeText}>{endpoints.length}</Text>
              </View>
            </TouchableOpacity>

            {isExpanded && endpoints.map((ep, idx) => {
              const epKey = `${ep.method}-${ep.path}`;
              const isEpExpanded = expandedEndpoints.has(epKey);
              return (
                <View key={idx} style={styles.endpointCard}>
                  <TouchableOpacity
                    style={styles.endpointHeader}
                    onPress={() => toggleEndpoint(epKey)}
                  >
                    <View style={[styles.methodBadge, { backgroundColor: METHOD_COLORS[ep.method] || '#6B7280' }]}>
                      <Text style={styles.methodText}>{ep.method}</Text>
                    </View>
                    <Text style={styles.endpointPath} numberOfLines={1}>{ep.path}</Text>
                    <Ionicons
                      name={isEpExpanded ? 'chevron-up' : 'chevron-down'}
                      size={16}
                      color={COLORS.textMuted}
                    />
                  </TouchableOpacity>

                  {/* Channel tags */}
                  <View style={styles.channelTags}>
                    {ep.channels.map(ch => (
                      <View key={ch} style={[styles.channelTag, { backgroundColor: CHANNEL_COLORS[ch]?.bg || '#F3F4F6' }]}>
                        <Text style={[styles.channelTagText, { color: CHANNEL_COLORS[ch]?.text || '#6B7280' }]}>
                          {ch}
                        </Text>
                      </View>
                    ))}
                  </View>

                  {ep.summary ? <Text style={styles.endpointSummary}>{ep.summary}</Text> : null}

                  {isEpExpanded && (
                    <View style={styles.endpointDetail}>
                      {ep.description ? (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Description</Text>
                          <Text style={styles.detailText}>{ep.description}</Text>
                        </View>
                      ) : null}

                      {ep.parameters.length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Parameters</Text>
                          {ep.parameters.map((p: any, pi: number) => (
                            <View key={pi} style={styles.paramRow}>
                              <Text style={styles.paramName}>{p.name}</Text>
                              <Text style={styles.paramMeta}>{p.in} • {p.type}{p.required ? ' • required' : ''}</Text>
                            </View>
                          ))}
                        </View>
                      )}

                      {ep.request_sample && Object.keys(ep.request_sample).length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Request Body (Sample)</Text>
                          <View style={styles.codeBlock}>
                            <Text style={styles.codeText}>
                              {JSON.stringify(ep.request_sample, null, 2)}
                            </Text>
                          </View>
                        </View>
                      )}

                      {ep.response_sample && Object.keys(ep.response_sample).length > 0 && (
                        <View style={styles.detailSection}>
                          <Text style={styles.detailLabel}>Response (Sample)</Text>
                          <View style={styles.codeBlock}>
                            <Text style={styles.codeText}>
                              {JSON.stringify(ep.response_sample, null, 2)}
                            </Text>
                          </View>
                        </View>
                      )}

                      <View style={styles.detailSection}>
                        <Text style={styles.detailLabel}>Authentication</Text>
                        <Text style={styles.detailText}>
                          {ep.requires_auth ? '🔒 Bearer Token Required' : '🔓 Public'}
                        </Text>
                      </View>
                    </View>
                  )}
                </View>
              );
            })}
          </View>
        );
      })}
    </View>
  );

  // ========== RENDER DOC CONTENT ==========
  const renderDocContent = (docType: DocType) => {
    const doc = docs[docType];
    const isRefreshing = refreshingDoc === docType;

    return (
      <View>
        {/* Doc Header */}
        <View style={styles.docHeader}>
          <View style={{ flex: 1 }}>
            <Text style={styles.docTimestamp}>
              Last generated: {formatDate(doc?.generated_at || null)}
            </Text>
            {doc?.generated_by && (
              <Text style={styles.docAuthor}>By: {doc.generated_by}</Text>
            )}
          </View>
          <TouchableOpacity
            style={[styles.refreshBtn, isRefreshing && { opacity: 0.5 }]}
            onPress={() => handleRefreshDoc(docType)}
            disabled={isRefreshing}
          >
            {isRefreshing ? (
              <ActivityIndicator color="#6366F1" size="small" />
            ) : (
              <>
                <Ionicons name="refresh" size={16} color="#6366F1" />
                <Text style={styles.refreshBtnText}>Regenerate</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Content */}
        {!doc?.content ? (
          <View style={styles.noContent}>
            <Ionicons name="document-outline" size={40} color="#D1D5DB" />
            <Text style={styles.noContentTitle}>Not Yet Generated</Text>
            <Text style={styles.noContentText}>
              Click "Regenerate" above or use "Refresh All" to generate this document using AI.
            </Text>
          </View>
        ) : (
          <View style={styles.docContent}>
            {renderMarkdown(doc.content)}
          </View>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <LinearGradient
        colors={['#1E293B', '#334155']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.header}
      >
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Documentation Hub</Text>
          <Text style={styles.headerSub}>PRD • SRS • Tests • API Catalog</Text>
        </View>
        <TouchableOpacity
          style={[styles.refreshAllBtn, refreshingAll && { opacity: 0.5 }]}
          onPress={handleRefreshAll}
          disabled={refreshingAll}
        >
          {refreshingAll ? (
            <ActivityIndicator color="#FFF" size="small" />
          ) : (
            <>
              <Ionicons name="sync" size={16} color="#FFF" />
              <Text style={styles.refreshAllText}>Refresh All</Text>
            </>
          )}
        </TouchableOpacity>
      </LinearGradient>

      {/* Tabs */}
      <View style={styles.tabBar}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingHorizontal: 16 }}>
          {TABS.map(tab => (
            <TouchableOpacity
              key={tab.key}
              style={[styles.tab, activeTab === tab.key && { backgroundColor: tab.color }]}
              onPress={() => setActiveTab(tab.key)}
            >
              <Ionicons
                name={tab.icon as any}
                size={15}
                color={activeTab === tab.key ? '#FFF' : COLORS.textSecondary}
              />
              <Text style={[
                styles.tabText,
                activeTab === tab.key && { color: '#FFF', fontWeight: '700' },
              ]}>{tab.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Content */}
      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={{ color: COLORS.textSecondary, marginTop: 12 }}>Loading documentation...</Text>
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
          showsVerticalScrollIndicator={false}
        >
          {activeTab === 'api_catalog' ? renderApiCatalog() : renderDocContent(activeTab)}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  // Header
  header: {
    flexDirection: 'row', alignItems: 'center',
    padding: 16, paddingTop: 12, paddingBottom: 18, gap: 12,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.15)',
    justifyContent: 'center', alignItems: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  refreshAllBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#6366F1', paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 10,
  },
  refreshAllText: { fontSize: 12, fontWeight: '700', color: '#FFF' },

  // Tabs
  tabBar: {
    paddingVertical: 10,
    backgroundColor: '#FFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  tab: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 20, backgroundColor: '#F3F4F6',
  },
  tabText: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },

  // Channel filters
  channelFilters: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16,
  },
  channelChip: {
    paddingHorizontal: 14, paddingVertical: 8,
    borderRadius: 20, backgroundColor: '#F3F4F6',
    borderWidth: 1, borderColor: '#E5E7EB',
  },
  channelChipActive: { backgroundColor: '#1E293B', borderColor: '#1E293B' },
  channelChipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },

  // Category section
  categorySection: { marginBottom: 12 },
  categoryHeader: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: '#FFF', padding: 14, borderRadius: 12,
    borderWidth: 1, borderColor: '#E5E7EB',
  },
  categoryLeft: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 },
  categoryTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  categoryBadge: {
    backgroundColor: '#EFF6FF', paddingHorizontal: 10, paddingVertical: 3, borderRadius: 10,
  },
  categoryBadgeText: { fontSize: 11, fontWeight: '700', color: '#2563EB' },

  // Endpoint card
  endpointCard: {
    backgroundColor: '#FFF', borderRadius: 10, padding: 12,
    marginTop: 6, marginLeft: 12, borderWidth: 1, borderColor: '#F3F4F6',
  },
  endpointHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
  },
  methodBadge: {
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4, minWidth: 50, alignItems: 'center',
  },
  methodText: { fontSize: 10, fontWeight: '800', color: '#FFF', letterSpacing: 0.5 },
  endpointPath: { flex: 1, fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, fontFamily: 'monospace' },
  endpointSummary: { fontSize: 12, color: COLORS.textSecondary, marginTop: 6 },

  // Channel tags
  channelTags: { flexDirection: 'row', gap: 4, marginTop: 6 },
  channelTag: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  channelTagText: { fontSize: 10, fontWeight: '600' },

  // Endpoint detail
  endpointDetail: {
    marginTop: 12, paddingTop: 12,
    borderTopWidth: 1, borderTopColor: '#F3F4F6',
  },
  detailSection: { marginBottom: 12 },
  detailLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted, textTransform: 'uppercase', marginBottom: 4, letterSpacing: 0.5 },
  detailText: { fontSize: 13, color: COLORS.textPrimary, lineHeight: 18 },
  paramRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 4 },
  paramName: { fontSize: 13, fontWeight: '600', color: '#6366F1', fontFamily: 'monospace' },
  paramMeta: { fontSize: 11, color: COLORS.textMuted },
  codeBlock: {
    backgroundColor: '#1E293B', borderRadius: 8, padding: 12,
  },
  codeText: { fontSize: 11, color: '#A5F3FC', fontFamily: 'monospace', lineHeight: 16 },

  // Doc header
  docHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#FFF', borderRadius: 12, padding: 14,
    marginBottom: 16, borderWidth: 1, borderColor: '#E5E7EB',
  },
  docTimestamp: { fontSize: 12, color: COLORS.textSecondary },
  docAuthor: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  refreshBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#EEF2FF', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8,
  },
  refreshBtnText: { fontSize: 12, fontWeight: '600', color: '#6366F1' },

  // No content
  noContent: {
    alignItems: 'center', paddingVertical: 48, gap: 10,
  },
  noContentTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  noContentText: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', paddingHorizontal: 32, lineHeight: 18 },

  // Doc content (Markdown rendering)
  docContent: {
    backgroundColor: '#FFF', borderRadius: 12, padding: 16,
    borderWidth: 1, borderColor: '#E5E7EB',
  },
  mdH1: { fontSize: 22, fontWeight: '800', color: COLORS.textPrimary, marginTop: 16, marginBottom: 8 },
  mdH2: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginTop: 14, marginBottom: 6, borderBottomWidth: 1, borderBottomColor: '#E5E7EB', paddingBottom: 4 },
  mdH3: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginTop: 10, marginBottom: 4 },
  mdH4: { fontSize: 14, fontWeight: '600', color: COLORS.textSecondary, marginTop: 8, marginBottom: 4 },
  mdBold: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginVertical: 4 },
  mdText: { fontSize: 13, color: COLORS.textPrimary, lineHeight: 20 },
  mdListItem: { flexDirection: 'row', gap: 8, paddingLeft: 8, marginVertical: 2 },
  mdBullet: { fontSize: 13, color: COLORS.textMuted, width: 12 },
  mdNum: { fontSize: 13, fontWeight: '600', color: COLORS.textMuted, width: 20 },
  mdListText: { flex: 1, fontSize: 13, color: COLORS.textPrimary, lineHeight: 20 },
  mdBlockquote: {
    borderLeftWidth: 3, borderLeftColor: '#6366F1',
    paddingLeft: 12, marginVertical: 4,
  },
  mdBlockquoteText: { fontSize: 13, color: '#4338CA', fontStyle: 'italic' },
  mdHr: { height: 1, backgroundColor: '#E5E7EB', marginVertical: 12 },

  // Postman Export
  postmanExportBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#F97316', borderRadius: 14, padding: 16,
    marginBottom: 16,
  },
  postmanExportTitle: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  postmanExportSub: { fontSize: 11, color: 'rgba(255,255,255,0.8)', marginTop: 1 },
});
