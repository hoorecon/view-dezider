/**
 * /admin/appearance — Admin UI to pick the app-wide font family.
 *
 * Reads/writes GET|PUT /api/appearance. Selecting a font saves it server-side
 * AND applies it live via FontFamilyContext so the admin sees the change
 * instantly (on web). Default is Inter (matches jelcos.ai).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TextInput, TouchableOpacity, ActivityIndicator, Image, Platform, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';
import { FONT_OPTIONS, getFontOption } from '../../src/constants/fonts';
import { useFontFamily, useAppLogo } from '../../src/contexts/FontFamilyContext';
import { useAuthStore } from '../../src/store/authStore';
import { invalidateLoaderMusicCache } from '../../src/hooks/useLoaderMusic';

export default function AdminAppearance() {
  const router = useRouter();
  const { fontKey, setFont, companyName: liveCompany, setCompanyName, refreshAppearance } = useFontFamily();
  const logoUri = useAppLogo();
  const user = useAuthStore((s) => s.user);
  const isSuperAdmin = user?.role === 'super_admin';
  const [selected, setSelected] = useState<string>(fontKey);
  const [profile, setProfile] = useState({
    brand_name: '', tagline: '', legal_name: liveCompany,
    address: '', phone: '', email: '', website: '', support_hours: '',
  });
  const setField = (k: string, v: string) => setProfile((prev) => ({ ...prev, [k]: v }));
  const [savingCompany, setSavingCompany] = useState(false);
  const [logoBusy, setLogoBusy] = useState(false);
  // Loader music — multi-slot, keyed by slot id from the backend.
  type SlotInfo = { label: string; has: boolean; silent: boolean; url: string | null;
                    filename: string | null; version: number };
  const [musicSlots, setMusicSlots] = useState<Record<string, SlotInfo>>({});
  const [musicBusySlot, setMusicBusySlot] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get('/appearance');
      setSelected(r.data?.font_family || 'Inter');
      const d = r.data || {};
      setProfile({
        brand_name: d.brand_name || '', tagline: d.tagline || '',
        legal_name: d.legal_name || d.company_name || '', address: d.address || '',
        phone: d.phone || '', email: d.email || '', website: d.website || '',
        support_hours: d.support_hours || '',
      });
      setMusicSlots(d.loader_music_slots || {});
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Could not fetch appearance settings');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const saveCompany = useCallback(async () => {
    if ((profile.legal_name || '').trim().length < 2) { showAlert('Invalid', 'Legal name is too short.'); return; }
    setSavingCompany(true);
    try {
      await api.put('/admin/company-info', {
        brand_name: profile.brand_name.trim(),
        tagline: profile.tagline.trim(),
        legal_name: profile.legal_name.trim(),
        address: profile.address,
        phone: profile.phone.trim(),
        email: profile.email.trim(),
        website: profile.website.trim(),
        support_hours: profile.support_hours.trim(),
      });
      setCompanyName(profile.legal_name.trim());
      await refreshAppearance();
      showAlert('Saved', 'Company profile updated across Contact, all policy pages, footer & headers.');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not save company profile');
    } finally { setSavingCompany(false); }
  }, [profile, setCompanyName, refreshAppearance]);

  const uploadLogo = useCallback(async (dataUrl: string) => {
    setLogoBusy(true);
    try {
      await api.put('/admin/logo', { logo_base64: dataUrl });
      await refreshAppearance();
      showAlert('Logo updated', 'Your logo now appears across the app and PDF reports.');
    } catch (e: any) {
      showAlert('Upload failed', e?.response?.data?.detail || 'Could not save the logo.');
    } finally { setLogoBusy(false); }
  }, [refreshAppearance]);

  const pickLogo = useCallback(async () => {
    // Native: request media-library permission contextually.
    if (Platform.OS !== 'web') {
      const cur = await ImagePicker.getMediaLibraryPermissionsAsync();
      let status = cur.status;
      if (status !== 'granted' && cur.canAskAgain) {
        status = (await ImagePicker.requestMediaLibraryPermissionsAsync()).status;
      }
      if (status !== 'granted') {
        showAlert('Permission needed', 'Allow photo access to choose a logo.', [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Open Settings', onPress: () => Linking.openSettings() },
        ]);
        return;
      }
    }
    try {
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        quality: 1,
        base64: true,
      });
      if (res.canceled || !res.assets?.length) return;
      const a = res.assets[0];
      if (!a.base64) { showAlert('Unsupported', 'Could not read the image.'); return; }
      const mime = (a.mimeType || '').toLowerCase();
      const normMime = mime.includes('jpeg') || mime.includes('jpg') ? 'image/jpeg'
        : mime.includes('png') ? 'image/png' : '';
      if (!normMime) { showAlert('Unsupported format', 'Please choose a PNG or JPG image.'); return; }
      // ~1MB guard (base64 length ≈ 1.37 × bytes)
      if (a.base64.length > 1.4 * 1024 * 1024) { showAlert('Too large', 'Logo must be 1 MB or smaller.'); return; }
      await uploadLogo(`data:${normMime};base64,${a.base64}`);
    } catch (e: any) {
      showAlert('Picker error', e?.message || 'Could not open the image picker.');
    }
  }, [uploadLogo]);

  const removeLogo = useCallback(async () => {
    setLogoBusy(true);
    try {
      await api.delete('/admin/logo');
      await refreshAppearance();
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Could not remove the logo.');
    } finally { setLogoBusy(false); }
  }, [refreshAppearance]);

  // ── Loader music handlers (multi-slot) ──────────────────────────────
  const pickLoaderMusic = useCallback(async (slot: string) => {
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav',
               'audio/ogg', 'audio/webm', 'audio/mp4', 'audio/aac', 'audio/*'],
        multiple: false,
        copyToCacheDirectory: true,
      });
      if (res.canceled || !res.assets?.length) return;
      const a = res.assets[0];
      if (a.size && a.size > 3 * 1024 * 1024) {
        showAlert('Too large', 'Audio file must be 3 MB or smaller. Compress to a lower bitrate (e.g. 128 kbps MP3).');
        return;
      }
      let base64: string | null = null;
      let mime = (a.mimeType || 'audio/mpeg').toLowerCase();
      if (Platform.OS === 'web' && (a as any).file) {
        const file: File = (a as any).file;
        base64 = await new Promise<string>((resolve, reject) => {
          const fr = new FileReader();
          fr.onload = () => {
            const r = String(fr.result || '');
            const idx = r.indexOf(',');
            resolve(idx >= 0 ? r.slice(idx + 1) : r);
          };
          fr.onerror = () => reject(fr.error);
          fr.readAsDataURL(file);
        });
        if (file.type) mime = file.type;
      } else if (a.uri) {
        base64 = await FileSystem.readAsStringAsync(a.uri, { encoding: FileSystem.EncodingType.Base64 });
      }
      if (!base64) { showAlert('Unsupported', 'Could not read the audio file.'); return; }
      const dataUrl = `data:${mime};base64,${base64}`;
      setMusicBusySlot(slot);
      await api.put(`/admin/loader-music/${slot}`, {
        music_base64: dataUrl, filename: a.name || `${slot}-music`,
      });
      invalidateLoaderMusicCache();
      await load();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Could not save the audio.';
      showAlert('Upload failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setMusicBusySlot(null);
    }
  }, [load]);

  const removeLoaderMusic = useCallback(async (slot: string) => {
    setMusicBusySlot(slot);
    try {
      await api.delete(`/admin/loader-music/${slot}`);
      invalidateLoaderMusicCache();
      await load();
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Could not remove the audio.');
    } finally { setMusicBusySlot(null); }
  }, [load]);

  const toggleSilent = useCallback(async (slot: string, silent: boolean) => {
    setMusicBusySlot(slot);
    try {
      await api.put(`/admin/loader-music/${slot}/silent`, { silent });
      invalidateLoaderMusicCache();
      await load();
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Could not update the slot.');
    } finally { setMusicBusySlot(null); }
  }, [load]);

  const choose = useCallback(async (key: string) => {
    setSaving(key);
    const prev = selected;
    setSelected(key);
    setFont(key); // live preview (web)
    try {
      await api.put('/admin/appearance', { font_family: key });
    } catch (e: any) {
      setSelected(prev);
      setFont(prev);
      showAlert('Save failed', e?.response?.data?.detail || 'Could not save font');
    } finally { setSaving(null); }
  }, [selected, setFont]);

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={8} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Appearance · Font</Text>
        <View style={{ width: 22 }} />
      </View>

      {loading ? (
        <View style={s.center}><ActivityIndicator color={COLORS.primary} /></View>
      ) : (
        <ScrollView contentContainerStyle={s.body}>
          <Text style={s.intro}>
            Choose the app-wide font. Applies to the web app instantly; native apps use the
            bundled default (Inter) until a build includes the selected font.
          </Text>

          {/* Company profile (Super Admin only) */}
          <View style={s.companyCard}>
            <Text style={s.sectionTitle}>Company Profile</Text>
            <Text style={s.companyHint}>Shown on Contact Us, all policy pages, footer, headers & the PII-access NDA.</Text>

            {([
              ['brand_name', 'Brand / Display Name', 'JELCOS AI', false],
              ['tagline', 'Tagline', 'Your product tagline', false],
              ['legal_name', 'Legal Entity Name', 'HOORECON IT-Sys Pvt Ltd', false],
              ['address', 'Registered Address', 'Street, City, State, PIN, Country', true],
              ['phone', 'Phone', '+(91)-(0)44-46972104', false],
              ['email', 'Email', 'admin@hoorecon.com', false],
              ['website', 'Website', 'www.hoorecon.com', false],
              ['support_hours', 'Support Hours', 'Mon-Fri, 10:00 AM - 6:00 PM IST', false],
            ] as [string, string, string, boolean][]).map(([key, label, ph, multi]) => (
              <View key={key} style={{ marginBottom: 10 }}>
                <Text style={s.fieldLabel}>{label}</Text>
                <TextInput
                  style={[s.companyInput, multi && { minHeight: 70, textAlignVertical: 'top' }, !isSuperAdmin && { opacity: 0.6 }]}
                  value={(profile as any)[key]}
                  onChangeText={(v) => setField(key, v)}
                  editable={isSuperAdmin}
                  placeholder={ph}
                  placeholderTextColor="#94A3B8"
                  multiline={multi}
                  autoCapitalize={key === 'email' || key === 'website' ? 'none' : 'sentences'}
                />
              </View>
            ))}

            {isSuperAdmin ? (
              <TouchableOpacity style={[s.companySave, { alignSelf: 'flex-start', paddingHorizontal: 24, marginTop: 4 }, savingCompany && { opacity: 0.6 }]} onPress={saveCompany} disabled={savingCompany}>
                {savingCompany ? <ActivityIndicator size="small" color="#FFF" /> : <Text style={s.companySaveText}>Save profile</Text>}
              </TouchableOpacity>
            ) : (
              <Text style={s.companyLocked}>Only a Super Admin can change the company profile.</Text>
            )}
          </View>

          {/* Logo (Super Admin only) */}
          <View style={s.companyCard}>
            <Text style={s.sectionTitle}>App Logo</Text>
            <Text style={s.companyHint}>PNG or JPG, up to 1 MB. Shown in header, footer, login & PDF reports.</Text>
            <View style={s.logoRow}>
              <View style={s.logoPreview}>
                {logoUri ? (
                  <Image source={{ uri: logoUri }} style={s.logoImg} resizeMode="contain" />
                ) : (
                  <Ionicons name="image-outline" size={28} color={COLORS.textMuted} />
                )}
              </View>
              {isSuperAdmin ? (
                <View style={{ flex: 1, gap: 8 }}>
                  <TouchableOpacity style={[s.logoBtn, logoBusy && { opacity: 0.6 }]} onPress={pickLogo} disabled={logoBusy}>
                    {logoBusy ? <ActivityIndicator size="small" color="#FFF" /> : <><Ionicons name="cloud-upload-outline" size={16} color="#FFF" /><Text style={s.logoBtnText}>{logoUri ? 'Replace logo' : 'Upload logo'}</Text></>}
                  </TouchableOpacity>
                  {!!logoUri && (
                    <TouchableOpacity style={s.logoResetBtn} onPress={removeLogo} disabled={logoBusy}>
                      <Text style={s.logoResetText}>Remove (use default)</Text>
                    </TouchableOpacity>
                  )}
                </View>
              ) : (
                <Text style={[s.companyLocked, { flex: 1 }]}>Only a Super Admin can change the logo.</Text>
              )}
            </View>
          </View>

          {/* Loader music — multi-slot. The `default` slot is the fallback
              every other slot inherits from when empty. An admin can also
              mark any slot silent to opt one specific workflow OUT of music
              without removing the default. Users can per-user mute via the
              speaker icon shown next to each loader. */}
          <View style={s.companyCard}>
            <Text style={s.sectionTitle}>Loader music (per-workflow)</Text>
            <Text style={s.companyHint}>
              Pick a different MP3 / WAV / OGG / M4A (≤ 3 MB, trim to ~30s for clean looping) for each major
              progress loader. Empty slots fall back to the <Text style={{ fontWeight: '700' }}>default</Text> slot.
              Mark a slot <Text style={{ fontWeight: '700' }}>silent</Text> to opt only that workflow out of music
              while keeping the default soundtrack elsewhere.
            </Text>
            {(Object.entries(musicSlots) as [string, SlotInfo][]).map(([slot, info]) => {
              const busy = musicBusySlot === slot;
              const fallback = !info.has && !info.silent && slot !== 'default' && !!musicSlots.default?.has;
              const previewUrl = info.has && info.url
                ? `${(api.defaults.baseURL || '').replace(/\/api\/?$/, '')}${info.url}?v=${info.version || 0}`
                : null;
              return (
                <View
                  key={slot}
                  testID={`admin-loader-music-slot-${slot}`}
                  style={{
                    paddingVertical: 12, paddingHorizontal: 12, marginTop: 10,
                    borderRadius: 10, borderWidth: 1,
                    borderColor: info.silent ? '#FCA5A5' : (info.has ? '#C4B5FD' : '#E5E7EB'),
                    backgroundColor: info.silent ? '#FEF2F2' : (info.has ? '#FAF5FF' : '#F8FAFC'),
                  }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                    <Ionicons
                      name={info.silent ? 'volume-mute' : (info.has ? 'musical-notes' : 'musical-notes-outline')}
                      size={20}
                      color={info.silent ? '#DC2626' : (info.has ? '#7C3AED' : COLORS.textMuted)}
                    />
                    <View style={{ flex: 1, minWidth: 220 }}>
                      <Text style={{ fontSize: 13, fontWeight: '700', color: COLORS.textPrimary }}>
                        {info.label}
                      </Text>
                      <Text style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 2 }} numberOfLines={1}>
                        {info.silent
                          ? '🔇 Silent — no music for this workflow.'
                          : info.has
                            ? `Audio: ${info.filename || `${slot}-music`}`
                            : (fallback
                                ? 'Empty — falls back to the default slot\u2019s music.'
                                : 'Empty — silent loader.')}
                      </Text>
                    </View>
                    {isSuperAdmin && (
                      <View style={{ flexDirection: 'row', gap: 6 }}>
                        <TouchableOpacity
                          testID={`admin-music-upload-${slot}`}
                          disabled={busy}
                          onPress={() => pickLoaderMusic(slot)}
                          style={[s.logoBtn, busy && { opacity: 0.6 }, { paddingHorizontal: 12 }]}>
                          {busy ? <ActivityIndicator size="small" color="#FFF" /> :
                            <><Ionicons name="cloud-upload-outline" size={14} color="#FFF" />
                              <Text style={[s.logoBtnText, { fontSize: 12 }]}>{info.has ? 'Replace' : 'Upload'}</Text></>}
                        </TouchableOpacity>
                        {info.has && (
                          <TouchableOpacity
                            testID={`admin-music-remove-${slot}`}
                            disabled={busy}
                            onPress={() => removeLoaderMusic(slot)}
                            style={[s.logoResetBtn, { paddingHorizontal: 10 }]}>
                            <Text style={[s.logoResetText, { fontSize: 11 }]}>Remove</Text>
                          </TouchableOpacity>
                        )}
                        {slot !== 'default' && (
                          <TouchableOpacity
                            testID={`admin-music-silent-${slot}`}
                            disabled={busy}
                            onPress={() => toggleSilent(slot, !info.silent)}
                            style={[s.logoResetBtn, { paddingHorizontal: 10,
                              backgroundColor: info.silent ? '#FEE2E2' : undefined }]}>
                            <Text style={[s.logoResetText, { fontSize: 11,
                              color: info.silent ? '#991B1B' : s.logoResetText.color }]}>
                              {info.silent ? 'Un-silence' : 'Silent'}
                            </Text>
                          </TouchableOpacity>
                        )}
                      </View>
                    )}
                  </View>
                  {Platform.OS === 'web' && previewUrl && (
                    <View style={{ marginTop: 8 }}>
                      {React.createElement('audio', { src: previewUrl, controls: true,
                        style: { width: '100%', maxWidth: 360 } })}
                    </View>
                  )}
                </View>
              );
            })}
          </View>

          {FONT_OPTIONS.map((opt) => {
            const isSel = selected === opt.key;
            const stack = Platform.OS === 'web' ? (getFontOption(opt.key).webStack as any) : undefined;
            return (
              <TouchableOpacity
                key={opt.key}
                style={[s.card, isSel && s.cardSel]}
                onPress={() => choose(opt.key)}
                activeOpacity={0.8}
                disabled={!!saving}
              >
                <View style={{ flex: 1 }}>
                  <Text style={[s.cardLabel, isSel && { color: COLORS.primary }]}>{opt.label}</Text>
                  {/* Live preview line rendered in the option's own font (web). */}
                  <Text style={[s.previewText, Platform.OS === 'web' ? ({ fontFamily: stack } as any) : null]}>
                    Make every life choice with clarity — 12345
                  </Text>
                </View>
                {saving === opt.key ? (
                  <ActivityIndicator size="small" color={COLORS.primary} />
                ) : isSel ? (
                  <Ionicons name="checkmark-circle" size={24} color={COLORS.primary} />
                ) : (
                  <Ionicons name="ellipse-outline" size={24} color={COLORS.border} />
                )}
              </TouchableOpacity>
            );
          })}

          <Text style={s.note}>
            Note: Satoshi, Mona Sans, Clash Display and Geist Mono need bundled font files and
            will be added in a follow-up.
          </Text>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: COLORS.border, backgroundColor: COLORS.white },
  backBtn: { width: 22 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  body: { padding: 16, paddingBottom: 40 },
  intro: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19, marginBottom: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 10, marginTop: 4 },
  companyCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: COLORS.border },
  companyHint: { fontSize: 12, color: COLORS.textMuted, marginTop: -6, marginBottom: 12 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 4 },
  companyRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  companyInput: { flex: 1, borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, backgroundColor: '#F8FAFC' },
  companySave: { backgroundColor: COLORS.primary, borderRadius: 10, paddingHorizontal: 18, paddingVertical: 11, minWidth: 70, alignItems: 'center' },
  companySaveText: { color: '#FFFFFF', fontWeight: '700', fontSize: 14 },
  companyLocked: { fontSize: 12, color: COLORS.textMuted, marginTop: 10 },
  logoRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  logoPreview: { width: 84, height: 84, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F8FAFC', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  logoImg: { width: '100%', height: '100%' },
  logoBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: COLORS.primary, borderRadius: 10, paddingVertical: 11, paddingHorizontal: 14 },
  logoBtnText: { color: '#FFFFFF', fontWeight: '700', fontSize: 14 },
  logoResetBtn: { alignItems: 'center', paddingVertical: 6 },
  logoResetText: { color: '#DC2626', fontSize: 13, fontWeight: '600' },
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.white, borderRadius: 12, padding: 16, marginBottom: 10, borderWidth: 1.5, borderColor: COLORS.border },
  cardSel: { borderColor: COLORS.primary, backgroundColor: COLORS.primary + '08' },
  cardLabel: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  previewText: { fontSize: 14, color: COLORS.textSecondary, marginTop: 4 },
  note: { fontSize: 12, color: COLORS.textMuted, marginTop: 12, lineHeight: 18 },
});
