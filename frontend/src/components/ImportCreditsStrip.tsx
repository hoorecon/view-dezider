/**
 * ImportCreditsStrip — upfront credits preview for the URL-import flows.
 *
 * Shows "≈ N cr needed · M cr available" (history-based estimate from the
 * user's recent runs) with a Top-up shortcut when the balance falls short.
 *
 * When the user is short on credits, ALSO surfaces the OpenAI free-tier
 * opt-in inline — if the user enables data-sharing on their OpenAI org,
 * Deep Import / Import URL calls route to OpenAI's free tier (0 wallet
 * credits) and they may not need to top up at all.
 */
import React, { useEffect, useState } from 'react';
import {
  View, Text, TouchableOpacity, ActivityIndicator, StyleSheet, Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import api from '../utils/api';
import { showAlert } from '../utils/alert';

interface Props {
  endpoint: 'import' | 'deep_import';
  pages?: number;
  tier?: string;
}

const fmt = (v: number) =>
  Number(v ?? 0) >= 10000 ? `${(v / 1000).toFixed(1)}k` : `${Math.round(Number(v ?? 0))}`;

export const ImportCreditsStrip: React.FC<Props> = ({ endpoint, pages = 1, tier = 'fast' }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // OpenAI free-tier consent — shown inline when the user is short on credits
  // so they can opt into 0-credit AI calls without leaving the Deep Import /
  // Import URL flow. Lazily loaded the first time the strip flips to "short".
  const [consent, setConsent] = useState<{
    allow_openai: boolean; mode: string;
    openai_free_tier: boolean; openai_available: boolean;
  } | null>(null);
  const [consentLoading, setConsentLoading] = useState(false);
  const [savingConsent, setSavingConsent] = useState(false);

  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get('/ai-wallet/import-estimate', { params: { endpoint, pages, tier } })
      .then(r => { if (on) setData(r.data); })
      .catch(() => { if (on) setData(null); })
      .finally(() => { if (on) setLoading(false); });
    return () => { on = false; };
  }, [endpoint, pages, tier]);

  // Lazy-load consent only when the user is short (sufficient === false).
  // ⚠ Important: if the consent endpoint fails (404 / 401 / network) we MUST
  // still render the opt-in panel with a safe default — otherwise the panel
  // stays hidden forever and the user thinks the feature is missing.
  useEffect(() => {
    if (!data || data.sufficient || consent || consentLoading) return;
    let on = true;
    setConsentLoading(true);
    api.get('/ai-wallet/provider-consent')
      .then(r => { if (on) setConsent(r.data); })
      .catch(() => {
        // Fallback default — assumes nothing is set yet. The PUT below
        // will create the real consent doc if the user clicks "Enable".
        if (on) setConsent({
          allow_openai: false, mode: 'ask',
          openai_free_tier: false, openai_available: true,
        });
      })
      .finally(() => { if (on) setConsentLoading(false); });
    return () => { on = false; };
  }, [data, consent, consentLoading]);

  const enableFreeTier = async () => {
    if (!consent) return;
    setSavingConsent(true);
    try {
      const res = await api.put('/ai-wallet/provider-consent', {
        allow_openai: true, mode: consent.mode || 'always', openai_free_tier: true,
      });
      setConsent(res.data);
      showAlert(
        'Free-tier ON',
        'Your AI calls will now route to OpenAI free-tier first. You can change this anytime in AI Wallet → Provider settings.',
      );
    } catch (e: any) {
      showAlert('Could not enable', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setSavingConsent(false);
    }
  };

  if (loading) {
    return (
      <View style={[s.strip, s.neutral]} testID="import-credits-strip-loading">
        <ActivityIndicator size="small" color="#94A3B8" />
        <Text style={s.mutedTxt}>Checking your AI credits…</Text>
      </View>
    );
  }
  if (!data) return null;

  const ok = !!data.sufficient;
  const isScaled = data.basis === 'history_scaled';
  const isDefault = data.basis === 'default';

  // Always offer the free-tier opt-in when the user is short on credits.
  // We deliberately DON'T gate on `consent.openai_available` — the server
  // may or may not yet have OPENAI_API_KEY set, but the user-side consent
  // still needs to be captured. Once both align, AI calls route to OpenAI
  // free credits automatically.
  const showFreeTierPanel = !ok && consent && !consent.openai_free_tier;
  const freeTierAlreadyOn = !ok && consent && consent.openai_free_tier;

  return (
    <View testID="import-credits-strip-wrap">
      <View style={[s.strip, ok ? s.ok : s.bad]} testID="import-credits-strip">
        <Ionicons name={ok ? 'checkmark-circle' : 'alert-circle'} size={15}
          color={ok ? '#059669' : '#DC2626'} />
        <Text style={[s.txt, { color: ok ? '#065F46' : '#991B1B' }]} testID="import-credits-text">
          ≈ {fmt(data.estimate)} cr needed · {fmt(data.balance)} cr available
          {tier === 'precise' ? ' · Precise' : ' · Fast'}
          {isDefault ? ' (est.)' : ''}
          {isScaled ? ` (~${(data.tier_multiplier ?? 4.5).toFixed(1)}× scaled)` : ''}
        </Text>
        {!ok && (
          <TouchableOpacity testID="import-credits-topup-btn" style={s.topup}
            activeOpacity={0.85} onPress={() => router.push('/ai-wallet')}>
            <Ionicons name="flash" size={11} color="#FFF" />
            <Text style={s.topupTxt}>Top up</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Inline OpenAI free-tier opt-in — only when user is short on credits
          AND the server has an OpenAI key configured AND they haven't already
          opted in. Lets them skip the top-up entirely. */}
      {showFreeTierPanel && (
        <View style={s.ftPanel} testID="import-credits-freetier-panel">
          <View style={s.ftHeader}>
            <Ionicons name="sparkles" size={14} color="#7C3AED" />
            <Text style={s.ftTitle}>Skip the top-up — use OpenAI free-tier</Text>
          </View>
          <Text style={s.ftBody}>
            Enable data-sharing on your OpenAI organisation (
            <Text
              testID="import-credits-openai-link"
              style={s.ftLink}
              onPress={() => Linking.openURL('https://platform.openai.com/settings/organization/data-controls')}>
              platform.openai.com/settings/organization/data-controls
            </Text>
            ) and we'll route this Import / Deep Import to OpenAI free credits — your AI Wallet is{' '}
            <Text style={{ fontWeight: '800' }}>not charged</Text>. Your prompts may be used by OpenAI to improve models.
          </Text>
          <TouchableOpacity
            testID="import-credits-enable-freetier-btn"
            style={[s.ftBtn, savingConsent && { opacity: 0.6 }]}
            disabled={savingConsent}
            activeOpacity={0.85}
            onPress={enableFreeTier}>
            {savingConsent
              ? <ActivityIndicator size="small" color="#FFF" />
              : <><Ionicons name="checkmark-circle" size={13} color="#FFF" />
                  <Text style={s.ftBtnText}>I've enabled it — use free-tier</Text></>}
          </TouchableOpacity>
        </View>
      )}

      {freeTierAlreadyOn && (
        <View style={s.ftOnPanel} testID="import-credits-freetier-on-panel">
          <Ionicons name="checkmark-circle" size={13} color="#059669" />
          <Text style={s.ftOnText}>
            OpenAI free-tier is <Text style={{ fontWeight: '800' }}>ON</Text> — this run will use OpenAI free credits (0 cr charged) when available.
          </Text>
        </View>
      )}
    </View>
  );
};

const s = StyleSheet.create({
  strip: { flexDirection: 'row', alignItems: 'center', gap: 7, marginTop: 10, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 9, borderWidth: 1 },
  neutral: { backgroundColor: '#F8FAFC', borderColor: '#E2E8F0' },
  ok: { backgroundColor: '#ECFDF5', borderColor: '#A7F3D0' },
  bad: { backgroundColor: '#FEF2F2', borderColor: '#FECACA' },
  txt: { flex: 1, fontSize: 12, fontWeight: '700' },
  mutedTxt: { fontSize: 12, color: '#94A3B8', fontWeight: '600' },
  topup: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#DC2626', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14 },
  topupTxt: { fontSize: 11.5, fontWeight: '800', color: '#FFF' },

  ftPanel: { marginTop: 8, padding: 10, borderRadius: 9, borderWidth: 1, borderColor: '#DDD6FE', backgroundColor: '#F5F3FF' },
  ftHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  ftTitle: { fontSize: 12.5, fontWeight: '800', color: '#5B21B6' },
  ftBody: { fontSize: 11.5, color: '#4C1D95', lineHeight: 16, marginBottom: 8 },
  ftLink: { color: '#7C3AED', textDecorationLine: 'underline', fontWeight: '700' },
  ftBtn: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#7C3AED', paddingHorizontal: 11, paddingVertical: 6, borderRadius: 14 },
  ftBtnText: { color: '#FFF', fontSize: 11.5, fontWeight: '800' },

  ftOnPanel: { marginTop: 8, flexDirection: 'row', alignItems: 'center', gap: 6, padding: 8, borderRadius: 8, backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0' },
  ftOnText: { flex: 1, fontSize: 11.5, color: '#065F46', fontWeight: '600', lineHeight: 16 },
});

export default ImportCreditsStrip;
