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

  // Template Builder state (fills raw HTML/CSS when Generate clicked)
  const [activeTab, setActiveTab] = useState<'template' | 'code' | 'meta'>('template');
  const defaultTemplate = () => ({
    ribbon: 'THE WAIT IS OVER — SANGAMAM #26 IS HERE!',
    tamil_title: 'சங்கமம்',
    tamil_hash: '#26',
    english_title: 'Tamilpreneur Sangamam #26',
    subtitle: 'Startup Networking Event · Chennai',
    divider_text: 'Launch & Recognition',
    tagline: 'Connecting Founders. Creating Opportunities.',
    details: [
      { icon: '📅', label: 'Date', value: '1st Aug, 2026 · Saturday', highlight: false },
      { icon: '⏰', label: 'Time', value: '3:00 PM – 7:00 PM', highlight: false },
      { icon: '📍', label: 'Venue', value: 'Bloom Hub, Guindy, Chennai', highlight: false },
      { icon: '⭐', label: 'Limited', value: 'First 100 spots open now!', highlight: true },
    ],
    person_left: { role_label: 'Launched by', name: 'Shyam Siddarth', org: 'Founder, Tamilpreneur' },
    app_card: { name: 'JELCOS AI', subtitle: 'A Decision Intelligence Platform', description: 'For Founders, Business Owners, CXOs & Leaders' },
    person_right: { role_label: 'Received by', name: 'Ad Shezhiyan Raj', org: 'Founder & CEO, VEALES Vedic Decisions Pvt. Ltd.' },
    gold_band_text: 'சங்கமத்தில் சந்திப்போம்! ❤',
    chips: [
      { emoji: '🧠', text: 'AI Powered' },
      { emoji: '🎯', text: 'Smarter Decisions' },
      { emoji: '📈', text: 'Better Outcomes' },
      { emoji: '🪷', text: 'Conscious Living' },
    ],
    primary_cta_text: 'Book Your Spot Now',
    primary_cta_href: '/auth/register?ref=tps',
    secondary_cta_text: 'Try the free Decision-Style Quiz →',
    secondary_cta_href: '/quiz',
    footer_text: '© 2026 Jelcos AI · Chennai · <a href="https://jelcos.ai">jelcos.ai</a>',
    bg_gradient: 'linear-gradient(180deg,#3d0a12 0%,#1a0409 55%,#2a0710 100%)',
    accent_gold: '#c9a24e',
    accent_red: '#e11d48',
    text_light: '#f7e4a8',
  });
  const [tpl, setTpl] = useState<any>(defaultTemplate());
  const resetTemplate = () => setTpl(defaultTemplate());
  const [generating, setGenerating] = useState(false);
  const generateFromTemplate = async () => {
    setGenerating(true);
    try {
      const r = await api.post('/admin/landing-pages/generate-from-template', tpl);
      if (editing) setEditing({ ...editing, html: r.data.html, css: r.data.css });
      showAlert('Generated', 'HTML & CSS updated from template. Switch to the Code tab to preview or fine-tune.');
      setActiveTab('code');
    } catch (e: any) {
      showAlert('Generate failed', e?.response?.data?.detail || 'Could not generate.');
    } finally {
      setGenerating(false);
    }
  };
  const setTplField = (path: string, value: any) => {
    setTpl((prev: any) => {
      const clone = JSON.parse(JSON.stringify(prev));
      const keys = path.split('.');
      let cur = clone;
      for (let i = 0; i < keys.length - 1; i++) cur = cur[keys[i]];
      cur[keys[keys.length - 1]] = value;
      return clone;
    });
  };
  const setTplListItem = (list: 'details' | 'chips', idx: number, field: string, value: any) => {
    setTpl((prev: any) => {
      const clone = JSON.parse(JSON.stringify(prev));
      clone[list][idx][field] = value;
      return clone;
    });
  };
  const addTplListItem = (list: 'details' | 'chips') => {
    setTpl((prev: any) => {
      const clone = JSON.parse(JSON.stringify(prev));
      clone[list].push(list === 'details' ? { icon: '', label: '', value: '', highlight: false } : { emoji: '', text: '' });
      return clone;
    });
  };
  const removeTplListItem = (list: 'details' | 'chips', idx: number) => {
    setTpl((prev: any) => {
      const clone = JSON.parse(JSON.stringify(prev));
      clone[list].splice(idx, 1);
      return clone;
    });
  };

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

  const openEdit = (p: LP) => { setEditing({ ...p }); setCreating(false); setActiveTab('code'); };
  const openCreate = () => { setEditing(emptyDraft()); setCreating(true); setActiveTab('template'); resetTemplate(); };
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

                  {/* Tab strip: Template Builder · Code · Meta */}
                  <View style={styles.tabBar}>
                    {(['template', 'code', 'meta'] as const).map((t) => (
                      <TouchableOpacity key={t} onPress={() => setActiveTab(t)} style={[styles.tabBtn, activeTab === t && styles.tabBtnActive]}>
                        <Text style={[styles.tabBtnT, activeTab === t && styles.tabBtnTActive]}>
                          {t === 'template' ? '🎨 Template Builder' : t === 'code' ? '💻 HTML / CSS / JS' : '📝 Meta'}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  {activeTab === 'template' && (
                    <>
                      <Text style={styles.sectionTitle}>Hero</Text>
                      <Text style={styles.formLabel}>Ribbon banner</Text>
                      <TextInput style={styles.formInput} value={tpl.ribbon} onChangeText={(v) => setTplField('ribbon', v)} />

                      <View style={{ flexDirection: 'row', gap: 8 }}>
                        <View style={{ flex: 2 }}>
                          <Text style={styles.formLabel}>Tamil Title</Text>
                          <TextInput style={styles.formInput} value={tpl.tamil_title} onChangeText={(v) => setTplField('tamil_title', v)} />
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.formLabel}>Suffix (red)</Text>
                          <TextInput style={styles.formInput} value={tpl.tamil_hash} onChangeText={(v) => setTplField('tamil_hash', v)} />
                        </View>
                      </View>

                      <Text style={styles.formLabel}>English Title</Text>
                      <TextInput style={styles.formInput} value={tpl.english_title} onChangeText={(v) => setTplField('english_title', v)} />
                      <Text style={styles.formLabel}>Subtitle</Text>
                      <TextInput style={styles.formInput} value={tpl.subtitle} onChangeText={(v) => setTplField('subtitle', v)} />
                      <Text style={styles.formLabel}>Divider text (between ◆ marks)</Text>
                      <TextInput style={styles.formInput} value={tpl.divider_text} onChangeText={(v) => setTplField('divider_text', v)} />
                      <Text style={styles.formLabel}>Tagline</Text>
                      <TextInput style={styles.formInput} value={tpl.tagline} onChangeText={(v) => setTplField('tagline', v)} />

                      <Text style={styles.sectionTitle}>Detail cards ({tpl.details.length})</Text>
                      {tpl.details.map((c: any, idx: number) => (
                        <View key={idx} style={styles.subCard}>
                          <View style={{ flexDirection: 'row', gap: 6 }}>
                            <TextInput style={[styles.formInput, { flex: 0.5 }]} placeholder="📅" placeholderTextColor={COLORS.textMuted} value={c.icon} onChangeText={(v) => setTplListItem('details', idx, 'icon', v)} />
                            <TextInput style={[styles.formInput, { flex: 1 }]} placeholder="Date" placeholderTextColor={COLORS.textMuted} value={c.label} onChangeText={(v) => setTplListItem('details', idx, 'label', v)} />
                            <TextInput style={[styles.formInput, { flex: 2 }]} placeholder="1st Aug, 2026" placeholderTextColor={COLORS.textMuted} value={c.value} onChangeText={(v) => setTplListItem('details', idx, 'value', v)} />
                          </View>
                          <View style={styles.rowJustify}>
                            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                              <Switch value={!!c.highlight} onValueChange={(v) => setTplListItem('details', idx, 'highlight', v)} />
                              <Text style={styles.smallLbl}>Highlight (red/gold accent)</Text>
                            </View>
                            <TouchableOpacity onPress={() => removeTplListItem('details', idx)}><Ionicons name="trash-outline" size={16} color="#DC2626" /></TouchableOpacity>
                          </View>
                        </View>
                      ))}
                      <TouchableOpacity onPress={() => addTplListItem('details')} style={styles.addRowBtn}><Ionicons name="add" size={14} color={COLORS.primary} /><Text style={styles.addRowT}>Add detail card</Text></TouchableOpacity>

                      <Text style={styles.sectionTitle}>People + App card</Text>
                      <Text style={styles.formLabel}>LEFT PERSON</Text>
                      <TextInput style={styles.formInput} placeholder="Launched by" placeholderTextColor={COLORS.textMuted} value={tpl.person_left.role_label} onChangeText={(v) => setTplField('person_left.role_label', v)} />
                      <TextInput style={styles.formInput} placeholder="Shyam Siddarth" placeholderTextColor={COLORS.textMuted} value={tpl.person_left.name} onChangeText={(v) => setTplField('person_left.name', v)} />
                      <TextInput style={styles.formInput} placeholder="Founder, Tamilpreneur" placeholderTextColor={COLORS.textMuted} value={tpl.person_left.org} onChangeText={(v) => setTplField('person_left.org', v)} />

                      <Text style={styles.formLabel}>CENTER APP CARD</Text>
                      <TextInput style={styles.formInput} placeholder="JELCOS AI" placeholderTextColor={COLORS.textMuted} value={tpl.app_card.name} onChangeText={(v) => setTplField('app_card.name', v)} />
                      <TextInput style={styles.formInput} placeholder="A Decision Intelligence Platform" placeholderTextColor={COLORS.textMuted} value={tpl.app_card.subtitle} onChangeText={(v) => setTplField('app_card.subtitle', v)} />
                      <TextInput style={styles.formInput} placeholder="For Founders, Business Owners, CXOs & Leaders" placeholderTextColor={COLORS.textMuted} value={tpl.app_card.description} onChangeText={(v) => setTplField('app_card.description', v)} />

                      <Text style={styles.formLabel}>RIGHT PERSON</Text>
                      <TextInput style={styles.formInput} placeholder="Received by" placeholderTextColor={COLORS.textMuted} value={tpl.person_right.role_label} onChangeText={(v) => setTplField('person_right.role_label', v)} />
                      <TextInput style={styles.formInput} placeholder="Ad Shezhiyan Raj" placeholderTextColor={COLORS.textMuted} value={tpl.person_right.name} onChangeText={(v) => setTplField('person_right.name', v)} />
                      <TextInput style={styles.formInput} placeholder="Founder & CEO, VEALES..." placeholderTextColor={COLORS.textMuted} value={tpl.person_right.org} onChangeText={(v) => setTplField('person_right.org', v)} />

                      <Text style={styles.sectionTitle}>Gold band</Text>
                      <TextInput style={styles.formInput} value={tpl.gold_band_text} onChangeText={(v) => setTplField('gold_band_text', v)} />

                      <Text style={styles.sectionTitle}>Chip badges ({tpl.chips.length})</Text>
                      {tpl.chips.map((c: any, idx: number) => (
                        <View key={idx} style={{ flexDirection: 'row', gap: 6, marginBottom: 6, alignItems: 'center' }}>
                          <TextInput style={[styles.formInput, { flex: 0.5 }]} placeholder="🧠" placeholderTextColor={COLORS.textMuted} value={c.emoji} onChangeText={(v) => setTplListItem('chips', idx, 'emoji', v)} />
                          <TextInput style={[styles.formInput, { flex: 3 }]} placeholder="AI Powered" placeholderTextColor={COLORS.textMuted} value={c.text} onChangeText={(v) => setTplListItem('chips', idx, 'text', v)} />
                          <TouchableOpacity onPress={() => removeTplListItem('chips', idx)}><Ionicons name="close-circle" size={22} color="#DC2626" /></TouchableOpacity>
                        </View>
                      ))}
                      <TouchableOpacity onPress={() => addTplListItem('chips')} style={styles.addRowBtn}><Ionicons name="add" size={14} color={COLORS.primary} /><Text style={styles.addRowT}>Add chip</Text></TouchableOpacity>

                      <Text style={styles.sectionTitle}>Call-to-action</Text>
                      <Text style={styles.formLabel}>Primary CTA text</Text>
                      <TextInput style={styles.formInput} value={tpl.primary_cta_text} onChangeText={(v) => setTplField('primary_cta_text', v)} />
                      <Text style={styles.formLabel}>Primary CTA link</Text>
                      <TextInput style={styles.formInput} value={tpl.primary_cta_href} onChangeText={(v) => setTplField('primary_cta_href', v)} autoCapitalize="none" />
                      <Text style={styles.formLabel}>Secondary CTA text</Text>
                      <TextInput style={styles.formInput} value={tpl.secondary_cta_text} onChangeText={(v) => setTplField('secondary_cta_text', v)} />
                      <Text style={styles.formLabel}>Secondary CTA link</Text>
                      <TextInput style={styles.formInput} value={tpl.secondary_cta_href} onChangeText={(v) => setTplField('secondary_cta_href', v)} autoCapitalize="none" />

                      <Text style={styles.sectionTitle}>Theme colours</Text>
                      <View style={{ flexDirection: 'row', gap: 6 }}>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.formLabel}>Gold</Text>
                          <TextInput style={styles.formInput} value={tpl.accent_gold} onChangeText={(v) => setTplField('accent_gold', v)} autoCapitalize="none" />
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.formLabel}>Red</Text>
                          <TextInput style={styles.formInput} value={tpl.accent_red} onChangeText={(v) => setTplField('accent_red', v)} autoCapitalize="none" />
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.formLabel}>Text light</Text>
                          <TextInput style={styles.formInput} value={tpl.text_light} onChangeText={(v) => setTplField('text_light', v)} autoCapitalize="none" />
                        </View>
                      </View>

                      <TouchableOpacity style={[styles.generateBtn, generating && { opacity: 0.6 }]} onPress={generateFromTemplate} disabled={generating}>
                        {generating ? <ActivityIndicator color={COLORS.white} /> : (
                          <>
                            <Ionicons name="sparkles" size={16} color={COLORS.white} />
                            <Text style={styles.generateBtnT}>Generate HTML &amp; CSS</Text>
                          </>
                        )}
                      </TouchableOpacity>
                      <Text style={styles.formHint}>Click Generate — it fills the HTML/CSS tabs. You can then fine-tune before Save.</Text>
                    </>
                  )}

                  {activeTab === 'meta' && (
                    <>
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

                      <View style={styles.activeRow}>
                        <Text style={{ fontWeight: '700', color: COLORS.textPrimary }}>Active</Text>
                        <Switch value={editing.active} onValueChange={(v) => setEditing({ ...editing, active: v })} />
                      </View>
                    </>
                  )}

                  {activeTab === 'code' && (
                    <>
                      <Text style={styles.formLabel}>HTML body</Text>
                      <TextInput
                        style={[styles.formInput, styles.code, { minHeight: 200 }]} multiline
                        value={editing.html}
                        onChangeText={(t) => setEditing({ ...editing, html: t })}
                        autoCapitalize="none" autoCorrect={false}
                      />

                      <Text style={styles.formLabel}>CSS</Text>
                      <TextInput
                        style={[styles.formInput, styles.code, { minHeight: 160 }]} multiline
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
                    </>
                  )}

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
  tabBar: { flexDirection: 'row', gap: 6, marginTop: 12, marginBottom: 4, borderBottomWidth: 1, borderBottomColor: COLORS.border, paddingBottom: 6 },
  tabBtn: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, backgroundColor: COLORS.background },
  tabBtnActive: { backgroundColor: '#EEF2FF', borderWidth: 1, borderColor: COLORS.primary },
  tabBtnT: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  tabBtnTActive: { color: COLORS.primary, fontWeight: '800' },
  sectionTitle: { fontSize: 13, fontWeight: '800', color: COLORS.textPrimary, marginTop: 18, marginBottom: 4, paddingTop: 6, borderTopWidth: 1, borderTopColor: '#F1F5F9' },
  subCard: { padding: 8, backgroundColor: COLORS.background, borderRadius: 8, marginBottom: 8, gap: 6 },
  rowJustify: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 },
  smallLbl: { fontSize: 11, color: COLORS.textSecondary },
  addRowBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: COLORS.primary, borderStyle: 'dashed', alignSelf: 'flex-start', marginTop: 4 },
  addRowT: { fontSize: 12, color: COLORS.primary, fontWeight: '700' },
  generateBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#7C3AED', paddingVertical: 12, borderRadius: 10, marginTop: 18 },
  generateBtnT: { color: COLORS.white, fontWeight: '800', fontSize: 14 },
});
