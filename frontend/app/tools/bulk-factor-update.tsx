import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, TextInput,
  ActivityIndicator, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams, Stack } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import * as Clipboard from 'expo-clipboard';
import * as Sharing from 'expo-sharing';
import * as FileSystem from 'expo-file-system/legacy';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack } from '../../src/utils/navigation';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

interface TokenInfo {
  token: string | null;
  auto_approve?: boolean;
  webhook_path: string;
  header_name: string;
  sample_payload: any;
}

export default function BulkFactorUpdate() {
  const params = useLocalSearchParams();
  const solutionId = String(params.solution_id || '');
  const solutionName = String(params.name || 'this solution');
  const { sessionToken } = useAuthStore();

  const [busy, setBusy] = useState<string | null>(null);
  const [sheetUrl, setSheetUrl] = useState('');
  const [tokenInfo, setTokenInfo] = useState<TokenInfo | null>(null);
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(true);

  const webhookUrl = tokenInfo ? `${API_URL}${tokenInfo.webhook_path}` : `${API_URL}/api/solutions-store/factor-values/webhook`;

  const loadMeta = useCallback(async () => {
    try {
      const [tk, subs] = await Promise.all([
        api.get(`/solutions-store/${solutionId}/ingestion-token`),
        api.get('/solutions-store/factor-submissions', { params: { status: 'all' } }),
      ]);
      setTokenInfo(tk.data);
      setSubmissions((subs.data?.items || []).filter((s: any) => s.solution_id === solutionId));
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not load integration details.');
    } finally {
      setLoadingMeta(false);
    }
  }, [solutionId]);

  useEffect(() => { if (solutionId) loadMeta(); }, [solutionId, loadMeta]);

  const refreshSubs = async () => {
    try {
      const subs = await api.get('/solutions-store/factor-submissions', { params: { status: 'all' } });
      setSubmissions((subs.data?.items || []).filter((s: any) => s.solution_id === solutionId));
    } catch { /* noop */ }
  };

  // ── 1) Download XLS template ──
  const downloadTemplate = async () => {
    setBusy('template');
    try {
      const url = `${API_URL}/api/solutions-store/factor-template.xlsx?solution_id=${encodeURIComponent(solutionId)}`;
      const token = sessionToken || (await AsyncStorage.getItem('session_token'));
      if (Platform.OS === 'web') {
        const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        if (!resp.ok) throw new Error('Download failed');
        const blob = await resp.blob();
        const a = (document as any).createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'factor_values_template.xlsx';
        a.click();
        URL.revokeObjectURL(a.href);
      } else {
        const fileUri = `${FileSystem.cacheDirectory}factor_values_template.xlsx`;
        const dl = await FileSystem.downloadAsync(url, fileUri, { headers: { Authorization: `Bearer ${token}` } });
        if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(dl.uri);
        else showAlert('Downloaded', `Template saved to ${dl.uri}`);
      }
    } catch (e: any) {
      showAlert('Download failed', e?.message || 'Please try again.');
    } finally {
      setBusy(null);
    }
  };

  // ── 2) Upload filled XLS ──
  const uploadXls = async () => {
    setBusy('upload');
    try {
      const picked = await DocumentPicker.getDocumentAsync({
        type: ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/octet-stream', '*/*'],
        copyToCacheDirectory: true,
      });
      if (picked.canceled || !picked.assets?.length) { setBusy(null); return; }
      const file = picked.assets[0];
      const form = new FormData();
      if (Platform.OS === 'web') {
        const blob = await (await fetch(file.uri)).blob();
        form.append('file', blob, file.name || 'upload.xlsx');
      } else {
        form.append('file', {
          uri: file.uri,
          name: file.name || 'upload.xlsx',
          type: file.mimeType || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        } as any);
      }
      const res = await api.post(
        `/solutions-store/factor-values/upload?solution_id=${encodeURIComponent(solutionId)}`,
        form,
      );
      showAlert('Submitted for review', `${res.data?.parsed_rows || 0} row(s) uploaded. An admin will review & approve them.`);
      refreshSubs();
    } catch (e: any) {
      showAlert('Upload failed', e?.response?.data?.detail || e?.message || 'Please try again.');
    } finally {
      setBusy(null);
    }
  };

  // ── 3) Import from Google Sheet ──
  const importGsheet = async () => {
    if (!sheetUrl.trim()) { showAlert('Link required', 'Paste a published/shared Google Sheet link.'); return; }
    setBusy('gsheet');
    try {
      const res = await api.post('/solutions-store/factor-values/import-gsheet', {
        sheet_url: sheetUrl.trim(),
        solution_id: solutionId,
      });
      showAlert('Submitted for review', `${res.data?.parsed_rows || 0} row(s) imported from the sheet. An admin will review & approve them.`);
      setSheetUrl('');
      refreshSubs();
    } catch (e: any) {
      showAlert('Import failed', e?.response?.data?.detail || 'Please check the link is public/published and try again.');
    } finally {
      setBusy(null);
    }
  };

  // ── 4) Webhook token ──
  const generateToken = async () => {
    setBusy('token');
    try {
      const res = await api.post(`/solutions-store/${solutionId}/ingestion-token`);
      setTokenInfo((prev) => ({ ...(prev as any), ...res.data }));
      showAlert('Token ready', 'A new ingestion token was generated. Update it in your 3rd-party system.');
    } catch (e: any) {
      showAlert('Could not generate token', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setBusy(null);
    }
  };

  const copy = async (label: string, value: string) => {
    await Clipboard.setStringAsync(value);
    showAlert('Copied', `${label} copied to clipboard.`);
  };

  const statusColor = (s: string) =>
    s === 'approved' ? '#15803D' : s === 'rejected' ? COLORS.error : '#B45309';

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }} style={{ width: 44 }}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>Bulk Factor Updates</Text>
        <View style={{ width: 44 }} />
      </View>

      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }} keyboardShouldPersistTaps="handled">
        <Text style={styles.sub} numberOfLines={2}>
          Update key factor values for <Text style={{ fontWeight: '800' }}>{solutionName}</Text> in bulk. All
          submissions are reviewed & approved by an admin before going live.
        </Text>

        {/* 1. XLS Template */}
        <View style={styles.card}>
          <View style={styles.cardHead}>
            <Ionicons name="grid-outline" size={18} color={COLORS.primary} />
            <Text style={styles.cardTitle}>1. Excel (.xlsx) template</Text>
          </View>
          <Text style={styles.cardDesc}>Download the template (pre-filled with current factors), edit values, then upload it back.</Text>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <TouchableOpacity style={[styles.btnOutline, { flex: 1 }]} onPress={downloadTemplate} disabled={busy === 'template'}>
              {busy === 'template' ? <ActivityIndicator size="small" color={COLORS.primary} /> : <Ionicons name="download-outline" size={16} color={COLORS.primary} />}
              <Text style={styles.btnOutlineText}>Template</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.btnPrimary, { flex: 1 }]} onPress={uploadXls} disabled={busy === 'upload'}>
              {busy === 'upload' ? <ActivityIndicator size="small" color="#FFF" /> : <Ionicons name="cloud-upload-outline" size={16} color="#FFF" />}
              <Text style={styles.btnPrimaryText}>Upload .xlsx</Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* 2. Google Sheet */}
        <View style={styles.card}>
          <View style={styles.cardHead}>
            <Ionicons name="logo-google" size={18} color={COLORS.primary} />
            <Text style={styles.cardTitle}>2. Google Sheet link</Text>
          </View>
          <Text style={styles.cardDesc}>Paste a “Published to web” or link-shareable sheet that follows the template columns.</Text>
          <TextInput
            style={styles.input}
            placeholder="https://docs.google.com/spreadsheets/d/.../pub?output=csv"
            placeholderTextColor={COLORS.textMuted}
            value={sheetUrl}
            onChangeText={setSheetUrl}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <TouchableOpacity style={styles.btnPrimary} onPress={importGsheet} disabled={busy === 'gsheet'}>
            {busy === 'gsheet' ? <ActivityIndicator size="small" color="#FFF" /> : <Ionicons name="sync-outline" size={16} color="#FFF" />}
            <Text style={styles.btnPrimaryText}>Import from Sheet</Text>
          </TouchableOpacity>
        </View>

        {/* 3. Webhook / API */}
        <View style={styles.card}>
          <View style={styles.cardHead}>
            <Ionicons name="git-network-outline" size={18} color={COLORS.primary} />
            <Text style={styles.cardTitle}>3. API / Webhook (live updates)</Text>
          </View>
          <Text style={styles.cardDesc}>
            Configure this endpoint in your system to push live factor values. Send a POST with your token in the header.
          </Text>

          {loadingMeta ? (
            <ActivityIndicator color={COLORS.primary} style={{ marginVertical: 12 }} />
          ) : (
            <>
              <Text style={styles.fieldLabel}>Endpoint URL (POST)</Text>
              <View style={styles.codeRow}>
                <Text style={styles.code} selectable numberOfLines={2}>{webhookUrl}</Text>
                <TouchableOpacity onPress={() => copy('Endpoint URL', webhookUrl)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
                  <Ionicons name="copy-outline" size={18} color={COLORS.primary} />
                </TouchableOpacity>
              </View>

              <Text style={styles.fieldLabel}>Header</Text>
              <View style={styles.codeRow}>
                <Text style={styles.code} selectable>{tokenInfo?.header_name || 'X-Ingestion-Token'}: &lt;token&gt;</Text>
              </View>

              <Text style={styles.fieldLabel}>Secret token</Text>
              {tokenInfo?.token ? (
                <View style={styles.codeRow}>
                  <Text style={styles.code} selectable numberOfLines={1}>{tokenInfo.token}</Text>
                  <TouchableOpacity onPress={() => copy('Token', tokenInfo.token as string)} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
                    <Ionicons name="copy-outline" size={18} color={COLORS.primary} />
                  </TouchableOpacity>
                </View>
              ) : (
                <Text style={[styles.cardDesc, { fontStyle: 'italic' }]}>No token yet. Generate one to enable the webhook.</Text>
              )}

              <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
                <TouchableOpacity style={[styles.btnOutline, { flex: 1 }]} onPress={generateToken} disabled={busy === 'token'}>
                  {busy === 'token' ? <ActivityIndicator size="small" color={COLORS.primary} /> : <Ionicons name="key-outline" size={16} color={COLORS.primary} />}
                  <Text style={styles.btnOutlineText}>{tokenInfo?.token ? 'Regenerate' : 'Generate token'}</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.btnOutline, { flex: 1 }]}
                  onPress={() => copy('Sample payload', JSON.stringify(tokenInfo?.sample_payload || {}, null, 2))}
                >
                  <Ionicons name="code-slash-outline" size={16} color={COLORS.primary} />
                  <Text style={styles.btnOutlineText}>Copy sample</Text>
                </TouchableOpacity>
              </View>
              <Text style={[styles.cardDesc, { marginTop: 8, fontSize: 11 }]}>
                Tip: regenerating invalidates the previous token. Webhook pushes are queued for admin approval
                {tokenInfo?.auto_approve ? ' (auto-approve is ON for this token).' : '.'}
              </Text>
            </>
          )}
        </View>

        {/* Submission status */}
        <View style={styles.card}>
          <View style={[styles.cardHead, { justifyContent: 'space-between' }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <Ionicons name="time-outline" size={18} color={COLORS.primary} />
              <Text style={styles.cardTitle}>Recent submissions</Text>
            </View>
            <TouchableOpacity onPress={refreshSubs} hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}>
              <Ionicons name="refresh" size={18} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>
          {submissions.length === 0 ? (
            <Text style={[styles.cardDesc, { fontStyle: 'italic' }]}>No submissions yet for this solution.</Text>
          ) : (
            submissions.map((s) => (
              <View key={s.submission_id} style={styles.subRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.subSource}>{(s.source || '').toUpperCase()} · {s.row_count} row(s)</Text>
                  <Text style={styles.subDate}>{new Date(s.created_at).toLocaleString()}</Text>
                </View>
                <View style={[styles.statusPill, { backgroundColor: statusColor(s.status) + '22' }]}>
                  <Text style={[styles.statusText, { color: statusColor(s.status) }]}>{s.status}</Text>
                </View>
              </View>
            ))
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary, flex: 1, textAlign: 'center' },
  sub: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19, marginBottom: 14 },
  card: { backgroundColor: COLORS.white, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, padding: 16, marginBottom: 14 },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  cardTitle: { fontSize: 15, fontWeight: '800', color: COLORS.textPrimary },
  cardDesc: { fontSize: 12.5, color: COLORS.textMuted, lineHeight: 18, marginBottom: 12 },
  btnPrimary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary, borderRadius: 10, paddingVertical: 12, paddingHorizontal: 14 },
  btnPrimaryText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  btnOutline: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderWidth: 1.5, borderColor: COLORS.primary, borderRadius: 10, paddingVertical: 11, paddingHorizontal: 14 },
  btnOutlineText: { color: COLORS.primary, fontWeight: '800', fontSize: 14 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, marginBottom: 12, backgroundColor: COLORS.background },
  fieldLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textSecondary, marginTop: 10, marginBottom: 4, textTransform: 'uppercase' },
  codeRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#0F172A', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 9 },
  code: { flex: 1, color: '#E2E8F0', fontSize: 12, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  subRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderTopWidth: 1, borderTopColor: COLORS.border },
  subSource: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  subDate: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  statusText: { fontSize: 11, fontWeight: '800', textTransform: 'capitalize' },
});
