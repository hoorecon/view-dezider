/**
 * /tools/jitsi-room  — minimal public-Jitsi room for ExpertNet, instant connects, and webinars.
 *
 * Query params:
 *   room       — Jitsi room name (REQUIRED). Will be sanitised to alphanumeric+dash.
 *   name       — display name shown in the meeting (optional)
 *   subject    — topic shown in the meeting bar (optional)
 *   domain     — override jitsi domain (default meet.jit.si)
 *
 * Renders the Jitsi room inside a WebView on native; on web it injects the
 * external_api.js loader directly. Works without authentication — backend
 * mints unique room slugs (`vc_xxx`, `vc_wb_xxx`) that are effectively
 * unguessable secret URLs.
 */
import React, { useMemo, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator,
  Platform, Linking,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';

let WebView: any = null;
if (Platform.OS !== 'web') {
  try { WebView = require('react-native-webview').WebView; } catch { /* ignore */ }
}

function sanitiseRoom(r: string): string {
  return (r || '').replace(/[^a-zA-Z0-9_\-]/g, '').slice(0, 64) || `expert${Date.now()}`;
}

export default function JitsiRoomScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const room = sanitiseRoom(String(params.room || params.session_id || params.sessionId || ''));
  const displayName = String(params.name || 'Guest');
  const subject = String(params.subject || 'ExpertNet Session');
  const domain = String(params.domain || 'meet.jit.si');

  const [loaded, setLoaded] = useState(false);
  const webRef = useRef<any>(null);

  // The HTML payload renders Jitsi via its external API and auto-joins.
  const html = useMemo(() => `<!doctype html>
<html><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no" />
<title>${subject}</title>
<style>
  html,body,#root{height:100%;margin:0;padding:0;background:#000;overflow:hidden}
</style>
</head><body>
<div id="root"></div>
<script src="https://${domain}/external_api.js"></script>
<script>
  function start(){
    try {
      var api = new JitsiMeetExternalAPI('${domain}', {
        roomName: '${room}',
        parentNode: document.getElementById('root'),
        width: '100%', height: '100%',
        userInfo: { displayName: ${JSON.stringify(displayName)} },
        configOverwrite: {
          prejoinPageEnabled: false,
          startWithAudioMuted: false,
          startWithVideoMuted: false,
          subject: ${JSON.stringify(subject)},
          disableDeepLinking: true
        },
        interfaceConfigOverwrite: {
          MOBILE_APP_PROMO: false,
          SHOW_JITSI_WATERMARK: false,
          DEFAULT_BACKGROUND: '#000'
        }
      });
      api.addEventListener('readyToClose', function(){
        if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage('CLOSE');
        else window.history.back();
      });
    } catch (e) {
      document.body.innerHTML = '<div style="color:#fff;padding:24px;font-family:sans-serif">Could not load Jitsi. Tap Open externally.</div>';
    }
  }
  if (window.JitsiMeetExternalAPI) start();
  else window.addEventListener('load', start);
</script>
</body></html>`, [room, displayName, subject, domain]);

  if (!room) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.center}><Text style={styles.errText}>Missing room name</Text></View>
      </SafeAreaView>
    );
  }

  const externalUrl = `https://${domain}/${room}#userInfo.displayName=%22${encodeURIComponent(displayName)}%22`;

  const handleEnd = () => {
    try { router.back(); } catch { /* ignore */ }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={handleEnd} style={styles.iconBtn}>
          <Ionicons name="close" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title} numberOfLines={1}>{subject}</Text>
          <Text style={styles.subtitle} numberOfLines={1}>room: {room}</Text>
        </View>
        <TouchableOpacity onPress={() => Linking.openURL(externalUrl)} style={styles.iconBtn}>
          <Ionicons name="open-outline" size={20} color="#FFF" />
        </TouchableOpacity>
      </View>

      {Platform.OS === 'web' ? (
        // On web preview, use a plain iframe via dangerouslySetInnerHTML pattern
        <View style={{ flex: 1, backgroundColor: '#000' }} testID="jitsi-iframe">
          {/* @ts-ignore */}
          <iframe
            src={`https://${domain}/${room}#config.prejoinPageEnabled=false&userInfo.displayName=%22${encodeURIComponent(displayName)}%22`}
            allow="camera; microphone; fullscreen; display-capture; autoplay"
            style={{ flex: 1, width: '100%', height: '100%', border: 'none' }}
            onLoad={() => setLoaded(true)}
          />
        </View>
      ) : WebView ? (
        <WebView
          ref={webRef}
          originWhitelist={['*']}
          source={{ html, baseUrl: `https://${domain}/` }}
          javaScriptEnabled
          domStorageEnabled
          allowsInlineMediaPlayback
          mediaPlaybackRequiresUserAction={false}
          mixedContentMode="always"
          style={{ flex: 1, backgroundColor: '#000' }}
          onLoadEnd={() => setLoaded(true)}
          onMessage={(e: any) => {
            if (e?.nativeEvent?.data === 'CLOSE') handleEnd();
          }}
        />
      ) : (
        <View style={styles.center}>
          <Text style={styles.errText}>WebView unavailable.</Text>
          <TouchableOpacity onPress={() => Linking.openURL(externalUrl)} style={styles.openExternalBtn}>
            <Text style={styles.openExternalText}>Open in browser</Text>
          </TouchableOpacity>
        </View>
      )}

      {!loaded && (
        <View style={styles.loaderOverlay} pointerEvents="none">
          <ActivityIndicator color="#FFF" size="large" />
          <Text style={{ color: '#FFF', marginTop: 8, fontSize: 12 }}>Connecting to {domain}…</Text>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#000' },
  header: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 12, paddingVertical: 10,
    backgroundColor: '#0F172A',
  },
  iconBtn: { padding: 6 },
  title: { color: '#FFF', fontSize: 14, fontWeight: '700' },
  subtitle: { color: '#94A3B8', fontSize: 11 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  errText: { color: '#FFF', fontSize: 14 },
  openExternalBtn: { marginTop: 12, backgroundColor: COLORS.primary, paddingHorizontal: 18, paddingVertical: 10, borderRadius: 8 },
  openExternalText: { color: '#FFF', fontWeight: '700' },
  loaderOverlay: {
    position: 'absolute', top: 56, left: 0, right: 0, bottom: 0,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
});
