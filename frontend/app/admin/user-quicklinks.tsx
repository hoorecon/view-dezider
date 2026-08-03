import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

/**
 * /admin/user-quicklinks — configure the max-3 tiles that show under
 * "Quick Links" on the USER APP home (jelcos.ai). Independent from the
 * admin dashboard pins.
 */

type Tile = {
  key: string;
  label: string;
  subtitle: string;
  icon: string;
  color: string;
  href: string;
};

export default function AdminUserQuickLinksScreen() {
  const router = useRouter();
  const [available, setAvailable] = useState<Tile[]>([]);
  const [pinnedKeys, setPinnedKeys] = useState<string[]>([]);
  const [maxN, setMaxN] = useState(3);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => { (async () => {
    try {
      const r = await api.get('/admin/user-quicklinks');
      setAvailable(r.data?.available || []);
      setPinnedKeys(r.data?.pinned_keys || []);
      setMaxN(r.data?.max || 3);
    } catch { /* silent */ }
    setLoading(false);
  })(); }, []);

  const toggle = (k: string) => {
    setPinnedKeys((prev) => {
      if (prev.includes(k)) return prev.filter((x) => x !== k);
      if (prev.length >= maxN) {
        showAlert('Maximum reached', `Only ${maxN} tiles can be pinned in the user app's Quick Links. Unpin one first.`);
        return prev;
      }
      return [...prev, k];
    });
  };

  const move = (k: string, dir: -1 | 1) => {
    setPinnedKeys((prev) => {
      const i = prev.indexOf(k);
      if (i < 0) return prev;
      const j = i + dir;
      if (j < 0 || j >= prev.length) return prev;
      const next = [...prev];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      await api.put('/admin/user-quicklinks', { pinned_keys: pinnedKeys });
      showAlert('Saved', 'User app Quick Links updated. Users will see the new tiles on next page load.');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not save.');
    } finally { setSaving(false); }
  };

  if (loading) {
    return <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}><ActivityIndicator size="large" color={COLORS.primary} /></View>;
  }

  const pinnedTiles = pinnedKeys.map((k) => available.find((t) => t.key === k)).filter(Boolean) as Tile[];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>User App · Quick Links</Text>
        <TouchableOpacity onPress={save} disabled={saving}>
          {saving ? <ActivityIndicator size="small" color={COLORS.primary} /> :
            <Text style={styles.saveTxt}>Save</Text>}
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.info}>
          <Ionicons name="information-circle" size={18} color={COLORS.primary} />
          <Text style={styles.infoTxt}>
            Pick up to <Text style={{ fontWeight: '800' }}>{maxN}</Text> tiles to surface in the "Quick Links"
            section of the user home page (jelcos.ai). Order matters — use ↑/↓ to reorder.
          </Text>
        </View>

        <Text style={styles.section}>Pinned ({pinnedKeys.length}/{maxN})</Text>
        {pinnedTiles.length === 0 ? (
          <Text style={styles.empty}>Nothing pinned yet — tap any tile below to add it.</Text>
        ) : pinnedTiles.map((t, i) => (
          <View key={t.key} style={[styles.tile, { borderLeftColor: t.color }]}>
            <View style={[styles.icoWrap, { backgroundColor: t.color + '20' }]}>
              <Ionicons name={t.icon as any} size={18} color={t.color} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.tileLabel}>{t.label}</Text>
              <Text style={styles.tileSub}>{t.subtitle}</Text>
            </View>
            <TouchableOpacity onPress={() => move(t.key, -1)} disabled={i === 0} style={styles.chip}>
              <Ionicons name="arrow-up" size={14} color={i === 0 ? '#CCC' : COLORS.textPrimary} />
            </TouchableOpacity>
            <TouchableOpacity onPress={() => move(t.key, 1)} disabled={i === pinnedTiles.length - 1} style={styles.chip}>
              <Ionicons name="arrow-down" size={14} color={i === pinnedTiles.length - 1 ? '#CCC' : COLORS.textPrimary} />
            </TouchableOpacity>
            <TouchableOpacity onPress={() => toggle(t.key)} style={styles.chip}>
              <Ionicons name="close" size={16} color="#DC2626" />
            </TouchableOpacity>
          </View>
        ))}

        <Text style={styles.section}>Available modules</Text>
        {available.filter((t) => !pinnedKeys.includes(t.key)).map((t) => (
          <TouchableOpacity key={t.key} style={styles.tile} onPress={() => toggle(t.key)}>
            <View style={[styles.icoWrap, { backgroundColor: t.color + '20' }]}>
              <Ionicons name={t.icon as any} size={18} color={t.color} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.tileLabel}>{t.label}</Text>
              <Text style={styles.tileSub}>{t.subtitle}</Text>
            </View>
            <Ionicons name="add-circle" size={22} color={COLORS.primary} />
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12, backgroundColor: COLORS.surface, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  saveTxt: { color: COLORS.primary, fontWeight: '800', fontSize: 15 },
  scroll: { padding: 14, paddingBottom: 40 },
  info: { flexDirection: 'row', gap: 8, backgroundColor: COLORS.primary + '10', padding: 12, borderRadius: 10, marginBottom: 14 },
  infoTxt: { flex: 1, fontSize: 12.5, color: COLORS.textSecondary, lineHeight: 18 },
  section: { fontSize: 12, fontWeight: '800', color: COLORS.textMuted, letterSpacing: 1, textTransform: 'uppercase', marginTop: 14, marginBottom: 8 },
  empty: { color: COLORS.textMuted, fontSize: 12, fontStyle: 'italic', paddingVertical: 8 },
  tile: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.surface, borderRadius: 12, padding: 12, marginBottom: 8, borderLeftWidth: 4, borderLeftColor: COLORS.border, borderWidth: 1, borderColor: COLORS.border },
  icoWrap: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  tileLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  tileSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  chip: { width: 30, height: 30, borderRadius: 8, backgroundColor: '#F3F4F6', alignItems: 'center', justifyContent: 'center' },
});
