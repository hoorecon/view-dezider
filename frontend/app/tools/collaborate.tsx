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

export default function CollaborateScreen() {
  const router = useRouter();
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Create session
  const [showCreate, setShowCreate] = useState(false);
  const [createStep, setCreateStep] = useState(0); // 0=select module, 1=select mode, 2=select participants, 3=auth config
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

  const fetchSessions = async () => {
    try {
      const res = await api.get('/collaboration/sessions');
      setSessions(res.data || []);
    } catch (err) {
      console.error('Error fetching sessions:', err);
    } finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { fetchSessions(); }, []));

  const onRefresh = async () => { setRefreshing(true); await fetchSessions(); setRefreshing(false); };

  const startCreate = async () => {
    setShowCreate(true);
    setCreateStep(0);
    setSelectedModule(null);
    setSelectedMode('equal');
    setSelectedContacts(new Set());
    setAuthConfig({ methods_required: 0, verify_each_time: false, enabled_methods: [] });

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
          <Text style={styles.stepHint}>Choose the PRR Decision or Solution Finder to collaborate on.</Text>
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
          <ScrollView style={{ maxHeight: 320 }} showsVerticalScrollIndicator={false}>
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
          <Text style={styles.stepTitle}>Participant Authentication</Text>
          <Text style={styles.stepHint}>Configure identity verification for participants. Select which methods and how many required.</Text>
          
          {AUTH_METHODS.map(m => (
            <TouchableOpacity key={m.key} style={[styles.authMethodCard, authConfig.enabled_methods.includes(m.key) && styles.authMethodActive]}
              onPress={() => toggleAuth(m.key)}>
              <Ionicons name={m.icon as any} size={22} color={authConfig.enabled_methods.includes(m.key) ? '#6366F1' : COLORS.textMuted} />
              <View style={{ flex: 1 }}>
                <Text style={styles.authMethodLabel}>{m.label}</Text>
                <Text style={styles.authMethodDesc}>{m.desc}</Text>
              </View>
              <Ionicons name={authConfig.enabled_methods.includes(m.key) ? 'checkbox' : 'square-outline'} size={22}
                color={authConfig.enabled_methods.includes(m.key) ? '#6366F1' : '#D1D5DB'} />
            </TouchableOpacity>
          ))}

          {authConfig.enabled_methods.length >= 2 && (
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

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#7C3AED', '#A855F7']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
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
                <TouchableOpacity key={s.id} style={styles.sessionCard} activeOpacity={0.7}>
                  <View style={styles.sessionHeader}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.sessionTitle} numberOfLines={1}>{s.title}</Text>
                      <Text style={styles.sessionMeta}>{s.module_type === 'decision' ? 'PRR Decision' : 'Solution Finder'} • {s.decision_mode?.name}</Text>
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
                    <View style={{ flex: 1 }} />
                    <Text style={styles.sessionDate}>
                      {new Date(s.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                    </Text>
                  </View>
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
                {['Module', 'Mode', 'People', 'Auth'].map((s, i) => (
                  <View key={i} style={styles.stepItem}>
                    <View style={[styles.stepDot, createStep >= i && { backgroundColor: '#7C3AED' }]}>
                      <Text style={[styles.stepDotText, createStep >= i && { color: '#FFF' }]}>{i + 1}</Text>
                    </View>
                    <Text style={[styles.stepLabel, createStep === i && { color: '#7C3AED', fontWeight: '700' }]}>{s}</Text>
                  </View>
                ))}
              </View>

              <ScrollView style={{ maxHeight: 440 }} showsVerticalScrollIndicator={false}>
                {renderCreateStep()}
              </ScrollView>

              <View style={styles.modalFooter}>
                {createStep > 0 && (
                  <TouchableOpacity style={styles.prevBtn} onPress={() => setCreateStep(createStep - 1)}>
                    <Text style={styles.prevBtnText}>Back</Text>
                  </TouchableOpacity>
                )}
                <View style={{ flex: 1 }} />
                {createStep < 3 ? (
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
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end', alignItems: 'center' },
  modalContent: { width: '100%', maxWidth: 500, backgroundColor: '#FFF', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 24, maxHeight: '90%' },
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
});
