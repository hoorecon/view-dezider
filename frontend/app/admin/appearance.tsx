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
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';
import { FONT_OPTIONS, getFontOption } from '../../src/constants/fonts';
import { useFontFamily, useAppLogo } from '../../src/contexts/FontFamilyContext';
import { useAuthStore } from '../../src/store/authStore';

export default function AdminAppearance() {
  const router = useRouter();
  const { fontKey, setFont, companyName: liveCompany, setCompanyName, refreshAppearance } = useFontFamily();
  const logoUri = useAppLogo();
  const user = useAuthStore((s) => s.user);
  const isSuperAdmin = user?.role === 'super_admin';
  const [selected, setSelected] = useState<string>(fontKey);
  const [companyInput, setCompanyInput] = useState<string>(liveCompany);
  const [savingCompany, setSavingCompany] = useState(false);
  const [logoBusy, setLogoBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get('/appearance');
      setSelected(r.data?.font_family || 'Inter');
      if (r.data?.company_name) setCompanyInput(r.data.company_name);
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Could not fetch appearance settings');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const saveCompany = useCallback(async () => {
    const name = companyInput.trim();
    if (name.length < 2) { showAlert('Invalid', 'Company name is too short.'); return; }
    setSavingCompany(true);
    try {
      await api.put('/admin/company-name', { company_name: name });
      setCompanyName(name);
      showAlert('Saved', 'Company name updated across the app.');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not save company name');
    } finally { setSavingCompany(false); }
  }, [companyInput, setCompanyName]);

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

          {/* Company name (Super Admin only) */}
          <View style={s.companyCard}>
            <Text style={s.sectionTitle}>Company / Legal Name</Text>
            <Text style={s.companyHint}>Used across legal pages, footer and the PII-access NDA.</Text>
            <View style={s.companyRow}>
              <TextInput
                style={[s.companyInput, !isSuperAdmin && { opacity: 0.6 }]}
                value={companyInput}
                onChangeText={setCompanyInput}
                editable={isSuperAdmin}
                placeholder="HOORECON IT-Sys Pvt Ltd"
                placeholderTextColor="#94A3B8"
              />
              {isSuperAdmin && (
                <TouchableOpacity style={[s.companySave, savingCompany && { opacity: 0.6 }]} onPress={saveCompany} disabled={savingCompany}>
                  {savingCompany ? <ActivityIndicator size="small" color="#FFF" /> : <Text style={s.companySaveText}>Save</Text>}
                </TouchableOpacity>
              )}
            </View>
            {!isSuperAdmin && <Text style={s.companyLocked}>Only a Super Admin can change the company name.</Text>}
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

          <Text style={s.sectionTitle}>App Font</Text>

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
