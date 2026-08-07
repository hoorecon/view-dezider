import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ActivityIndicator, TouchableOpacity, Platform, Share, Linking,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

/**
 * Public share landing: /s/[slug]
 * Fetches the short URL, shows the title + share message + Share/Continue buttons.
 * On web, auto-redirects to target after 2.5s unless user opens the Share sheet.
 * On mobile, requires an explicit "Continue" tap.
 */

type Payload = {
  slug: string;
  title: string;
  target_href: string;
  share_message: string;
  share_subject?: string;
  share_body_email?: string;
  share_body_whatsapp?: string;
  kind: 'template' | 'app' | 'custom';
  active: boolean;
};

export default function ShortUrlScreen() {
  const router = useRouter();
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await api.get(`/short/${slug}`);
        if (mounted) setData(r.data);
      } catch (e: any) {
        if (mounted) setError(e?.response?.data?.detail || 'Link not found or inactive.');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [slug]);

  const publicBase = (typeof window !== 'undefined' && window.location?.origin) || 'https://jelcos.ai';
  const shareUrl = `${publicBase}/s/${slug}`;

  // Substitute [LINK] with the short URL. If the admin body doesn't include
  // [LINK] we append the URL on a new line so recipients can still click.
  const withLink = (body: string): string => {
    if (!body) return shareUrl;
    return body.includes('[LINK]') ? body.replace(/\[LINK\]/g, shareUrl) : `${body}\n${shareUrl}`;
  };
  const emailSubject = () => (data?.share_subject && data.share_subject.trim())
    || (data?.title ? `Try "${data.title}"` : 'Have a look');
  const emailBody = () => withLink((data?.share_body_email || data?.share_message || '').trim());
  const whatsappBody = () => withLink((data?.share_body_whatsapp || data?.share_message || '').trim());

  const onShare = async () => {
    if (!data) return;
    const message = withLink((data.share_message || data.title || '').trim());
    try {
      if (Platform.OS !== 'web') {
        await Share.share({ message, url: shareUrl, title: data.title });
      } else if ((navigator as any).share) {
        // Web Share API on desktop Gmail integration only forwards URL — so
        // we bake the message INTO the url-safe text field. Recipients see
        // both the pre-filled body and the tracked short URL.
        await (navigator as any).share({ title: data.title, text: message, url: shareUrl });
      } else {
        await Clipboard.setStringAsync(message);
        showAlert('Copied', 'Share message + link copied to clipboard.');
      }
    } catch { /* user cancelled */ }
  };

  const onEmail = () => {
    if (!data) return;
    const subject = encodeURIComponent(emailSubject());
    const body = encodeURIComponent(emailBody());
    const href = `mailto:?subject=${subject}&body=${body}`;
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      // Some browsers block window.location = 'mailto:' from an async
      // handler; open in a new window so the mail client actually launches.
      const w = window.open(href, '_blank');
      if (!w) window.location.href = href;
    } else {
      Linking.openURL(href).catch(() => {});
    }
  };

  const onWhatsApp = () => {
    if (!data) return;
    const text = encodeURIComponent(whatsappBody());
    const href = `https://wa.me/?text=${text}`;
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      window.open(href, '_blank');
    } else {
      Linking.openURL(href).catch(() => {});
    }
  };

  const onContinue = async () => {
    if (!data) return;
    // For external URLs → Linking.openURL. Internal → router.replace.
    if (/^https?:\/\//i.test(data.target_href)) {
      Linking.openURL(data.target_href).catch(() => {});
    } else {
      router.replace(data.target_href as any);
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} />
      </SafeAreaView>
    );
  }
  if (error || !data) {
    return (
      <SafeAreaView style={styles.container}>
        <Ionicons name="alert-circle" size={44} color="#DC2626" />
        <Text style={styles.err}>{error || 'Link not found.'}</Text>
        <TouchableOpacity style={[styles.btn, { backgroundColor: COLORS.primary }]} onPress={() => router.replace('/' as any)}>
          <Text style={styles.btnTxt}>Go home</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.card}>
        <View style={styles.kind}><Text style={styles.kindTxt}>{data.kind.toUpperCase()}</Text></View>
        <Text style={styles.title}>{data.title}</Text>
        {data.share_message ? <Text style={styles.body}>{data.share_message}</Text> : null}
        <Text style={styles.mono}>{shareUrl}</Text>
        <View style={styles.row}>
          <TouchableOpacity style={[styles.btn, { backgroundColor: '#DC2626' }]} onPress={onEmail}>
            <Ionicons name="mail" size={16} color="#FFF" />
            <Text style={styles.btnTxt}>Email</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.btn, { backgroundColor: '#16A34A' }]} onPress={onWhatsApp}>
            <Ionicons name="logo-whatsapp" size={16} color="#FFF" />
            <Text style={styles.btnTxt}>WhatsApp</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.btn, { backgroundColor: '#0EA5E9' }]} onPress={onShare}>
            <Ionicons name="share-social" size={16} color="#FFF" />
            <Text style={styles.btnTxt}>Share</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.btn, { backgroundColor: '#0F172A' }]} onPress={onContinue}>
            <Text style={styles.btnTxt}>Continue →</Text>
          </TouchableOpacity>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background, alignItems: 'center', justifyContent: 'center', padding: 20 },
  card: { backgroundColor: '#FFF', borderRadius: 16, padding: 22, width: '100%', maxWidth: 480, alignItems: 'center', shadowColor: '#000', shadowOpacity: 0.08, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
  kind: { backgroundColor: '#EEF2FF', paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999, marginBottom: 12 },
  kindTxt: { fontSize: 10, fontWeight: '800', color: '#4F46E5', letterSpacing: 1 },
  title: { fontSize: 22, fontWeight: '800', color: COLORS.textPrimary, textAlign: 'center' },
  body: { marginTop: 10, fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', lineHeight: 20 },
  mono: { marginTop: 14, fontSize: 11, color: COLORS.textMuted, fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  row: { flexDirection: 'row', gap: 10, marginTop: 20 },
  btn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 18, paddingVertical: 10, borderRadius: 999 },
  btnTxt: { color: '#FFF', fontWeight: '800', fontSize: 13 },
  err: { color: '#DC2626', fontSize: 14, marginTop: 8, marginBottom: 16, textAlign: 'center' },
});
