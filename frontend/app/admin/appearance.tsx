/**
 * /admin/appearance — Admin UI to pick the app-wide font family.
 *
 * Reads/writes GET|PUT /api/appearance. Selecting a font saves it server-side
 * AND applies it live via FontFamilyContext so the admin sees the change
 * instantly (on web). Default is Inter (matches jelcos.ai).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';
import { FONT_OPTIONS, getFontOption } from '../../src/constants/fonts';
import { useFontFamily } from '../../src/contexts/FontFamilyContext';

export default function AdminAppearance() {
  const router = useRouter();
  const { fontKey, setFont } = useFontFamily();
  const [selected, setSelected] = useState<string>(fontKey);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get('/appearance');
      setSelected(r.data?.font_family || 'Inter');
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Could not fetch appearance settings');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

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
  card: { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.white, borderRadius: 12, padding: 16, marginBottom: 10, borderWidth: 1.5, borderColor: COLORS.border },
  cardSel: { borderColor: COLORS.primary, backgroundColor: COLORS.primary + '08' },
  cardLabel: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  previewText: { fontSize: 14, color: COLORS.textSecondary, marginTop: 4 },
  note: { fontSize: 12, color: COLORS.textMuted, marginTop: 12, lineHeight: 18 },
});
