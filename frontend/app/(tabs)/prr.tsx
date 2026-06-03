import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
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
import { formatAbsolute } from '../../src/utils/datetime';
import { LIFE_AREAS, getLifeArea } from '../../src/constants/lifeAreas';
import ListFilterBar, { DateRangeKey, withinDateRange } from '../../src/components/ListFilterBar';

/**
 * Solution Box — unified home for ALL solution flows owned by the user:
 *   - Decider              (db.decisions)
 *   - Pros & Cons (normal) (db.pros_cons, current_step=1, no options/factors)
 *   - Pros & Cons (8-Step) (db.pros_cons, current_step>1 or has options/factors)
 *   - SWOT                 (db.swot)
 *
 * Backed by GET /api/solution-box (aggregator endpoint).
 * Each card deep-links to the correct wizard/detail page.
 */

type SolutionType = 'decider' | 'pros_cons' | 'swot' | 'test123' | 'solution_finder';
type SolutionStatus = 'draft' | 'in_progress' | 'completed';

interface SolutionItem {
  id: string;
  type: SolutionType;
  title: string;
  context: string;
  life_area?: string | null;
  status: SolutionStatus;
  current_step?: number | null;
  created_at: string | null;
  updated_at: string | null;
  route: string;
  linked_from_decision_id?: string | null;
  options_count?: number;
  _collection?: string;
  acting_as_context?: string | null;
  decision_type?: string | null;
  sub_area_name?: string | null;
  scenario_title?: string | null;
}

const TYPE_CHIPS: { key: 'all' | SolutionType; label: string; icon: string; color: string }[] = [
  { key: 'all',              label: 'All',         icon: 'apps',           color: COLORS.primary },
  { key: 'decider',          label: 'Decider',     icon: 'analytics',      color: '#6366F1' },
  { key: 'pros_cons',        label: 'Pros & Cons', icon: 'layers',         color: '#7C3AED' },
  { key: 'swot',             label: 'SWOT',        icon: 'grid',           color: '#F59E0B' },
  { key: 'test123',          label: 'Test123',     icon: 'flash',          color: '#EC4899' },
  { key: 'solution_finder',  label: 'Solution Finder', icon: 'compass',        color: '#0EA5E9' },
];

const TYPE_META: Record<SolutionType, { label: string; short: string; icon: string; color: string; bg: string }> = {
  decider:         { label: 'Decider',     short: 'Decider',  icon: 'analytics',       color: '#6366F1', bg: '#EEF2FF' },
  pros_cons:       { label: 'Pros & Cons', short: 'P&C',      icon: 'layers',          color: '#7C3AED', bg: '#F5F3FF' },
  swot:            { label: 'SWOT',        short: 'SWOT',     icon: 'grid',            color: '#F59E0B', bg: '#FFFBEB' },
  test123:         { label: 'Test123',     short: 'Test123',  icon: 'flash',           color: '#EC4899', bg: '#FDF2F8' },
  solution_finder: { label: 'Solution Finder', short: 'Finder',   icon: 'compass',         color: '#0EA5E9', bg: '#F0F9FF' },
};

const STATUS_META: Record<SolutionStatus, { label: string; color: string; bg: string }> = {
  draft:       { label: 'Draft',       color: '#6B7280', bg: '#F3F4F6' },
  in_progress: { label: 'In Progress', color: '#B45309', bg: '#FEF3C7' },
  completed:   { label: 'Completed',   color: '#047857', bg: '#D1FAE5' },
};

export default function SolutionBoxScreen() {
  const router = useRouter();
  const [items, setItems] = useState<SolutionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedLifeArea, setSelectedLifeArea] = useState<string | null>(null);
  const [selectedType, setSelectedType] = useState<'all' | SolutionType>('all');
  const [showFolders, setShowFolders] = useState(true);
  const [showNewMenu, setShowNewMenu] = useState(false);
  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SolutionItem | null>(null);
  const [cloneModalVisible, setCloneModalVisible] = useState(false);
  const [cloneTarget, setCloneTarget] = useState<any>(null);
  const [templateBrowserVisible, setTemplateBrowserVisible] = useState(false);
  const [userRole, setUserRole] = useState('user');
  const [folderCounts, setFolderCounts] = useState<Record<string, number>>({});

  // Extra client-side filters (search + date range + decision type) layered
  // on top of the server-side life-area & flow-type filtering.
  const [search, setSearch] = useState('');
  const [dateRange, setDateRange] = useState<DateRangeKey>('all');
  const [decisionType, setDecisionType] = useState<string | null>(null);

  const availableDecisionTypes = useMemo(
    () => Array.from(new Set(items.map((i) => i.decision_type).filter(Boolean))) as string[],
    [items],
  );

  const displayItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((it) => {
      if (q && !(`${it.title} ${it.context || ''} ${it.sub_area_name || ''} ${it.scenario_title || ''}`.toLowerCase().includes(q))) return false;
      if (decisionType && it.decision_type !== decisionType) return false;
      if (!withinDateRange(it.updated_at || it.created_at, dateRange)) return false;
      return true;
    });
  }, [items, search, decisionType, dateRange]);

  const fetchItems = async (
    lifeAreaFilter?: string | null,
    typeFilter?: 'all' | SolutionType,
  ) => {
    try {
      const params: string[] = [];
      if (lifeAreaFilter) params.push(`life_area=${encodeURIComponent(lifeAreaFilter)}`);
      if (typeFilter && typeFilter !== 'all') params.push(`type=${typeFilter}`);
      const qs = params.length ? `?${params.join('&')}` : '';
      const response = await api.get(`/solution-box${qs}`);
      setItems(response.data || []);
      // recompute life-area counts from the unfiltered fetch only
      if (!lifeAreaFilter && (!typeFilter || typeFilter === 'all')) {
        const counts: Record<string, number> = {};
        (response.data || []).forEach((it: SolutionItem) => {
          if (it.life_area) counts[it.life_area] = (counts[it.life_area] || 0) + 1;
        });
        setFolderCounts(counts);
      }
    } catch (err) {
      console.error('Solution Box fetch error:', err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserRole = async () => {
    try {
      const response = await api.get('/auth/me');
      setUserRole(response.data.role || 'user');
    } catch {
      // silent
    }
  };

  useFocusEffect(
    useCallback(() => {
      fetchItems(selectedLifeArea, selectedType);
      fetchUserRole();
    }, [selectedLifeArea, selectedType])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchItems(selectedLifeArea, selectedType);
    setRefreshing(false);
  };

  const handleFolderSelect = (folderId: string) => {
    if (selectedLifeArea === folderId) {
      setSelectedLifeArea(null);
      setShowFolders(true);
    } else {
      setSelectedLifeArea(folderId);
      setShowFolders(false);
    }
  };

  const handleTypeSelect = (typeKey: 'all' | SolutionType) => {
    setSelectedType(typeKey);
  };

  const handleItemPress = (it: SolutionItem) => {
    router.push(it.route as any);
  };

  const handleDeletePress = (it: SolutionItem) => {
    setDeleteTarget(it);
    setDeleteModalVisible(true);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      let endpoint = '';
      switch (deleteTarget.type) {
        case 'decider':         endpoint = `/decisions/${deleteTarget.id}`; break;
        case 'pros_cons':       endpoint = `/pros-cons/${deleteTarget.id}`; break;
        case 'swot':
          // SWOT-converted decisions live in db.decisions (reported with
          // _collection="decisions" by the backend). Raw SWOT analyses
          // live in db.swot. Use the collection hint to route correctly.
          endpoint = (deleteTarget as any)._collection === 'decisions'
            ? `/decisions/${deleteTarget.id}`
            : `/swot/${deleteTarget.id}`;
          break;
        case 'test123':         endpoint = `/test123/${deleteTarget.id}`; break;
        case 'solution_finder': endpoint = `/solution-finders/${deleteTarget.id}`; break;
        default:
          throw new Error(`Unsupported solution type: ${deleteTarget.type}`);
      }
      await api.delete(endpoint);
      setItems((prev) => prev.filter((d) => d.id !== deleteTarget.id));
    } catch (err) {
      console.error('Delete error:', err);
      showAlert('Delete Failed', 'Could not delete this item. Please try again.');
    } finally {
      setDeleteModalVisible(false);
      setDeleteTarget(null);
    }
  };

  const formatDate = (dateString?: string | null) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return '';
    return formatAbsolute(dateString);
  };

  const selectedFolderData = getLifeArea(selectedLifeArea);

  // ---------- Render: Life-area folder grid ----------
  const renderFolderGrid = () => (
    <View style={styles.foldersSection}>
      <Text style={styles.foldersTitle}>Life Area Folders</Text>
      <View style={styles.foldersGrid}>
        {LIFE_AREAS.map((folder) => {
          const count = folderCounts[folder.id] || 0;
          return (
            <TouchableOpacity
              key={folder.id}
              style={[
                styles.folderCard,
                { borderColor: folder.color + '40' },
                selectedLifeArea === folder.id && { borderColor: folder.color, backgroundColor: folder.color + '12' },
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

  // ---------- Render: Type filter chip bar ----------
  const renderTypeChips = () => (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.chipBar}
    >
      {TYPE_CHIPS.map((chip) => {
        const active = selectedType === chip.key;
        return (
          <TouchableOpacity
            key={chip.key}
            style={[
              styles.chip,
              active && { backgroundColor: chip.color, borderColor: chip.color },
            ]}
            onPress={() => handleTypeSelect(chip.key)}
            activeOpacity={0.8}
          >
            <Ionicons
              name={chip.icon as any}
              size={13}
              color={active ? '#FFF' : chip.color}
            />
            <Text style={[styles.chipText, active ? { color: '#FFF' } : { color: chip.color }]}>
              {chip.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );

  // ---------- Render: Single solution card ----------
  const renderItem = ({ item }: { item: SolutionItem }) => {
    const typeMeta = TYPE_META[item.type];
    const statusMeta = STATUS_META[item.status] || STATUS_META.draft;
    const laMeta = getLifeArea(item.life_area);
    return (
      <Card style={styles.itemCard}>
        <TouchableOpacity
          onPress={() => handleItemPress(item)}
          activeOpacity={0.7}
          style={styles.cardContent}
        >
          {/* Top row: type chip + status pill */}
          <View style={styles.cardTopRow}>
            <View style={[styles.typeChip, { backgroundColor: typeMeta.bg }]}>
              <Ionicons name={typeMeta.icon as any} size={11} color={typeMeta.color} />
              <Text style={[styles.typeChipText, { color: typeMeta.color }]}>{typeMeta.label}</Text>
            </View>
            <View style={[styles.statusPill, { backgroundColor: statusMeta.bg }]}>
              <View style={[styles.statusDot, { backgroundColor: statusMeta.color }]} />
              <Text style={[styles.statusPillText, { color: statusMeta.color }]}>
                {statusMeta.label}
                {item.type !== 'decider' && item.current_step ? ` · Step ${item.current_step}/8` : ''}
              </Text>
            </View>
          </View>

          <Text style={styles.cardTitle} numberOfLines={1}>{item.title}</Text>
          {!!item.context && (
            <Text style={styles.cardContext} numberOfLines={2}>{item.context}</Text>
          )}
          {(item.sub_area_name || item.scenario_title || item.acting_as_context) && (
            <Text style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 4 }} numberOfLines={1}>
              {[
                item.acting_as_context
                  ? item.acting_as_context.charAt(0) + item.acting_as_context.slice(1).toLowerCase()
                  : null,
                item.sub_area_name,
                item.scenario_title,
              ].filter(Boolean).join(' · ')}
            </Text>
          )}

          <View style={styles.cardFooter}>
            <View style={styles.cardFooterLeft}>
              {laMeta && (
                <View style={[styles.folderTag, { backgroundColor: laMeta.color + '15' }]}>
                  <Ionicons name={laMeta.icon as any} size={11} color={laMeta.color} />
                  <Text style={[styles.folderTagText, { color: laMeta.color }]}>{laMeta.name}</Text>
                </View>
              )}
              <Text style={styles.cardDate}>{formatDate(item.updated_at || item.created_at)}</Text>
            </View>
            {!!item.options_count && (
              <View style={styles.optionsCount}>
                <Ionicons name="list" size={13} color={COLORS.textSecondary} />
                <Text style={styles.optionsText}>{item.options_count}</Text>
              </View>
            )}
          </View>
        </TouchableOpacity>
        <View style={styles.cardActions}>
          {item.type === 'decider' && (
            <TouchableOpacity
              onPress={() => { setCloneTarget(item); setCloneModalVisible(true); }}
              style={styles.actionButton}
            >
              <Ionicons name="copy-outline" size={18} color={COLORS.primary} />
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={() => handleDeletePress(item)} style={styles.actionButton}>
            <Ionicons name="trash-outline" size={18} color={COLORS.error} />
          </TouchableOpacity>
        </View>
      </Card>
    );
  };

  // ---------- Render: Empty state ----------
  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Ionicons name="albums-outline" size={56} color={COLORS.textMuted} />
      <Text style={styles.emptyTitle}>
        {selectedLifeArea
          ? `No items in ${selectedFolderData?.name || 'this folder'}`
          : selectedType !== 'all'
            ? `No ${TYPE_META[selectedType as SolutionType]?.label || ''} items yet`
            : 'Your Solution Box is empty'}
      </Text>
      <Text style={styles.emptyText}>
        Start a new Decider, Pros &amp; Cons, 8-Step or SWOT analysis below.
      </Text>
      <TouchableOpacity
        style={styles.emptyButton}
        onPress={() => setShowNewMenu(true)}
      >
        <Ionicons name="add" size={18} color={COLORS.white} />
        <Text style={styles.emptyButtonText}>Start New</Text>
      </TouchableOpacity>
    </View>
  );

  const renderHeader = () => (
    <View>
      {showFolders && renderFolderGrid()}
      {selectedLifeArea && (
        <View style={styles.filterBar}>
          <TouchableOpacity
            style={styles.filterBackBtn}
            onPress={() => { setSelectedLifeArea(null); setShowFolders(true); }}
          >
            <Ionicons name="arrow-back" size={18} color={COLORS.primary} />
          </TouchableOpacity>
          {selectedFolderData && (
            <View style={[styles.filterBadge, { backgroundColor: selectedFolderData.color + '15' }]}>
              <Ionicons name={selectedFolderData.icon as any} size={14} color={selectedFolderData.color} />
              <Text style={[styles.filterBadgeText, { color: selectedFolderData.color }]}>
                {selectedFolderData.name}
              </Text>
            </View>
          )}
          <Text style={styles.filterCount}>
            {items.length} item{items.length !== 1 ? 's' : ''}
          </Text>
        </View>
      )}
      {renderTypeChips()}
      <ListFilterBar
        search={search} onSearch={setSearch}
        dateRange={dateRange} onDateRange={setDateRange}
        lifeArea={null} onLifeArea={() => {}}
        decisionType={decisionType} onDecisionType={setDecisionType}
        availableLifeAreas={[]}
        availableDecisionTypes={availableDecisionTypes}
        searchPlaceholder="Search your Solution Box…"
      />
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Solution Box</Text>
          <Text style={styles.subtitle}>All your decisions, analyses & frameworks</Text>
        </View>
        <View style={styles.headerActions}>
          <TouchableOpacity
            style={styles.templateButton}
            onPress={() => router.push('/(tabs)/shared' as any)}
          >
            <Ionicons name="share-social-outline" size={20} color={COLORS.primary} />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.templateButton}
            onPress={() => setTemplateBrowserVisible(true)}
          >
            <Ionicons name="bookmark-outline" size={20} color={COLORS.primary} />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.addButton}
            onPress={() => setShowNewMenu(true)}
          >
            <Ionicons name="add" size={24} color={COLORS.white} />
          </TouchableOpacity>
        </View>
      </View>

      <FlatList
        data={displayItems}
        renderItem={renderItem}
        keyExtractor={(item) => `${item.type}-${item.id}`}
        contentContainerStyle={[styles.list, { paddingBottom: 100 }]}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListHeaderComponent={renderHeader()}
        ListEmptyComponent={loading ? null : renderEmpty}
      />

      {/* New flow chooser modal */}
      <Modal
        visible={showNewMenu}
        transparent
        animationType="fade"
        onRequestClose={() => setShowNewMenu(false)}
      >
        <TouchableOpacity
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowNewMenu(false)}
        >
          <View style={styles.newMenuCard}>
            <Text style={styles.newMenuTitle}>Start a new…</Text>
            <Text style={styles.newMenuSubtitle}>Pick the framework that fits your problem</Text>

            <TouchableOpacity
              style={[styles.newMenuItem, { borderColor: TYPE_META.decider.color + '40' }]}
              onPress={() => { setShowNewMenu(false); router.push('/prr/new'); }}
            >
              <View style={[styles.newMenuIcon, { backgroundColor: TYPE_META.decider.bg }]}>
                <Ionicons name={TYPE_META.decider.icon as any} size={20} color={TYPE_META.decider.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.newMenuItemTitle}>Decider</Text>
                <Text style={styles.newMenuItemDesc}>Quick option-based decision with weighted factors</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.newMenuItem, { borderColor: TYPE_META.pros_cons.color + '40' }]}
              onPress={() => { setShowNewMenu(false); router.push('/tools/pros-cons-wizard?module=pros-cons'); }}
            >
              <View style={[styles.newMenuIcon, { backgroundColor: TYPE_META.pros_cons.bg }]}>
                <Ionicons name={TYPE_META.pros_cons.icon as any} size={20} color={TYPE_META.pros_cons.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.newMenuItemTitle}>Pros &amp; Cons</Text>
                <Text style={styles.newMenuItemDesc}>Guided 8-step framework with factors &amp; options</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.newMenuItem, { borderColor: TYPE_META.swot.color + '40' }]}
              onPress={() => { setShowNewMenu(false); router.push('/tools/swot'); }}
            >
              <View style={[styles.newMenuIcon, { backgroundColor: TYPE_META.swot.bg }]}>
                <Ionicons name={TYPE_META.swot.icon as any} size={20} color={TYPE_META.swot.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.newMenuItemTitle}>SWOT</Text>
                <Text style={styles.newMenuItemDesc}>Strengths · Weaknesses · Opportunities · Threats</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.newMenuItem, { borderColor: TYPE_META.test123.color + '40' }]}
              onPress={() => { setShowNewMenu(false); router.push('/test123/new' as any); }}
            >
              <View style={[styles.newMenuIcon, { backgroundColor: TYPE_META.test123.bg }]}>
                <Ionicons name={TYPE_META.test123.icon as any} size={20} color={TYPE_META.test123.color} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.newMenuItemTitle}>Test123 · Quick Decision</Text>
                <Text style={styles.newMenuItemDesc}>3-step gut check: situation → worst case → real needs</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.newMenuCancel}
              onPress={() => setShowNewMenu(false)}
            >
              <Text style={styles.newMenuCancelText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        visible={deleteModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setDeleteModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Ionicons name="warning" size={48} color={COLORS.error} />
            <Text style={styles.modalTitle}>Delete this item?</Text>
            <Text style={styles.modalText}>
              {deleteTarget ? `"${deleteTarget.title}" will be permanently removed.` : 'This action cannot be undone.'}
            </Text>
            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.cancelButton} onPress={() => setDeleteModalVisible(false)}>
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
          onCloneSuccess={(newId) => { fetchItems(selectedLifeArea, selectedType); router.push(`/prr/${newId}`); }}
          onTemplateSuccess={() => showAlert('Template Saved', 'Decision saved as template.')}
        />
      )}

      <TemplateBrowserModal
        visible={templateBrowserVisible}
        onClose={() => setTemplateBrowserVisible(false)}
        onUseTemplate={(newId) => { fetchItems(selectedLifeArea, selectedType); router.push(`/prr/${newId}`); }}
        userRole={userRole}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start',
    padding: 16, paddingTop: 8,
  },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  templateButton: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: 'rgba(142,36,170,0.1)', justifyContent: 'center', alignItems: 'center',
  },
  title: { fontSize: 26, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
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

  // Filter bar
  filterBar: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 8, marginBottom: 4,
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

  // Type filter chips
  chipBar: { flexDirection: 'row', gap: 8, paddingBottom: 10, paddingTop: 2 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 16, borderWidth: 1.5,
    backgroundColor: COLORS.white,
    borderColor: COLORS.border,
  },
  chipText: { fontSize: 12, fontWeight: '600' },

  // Item Cards
  itemCard: { marginBottom: 10, flexDirection: 'row', alignItems: 'flex-start' },
  cardContent: { flex: 1 },
  cardTopRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6, gap: 6 },
  typeChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10,
  },
  typeChipText: { fontSize: 10, fontWeight: '700' },
  statusPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10,
  },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusPillText: { fontSize: 10, fontWeight: '700' },
  cardTitle: { fontSize: 16, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 3 },
  cardContext: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18, marginBottom: 8 },
  cardFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cardFooterLeft: { flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1, flexWrap: 'wrap' },
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
  emptyTitle: { fontSize: 18, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12, textAlign: 'center', paddingHorizontal: 16 },
  emptyText: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', marginTop: 6, marginBottom: 20, paddingHorizontal: 24 },
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

  // New menu modal
  newMenuCard: {
    backgroundColor: COLORS.white, borderRadius: 16,
    padding: 20, width: '100%', maxWidth: 400,
  },
  newMenuTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 2 },
  newMenuSubtitle: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 14 },
  newMenuItem: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    padding: 12, borderRadius: 12, borderWidth: 1.5,
    marginBottom: 10, backgroundColor: COLORS.white,
  },
  newMenuIcon: {
    width: 40, height: 40, borderRadius: 20,
    justifyContent: 'center', alignItems: 'center',
  },
  newMenuItemTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  newMenuItemDesc: { fontSize: 11, color: COLORS.textSecondary, marginTop: 2 },
  newMenuCancel: {
    paddingVertical: 12, alignItems: 'center', marginTop: 4,
  },
  newMenuCancelText: { fontSize: 14, fontWeight: '600', color: COLORS.textSecondary },
});
