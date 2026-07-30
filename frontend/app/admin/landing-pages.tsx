/**
 * Admin · Custom Landing Pages CRUD.
 *
 * Manage HTML/CSS/JS landing pages served at short jelcos.ai URLs like /tps,
 * /sangamam, /launch. Slug becomes the URL path. Toggle active/inactive.
 * "Preview" opens the page in a new tab.
 */
import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Switch, Platform, KeyboardAvoidingView, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack } from '../../src/utils/navigation';

type LP = {
  slug: string;
  title: string;
  html: string;
  css: string;
  js: string;
  meta_description?: string;
  meta_og_image?: string;
  active: boolean;
  created_at?: string;
  updated_at?: string;
  source?: string;
};

export default function AdminLandingPagesScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const role = (user?.role || '').toLowerCase();
  const isAdmin = role === 'super_admin' || role === 'admin';

  const [pages, setPages] = useState<LP[]>([]);
  const [reserved, setReserved] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<LP | null>(null);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);

  const emptyDraft = (): LP => ({
    slug: '', title: '', html: '', css: '', js: '',
    meta_description: '', meta_og_image: '', active: true,
  });

  const fetchPages = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/landing-pages');
      setPages(r.data?.pages || []);
      setReserved(r.data?.reserved_slugs || []);
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Could not load landing pages.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { if (isAdmin) fetchPages(); }, [isAdmin, fetchPages]));

  const openEdit = (p: LP) => { setEditing({ ...p }); setCreating(false); };
  const openCreate = () => { setEditing(emptyDraft()); setCreating(true); };
  const closeEdit = () => { setEditing(null); setCreating(false); };

  const save = async () => {
    if (!editing) return;
    if (!editing.title.trim()) { showAlert('Title required', 'Please enter a title.'); return; }
    setSaving(true);
    try {
      if (creating) {
        if (!editing.slug.trim()) { showAlert('Slug required', 'Enter a short URL slug like "tps".'); setSaving(false); return; }
        await api.post('/admin/landing-pages', editing);
        showAlert('Created', `Landing page /${editing.slug} is live.`);
      } else {
        const { slug, source, created_at, updated_at, ...body } = editing as any;
        await api.put(`/admin/landing-pages/${slug}`, body);
        showAlert('Saved', `/${slug} updated.`);
      }
      closeEdit();
      await fetchPages();
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not save.');
    } finally {
      setSaving(false);
    }
  };

  const del = async (slug: string) => {
    try {
      await api.delete(`/admin/landing-pages/${slug}`);
      setPages((prev) => prev.filter((p) => p.slug !== slug));
    } catch (e: any) {
      showAlert('Delete failed', e?.response?.data?.detail || 'Could not delete.');
    }
  };

  const toggleActive = async (p: LP, v: boolean) => {
    setPages((prev) => prev.map((x) => (x.slug === p.slug ? { ...x, active: v } : x)));
    try { await api.put(`/admin/landing-pages/${p.slug}`, { active: v }); }
    catch (e: any) { showAlert('Save failed', 'Could not toggle.'); fetchPages(); }
  };

  const openPreview = (slug: string) => {
    if (Platform.OS === 'web') window.open(`/${slug}`, '_blank');
  };

  if (!isAdmin) {
    return <SafeAreaView style={styles.container}><Text style={styles.gate}>Super-admin access only.</Text></SafeAreaView>;
  }

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => safeBack(router, '/admin')} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={22} color={COLORS.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Landing Pages</Text>
          <TouchableOpacity onPress={openCreate} style={styles.addBtn}>
            <Ionicons name="add" size={16} color={COLORS.white} />
            <Text style={styles.addBtnText}>New</Text>
          </TouchableOpacity>
        </View>

        {loading ? <ActivityIndicator color={COLORS.primary} style={{ marginTop: 40 }} /> : (
          <ScrollView contentContainerStyle={styles.scroll}>
            <View style={styles.infoCard}>
              <Ionicons name="information-circle" size={18} color={COLORS.primary} />
              <Text style={styles.infoText}>
                Serve custom event pages at short URLs like{' '}
                <Text style={{ fontWeight: '700' }}>jelcos.ai/tps</Text>. The slug becomes the URL path.
                Reserved paths (like{' '}
                <Text style={{ fontFamily: Platform.select({ web: 'monospace', default: 'System' }) }}>admin, api, auth, quiz, tools, prr</Text>
                ) can&apos;t be used. Inactive pages return 404. Preview opens in a new tab.
              </Text>
            </View>

            {pages.length === 0 && <Text style={styles.empty}>No landing pages yet. Click New.</Text>}

            {pages.map((p) => (
              <View key={p.slug} style={[styles.card, !p.active && styles.cardInactive]}>
                <View style={styles.cardHead}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.slug}>jelcos.ai/{p.slug}</Text>
                    <Text style={styles.title} numberOfLines={1}>{p.title}</Text>
                    {!!p.meta_description && (
                      <Text style={styles.desc} numberOfLines={2}>{p.meta_description}</Text>
                    )}
                    {!!p.updated_at && (
                      <Text style={styles.meta}>Updated {new Date(p.updated_at).toLocaleString()}</Text>
                    )}
                  </View>
                  <Switch value={p.active} onValueChange={(v) => toggleActive(p, v)} />
                </View>
                <View style={styles.cardActions}>
                  {Platform.OS === 'web' && (
                    <TouchableOpacity style={styles.actionBtn} onPress={() => openPreview(p.slug)}>
                      <Ionicons name="open-outline" size={14} color={COLORS.primary} />
                      <Text style={styles.actionT}>Preview</Text>
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity style={styles.actionBtn} onPress={() => openEdit(p)}>
                    <Ionicons name="create-outline" size={14} color={COLORS.primary} />
                    <Text style={styles.actionT}>Edit</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.actionBtn, styles.deleteBtn]} onPress={() => del(p.slug)}>
                    <Ionicons name="trash-outline" size={14} color="#DC2626" />
                    <Text style={[styles.actionT, { color: '#DC2626' }]}>Delete</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ))}

            {reserved.length > 0 && (
              <Text style={styles.reservedList}>
                <Text style={{ fontWeight: '700' }}>Reserved paths (cannot be used):</Text> {reserved.join(', ')}
              </Text>
            )}
          </ScrollView>
        )}

        {/* Edit / Create modal */}
        <Modal visible={!!editing} transparent animationType="slide" onRequestClose={closeEdit}>
          <View style={styles.modalOverlay}>
            <View style={styles.modalSheet}>
              <View style={styles.modalHead}>
                <Text style={styles.modalTitle}>{creating ? 'New Landing Page' : `Edit /${editing?.slug}`}</Text>
                <TouchableOpacity onPress={closeEdit}><Ionicons name="close" size={22} color={COLORS.textSecondary} /></TouchableOpacity>
              </View>
              {editing && (
                <ScrollView>
                  {creating && (
                    <>
                      <Text style={styles.formLabel}>URL Slug *</Text>
                      <TextInput
                        style={styles.formInput}
                        placeholder="tps"
                        placeholderTextColor={COLORS.textMuted}
                        value={editing.slug}
                        onChangeText={(t) => setEditing({ ...editing, slug: t.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                        autoCapitalize="none"
                      />
                      <Text style={styles.formHint}>Lowercase, letters/digits/hyphens only. URL becomes jelcos.ai/{editing.slug || 'your-slug'}</Text>
                    </>
                  )}

                  <Text style={styles.formLabel}>Title (browser tab &amp; social share) *</Text>
                  <TextInput style={styles.formInput} value={editing.title} onChangeText={(t) => setEditing({ ...editing, title: t })} />

                  <Text style={styles.formLabel}>Meta description (SEO / social unfurl)</Text>
                  <TextInput
                    style={[styles.formInput, { height: 60 }]} multiline
                    value={editing.meta_description || ''}
                    onChangeText={(t) => setEditing({ ...editing, meta_description: t })}
                  />

                  <Text style={styles.formLabel}>OG Image URL (social share thumbnail)</Text>
                  <TextInput
                    style={styles.formInput}
                    placeholder="https://…/image.png"
                    placeholderTextColor={COLORS.textMuted}
                    value={editing.meta_og_image || ''}
                    onChangeText={(t) => setEditing({ ...editing, meta_og_image: t })}
                    autoCapitalize="none"
                  />

                  <Text style={styles.formLabel}>HTML body</Text>
                  <TextInput
                    style={[styles.formInput, styles.code, { minHeight: 180 }]} multiline
                    value={editing.html}
                    onChangeText={(t) => setEditing({ ...editing, html: t })}
                    autoCapitalize="none" autoCorrect={false}
                  />

                  <Text style={styles.formLabel}>CSS</Text>
                  <TextInput
                    style={[styles.formInput, styles.code, { minHeight: 140 }]} multiline
                    value={editing.css}
                    onChangeText={(t) => setEditing({ ...editing, css: t })}
                    autoCapitalize="none" autoCorrect={false}
                  />

                  <Text style={styles.formLabel}>JavaScript (optional)</Text>
                  <TextInput
                    style={[styles.formInput, styles.code, { minHeight: 80 }]} multiline
                    value={editing.js}
                    onChangeText={(t) => setEditing({ ...editing, js: t })}
                    autoCapitalize="none" autoCorrect={false}
                  />
                  <Text style={styles.formHint}>⚠️ JS runs in the visitor&apos;s browser. Only paste code you trust.</Text>

                  <View style={styles.activeRow}>
                    <Text style={{ fontWeight: '700', color: COLORS.textPrimary }}>Active</Text>
                    <Switch value={editing.active} onValueChange={(v) => setEditing({ ...editing, active: v })} />
                  </View>

                  <TouchableOpacity style={[styles.saveBtn, saving && { opacity: 0.6 }]} onPress={save} disabled={saving}>
                    {saving ? <ActivityIndicator color={COLORS.white} /> : <Text style={styles.saveBtnText}>{creating ? 'Create' : 'Save changes'}</Text>}
                  </TouchableOpacity>
                </ScrollView>
              )}
            </View>
          </View>
        </Modal>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  gate: { fontSize: 14, color: COLORS.textMuted, textAlign: 'center', marginTop: 40 },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.border, backgroundColor: COLORS.white },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary, flex: 1, marginLeft: 8 },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  addBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 13 },
  scroll: { padding: 12, paddingBottom: 40, maxWidth: 900, width: '100%', alignSelf: 'center' },
  infoCard: { flexDirection: 'row', gap: 8, backgroundColor: '#EEF2FF', padding: 12, borderRadius: 12, marginBottom: 14 },
  infoText: { flex: 1, fontSize: 12, color: COLORS.textSecondary, lineHeight: 18 },
  empty: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', marginVertical: 30 },
  card: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  cardInactive: { opacity: 0.55 },
  cardHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  slug: { fontSize: 13, fontWeight: '800', color: COLORS.primary, marginBottom: 2, fontFamily: Platform.select({ web: 'monospace', default: 'System' }) },
  title: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  desc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 3, lineHeight: 16 },
  meta: { fontSize: 10, color: COLORS.textMuted, marginTop: 4 },
  cardActions: { flexDirection: 'row', gap: 6, marginTop: 10, flexWrap: 'wrap' },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.background },
  deleteBtn: { borderColor: '#DC262633', backgroundColor: '#FEF2F2' },
  actionT: { fontSize: 11, color: COLORS.primary, fontWeight: '600' },
  reservedList: { fontSize: 11, color: COLORS.textMuted, marginTop: 12, lineHeight: 16 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalSheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, maxHeight: '92%', maxWidth: 900, width: '100%', alignSelf: 'center' },
  modalHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary },
  formLabel: { fontSize: 11, fontWeight: '800', color: COLORS.textSecondary, textTransform: 'uppercase', marginTop: 12, marginBottom: 6 },
  formInput: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  code: { fontFamily: Platform.select({ web: 'monospace', default: 'System' }), fontSize: 12, textAlignVertical: 'top' },
  formHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 4, fontStyle: 'italic' },
  activeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 14, paddingHorizontal: 4 },
  saveBtn: { backgroundColor: COLORS.primary, paddingVertical: 12, borderRadius: 10, alignItems: 'center', marginTop: 18, marginBottom: 20 },
  saveBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 14 },
});
