/**
 * PolicyConsentModal — shown before a consumer USES a public Decider App
 * or public Decision Template.
 *
 * If the publisher attached custom policies (in `template.policies` or
 * `app.policies`), those are used. Otherwise the standard defaults are
 * shown so the consent flow ALWAYS runs — even on legacy items that
 * pre-date the policy fields (backfill script covers most, but this is a
 * safety net for anything missed).
 *
 * On agree → invokes `onAgree()`. On close/cancel → `onClose()`.
 *
 * Cross-app reuse: same component is imported by
 *   • /decider-store/[id].tsx  ("Use this template / Use this Finder")
 *   • TemplateBrowserModal      ("Use" button on any tab)
 */
import React, { useState } from 'react';
import {
  View, Text, Modal, ScrollView, TouchableOpacity, StyleSheet, Linking,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';

const DEFAULT_PRIVACY =
  'By using this public template / app, you agree that any lead-generation contact ' +
  'details you provide to the publisher (name, email, WhatsApp) may be shared with ' +
  'the publisher so they can reach out to you. JELCOS AI does not sell or share this ' +
  'data with third parties and stores it only for the purpose of connecting you with ' +
  'the publisher.';
const DEFAULT_TERMS =
  'This template / app is offered as a starting point for decision-making. The ' +
  'publisher is not liable for outcomes of any decision made using this template. ' +
  'You may clone and modify it for personal use; commercial re-distribution requires ' +
  'written permission from the publisher.';

interface LeadGen {
  contact_name?: string;
  organization?: string;
  designation?: string;
  email?: string;
  whatsapp?: string;
  mobile?: string;
  redirect_url?: string;
}

interface Props {
  visible: boolean;
  onClose: () => void;
  onAgree: () => void;
  item: any;                     // template or app doc
  actionLabel?: string;          // e.g. "Use this template" / "Use this Finder"
}

export default function PolicyConsentModal({ visible, onClose, onAgree, item, actionLabel }: Props) {
  const [agreed, setAgreed] = useState(false);

  const policies = (item && item.policies) || {};
  const privacy = policies.privacy_policy || DEFAULT_PRIVACY;
  const terms = policies.terms_of_use || DEFAULT_TERMS;

  const lg: LeadGen = (item && item.lead_gen) || {};
  const hasLeadGen = !!(lg.contact_name || lg.organization || lg.email || lg.whatsapp);

  const openLink = () => {
    if (!lg.redirect_url) return;
    Linking.openURL(lg.redirect_url).catch(() => {});
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.container}>
          <View style={s.header}>
            <View style={{ flex: 1 }}>
              <Text style={s.title}>Publisher terms — please review</Text>
              <Text style={s.subtitle}>You&apos;re about to {actionLabel || 'use this item'}. Please agree before we proceed.</Text>
            </View>
            <TouchableOpacity onPress={onClose} testID="policy-consent-close">
              <Ionicons name="close" size={22} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>

          <ScrollView style={s.body} contentContainerStyle={{ padding: 16, paddingBottom: 8 }}>
            {hasLeadGen && (
              <View style={s.card}>
                <Text style={s.cardHead}>Publisher · How to reach out</Text>
                {lg.contact_name ? <Text style={s.cardLine}>· {lg.contact_name}</Text> : null}
                {lg.organization ? <Text style={s.cardLine}>· {lg.organization}{lg.designation ? ` — ${lg.designation}` : ''}</Text> : null}
                {lg.email ? <Text style={s.cardLine}>· ✉️ {lg.email}</Text> : null}
                {lg.whatsapp ? <Text style={s.cardLine}>· 💬 WhatsApp {lg.whatsapp}</Text> : null}
                {lg.mobile ? <Text style={s.cardLine}>· 📞 {lg.mobile}</Text> : null}
                {lg.redirect_url ? (
                  <TouchableOpacity onPress={openLink} style={s.linkBtn}>
                    <Ionicons name="open-outline" size={14} color={COLORS.primary} />
                    <Text style={s.linkText}>Publisher page (opens in a new tab)</Text>
                  </TouchableOpacity>
                ) : null}
              </View>
            )}

            <Text style={s.sectionHead}>Privacy Policy</Text>
            <Text style={s.body2}>{privacy}</Text>

            <Text style={[s.sectionHead, { marginTop: 12 }]}>Terms of Use</Text>
            <Text style={s.body2}>{terms}</Text>
          </ScrollView>

          <TouchableOpacity style={s.consentRow} onPress={() => setAgreed(!agreed)} testID="policy-consent-agree">
            <Ionicons name={agreed ? 'checkbox' : 'square-outline'} size={22} color={agreed ? COLORS.primary : COLORS.textMuted} />
            <Text style={s.consentText}>I have read and agree to the Privacy Policy and Terms of Use above.</Text>
          </TouchableOpacity>

          <View style={s.footer}>
            <TouchableOpacity style={s.cancelBtn} onPress={onClose}>
              <Text style={s.cancelBtnText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[s.agreeBtn, !agreed && s.agreeBtnDisabled]}
              onPress={() => { if (agreed) onAgree(); }}
              disabled={!agreed}
              testID="policy-consent-continue"
            >
              <Ionicons name="checkmark-done" size={18} color="#FFF" />
              <Text style={s.agreeBtnText}>Agree & continue</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  container: { backgroundColor: '#FFF', borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '92%' },
  header: { flexDirection: 'row', alignItems: 'flex-start', padding: 16, paddingBottom: 8, gap: 10 },
  title: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary },
  subtitle: { fontSize: 12.5, color: COLORS.textSecondary, marginTop: 3, lineHeight: 17 },
  body: { maxHeight: 460, borderTopWidth: 1, borderTopColor: COLORS.divider },
  card: { padding: 12, borderRadius: 12, borderWidth: 1, borderColor: '#BBF7D0', backgroundColor: '#F0FDF4', marginBottom: 12, gap: 3 },
  cardHead: { fontSize: 12.5, fontWeight: '800', color: '#065F46', marginBottom: 3 },
  cardLine: { fontSize: 13, color: '#065F46' },
  linkBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6 },
  linkText: { color: COLORS.primary, fontWeight: '700', fontSize: 12.5 },
  sectionHead: { fontSize: 13, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 4 },
  body2: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19 },
  consentRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingVertical: 10, borderTopWidth: 1, borderTopColor: COLORS.divider },
  consentText: { flex: 1, fontSize: 13, color: COLORS.textPrimary, fontWeight: '600' },
  footer: { flexDirection: 'row', gap: 10, padding: 14, borderTopWidth: 1, borderTopColor: COLORS.divider },
  cancelBtn: { flex: 1, paddingVertical: 13, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center', justifyContent: 'center' },
  cancelBtnText: { color: COLORS.textPrimary, fontWeight: '700' },
  agreeBtn: { flex: 2, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary, paddingVertical: 13, borderRadius: 12 },
  agreeBtnDisabled: { opacity: 0.45 },
  agreeBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14.5 },
});
