/**
 * Admin → EFT Tapping for Stress Relief configuration.
 * Lets an admin configure the EFT sub-module: enable/disable, copy,
 * affirmation templates, tapping points (+order), diagram image & video
 * (external URL OR in-app upload), disclaimer and safety keywords.
 * Backed by GET/PUT /api/emotional-gatekeeper/eft/admin/config and
 * POST /api/emotional-gatekeeper/eft/admin/upload-media.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView,
  ActivityIndicator, Switch, Image, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';
import { safeBack } from '../../src/utils/navigation';

const TEAL = '#0D9488';
const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface TapPoint { id: string; name: string; instruction: string; is_setup?: boolean; image_url?: string; }
interface EftCfg {
  enabled: boolean; title: string; description: string;
  affirmation_template_emotion: string; affirmation_template_problem: string;
  alt_affirmation_template_emotion: string; alt_affirmation_template_problem: string;
  tapping_instructions: string; tapping_points: TapPoint[];
  diagram_image_url: string; video_url: string;
  disclaimer: string; safety_keywords: string[]; safety_message: string;
}

const abs = (u: string) => (u && u.startsWith('/') ? `${BACKEND}${u}` : u);

export default function AdminEftConfig() {
  const router = useRouter();
  const [cfg, setCfg] = useState<EftCfg | null>(null);
  const [defaults, setDefaults] = useState<EftCfg | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [kwText, setKwText] = useState('');
  const [uploading, setUploading] = useState<'image' | 'video' | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/emotional-gatekeeper/eft/admin/config');
      setCfg(r.data.config);
      setDefaults(r.data.defaults);
      setKwText((r.data.config.safety_keywords || []).join(', '));
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not load EFT config.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const set = (k: keyof EftCfg, v: any) => setCfg((c) => (c ? { ...c, [k]: v } : c));

  const setPoint = (idx: number, field: 'name' | 'instruction' | 'image_url', value: string) => {
    setCfg((c) => {
      if (!c) return c;
      const pts = [...c.tapping_points];
      pts[idx] = { ...pts[idx], [field]: value };
      return { ...c, tapping_points: pts };
    });
  };
  const movePoint = (idx: number, dir: -1 | 1) => {
    setCfg((c) => {
      if (!c) return c;
      const pts = [...c.tapping_points];
      const j = idx + dir;
      if (j < 0 || j >= pts.length) return c;
      [pts[idx], pts[j]] = [pts[j], pts[idx]];
      return { ...c, tapping_points: pts };
    });
  };
  const removePoint = (idx: number) => setCfg((c) => (c ? { ...c, tapping_points: c.tapping_points.filter((_, i) => i !== idx) } : c));
  const addPoint = () => setCfg((c) => (c ? { ...c, tapping_points: [...c.tapping_points, { id: `pt_${Date.now()}`, name: 'New Point', instruction: '' }] } : c));
  const resetPoints = () => defaults && setCfg((c) => (c ? { ...c, tapping_points: JSON.parse(JSON.stringify(defaults.tapping_points)) } : c));

  const uploadMedia = useCallback(async (kind: 'image' | 'video') => {
    try {
      const types = kind === 'image'
        ? ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
        : ['video/mp4', 'video/webm', 'video/quicktime', 'video/ogg'];
      const res = await DocumentPicker.getDocumentAsync({ type: types, multiple: false, copyToCacheDirectory: true });
      if (res.canceled || !res.assets?.length) return;
      const a = res.assets[0];
      const cap = kind === 'image' ? 8 : 50;
      if (a.size && a.size > cap * 1024 * 1024) {
        showAlert('Too large', `${kind === 'image' ? 'Image' : 'Video'} must be ${cap} MB or smaller. For long videos, paste an external URL (Vimeo/YouTube) instead.`);
        return;
      }
      let blob: Blob | null = null;
      let mime = (a.mimeType || (kind === 'image' ? 'image/jpeg' : 'video/mp4')).toLowerCase();
      if (Platform.OS === 'web' && (a as any).file) {
        blob = (a as any).file as File;
        if (blob.type) mime = blob.type;
      } else if (a.uri) {
        const r = await fetch(a.uri);
        blob = await r.blob();
        if (blob.type) mime = blob.type || mime;
      }
      if (!blob) { showAlert('Unsupported', 'Could not read the file.'); return; }

      setUploading(kind);
      const form = new FormData();
      form.append('file', blob as any, a.name || `eft-${kind}`);
      const up = await api.post(`/emotional-gatekeeper/eft/admin/upload-media?media_type=${kind}`, form, {
        headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120_000,
      });
      const url = up.data.url as string;
      set(kind === 'image' ? 'diagram_image_url' : 'video_url', url);
      showAlert('Uploaded', `${kind === 'image' ? 'Image' : 'Video'} uploaded. Don't forget to Save.`);
    } catch (e: any) {
      showAlert('Upload failed', e?.response?.data?.detail || e?.message || 'Could not upload the file.');
    } finally { setUploading(null); }
  }, []);

  const save = useCallback(async () => {
    if (!cfg) return;
    setSaving(true);
    try {
      const payload = {
        ...cfg,
        safety_keywords: kwText.split(',').map((s) => s.trim()).filter(Boolean),
      };
      await api.put('/emotional-gatekeeper/eft/admin/config', payload);
      showAlert('Saved', 'EFT Tapping configuration updated.');
      await load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not save.');
    } finally { setSaving(false); }
  }, [cfg, kwText, load]);

  if (loading || !cfg) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingWrap}><ActivityIndicator size="large" color={TEAL} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>EFT Tapping Config</Text>
        <TouchableOpacity onPress={save} disabled={saving} testID="eft-cfg-save" style={styles.saveBtn}>
          {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.saveBtnTxt}>Save</Text>}
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Enable */}
        <View style={styles.rowCard}>
          <View style={{ flex: 1 }}>
            <Text style={styles.rowLabel}>Enable this sub-module</Text>
            <Text style={styles.rowHint}>When off, EFT is hidden from the Emotional Gatekeepers hub.</Text>
          </View>
          <Switch
            testID="eft-cfg-enabled"
            value={cfg.enabled} onValueChange={(v) => set('enabled', v)}
            trackColor={{ true: TEAL, false: COLORS.border }}
          />
        </View>

        <Field label="Sub-module title" value={cfg.title} onChange={(v) => set('title', v)} testID="eft-cfg-title" />
        <Field label="Short description" value={cfg.description} onChange={(v) => set('description', v)} multiline />

        <Section title="Affirmation Templates" hint="Use {input} where the user's emotion or problem should appear." />
        <Field label="Emotion (default)" value={cfg.affirmation_template_emotion} onChange={(v) => set('affirmation_template_emotion', v)} multiline />
        <Field label="Problem (default)" value={cfg.affirmation_template_problem} onChange={(v) => set('affirmation_template_problem', v)} multiline />
        <Field label="Emotion (alternative)" value={cfg.alt_affirmation_template_emotion} onChange={(v) => set('alt_affirmation_template_emotion', v)} multiline />
        <Field label="Problem (alternative)" value={cfg.alt_affirmation_template_problem} onChange={(v) => set('alt_affirmation_template_problem', v)} multiline />

        <Section title="Tapping Instructions" />
        <Field label="General instruction (shown before tapping)" value={cfg.tapping_instructions} onChange={(v) => set('tapping_instructions', v)} multiline />

        <Section title="Tapping Points & Order" hint={`${cfg.tapping_points.length} points`} />
        {cfg.tapping_points.map((p, i) => (
          <View key={p.id || i} style={styles.pointCard} testID={`eft-cfg-point-${i}`}>
            <View style={styles.pointHead}>
              <Text style={styles.pointNum}>{i + 1}</Text>
              <View style={styles.pointActions}>
                <TouchableOpacity onPress={() => movePoint(i, -1)} disabled={i === 0}><Ionicons name="arrow-up" size={18} color={i === 0 ? COLORS.border : TEAL} /></TouchableOpacity>
                <TouchableOpacity onPress={() => movePoint(i, 1)} disabled={i === cfg.tapping_points.length - 1}><Ionicons name="arrow-down" size={18} color={i === cfg.tapping_points.length - 1 ? COLORS.border : TEAL} /></TouchableOpacity>
                <TouchableOpacity onPress={() => removePoint(i)}><Ionicons name="trash" size={18} color={COLORS.error} /></TouchableOpacity>
              </View>
            </View>
            <TextInput style={styles.pointInput} value={p.name} onChangeText={(t) => setPoint(i, 'name', t)} placeholder="Point name" placeholderTextColor={COLORS.textMuted} />
            <TextInput style={[styles.pointInput, { minHeight: 56 }]} value={p.instruction} onChangeText={(t) => setPoint(i, 'instruction', t)} placeholder="Tapping instruction" placeholderTextColor={COLORS.textMuted} multiline />
            <TextInput style={styles.pointInput} value={p.image_url || ''} onChangeText={(t) => setPoint(i, 'image_url', t)} placeholder="Image URL for this point (optional — falls back to the diagram)" placeholderTextColor={COLORS.textMuted} autoCapitalize="none" />
            {!!p.image_url && <Image source={{ uri: abs(p.image_url) }} style={styles.pointThumb} resizeMode="contain" />}
          </View>
        ))}
        <View style={styles.btnRow}>
          <TouchableOpacity style={styles.ghostBtn} onPress={addPoint}><Ionicons name="add" size={16} color={TEAL} /><Text style={styles.ghostBtnTxt}>Add point</Text></TouchableOpacity>
          <TouchableOpacity style={styles.ghostBtn} onPress={resetPoints}><Ionicons name="refresh" size={16} color={COLORS.textMuted} /><Text style={[styles.ghostBtnTxt, { color: COLORS.textMuted }]}>Reset to default</Text></TouchableOpacity>
        </View>

        {/* Diagram */}
        <Section title="Tapping Points Diagram" />
        <Field label="Image URL" value={cfg.diagram_image_url} onChange={(v) => set('diagram_image_url', v)} />
        {!!cfg.diagram_image_url && (
          <Image source={{ uri: abs(cfg.diagram_image_url) }} style={styles.preview} resizeMode="contain" />
        )}
        <View style={styles.btnRow}>
          <TouchableOpacity style={styles.uploadBtn} onPress={() => uploadMedia('image')} disabled={uploading === 'image'} testID="eft-cfg-upload-image">
            {uploading === 'image' ? <ActivityIndicator color="#FFF" size="small" /> : <><Ionicons name="cloud-upload" size={16} color="#FFF" /><Text style={styles.uploadBtnTxt}>Upload image</Text></>}
          </TouchableOpacity>
          <TouchableOpacity style={styles.ghostBtn} onPress={() => defaults && set('diagram_image_url', defaults.diagram_image_url)}>
            <Ionicons name="refresh" size={16} color={COLORS.textMuted} /><Text style={[styles.ghostBtnTxt, { color: COLORS.textMuted }]}>Default</Text>
          </TouchableOpacity>
        </View>

        {/* Video */}
        <Section title="Tapping Instruction Video" hint="External URL (Vimeo/YouTube/MP4) or upload a file (≤50 MB)." />
        <Field label="Video URL" value={cfg.video_url} onChange={(v) => set('video_url', v)} />
        <View style={styles.btnRow}>
          <TouchableOpacity style={styles.uploadBtn} onPress={() => uploadMedia('video')} disabled={uploading === 'video'} testID="eft-cfg-upload-video">
            {uploading === 'video' ? <ActivityIndicator color="#FFF" size="small" /> : <><Ionicons name="cloud-upload" size={16} color="#FFF" /><Text style={styles.uploadBtnTxt}>Upload video</Text></>}
          </TouchableOpacity>
          <TouchableOpacity style={styles.ghostBtn} onPress={() => defaults && set('video_url', defaults.video_url)}>
            <Ionicons name="refresh" size={16} color={COLORS.textMuted} /><Text style={[styles.ghostBtnTxt, { color: COLORS.textMuted }]}>Default</Text>
          </TouchableOpacity>
        </View>

        {/* Safety */}
        <Section title="Safety" hint="Comma-separated keywords trigger the gentle support message." />
        <Field label="Safety keywords" value={kwText} onChange={setKwText} multiline />
        <Field label="Safety message" value={cfg.safety_message} onChange={(v) => set('safety_message', v)} multiline />

        <Section title="Disclaimer" />
        <Field label="Disclaimer text" value={cfg.disclaimer} onChange={(v) => set('disclaimer', v)} multiline />

        <TouchableOpacity style={styles.saveWide} onPress={save} disabled={saving} testID="eft-cfg-save-bottom">
          {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveWideTxt}>Save Configuration</Text>}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

function Field({ label, value, onChange, multiline, testID }: { label: string; value: string; onChange: (v: string) => void; multiline?: boolean; testID?: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        testID={testID}
        style={[styles.input, multiline && { minHeight: 70, textAlignVertical: 'top' }]}
        value={value} onChangeText={onChange} multiline={multiline}
        placeholderTextColor={COLORS.textMuted}
      />
    </View>
  );
}

function Section({ title, hint }: { title: string; hint?: string }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {!!hint && <Text style={styles.sectionHint}>{hint}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: COLORS.border },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: COLORS.background, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: COLORS.textPrimary },
  saveBtn: { backgroundColor: TEAL, paddingHorizontal: 18, paddingVertical: 9, borderRadius: 10, minWidth: 64, alignItems: 'center' },
  saveBtnTxt: { color: '#FFF', fontWeight: '700' },
  scroll: { padding: 16, paddingBottom: 60 },

  rowCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 12, padding: 16, borderWidth: 1, borderColor: COLORS.border, marginBottom: 14 },
  rowLabel: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  rowHint: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },

  field: { marginBottom: 14 },
  fieldLabel: { fontSize: 13, fontWeight: '700', color: COLORS.textSecondary, marginBottom: 6 },
  input: { backgroundColor: '#FFF', borderRadius: 10, padding: 12, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border },

  section: { marginTop: 10, marginBottom: 10 },
  sectionTitle: { fontSize: 16, fontWeight: '800', color: TEAL },
  sectionHint: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },

  pointCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 10 },
  pointHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  pointNum: { width: 26, height: 26, borderRadius: 13, backgroundColor: TEAL, color: '#FFF', textAlign: 'center', lineHeight: 26, fontWeight: '800' },
  pointActions: { flexDirection: 'row', gap: 16, alignItems: 'center' },
  pointInput: { backgroundColor: COLORS.background, borderRadius: 8, padding: 10, fontSize: 13, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border, marginTop: 6 },
  pointThumb: { width: '100%', height: 120, borderRadius: 8, marginTop: 6, backgroundColor: '#FFF', borderWidth: 1, borderColor: COLORS.border },

  btnRow: { flexDirection: 'row', gap: 10, marginBottom: 16, marginTop: 4, alignItems: 'center' },
  ghostBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FFF' },
  ghostBtnTxt: { fontSize: 13, fontWeight: '700', color: TEAL },
  uploadBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingVertical: 11, borderRadius: 10, backgroundColor: TEAL },
  uploadBtnTxt: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  preview: { width: '100%', height: 220, borderRadius: 12, backgroundColor: '#FFF', borderWidth: 1, borderColor: COLORS.border, marginBottom: 10 },

  saveWide: { backgroundColor: TEAL, paddingVertical: 16, borderRadius: 12, alignItems: 'center', marginTop: 20 },
  saveWideTxt: { color: '#FFF', fontSize: 16, fontWeight: '800' },
});
