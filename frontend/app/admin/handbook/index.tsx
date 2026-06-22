/**
 * Admin Docs viewer — list page.
 *
 * Renders the catalogue of markdown docs (PRD/SRS/API/UAT/ACM/...) so admins
 * can read them in-app on mobile.
 */
import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../src/constants/colors';
import api from '../../../src/utils/api';
import { safeBack } from '../../../src/utils/navigation';

interface DocMeta {
  slug: string;
  title: string;
  size_bytes: number;
  version?: string;
  updated?: string;
}

const ICONS: Record<string, string> = {
  INDEX: 'list',
  PRD: 'rocket',
  SRS: 'cog',
  API_REFERENCE: 'code-slash',
  POSTMAN: 'paper-plane',
  REGRESSION: 'shield-checkmark',
  UAT: 'people',
  ACM: 'lock-closed',
  WOWO: 'folder',
  CLD: 'git-branch',
  SECURITY: 'shield',
  DEPLOYMENT: 'cloud-upload',
};

export default function AdminDocsListScreen() {
  const router = useRouter();
  const [items, setItems] = useState<DocMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/admin-docs');
        setItems(res.data?.items || []);
      } catch (e: any) {
        if (e?.response?.status === 401 || e?.response?.status === 403) {
          setError('Admin access required.');
        } else {
          setError('Failed to load docs.');
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={26} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Admin Documentation</Text>
          <Text style={styles.headerSub}>PRD · SRS · API · UAT · ACM · Security · Deployment</Text>
        </View>
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
      ) : error ? (
        <View style={styles.errCard}>
          <Ionicons name="lock-closed" size={28} color="#9CA3AF" />
          <Text style={styles.errTitle}>Cannot load docs</Text>
          <Text style={styles.errBody}>{error}</Text>
        </View>
      ) : items.length === 0 ? (
        <View style={styles.errCard}>
          <Ionicons name="document-outline" size={28} color="#9CA3AF" />
          <Text style={styles.errTitle}>No documents found</Text>
          <Text style={styles.errBody}>The /app/docs directory appears empty in the backend container.</Text>
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.countLabel}>{items.length} documents available</Text>
          {items.map(it => (
            <TouchableOpacity
              key={it.slug}
              style={styles.card}
              onPress={() => router.push(`/admin/handbook/${it.slug}` as any)}
            >
              <View style={[styles.iconBubble, { backgroundColor: COLORS.primary + '15' }]}>
                <Ionicons name={(ICONS[it.slug] || 'document-text') as any} size={22} color={COLORS.primary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.cardTitle}>{it.title}</Text>
                <View style={styles.cardMeta}>
                  {it.version ? <Text style={styles.cardMetaText}>v{it.version}</Text> : null}
                  {it.updated ? <Text style={styles.cardMetaText}>· {it.updated}</Text> : null}
                  <Text style={styles.cardMetaText}>· {Math.ceil(it.size_bytes / 1024)} KB</Text>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={20} color={COLORS.textMuted} />
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, minHeight: 600, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingBottom: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  headerSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  countLabel: { fontSize: 12, color: COLORS.textMuted, marginBottom: 12, fontWeight: '600' },
  card: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: COLORS.white, padding: 14, borderRadius: 12,
    borderWidth: 1, borderColor: COLORS.border, marginBottom: 10,
  },
  iconBubble: { width: 44, height: 44, borderRadius: 22, justifyContent: 'center', alignItems: 'center' },
  cardTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  cardMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 },
  cardMetaText: { fontSize: 11, color: COLORS.textMuted },
  errCard: { padding: 24, alignItems: 'center', marginTop: 80 },
  errTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 12 },
  errBody: { fontSize: 12, color: COLORS.textMuted, marginTop: 6, textAlign: 'center' },
});
