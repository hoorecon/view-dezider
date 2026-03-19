import React, { useEffect, useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
  Platform,
  Modal,
  ScrollView,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import CloneTemplateModal from '../../src/components/CloneTemplateModal';
import TemplateBrowserModal from '../../src/components/TemplateBrowserModal';
import api from '../../src/utils/api';

interface Decision {
  id: string;
  title: string;
  context: string;
  status: string;
  options: any[];
  folder: string;
  created_at: string;
  chosen_option_id?: string;
}

interface Folder {
  id: string;
  name: string;
  icon: string;
  color: string;
}

const FOLDER_DATA: Folder[] = [
  { id: 'holistic_health', name: 'Holistic Health', icon: 'fitness', color: '#10B981' },
  { id: 'knowledge_skills', name: 'Knowledge & Skills', icon: 'book', color: '#3B82F6' },
  { id: 'relationships', name: 'Relationships', icon: 'heart', color: '#EC4899' },
  { id: 'finance', name: 'Finance', icon: 'cash', color: '#F59E0B' },
  { id: 'assets', name: 'Assets', icon: 'home', color: '#8B5CF6' },
  { id: 'career', name: 'Career', icon: 'briefcase', color: '#6366F1' },
  { id: 'hobbies_entertainment', name: 'Hobbies & Entertainment', icon: 'game-controller', color: '#14B8A6' },
  { id: 'social_image', name: 'Social Image & Influence', icon: 'star', color: '#F97316' },
  { id: 'social_contributions', name: 'Social Contributions', icon: 'people', color: '#06B6D4' },
  { id: 'spirituality_religion', name: 'Spirituality & Religion', icon: 'leaf', color: '#A855F7' },
];

export default function PRRScreen() {
  const router = useRouter();
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null);
  const [showFolders, setShowFolders] = useState(true);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [cloneModalVisible, setCloneModalVisible] = useState(false);
  const [cloneTarget, setCloneTarget] = useState<Decision | null>(null);
  const [templateBrowserVisible, setTemplateBrowserVisible] = useState(false);
  const [userRole, setUserRole] = useState('user');
  const [folderCounts, setFolderCounts] = useState<Record<string, number>>({});

  const fetchDecisions = async (folder?: string | null) => {
    try {
      const url = folder ? `/decisions?folder=${folder}` : '/decisions';
      const response = await api.get(url);
      setDecisions(response.data);
      // Calculate folder counts if fetching all
      if (!folder) {
        const counts: Record<string, number> = {};
        response.data.forEach((d: Decision) => {
          const f = d.folder || 'uncategorized';
          counts[f] = (counts[f] || 0) + 1;
        });
        setFolderCounts(counts);
      }
    } catch (error) {
      console.error('Error fetching decisions:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserRole = async () => {
    try {
      const response = await api.get('/auth/me');
      setUserRole(response.data.role || 'user');
    } catch (error) {
      console.error('Error fetching user role:', error);
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchDecisions(selectedFolder);
      fetchUserRole();
    }, [selectedFolder])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchDecisions(selectedFolder);
    setRefreshing(false);
  };

  const handleFolderSelect = (folderId: string) => {
    if (selectedFolder === folderId) {
      setSelectedFolder(null);
      setShowFolders(true);
      fetchDecisions(null);
    } else {
      setSelectedFolder(folderId);
      setShowFolders(false);
      fetchDecisions(folderId);
    }
  };

  const handleDeletePress = (id: string) => {
    setDeleteTargetId(id);
    setDeleteModalVisible(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTargetId) return;
    try {
      await api.delete(`/decisions/${deleteTargetId}`);
      setDecisions((prev) => prev.filter((d) => d.id !== deleteTargetId));
    } catch (error) {
      console.error('Delete error:', error);
    } finally {
      setDeleteModalVisible(false);
      setDeleteTargetId(null);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteModalVisible(false);
    setDeleteTargetId(null);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return COLORS.success;
      case 'in_progress': return COLORS.warning;
      default: return COLORS.textMuted;
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'completed': return 'Completed';
      case 'in_progress': return 'In Progress';
      default: return 'Draft';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const selectedFolderData = FOLDER_DATA.find(f => f.id === selectedFolder);

  const renderFolderGrid = () => (
    <View style={styles.foldersSection}>
      <Text style={styles.foldersTitle}>Life Area Folders</Text>
      <View style={styles.foldersGrid}>
        {FOLDER_DATA.map((folder) => {
          const count = folderCounts[folder.id] || 0;
          return (
            <TouchableOpacity
              key={folder.id}
              style={[
                styles.folderCard,
                { borderColor: folder.color + '40' },
                selectedFolder === folder.id && { borderColor: folder.color, backgroundColor: folder.color + '12' },
              ]}
              onPress={() => handleFolderSelect(folder.id)}
              activeOpacity={0.7}
            >
              <View style={[styles.folderIconWrap, { backgroundColor: folder.color + '18' }]}>
                <Ionicons name={folder.icon as any} size={20} color={folder.color} />
              </View>
              <Text style={styles.folderName} numberOfLines={2}>{folder.name}</Text>
              {count > 0 && (
                <View style={[styles.folderBadge, { backgroundColor: folder.color }]}>
                  <Text style={styles.folderBadgeText}>{count}</Text>
                </View>
              )}
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );

  const renderDecision = ({ item }: { item: Decision }) => {
    const folderData = FOLDER_DATA.find(f => f.id === item.folder);
    return (
      <Card style={styles.decisionCard}>
        <TouchableOpacity
          onPress={() => router.push(`/prr/${item.id}`)}
          activeOpacity={0.7}
          style={styles.cardContent}
        >
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle} numberOfLines={1}>{item.title}</Text>
            <View style={styles.statusContainer}>
              <View style={[styles.statusDot, { backgroundColor: getStatusColor(item.status) }]} />
              <Text style={styles.statusText}>{getStatusLabel(item.status)}</Text>
            </View>
          </View>
          <Text style={styles.cardContext} numberOfLines={2}>{item.context}</Text>
          <View style={styles.cardFooter}>
            <View style={styles.cardFooterLeft}>
              {folderData && (
                <View style={[styles.folderTag, { backgroundColor: folderData.color + '15' }]}>
                  <Ionicons name={folderData.icon as any} size={11} color={folderData.color} />
                  <Text style={[styles.folderTagText, { color: folderData.color }]}>{folderData.name}</Text>
                </View>
              )}
              <Text style={styles.cardDate}>{formatDate(item.created_at)}</Text>
            </View>
            <View style={styles.optionsCount}>
              <Ionicons name="list" size={14} color={COLORS.textSecondary} />
              <Text style={styles.optionsText}>{item.options?.length || 0}</Text>
            </View>
          </View>
        </TouchableOpacity>
        <View style={styles.cardActions}>
          <TouchableOpacity
            onPress={() => { setCloneTarget(item); setCloneModalVisible(true); }}
            style={styles.actionButton}
          >
            <Ionicons name="copy-outline" size={18} color={COLORS.primary} />
          </TouchableOpacity>
          <TouchableOpacity onPress={() => handleDeletePress(item.id)} style={styles.actionButton}>
            <Ionicons name="trash-outline" size={18} color={COLORS.error} />
          </TouchableOpacity>
        </View>
      </Card>
    );
  };

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Ionicons name="analytics-outline" size={56} color={COLORS.textMuted} />
      <Text style={styles.emptyTitle}>
        {selectedFolder ? `No decisions in ${selectedFolderData?.name || 'this folder'}` : 'No PRR Decisions Yet'}
      </Text>
      <Text style={styles.emptyText}>
        {selectedFolder ? 'Create a new decision in this life area' : 'Start making better decisions with the PRR system'}
      </Text>
      <TouchableOpacity
        style={styles.emptyButton}
        onPress={() => router.push('/prr/new')}
      >
        <Ionicons name="add" size={18} color={COLORS.white} />
        <Text style={styles.emptyButtonText}>Create Decision</Text>
      </TouchableOpacity>
    </View>
  );

  const renderHeader = () => (
    <>
      {showFolders && renderFolderGrid()}
      {selectedFolder && (
        <View style={styles.filterBar}>
          <TouchableOpacity
            style={styles.filterBackBtn}
            onPress={() => { setSelectedFolder(null); setShowFolders(true); fetchDecisions(null); }}
          >
            <Ionicons name="arrow-back" size={18} color={COLORS.primary} />
          </TouchableOpacity>
          <View style={[styles.filterBadge, { backgroundColor: selectedFolderData?.color + '15' }]}>
            <Ionicons name={selectedFolderData?.icon as any} size={14} color={selectedFolderData?.color || COLORS.primary} />
            <Text style={[styles.filterBadgeText, { color: selectedFolderData?.color }]}>{selectedFolderData?.name}</Text>
          </View>
          <Text style={styles.filterCount}>{decisions.length} decision{decisions.length !== 1 ? 's' : ''}</Text>
        </View>
      )}
    </>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <Text style={styles.title}>Decision Box</Text>
        <View style={styles.headerActions}>
          <TouchableOpacity
            style={styles.templateButton}
            onPress={() => setTemplateBrowserVisible(true)}
          >
            <Ionicons name="bookmark-outline" size={20} color={COLORS.primary} />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.addButton}
            onPress={() => router.push('/prr/new')}
          >
            <Ionicons name="add" size={24} color={COLORS.white} />
          </TouchableOpacity>
        </View>
      </View>

      <FlatList
        data={decisions}
        renderItem={renderDecision}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={loading ? null : renderEmpty}
      />

      {/* Delete Confirmation Modal */}
      <Modal visible={deleteModalVisible} transparent animationType="fade" onRequestClose={handleDeleteCancel}>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Ionicons name="warning" size={48} color={COLORS.error} />
            <Text style={styles.modalTitle}>Delete Decision?</Text>
            <Text style={styles.modalText}>This action cannot be undone.</Text>
            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.cancelButton} onPress={handleDeleteCancel}>
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.confirmDeleteButton} onPress={handleDeleteConfirm}>
                <Text style={styles.confirmDeleteButtonText}>Delete</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {cloneTarget && (
        <CloneTemplateModal
          visible={cloneModalVisible}
          onClose={() => { setCloneModalVisible(false); setCloneTarget(null); }}
          decision={cloneTarget}
          onCloneSuccess={(newId) => { fetchDecisions(selectedFolder); router.push(`/prr/${newId}`); }}
          onTemplateSuccess={() => Alert.alert('Template Saved', 'Decision saved as template.')}
        />
      )}

      <TemplateBrowserModal
        visible={templateBrowserVisible}
        onClose={() => setTemplateBrowserVisible(false)}
        onUseTemplate={(newId) => { fetchDecisions(selectedFolder); router.push(`/prr/${newId}`); }}
        userRole={userRole}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, paddingTop: 8,
  },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  templateButton: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: 'rgba(142,36,170,0.1)', justifyContent: 'center', alignItems: 'center',
  },
  title: { fontSize: 28, fontWeight: '700', color: COLORS.textPrimary },
  addButton: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: COLORS.primary, justifyContent: 'center', alignItems: 'center',
  },
  list: { padding: 16, paddingTop: 0, flexGrow: 1 },

  // Folder Grid
  foldersSection: { marginBottom: 16 },
  foldersTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 10, paddingHorizontal: 2 },
  foldersGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  folderCard: {
    width: '31%', flexBasis: '31%',
    backgroundColor: COLORS.white, borderRadius: 12, padding: 10,
    alignItems: 'center', borderWidth: 1.5, borderColor: COLORS.border,
    minHeight: 88,
  },
  folderIconWrap: {
    width: 36, height: 36, borderRadius: 18,
    justifyContent: 'center', alignItems: 'center', marginBottom: 6,
  },
  folderName: { fontSize: 10, fontWeight: '600', color: COLORS.textPrimary, textAlign: 'center', lineHeight: 13 },
  folderBadge: {
    position: 'absolute', top: 4, right: 4,
    width: 18, height: 18, borderRadius: 9,
    justifyContent: 'center', alignItems: 'center',
  },
  folderBadgeText: { fontSize: 9, fontWeight: '700', color: '#FFF' },

  // Filter bar (when folder is selected)
  filterBar: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 8, marginBottom: 8,
  },
  filterBackBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: 'rgba(142,36,170,0.08)', justifyContent: 'center', alignItems: 'center',
  },
  filterBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14,
  },
  filterBadgeText: { fontSize: 12, fontWeight: '600' },
  filterCount: { fontSize: 12, color: COLORS.textMuted, marginLeft: 'auto' },

  // Decision Cards
  decisionCard: { marginBottom: 10, flexDirection: 'row', alignItems: 'flex-start' },
  cardContent: { flex: 1 },
  cardHeader: { marginBottom: 6 },
  cardTitle: { fontSize: 16, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 3 },
  statusContainer: { flexDirection: 'row', alignItems: 'center', marginTop: 2 },
  statusDot: { width: 7, height: 7, borderRadius: 4, marginRight: 5 },
  statusText: { fontSize: 11, color: COLORS.textSecondary },
  cardContext: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18, marginBottom: 8 },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardFooterLeft: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 },
  folderTag: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8,
  },
  folderTagText: { fontSize: 9, fontWeight: '600' },
  cardDate: { fontSize: 11, color: COLORS.textMuted },
  optionsCount: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  optionsText: { fontSize: 11, color: COLORS.textSecondary },
  cardActions: { flexDirection: 'column', alignItems: 'center', gap: 2, marginLeft: 4 },
  actionButton: { padding: 6 },

  // Empty
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 48 },
  emptyTitle: { fontSize: 18, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12 },
  emptyText: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', marginTop: 6, marginBottom: 20 },
  emptyButton: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: COLORS.primary, paddingVertical: 10, paddingHorizontal: 18, borderRadius: 12,
  },
  emptyButtonText: { fontSize: 15, fontWeight: '600', color: COLORS.white },

  // Modals
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 24 },
  modalContent: { backgroundColor: COLORS.white, borderRadius: 16, padding: 24, alignItems: 'center', maxWidth: 320, width: '100%' },
  modalTitle: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary, marginTop: 16, marginBottom: 8 },
  modalText: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 24, lineHeight: 20 },
  modalButtons: { flexDirection: 'row', gap: 12, width: '100%' },
  cancelButton: { flex: 1, paddingVertical: 12, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  cancelButtonText: { fontSize: 16, fontWeight: '600', color: COLORS.textSecondary },
  confirmDeleteButton: { flex: 1, paddingVertical: 12, borderRadius: 8, backgroundColor: COLORS.error, alignItems: 'center' },
  confirmDeleteButtonText: { fontSize: 16, fontWeight: '600', color: COLORS.white },
});
