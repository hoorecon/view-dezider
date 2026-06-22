import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Modal, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { Alert } from '../../src/utils/crossAlert';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { AudioGuidePlayer } from '../../src/components/AudioGuidePlayer';
import { VoiceTextInput } from '../../src/components/VoiceTextInput';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

interface Outlet {
  id: string; number: string; name: string; category: string;
  relief_type: string; duration: string; icon: string; color: string;
  description: string; instructions: string[]; tip: string;
  affirmation_text?: string; has_audio_play?: boolean;
  has_affirmation_browser?: boolean; has_journal_entry?: boolean;
  is_redirect?: boolean; redirect_to?: string;
  audio_url?: string; script?: string; has_guided_flow?: boolean;
}
interface AffirmationCategory {
  id: string; title: string; icon: string; frequency: string;
  note?: string; sections: { type: string; text: string }[];
}

const SECTION_LABELS: Record<string, { label: string; color: string }> = {
  invocation: { label: 'Invocation', color: '#7C3AED' },
  declaration: { label: 'Declaration', color: '#6366F1' },
  acknowledgement: { label: 'Acknowledgement', color: '#8B5CF6' },
  seeking: { label: 'Seeking Forgiveness', color: '#F59E0B' },
  granting: { label: 'Granting Forgiveness', color: '#10B981' },
  blessing: { label: 'Blessings & Peace', color: '#3B82F6' },
  manifestation: { label: 'Manifestation', color: '#EC4899' },
  gratitude: { label: 'Gratitude', color: '#D97706' },
  release: { label: 'Release', color: '#059669' },
};

const CATEGORY_ICONS: Record<string, { name: string; bg: string }> = {
  physical: { name: 'fitness', bg: '#FEE2E2' },
  energy: { name: 'sunny', bg: '#FEF3C7' },
  mental: { name: 'brain', bg: '#EDE9FE' },
  emotional: { name: 'heart', bg: '#D1FAE5' },
  spiritual: { name: 'sparkles', bg: '#E0E7FF' },
  behavioral: { name: 'git-compare', bg: '#DBEAFE' },
};

export default function EGAdvisorScreen() {
  const router = useRouter();
  const goBack = () => { if (router.canGoBack?.()) safeBack(router); else router.replace('/tools/emotional-gatekeeper' as any); };
  const [loading, setLoading] = useState(true);
  const [outlets, setOutlets] = useState<Outlet[]>([]);
  const [affirmations, setAffirmations] = useState<AffirmationCategory[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [practices, setPractices] = useState<any>(null);

  // Modals
  const [affirmModal, setAffirmModal] = useState(false);
  const [selectedAffirmation, setSelectedAffirmation] = useState<AffirmationCategory | null>(null);
  const [audioPlaying, setAudioPlaying] = useState<string | null>(null);
  const [gratitudeModal, setGratitudeModal] = useState(false);
  const [gratitudeEntries, setGratitudeEntries] = useState(['', '', '']);
  const [savingGratitude, setSavingGratitude] = useState(false);
  const [smsModal, setSmsModal] = useState(false);
  const [smsData, setSmsData] = useState<any>(null);
  const [loadingSms, setLoadingSms] = useState(false);

  // Timer for audio play
  const timerRef = useRef<any>(null);
  const [timerSeconds, setTimerSeconds] = useState(0);

  useEffect(() => {
    fetchData();
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  const fetchData = async () => {
    try {
      const [outletsRes, practicesRes] = await Promise.all([
        api.get('/emotional-gatekeeper/advisor/outlets'),
        api.get('/emotional-gatekeeper/advisor/my-practices'),
      ]);
      setOutlets(outletsRes.data.outlets || []);
      setAffirmations(outletsRes.data.forgiveness_affirmations || []);
      setPractices(practicesRes.data);
    } catch (err) { console.error(err); }
    finally { setLoading(false); }
  };

  const logPractice = async (outletId: string, extras?: any) => {
    try {
      await api.post('/emotional-gatekeeper/advisor/practice-log', {
        outlet_id: outletId, ...extras,
      });
      // Refresh practices
      const res = await api.get('/emotional-gatekeeper/advisor/my-practices');
      setPractices(res.data);
      Alert.alert('Logged!', 'Practice recorded. Keep going!');
    } catch (err) {
      console.error(err);
    }
  };

  const startAudioTimer = (outletId: string, durationSec: number) => {
    if (audioPlaying === outletId) {
      // Stop
      if (timerRef.current) clearInterval(timerRef.current);
      setAudioPlaying(null);
      setTimerSeconds(0);
      logPractice(outletId, { duration_seconds: durationSec });
      return;
    }
    setAudioPlaying(outletId);
    setTimerSeconds(durationSec);
    timerRef.current = setInterval(() => {
      setTimerSeconds(prev => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          setAudioPlaying(null);
          logPractice(outletId, { duration_seconds: durationSec });
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const openForgivenessBrowser = () => {
    setAffirmModal(true);
  };

  const openSmsRecommendations = async () => {
    setSmsModal(true);
    setLoadingSms(true);
    try {
      const res = await api.get('/emotional-gatekeeper/advisor/sms-recommendations');
      setSmsData(res.data);
    } catch (err) { console.error(err); }
    finally { setLoadingSms(false); }
  };

  const saveGratitude = async () => {
    const filled = gratitudeEntries.filter(e => e.trim());
    if (filled.length === 0) { Alert.alert('Required', 'Write at least one gratitude entry.'); return; }
    setSavingGratitude(true);
    try {
      await api.post('/emotional-gatekeeper/advisor/gratitude', { entries: filled });
      setGratitudeModal(false);
      setGratitudeEntries(['', '', '']);
      const res = await api.get('/emotional-gatekeeper/advisor/my-practices');
      setPractices(res.data);
      Alert.alert('Saved!', 'Gratitude journal entry recorded.');
    } catch (err) { Alert.alert('Error', 'Failed to save.'); }
    finally { setSavingGratitude(false); }
  };

  const handleOutletAction = (outlet: Outlet) => {
    if ((outlet as any).has_guided_flow) {
      router.push('/tools/eg-emotional-reception' as any);
    } else if (outlet.has_affirmation_browser) {
      openForgivenessBrowser();
    } else if (outlet.has_journal_entry) {
      setGratitudeModal(true);
    } else if (outlet.is_redirect) {
      openSmsRecommendations();
    } else if (outlet.has_audio_play) {
      startAudioTimer(outlet.id, 120);
    } else {
      logPractice(outlet.id);
    }
  };

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Group outlets by category
  const grouped = outlets.reduce((acc: Record<string, Outlet[]>, o) => {
    const cat = o.category;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(o);
    return acc;
  }, {});

  if (loading) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#10B981" />
          <Text style={{ marginTop: 12, color: COLORS.textMuted }}>Loading Advisor...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 60 }}>
        {/* Header */}
        <LinearGradient colors={['#10B981', '#059669', '#047857']} style={s.header}>
          <TouchableOpacity style={s.backBtn} onPress={goBack}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <Text style={s.headerTitle}>Effective Outlets Advisor</Text>
          <Text style={s.headerSub}>9 constructive techniques to replace destructive habits</Text>
        </LinearGradient>

        {/* Iter 133 — cross-nav strip: jump to any other EG sub-flow */}
        <View style={egNavStrip.wrap}>
          <Text style={egNavStrip.head}>Jump to another EG flow:</Text>
          <View style={egNavStrip.row}>
            {[
              { label: 'Reception', href: '/tools/eg-emotional-reception', color: '#0EA5E9' },
              { label: 'Trap', href: '/tools/eg-trap', color: '#EF4444' },
              { label: 'Loop', href: '/tools/eg-loop', color: '#8B5CF6' },
              { label: 'Limitations', href: '/tools/eg-limitation', color: '#3B82F6' },
              { label: 'Tenses & Feels', href: '/tools/tenses-feels', color: '#F59E0B' },
              { label: 'Goals & Feels', href: '/tools/goals-feels', color: '#8B5CF6' },
            ].map(x => (
              <TouchableOpacity key={x.label} style={[egNavStrip.chip, { borderColor: x.color }]} onPress={() => router.push(x.href as any)}>
                <Text style={[egNavStrip.chipText, { color: x.color }]}>{x.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={s.content}>
          {/* Streak Card */}
          {practices?.stats && (
            <View style={s.statsCard}>
              <View style={s.statItem}>
                <Text style={s.statEmoji}>🔥</Text>
                <Text style={s.statNum}>{practices.stats.streak}</Text>
                <Text style={s.statLabel}>Day Streak</Text>
              </View>
              <View style={s.statDivider} />
              <View style={s.statItem}>
                <Text style={s.statNum}>{practices.stats.total_practices}</Text>
                <Text style={s.statLabel}>Total Practices</Text>
              </View>
              <View style={s.statDivider} />
              <View style={s.statItem}>
                <Text style={s.statNum}>{practices.stats.unique_days}</Text>
                <Text style={s.statLabel}>Active Days</Text>
              </View>
            </View>
          )}

          {/* Sequential numbering counter — increments across category
              groups so users see 1, 2, 3 ... in reading order regardless
              of how the backend grouped them. */}
          {(() => { /* reset counter on every render */ return null; })()}
          {(() => {
            // We rebuild the grouped list here so we can hand a sequential
            // number to each outlet card below. The counter is a closure
            // local to this render pass.
            (globalThis as any).__outletNum = 0;
            return null;
          })()}
          {Object.entries(grouped).map(([cat, items]) => {
            const catInfo = CATEGORY_ICONS[cat] || { name: 'ellipse', bg: '#F3F4F6' };
            return (
              <View key={cat}>
                <View style={s.catHeader}>
                  <View style={[s.catIconBg, { backgroundColor: catInfo.bg }]}>
                    <Ionicons name={catInfo.name as any} size={16} color={items[0]?.color || '#666'} />
                  </View>
                  <Text style={s.catTitle}>{cat.charAt(0).toUpperCase() + cat.slice(1)}</Text>
                </View>
                {items.map(outlet => {
                  const isExpanded = expanded === outlet.id;
                  const practiceCount = practices?.stats?.outlet_counts?.[outlet.id] || 0;
                  const isPlayingThis = audioPlaying === outlet.id;
                  // Assign sequential number 1..N across all groups.
                  const seqNum = (++(globalThis as any).__outletNum);

                  // Push-to-lifestyle deep-links. Regular routine →
                  // /tools/lifestyle-designer; on-demand CTT →
                  // /tools/action-center. The receiving screens read these
                  // params on mount and pre-fill their add-form.
                  const pushToDesigner = () => router.push({
                    pathname: '/tools/lifestyle-designer' as any,
                    params: {
                      bootstrap: '1',
                      title: outlet.name,
                      duration: outlet.duration,
                      category: cat,
                      cadence: 'daily',
                    },
                  });
                  const pushToAction = () => router.push({
                    pathname: '/tools/action-center' as any,
                    params: {
                      bootstrap: '1',
                      title: outlet.name,
                      notes: `${outlet.relief_type} • ${outlet.duration}`,
                      source: 'eg_outlet',
                    },
                  });

                  return (
                    <View key={outlet.id}>
                      <TouchableOpacity
                        style={[s.outletCard, isExpanded && { borderColor: outlet.color, borderWidth: 2 }]}
                        onPress={() => setExpanded(isExpanded ? null : outlet.id)}
                        activeOpacity={0.7}
                      >
                        <View style={[s.outletNum, { backgroundColor: outlet.color }]}>
                          <Text style={s.outletNumText}>{seqNum}</Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={s.outletName}>{outlet.name}</Text>
                          <Text style={s.outletRelief}>{outlet.relief_type} • {outlet.duration}</Text>
                        </View>
                        {/* Push-to-Lifestyle icons (right-aligned, before
                            the chevron). Each opens the target planner
                            pre-filled with this outlet. */}
                        <TouchableOpacity
                          testID={`outlet-${outlet.id}-to-designer`}
                          onPress={(e) => { e.stopPropagation?.(); pushToDesigner(); }}
                          style={s.pushIconBtn}
                          accessibilityLabel="Add to Lifestyle Designer (regular routine)"
                        >
                          <Ionicons name="calendar" size={16} color="#7C3AED" />
                        </TouchableOpacity>
                        <TouchableOpacity
                          testID={`outlet-${outlet.id}-to-action`}
                          onPress={(e) => { e.stopPropagation?.(); pushToAction(); }}
                          style={s.pushIconBtn}
                          accessibilityLabel="Add to Action Center (on-demand CTT)"
                        >
                          <Ionicons name="flash" size={16} color="#F97316" />
                        </TouchableOpacity>
                        {practiceCount > 0 && (
                          <View style={s.pracBadge}>
                            <Text style={s.pracBadgeText}>{practiceCount}×</Text>
                          </View>
                        )}
                        <Ionicons name={isExpanded ? 'chevron-up' : 'chevron-down'} size={18} color={COLORS.textMuted} />
                      </TouchableOpacity>

                      {isExpanded && (
                        <View style={[s.expandedCard, { borderLeftColor: outlet.color }]}>
                          <Text style={s.expandDesc}>{outlet.description}</Text>

                          {/* Script Text (detailed IVR content) */}
                          {(outlet as any).script && (
                            <View style={s.scriptBox}>
                              <Text style={s.scriptText}>{(outlet as any).script}</Text>
                            </View>
                          )}

                          {/* Audio Guide Player */}
                          {outlet.audio_url && (
                            <AudioGuidePlayer
                              uri={outlet.audio_url}
                              title={`Listen: ${outlet.name}`}
                              color={outlet.color}
                            />
                          )}

                          {/* Instructions */}
                          <Text style={s.instrTitle}>How to Practice:</Text>
                          {outlet.instructions.map((inst, i) => (
                            <View key={i} style={s.instrRow}>
                              <View style={[s.instrDot, { backgroundColor: outlet.color }]}>
                                <Text style={s.instrDotText}>{i + 1}</Text>
                              </View>
                              <Text style={s.instrText}>{inst}</Text>
                            </View>
                          ))}

                          {/* Affirmation Text (Release & HOORECON) */}
                          {outlet.affirmation_text && (
                            <View style={[s.affirmBox, { borderColor: outlet.color }]}>
                              <Text style={s.affirmLabel}>Repeat this affirmation:</Text>
                              <Text style={[s.affirmText, { color: outlet.color }]}>
                                "{outlet.affirmation_text}"
                              </Text>
                            </View>
                          )}

                          {/* Tip */}
                          <View style={s.tipBox}>
                            <Ionicons name="bulb" size={16} color="#D97706" />
                            <Text style={s.tipText}>{outlet.tip}</Text>
                          </View>

                          {/* Action Button */}
                          {(outlet as any).has_guided_flow && (
                            <TouchableOpacity
                              style={[s.actionBtn, { backgroundColor: outlet.color }]}
                              onPress={() => router.push('/tools/eg-emotional-reception' as any)}
                            >
                              <Ionicons name="play-circle" size={20} color="#FFF" />
                              <Text style={s.actionBtnText}>Start 5-Minute Guided Practice</Text>
                            </TouchableOpacity>
                          )}

                          {outlet.has_audio_play && (
                            <TouchableOpacity
                              style={[s.actionBtn, { backgroundColor: isPlayingThis ? '#EF4444' : outlet.color }]}
                              onPress={() => startAudioTimer(outlet.id, 120)}
                            >
                              <Ionicons name={isPlayingThis ? 'stop-circle' : 'play-circle'} size={20} color="#FFF" />
                              <Text style={s.actionBtnText}>
                                {isPlayingThis ? `Stop (${formatTime(timerSeconds)})` : 'Start 2-Minute Timer'}
                              </Text>
                            </TouchableOpacity>
                          )}

                          {outlet.has_affirmation_browser && (
                            <TouchableOpacity
                              style={[s.actionBtn, { backgroundColor: outlet.color }]}
                              onPress={openForgivenessBrowser}
                            >
                              <Ionicons name="book" size={18} color="#FFF" />
                              <Text style={s.actionBtnText}>Browse 7 Affirmation Categories</Text>
                            </TouchableOpacity>
                          )}

                          {outlet.has_journal_entry && (
                            <TouchableOpacity
                              style={[s.actionBtn, { backgroundColor: outlet.color }]}
                              onPress={() => setGratitudeModal(true)}
                            >
                              <Ionicons name="create" size={18} color="#FFF" />
                              <Text style={s.actionBtnText}>Write Gratitude Journal</Text>
                            </TouchableOpacity>
                          )}

                          {outlet.is_redirect && (
                            <TouchableOpacity
                              style={[s.actionBtn, { backgroundColor: outlet.color }]}
                              onPress={openSmsRecommendations}
                            >
                              <Ionicons name="arrow-forward-circle" size={18} color="#FFF" />
                              <Text style={s.actionBtnText}>View My SMS Recommendations</Text>
                            </TouchableOpacity>
                          )}

                          {/* Log Practice */}
                          {!outlet.has_audio_play && !outlet.has_affirmation_browser && !outlet.has_journal_entry && !outlet.is_redirect && (
                            <TouchableOpacity
                              style={[s.logBtn, { borderColor: outlet.color }]}
                              onPress={() => logPractice(outlet.id)}
                            >
                              <Ionicons name="checkmark-circle" size={18} color={outlet.color} />
                              <Text style={[s.logBtnText, { color: outlet.color }]}>Mark as Practiced</Text>
                            </TouchableOpacity>
                          )}
                        </View>
                      )}
                    </View>
                  );
                })}
              </View>
            );
          })}
        </View>
      </ScrollView>

      {/* ── Forgiveness Affirmation Browser Modal ── */}
      <Modal visible={affirmModal} animationType="slide" presentationStyle="pageSheet">
        <SafeAreaView style={s.modalContainer} edges={['top']}>
          <View style={s.modalHeader}>
            <Text style={s.modalTitle}>Forgiveness Affirmations</Text>
            <TouchableOpacity onPress={() => { setAffirmModal(false); setSelectedAffirmation(null); }}>
              <Ionicons name="close-circle" size={28} color={COLORS.textMuted} />
            </TouchableOpacity>
          </View>
          <Text style={s.modalSubtitle}>Courtesy: Prana Violet Healing</Text>

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 40 }}>
            {!selectedAffirmation ? (
              <View style={s.affirmList}>
                {affirmations.map(af => (
                  <TouchableOpacity
                    key={af.id}
                    style={s.affirmCatCard}
                    onPress={() => setSelectedAffirmation(af)}
                  >
                    <View style={s.affirmCatIcon}>
                      <Ionicons name={af.icon as any} size={22} color="#7C3AED" />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.affirmCatTitle}>{af.title}</Text>
                      <Text style={s.affirmCatFreq}>{af.frequency}</Text>
                      {af.note && <Text style={s.affirmCatNote}>{af.note}</Text>}
                    </View>
                    <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
                  </TouchableOpacity>
                ))}
              </View>
            ) : (
              <View style={s.affirmDetail}>
                <TouchableOpacity style={s.affirmBack} onPress={() => setSelectedAffirmation(null)}>
                  <Ionicons name="arrow-back" size={18} color="#7C3AED" />
                  <Text style={s.affirmBackText}>All Categories</Text>
                </TouchableOpacity>
                <Text style={s.affirmDetailTitle}>{selectedAffirmation.title}</Text>
                <Text style={s.affirmDetailFreq}>{selectedAffirmation.frequency}</Text>
                {selectedAffirmation.note && (
                  <View style={s.noteBox}>
                    <Ionicons name="warning" size={16} color="#D97706" />
                    <Text style={s.noteText}>{selectedAffirmation.note}</Text>
                  </View>
                )}
                {selectedAffirmation.sections.map((sec, i) => {
                  const info = SECTION_LABELS[sec.type] || { label: sec.type, color: '#6B7280' };
                  return (
                    <View key={i} style={s.affirmSection}>
                      <View style={[s.sectionBadge, { backgroundColor: info.color }]}>
                        <Text style={s.sectionBadgeText}>{info.label}</Text>
                      </View>
                      <Text style={s.sectionText}>{sec.text}</Text>
                    </View>
                  );
                })}
                <TouchableOpacity
                  style={[s.actionBtn, { backgroundColor: '#7C3AED', marginTop: 20 }]}
                  onPress={() => {
                    logPractice('forgiveness_affirmations', { affirmation_category: selectedAffirmation.id });
                    setSelectedAffirmation(null);
                    setAffirmModal(false);
                  }}
                >
                  <Ionicons name="checkmark-circle" size={18} color="#FFF" />
                  <Text style={s.actionBtnText}>Mark as Practiced</Text>
                </TouchableOpacity>
              </View>
            )}
          </ScrollView>
        </SafeAreaView>
      </Modal>

      {/* ── Gratitude Journal Modal ── */}
      <Modal visible={gratitudeModal} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={s.gratModal}>
            <View style={s.gratHeader}>
              <Text style={s.gratTitle}>Gratitude Journal</Text>
              <TouchableOpacity onPress={() => setGratitudeModal(false)}>
                <Ionicons name="close-circle" size={26} color={COLORS.textMuted} />
              </TouchableOpacity>
            </View>
            <Text style={s.gratHint}>Write 3 things you're grateful for today:</Text>
            {gratitudeEntries.map((entry, i) => (
              <View key={i} style={s.gratInputRow}>
                <Text style={s.gratNum}>{i + 1}.</Text>
                <View style={{ flex: 1 }}>
                  <VoiceTextInput
                    inputStyle={s.gratInput}
                    placeholder={`I'm grateful for...`}
                    value={entry}
                    onChangeText={(t) => {
                      const newEntries = [...gratitudeEntries];
                      newEntries[i] = t;
                      setGratitudeEntries(newEntries);
                    }}
                    placeholderTextColor={COLORS.textMuted}
                    sessionId=""
                    field={`gratitude_${i + 1}`}
                    color="#059669"
                    module="eg-generic"
                  />
                </View>
              </View>
            ))}
            <TouchableOpacity
              style={s.gratAddBtn}
              onPress={() => setGratitudeEntries(prev => [...prev, ''])}
            >
              <Ionicons name="add" size={16} color="#059669" />
              <Text style={s.gratAddText}>Add More</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.gratSaveBtn} onPress={saveGratitude} disabled={savingGratitude}>
              {savingGratitude ? <ActivityIndicator color="#FFF" /> :
                <><Ionicons name="heart" size={18} color="#FFF" /><Text style={s.gratSaveBtnText}>Save Journal Entry</Text></>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* ── SMS Recommendations Modal ── */}
      <Modal visible={smsModal} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <View style={[s.gratModal, { maxHeight: '80%' }]}>
            <View style={s.gratHeader}>
              <Text style={s.gratTitle}>Your SMS Recommendations</Text>
              <TouchableOpacity onPress={() => setSmsModal(false)}>
                <Ionicons name="close-circle" size={26} color={COLORS.textMuted} />
              </TouchableOpacity>
            </View>
            {loadingSms ? (
              <ActivityIndicator size="large" color="#3B82F6" style={{ marginTop: 20 }} />
            ) : !smsData?.has_analysis ? (
              <View style={{ padding: 20, alignItems: 'center' }}>
                <Ionicons name="analytics" size={40} color={COLORS.textMuted} />
                <Text style={{ fontSize: 14, color: COLORS.textMuted, textAlign: 'center', marginTop: 12 }}>
                  {smsData?.message || 'Complete the Outlet Analyzer first to get personalised recommendations.'}
                </Text>
                <TouchableOpacity
                  style={[s.actionBtn, { backgroundColor: '#10B981', marginTop: 16 }]}
                  onPress={() => { setSmsModal(false); router.push('/tools/emotional-gatekeeper' as any); }}
                >
                  <Text style={s.actionBtnText}>Go to Outlet Analyzer</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <ScrollView showsVerticalScrollIndicator={false} style={{ flex: 1 }}>
                {smsData.overall_pattern && (
                  <View style={s.smsPattern}>
                    <Ionicons name="bulb" size={16} color="#065F46" />
                    <Text style={s.smsPatternText}>{smsData.overall_pattern}</Text>
                  </View>
                )}
                {smsData.recommendations?.map((rec: any, i: number) => (
                  <View key={i} style={s.smsCard}>
                    <View style={s.smsFrom}>
                      <Ionicons name="close-circle" size={16} color="#EF4444" />
                      <Text style={s.smsFromText}>{rec.destructive_habit}</Text>
                    </View>
                    <Ionicons name="arrow-down" size={18} color={COLORS.textMuted} style={{ alignSelf: 'center' }} />
                    <View style={s.smsTo}>
                      <Ionicons name="checkmark-circle" size={16} color="#10B981" />
                      <View style={{ flex: 1 }}>
                        <Text style={s.smsToText}>{rec.alternative}</Text>
                        <Text style={s.smsWhy}>{rec.why}</Text>
                      </View>
                    </View>
                  </View>
                ))}
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { padding: 20, paddingTop: 8, paddingBottom: 24, borderBottomLeftRadius: 24, borderBottomRightRadius: 24 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginBottom: 10 },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#FFF' },
  headerSub: { fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 4 },
  content: { padding: 16 },
  statsCard: {
    flexDirection: 'row', backgroundColor: '#FFF', borderRadius: 14, padding: 16,
    marginBottom: 20, borderWidth: 1, borderColor: '#D1FAE5',
    justifyContent: 'space-around', alignItems: 'center',
  },
  statItem: { alignItems: 'center' },
  statEmoji: { fontSize: 24 },
  statNum: { fontSize: 22, fontWeight: '800', color: '#059669' },
  statLabel: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },
  statDivider: { width: 1, height: 30, backgroundColor: COLORS.border },
  catHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 16, marginBottom: 10 },
  catIconBg: { width: 28, height: 28, borderRadius: 8, justifyContent: 'center', alignItems: 'center' },
  catTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, textTransform: 'uppercase', letterSpacing: 0.5 },
  outletCard: {
    flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF',
    borderRadius: 12, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: COLORS.border,
  },
  outletNum: { width: 36, height: 36, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  outletNumText: { fontSize: 13, fontWeight: '800', color: '#FFF' },
  outletName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  outletRelief: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  pracBadge: { backgroundColor: '#ECFDF5', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  pushIconBtn: {
    padding: 6, marginHorizontal: 2, borderRadius: 8,
    backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0',
  },
  pracBadgeText: { fontSize: 11, fontWeight: '700', color: '#059669' },
  expandedCard: {
    backgroundColor: '#FAFAFA', borderRadius: 12, padding: 14, marginBottom: 8,
    marginLeft: 8, borderLeftWidth: 3,
  },
  expandDesc: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19, marginBottom: 12 },
  scriptBox: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 14, marginBottom: 12, borderLeftWidth: 3, borderLeftColor: '#CBD5E1' },
  scriptText: { fontSize: 13, color: '#475569', lineHeight: 20, fontStyle: 'italic' },
  instrTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  instrRow: { flexDirection: 'row', gap: 8, marginBottom: 6, alignItems: 'flex-start' },
  instrDot: { width: 22, height: 22, borderRadius: 11, justifyContent: 'center', alignItems: 'center' },
  instrDotText: { fontSize: 10, fontWeight: '800', color: '#FFF' },
  instrText: { fontSize: 12, color: COLORS.textSecondary, flex: 1, lineHeight: 17 },
  affirmBox: {
    backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginTop: 12,
    borderWidth: 1, borderStyle: 'dashed',
  },
  affirmLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted, marginBottom: 6, textTransform: 'uppercase' },
  affirmText: { fontSize: 14, fontWeight: '600', lineHeight: 22, fontStyle: 'italic' },
  tipBox: { flexDirection: 'row', gap: 6, backgroundColor: '#FFFBEB', borderRadius: 10, padding: 10, marginTop: 12 },
  tipText: { fontSize: 12, color: '#92400E', flex: 1, lineHeight: 16 },
  actionBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    borderRadius: 12, paddingVertical: 14, marginTop: 12,
  },
  actionBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  logBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    borderRadius: 12, paddingVertical: 12, marginTop: 12, borderWidth: 1.5, borderStyle: 'dashed',
  },
  logBtnText: { fontSize: 13, fontWeight: '600' },

  // Modal styles
  modalContainer: { flex: 1, backgroundColor: COLORS.background },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, paddingBottom: 4 },
  modalTitle: { fontSize: 20, fontWeight: '800', color: COLORS.textPrimary },
  modalSubtitle: { fontSize: 12, color: COLORS.textMuted, paddingHorizontal: 16, marginBottom: 12 },
  affirmList: { padding: 16 },
  affirmCatCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFF',
    borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#EDE9FE',
  },
  affirmCatIcon: { width: 44, height: 44, borderRadius: 12, backgroundColor: '#EDE9FE', justifyContent: 'center', alignItems: 'center' },
  affirmCatTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  affirmCatFreq: { fontSize: 11, color: '#7C3AED', marginTop: 2 },
  affirmCatNote: { fontSize: 10, color: '#D97706', marginTop: 2, fontStyle: 'italic' },
  affirmDetail: { padding: 16 },
  affirmBack: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 12 },
  affirmBackText: { fontSize: 13, fontWeight: '600', color: '#7C3AED' },
  affirmDetailTitle: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary, marginBottom: 4 },
  affirmDetailFreq: { fontSize: 12, color: '#7C3AED', marginBottom: 12 },
  noteBox: { flexDirection: 'row', gap: 6, backgroundColor: '#FFFBEB', borderRadius: 10, padding: 10, marginBottom: 12 },
  noteText: { fontSize: 12, color: '#92400E', flex: 1 },
  affirmSection: { marginBottom: 14 },
  sectionBadge: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, marginBottom: 6 },
  sectionBadgeText: { fontSize: 10, fontWeight: '700', color: '#FFF', textTransform: 'uppercase' },
  sectionText: { fontSize: 14, color: COLORS.textPrimary, lineHeight: 22 },

  // Gratitude Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  gratModal: { backgroundColor: '#FFF', borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: 20, maxHeight: '70%' },
  gratHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  gratTitle: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary },
  gratHint: { fontSize: 13, color: COLORS.textMuted, marginBottom: 12 },
  gratInputRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  gratNum: { fontSize: 16, fontWeight: '800', color: '#059669', width: 24 },
  gratInput: { flex: 1, backgroundColor: '#F0FDF4', borderRadius: 10, padding: 12, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: '#D1FAE5' },
  gratAddBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8 },
  gratAddText: { fontSize: 12, fontWeight: '600', color: '#059669' },
  gratSaveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#059669', borderRadius: 12, paddingVertical: 14, marginTop: 8 },
  gratSaveBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },

  // SMS Modal
  smsPattern: { flexDirection: 'row', gap: 8, backgroundColor: '#ECFDF5', borderRadius: 12, padding: 14, marginHorizontal: 16, marginBottom: 12 },
  smsPatternText: { fontSize: 13, color: '#065F46', flex: 1, lineHeight: 18 },
  smsCard: { backgroundColor: '#F9FAFB', borderRadius: 12, padding: 12, marginHorizontal: 16, marginBottom: 10 },
  smsFrom: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  smsFromText: { fontSize: 13, color: '#991B1B', textDecorationLine: 'line-through', flex: 1 },
  smsTo: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  smsToText: { fontSize: 13, fontWeight: '700', color: '#065F46' },
  smsWhy: { fontSize: 11, color: '#047857', marginTop: 2 },
});


const egNavStrip = StyleSheet.create({
  wrap: { margin: 14, marginBottom: 0, padding: 10, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  head: { fontSize: 11, color: '#64748B', fontWeight: '700' },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 },
  chip: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12, borderWidth: 1.5, backgroundColor: '#FFF' },
  chipText: { fontSize: 11, fontWeight: '700' },
});