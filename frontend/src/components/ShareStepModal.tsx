import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  TextInput,
  ScrollView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { COLORS } from '../constants/colors';
import api from '../utils/api';

interface ShareStepModalProps {
  visible: boolean;
  onClose: () => void;
  decisionId: string;
  stepNumber: number;
  stepName: string;
  onShareSuccess: () => void;
}

const STEP_NAMES: Record<number, string> = {
  1: 'Context & Options',
  2: 'List Factors',
  3: 'Classify Factors',
  4: 'Prioritize Factors',
  5: 'Calculate Ratings',
  6: 'Define Options',
  7: 'Assess & Calculate',
  8: 'Results Summary',
  9: 'Reflection',
  10: 'Final Notes',
};

const MERGE_MODES = [
  {
    id: 'equal',
    name: 'Equal Weightage',
    description: 'All participants (including you) have equal say',
    icon: 'people',
  },
  {
    id: 'self_weighted',
    name: 'Self 50%',
    description: 'You keep 50%, others share the remaining 50% equally',
    icon: 'person',
  },
  {
    id: 'custom',
    name: 'Custom Weights',
    description: 'Set custom percentage for each participant',
    icon: 'options',
  },
];

export default function ShareStepModal({
  visible,
  onClose,
  decisionId,
  stepNumber,
  stepName,
  onShareSuccess,
}: ShareStepModalProps) {
  const [emailInput, setEmailInput] = useState('');
  const [emails, setEmails] = useState<string[]>([]);
  const [mergeMode, setMergeMode] = useState('equal');
  const [customWeights, setCustomWeights] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [sentShares, setSentShares] = useState<any[]>([]);
  const [showSent, setShowSent] = useState(false);
  const [allowReshare, setAllowReshare] = useState(false);
  // New: share source tab
  const [shareSource, setShareSource] = useState<'email' | 'contacts' | 'users' | 'experts'>('email');
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [experts, setExperts] = useState<any[]>([]);
  const [expertsLoading, setExpertsLoading] = useState(false);
  const [contacts, setContacts] = useState<any[]>([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [contactSearch, setContactSearch] = useState('');
  const [smeOnly, setSmeOnly] = useState(false);
  const router = useRouter();

  const askPublic = async () => {
    try {
      setLoading(true);
      await api.post(`/public-help/decisions/${decisionId}/ask-public`, {
        step_number: stepNumber,
        message,
      });
      Alert.alert('Published 📢', 'Your request is now on the Public Help feed. Track contributions under "My Requests".');
      onClose();
      router.push('/public-help');
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail || 'Failed to publish');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      fetchSentShares();
      fetchExperts();
    }
  }, [visible]);

  // Debounced user search
  useEffect(() => {
    if (shareSource !== 'users' || userSearchQuery.length < 2) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const resp = await api.get(`/users/search?q=${encodeURIComponent(userSearchQuery)}`);
        setSearchResults(resp.data || []);
      } catch { setSearchResults([]); }
      finally { setSearchLoading(false); }
    }, 400);
    return () => clearTimeout(timer);
  }, [userSearchQuery, shareSource]);

  const fetchSentShares = async () => {
    try {
      const response = await api.get('/shared-steps/sent');
      const filtered = response.data.filter(
        (s: any) => s.decision_id === decisionId && s.step_number === stepNumber
      );
      setSentShares(filtered);
    } catch {}
  };

  const fetchExperts = async () => {
    setExpertsLoading(true);
    try {
      const [pRes, lRes] = await Promise.allSettled([
        api.get('/platform-experts'),
        api.get('/experts'),
      ]);
      const platform = pRes.status === 'fulfilled' ? (pRes.value.data?.items || []) : [];
      const legacy = lRes.status === 'fulfilled' ? (lRes.value.data?.items || lRes.value.data || []) : [];
      const merged: any[] = [];
      const seen = new Set<string>();
      [...platform, ...legacy].forEach((e: any) => {
        const email = (e.email || '').toLowerCase();
        if (!email || seen.has(email)) return;
        seen.add(email);
        merged.push({
          key: e.expert_id || e.id || email,
          name: e.name,
          email,
          specialization: e.expert_type || e.specialization || (e.specializations && e.specializations[0]) || '',
        });
      });
      setExperts(merged);
    } catch { setExperts([]); }
    finally { setExpertsLoading(false); }
  };

  // Contacts tab — share with the user's own Contacts (optionally SME experts).
  const fetchContacts = async () => {
    setContactsLoading(true);
    try {
      const params: string[] = [];
      if (contactSearch.trim()) params.push(`search=${encodeURIComponent(contactSearch.trim())}`);
      if (smeOnly) params.push('is_sme=true');
      const resp = await api.get(`/contacts${params.length ? '?' + params.join('&') : ''}`);
      setContacts((resp.data?.contacts || []).filter((c: any) => c.email));
    } catch { setContacts([]); }
    finally { setContactsLoading(false); }
  };
  useEffect(() => {
    if (!visible || shareSource !== 'contacts') return;
    const t = setTimeout(fetchContacts, 300);
    return () => clearTimeout(t);
  }, [visible, shareSource, contactSearch, smeOnly]);

  const addEmail = () => {
    const email = emailInput.trim().toLowerCase();
    if (email && email.includes('@') && !emails.includes(email)) {
      setEmails([...emails, email]);
      setEmailInput('');
    }
  };

  const addUserEmail = (email: string) => {
    if (email && !emails.includes(email)) {
      setEmails([...emails, email]);
    }
  };

  const removeEmail = (email: string) => {
    setEmails(emails.filter(e => e !== email));
  };

  const handleShare = async () => {
    if (emails.length === 0) {
      Alert.alert('Error', 'Please add at least one email');
      return;
    }

    setLoading(true);
    try {
      const payload: any = {
        decision_id: decisionId,
        step_number: stepNumber,
        recipient_emails: emails,
        merge_mode: mergeMode,
        message,
        allow_reshare: allowReshare,
      };

      if (mergeMode === 'custom') {
        const weights: Record<string, number> = {};
        for (const email of emails) {
          weights[email] = parseInt(customWeights[email] || '0', 10);
        }
        payload.custom_weights = weights;
      }

      const res = await api.post(`/decisions/${decisionId}/share-step`, payload);
      Alert.alert(
        'Shared!',
        res.data?.message
          || `Step ${stepNumber} has been shared with ${emails.length} user(s)`,
      );
      onShareSuccess();
      onClose();
    } catch (error: any) {
      const msg = error.response?.data?.detail || 'Failed to share step';
      Alert.alert('Error', msg);
    } finally {
      setLoading(false);
    }
  };

  const handleMerge = async (shareId: string) => {
    try {
      setLoading(true);
      await api.post(`/shared-steps/${shareId}/merge`, { merge_mode: mergeMode });
      Alert.alert('Merged!', 'Contributions have been merged into your decision');
      onShareSuccess();
      fetchSentShares();
    } catch (error: any) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to merge');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={styles.container}>
          {/* Header */}
          <View style={styles.header}>
            <View>
              <Text style={styles.headerTitle}>Share Step {stepNumber}</Text>
              <Text style={styles.headerSubtitle}>{STEP_NAMES[stepNumber] || stepName}</Text>
            </View>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
              <Ionicons name="close" size={22} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.body} showsVerticalScrollIndicator={false}>
            {/* Tab: New Share / Sent Shares */}
            <View style={styles.tabRow}>
              <TouchableOpacity
                style={[styles.tab, !showSent && styles.tabActive]}
                onPress={() => setShowSent(false)}
              >
                <Text style={[styles.tabText, !showSent && styles.tabTextActive]}>New Share</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.tab, showSent && styles.tabActive]}
                onPress={() => setShowSent(true)}
              >
                <Text style={[styles.tabText, showSent && styles.tabTextActive]}>
                  Sent ({sentShares.length})
                </Text>
              </TouchableOpacity>
            </View>

            {!showSent ? (
              <>
                {/* Share Source Tabs: Email / Users / Experts */}
                <View style={styles.sourceTabRow}>
                  {[
                    { id: 'email' as const, label: 'Email', icon: 'mail-outline' },
                    { id: 'contacts' as const, label: 'Contacts', icon: 'person-outline' },
                    { id: 'users' as const, label: 'Users', icon: 'people-outline' },
                    { id: 'experts' as const, label: 'Experts', icon: 'shield-checkmark-outline' },
                  ].map((st) => (
                    <TouchableOpacity
                      key={st.id}
                      style={[styles.sourceTab, shareSource === st.id && styles.sourceTabActive]}
                      onPress={() => setShareSource(st.id)}
                    >
                      <Ionicons name={st.icon as any} size={14} color={shareSource === st.id ? COLORS.primary : COLORS.textMuted} />
                      <Text style={[styles.sourceTabText, shareSource === st.id && styles.sourceTabTextActive]}>{st.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Add Recipients */}
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Recipients</Text>

                  {/* Email direct entry */}
                  {shareSource === 'email' && (
                    <View style={styles.emailInputRow}>
                      <TextInput
                        style={styles.emailInput}
                        placeholder="Enter email address..."
                        placeholderTextColor={COLORS.textMuted}
                        value={emailInput}
                        onChangeText={setEmailInput}
                        keyboardType="email-address"
                        autoCapitalize="none"
                        onSubmitEditing={addEmail}
                      />
                      <TouchableOpacity style={styles.addEmailBtn} onPress={addEmail}>
                        <Ionicons name="add" size={20} color="#FFF" />
                      </TouchableOpacity>
                    </View>
                  )}

                  {/* Contacts (own contacts, optional SME experts) */}
                  {shareSource === 'contacts' && (
                    <View>
                      <TextInput
                        style={[styles.emailInput, { marginBottom: 6 }]}
                        placeholder="Search your contacts..."
                        placeholderTextColor={COLORS.textMuted}
                        value={contactSearch}
                        onChangeText={setContactSearch}
                        autoCapitalize="none"
                      />
                      <TouchableOpacity
                        onPress={() => setSmeOnly((v) => !v)}
                        style={{ flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 4, marginBottom: 4 }}
                        testID="share-sme-only"
                      >
                        <Ionicons name={smeOnly ? 'checkbox' : 'square-outline'} size={18} color={smeOnly ? COLORS.primary : COLORS.textMuted} />
                        <Text style={{ fontSize: 12.5, color: COLORS.textSecondary, fontWeight: '600' }}>Experts only (Subject-Matter)</Text>
                      </TouchableOpacity>
                      {contactsLoading && <ActivityIndicator size="small" color={COLORS.primary} style={{ marginBottom: 6 }} />}
                      {!contactsLoading && contacts.length === 0 && (
                        <Text style={{ fontSize: 12, color: COLORS.textMuted, padding: 8 }}>
                          {smeOnly ? 'No SME contacts with an email found.' : 'No contacts with an email found.'}
                        </Text>
                      )}
                      {contacts.map((c) => (
                        <TouchableOpacity
                          key={c.id || c.contact_id || c.email}
                          style={[styles.userResultItem, emails.includes(c.email) && { backgroundColor: '#F0FDF4' }]}
                          onPress={() => addUserEmail(c.email)}
                        >
                          <View style={[styles.userAvatar, c.is_sme && { backgroundColor: '#6366F1' }]}>
                            {c.is_sme
                              ? <Ionicons name="shield-checkmark" size={14} color="#FFF" />
                              : <Text style={styles.userAvatarText}>{(c.name || c.email)[0].toUpperCase()}</Text>}
                          </View>
                          <View style={{ flex: 1 }}>
                            <Text style={styles.userName}>{c.name || c.email}{c.is_sme ? '  · SME' : ''}</Text>
                            <Text style={styles.userEmail}>{c.email}</Text>
                          </View>
                          {emails.includes(c.email)
                            ? <Ionicons name="checkmark-circle" size={18} color="#16A34A" />
                            : <Ionicons name="add-circle-outline" size={18} color={COLORS.primary} />}
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}

                  {/* User search */}
                  {shareSource === 'users' && (
                    <View>
                      <TextInput
                        style={[styles.emailInput, { marginBottom: 6 }]}
                        placeholder="Search users by name or email..."
                        placeholderTextColor={COLORS.textMuted}
                        value={userSearchQuery}
                        onChangeText={setUserSearchQuery}
                        autoCapitalize="none"
                      />
                      {searchLoading && <ActivityIndicator size="small" color={COLORS.primary} style={{ marginBottom: 6 }} />}
                      {searchResults.map((u) => (
                        <TouchableOpacity
                          key={u.user_id}
                          style={[styles.userResultItem, emails.includes(u.email) && { backgroundColor: '#F0FDF4' }]}
                          onPress={() => addUserEmail(u.email)}
                        >
                          <View style={styles.userAvatar}>
                            <Text style={styles.userAvatarText}>{(u.name || u.email)[0].toUpperCase()}</Text>
                          </View>
                          <View style={{ flex: 1 }}>
                            <Text style={styles.userName}>{u.name}</Text>
                            <Text style={styles.userEmail}>{u.email}</Text>
                          </View>
                          {emails.includes(u.email) ? (
                            <Ionicons name="checkmark-circle" size={18} color="#16A34A" />
                          ) : (
                            <Ionicons name="add-circle-outline" size={18} color={COLORS.primary} />
                          )}
                        </TouchableOpacity>
                      ))}
                      {!searchLoading && userSearchQuery.length >= 2 && searchResults.length === 0 && (
                        <Text style={{ fontSize: 12, color: COLORS.textMuted, padding: 8 }}>No users found</Text>
                      )}
                    </View>
                  )}

                  {/* Authorized Experts */}
                  {shareSource === 'experts' && (
                    <View>
                      {expertsLoading && <ActivityIndicator size="small" color={COLORS.primary} style={{ marginBottom: 6 }} />}
                      {experts.length === 0 && !expertsLoading && (
                        <Text style={{ fontSize: 12, color: COLORS.textMuted, padding: 8 }}>No authorized experts available.</Text>
                      )}
                      {experts.map((exp) => (
                        <TouchableOpacity
                          key={exp.key}
                          style={[styles.userResultItem, emails.includes(exp.email) && { backgroundColor: '#F0FDF4' }]}
                          onPress={() => addUserEmail(exp.email)}
                        >
                          <View style={[styles.userAvatar, { backgroundColor: '#6366F1' }]}>
                            <Ionicons name="shield-checkmark" size={14} color="#FFF" />
                          </View>
                          <View style={{ flex: 1 }}>
                            <Text style={styles.userName}>{exp.name}</Text>
                            <Text style={styles.userEmail}>{exp.email}</Text>
                            {exp.specialization ? (
                              <Text style={{ fontSize: 10, color: COLORS.primary, fontWeight: '600' }}>{exp.specialization}</Text>
                            ) : null}
                          </View>
                          {emails.includes(exp.email) ? (
                            <Ionicons name="checkmark-circle" size={18} color="#16A34A" />
                          ) : (
                            <Ionicons name="add-circle-outline" size={18} color={COLORS.primary} />
                          )}
                        </TouchableOpacity>
                      ))}
                    </View>
                  )}

                  {/* Selected recipients chips */}
                  <View style={styles.emailChips}>
                    {emails.map(email => (
                      <View key={email} style={styles.emailChip}>
                        <Text style={styles.emailChipText} numberOfLines={1}>{email}</Text>
                        <TouchableOpacity onPress={() => removeEmail(email)}>
                          <Ionicons name="close-circle" size={16} color={COLORS.textMuted} />
                        </TouchableOpacity>
                      </View>
                    ))}
                  </View>
                </View>

                {/* Merge Mode */}
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Merge Mode</Text>
                  <Text style={styles.sectionHint}>How will contributions be weighted?</Text>
                  {MERGE_MODES.map(mode => (
                    <TouchableOpacity
                      key={mode.id}
                      style={[styles.modeCard, mergeMode === mode.id && styles.modeCardActive]}
                      onPress={() => setMergeMode(mode.id)}
                    >
                      <Ionicons
                        name={mode.icon as any}
                        size={20}
                        color={mergeMode === mode.id ? COLORS.primary : COLORS.textMuted}
                      />
                      <View style={styles.modeInfo}>
                        <Text style={[styles.modeName, mergeMode === mode.id && styles.modeNameActive]}>
                          {mode.name}
                        </Text>
                        <Text style={styles.modeDesc}>{mode.description}</Text>
                      </View>
                      <View style={[styles.radio, mergeMode === mode.id && styles.radioActive]}>
                        {mergeMode === mode.id && <View style={styles.radioInner} />}
                      </View>
                    </TouchableOpacity>
                  ))}
                </View>

                {/* Custom Weights */}
                {mergeMode === 'custom' && emails.length > 0 && (
                  <View style={styles.section}>
                    <Text style={styles.sectionTitle}>Custom Weights</Text>
                    <View style={styles.weightRow}>
                      <Text style={styles.weightLabel}>You (self)</Text>
                      <TextInput
                        style={styles.weightInput}
                        value={customWeights['self'] || '50'}
                        onChangeText={(v) => setCustomWeights({ ...customWeights, self: v })}
                        keyboardType="numeric"
                        maxLength={3}
                      />
                      <Text style={styles.weightPercent}>%</Text>
                    </View>
                    {emails.map(email => (
                      <View key={email} style={styles.weightRow}>
                        <Text style={styles.weightLabel} numberOfLines={1}>{email}</Text>
                        <TextInput
                          style={styles.weightInput}
                          value={customWeights[email] || ''}
                          onChangeText={(v) => setCustomWeights({ ...customWeights, [email]: v })}
                          keyboardType="numeric"
                          maxLength={3}
                          placeholder="0"
                          placeholderTextColor={COLORS.textMuted}
                        />
                        <Text style={styles.weightPercent}>%</Text>
                      </View>
                    ))}
                  </View>
                )}

                {/* Optional Message */}
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Message (optional)</Text>
                  <TextInput
                    style={styles.messageInput}
                    placeholder="Add a note for recipients..."
                    placeholderTextColor={COLORS.textMuted}
                    value={message}
                    onChangeText={setMessage}
                    multiline
                    numberOfLines={3}
                  />
                </View>

                {/* Allow re-share (transparent attribution) */}
                <TouchableOpacity
                  testID="share-allow-reshare"
                  activeOpacity={0.8}
                  onPress={() => setAllowReshare(v => !v)}
                  style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 }}
                >
                  <Ionicons
                    name={allowReshare ? 'checkbox' : 'square-outline'}
                    size={22} color={allowReshare ? COLORS.primary : COLORS.textSecondary}
                  />
                  <View style={{ flex: 1 }}>
                    <Text style={{ fontSize: 13.5, fontWeight: '700', color: COLORS.textPrimary }}>
                      Allow recipients to seek further help
                    </Text>
                    <Text style={{ fontSize: 11.5, color: COLORS.textSecondary, marginTop: 2, lineHeight: 16 }}>
                      Contributors can forward to their own contacts/experts. Every input stays transparently attributed to you.
                    </Text>
                  </View>
                </TouchableOpacity>

                {/* Ask the public for help */}
                <TouchableOpacity
                  testID="ask-public-btn"
                  style={styles.askPublicBtn}
                  onPress={askPublic}
                  disabled={loading}
                  activeOpacity={0.85}
                >
                  <Ionicons name="megaphone-outline" size={18} color="#0369A1" />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.askPublicTitle}>Ask the public for help</Text>
                    <Text style={styles.askPublicDesc}>Publish this step to the community feed — anyone can contribute ideas you can review &amp; merge.</Text>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color="#0369A1" />
                </TouchableOpacity>

                {/* Share Button */}
                <TouchableOpacity
                  style={[styles.shareBtn, loading && styles.shareBtnDisabled]}
                  onPress={handleShare}
                  disabled={loading}
                >
                  {loading ? (
                    <ActivityIndicator color="#FFF" size="small" />
                  ) : (
                    <>
                      <Ionicons name="share-outline" size={18} color="#FFF" />
                      <Text style={styles.shareBtnText}>Share Step {stepNumber}</Text>
                    </>
                  )}
                </TouchableOpacity>
              </>
            ) : (
              /* Sent Shares */
              <View style={styles.section}>
                {sentShares.length === 0 ? (
                  <Text style={styles.noShares}>No shares sent for this step yet.</Text>
                ) : (
                  sentShares.map(share => {
                    const contributed = share.recipients.filter((r: any) => r.status === 'contributed').length;
                    const total = share.recipients.length;
                    return (
                      <View key={share.id} style={styles.sentCard}>
                        <View style={styles.sentHeader}>
                          <Text style={styles.sentTitle}>
                            {total} recipient{total > 1 ? 's' : ''}
                          </Text>
                          <View style={[
                            styles.sentStatus,
                            share.status === 'merged' && styles.sentStatusMerged,
                          ]}>
                            <Text style={styles.sentStatusText}>
                              {share.status === 'merged' ? 'Merged' : `${contributed}/${total} contributed`}
                            </Text>
                          </View>
                        </View>
                        <Text style={styles.sentMode}>Mode: {share.merge_mode}</Text>
                        {share.recipients.map((r: any) => (
                          <View key={r.user_id} style={styles.recipientRow}>
                            <Ionicons
                              name={r.status === 'contributed' ? 'checkmark-circle' : 'time-outline'}
                              size={14}
                              color={r.status === 'contributed' ? COLORS.success : COLORS.textMuted}
                            />
                            <Text style={styles.recipientEmail}>{r.email}</Text>
                            <Text style={styles.recipientStatus}>{r.status}</Text>
                          </View>
                        ))}
                        {share.status === 'active' && contributed > 0 && (
                          <TouchableOpacity
                            style={styles.mergeBtn}
                            onPress={() => handleMerge(share.id)}
                          >
                            <Ionicons name="git-merge-outline" size={16} color="#FFF" />
                            <Text style={styles.mergeBtnText}>Merge Contributions</Text>
                          </TouchableOpacity>
                        )}
                      </View>
                    );
                  })
                )}
              </View>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  container: {
    backgroundColor: COLORS.white, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    maxHeight: '85%', minHeight: '50%',
  },
  header: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  headerSubtitle: { fontSize: 13, color: COLORS.textSecondary, marginTop: 2 },
  closeBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: COLORS.background, justifyContent: 'center', alignItems: 'center' },
  body: { padding: 16 },

  tabRow: { flexDirection: 'row', gap: 8, marginBottom: 16 },
  tab: { flex: 1, paddingVertical: 8, borderRadius: 10, backgroundColor: COLORS.background, alignItems: 'center' },
  tabActive: { backgroundColor: COLORS.primary },
  tabText: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  tabTextActive: { color: '#FFF' },

  section: { marginBottom: 18 },
  sectionTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 6 },
  sectionHint: { fontSize: 12, color: COLORS.textMuted, marginBottom: 8 },

  emailInputRow: { flexDirection: 'row', gap: 8 },
  emailInput: {
    flex: 1, borderWidth: 1, borderColor: COLORS.border, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary,
  },
  addEmailBtn: {
    width: 42, height: 42, borderRadius: 10,
    backgroundColor: COLORS.primary, justifyContent: 'center', alignItems: 'center',
  },
  emailChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 },
  emailChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(142,36,170,0.08)', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14,
  },
  emailChipText: { fontSize: 12, color: COLORS.primary, maxWidth: 180 },

  modeCard: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    padding: 12, borderRadius: 10, borderWidth: 1.5, borderColor: COLORS.border,
    backgroundColor: COLORS.white, marginBottom: 8,
  },
  modeCardActive: { borderColor: COLORS.primary, backgroundColor: 'rgba(142,36,170,0.04)' },
  modeInfo: { flex: 1 },
  modeName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  modeNameActive: { color: COLORS.primary },
  modeDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: COLORS.border, justifyContent: 'center', alignItems: 'center' },
  radioActive: { borderColor: COLORS.primary },
  radioInner: { width: 10, height: 10, borderRadius: 5, backgroundColor: COLORS.primary },

  weightRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  weightLabel: { flex: 1, fontSize: 13, color: COLORS.textPrimary },
  weightInput: {
    width: 50, borderWidth: 1, borderColor: COLORS.border, borderRadius: 8,
    textAlign: 'center', paddingVertical: 4, fontSize: 14, color: COLORS.textPrimary,
  },
  weightPercent: { fontSize: 14, color: COLORS.textMuted },

  messageInput: {
    borderWidth: 1, borderColor: COLORS.border, borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary,
    minHeight: 60, textAlignVertical: 'top',
  },

  shareBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: COLORS.primary, paddingVertical: 14, borderRadius: 12, marginBottom: 24,
  },
  shareBtnDisabled: { opacity: 0.6 },
  shareBtnText: { fontSize: 16, fontWeight: '600', color: '#FFF' },

  askPublicBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: '#F0F9FF', borderWidth: 1, borderColor: '#BAE6FD',
    borderRadius: 12, padding: 12, marginBottom: 12,
  },
  askPublicTitle: { fontSize: 13.5, fontWeight: '700', color: '#0369A1' },
  askPublicDesc: { fontSize: 11.5, color: '#0C4A6E', marginTop: 2, lineHeight: 15 },

  // Sent shares
  noShares: { fontSize: 14, color: COLORS.textMuted, textAlign: 'center', paddingVertical: 20 },
  sentCard: {
    borderWidth: 1, borderColor: COLORS.border, borderRadius: 12,
    padding: 12, marginBottom: 10, backgroundColor: COLORS.white,
  },
  sentHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  sentTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  sentStatus: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, backgroundColor: 'rgba(245,158,11,0.12)' },
  sentStatusMerged: { backgroundColor: 'rgba(16,185,129,0.12)' },
  sentStatusText: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },
  sentMode: { fontSize: 11, color: COLORS.textMuted, marginBottom: 6 },
  recipientRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 3 },
  recipientEmail: { flex: 1, fontSize: 12, color: COLORS.textPrimary },
  recipientStatus: { fontSize: 10, color: COLORS.textMuted, textTransform: 'capitalize' },
  mergeBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: COLORS.success, paddingVertical: 10, borderRadius: 10, marginTop: 8,
  },
  mergeBtnText: { fontSize: 13, fontWeight: '600', color: '#FFF' },
  sourceTabRow: {
    flexDirection: 'row', gap: 4, marginBottom: 12, backgroundColor: '#F1F5F9',
    borderRadius: 10, padding: 3,
  },
  sourceTab: {
    flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
    paddingVertical: 7, borderRadius: 8,
  },
  sourceTabActive: {
    backgroundColor: COLORS.white,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 2, elevation: 2,
  },
  sourceTabText: { fontSize: 12, color: COLORS.textMuted },
  sourceTabTextActive: { color: COLORS.primary, fontWeight: '600' },
  userResultItem: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingVertical: 8, paddingHorizontal: 8, borderRadius: 8,
    borderBottomWidth: 1, borderBottomColor: '#F1F5F9',
  },
  userAvatar: {
    width: 32, height: 32, borderRadius: 16, backgroundColor: COLORS.primary + '20',
    alignItems: 'center', justifyContent: 'center',
  },
  userAvatarText: { fontSize: 14, fontWeight: '700', color: COLORS.primary },
  userName: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  userEmail: { fontSize: 11, color: COLORS.textMuted },
});
