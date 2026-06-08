import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';
import { LIFE_AREAS } from '../../src/constants/lifeAreas';
import { safeBack, goHome } from '../../src/utils/navigation';
import api from '../../src/utils/api';
import UrlAccessConsentModal, { UrlConsentPayload } from '../../src/components/UrlAccessConsentModal';

type Target = 'mydezider' | 'pros_cons';

export default function AnalyseUrlScreen() {
  const router = useRouter();
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [target, setTarget] = useState<Target>('mydezider');
  const [lifeArea, setLifeArea] = useState<string | null>(null);
  const [decisionType, setDecisionType] = useState('');
  const [consentOpen, setConsentOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const validUrl = /^https?:\/\/.+/i.test(url.trim());

  const startAnalyse = () => {
    if (!validUrl) { showAlert('Enter a URL', 'Paste a valid http(s) link to a comparison or filter page.'); return; }
    setConsentOpen(true);
  };

  const runAnalyse = async (consent: UrlConsentPayload) => {
    setBusy(true);
    try {
      const { data } = await api.post('/url-analyze', {
        url: url.trim(),
        eligibility_type: consent.eligibility_type,
        custom_note: consent.custom_note,
        accepted: true,
        target,
        title: title.trim() || undefined,
        life_area: lifeArea || undefined,
        decision_type: decisionType.trim() || undefined,
      });
      setConsentOpen(false);
      setBusy(false);
      showAlert(
        'Decision ready',
        `Built from ${data.item_count} items and ${data.factor_count} factors. Opening the assessment…`,
        [{ text: 'Open', onPress: () => {
          if (data.target === 'pros_cons') router.replace(`/tools/pros-cons-wizard?id=${data.id}&module=pros-cons` as any);
          else router.replace(`/prr/${data.id}` as any);
        } }]
      );
    } catch (e: any) {
      setBusy(false);
      const msg = e?.response?.data?.detail || 'Could not analyse this URL. Try a page that lists items in a table.';
      showAlert('Analyse failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <LinearGradient colors={['#0F172A', '#1E3A5F']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.header}>
        <TouchableOpacity testID="analyse-url-back" onPress={() => safeBack(router)} style={styles.hBtn}>
          <Ionicons name="arrow-back" size={22} color="#fff" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.hTitle}>Analyse a URL</Text>
          <Text style={styles.hSub}>Turn any comparison page into a decision</Text>
        </View>
        <TouchableOpacity testID="analyse-url-home" onPress={() => goHome(router)} style={styles.hBtn}>
          <Ionicons name="home" size={20} color="#fff" />
        </TouchableOpacity>
      </LinearGradient>

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTapping="handled">
          <View style={styles.infoCard}>
            <Ionicons name="sparkles" size={18} color="#2563EB" />
            <Text style={styles.infoText}>
              Paste a comparison / filter page (funds, phones, cars, plans…). We extract the items
              and their attributes, derive weighted factors, and pre-fill a decision — ready to assess.
            </Text>
          </View>

          <Text style={styles.label}>Page URL</Text>
          <TextInput
            testID="analyse-url-input"
            style={styles.input}
            placeholder="https://example.com/compare?filter=…"
            placeholderTextColor="#9CA3AF"
            value={url}
            onChangeText={setUrl}
            autoCapitalize="none"
            keyboardType="url"
          />

          <Text style={styles.label}>Build as</Text>
          <View style={styles.seg}>
            {([['mydezider', 'MyDezider', 'git-branch'], ['pros_cons', 'Pros & Cons', 'layers']] as const).map(([k, l, ic]) => {
              const on = target === k;
              return (
                <TouchableOpacity key={k} testID={`analyse-url-target-${k}`} style={[styles.segBtn, on && styles.segBtnOn]} onPress={() => setTarget(k as Target)}>
                  <Ionicons name={ic as any} size={15} color={on ? '#fff' : COLORS.textSecondary} />
                  <Text style={[styles.segText, on && { color: '#fff' }]}>{l}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={styles.label}>Title <Text style={styles.opt}>(optional)</Text></Text>
          <TextInput
            testID="analyse-url-title"
            style={styles.input}
            placeholder="e.g. Best multi-cap fund for me"
            placeholderTextColor="#9CA3AF"
            value={title}
            onChangeText={setTitle}
          />

          <Text style={styles.label}>Life area <Text style={styles.opt}>(pick one)</Text></Text>
          <View style={styles.chips}>
            {LIFE_AREAS.map(la => {
              const on = lifeArea === la.id;
              return (
                <TouchableOpacity key={la.id} testID={`analyse-url-life-${la.id}`} style={[styles.chip, on && styles.chipOn]} onPress={() => setLifeArea(on ? null : la.id)}>
                  <Ionicons name={la.icon as any} size={13} color={on ? '#fff' : COLORS.textSecondary} />
                  <Text style={[styles.chipText, on && { color: '#fff' }]}>{la.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={styles.label}>Decision type <Text style={styles.opt}>(optional)</Text></Text>
          <TextInput
            testID="analyse-url-type"
            style={styles.input}
            placeholder="e.g. Investment, Purchase, Hiring…"
            placeholderTextColor="#9CA3AF"
            value={decisionType}
            onChangeText={setDecisionType}
          />

          <TouchableOpacity
            testID="analyse-url-submit"
            style={[styles.cta, !validUrl && { opacity: 0.5 }]}
            onPress={startAnalyse}
            disabled={!validUrl || busy}
          >
            <Ionicons name="shield-checkmark" size={18} color="#fff" />
            <Text style={styles.ctaText}>Review consent & analyse</Text>
          </TouchableOpacity>

          <Text style={styles.note}>
            You&apos;ll be asked to confirm your access rights before we fetch the page. View Dezider only
            acts on your behalf and never bypasses paywalls or logins.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>

      <UrlAccessConsentModal
        visible={consentOpen}
        url={url.trim()}
        busy={busy}
        primary="#2563EB"
        onCancel={() => { if (!busy) setConsentOpen(false); }}
        onConfirm={runAnalyse}
      />

      {busy && !consentOpen && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color="#2563EB" />
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingVertical: 14 },
  hBtn: { padding: 4 },
  hTitle: { fontSize: 18, fontWeight: '800', color: '#fff' },
  hSub: { fontSize: 12, color: 'rgba(255,255,255,0.8)', marginTop: 1 },
  body: { padding: 18, paddingBottom: 60 },
  infoCard: { flexDirection: 'row', gap: 10, backgroundColor: '#EFF6FF', borderRadius: 12, padding: 13, marginBottom: 18, borderWidth: 1, borderColor: '#BFDBFE' },
  infoText: { flex: 1, fontSize: 12.5, lineHeight: 18, color: '#1E40AF' },
  label: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 7, marginTop: 4 },
  opt: { fontSize: 11, fontWeight: '500', color: COLORS.textMuted },
  input: { borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 11, paddingHorizontal: 13, paddingVertical: 11, fontSize: 14, color: COLORS.textPrimary, backgroundColor: '#fff', marginBottom: 14 },
  seg: { flexDirection: 'row', gap: 8, marginBottom: 14 },
  segBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 11, borderRadius: 11, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#fff' },
  segBtnOn: { backgroundColor: '#2563EB', borderColor: '#2563EB' },
  segText: { fontSize: 13, fontWeight: '700', color: COLORS.textSecondary },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 11, paddingVertical: 7, borderRadius: 18, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#fff' },
  chipOn: { backgroundColor: '#2563EB', borderColor: '#2563EB' },
  chipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 9, backgroundColor: '#2563EB', paddingVertical: 15, borderRadius: 13, marginTop: 8 },
  ctaText: { fontSize: 15, fontWeight: '800', color: '#fff' },
  note: { fontSize: 11.5, color: COLORS.textMuted, lineHeight: 17, marginTop: 12, textAlign: 'center' },
  loadingOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(255,255,255,0.6)', justifyContent: 'center', alignItems: 'center' },
});
