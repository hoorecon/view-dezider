/**
 * Cross-platform in-app media player (YouTube / Vimeo / direct video).
 * Keeps users inside the app instead of bouncing them to the YouTube app.
 * Mirrors the EFT tool's embed approach: react-native-webview is NOT
 * supported on react-native-web, so on web we render a real DOM iframe/video;
 * on native we use a WebView with an HTML document.
 */
import React from 'react';
import { Modal, View, Text, TouchableOpacity, Platform, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { WebView } from 'react-native-webview';

const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';

function buildMediaHtml(rawUrl: string): string {
  let url = (rawUrl || '').trim();
  if (url.startsWith('/')) url = `${BACKEND}${url}`;
  const lower = url.toLowerCase();
  let inner = '';
  if (/\.(mp4|webm|ogg|mov)(\?|$)/.test(lower)) {
    inner = `<video controls playsinline style="width:100%;height:100%;background:#000" src="${url}"></video>`;
  } else if (lower.includes('youtube.com') || lower.includes('youtu.be')) {
    const m1 = url.match(/[?&]v=([^&]+)/);
    const m2 = url.match(/youtu\.be\/([^?&]+)/);
    const m3 = url.match(/embed\/([^?&]+)/);
    const id = (m1 && m1[1]) || (m2 && m2[1]) || (m3 && m3[1]) || '';
    inner = `<iframe src="https://www.youtube.com/embed/${id}" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="width:100%;height:100%"></iframe>`;
  } else if (lower.includes('vimeo.com')) {
    const m = url.match(/vimeo\.com\/(?:video\/)?(\d+)(?:\/([0-9a-zA-Z]+))?/);
    const id = m ? m[1] : '';
    const hash = m && m[2] ? `?h=${m[2]}` : '';
    inner = `<iframe src="https://player.vimeo.com/video/${id}${hash}" frameborder="0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen style="width:100%;height:100%"></iframe>`;
  } else {
    inner = `<iframe src="${url}" frameborder="0" allowfullscreen style="width:100%;height:100%"></iframe>`;
  }
  return `<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>*{margin:0;padding:0;box-sizing:border-box}html,body{height:100%;background:#000;overflow:hidden}</style></head><body>${inner}</body></html>`;
}

function resolveMediaSrc(rawUrl: string): { kind: 'video' | 'iframe'; src: string } {
  let url = (rawUrl || '').trim();
  if (url.startsWith('/')) url = `${BACKEND}${url}`;
  const lower = url.toLowerCase();
  if (/\.(mp4|webm|ogg|mov)(\?|$)/.test(lower)) return { kind: 'video', src: url };
  if (lower.includes('youtube.com') || lower.includes('youtu.be')) {
    const m1 = url.match(/[?&]v=([^&]+)/);
    const m2 = url.match(/youtu\.be\/([^?&]+)/);
    const m3 = url.match(/embed\/([^?&]+)/);
    const id = (m1 && m1[1]) || (m2 && m2[1]) || (m3 && m3[1]) || '';
    return { kind: 'iframe', src: `https://www.youtube.com/embed/${id}` };
  }
  if (lower.includes('vimeo.com')) {
    const m = url.match(/vimeo\.com\/(?:video\/)?(\d+)(?:\/([0-9a-zA-Z]+))?/);
    const id = m ? m[1] : '';
    const hash = m && m[2] ? `?h=${m[2]}` : '';
    return { kind: 'iframe', src: `https://player.vimeo.com/video/${id}${hash}` };
  }
  return { kind: 'iframe', src: url };
}

function MediaEmbed({ url }: { url: string }) {
  if (Platform.OS === 'web') {
    const { kind, src } = resolveMediaSrc(url);
    const style: any = { width: '100%', height: '100%', border: '0', backgroundColor: '#000' };
    if (kind === 'video') return React.createElement('video', { src, controls: true, playsInline: true, style });
    return React.createElement('iframe', {
      src, style, allowFullScreen: true,
      allow: 'autoplay; fullscreen; picture-in-picture; encrypted-media',
    });
  }
  return (
    <WebView
      source={{ html: buildMediaHtml(url) }}
      style={{ flex: 1, backgroundColor: '#000' }}
      originWhitelist={['*']}
      javaScriptEnabled
      allowsFullscreenVideo
    />
  );
}

export default function InAppVideoModal({
  url, title, visible, onClose,
}: { url: string; title?: string; visible: boolean; onClose: () => void }) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.header}>
            <Text style={s.title} numberOfLines={1}>{title || 'Now playing'}</Text>
            <TouchableOpacity onPress={onClose} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
              <Ionicons name="close" size={24} color="#FFF" />
            </TouchableOpacity>
          </View>
          <View style={s.player}>
            {visible && !!url && <MediaEmbed url={url} />}
          </View>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.85)', justifyContent: 'center', padding: 12 },
  sheet: { backgroundColor: '#000', borderRadius: 14, overflow: 'hidden', maxWidth: 900, width: '100%', alignSelf: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#111' },
  title: { color: '#FFF', fontSize: 15, fontWeight: '700', flex: 1, marginRight: 12 },
  player: { width: '100%', aspectRatio: 16 / 9, backgroundColor: '#000' },
});
