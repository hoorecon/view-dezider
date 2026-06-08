import React, { useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, TextInput, Modal, ScrollView,
  ActivityIndicator, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';

export interface UrlConsentPayload {
  eligibility_type: 'own' | 'partner' | 'free_public' | 'custom';
  custom_note?: string;
}

const ELIGIBILITY: { key: UrlConsentPayload['eligibility_type']; label: string; desc: string; icon: string }[] = [
  { key: 'own', label: 'My own site', desc: 'I own or operate this website / data', icon: 'home' },
  { key: 'partner', label: 'Partner site', desc: 'I have a partnership / written permission to use this data', icon: 'people' },
  { key: 'free_public', label: 'Free / public site', desc: 'Publicly accessible data whose terms permit personal analysis', icon: 'globe' },
  { key: 'custom', label: 'Other (specify)', desc: 'Describe the basis for my access right', icon: 'create' },
];

interface Props {
  visible: boolean;
  url?: string;
  busy?: boolean;
  primary?: string;
  onCancel: () => void;
  onConfirm: (payload: UrlConsentPayload) => void;
}

/**
 * Mandatory legal + site-access-rights consent gate shown BEFORE any pasted URL
 * is fetched/crawled. The user must (1) pick an access-eligibility type and
 * (2) accept the disclaimer. Used by both the standalone "Analyse a URL" flow
 * and the partner Screener paste-URL mode.
 */
export const UrlAccessConsentModal: React.FC<Props> = ({
  visible, url, busy, primary = COLORS.primary, onCancel, onConfirm,
}) => {
  const [elig, setElig] = useState<UrlConsentPayload['eligibility_type'] | null>(null);
  const [customNote, setCustomNote] = useState('');
  const [accepted, setAccepted] = useState(false);

  const canProceed = !!elig && accepted && (elig !== 'custom' || customNote.trim().length > 0);

  const reset = () => { setElig(null); setCustomNote(''); setAccepted(false); };
  const handleCancel = () => { reset(); onCancel(); };
  const handleConfirm = () => {
    if (!canProceed || !elig) return;
    onConfirm({ eligibility_type: elig, custom_note: elig === 'custom' ? customNote.trim() : undefined });
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={handleCancel}>
      <View style={styles.overlay}>
        <View style={styles.card}>
          <View style={styles.header}>
            <Ionicons name="shield-checkmark" size={22} color={primary} />
            <Text style={styles.title}>Data-access consent</Text>
            <TouchableOpacity testID="url-consent-close" onPress={handleCancel} style={styles.closeBtn}>
              <Ionicons name="close" size={22} color={COLORS.textMuted} />
            </TouchableOpacity>
          </View>

          <ScrollView style={{ maxHeight: 420 }} showsVerticalScrollIndicator={false}>
            {!!url && (
              <View style={styles.urlBox}>
                <Ionicons name="link" size={14} color={COLORS.textSecondary} />
                <Text style={styles.urlText} numberOfLines={2}>{url}</Text>
              </View>
            )}

            <Text style={styles.q}>What is your right to access this data?</Text>
            {ELIGIBILITY.map(opt => {
              const on = elig === opt.key;
              return (
                <TouchableOpacity
                  key={opt.key}
                  testID={`url-consent-elig-${opt.key}`}
                  activeOpacity={0.8}
                  style={[styles.opt, on && { borderColor: primary, backgroundColor: primary + '0F' }]}
                  onPress={() => setElig(opt.key)}
                >
                  <Ionicons name={(on ? 'radio-button-on' : 'radio-button-off') as any} size={18} color={on ? primary : COLORS.textMuted} />
                  <View style={{ flex: 1, marginLeft: 10 }}>
                    <Text style={styles.optLabel}>{opt.label}</Text>
                    <Text style={styles.optDesc}>{opt.desc}</Text>
                  </View>
                  <Ionicons name={opt.icon as any} size={16} color={on ? primary : COLORS.textMuted} />
                </TouchableOpacity>
              );
            })}

            {elig === 'custom' && (
              <TextInput
                testID="url-consent-custom-note"
                style={styles.input}
                placeholder="Describe your access basis (e.g. licensed data, written approval…)"
                placeholderTextColor="#9CA3AF"
                value={customNote}
                onChangeText={setCustomNote}
                multiline
              />
            )}

            <View style={styles.disclaimer}>
              <Text style={styles.disclaimerText}>
                By proceeding you confirm that you have the legal right to access and analyse the
                content at this URL, that doing so does not violate the site&apos;s Terms of Service,
                applicable laws, robots/anti-scraping rules, copyright or data-protection
                regulations, and that View Dezider acts solely as a tool on your behalf. You accept
                full responsibility for this use. View Dezider does not bypass paywalls or
                authentication and fetches pages with a transparent, identifiable agent.
              </Text>
            </View>
          </ScrollView>

          {/* Accept row kept OUTSIDE the scroll area so the checkbox + button are
              always visible together without hunting/scrolling. */}
          <TouchableOpacity
            testID="url-consent-accept"
            style={styles.acceptRow}
            activeOpacity={0.8}
            onPress={() => setAccepted(a => !a)}
          >
            <Ionicons name={(accepted ? 'checkbox' : 'square-outline') as any} size={22} color={accepted ? primary : COLORS.textMuted} />
            <Text style={styles.acceptText}>I have read and accept the above. I confirm my access rights.</Text>
          </TouchableOpacity>

          <View style={styles.footer}>
            <TouchableOpacity testID="url-consent-cancel" style={styles.cancelBtn} onPress={handleCancel} disabled={busy}>
              <Text style={styles.cancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="url-consent-proceed"
              style={[styles.proceedBtn, { backgroundColor: primary }, (!canProceed || busy) && { opacity: 0.5 }]}
              onPress={handleConfirm}
              disabled={!canProceed || busy}
            >
              {busy ? <ActivityIndicator color="#fff" size="small" /> : (
                <><Ionicons name="play" size={15} color="#fff" /><Text style={styles.proceedText}>Agree & Analyse</Text></>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', justifyContent: 'center', alignItems: 'center', padding: 18 },
  card: { width: '100%', maxWidth: 480, backgroundColor: '#fff', borderRadius: 18, padding: 18, ...(Platform.OS === 'web' ? { boxShadow: '0 24px 60px rgba(0,0,0,0.28)' } as any : { elevation: 12 }) },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  title: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary, flex: 1 },
  closeBtn: { padding: 2 },
  urlBox: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#F1F5F9', borderRadius: 8, padding: 8, marginBottom: 12 },
  urlText: { flex: 1, fontSize: 12, color: COLORS.textSecondary },
  q: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  opt: { flexDirection: 'row', alignItems: 'center', borderWidth: 1.5, borderColor: '#E2E8F0', borderRadius: 12, padding: 12, marginBottom: 8 },
  optLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  optDesc: { fontSize: 11.5, color: COLORS.textSecondary, marginTop: 2 },
  input: { borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, padding: 10, fontSize: 13, color: COLORS.textPrimary, minHeight: 60, textAlignVertical: 'top', marginBottom: 8 },
  disclaimer: { backgroundColor: '#FEF9C3', borderRadius: 10, padding: 11, marginTop: 6, marginBottom: 12, borderWidth: 1, borderColor: '#FDE68A' },
  disclaimerText: { fontSize: 11.5, lineHeight: 17, color: '#713F12' },
  acceptRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 9, marginBottom: 6 },
  acceptText: { flex: 1, fontSize: 12.5, color: COLORS.textPrimary, fontWeight: '600', lineHeight: 18 },
  footer: { flexDirection: 'row', gap: 10, marginTop: 14 },
  cancelBtn: { flex: 1, paddingVertical: 13, borderRadius: 12, borderWidth: 1, borderColor: '#CBD5E1', alignItems: 'center' },
  cancelText: { fontSize: 14, fontWeight: '700', color: COLORS.textSecondary },
  proceedBtn: { flex: 2, paddingVertical: 13, borderRadius: 12, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 7 },
  proceedText: { fontSize: 14, fontWeight: '800', color: '#fff' },
});

export default UrlAccessConsentModal;
