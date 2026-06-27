import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, TextInput, Modal,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { formatAbsolute } from '../../src/utils/datetime';
import { safeBack } from '../../src/utils/navigation';
import { useAuthStore } from '../../src/store/authStore';

const STATUS_COLORS: Record<string, {bg: string; text: string; label: string}> = {
  active: { bg: '#ECFDF5', text: '#059669', label: 'Active' },
  completed: { bg: '#EFF6FF', text: '#2563EB', label: 'Completed' },
  cancelled: { bg: '#FEF2F2', text: '#DC2626', label: 'Cancelled' },
};

const AUTH_METHODS = [
  { key: 'country_id', label: 'Country ID (Aadhar)', icon: 'card', desc: 'National ID verification' },
  { key: 'biometric', label: 'Biometric', icon: 'finger-print', desc: 'Fingerprint / Retina scan' },
  { key: 'authenticator', label: 'Authenticator App', icon: 'key', desc: 'TOTP 6-digit code' },
];

const OTP_METHODS = [
  { key: 'whatsapp_otp', label: 'WhatsApp OTP', icon: 'logo-whatsapp', desc: '6-digit code sent on WhatsApp' },
  { key: 'email_otp', label: 'Email OTP', icon: 'mail', desc: '6-digit code sent by email' },
];

const SESSION_MODES = [
  { key: 'async', label: 'Asynchronous', icon: 'time-outline', desc: 'Participants contribute at their own pace', color: '#3B82F6' },
  { key: 'live_sync', label: 'Live Sync', icon: 'videocam-outline', desc: 'Real-time collaboration with video call', color: '#059669' },
];

export default function CollaborateScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [detailSession, setDetailSession] = useState<any>(null);
  const [advancedAuthEnabled, setAdvancedAuthEnabled] = useState(false);
  // Participant OTP verification
  const [otpChannel, setOtpChannel] = useState<'whatsapp' | 'email'>('email');
  const [otpContact, setOtpContact] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otpSending, setOtpSending] = useState(false);

  // Create session
  const [showCreate, setShowCreate] = useState(false);
  const [createStep, setCreateStep] = useState(0); // 0=select module, 1=select mode, 2=select participants, 3=session config, 4=auth config
  const [modules, setModules] = useState<any[]>([]);
  const [selectedModule, setSelectedModule] = useState<any>(null);
  const [modes, setModes] = useState<any[]>([]);
  const [selectedMode, setSelectedMode] = useState<string>('equal');
  const [contacts, setContacts] = useState<any[]>([]);
  const [selectedContacts, setSelectedContacts] = useState<Set<string>>(new Set());
  const [contactSearch, setContactSearch] = useState('');
  const [authConfig, setAuthConfig] = useState<any>({ methods_required: 0, verify_each_time: false, enabled_methods: [] });
  const [notifyParticipants, setNotifyParticipants] = useState(true);
  const [notifyMode, setNotifyMode] = useState(true);
  const [creating, setCreating] = useState(false);
  const [smeFilter, setSmeFilter] = useState(false);
  const [sessionMode, setSessionMode] = useState<string>('async');
  const [modeConfigOverride, setModeConfigOverride] = useState<any>(null);
  const [showOverride, setShowOverride] = useState(false);
  const [overrideFields, setOverrideFields] = useState<Record<string, string>>({});

  // Verification Modal
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [verifySession, setVerifySession] = useState<any>(null);
  const [verifyMethod, setVerifyMethod] = useState('');
  const [verifyInput, setVerifyInput] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [totpStatus, setTotpStatus] = useState<any>(null);
  const [biometricStatus, setBiometricStatus] = useState<any>(null);
  const [digilockerStatus, setDigilockerStatus] = useState<any>(null);

  // Contribute / Merge (async flow)
  const [contributeOpen, setContributeOpen] = useState(false);
  const [contribNotes, setContribNotes] = useState('');
  const [contribVote, setContribVote] = useState<boolean | null>(null);
  const [contribAccepted, setContribAccepted] = useState<boolean | null>(null);
  const [submittingContrib, setSubmittingContrib] = useState(false);
  const [merging, setMerging] = useState(false);

  const refreshDetail = async (sessionId: string) => {
    try {
      const r = await api.get(`/collaboration/sessions/${sessionId}`);
      setDetailSession(r.data);
    } catch { /* ignore */ }
    fetchSessions();
  };

  const submitContribution = async () => {
    if (!detailSession) return;
    const modeId = detailSession.decision_mode_id;
    if (modeId === 'voting' && contribVote === null) { showAlert('Required', 'Cast your vote (Yes / No).'); return; }
    if (modeId === 'consensus' && contribAccepted === null) { showAlert('Required', 'Accept or reject the proposal.'); return; }
    setSubmittingContrib(true);
    try {
      await api.post(`/collaboration/sessions/${detailSession.id}/contribute`, {
        contribution: { notes: contribNotes.trim() },
        vote: contribVote,
        accepted: contribAccepted,
      });
      setContributeOpen(false);
      setContribNotes(''); setContribVote(null); setContribAccepted(null);
      showAlert('Contribution submitted', 'Your input has been recorded for this session.');
      await refreshDetail(detailSession.id);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not submit contribution');
    } finally { setSubmittingContrib(false); }
  };

  const mergeSession = async () => {
    if (!detailSession) return;
    setMerging(true);
    try {
      const { data } = await api.post(`/collaboration/sessions/${detailSession.id}/merge`, {});
      if (data.status === 'merged') {
        showAlert('Merged ✓', data.merge_details?.message || 'Contributions merged and the decision was finalized.');
      } else if (data.status === 'pending_consensus') {
        showAlert('Consensus pending', data.message || 'Not all participants have accepted yet.');
      } else if (data.status === 'voting_failed') {
        showAlert('Voting threshold not met', data.message || 'The required vote share was not reached.');
      } else {
        showAlert('Merge', data.message || 'Done.');
      }
      await refreshDetail(detailSession.id);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not merge contributions');
    } finally { setMerging(false); }
  };

  const fetchSessions = async () => {
    try {
      const res = await api.get('/collaboration/sessions');
      setSessions(res.data || []);
    } catch (err) {
      console.error('Error fetching sessions:', err);
    } finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => {
    fetchSessions();
    api.get('/collaboration/auth-config')
      .then(r => setAdvancedAuthEnabled(!!r.data?.advanced_methods_enabled))
      .catch(() => {});
  }, []));

  const onRefresh = async () => { setRefreshing(true); await fetchSessions(); setRefreshing(false); };

  const startCreate = async () => {
    setShowCreate(true);
    setCreateStep(0);
    setSelectedModule(null);
    setSelectedMode('equal');
    setSelectedContacts(new Set());
    setAuthConfig({ methods_required: 0, verify_each_time: false, enabled_methods: [] });
    setSessionMode('async');
    setModeConfigOverride(null);
    setShowOverride(false);
    setOverrideFields({});

    // Fetch all modules (decisions + solution finders)
    try {
      const [decisionsRes, sfRes, modesRes, contactsRes] = await Promise.all([
        api.get('/decisions?limit=50'),
        api.get('/solution-finder').catch(() => ({ data: [] })),
        api.get('/collaboration/decision-modes'),
        api.get('/contacts?limit=200'),
      ]);
      const decisionModules = (decisionsRes.data || []).map((d: any) => ({ type: 'decision', id: d.id, title: d.title || 'Untitled Decision', status: d.current_step }));
      const sfModules = (Array.isArray(sfRes.data) ? sfRes.data : []).map((s: any) => ({ type: 'solution_finder', id: s.entry_id, title: s.smart_goal || 'Untitled', status: s.status }));
      setModules([...decisionModules, ...sfModules]);
      setModes((modesRes.data || []).filter((m: any) => m.active));
      setContacts(contactsRes.data?.contacts || []);
    } catch (err) {
      console.error('Error loading data:', err);
    }
  };

  const handleCreate = async () => {
    if (!selectedModule) { showAlert('Required', 'Select a decision or problem'); return; }
    if (selectedContacts.size === 0) { showAlert('Required', 'Select at least one participant'); return; }

    setCreating(true);
    try {
      const res = await api.post('/collaboration/sessions', {
        module_type: selectedModule.type,
        module_id: selectedModule.id,
        title: selectedModule.title,
        decision_mode_id: selectedMode,
        participant_contact_ids: Array.from(selectedContacts),
        auth_config: authConfig,
        notify_participants: notifyParticipants,
        notify_mode: notifyMode,
        session_mode: sessionMode,
        mode_config_override: showOverride && Object.keys(overrideFields).length > 0
          ? Object.fromEntries(Object.entries(overrideFields).map(([k, v]) => [k, parseFloat(v) || v]))
          : null,
      });
      setShowCreate(false);
      showAlert('Session Created', `Collaboration session created with ${selectedContacts.size} participant(s). Mode: ${modes.find((m: any) => m.id === selectedMode)?.name || selectedMode}`);
      fetchSessions();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to create session');
    } finally { setCreating(false); }
  };

  const toggleAuth = (method: string) => {
    const enabled = [...authConfig.enabled_methods];
    const idx = enabled.indexOf(method);
    if (idx >= 0) enabled.splice(idx, 1); else enabled.push(method);
    setAuthConfig({ ...authConfig, enabled_methods: enabled, methods_required: Math.min(enabled.length, 2) });
  };

  const toggleContact = (id: string) => {
    const next = new Set(selectedContacts);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedContacts(next);
  };

  const filteredContacts = contacts.filter(c => {
    if (contactSearch) {
      const s = contactSearch.toLowerCase();
      if (!c.name?.toLowerCase().includes(s) && !c.email?.toLowerCase().includes(s) && !c.organization?.toLowerCase().includes(s)) return false;
    }
    if (smeFilter && !c.is_sme) return false;
    return true;
  });

  const renderCreateStep = () => {
    switch (createStep) {
      case 0: return (
        <View>
          <Text style={styles.stepTitle}>Select Decision / Problem</Text>
          <Text style={styles.stepHint}>Choose the My Dezider or Solution Finder to collaborate on.</Text>
          <ScrollView style={{ maxHeight: 350 }} showsVerticalScrollIndicator={false}>
            {modules.length === 0 ? (
              <Text style={styles.noItems}>No decisions or problems found. Create one first.</Text>
            ) : modules.map((m, i) => (
              <TouchableOpacity key={i} style={[styles.moduleCard, selectedModule?.id === m.id && styles.moduleCardSelected]}
                onPress={() => setSelectedModule(m)}>
                <View style={[styles.moduleType, { backgroundColor: m.type === 'decision' ? '#EFF6FF' : '#FFF7ED' }]}>
                  <Ionicons name={m.type === 'decision' ? 'git-branch' : 'bulb'} size={14}
                    color={m.type === 'decision' ? '#2563EB' : '#D97706'} />
                  <Text style={{ fontSize: 10, fontWeight: '700', color: m.type === 'decision' ? '#2563EB' : '#D97706' }}>
                    {m.type === 'decision' ? 'PRR' : 'SOLVER'}
                  </Text>
                </View>
                <Text style={styles.moduleTitle} numberOfLines={2}>{m.title}</Text>
                {selectedModule?.id === m.id && <Ionicons name="checkmark-circle" size={20} color="#059669" />}
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      );
      case 1: return (
        <View>
          <Text style={styles.stepTitle}>Decision Making Mode</Text>
          <Text style={styles.stepHint}>How should participant contributions be weighted and merged?</Text>
          <ScrollView style={{ maxHeight: 400 }} showsVerticalScrollIndicator={false}>
            {modes.map((mode: any) => (
              <TouchableOpacity key={mode.id} style={[styles.modeCard, selectedMode === mode.id && { borderColor: mode.color, borderWidth: 2 }]}
                onPress={() => setSelectedMode(mode.id)}>
                <View style={[styles.modeIcon, { backgroundColor: mode.color }]}>
                  <Ionicons name={mode.icon || 'ellipse'} size={18} color="#FFF" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.modeName}>{mode.name}</Text>
                  <Text style={styles.modeDesc}>{mode.description}</Text>
                </View>
                {selectedMode === mode.id && <Ionicons name="checkmark-circle" size={20} color={mode.color} />}
              </TouchableOpacity>
            ))}
          </ScrollView>
          {/* Notification options */}
          <View style={styles.notifySection}>
            <TouchableOpacity style={styles.notifyRow} onPress={() => setNotifyParticipants(!notifyParticipants)}>
              <Ionicons name={notifyParticipants ? 'checkbox' : 'square-outline'} size={20} color={notifyParticipants ? '#6366F1' : COLORS.textMuted} />
              <Text style={styles.notifyText}>Notify participants about invitation</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.notifyRow} onPress={() => setNotifyMode(!notifyMode)}>
              <Ionicons name={notifyMode ? 'checkbox' : 'square-outline'} size={20} color={notifyMode ? '#6366F1' : COLORS.textMuted} />
              <Text style={styles.notifyText}>Disclose decision making mode to participants</Text>
            </TouchableOpacity>
          </View>
        </View>
      );
      case 2: return (
        <View>
          <Text style={styles.stepTitle}>Select Participants ({selectedContacts.size} selected)</Text>
          <Text style={styles.stepHint}>Filter and choose from your contacts.</Text>
          <View style={{ flexDirection: 'row', gap: 8, marginBottom: 12 }}>
            <View style={styles.contactSearchWrap}>
              <Ionicons name="search" size={16} color={COLORS.textMuted} />
              <TextInput style={styles.contactSearchInput} placeholder="Search..." value={contactSearch} onChangeText={setContactSearch} />
            </View>
            <TouchableOpacity style={[styles.smeBtn, smeFilter && { backgroundColor: '#F59E0B', borderColor: '#F59E0B' }]}
              onPress={() => setSmeFilter(!smeFilter)}>
              <Ionicons name="star" size={14} color={smeFilter ? '#FFF' : COLORS.textMuted} />
              <Text style={[styles.smeBtnText, smeFilter && { color: '#FFF' }]}>SME</Text>
            </TouchableOpacity>
          </View>
          <ScrollView style={{ maxHeight: 440 }} showsVerticalScrollIndicator={true}>
            {filteredContacts.length === 0 ? (
              <Text style={styles.noItems}>No contacts match. Add contacts from the Contacts screen first.</Text>
            ) : filteredContacts.map(c => (
              <TouchableOpacity key={c.id} style={[styles.contactRow, selectedContacts.has(c.id) && styles.contactRowSelected]}
                onPress={() => toggleContact(c.id)}>
                <View style={styles.contactAvatar}>
                  <Text style={styles.contactAvatarText}>{(c.name || '?')[0].toUpperCase()}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.contactName}>{c.name}</Text>
                  <Text style={styles.contactDetail}>{[c.profession, c.organization, c.country].filter(Boolean).join(' • ')}</Text>
                </View>
                {c.is_sme && <View style={styles.smeBadge}><Ionicons name="star" size={10} color="#F59E0B" /></View>}
                <Ionicons name={selectedContacts.has(c.id) ? 'checkmark-circle' : 'ellipse-outline'} size={22}
                  color={selectedContacts.has(c.id) ? '#059669' : '#D1D5DB'} />
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      );
      case 3: return (
        <View>
          <Text style={styles.stepTitle}>Session Configuration</Text>
          <Text style={styles.stepHint}>Choose how participants will collaborate and optionally override mode settings.</Text>
          
          {/* Session Mode Toggle */}
          <Text style={[styles.inputLabel, { marginTop: 4, marginBottom: 8 }]}>Collaboration Mode</Text>
          {SESSION_MODES.map(sm => (
            <TouchableOpacity key={sm.key}
              style={[styles.sessionModeCard, sessionMode === sm.key && { borderColor: sm.color, backgroundColor: sm.color + '08' }]}
              onPress={() => setSessionMode(sm.key)}>
              <View style={[styles.sessionModeIcon, { backgroundColor: sm.color }]}>
                <Ionicons name={sm.icon as any} size={20} color="#FFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.sessionModeLabel, sessionMode === sm.key && { color: sm.color }]}>{sm.label}</Text>
                <Text style={styles.sessionModeDesc}>{sm.desc}</Text>
              </View>
              <Ionicons name={sessionMode === sm.key ? 'radio-button-on' : 'radio-button-off'} size={22} color={sessionMode === sm.key ? sm.color : '#D1D5DB'} />
            </TouchableOpacity>
          ))}

          {sessionMode === 'live_sync' && (
            <View style={styles.liveSyncInfo}>
              <Ionicons name="information-circle" size={16} color="#059669" />
              <Text style={styles.liveSyncInfoText}>A video call link will be generated when the session starts. Participants join in real-time.</Text>
            </View>
          )}

          {/* Mode Config Override */}
          <View style={styles.overrideSection}>
            <TouchableOpacity style={styles.overrideToggle} onPress={() => setShowOverride(!showOverride)}>
              <Ionicons name={showOverride ? 'checkbox' : 'square-outline'} size={20} color={showOverride ? '#7C3AED' : COLORS.textMuted} />
              <View style={{ flex: 1 }}>
                <Text style={styles.overrideLabel}>Override Mode Configuration</Text>
                <Text style={styles.overrideHint}>Customize percentages and weights for this session only</Text>
              </View>
              <Ionicons name={showOverride ? 'chevron-up' : 'chevron-down'} size={18} color={COLORS.textMuted} />
            </TouchableOpacity>
            
            {showOverride && (
              <View style={styles.overrideFields}>
                {selectedMode === 'command' && (
                  <View style={styles.overrideFieldRow}>
                    <Text style={styles.overrideFieldLabel}>Leader Weight %</Text>
                    <TextInput style={styles.overrideFieldInput} keyboardType="numeric" placeholder="60"
                      value={overrideFields.leader_weight_pct || ''}
                      onChangeText={v => setOverrideFields({...overrideFields, leader_weight_pct: v})} />
                  </View>
                )}
                {selectedMode === 'sme' && (
                  <View style={styles.overrideFieldRow}>
                    <Text style={styles.overrideFieldLabel}>SME Weight Multiplier</Text>
                    <TextInput style={styles.overrideFieldInput} keyboardType="numeric" placeholder="2.0"
                      value={overrideFields.sme_weight_multiplier || ''}
                      onChangeText={v => setOverrideFields({...overrideFields, sme_weight_multiplier: v})} />
                  </View>
                )}
                {selectedMode === 'voting' && (
                  <View style={styles.overrideFieldRow}>
                    <Text style={styles.overrideFieldLabel}>Approval Threshold %</Text>
                    <TextInput style={styles.overrideFieldInput} keyboardType="numeric" placeholder="51"
                      value={overrideFields.threshold_pct || ''}
                      onChangeText={v => setOverrideFields({...overrideFields, threshold_pct: v})} />
                  </View>
                )}
                {selectedMode === 'consensus' && (
                  <View style={styles.overrideFieldRow}>
                    <Text style={styles.overrideFieldLabel}>Consensus Threshold %</Text>
                    <TextInput style={styles.overrideFieldInput} keyboardType="numeric" placeholder="80"
                      value={overrideFields.consensus_pct || ''}
                      onChangeText={v => setOverrideFields({...overrideFields, consensus_pct: v})} />
                  </View>
                )}
                <View style={styles.overrideFieldRow}>
                  <View style={{ flex: 1, paddingRight: 8 }}>
                    <Text style={styles.overrideFieldLabel}>Deadline (Hours)</Text>
                    <Text style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 2 }}>Window to contribute before the session auto-locks. Late inputs stay as reference.</Text>
                  </View>
                  <TextInput style={styles.overrideFieldInput} keyboardType="numeric" placeholder="48"
                    value={overrideFields.deadline_hours || ''}
                    onChangeText={v => setOverrideFields({...overrideFields, deadline_hours: v})} />
                </View>
                <View style={styles.overrideFieldRow}>
                  <View style={{ flex: 1, paddingRight: 8 }}>
                    <Text style={styles.overrideFieldLabel}>Presence Check (Seconds)</Text>
                    <Text style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 2 }}>Live-sync heartbeat — how often to confirm participants are still active.</Text>
                  </View>
                  <TextInput style={styles.overrideFieldInput} keyboardType="numeric" placeholder="300"
                    value={overrideFields.presence_check_interval || ''}
                    onChangeText={v => setOverrideFields({...overrideFields, presence_check_interval: v})} />
                </View>
              </View>
            )}
          </View>
        </View>
      );
      case 4: return (
        <View>
          <Text style={styles.stepTitle}>Participant Authentication</Text>
          <Text style={styles.stepHint}>{advancedAuthEnabled
            ? 'Configure identity verification for participants. Select which methods and how many required.'
            : 'Choose how participants verify before contributing. Pick one or both — they can use whichever is convenient. Leave both unchecked to skip verification.'}</Text>

          {(advancedAuthEnabled ? AUTH_METHODS : OTP_METHODS).map(m => (
            <TouchableOpacity key={m.key} style={[styles.authMethodCard, authConfig.enabled_methods.includes(m.key) && styles.authMethodActive]}
              onPress={() => (advancedAuthEnabled ? toggleAuth(m.key) : toggleOtp(m.key))}>
              <Ionicons name={m.icon as any} size={22} color={authConfig.enabled_methods.includes(m.key) ? '#6366F1' : COLORS.textMuted} />
              <View style={{ flex: 1 }}>
                <Text style={styles.authMethodLabel}>{m.label}</Text>
                <Text style={styles.authMethodDesc}>{m.desc}</Text>
              </View>
              <Ionicons name={authConfig.enabled_methods.includes(m.key) ? 'checkbox' : 'square-outline'} size={22}
                color={authConfig.enabled_methods.includes(m.key) ? '#6366F1' : '#D1D5DB'} />
            </TouchableOpacity>
          ))}

          {advancedAuthEnabled && authConfig.enabled_methods.length >= 2 && (
            <View style={styles.authRequiredBox}>
              <Text style={styles.authRequiredLabel}>Methods required per participant:</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {[0, 1, 2].filter(n => n <= authConfig.enabled_methods.length).map(n => (
                  <TouchableOpacity key={n}
                    style={[styles.reqBtn, authConfig.methods_required === n && styles.reqBtnActive]}
                    onPress={() => setAuthConfig({ ...authConfig, methods_required: n })}>
                    <Text style={[styles.reqBtnText, authConfig.methods_required === n && { color: '#FFF' }]}>
                      {n === 0 ? 'None' : n}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          )}

          {authConfig.methods_required > 0 && (
            <TouchableOpacity style={styles.verifyToggle} onPress={() => setAuthConfig({ ...authConfig, verify_each_time: !authConfig.verify_each_time })}>
              <Ionicons name={authConfig.verify_each_time ? 'checkbox' : 'square-outline'} size={20}
                color={authConfig.verify_each_time ? '#6366F1' : COLORS.textMuted} />
              <Text style={styles.verifyText}>Require verification each time (not just first time)</Text>
            </TouchableOpacity>
          )}
        </View>
      );
    }
  };

  const fetchVerificationStatus = async () => {
    try {
      const [totp, bio, digi] = await Promise.all([
        api.get('/collaboration/totp/setup').catch(() => ({ data: null })),
        api.get('/collaboration/biometric/status').catch(() => ({ data: null })),
        api.get('/collaboration/digilocker/status').catch(() => ({ data: null })),
      ]);
      setTotpStatus(totp.data);
      setBiometricStatus(bio.data);
      setDigilockerStatus(digi.data);
    } catch (e) { /* ignore */ }
  };

  const handleVerify = async (method: string) => {
    setVerifying(true);
    try {
      if (method === 'country_id') {
        const res = await api.post('/collaboration/digilocker/initiate');
        if (res.data?.status === 'not_configured') {
          showAlert('DigiLocker', 'DigiLocker integration is not configured yet. Contact your administrator to set DIGILOCKER_CLIENT_ID and DIGILOCKER_CLIENT_SECRET in server environment.');
        } else if (res.data?.auth_url) {
          showAlert('DigiLocker', 'DigiLocker OAuth URL generated. In production, you would be redirected to complete KYC verification.');
        } else {
          showAlert('DigiLocker', res.data?.message || 'DigiLocker initiation received.');
        }
      } else if (method === 'biometric') {
        const res = await api.post('/collaboration/biometric/register', {
          type: 'fingerprint',
          device_id: 'mantra_mfs100',
          template_data: 'device_fingerprint_' + Date.now(),
        });
        showAlert('Biometric', res.data?.message || 'Biometric registration submitted.');
      } else if (method === 'authenticator') {
        const res = await api.get('/collaboration/totp/setup');
        if (res.data?.secret) {
          showAlert('TOTP Setup', `Secret: ${res.data.secret}\n\nScan the QR code in your Authenticator app, then verify with the 6-digit code.`);
        } else {
          showAlert('TOTP', res.data?.message || 'TOTP setup response received.');
        }
      }
      await fetchVerificationStatus();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Verification failed');
    } finally {
      setVerifying(false);
    }
  };

  const handleTotpVerify = async () => {
    if (!verifyInput || verifyInput.length !== 6) {
      showAlert('Invalid', 'Enter a valid 6-digit code');
      return;
    }
    setVerifying(true);
    try {
      const res = await api.post('/collaboration/totp/verify', { code: verifyInput });
      showAlert('TOTP', res.data?.verified ? 'Verification successful!' : 'Invalid code. Please try again.');
      setVerifyInput('');
      await fetchVerificationStatus();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'TOTP verification failed');
    } finally {
      setVerifying(false);
    }
  };

  const toggleOtp = (method: string) => {
    const enabled = [...authConfig.enabled_methods];
    const idx = enabled.indexOf(method);
    if (idx >= 0) enabled.splice(idx, 1); else enabled.push(method);
    // Any selected OTP channel ⇒ contributor verifies via one; none ⇒ verification skipped.
    setAuthConfig({ ...authConfig, enabled_methods: enabled, methods_required: enabled.length > 0 ? 1 : 0 });
  };

  const sendOtp = async () => {
    if (!otpContact.trim()) { showAlert('Required', otpChannel === 'email' ? 'Enter your email' : 'Enter your WhatsApp number'); return; }
    setOtpSending(true);
    try {
      await api.post(`/collaboration/sessions/${verifySession?.id}/otp/send`, { channel: otpChannel, contact: otpContact.trim() });
      setOtpSent(true);
      showAlert('Code sent', `A 6-digit code was sent via ${otpChannel === 'email' ? 'email' : 'WhatsApp'}. It expires in 10 minutes.`);
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Could not send code');
    } finally { setOtpSending(false); }
  };

  const verifyOtp = async () => {
    if (otpCode.length !== 6) { showAlert('Invalid', 'Enter the 6-digit code'); return; }
    setOtpSending(true);
    try {
      await api.post(`/collaboration/sessions/${verifySession?.id}/otp/verify`, { channel: otpChannel, contact: otpContact.trim(), otp: otpCode });
      showAlert('Verified', 'Your identity is verified for this session.');
      setOtpSent(false); setOtpCode('');
      setShowVerifyModal(false);
      fetchSessions();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Verification failed');
    } finally { setOtpSending(false); }
  };

  const renderOtpVerify = () => {
    const enabled: string[] = verifySession?.auth_requirements?.enabled_methods || [];
    const channels: ('whatsapp' | 'email')[] = [];
    if (enabled.includes('whatsapp_otp')) channels.push('whatsapp');
    if (enabled.includes('email_otp')) channels.push('email');
    if (channels.length === 0) {
      return <Text style={styles.stepHint}>No verification is required for this session — you can contribute directly.</Text>;
    }
    return (
      <View style={styles.verifyCard}>
        <Text style={styles.verifyCardTitle}>One-Time Passcode</Text>
        <Text style={styles.verifyCardDesc}>Pick a channel, get a 6-digit code, and enter it below.</Text>
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
          {channels.map(ch => (
            <TouchableOpacity key={ch} style={[styles.otpChannelBtn, otpChannel === ch && styles.otpChannelActive]}
              onPress={() => { setOtpChannel(ch); setOtpSent(false); }}>
              <Ionicons name={ch === 'whatsapp' ? 'logo-whatsapp' : 'mail'} size={16} color={otpChannel === ch ? '#FFF' : COLORS.textSecondary} />
              <Text style={[styles.otpChannelTxt, otpChannel === ch && { color: '#FFF' }]}>{ch === 'whatsapp' ? 'WhatsApp' : 'Email'}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <TextInput style={[styles.totpInput, { marginTop: 10 }]}
          placeholder={otpChannel === 'email' ? 'your@email.com' : 'WhatsApp number (e.g. 9198…)'}
          autoCapitalize="none" keyboardType={otpChannel === 'email' ? 'email-address' : 'phone-pad'}
          value={otpContact} onChangeText={setOtpContact} />
        {!otpSent ? (
          <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#7C3AED', marginTop: 10 }]} onPress={sendOtp} disabled={otpSending}>
            {otpSending ? <ActivityIndicator color="#FFF" size="small" /> : (<><Ionicons name="send" size={14} color="#FFF" /><Text style={styles.verifyActionText}>Send Code</Text></>)}
          </TouchableOpacity>
        ) : (
          <>
            <View style={[styles.totpVerifyRow, { marginTop: 10 }]}>
              <TextInput style={styles.totpInput} placeholder="6-digit code" keyboardType="numeric" maxLength={6} value={otpCode} onChangeText={setOtpCode} />
              <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#059669', flex: 0 }]} onPress={verifyOtp} disabled={otpSending}>
                {otpSending ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.verifyActionText}>Verify</Text>}
              </TouchableOpacity>
            </View>
            <TouchableOpacity onPress={sendOtp} disabled={otpSending} style={{ marginTop: 8 }}>
              <Text style={{ color: '#7C3AED', fontSize: 12, fontWeight: '600' }}>Resend code</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#7C3AED', '#A855F7']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => safeBack(router)}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Group Decisions</Text>
          <Text style={styles.headerSub}>Multi-user collaboration sessions</Text>
        </View>
        <TouchableOpacity style={styles.createHdrBtn} onPress={startCreate}>
          <Ionicons name="add" size={22} color="#7C3AED" />
        </TouchableOpacity>
      </LinearGradient>

      {loading ? (
        <View style={styles.centered}><ActivityIndicator size="large" color="#7C3AED" /></View>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          showsVerticalScrollIndicator={false}>
          
          {sessions.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="git-network-outline" size={48} color="#D1D5DB" />
              <Text style={styles.emptyTitle}>No Collaboration Sessions</Text>
              <Text style={styles.emptyText}>Create a group session to involve multiple people in decisions or problem-solving.</Text>
              <TouchableOpacity style={styles.emptyBtn} onPress={startCreate}>
                <Ionicons name="add" size={18} color="#FFF" />
                <Text style={{ color: '#FFF', fontWeight: '600' }}>New Session</Text>
              </TouchableOpacity>
            </View>
          ) : (
            sessions.map((s: any) => {
              const status = STATUS_COLORS[s.status] || STATUS_COLORS.active;
              const contributed = (s.participants || []).filter((p: any) => p.status === 'contributed').length;
              return (
                <TouchableOpacity key={s.id} style={styles.sessionCard} activeOpacity={0.7}
                  onPress={() => setDetailSession(s)}>
                  <View style={styles.sessionHeader}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.sessionTitle} numberOfLines={1}>{s.title}</Text>
                      <Text style={styles.sessionMeta}>{s.module_type === 'decision' ? 'My Dezider' : 'Solution Finder'} • {s.decision_mode?.name}</Text>
                    </View>
                    <View style={[styles.statusBadge, { backgroundColor: status.bg }]}>
                      <Text style={[styles.statusText, { color: status.text }]}>{status.label}</Text>
                    </View>
                  </View>
                  <View style={styles.participantBar}>
                    <Ionicons name="people" size={14} color={COLORS.textMuted} />
                    <Text style={styles.participantText}>
                      {contributed}/{(s.participants || []).length} contributed
                    </Text>
                    {s.session_mode && (
                      <View style={[styles.modeBadge, { backgroundColor: s.session_mode === 'live_sync' ? '#ECFDF5' : '#EFF6FF' }]}>
                        <Ionicons name={s.session_mode === 'live_sync' ? 'videocam' : 'time'} size={10}
                          color={s.session_mode === 'live_sync' ? '#059669' : '#3B82F6'} />
                        <Text style={[styles.modeBadgeText, { color: s.session_mode === 'live_sync' ? '#059669' : '#3B82F6' }]}>
                          {s.session_mode === 'live_sync' ? 'Live' : 'Async'}
                        </Text>
                      </View>
                    )}
                    <View style={{ flex: 1 }} />
                    <TouchableOpacity style={styles.verifyJoinBtn}
                      onPress={() => { setVerifySession(s); setShowVerifyModal(true); fetchVerificationStatus(); }}>
                      <Ionicons name="shield-checkmark" size={12} color="#7C3AED" />
                      <Text style={styles.verifyJoinText}>Verify</Text>
                    </TouchableOpacity>
                    <Text style={styles.sessionDate}>
                      {formatAbsolute(s.created_at)}
                    </Text>
                  </View>
                  {/* Video Call Button for Live Sync */}
                  {s.session_mode === 'live_sync' && s.status === 'active' && (
                    <TouchableOpacity style={styles.joinCallBtn}
                      onPress={() => router.push({ pathname: '/tools/collab-call', params: { sessionId: s.id } } as any)}>
                      <View style={styles.joinCallIcon}>
                        <Ionicons name="videocam" size={16} color="#FFF" />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.joinCallTitle}>
                          {s.call_room_url ? 'Join Video Call' : 'Start Video Call'}
                        </Text>
                        <Text style={styles.joinCallSub}>Jitsi Meet • Screen sharing enabled</Text>
                      </View>
                      <Ionicons name="arrow-forward" size={16} color="#059669" />
                    </TouchableOpacity>
                  )}
                </TouchableOpacity>
              );
            })
          )}
        </ScrollView>
      )}

      {/* Create Modal */}
      <Modal visible={showCreate} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ width: '100%', alignItems: 'center' }}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>New Collaboration</Text>
                <TouchableOpacity onPress={() => setShowCreate(false)}>
                  <Ionicons name="close" size={24} color={COLORS.textSecondary} />
                </TouchableOpacity>
              </View>

              {/* Step indicator */}
              <View style={styles.steps}>
                {['Module', 'Mode', 'People', 'Config', 'Auth'].map((s, i) => (
                  <View key={i} style={styles.stepItem}>
                    <View style={[styles.stepDot, createStep >= i && { backgroundColor: '#7C3AED' }]}>
                      <Text style={[styles.stepDotText, createStep >= i && { color: '#FFF' }]}>{i + 1}</Text>
                    </View>
                    <Text style={[styles.stepLabel, createStep === i && { color: '#7C3AED', fontWeight: '700' }]}>{s}</Text>
                  </View>
                ))}
              </View>

              <ScrollView style={{ maxHeight: 560 }} showsVerticalScrollIndicator={true}>
                {renderCreateStep()}
              </ScrollView>

              <View style={styles.modalFooter}>
                {createStep > 0 && (
                  <TouchableOpacity style={styles.prevBtn} onPress={() => setCreateStep(createStep - 1)}>
                    <Text style={styles.prevBtnText}>Back</Text>
                  </TouchableOpacity>
                )}
                <View style={{ flex: 1 }} />
                {createStep < 4 ? (
                  <TouchableOpacity style={styles.nextBtn} onPress={() => {
                    if (createStep === 0 && !selectedModule) { showAlert('Required', 'Select a module first'); return; }
                    if (createStep === 2 && selectedContacts.size === 0) { showAlert('Required', 'Select at least one participant'); return; }
                    setCreateStep(createStep + 1);
                  }}>
                    <Text style={styles.nextBtnText}>Next</Text>
                    <Ionicons name="arrow-forward" size={16} color="#FFF" />
                  </TouchableOpacity>
                ) : (
                  <TouchableOpacity style={styles.createBtn} onPress={handleCreate} disabled={creating}>
                    {creating ? <ActivityIndicator color="#FFF" size="small" /> : (
                      <>
                        <Ionicons name="rocket" size={16} color="#FFF" />
                        <Text style={styles.createBtnText}>Launch Session</Text>
                      </>
                    )}
                  </TouchableOpacity>
                )}
              </View>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>

      {/* Session Detail Modal — opens when a session card is tapped */}
      <Modal visible={!!detailSession} transparent animationType="slide" onRequestClose={() => setDetailSession(null)}>
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { maxHeight: '82%' }]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle} numberOfLines={1}>{detailSession?.title || 'Session'}</Text>
              <TouchableOpacity onPress={() => setDetailSession(null)}>
                <Ionicons name="close" size={24} color={COLORS.textSecondary} />
              </TouchableOpacity>
            </View>
            {detailSession && (
              <ScrollView showsVerticalScrollIndicator={true}>
                <View style={{ flexDirection: 'row', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
                  <View style={[styles.statusBadge, { backgroundColor: (STATUS_COLORS[detailSession.status] || STATUS_COLORS.active).bg }]}>
                    <Text style={[styles.statusText, { color: (STATUS_COLORS[detailSession.status] || STATUS_COLORS.active).text }]}>{(STATUS_COLORS[detailSession.status] || STATUS_COLORS.active).label}</Text>
                  </View>
                  <View style={[styles.modeBadge, { backgroundColor: detailSession.session_mode === 'live_sync' ? '#ECFDF5' : '#EFF6FF', marginLeft: 0 }]}>
                    <Ionicons name={detailSession.session_mode === 'live_sync' ? 'videocam' : 'time'} size={10} color={detailSession.session_mode === 'live_sync' ? '#059669' : '#3B82F6'} />
                    <Text style={[styles.modeBadgeText, { color: detailSession.session_mode === 'live_sync' ? '#059669' : '#3B82F6' }]}>{detailSession.session_mode === 'live_sync' ? 'Live Sync' : 'Async'}</Text>
                  </View>
                </View>
                <Text style={styles.sessionMeta}>{detailSession.module_type === 'decision' ? 'My Dezider' : 'Solution Finder'} · {detailSession.decision_mode?.name || detailSession.decision_mode_id} · {formatAbsolute(detailSession.created_at)}</Text>

                <Text style={[styles.inputLabel, { marginTop: 16, marginBottom: 8 }]}>Participants ({(detailSession.participants || []).length})</Text>
                {(detailSession.participants || []).length === 0 ? (
                  <Text style={styles.noItems}>No participants added.</Text>
                ) : (detailSession.participants || []).map((p: any, i: number) => (
                  <View key={i} style={styles.contactRow}>
                    <View style={styles.contactAvatar}><Text style={styles.contactAvatarText}>{(p.name || p.contact_name || '?')[0]?.toUpperCase()}</Text></View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.contactName}>{p.name || p.contact_name || 'Participant'}</Text>
                      {!!(p.email || p.contact_email) && <Text style={styles.contactDetail}>{p.email || p.contact_email}</Text>}
                    </View>
                    <View style={[styles.statusBadge, { backgroundColor: p.status === 'contributed' ? '#ECFDF5' : '#FEF3C7' }]}>
                      <Text style={[styles.statusText, { color: p.status === 'contributed' ? '#059669' : '#B45309' }]}>{p.status === 'contributed' ? 'Contributed' : 'Pending'}</Text>
                    </View>
                  </View>
                ))}

                <View style={{ flexDirection: 'row', gap: 10, marginTop: 18 }}>
                  <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#7C3AED' }]}
                    onPress={() => { const s = detailSession; setDetailSession(null); setVerifySession(s); setShowVerifyModal(true); fetchVerificationStatus(); }}>
                    <Ionicons name="shield-checkmark" size={14} color="#FFF" />
                    <Text style={styles.verifyActionText}>Verify Identity</Text>
                  </TouchableOpacity>
                  {detailSession.session_mode === 'live_sync' && detailSession.status === 'active' && (
                    <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#059669' }]}
                      onPress={() => { const sid = detailSession.id; setDetailSession(null); router.push({ pathname: '/tools/collab-call', params: { sessionId: sid } } as any); }}>
                      <Ionicons name="videocam" size={14} color="#FFF" />
                      <Text style={styles.verifyActionText}>{detailSession.call_room_url ? 'Join Call' : 'Start Call'}</Text>
                    </TouchableOpacity>
                  )}
                </View>

                {/* Contribute (participant) + Merge (owner) — async flow */}
                {detailSession.status === 'active' && (() => {
                  const isOwner = detailSession.owner_id === user?.user_id;
                  const myP = (detailSession.participants || []).find((p: any) => p.linked_user_id === user?.user_id);
                  const modeId = detailSession.decision_mode_id;
                  return (
                    <View style={{ marginTop: 10 }}>
                      <View style={{ flexDirection: 'row', gap: 10 }}>
                        {myP && (
                          <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#2563EB' }]}
                            onPress={() => { setContributeOpen((v) => !v); setContribNotes(myP.contribution?.notes || ''); setContribVote(myP.vote ?? null); setContribAccepted(myP.accepted ?? null); }}>
                            <Ionicons name="create-outline" size={14} color="#FFF" />
                            <Text style={styles.verifyActionText}>{myP.status === 'contributed' ? 'Edit Contribution' : 'Contribute'}</Text>
                          </TouchableOpacity>
                        )}
                        {isOwner && (
                          <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#059669' }]}
                            onPress={mergeSession} disabled={merging}>
                            {merging ? <ActivityIndicator color="#FFF" size="small" /> : (
                              <><Ionicons name="git-merge-outline" size={14} color="#FFF" /><Text style={styles.verifyActionText}>Merge &amp; Finalize</Text></>
                            )}
                          </TouchableOpacity>
                        )}
                      </View>

                      {contributeOpen && myP && (
                        <View style={styles.contribForm}>
                          <Text style={styles.inputLabel}>Your input / perspective</Text>
                          <TextInput
                            style={styles.contribInput}
                            placeholder="Share your view, reasoning or recommendation…"
                            placeholderTextColor={COLORS.textMuted}
                            value={contribNotes} onChangeText={setContribNotes}
                            multiline numberOfLines={3}
                          />
                          {modeId === 'voting' && (
                            <View style={{ marginTop: 10 }}>
                              <Text style={styles.inputLabel}>Your vote</Text>
                              <View style={{ flexDirection: 'row', gap: 8, marginTop: 6 }}>
                                <TouchableOpacity style={[styles.choiceBtn, contribVote === true && styles.choiceBtnYes]} onPress={() => setContribVote(true)}>
                                  <Text style={[styles.choiceText, contribVote === true && { color: '#FFF' }]}>👍 Yes</Text>
                                </TouchableOpacity>
                                <TouchableOpacity style={[styles.choiceBtn, contribVote === false && styles.choiceBtnNo]} onPress={() => setContribVote(false)}>
                                  <Text style={[styles.choiceText, contribVote === false && { color: '#FFF' }]}>👎 No</Text>
                                </TouchableOpacity>
                              </View>
                            </View>
                          )}
                          {modeId === 'consensus' && (
                            <View style={{ marginTop: 10 }}>
                              <Text style={styles.inputLabel}>Do you accept the proposal?</Text>
                              <View style={{ flexDirection: 'row', gap: 8, marginTop: 6 }}>
                                <TouchableOpacity style={[styles.choiceBtn, contribAccepted === true && styles.choiceBtnYes]} onPress={() => setContribAccepted(true)}>
                                  <Text style={[styles.choiceText, contribAccepted === true && { color: '#FFF' }]}>✓ Accept</Text>
                                </TouchableOpacity>
                                <TouchableOpacity style={[styles.choiceBtn, contribAccepted === false && styles.choiceBtnNo]} onPress={() => setContribAccepted(false)}>
                                  <Text style={[styles.choiceText, contribAccepted === false && { color: '#FFF' }]}>✕ Reject</Text>
                                </TouchableOpacity>
                              </View>
                            </View>
                          )}
                          <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#2563EB', marginTop: 12 }]}
                            onPress={submitContribution} disabled={submittingContrib}>
                            {submittingContrib ? <ActivityIndicator color="#FFF" size="small" /> : (
                              <><Ionicons name="send" size={14} color="#FFF" /><Text style={styles.verifyActionText}>Submit Contribution</Text></>
                            )}
                          </TouchableOpacity>
                        </View>
                      )}
                    </View>
                  );
                })()}

                {/* Result (after merge) */}
                {detailSession.status === 'completed' && detailSession.result && (
                  <View style={styles.resultCard}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                      <Ionicons name="checkmark-circle" size={18} color="#059669" />
                      <Text style={styles.resultTitle}>Finalized result · {detailSession.result.mode}</Text>
                    </View>
                    {!!detailSession.result.merge_details?.message && (
                      <Text style={styles.resultMsg}>{detailSession.result.merge_details.message}</Text>
                    )}
                    {!!detailSession.result.weights && (
                      <View style={{ marginTop: 8 }}>
                        <Text style={styles.inputLabel}>Contribution weights</Text>
                        {(detailSession.participants || []).map((p: any, i: number) => {
                          const w = detailSession.result.weights[p.linked_user_id] ?? detailSession.result.weights[p.contact_id];
                          if (w == null) return null;
                          return (<Text key={i} style={styles.weightRow}>{p.name || 'Participant'} — {Math.round(w * 100)}%</Text>);
                        })}
                        {detailSession.result.weights[detailSession.owner_id] != null && (
                          <Text style={styles.weightRow}>{detailSession.owner_name || 'You (owner)'} — {Math.round(detailSession.result.weights[detailSession.owner_id] * 100)}%</Text>
                        )}
                      </View>
                    )}
                  </View>
                )}
                <View style={{ height: 20 }} />
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>

      {/* Verification Modal */}
      <Modal visible={showVerifyModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, { maxHeight: 520 }]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Identity Verification</Text>
              <TouchableOpacity onPress={() => setShowVerifyModal(false)}>
                <Ionicons name="close" size={24} color={COLORS.textSecondary} />
              </TouchableOpacity>
            </View>
            
            <ScrollView style={{ maxHeight: 420 }} showsVerticalScrollIndicator={false}>
              <Text style={styles.stepHint}>Complete verification to participate in this session.</Text>

              {!advancedAuthEnabled ? renderOtpVerify() : (<>
              {/* DigiLocker */}
              <View style={styles.verifyCard}>
                <View style={styles.verifyCardHeader}>
                  <View style={[styles.verifyIcon, { backgroundColor: '#EEF2FF' }]}>
                    <Ionicons name="card" size={20} color="#6366F1" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.verifyCardTitle}>DigiLocker (Aadhaar / Country ID)</Text>
                    <Text style={styles.verifyCardDesc}>Govt-issued identity verification</Text>
                  </View>
                  {digilockerStatus?.verified ? (
                    <View style={styles.verifiedBadge}><Ionicons name="checkmark-circle" size={16} color="#059669" /><Text style={styles.verifiedText}>Verified</Text></View>
                  ) : null}
                </View>
                {!digilockerStatus?.verified && (
                  <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#6366F1' }]}
                    onPress={() => handleVerify('country_id')} disabled={verifying}>
                    {verifying ? <ActivityIndicator color="#FFF" size="small" /> : (
                      <><Ionicons name="open-outline" size={14} color="#FFF" /><Text style={styles.verifyActionText}>Initiate DigiLocker</Text></>
                    )}
                  </TouchableOpacity>
                )}
              </View>

              {/* Biometric */}
              <View style={styles.verifyCard}>
                <View style={styles.verifyCardHeader}>
                  <View style={[styles.verifyIcon, { backgroundColor: '#FFF7ED' }]}>
                    <Ionicons name="finger-print" size={20} color="#F97316" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.verifyCardTitle}>Biometric Authentication</Text>
                    <Text style={styles.verifyCardDesc}>Fingerprint / Retina via supported device</Text>
                  </View>
                  {biometricStatus?.registrations?.length > 0 ? (
                    <View style={styles.verifiedBadge}><Ionicons name="checkmark-circle" size={16} color="#059669" /><Text style={styles.verifiedText}>Enrolled</Text></View>
                  ) : null}
                </View>
                <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#F97316' }]}
                  onPress={() => handleVerify('biometric')} disabled={verifying}>
                  {verifying ? <ActivityIndicator color="#FFF" size="small" /> : (
                    <><Ionicons name="finger-print" size={14} color="#FFF" /><Text style={styles.verifyActionText}>{biometricStatus?.registrations?.length > 0 ? 'Re-register' : 'Register Biometric'}</Text></>
                  )}
                </TouchableOpacity>
              </View>

              {/* TOTP Authenticator */}
              <View style={styles.verifyCard}>
                <View style={styles.verifyCardHeader}>
                  <View style={[styles.verifyIcon, { backgroundColor: '#ECFDF5' }]}>
                    <Ionicons name="key" size={20} color="#059669" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.verifyCardTitle}>Authenticator App (TOTP)</Text>
                    <Text style={styles.verifyCardDesc}>Google Authenticator / Authy / Microsoft</Text>
                  </View>
                  {totpStatus?.totp_configured ? (
                    <View style={styles.verifiedBadge}><Ionicons name="checkmark-circle" size={16} color="#059669" /><Text style={styles.verifiedText}>Active</Text></View>
                  ) : null}
                </View>
                {!totpStatus?.totp_configured ? (
                  <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#059669' }]}
                    onPress={() => handleVerify('authenticator')} disabled={verifying}>
                    {verifying ? <ActivityIndicator color="#FFF" size="small" /> : (
                      <><Ionicons name="qr-code" size={14} color="#FFF" /><Text style={styles.verifyActionText}>Setup TOTP</Text></>
                    )}
                  </TouchableOpacity>
                ) : (
                  <View style={styles.totpVerifyRow}>
                    <TextInput style={styles.totpInput} placeholder="6-digit code" keyboardType="numeric"
                      maxLength={6} value={verifyInput} onChangeText={setVerifyInput} />
                    <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#059669', flex: 0 }]}
                      onPress={handleTotpVerify} disabled={verifying}>
                      {verifying ? <ActivityIndicator color="#FFF" size="small" /> : (
                        <Text style={styles.verifyActionText}>Verify</Text>
                      )}
                    </TouchableOpacity>
                  </View>
                )}
              </View>

              {/* Face Authentication */}
              <View style={styles.verifyCard}>
                <View style={styles.verifyCardHeader}>
                  <View style={[styles.verifyIcon, { backgroundColor: '#F0FDF4' }]}>
                    <Ionicons name="scan" size={20} color="#059669" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.verifyCardTitle}>Face Authentication + Liveness</Text>
                    <Text style={styles.verifyCardDesc}>Camera-based face match with continuous presence</Text>
                  </View>
                </View>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#059669' }]}
                    onPress={() => { setShowVerifyModal(false); router.push({ pathname: '/tools/face-auth', params: { mode: 'register' } } as any); }}>
                    <Ionicons name="person-add" size={14} color="#FFF" />
                    <Text style={styles.verifyActionText}>Register Face</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.verifyActionBtn, { backgroundColor: '#3B82F6' }]}
                    onPress={() => { setShowVerifyModal(false); router.push({ pathname: '/tools/face-auth', params: { mode: 'verify' } } as any); }}>
                    <Ionicons name="shield-checkmark" size={14} color="#FFF" />
                    <Text style={styles.verifyActionText}>Verify</Text>
                  </TouchableOpacity>
                </View>
              </View>
              </>)}

            </ScrollView>
          </View>
        </View>
      </Modal>

    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingTop: 12, paddingBottom: 18, gap: 12 },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  createHdrBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: '#FFF', justifyContent: 'center', alignItems: 'center' },
  emptyState: { alignItems: 'center', paddingVertical: 48, gap: 10 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptyText: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', paddingHorizontal: 32 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#7C3AED', paddingHorizontal: 20, paddingVertical: 12, borderRadius: 12, marginTop: 8 },
  sessionCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: '#E5E7EB' },
  sessionHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  sessionTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  sessionMeta: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  statusBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  statusText: { fontSize: 11, fontWeight: '700' },
  participantBar: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  participantText: { fontSize: 12, color: COLORS.textSecondary },
  sessionDate: { fontSize: 11, color: COLORS.textMuted },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  modalContent: { width: '100%', maxWidth: 500, backgroundColor: '#FFF', borderRadius: 24, padding: 24, maxHeight: '88%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  steps: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 20, paddingHorizontal: 8 },
  stepItem: { alignItems: 'center', gap: 4 },
  stepDot: { width: 28, height: 28, borderRadius: 14, backgroundColor: '#E5E7EB', justifyContent: 'center', alignItems: 'center' },
  stepDotText: { fontSize: 12, fontWeight: '700', color: COLORS.textMuted },
  stepLabel: { fontSize: 10, color: COLORS.textMuted },
  stepTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  stepHint: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 14 },
  noItems: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', padding: 20 },
  moduleCard: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 10, backgroundColor: '#F9FAFB', marginBottom: 8, borderWidth: 1, borderColor: '#E5E7EB' },
  moduleCardSelected: { borderColor: '#059669', backgroundColor: '#ECFDF5' },
  moduleType: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  moduleTitle: { flex: 1, fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  modeCard: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 10, backgroundColor: '#F9FAFB', marginBottom: 8, borderWidth: 1, borderColor: '#E5E7EB' },
  modeIcon: { width: 36, height: 36, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  modeName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  modeDesc: { fontSize: 11, color: COLORS.textSecondary, marginTop: 2 },
  notifySection: { marginTop: 12, gap: 8 },
  notifyRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  notifyText: { fontSize: 13, color: COLORS.textPrimary },
  contactSearchWrap: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#F9FAFB', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, borderWidth: 1, borderColor: '#E5E7EB' },
  contactSearchInput: { flex: 1, fontSize: 13, color: COLORS.textPrimary },
  smeBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB' },
  smeBtnText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },
  contactRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: 10, marginBottom: 6, backgroundColor: '#F9FAFB' },
  contactRowSelected: { backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0' },
  contactAvatar: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#6366F1', justifyContent: 'center', alignItems: 'center' },
  contactAvatarText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  contactName: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  contactDetail: { fontSize: 11, color: COLORS.textMuted },
  smeBadge: { padding: 2 },
  authMethodCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 12, backgroundColor: '#F9FAFB', marginBottom: 8, borderWidth: 1, borderColor: '#E5E7EB' },
  otpChannelBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB', backgroundColor: '#FFF' },
  otpChannelActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  otpChannelTxt: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  authMethodActive: { backgroundColor: '#EEF2FF', borderColor: '#C7D2FE' },
  authMethodLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  authMethodDesc: { fontSize: 11, color: COLORS.textSecondary },
  authRequiredBox: { marginTop: 12, backgroundColor: '#F5F3FF', borderRadius: 10, padding: 14, gap: 8 },
  authRequiredLabel: { fontSize: 13, fontWeight: '600', color: '#5B21B6' },
  reqBtn: { paddingHorizontal: 20, paddingVertical: 8, borderRadius: 8, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#DDD6FE' },
  reqBtnActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  reqBtnText: { fontSize: 13, fontWeight: '700', color: COLORS.textSecondary },
  verifyToggle: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: '#F3F4F6' },
  verifyText: { fontSize: 13, color: COLORS.textPrimary, flex: 1 },
  modalFooter: { flexDirection: 'row', alignItems: 'center', marginTop: 16, gap: 12 },
  prevBtn: { paddingHorizontal: 16, paddingVertical: 12, borderRadius: 10, backgroundColor: '#F3F4F6' },
  prevBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textSecondary },
  nextBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 20, paddingVertical: 12, borderRadius: 10, backgroundColor: '#7C3AED' },
  nextBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
  createBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 20, paddingVertical: 12, borderRadius: 10, backgroundColor: '#059669' },
  createBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },

  // Session Mode styles
  sessionModeCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 12, backgroundColor: '#F9FAFB', marginBottom: 8, borderWidth: 1.5, borderColor: '#E5E7EB' },
  sessionModeIcon: { width: 40, height: 40, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  sessionModeLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  sessionModeDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  liveSyncInfo: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#ECFDF5', padding: 10, borderRadius: 8, marginBottom: 12 },
  liveSyncInfoText: { fontSize: 11, color: '#059669', flex: 1 },
  inputLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },

  // Override styles
  overrideSection: { marginTop: 16, borderTopWidth: 1, borderTopColor: '#F3F4F6', paddingTop: 12 },
  overrideToggle: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  overrideLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  overrideHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  overrideFields: { marginTop: 12, backgroundColor: '#F5F3FF', borderRadius: 10, padding: 12, gap: 10 },
  overrideFieldRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  overrideFieldLabel: { fontSize: 12, fontWeight: '600', color: '#5B21B6', flex: 1 },
  overrideFieldInput: { width: 80, borderWidth: 1, borderColor: '#DDD6FE', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, fontSize: 14, fontWeight: '700', color: '#7C3AED', backgroundColor: '#FFF', textAlign: 'center' },

  // Session mode badge
  modeBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, marginLeft: 6 },
  modeBadgeText: { fontSize: 10, fontWeight: '600' },

  // Verify join button
  verifyJoinBtn: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, backgroundColor: '#F5F3FF', marginRight: 8 },
  verifyJoinText: { fontSize: 10, fontWeight: '600', color: '#7C3AED' },

  // Video Call join button
  joinCallBtn: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, marginTop: 8, borderRadius: 10, backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0' },
  joinCallIcon: { width: 32, height: 32, borderRadius: 10, backgroundColor: '#059669', justifyContent: 'center', alignItems: 'center' },
  joinCallTitle: { fontSize: 13, fontWeight: '700', color: '#059669' },
  joinCallSub: { fontSize: 10, color: '#6B7280', marginTop: 1 },

  // Verification Modal styles
  verifyCard: { backgroundColor: '#F9FAFB', borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#E5E7EB' },
  verifyCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  verifyIcon: { width: 36, height: 36, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  verifyCardTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  verifyCardDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  verifiedBadge: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, backgroundColor: '#ECFDF5' },
  verifiedText: { fontSize: 10, fontWeight: '600', color: '#059669' },
  verifyActionBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 8, flex: 1 },
  verifyActionText: { fontSize: 12, fontWeight: '700', color: '#FFF' },
  contribForm: { marginTop: 12, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 12, padding: 12 },
  contribInput: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8, padding: 10, fontSize: 13, color: COLORS.textPrimary, minHeight: 70, textAlignVertical: 'top' },
  choiceBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1', alignItems: 'center', backgroundColor: '#FFF' },
  choiceBtnYes: { backgroundColor: '#059669', borderColor: '#059669' },
  choiceBtnNo: { backgroundColor: '#DC2626', borderColor: '#DC2626' },
  choiceText: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  resultCard: { marginTop: 14, backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0', borderRadius: 12, padding: 14 },
  resultTitle: { fontSize: 14, fontWeight: '800', color: '#065F46' },
  resultMsg: { fontSize: 13, color: '#047857', lineHeight: 18 },
  weightRow: { fontSize: 12.5, color: '#065F46', marginTop: 3 },
  totpVerifyRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  totpInput: { flex: 1, borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 8, paddingHorizontal: 12, paddingVertical: 8, fontSize: 16, fontWeight: '700', letterSpacing: 4, textAlign: 'center' },
});
