/**
 * Admin · Manifestation Content (CAB-FAME)
 * Edit all Manifestation text (mantras, affirmations, instructions) and the
 * YouTube / resource URLs used across the 7 stages. Stored as a global
 * SuperAdmin override; changes apply to every user. "Reset to default"
 * removes the override and restores the built-in framework.
 *
 * A structured JSON editor is used so every field (including future ones)
 * stays editable without shipping a new screen each time.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, TextInput, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

export default function AdminManifestationContentScreen() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [isOverride, setIsOverride] = useState(false);
  const [text, setText] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/goal-manifestation/admin/framework');
      setText(JSON.stringify(r.data?.stages ?? [], null, 2));
      setIsOverride(!!r.data?.is_override);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not load content');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    let parsed: any;
    try {
      parsed = JSON.parse(text);
    } catch {
      showAlert('Invalid JSON', 'The content is not valid JSON. Fix the highlighted syntax and try again.');
      return;
    }
    if (!Array.isArray(parsed) || parsed.length === 0) {
      showAlert('Invalid', 'Content must be a non-empty list of stages.');
      return;
    }
    setSaving(true);
    try {
      await api.put('/goal-manifestation/admin/framework', { stages: parsed });
      setIsOverride(true);
      showAlert('Saved', 'Manifestation content updated for all users.');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not save');
    } finally {
      setSaving(false);
    }
  };

  const reset = async () => {
    setSaving(true);
    try {
      const r = await api.post('/goal-manifestation/admin/framework/reset', {});
      setText(JSON.stringify(r.data?.stages ?? [], null, 2));
      setIsOverride(false);
      showAlert('Reset', 'Restored the built-in default content.');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not reset');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#7C3AED', '#A855F7']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.header}>
        <TouchableOpacity onPress={() => safeBack('/admin')} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Manifestation Content</Text>
          <Text style={s.headerSub}>CAB-FAME · 7-stage text & video URLs</Text>
        </View>
        <View style={[s.badge, { backgroundColor: isOverride ? '#FEF3C7' : 'rgba(255,255,255,0.2)' }]}>
          <Text style={[s.badgeTxt, { color: isOverride ? '#B45309' : '#FFF' }]}>{isOverride ? 'CUSTOM' : 'DEFAULT'}</Text>
        </View>
      </LinearGradient>

      {loading ? (
        <View style={s.centered}><ActivityIndicator size="large" color="#7C3AED" /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16 }} showsVerticalScrollIndicator keyboardShouldPersistTaps="handled">
          <View style={s.tip}>
            <Ionicons name="information-circle" size={16} color="#1D4ED8" />
            <Text style={s.tipTxt}>
              Each stage has fields like name, summary, audio_url and a list of steps. Within a step you can edit
              title, instruction, content (the mantra/affirmation text), followup, link (YouTube/resource URL) and
              link_label. Keep the JSON structure intact. YouTube links play in-app automatically.
            </Text>
          </View>

          <TextInput
            style={s.editor}
            value={text}
            onChangeText={setText}
            multiline
            autoCapitalize="none"
            autoCorrect={false}
            spellCheck={false}
            textAlignVertical="top"
            placeholder="[ ... CAB-FAME stages JSON ... ]"
          />

          <View style={s.row}>
            <TouchableOpacity style={[s.btn, { backgroundColor: '#7C3AED' }]} onPress={save} disabled={saving}>
              {saving ? <ActivityIndicator color="#FFF" size="small" /> : (<><Ionicons name="save" size={16} color="#FFF" /><Text style={s.btnTxt}>Save for all users</Text></>)}
            </TouchableOpacity>
            <TouchableOpacity style={[s.btn, s.btnGhost]} onPress={reset} disabled={saving}>
              <Ionicons name="refresh" size={16} color="#7C3AED" />
              <Text style={[s.btnTxt, { color: '#7C3AED' }]}>Reset to default</Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity onPress={load} style={{ marginTop: 12, alignItems: 'center' }}>
            <Text style={{ color: '#6B7280', fontSize: 13, fontWeight: '600' }}>Reload (discard edits)</Text>
          </TouchableOpacity>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingTop: 12, paddingBottom: 18, gap: 12 },
  backBtn: { padding: 4 },
  headerTitle: { color: '#FFF', fontSize: 18, fontWeight: '800' },
  headerSub: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  badge: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8 },
  badgeTxt: { fontSize: 11, fontWeight: '800' },
  tip: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', backgroundColor: '#EFF6FF', padding: 12, borderRadius: 12, marginBottom: 12 },
  tipTxt: { flex: 1, fontSize: 12, lineHeight: 18, color: '#1D4ED8' },
  editor: {
    minHeight: 380, borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 12, padding: 12,
    fontSize: 12, color: '#111827', backgroundColor: '#FFF',
    fontFamily: Platform.select({ ios: 'Menlo', android: 'monospace', default: 'monospace' }),
  },
  row: { flexDirection: 'row', gap: 10, marginTop: 14 },
  btn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 13, borderRadius: 12 },
  btnGhost: { backgroundColor: '#F3E8FF' },
  btnTxt: { color: '#FFF', fontSize: 14, fontWeight: '700' },
});
