/**
 * /admin/publisher-defaults — set the default Publisher Contact block that
 * gets attached to every Admin-authored (jAI Verified) Template + Decider
 * App when the publisher doesn't supply their own lead_gen.
 *
 * These defaults apply globally. Per-item overrides live on the standard
 * `lead_gen` block edited from the Edit-Template modal or the Decider
 * Store admin page (per-row pencil — future cycle).
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TextInput, TouchableOpacity, ActivityIndicator, ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';

interface Cfg {
  contact_name?: string; organization?: string; designation?: string;
  email?: string; whatsapp?: string; mobile?: string; redirect_url?: string;
}

export default function AdminPublisherDefaults() {
  const router = useRouter();
  const [cfg, setCfg] = useState<Cfg>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/publisher-defaults');
      setCfg(r.data || {});
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not load config');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.patch('/admin/publisher-defaults', cfg);
      setCfg(r.data || cfg);
      showAlert('Saved', 'Default Publisher Contact updated. Applies to admin items without their own lead_gen.');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Save failed');
    } finally { setSaving(false); }
  };

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.headerTitle}>Default Publisher Contact</Text>
      </View>
      {loading ? <ActivityIndicator color={COLORS.primary} style={{ marginTop: 40 }} /> : (
        <ScrollView contentContainerStyle={{ padding: 16, gap: 8 }}>
          <Text style={s.help}>These defaults are attached to every admin-authored (jAI Verified) template & Decider App when the publisher hasn&apos;t supplied their own lead_gen block. Publishers can still override on a per-item basis via the Edit Template modal.</Text>
          <Text style={s.label}>Contact person name</Text>
          <TextInput style={s.input} value={cfg.contact_name || ''} onChangeText={(v) => setCfg({ ...cfg, contact_name: v })} />
          <Text style={s.label}>Organization</Text>
          <TextInput style={s.input} value={cfg.organization || ''} onChangeText={(v) => setCfg({ ...cfg, organization: v })} />
          <Text style={s.label}>Designation</Text>
          <TextInput style={s.input} value={cfg.designation || ''} onChangeText={(v) => setCfg({ ...cfg, designation: v })} />
          <Text style={s.label}>Email</Text>
          <TextInput style={s.input} value={cfg.email || ''} onChangeText={(v) => setCfg({ ...cfg, email: v })} keyboardType="email-address" autoCapitalize="none" />
          <Text style={s.label}>WhatsApp</Text>
          <TextInput style={s.input} value={cfg.whatsapp || ''} onChangeText={(v) => setCfg({ ...cfg, whatsapp: v })} keyboardType="phone-pad" />
          <Text style={s.label}>Mobile</Text>
          <TextInput style={s.input} value={cfg.mobile || ''} onChangeText={(v) => setCfg({ ...cfg, mobile: v })} keyboardType="phone-pad" />
          <Text style={s.label}>Website / Redirect URL</Text>
          <TextInput style={s.input} value={cfg.redirect_url || ''} onChangeText={(v) => setCfg({ ...cfg, redirect_url: v })} autoCapitalize="none" />
          <TouchableOpacity style={s.saveBtn} onPress={save} disabled={saving} testID="admin-pub-defaults-save">
            {saving ? <ActivityIndicator color="#FFF" /> : (<>
              <Ionicons name="save" size={16} color="#FFF" />
              <Text style={s.saveBtnText}>Save & apply to admin items</Text>
            </>)}
          </TouchableOpacity>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F1F5F9' },
  header: { flexDirection: 'row', gap: 10, padding: 14, backgroundColor: COLORS.primary, alignItems: 'center' },
  headerTitle: { color: '#FFF', fontSize: 16, fontWeight: '800' },
  help: { fontSize: 12.5, color: COLORS.textSecondary, fontStyle: 'italic', marginBottom: 6, lineHeight: 17 },
  label: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginTop: 6 },
  input: { backgroundColor: '#FFF', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: '#E2E8F0' },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary, paddingVertical: 14, borderRadius: 12, marginTop: 14 },
  saveBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14.5 },
});
