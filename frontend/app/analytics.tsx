import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../src/constants/colors';
import api from '../src/utils/api';

interface FolderStat {
  id: string;
  name: string;
  icon: string;
  color: string;
  total_decisions: number;
  completed: number;
  in_progress: number;
  draft: number;
  avg_factors: number;
  avg_options: number;
  completion_rate: number;
  recent_decision: any;
}

interface Analytics {
  folders: FolderStat[];
  active_folders: FolderStat[];
  summary: {
    total_decisions: number;
    total_completed: number;
    total_folders_used: number;
    overall_completion_rate: number;
    most_active_folder: string | null;
  };
}

export default function AnalyticsScreen() {
  const router = useRouter();
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expandedFolder, setExpandedFolder] = useState<string | null>(null);
  const [folderDetail, setFolderDetail] = useState<any>(null);

  const fetchAnalytics = async () => {
    try {
      const response = await api.get('/analytics/folders');
      setAnalytics(response.data);
    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchFolderDetail = async (folderId: string) => {
    try {
      const response = await api.get(`/analytics/folder/${folderId}`);
      setFolderDetail(response.data);
    } catch {}
  };

  useFocusEffect(useCallback(() => { fetchAnalytics(); }, []));

  const onRefresh = async () => { setRefreshing(true); await fetchAnalytics(); setRefreshing(false); };

  const handleExpandFolder = (folderId: string) => {
    if (expandedFolder === folderId) {
      setExpandedFolder(null);
      setFolderDetail(null);
    } else {
      setExpandedFolder(folderId);
      fetchFolderDetail(folderId);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      </SafeAreaView>
    );
  }

  const summary = analytics?.summary;
  const folders = analytics?.folders || [];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Folder Analytics</Text>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        showsVerticalScrollIndicator={false}
      >
        {/* Overall Summary */}
        <View style={styles.summaryCard}>
          <Text style={styles.summaryTitle}>Overall Decision Health</Text>
          <View style={styles.summaryGrid}>
            <View style={styles.summaryItem}>
              <Text style={styles.summaryNumber}>{summary?.total_decisions || 0}</Text>
              <Text style={styles.summaryLabel}>Total</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={[styles.summaryNumber, { color: COLORS.success }]}>{summary?.total_completed || 0}</Text>
              <Text style={styles.summaryLabel}>Completed</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={[styles.summaryNumber, { color: COLORS.primary }]}>{summary?.total_folders_used || 0}</Text>
              <Text style={styles.summaryLabel}>Life Areas</Text>
            </View>
            <View style={styles.summaryItem}>
              <Text style={[styles.summaryNumber, { color: '#F59E0B' }]}>{summary?.overall_completion_rate || 0}%</Text>
              <Text style={styles.summaryLabel}>Complete</Text>
            </View>
          </View>
          {summary?.most_active_folder && (
            <View style={styles.mostActive}>
              <Ionicons name="trending-up" size={14} color={COLORS.primary} />
              <Text style={styles.mostActiveText}>Most active: {summary.most_active_folder}</Text>
            </View>
          )}
        </View>

        {/* Folder Breakdown */}
        <Text style={styles.sectionTitle}>Life Area Breakdown</Text>

        {folders.map(folder => {
          const isExpanded = expandedFolder === folder.id;
          const hasDecisions = folder.total_decisions > 0;

          return (
            <TouchableOpacity
              key={folder.id}
              style={[styles.folderCard, isExpanded && styles.folderCardExpanded]}
              onPress={() => hasDecisions && handleExpandFolder(folder.id)}
              activeOpacity={hasDecisions ? 0.7 : 1}
            >
              {/* Folder header row */}
              <View style={styles.folderRow}>
                <View style={[styles.folderIconWrap, { backgroundColor: folder.color + '18' }]}>
                  <Ionicons name={folder.icon as any} size={20} color={folder.color} />
                </View>
                <View style={styles.folderInfo}>
                  <Text style={styles.folderName}>{folder.name}</Text>
                  <Text style={styles.folderCount}>
                    {folder.total_decisions} decision{folder.total_decisions !== 1 ? 's' : ''}
                  </Text>
                </View>
                {hasDecisions && (
                  <View style={styles.rateContainer}>
                    {/* Completion bar */}
                    <View style={styles.barBg}>
                      <View style={[styles.barFill, { width: `${Math.min(100, folder.completion_rate)}%`, backgroundColor: folder.color }]} />
                    </View>
                    <Text style={[styles.rateText, { color: folder.color }]}>{folder.completion_rate}%</Text>
                  </View>
                )}
                {hasDecisions && (
                  <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color={COLORS.textMuted} />
                )}
              </View>

              {/* Expanded detail */}
              {isExpanded && (
                <View style={styles.expandedContent}>
                  <View style={styles.detailGrid}>
                    <View style={[styles.detailItem, { backgroundColor: COLORS.success + '10' }]}>
                      <Text style={[styles.detailNum, { color: COLORS.success }]}>{folder.completed}</Text>
                      <Text style={styles.detailLabel}>Done</Text>
                    </View>
                    <View style={[styles.detailItem, { backgroundColor: '#F59E0B10' }]}>
                      <Text style={[styles.detailNum, { color: '#F59E0B' }]}>{folder.in_progress}</Text>
                      <Text style={styles.detailLabel}>Active</Text>
                    </View>
                    <View style={[styles.detailItem, { backgroundColor: COLORS.textMuted + '10' }]}>
                      <Text style={[styles.detailNum, { color: COLORS.textMuted }]}>{folder.draft}</Text>
                      <Text style={styles.detailLabel}>Draft</Text>
                    </View>
                    <View style={[styles.detailItem, { backgroundColor: COLORS.primary + '10' }]}>
                      <Text style={[styles.detailNum, { color: COLORS.primary }]}>{folder.avg_factors}</Text>
                      <Text style={styles.detailLabel}>Avg Factors</Text>
                    </View>
                  </View>

                  {/* Top Factors from detail */}
                  {folderDetail?.top_factors?.length > 0 && (
                    <View style={styles.topFactors}>
                      <Text style={styles.topFactorsTitle}>Common Factors</Text>
                      <View style={styles.factorChips}>
                        {folderDetail.top_factors.map((tf: any, i: number) => (
                          <View key={i} style={[styles.factorChip, { borderColor: folder.color + '40' }]}>
                            <Text style={[styles.factorChipText, { color: folder.color }]}>
                              {tf.name} ({tf.count})
                            </Text>
                          </View>
                        ))}
                      </View>
                    </View>
                  )}

                  {/* Recent decisions */}
                  {folderDetail?.recent_decisions?.length > 0 && (
                    <View style={styles.recentSection}>
                      <Text style={styles.recentTitle}>Recent Decisions</Text>
                      {folderDetail.recent_decisions.map((d: any) => (
                        <TouchableOpacity
                          key={d.id}
                          style={styles.recentItem}
                          onPress={() => router.push(`/prr/${d.id}`)}
                        >
                          <Text style={styles.recentName} numberOfLines={1}>{d.title}</Text>
                          <View style={[
                            styles.recentStatus,
                            d.status === 'completed' ? styles.recentDone : styles.recentDraft,
                          ]}>
                            <Text style={styles.recentStatusText}>{d.status}</Text>
                          </View>
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}
                </View>
              )}
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, gap: 12 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: COLORS.white, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { flex: 1, fontSize: 22, fontWeight: '700', color: COLORS.textPrimary },
  scrollContent: { padding: 16, paddingTop: 0 },

  // Summary
  summaryCard: { backgroundColor: COLORS.white, borderRadius: 16, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: COLORS.border },
  summaryTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  summaryGrid: { flexDirection: 'row', gap: 8 },
  summaryItem: { flex: 1, alignItems: 'center', padding: 8, backgroundColor: COLORS.background, borderRadius: 10 },
  summaryNumber: { fontSize: 22, fontWeight: '700', color: COLORS.textPrimary },
  summaryLabel: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted, marginTop: 2, textTransform: 'uppercase' },
  mostActive: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: COLORS.border },
  mostActiveText: { fontSize: 12, fontWeight: '600', color: COLORS.primary },

  sectionTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 10 },

  // Folder cards
  folderCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  folderCardExpanded: { borderColor: 'rgba(142,36,170,0.2)' },
  folderRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  folderIconWrap: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  folderInfo: { flex: 1 },
  folderName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  folderCount: { fontSize: 11, color: COLORS.textMuted },
  rateContainer: { alignItems: 'flex-end', gap: 3, width: 70 },
  barBg: { width: 60, height: 5, borderRadius: 3, backgroundColor: COLORS.background, overflow: 'hidden' },
  barFill: { height: 5, borderRadius: 3 },
  rateText: { fontSize: 10, fontWeight: '700' },

  // Expanded
  expandedContent: { marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: COLORS.border },
  detailGrid: { flexDirection: 'row', gap: 6, marginBottom: 12 },
  detailItem: { flex: 1, alignItems: 'center', padding: 8, borderRadius: 8 },
  detailNum: { fontSize: 18, fontWeight: '700' },
  detailLabel: { fontSize: 9, fontWeight: '600', color: COLORS.textMuted, marginTop: 2, textTransform: 'uppercase' },

  topFactors: { marginBottom: 10 },
  topFactorsTitle: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 6 },
  factorChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 5 },
  factorChip: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, borderWidth: 1 },
  factorChipText: { fontSize: 10, fontWeight: '600' },

  recentSection: { marginTop: 4 },
  recentTitle: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 6 },
  recentItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  recentName: { flex: 1, fontSize: 13, color: COLORS.textPrimary, marginRight: 8 },
  recentStatus: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  recentDone: { backgroundColor: 'rgba(16,185,129,0.1)' },
  recentDraft: { backgroundColor: COLORS.background },
  recentStatusText: { fontSize: 10, fontWeight: '600', color: COLORS.textSecondary, textTransform: 'capitalize' },
});
