/**
 * Admin · Dashboard Sections editor
 *
 * - Rename section titles (text only — numbering is auto on the dashboard)
 * - Drag to REORDER sections
 * - Move modules (tiles) BETWEEN sections + reorder within a section
 *
 * Persists to PUT /api/admin/dashboard-layout. Visibility stays governed by ACM.
 */
import React, { useCallback, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput, Modal,
  ActivityIndicator, Alert, ScrollView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import DraggableFlatList, { ScaleDecorator } from 'react-native-draggable-flatlist';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import api from '../../src/utils/api';
import { TILE_META, DEFAULT_LAYOUT, LayoutSection } from '../../src/config/dashboardTiles';

const C = {
  bg: '#F8FAFC', card: '#FFFFFF', border: '#E2E8F0',
  text: '#0F172A', muted: '#64748B', accent: '#0D9488', danger: '#DC2626',
  chipBg: '#F1F5F9',
};

export default function DashboardLayoutScreen() {
  const router = useRouter();
  const [sections, setSections] = useState<LayoutSection[]>([]);
  const [tileTitles, setTileTitles] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<LayoutSection | null>(null);
  const [moveTile, setMoveTile] = useState<{ tile: string; fromId: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/dashboard-layout');
      const secs = Array.isArray(r.data?.sections) && r.data.sections.length
        ? r.data.sections : DEFAULT_LAYOUT;
      setSections(secs.map((s: any) => ({ ...s, tiles: [...(s.tiles || [])] })));
      setTileTitles(r.data?.tile_titles && typeof r.data.tile_titles === 'object' ? r.data.tile_titles : {});
    } catch {
      setSections(DEFAULT_LAYOUT.map((s) => ({ ...s, tiles: [...s.tiles] })));
      setTileTitles({});
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const save = async () => {
    setSaving(true);
    try {
      await api.put('/admin/dashboard-layout', { sections, tile_titles: tileTitles });
      Alert.alert('Saved', 'Dashboard layout updated. Module renames are mirrored into the ACM matrix. Users see changes on next refresh.');
    } catch (e: any) {
      Alert.alert('Save failed', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const resetDefaults = () => {
    Alert.alert('Reset to defaults?', 'This restores the original section names, order, tile placement and module names.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Reset', style: 'destructive', onPress: async () => {
          try {
            const r = await api.post('/admin/dashboard-layout/reset');
            setSections((r.data?.sections || DEFAULT_LAYOUT).map((s: any) => ({ ...s, tiles: [...(s.tiles || [])] })));
            setTileTitles({});
            Alert.alert('Reset', 'Defaults restored. Tap Save to keep, or leave to revert.');
          } catch {
            Alert.alert('Reset failed', 'Please try again.');
          }
        },
      },
    ]);
  };

  // ---- section-level mutations ----
  const renameSection = (id: string, name: string) =>
    setSections((prev) => prev.map((s) => (s.id === id ? { ...s, name } : s)));
  const setEmoji = (id: string, emoji: string) =>
    setSections((prev) => prev.map((s) => (s.id === id ? { ...s, emoji } : s)));

  // ---- module(tile)-level rename ----
  // Effective display name = custom override, else the registry default.
  const tileLabel = (id: string) => tileTitles[id] ?? TILE_META[id]?.title ?? id;
  const renameTile = (id: string, name: string) =>
    setTileTitles((prev) => {
      const next = { ...prev };
      // Empty / unchanged-to-default → drop the override.
      if (!name.trim() || name.trim() === (TILE_META[id]?.title ?? id)) delete next[id];
      else next[id] = name;
      return next;
    });

  const reorderTilesInSection = (id: string, tiles: string[]) =>
    setSections((prev) => prev.map((s) => (s.id === id ? { ...s, tiles } : s)));

  const doMoveTile = (tile: string, fromId: string, toId: string) => {
    if (fromId === toId) { setMoveTile(null); return; }
    setSections((prev) => prev.map((s) => {
      if (s.id === fromId) return { ...s, tiles: s.tiles.filter((t) => t !== tile) };
      if (s.id === toId) return { ...s, tiles: [...s.tiles, tile] };
      return s;
    }));
    // keep editing modal in sync if open
    setEditing((e) => (e && e.id === fromId ? { ...e, tiles: e.tiles.filter((t) => t !== tile) } : e));
    setMoveTile(null);
  };

  // keep the editing modal's tiles synced from the canonical sections
  const editingLive = editing ? sections.find((s) => s.id === editing.id) || editing : null;

  if (loading) {
    return (
      <SafeAreaView style={styles.center}><ActivityIndicator size="large" color={C.accent} /></SafeAreaView>
    );
  }

  const renderSectionRow = ({ item, drag, isActive }: any) => (
    <ScaleDecorator>
      <View style={[styles.secRow, isActive && { opacity: 0.9, borderColor: C.accent }]}>
        <TouchableOpacity onLongPress={drag} delayLongPress={150} style={styles.dragHandle} accessibilityLabel="Drag to reorder section">
          <Ionicons name="reorder-three" size={24} color={C.muted} />
        </TouchableOpacity>
        <TextInput
          value={item.emoji}
          onChangeText={(t) => setEmoji(item.id, t)}
          style={styles.emojiInput}
          maxLength={4}
          placeholder="🏷️"
        />
        <View style={{ flex: 1 }}>
          <TextInput
            value={item.name}
            onChangeText={(t) => renameSection(item.id, t)}
            style={styles.nameInput}
            placeholder="Section title"
          />
          <Text style={styles.secMeta}>{item.tiles.length} module{item.tiles.length === 1 ? '' : 's'}</Text>
        </View>
        <TouchableOpacity style={styles.tilesBtn} onPress={() => setEditing(item)}>
          <Ionicons name="grid-outline" size={16} color={C.accent} />
          <Text style={styles.tilesBtnText}>Modules</Text>
        </TouchableOpacity>
      </View>
    </ScaleDecorator>
  );

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: C.bg }}>
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.hBtn}>
            <Ionicons name="arrow-back" size={22} color={C.text} />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={styles.hTitle}>Dashboard Sections</Text>
            <Text style={styles.hSub}>Rename · drag to reorder · move modules</Text>
          </View>
          <TouchableOpacity onPress={resetDefaults} style={styles.hBtn}>
            <Ionicons name="refresh" size={20} color={C.muted} />
          </TouchableOpacity>
          <TouchableOpacity onPress={save} disabled={saving} style={[styles.saveBtn, saving && { opacity: 0.6 }]}>
            {saving ? <ActivityIndicator size="small" color="#FFF" /> : <Text style={styles.saveText}>Save</Text>}
          </TouchableOpacity>
        </View>

        <View style={styles.tipRow}>
          <Ionicons name="information-circle-outline" size={16} color={C.muted} />
          <Text style={styles.tip}>Numbers (1, 2, 3…) are auto-applied to visible sections — edit titles only.</Text>
        </View>

        <DraggableFlatList
          data={sections}
          keyExtractor={(s) => s.id}
          onDragEnd={({ data }) => setSections(data)}
          renderItem={renderSectionRow}
          contentContainerStyle={{ padding: 16, paddingBottom: 48 }}
        />

        {/* ---- Section modules modal ---- */}
        <Modal visible={!!editing} animationType="slide" transparent onRequestClose={() => setEditing(null)}>
          <View style={styles.modalWrap}>
            <View style={styles.modalCard}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle} numberOfLines={1}>
                  {editingLive?.emoji} {editingLive?.name} · Modules
                </Text>
                <TouchableOpacity onPress={() => setEditing(null)}>
                  <Ionicons name="close" size={24} color={C.text} />
                </TouchableOpacity>
              </View>
              <Text style={styles.modalHint}>Rename a module (synced to the ACM matrix) · drag to reorder · tap “Move” to send it to another section.</Text>
              <View style={{ flex: 1 }}>
                <DraggableFlatList
                  data={editingLive?.tiles || []}
                  keyExtractor={(t) => t}
                  onDragEnd={({ data }) => editingLive && reorderTilesInSection(editingLive.id, data)}
                  renderItem={({ item, drag, isActive }: any) => (
                    <ScaleDecorator>
                      <View style={[styles.tileRow, isActive && { borderColor: C.accent }]}>
                        <TouchableOpacity onLongPress={drag} delayLongPress={150} style={styles.dragHandle}>
                          <Ionicons name="reorder-two" size={22} color={C.muted} />
                        </TouchableOpacity>
                        <TextInput
                          value={tileLabel(item)}
                          onChangeText={(t) => renameTile(item, t)}
                          style={styles.tileNameInput}
                          placeholder="Module name"
                        />
                        <TouchableOpacity
                          style={styles.moveBtn}
                          onPress={() => editingLive && setMoveTile({ tile: item, fromId: editingLive.id })}>
                          <Ionicons name="swap-horizontal" size={15} color={C.accent} />
                          <Text style={styles.moveText}>Move</Text>
                        </TouchableOpacity>
                      </View>
                    </ScaleDecorator>
                  )}
                  ListEmptyComponent={<Text style={styles.empty}>No modules. Move some here from other sections.</Text>}
                  contentContainerStyle={{ paddingVertical: 8 }}
                />
              </View>
              <TouchableOpacity style={styles.doneBtn} onPress={() => setEditing(null)}>
                <Text style={styles.doneText}>Done</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>

        {/* ---- Move-to-section picker ---- */}
        <Modal visible={!!moveTile} animationType="fade" transparent onRequestClose={() => setMoveTile(null)}>
          <TouchableOpacity style={styles.pickerWrap} activeOpacity={1} onPress={() => setMoveTile(null)}>
            <View style={styles.pickerCard}>
              <Text style={styles.pickerTitle}>Move “{moveTile ? tileLabel(moveTile.tile) : ''}” to…</Text>
              <ScrollView style={{ maxHeight: 360 }}>
                {sections.filter((s) => s.id !== moveTile?.fromId).map((s) => (
                  <TouchableOpacity key={s.id} style={styles.pickerRow}
                    onPress={() => moveTile && doMoveTile(moveTile.tile, moveTile.fromId, s.id)}>
                    <Text style={styles.pickerEmoji}>{s.emoji}</Text>
                    <Text style={styles.pickerName}>{s.name}</Text>
                    <Ionicons name="arrow-forward" size={16} color={C.accent} />
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          </TouchableOpacity>
        </Modal>
      </SafeAreaView>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: C.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 12, paddingVertical: 10,
    backgroundColor: C.card, borderBottomWidth: 1, borderBottomColor: C.border,
  },
  hBtn: { padding: 6 },
  hTitle: { fontSize: 17, fontWeight: '800', color: C.text },
  hSub: { fontSize: 11, color: C.muted, marginTop: 1 },
  saveBtn: { backgroundColor: C.accent, paddingHorizontal: 18, paddingVertical: 9, borderRadius: 10, minWidth: 64, alignItems: 'center' },
  saveText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
  tipRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingTop: 10 },
  tip: { fontSize: 12, color: C.muted, flex: 1 },
  secRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border,
    padding: 10, marginBottom: 10,
  },
  dragHandle: { padding: 4 },
  emojiInput: {
    width: 40, height: 40, textAlign: 'center', fontSize: 18,
    backgroundColor: C.chipBg, borderRadius: 8,
    ...(Platform.OS === 'web' ? ({ outlineStyle: 'none' } as any) : {}),
  },
  nameInput: {
    fontSize: 15, fontWeight: '700', color: C.text, paddingVertical: 2,
    ...(Platform.OS === 'web' ? ({ outlineStyle: 'none' } as any) : {}),
  },
  secMeta: { fontSize: 11, color: C.muted, marginTop: 1 },
  tilesBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: C.chipBg, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 8 },
  tilesBtnText: { fontSize: 12, fontWeight: '700', color: C.accent },
  // modal
  modalWrap: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalCard: { backgroundColor: C.bg, borderTopLeftRadius: 18, borderTopRightRadius: 18, height: '82%', padding: 16 },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  modalTitle: { fontSize: 16, fontWeight: '800', color: C.text, flex: 1, marginRight: 12 },
  modalHint: { fontSize: 12, color: C.muted, marginTop: 4, marginBottom: 8 },
  tileRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: C.card, borderRadius: 10, borderWidth: 1, borderColor: C.border,
    paddingHorizontal: 10, paddingVertical: 12, marginBottom: 8,
  },
  tileName: { flex: 1, fontSize: 14, fontWeight: '600', color: C.text },
  tileNameInput: {
    flex: 1, fontSize: 14, fontWeight: '600', color: C.text, paddingVertical: 2,
    ...(Platform.OS === 'web' ? ({ outlineStyle: 'none' } as any) : {}),
  },
  moveBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: C.chipBg, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  moveText: { fontSize: 12, fontWeight: '700', color: C.accent },
  empty: { textAlign: 'center', color: C.muted, fontSize: 13, paddingVertical: 24 },
  doneBtn: { backgroundColor: C.accent, borderRadius: 12, paddingVertical: 14, alignItems: 'center', marginTop: 8 },
  doneText: { color: '#FFF', fontWeight: '800', fontSize: 15 },
  // picker
  pickerWrap: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'center', padding: 28 },
  pickerCard: { backgroundColor: C.card, borderRadius: 16, padding: 16, maxWidth: 460, width: '100%', alignSelf: 'center' },
  pickerTitle: { fontSize: 15, fontWeight: '800', color: C.text, marginBottom: 10 },
  pickerRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: C.border },
  pickerEmoji: { fontSize: 18 },
  pickerName: { flex: 1, fontSize: 14, fontWeight: '600', color: C.text },
});
