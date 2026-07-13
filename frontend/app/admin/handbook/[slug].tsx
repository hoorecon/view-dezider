/**
 * Admin Docs viewer — detail page.
 *
 * Renders a single markdown doc with light-weight in-app formatting
 * (headings, bold, code blocks, lists). Falls back to monospaced text
 * for any raw chars we don't parse.
 */
import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Image, Platform, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { COLORS } from '../../../src/constants/colors';
import api from '../../../src/utils/api';
import { safeBack } from '../../../src/utils/navigation';

interface Doc {
  slug: string;
  title: string;
  body: string;
  version?: string;
  updated?: string;
}

// ----------------------------------------------------------------------
// Tiny markdown renderer (zero deps)
// ----------------------------------------------------------------------
function renderMarkdown(text: string) {
  const out: React.ReactElement[] = [];
  const lines = text.split('\n');
  let i = 0;
  let inCode = false;
  let codeBuf: string[] = [];
  let listBuf: string[] = [];

  const flushList = () => {
    if (listBuf.length) {
      out.push(
        <View key={`l${out.length}`} style={styles.listBlock}>
          {listBuf.map((line, idx) => (
            <View key={idx} style={styles.listRow}>
              <Text style={styles.bullet}>•</Text>
              <Text style={styles.listText}>{renderInline(line)}</Text>
            </View>
          ))}
        </View>
      );
      listBuf = [];
    }
  };
  const flushCode = () => {
    if (codeBuf.length) {
      out.push(
        <View key={`c${out.length}`} style={styles.codeBlock}>
          <Text style={styles.codeText}>{codeBuf.join('\n')}</Text>
        </View>
      );
      codeBuf = [];
    }
  };

  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith('```')) {
      if (inCode) { flushCode(); inCode = false; }
      else { flushList(); inCode = true; }
      i++;
      continue;
    }
    if (inCode) { codeBuf.push(line); i++; continue; }

    const imgMatch = line.match(/^!\[([^\]]*)\]\(([^)]+)\)\s*$/);
    if (imgMatch) {
      flushList();
      out.push(
        <Image
          key={i}
          source={{ uri: imgMatch[2] }}
          style={styles.docImage}
          resizeMode="contain"
          accessibilityLabel={imgMatch[1]}
        />
      );
      i++; continue;
    }

    if (/^#{1,6}\s/.test(line)) {
      flushList();
      const level = line.match(/^#{1,6}/)![0].length;
      const text = line.replace(/^#{1,6}\s+/, '');
      out.push(<Text key={i} style={[styles.h, level === 1 ? styles.h1 : level === 2 ? styles.h2 : styles.h3]}>{text}</Text>);
      i++; continue;
    }
    if (line.startsWith('|') && line.includes('|')) {
      // Table-ish — render as code-block monospace for now
      flushList();
      const tbl: string[] = [];
      while (i < lines.length && lines[i].startsWith('|')) {
        tbl.push(lines[i]); i++;
      }
      out.push(
        <View key={`t${out.length}`} style={styles.codeBlock}>
          <Text style={styles.codeText}>{tbl.join('\n')}</Text>
        </View>
      );
      continue;
    }
    if (/^[-*]\s/.test(line)) {
      listBuf.push(line.replace(/^[-*]\s+/, ''));
      i++; continue;
    }
    flushList();
    if (line.trim() === '') {
      out.push(<View key={i} style={styles.spacer} />);
    } else {
      out.push(<Text key={i} style={styles.p}>{renderInline(line)}</Text>);
    }
    i++;
  }
  flushList(); flushCode();
  return out;
}

function renderInline(text: string): React.ReactNode {
  // **bold** | `code` | _italic_
  const parts: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|_[^_]+_)/g;
  let last = 0; let key = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(<Text key={key++}>{text.slice(last, m.index)}</Text>);
    const tok = m[0];
    if (tok.startsWith('**')) parts.push(<Text key={key++} style={styles.bold}>{tok.slice(2, -2)}</Text>);
    else if (tok.startsWith('`')) parts.push(<Text key={key++} style={styles.inlineCode}>{tok.slice(1, -1)}</Text>);
    else if (tok.startsWith('_')) parts.push(<Text key={key++} style={styles.italic}>{tok.slice(1, -1)}</Text>);
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(<Text key={key++}>{text.slice(last)}</Text>);
  return parts;
}

export default function AdminDocDetailScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const slug = String(params.slug || '');
  const [doc, setDoc] = useState<Doc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      if (!slug) return;
      try {
        const res = await api.get(`/admin-docs/${slug}`);
        setDoc(res.data);
      } catch (e: any) {
        setError(e?.response?.status === 404 ? 'Doc not found' : 'Failed to load');
      } finally { setLoading(false); }
    })();
  }, [slug]);

  const [downloading, setDownloading] = useState(false);
  const downloadPdf = async () => {
    if (!slug) return;
    const fname = `${String(slug).toUpperCase()}.pdf`;
    setDownloading(true);
    try {
      if (Platform.OS === 'web') {
        const res = await api.get(`/admin-docs/${slug}/pdf`, { responseType: 'blob' });
        const url = window.URL.createObjectURL(res.data as Blob);
        const a = document.createElement('a');
        a.href = url; a.download = fname;
        document.body.appendChild(a); a.click(); a.remove();
        window.URL.revokeObjectURL(url);
      } else {
        const token = await AsyncStorage.getItem('session_token');
        const base = `${process.env.EXPO_PUBLIC_BACKEND_URL || ''}/api`;
        const fileUri = `${FileSystem.documentDirectory}${fname}`;
        const dl = await FileSystem.downloadAsync(
          `${base}/admin-docs/${slug}/pdf`, fileUri,
          { headers: token ? { Authorization: `Bearer ${token}` } : undefined },
        );
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(dl.uri, { mimeType: 'application/pdf', dialogTitle: fname, UTI: 'com.adobe.pdf' });
        }
      }
    } catch {
      const msg = 'Could not download the PDF. Please try again.';
      if (Platform.OS === 'web') window.alert(msg); else Alert.alert('Download failed', msg);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="chevron-back" size={26} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle} numberOfLines={1}>{doc?.title || slug}</Text>
          {!!doc?.version && (
            <Text style={styles.headerSub}>v{doc.version}{doc.updated ? ` · ${doc.updated}` : ''}</Text>
          )}
        </View>
        {doc && (
          <TouchableOpacity onPress={downloadPdf} style={styles.pdfBtn} disabled={downloading} accessibilityLabel="Download PDF">
            {downloading
              ? <ActivityIndicator size="small" color={COLORS.primary} />
              : <><Ionicons name="download-outline" size={16} color={COLORS.primary} /><Text style={styles.pdfBtnText}> PDF</Text></>}
          </TouchableOpacity>
        )}
      </View>
      {loading ? (
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
      ) : error ? (
        <Text style={styles.errText}>{error}</Text>
      ) : doc ? (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          showsVerticalScrollIndicator={true}
        >
          {renderMarkdown(doc.body)}
        </ScrollView>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, minHeight: 600, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingBottom: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  headerSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  pdfBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: COLORS.primary, borderRadius: 10, paddingVertical: 8, paddingHorizontal: 12, minWidth: 64, backgroundColor: COLORS.background },
  pdfBtnText: { color: COLORS.primary, fontWeight: '800', fontSize: 13 },
  h: { color: COLORS.textPrimary, fontWeight: '700', marginTop: 16, marginBottom: 8 },
  h1: { fontSize: 22 },
  h2: { fontSize: 18 },
  h3: { fontSize: 15 },
  p: { fontSize: 14, color: COLORS.textPrimary, lineHeight: 22, marginBottom: 6 },
  bold: { fontWeight: '700' },
  italic: { fontStyle: 'italic' },
  inlineCode: { fontFamily: 'Courier', fontSize: 13, backgroundColor: '#F3F4F6', paddingHorizontal: 4, borderRadius: 3 },
  codeBlock: { backgroundColor: '#0F172A', borderRadius: 8, padding: 12, marginVertical: 8 },
  codeText: { color: '#E2E8F0', fontFamily: 'Courier', fontSize: 11, lineHeight: 16 },
  docImage: { width: '100%', height: 220, borderRadius: 8, marginVertical: 8, backgroundColor: '#0F172A' },
  listBlock: { marginVertical: 4 },
  listRow: { flexDirection: 'row', gap: 6, paddingVertical: 1 },
  bullet: { color: COLORS.primary, fontSize: 14, fontWeight: '700' },
  listText: { flex: 1, fontSize: 14, color: COLORS.textPrimary, lineHeight: 22 },
  spacer: { height: 6 },
  errText: { textAlign: 'center', marginTop: 60, color: COLORS.error },
});
