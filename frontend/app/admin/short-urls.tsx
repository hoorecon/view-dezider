import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, Modal, Switch, RefreshControl, Platform, Share,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

/**
 * /admin/short-urls — CRUD for shareable short links.
 * Every decision template and store app can have (or auto-generate) a short
 * slug so it's shareable on WhatsApp/social with an admin-editable message.
 */

type Row = {
  slug: string;
  title: string;
  target_href: string;
  share_message: string;
  kind: 'template' | 'app' | 'custom';
  target_id?: string | null;
  active: boolean;
  updated_at?: string;
};

const KIND_META: Record<Row['kind'], { label: string; color: string; icon: any }> = {
  template: { label: 'Template', color: '#4F46E5', icon: 'document-text' },
  app:      { label: 'Store App', color: '#EC4899', icon: 'cube' },
  custom:   { label: 'Custom',    color: '#0EA5E9', icon: 'link' },
};

export default function AdminShortUrlsScreen() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState<Partial<Row> | null>(null);
  const [creating, setCreating] = useState(false);
  const [seeding, setSeeding] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get('/admin/short-urls');
      setRows(r.data?.items || []);
    } catch { setRows([]); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = rows.filter((r) => {
    const needle = q.trim().toLowerCase();
    if (!needle) return true;
    return (r.slug + ' ' + r.title + ' ' + r.target_href).toLowerCase().includes(needle);
  });

  const publicBase = (typeof window !== 'undefined' && window.location?.origin) || 'https://jelcos.ai';

  const shareLink = async (r: Row) => {
    const url = `${publicBase}/s/${r.slug}`;
    const message = (r.share_message || r.title || '') + '\n' + url;
    try {
      if (Platform.OS !== 'web') {
        await Share.share({ message, url, title: r.title });
      } else if ((navigator as any).share) {
        await (navigator as any).share({ title: r.title, text: r.share_message, url });
      } else {
        await Clipboard.setStringAsync(message);
        showAlert('Copied', 'Share message + link copied to clipboard.');
      }
    } catch { /* silent — user cancelled */ }
  };

  const copyUrl = async (r: Row) => {
    await Clipboard.setStringAsync(`${publicBase}/s/${r.slug}`);
    showAlert('Copied', `${publicBase}/s/${r.slug}`);
  };

  const save = async () => {
    if (!editing) return;
    try {
      if (creating) {
        await api.post('/admin/short-urls', editing);
      } else {
        await api.put(`/admin/short-urls/${editing.slug}`, editing);
      }
      setEditing(null); setCreating(false);
      await load();
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not save.');
    }
  };

  const remove = async (slug: string) => {
    if (!confirm(`Delete short URL "${slug}"?`)) return;
    try { await api.delete(`/admin/short-urls/${slug}`); await load(); }
    catch (e: any) { showAlert('Delete failed', e?.response?.data?.detail || 'Could not delete.'); }
  };

  const runSeed = async () => {
    setSeeding(true);
    try {
      const r = await api.post('/admin/short-urls/seed', {});
      showAlert(
        'Seed complete',
        `Templates added: ${r.data?.inserted_templates ?? 0}\nStore apps added: ${r.data?.inserted_apps ?? 0}`,
      );
      await load();
    } catch (e: any) {
      showAlert('Seed failed', e?.response?.data?.detail || 'Could not seed.');
    } finally { setSeeding(false); }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Short URLs & Share Links</Text>
        <TouchableOpacity onPress={() => { setEditing({ active: true, kind: 'custom' }); setCreating(true); }}>
          <Ionicons name="add-circle" size={24} color={COLORS.primary} />
        </TouchableOpacity>
      </View>

      <View style={styles.toolbar}>
        <View style={styles.searchWrap}>
          <Ionicons name="search" size={16} color={COLORS.textMuted} />
          <TextInput
            value={q} onChangeText={setQ}
            placeholder="Search slug, title, target…"
            placeholderTextColor={COLORS.textMuted}
            style={styles.searchInput}
          />
        </View>
        <TouchableOpacity style={[styles.btn, { backgroundColor: '#7C3AED' }]} onPress={runSeed} disabled={seeding}>
          {seeding ? <ActivityIndicator size="small" color="#FFF" /> :
            <><Ionicons name="sparkles" size={14} color="#FFF" />
              <Text style={styles.btnTxt}>Auto-seed all templates & apps</Text></>}
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        >
          {filtered.length === 0 ? (
            <View style={styles.empty}>
              <Ionicons name="link-outline" size={36} color={COLORS.textMuted} />
              <Text style={styles.emptyTxt}>
                No short URLs yet. Tap ✨ Auto-seed to generate one per template & store app.
              </Text>
            </View>
          ) : filtered.map((r) => {
            const meta = KIND_META[r.kind] || KIND_META.custom;
            return (
              <View key={r.slug} style={[styles.card, !r.active && { opacity: 0.5 }]}>
                <View style={styles.cardTop}>
                  <View style={[styles.kindPill, { backgroundColor: meta.color + '18' }]}>
                    <Ionicons name={meta.icon} size={11} color={meta.color} />
                    <Text style={[styles.kindTxt, { color: meta.color }]}>{meta.label}</Text>
                  </View>
                  <Text style={styles.title} numberOfLines={1}>{r.title || r.slug}</Text>
                </View>
                <Text style={styles.mono} numberOfLines={1}>{publicBase}/s/{r.slug}</Text>
                <Text style={styles.target} numberOfLines={1}>→ {r.target_href}</Text>
                {r.share_message ? <Text style={styles.msg} numberOfLines={2}>“{r.share_message}”</Text> : null}
                <View style={styles.actionRow}>
                  <TouchableOpacity style={styles.iconBtn} onPress={() => shareLink(r)}>
                    <Ionicons name="share-social" size={14} color="#0EA5E9" />
                    <Text style={[styles.iconBtnTxt, { color: '#0EA5E9' }]}>Share</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.iconBtn} onPress={() => copyUrl(r)}>
                    <Ionicons name="copy" size={14} color={COLORS.textPrimary} />
                    <Text style={styles.iconBtnTxt}>Copy URL</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.iconBtn} onPress={() => { setEditing(r); setCreating(false); }}>
                    <Ionicons name="create" size={14} color="#7C3AED" />
                    <Text style={[styles.iconBtnTxt, { color: '#7C3AED' }]}>Edit</Text>
                  </TouchableOpacity>
                  {r.kind === 'custom' && (
                    <TouchableOpacity style={styles.iconBtn} onPress={() => remove(r.slug)}>
                      <Ionicons name="trash" size={14} color="#DC2626" />
                      <Text style={[styles.iconBtnTxt, { color: '#DC2626' }]}>Delete</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}

      {/* Edit / create modal */}
      <Modal transparent visible={!!editing} animationType="fade" onRequestClose={() => setEditing(null)}>
        <View style={styles.modalWrap}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>{creating ? 'New short URL' : `Edit /s/${editing?.slug}`}</Text>
            <ScrollView style={{ maxHeight: 420 }}>
              {creating && (
                <>
                  <Text style={styles.fieldLabel}>Slug (URL segment)</Text>
                  <TextInput
                    value={editing?.slug || ''}
                    onChangeText={(v) => setEditing({ ...editing, slug: v.replace(/[^a-z0-9-]/gi, '').toLowerCase() })}
                    placeholder="business-model-chooser"
                    placeholderTextColor={COLORS.textMuted}
                    style={styles.field}
                  />
                </>
              )}
              <Text style={styles.fieldLabel}>Title</Text>
              <TextInput
                value={editing?.title || ''}
                onChangeText={(v) => setEditing({ ...editing, title: v })}
                style={styles.field}
              />
              <Text style={styles.fieldLabel}>Target URL (where it redirects)</Text>
              <TextInput
                value={editing?.target_href || ''}
                onChangeText={(v) => setEditing({ ...editing, target_href: v })}
                placeholder="/decider-store/business-model-chooser"
                placeholderTextColor={COLORS.textMuted}
                style={styles.field}
              />
              <Text style={styles.fieldLabel}>Share message (used by Share button & WhatsApp)</Text>
              <TextInput
                value={editing?.share_message || ''}
                onChangeText={(v) => setEditing({ ...editing, share_message: v })}
                multiline numberOfLines={3}
                style={[styles.field, { height: 80, textAlignVertical: 'top' }]}
              />
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 8 }}>
                <Switch
                  value={editing?.active ?? true}
                  onValueChange={(v) => setEditing({ ...editing, active: v })}
                />
                <Text style={styles.fieldLabel}>Active (public /s/{editing?.slug || '…'} works)</Text>
              </View>
            </ScrollView>
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 14, justifyContent: 'flex-end' }}>
              <TouchableOpacity onPress={() => { setEditing(null); setCreating(false); }} style={[styles.btn, { backgroundColor: '#E5E7EB' }]}>
                <Text style={[styles.btnTxt, { color: COLORS.textPrimary }]}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={save} style={[styles.btn, { backgroundColor: COLORS.primary }]}>
                <Ionicons name="checkmark" size={14} color="#FFF" />
                <Text style={styles.btnTxt}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12, backgroundColor: COLORS.surface,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  toolbar: { flexDirection: 'row', gap: 8, padding: 12, backgroundColor: COLORS.surface, alignItems: 'center' },
  searchWrap: {
    flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 10, paddingVertical: 8,
    borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, backgroundColor: '#FFF',
  },
  searchInput: { flex: 1, fontSize: 14, color: COLORS.textPrimary, paddingVertical: 0 },
  btn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  btnTxt: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  scroll: { padding: 12, paddingBottom: 32 },
  empty: { alignItems: 'center', paddingVertical: 48, gap: 8 },
  emptyTxt: { color: COLORS.textMuted, fontSize: 13, textAlign: 'center', paddingHorizontal: 30 },
  card: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  kindPill: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  kindTxt: { fontSize: 10, fontWeight: '800' },
  title: { flex: 1, fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  mono: { fontSize: 12, color: '#4F46E5', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  target: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  msg: { fontSize: 12, color: COLORS.textSecondary, fontStyle: 'italic', marginTop: 6 },
  actionRow: { flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' },
  iconBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 5, borderRadius: 6, backgroundColor: '#F3F4F6' },
  iconBtnTxt: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary },
  modalWrap: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', alignItems: 'center', justifyContent: 'center', padding: 20 },
  modalCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, width: '100%', maxWidth: 480 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 8 },
  fieldLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted, marginTop: 8, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 },
  field: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary, backgroundColor: '#FFF' },
});
