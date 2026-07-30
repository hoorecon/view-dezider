/**
 * Admin · Homepage Variant selector.
 * Choose which hero design renders at jelcos.ai — Classic Purple or Modern Grid.
 */
import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack } from '../../src/utils/navigation';

type Option = { slug: string; label: string; description: string };

export default function AdminHomeVariantScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const role = (user?.role || '').toLowerCase();
  const isAdmin = role === 'super_admin' || role === 'admin';
  const [active, setActive] = useState<string>('modern');
  const [options, setOptions] = useState<Option[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/home-variant');
      setActive(r.data?.active || 'modern');
      setOptions(r.data?.options || []);
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Could not load.');
    } finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { if (isAdmin) fetchData(); }, [isAdmin, fetchData]));

  const setVariant = async (slug: string) => {
    setSaving(slug);
    try {
      await api.put('/admin/home-variant', { variant: slug });
      setActive(slug);
      showAlert('Saved', `Homepage is now using the ${slug} variant. Visitors see it immediately.`);
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not save.');
    } finally { setSaving(''); }
  };

  const openPreview = (slug: string) => {
    if (Platform.OS === 'web') window.open(`/?variant=${slug}`, '_blank');
  };

  if (!isAdmin) return <SafeAreaView style={styles.container}><Text style={styles.gate}>Super-admin access only.</Text></SafeAreaView>;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router, '/admin')} style={{ padding: 4 }}>
          <Ionicons name="chevron-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Homepage Variant</Text>
      </View>

      {loading ? <ActivityIndicator color={COLORS.primary} style={{ marginTop: 40 }} /> : (
        <ScrollView contentContainerStyle={styles.scroll}>
          <View style={styles.infoCard}>
            <Ionicons name="information-circle" size={18} color={COLORS.primary} />
            <Text style={styles.infoText}>
              Choose which hero design shows on <Text style={{ fontWeight: '700' }}>jelcos.ai</Text> (guest / logged-out visitors).
              Switching takes effect immediately for new page loads. Preview opens the variant in a new tab
              via <Text style={{ fontFamily: Platform.select({ web: 'monospace', default: 'System' }) }}>?variant=…</Text>
              without changing the persisted default.
            </Text>
          </View>

          {options.map((o) => {
            const isActive = o.slug === active;
            return (
              <View key={o.slug} style={[styles.card, isActive && styles.cardActive]}>
                <View style={styles.cardHead}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.label}>{o.label}</Text>
                    <Text style={styles.slug}>variant = {o.slug}</Text>
                    <Text style={styles.desc}>{o.description}</Text>
                  </View>
                  {isActive && (
                    <View style={styles.activeBadge}>
                      <Ionicons name="checkmark-circle" size={14} color="#059669" />
                      <Text style={styles.activeBadgeT}>Active</Text>
                    </View>
                  )}
                </View>
                <View style={styles.actions}>
                  {Platform.OS === 'web' && (
                    <TouchableOpacity style={styles.previewBtn} onPress={() => openPreview(o.slug)}>
                      <Ionicons name="eye-outline" size={14} color={COLORS.primary} />
                      <Text style={styles.previewT}>Preview</Text>
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity
                    style={[styles.setBtn, isActive && styles.setBtnDisabled]}
                    disabled={isActive || saving === o.slug}
                    onPress={() => setVariant(o.slug)}
                  >
                    {saving === o.slug ? <ActivityIndicator color={COLORS.white} /> : (
                      <Text style={styles.setBtnT}>{isActive ? 'Currently Active' : 'Set as Default'}</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            );
          })}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  gate: { fontSize: 14, color: COLORS.textMuted, textAlign: 'center', marginTop: 40 },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.border, backgroundColor: COLORS.white },
  headerTitle: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary, marginLeft: 8 },
  scroll: { padding: 12, paddingBottom: 40, maxWidth: 800, width: '100%', alignSelf: 'center' },
  infoCard: { flexDirection: 'row', gap: 8, backgroundColor: '#EEF2FF', padding: 12, borderRadius: 12, marginBottom: 14 },
  infoText: { flex: 1, fontSize: 12, color: COLORS.textSecondary, lineHeight: 18 },
  card: { backgroundColor: COLORS.white, borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  cardActive: { borderColor: '#059669', backgroundColor: '#F0FDF4' },
  cardHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  label: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary },
  slug: { fontSize: 10, color: COLORS.textMuted, marginTop: 2, fontFamily: Platform.select({ web: 'monospace', default: 'System' }) },
  desc: { fontSize: 13, color: COLORS.textSecondary, marginTop: 6, lineHeight: 19 },
  activeBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#DCFCE7', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 999 },
  activeBadgeT: { fontSize: 10, color: '#059669', fontWeight: '800' },
  actions: { flexDirection: 'row', gap: 8, marginTop: 12 },
  previewBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.background },
  previewT: { fontSize: 12, color: COLORS.primary, fontWeight: '600' },
  setBtn: { flex: 1, backgroundColor: COLORS.primary, paddingVertical: 10, borderRadius: 8, alignItems: 'center' },
  setBtnDisabled: { backgroundColor: '#CBD5E1' },
  setBtnT: { color: COLORS.white, fontWeight: '700', fontSize: 13 },
});
