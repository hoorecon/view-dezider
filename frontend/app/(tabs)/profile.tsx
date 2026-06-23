import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Image,
  ActivityIndicator,
  Platform,
  Modal,
  Linking,
  TextInput,
} from 'react-native';
import ReportShareSheet, { downloadReportPdf } from '../../src/components/ReportShareSheet';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useAuthStore } from '../../src/store/authStore';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import { GradientButton } from '../../src/components/GradientButton';
import { Input } from '../../src/components/Input';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { useAiWalletStore } from '../../src/store/aiWalletStore';

const GENDER_OPTIONS = ['Male', 'Female', 'Other', 'Prefer not to say'];

interface AssessmentQuestion {
  id: string;
  text: string;
  mode: string;
}

export default function ProfileScreen() {
  const router = useRouter();
  const { user, logout, checkAuth } = useAuthStore();
  const aiBalance = useAiWalletStore((s) => s.balance);
  const refreshAiWallet = useAiWalletStore((s) => s.refresh);
  const [picBusy, setPicBusy] = useState(false);
  const [genderModalOpen, setGenderModalOpen] = useState(false);
  const [savingGender, setSavingGender] = useState(false);
  const [questions, setQuestions] = useState<AssessmentQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [assessmentResult, setAssessmentResult] = useState<any>(null);
  const [showQuiz, setShowQuiz] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [subjectType, setSubjectType] = useState<'self' | 'other'>('self');
  const [subjectName, setSubjectName] = useState('');
  const [subjectWhatsapp, setSubjectWhatsapp] = useState('');
  const [insightBusy, setInsightBusy] = useState<string | null>(null);
  const [pdfBusy, setPdfBusy] = useState<string | null>(null);
  const [shareTarget, setShareTarget] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  // Set Password state
  const [showSetPassword, setShowSetPassword] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [hasPassword, setHasPassword] = useState(false);

  // Role — used only to conditionally show admin quick-links (server enforces real access)
  const [userRole, setUserRole] = useState('user');

  useEffect(() => {
    fetchQuestions();
    fetchLatestAssessment();
    fetchUserInfo();
    refreshAiWallet();
  }, []);

  const fetchUserInfo = async () => {
    try {
      const response = await api.get('/auth/me');
      setHasPassword(response.data.has_password || false);
      setUserRole(response.data.role || 'user');
    } catch (error) {
      console.error('Error fetching user info:', error);
    }
  };

  const fetchQuestions = async () => {
    try {
      const response = await api.get('/assessment/questions');
      setQuestions(response.data.questions);
    } catch (error) {
      console.error('Error fetching questions:', error);
    }
  };

  const fetchLatestAssessment = async () => {
    try {
      const response = await api.get('/assessment/history');
      const data: any[] = response.data || [];
      setHistory(data);
      const latestSelf = data.find((x) => x.subject_type !== 'other');
      setAssessmentResult(latestSelf || data[0] || null);
    } catch (error) {
      console.error('Error fetching assessment:', error);
    }
  };

  const handleAnswerChange = (questionId: string, value: number) => {
    setAnswers({ ...answers, [questionId]: value });
  };

  const handleSubmitAssessment = async () => {
    const unanswered = questions.filter((q) => !answers[q.id]);
    if (unanswered.length > 0) {
      showAlert('Incomplete', 'Please answer all questions');
      return;
    }

    setSubmitting(true);
    try {
      const payload: any = { answers };
      if (subjectType === 'other') {
        if (!subjectName.trim()) { showAlert('Name needed', 'Enter the name of the person you are assessing.'); setSubmitting(false); return; }
        payload.subject_type = 'other';
        payload.subject_name = subjectName.trim();
        payload.subject_whatsapp = subjectWhatsapp.trim();
      }
      const response = await api.post('/assessment', payload);
      setShowQuiz(false);
      setAnswers({});
      await fetchLatestAssessment();
      if (subjectType === 'self') setAssessmentResult(response.data);
      setSubjectType('self'); setSubjectName(''); setSubjectWhatsapp('');
      setTimeout(() => scrollRef.current?.scrollTo({ y: 0, animated: true }), 120);
      const who = response.data?.subject_name ? ` for ${response.data.subject_name}` : '';
      showAlert('Assessment Complete', `Dominant mode${who}: ${response.data.dominant_mode}`);
    } catch (error) {
      showAlert('Error', 'Failed to submit assessment');
    } finally {
      setSubmitting(false);
    }
  };

  // ── Decision-Style: AI insight + share/whatsapp/PDF (reuses jelcos.ai hook) ──
  const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

  const generateInsight = async (a: any) => {
    setInsightBusy(a.id);
    try {
      const r = await api.post(`/assessment/${a.id}/ai-insight`);
      const insight = r.data.ai_insight;
      setHistory((h) => h.map((x) => (x.id === a.id ? { ...x, ai_insight: insight } : x)));
      setAssessmentResult((prev: any) => (prev && prev.id === a.id ? { ...prev, ai_insight: insight } : prev));
      refreshAiWallet();
      if (r.data.credits_charged) showAlert('AI insight ready', `${r.data.credits_charged} credits used.`);
    } catch (e: any) {
      showAlert('AI insight', e?.response?.data?.detail || 'Could not generate insight.');
    } finally { setInsightBusy(null); }
  };

  // Centralized share (WhatsApp via UltraMsg / Email via Resend + server PDF)
  const openShare = (a: any) => setShareTarget(a);

  const downloadPdf = async (a: any) => {
    setPdfBusy(a.id);
    try {
      await downloadReportPdf(`/api/assessment/${a.id}/report.pdf`, `jelcos_decision_style_${String(a.id).slice(0, 8)}.pdf`);
    } catch (e: any) {
      showAlert('PDF', e?.message || 'Could not generate the PDF.');
    } finally { setPdfBusy(null); }
  };

  const startQuiz = (type: 'self' | 'other') => {
    setSubjectType(type); setSubjectName(''); setSubjectWhatsapp(''); setAnswers({}); setShowQuiz(true);
  };

  const handleLogout = () => {
    showAlert(
      'Logout',
      'Are you sure you want to logout?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Logout',
          style: 'destructive',
          onPress: async () => {
            await logout();
            router.replace('/auth/login');
          },
        },
      ]
    );
  };

  const handleSetPassword = async () => {
    setPasswordError('');
    
    if (!newPassword) {
      setPasswordError('Please enter a password');
      return;
    }
    if (newPassword.length < 6) {
      setPasswordError('Password must be at least 6 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match');
      return;
    }

    setPasswordLoading(true);
    try {
      await api.post('/auth/set-password', { new_password: newPassword });
      setHasPassword(true);
      setShowSetPassword(false);
      setNewPassword('');
      setConfirmPassword('');
      showAlert('Success', 'Password set successfully! You can now also login with email and password.');
    } catch (err: any) {
      setPasswordError(err.response?.data?.detail || 'Failed to set password');
    } finally {
      setPasswordLoading(false);
    }
  };

  const getModeColor = (mode: string) => {
    switch (mode) {
      case 'emotional': return COLORS.emotional;
      case 'logical': return COLORS.logical;
      case 'intuitive': return COLORS.intuitive;
      case 'consciousness': return COLORS.consciousness;
      default: return COLORS.primary;
    }
  };

  const getModeDescription = (mode: string) => {
    switch (mode) {
      case 'emotional':
        return 'You tend to make decisions based on how you feel. While comfortable, consider adding more logical analysis for better long-term outcomes.';
      case 'logical':
        return 'You prefer rational analysis. Your decisions are well-thought-out but might benefit from incorporating emotional intelligence.';
      case 'intuitive':
        return 'You trust your instincts and inner knowing. Your decisions often come from deep insights that are hard to explain logically.';
      case 'consciousness':
        return 'You can observe situations with clarity and detachment. This is the highest form of decision-making with near-perfect accuracy.';
      default:
        return '';
    }
  };

  const renderQuiz = () => (
    <View style={styles.quizContainer}>
      <View style={styles.quizHeader}>
        <Text style={styles.quizTitle}>Decision Style Assessment</Text>
        <TouchableOpacity onPress={() => setShowQuiz(false)}>
          <Ionicons name="close" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
      </View>

      <View style={styles.subjectToggle}>
        <TouchableOpacity
          style={[styles.subjectBtn, subjectType === 'self' && styles.subjectBtnActive]}
          onPress={() => setSubjectType('self')}
        >
          <Ionicons name="person" size={15} color={subjectType === 'self' ? COLORS.white : COLORS.textSecondary} />
          <Text style={[styles.subjectBtnText, subjectType === 'self' && styles.subjectBtnTextActive]}>For myself</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.subjectBtn, subjectType === 'other' && styles.subjectBtnActive]}
          onPress={() => setSubjectType('other')}
        >
          <Ionicons name="people" size={15} color={subjectType === 'other' ? COLORS.white : COLORS.textSecondary} />
          <Text style={[styles.subjectBtnText, subjectType === 'other' && styles.subjectBtnTextActive]}>For someone else</Text>
        </TouchableOpacity>
      </View>

      {subjectType === 'other' && (
        <View style={styles.subjectInputs}>
          <TextInput
            style={styles.subjectInput}
            placeholder="Person's name *"
            placeholderTextColor={COLORS.textMuted}
            value={subjectName}
            onChangeText={setSubjectName}
          />
          <TextInput
            style={styles.subjectInput}
            placeholder="WhatsApp number (optional, e.g. +9198…)"
            placeholderTextColor={COLORS.textMuted}
            value={subjectWhatsapp}
            onChangeText={setSubjectWhatsapp}
            keyboardType="phone-pad"
          />
        </View>
      )}

      <Text style={styles.quizInstructions}>
        Rate each statement from 1 (Strongly Disagree) to 5 (Strongly Agree)
      </Text>

      {questions.map((question, index) => (
        <Card key={question.id} style={styles.questionCard}>
          <Text style={styles.questionNumber}>Question {index + 1}</Text>
          <Text style={styles.questionText}>{question.text}</Text>
          <View style={styles.ratingContainer}>
            {[1, 2, 3, 4, 5].map((value) => (
              <TouchableOpacity
                key={value}
                style={[
                  styles.ratingButton,
                  answers[question.id] === value && styles.ratingButtonActive,
                ]}
                onPress={() => handleAnswerChange(question.id, value)}
              >
                <Text
                  style={[
                    styles.ratingText,
                    answers[question.id] === value && styles.ratingTextActive,
                  ]}
                >
                  {value}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <View style={styles.ratingLabels}>
            <Text style={styles.ratingLabel}>Disagree</Text>
            <Text style={styles.ratingLabel}>Agree</Text>
          </View>
        </Card>
      ))}

      <GradientButton
        title="Submit Assessment"
        onPress={handleSubmitAssessment}
        loading={submitting}
        style={styles.submitButton}
      />
    </View>
  );

  const saveProfilePicture = async (dataUrl: string | '') => {
    setPicBusy(true);
    try {
      await api.patch('/auth/profile', { profile_picture: dataUrl });
      await checkAuth();
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Could not update picture.');
    } finally { setPicBusy(false); }
  };

  const pickProfilePicture = async () => {
    if (Platform.OS !== 'web') {
      const cur = await ImagePicker.getMediaLibraryPermissionsAsync();
      let status = cur.status;
      if (status !== 'granted' && cur.canAskAgain) {
        status = (await ImagePicker.requestMediaLibraryPermissionsAsync()).status;
      }
      if (status !== 'granted') {
        showAlert('Permission needed', 'Allow photo access to set a profile picture.', [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Open Settings', onPress: () => Linking.openSettings() },
        ]);
        return;
      }
    }
    try {
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'], allowsEditing: true, aspect: [1, 1], quality: 0.8, base64: true,
      });
      if (res.canceled || !res.assets?.length) return;
      const a = res.assets[0];
      if (!a.base64) { showAlert('Unsupported', 'Could not read the image.'); return; }
      const mime = (a.mimeType || '').toLowerCase();
      const normMime = mime.includes('jpeg') || mime.includes('jpg') ? 'image/jpeg'
        : mime.includes('png') ? 'image/png' : '';
      if (!normMime) { showAlert('Unsupported format', 'Please choose a PNG or JPG image.'); return; }
      if (a.base64.length > 1.4 * 1024 * 1024) { showAlert('Too large', 'Picture must be 1 MB or smaller.'); return; }
      await saveProfilePicture(`data:${normMime};base64,${a.base64}`);
    } catch (e: any) {
      showAlert('Picker error', e?.message || 'Could not open the image picker.');
    }
  };

  const onAvatarPress = () => {
    const opts: any[] = [
      { text: user?.has_custom_picture ? 'Replace photo' : 'Upload photo', onPress: pickProfilePicture },
    ];
    if (user?.has_custom_picture) {
      opts.push({ text: 'Remove photo', style: 'destructive', onPress: () => saveProfilePicture('') });
    }
    opts.push({ text: 'Cancel', style: 'cancel' });
    showAlert('Profile picture', 'Choose an option', opts);
  };

  const saveGender = async (g: string) => {
    setSavingGender(true);
    try {
      await api.patch('/auth/profile', { gender: g });
      await checkAuth();
      setGenderModalOpen(false);
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Could not update gender.');
    } finally { setSavingGender(false); }
  };

  const renderProfile = () => (
    <>
      {/* User Info */}
      <Card style={styles.userCard}>
        <View style={styles.userInfo}>
          <TouchableOpacity onPress={onAvatarPress} activeOpacity={0.8} disabled={picBusy}>
            {user?.picture ? (
              <Image source={{ uri: user.picture }} style={styles.avatar} />
            ) : (
              <View style={styles.avatarPlaceholder}>
                <Ionicons name="person" size={32} color={COLORS.white} />
              </View>
            )}
            <View style={styles.avatarEdit}>
              {picBusy ? <ActivityIndicator size="small" color={COLORS.white} /> : <Ionicons name="camera" size={14} color={COLORS.white} />}
            </View>
          </TouchableOpacity>
          <View style={styles.userDetails}>
            <Text style={styles.userName}>{user?.name}</Text>
            <Text style={styles.userEmail}>{user?.email}</Text>
            <View style={styles.authBadge}>
              <Ionicons
                name={user?.auth_method === 'google' ? 'logo-google' : 'mail'}
                size={12}
                color={COLORS.textSecondary}
              />
              <Text style={styles.authText}>
                {user?.auth_method === 'google' ? 'Google Account' : 'Email Account'}
              </Text>
            </View>
          </View>
        </View>

        {/* WhatsApp */}
        <View style={styles.fieldRow}>
          <View style={styles.fieldLeft}>
            <Ionicons name="logo-whatsapp" size={18} color="#25D366" />
            <View style={{ flexShrink: 1 }}>
              <Text style={styles.fieldLabel}>WhatsApp</Text>
              {user?.whatsapp_number ? (
                <View style={styles.waValueRow}>
                  <Text style={styles.fieldValue}>{user.whatsapp_number}</Text>
                  {user?.whatsapp_verified ? (
                    <View style={styles.verifiedPill}><Ionicons name="checkmark-circle" size={12} color="#059669" /><Text style={styles.verifiedText}>Verified</Text></View>
                  ) : (
                    <View style={styles.unverifiedPill}><Text style={styles.unverifiedText}>Unverified</Text></View>
                  )}
                </View>
              ) : (
                <Text style={styles.fieldMuted}>Not added</Text>
              )}
            </View>
          </View>
          <TouchableOpacity onPress={() => router.push('/whatsapp-verify?change=1' as any)} style={styles.fieldAction}>
            <Text style={styles.fieldActionText}>{user?.whatsapp_number ? 'Change' : 'Add'}</Text>
          </TouchableOpacity>
        </View>

        {/* Gender */}
        <View style={[styles.fieldRow, { borderBottomWidth: 0 }]}>
          <View style={styles.fieldLeft}>
            <Ionicons name="male-female" size={18} color={COLORS.primary} />
            <View style={{ flexShrink: 1 }}>
              <Text style={styles.fieldLabel}>Gender <Text style={styles.optional}>(optional)</Text></Text>
              <Text style={user?.gender ? styles.fieldValue : styles.fieldMuted}>{user?.gender || 'Not set'}</Text>
            </View>
          </View>
          <TouchableOpacity onPress={() => setGenderModalOpen(true)} style={styles.fieldAction}>
            <Text style={styles.fieldActionText}>Edit</Text>
          </TouchableOpacity>
        </View>
      </Card>

      {/* AI Credits wallet */}
      <TouchableOpacity activeOpacity={0.85} onPress={() => router.push('/ai-wallet' as any)}>
        <Card style={styles.aiCreditsCard}>
          <View style={styles.aiCreditsLeft}>
            <View style={styles.aiCreditsIcon}>
              <Ionicons name="sparkles" size={20} color={COLORS.white} />
            </View>
            <View style={{ flexShrink: 1 }}>
              <Text style={styles.aiCreditsLabel}>AI Credits</Text>
              <Text style={styles.aiCreditsSub}>Powers AI Assist in your decisions</Text>
            </View>
          </View>
          <View style={styles.aiCreditsRight}>
            <Text style={[styles.aiCreditsValue, aiBalance <= 0 && { color: COLORS.error }]}>
              {aiBalance.toFixed(aiBalance < 10 ? 1 : 0)}
            </Text>
            <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
          </View>
        </Card>
      </TouchableOpacity>

      {/* Subscription */}
      <TouchableOpacity activeOpacity={0.85} onPress={() => router.push('/subscription-plans' as any)}>
        <Card style={styles.aiCreditsCard}>
          <View style={styles.aiCreditsLeft}>
            <View style={[styles.aiCreditsIcon, { backgroundColor: COLORS.secondary || '#5E35B1' }]}>
              <Ionicons name="ribbon" size={20} color={COLORS.white} />
            </View>
            <View style={{ flexShrink: 1 }}>
              <Text style={styles.aiCreditsLabel}>Subscription</Text>
              <Text style={styles.aiCreditsSub}>Monthly plans &amp; auto-renew</Text>
            </View>
          </View>
          <View style={styles.aiCreditsRight}>
            <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
          </View>
        </Card>
      </TouchableOpacity>

      {/* Gender picker modal */}
      <Modal visible={genderModalOpen} transparent animationType="fade" onRequestClose={() => setGenderModalOpen(false)}>
        <TouchableOpacity style={styles.gOverlay} activeOpacity={1} onPress={() => setGenderModalOpen(false)}>
          <View style={styles.gCard}>
            <Text style={styles.gTitle}>Select gender</Text>
            {GENDER_OPTIONS.map((g) => (
              <TouchableOpacity key={g} style={styles.gOption} onPress={() => saveGender(g)} disabled={savingGender}>
                <Text style={[styles.gOptionText, user?.gender === g && { color: COLORS.primary, fontWeight: '700' }]}>{g}</Text>
                {user?.gender === g && <Ionicons name="checkmark" size={18} color={COLORS.primary} />}
              </TouchableOpacity>
            ))}
            {!!user?.gender && (
              <TouchableOpacity style={styles.gOption} onPress={() => saveGender('')} disabled={savingGender}>
                <Text style={[styles.gOptionText, { color: '#DC2626' }]}>Clear</Text>
              </TouchableOpacity>
            )}
          </View>
        </TouchableOpacity>
      </Modal>

      {/* Assessment Result */}
      <Text style={styles.sectionTitle}>Your Predominant Decision Mode</Text>
      {assessmentResult ? (
        <Card style={styles.resultCard}>
          <View style={styles.resultHeader}>
            <View
              style={[
                styles.modeIcon,
                { backgroundColor: getModeColor(assessmentResult.dominant_mode) },
              ]}
            >
              <Ionicons name="compass" size={28} color={COLORS.white} />
            </View>
            <View style={styles.modeInfo}>
              <Text style={styles.dominantMode}>
                {assessmentResult.dominant_mode.charAt(0).toUpperCase() +
                  assessmentResult.dominant_mode.slice(1)}
              </Text>
              <Text style={styles.modeLabel}>Dominant Mode</Text>
            </View>
          </View>
          <Text style={styles.modeDescription}>
            {getModeDescription(assessmentResult.dominant_mode)}
          </Text>

          <View style={styles.scoresContainer}>
            <Text style={styles.scoresTitle}>Mode Breakdown</Text>
            {Object.entries(assessmentResult.mode_scores).map(([mode, score]) => (
              <View key={mode} style={styles.scoreRow}>
                <View style={styles.scoreLabelRow}>
                  <View
                    style={[
                      styles.scoreDot,
                      { backgroundColor: getModeColor(mode) },
                    ]}
                  />
                  <Text style={styles.scoreLabel}>
                    {mode.charAt(0).toUpperCase() + mode.slice(1)}
                  </Text>
                </View>
                <View style={styles.scoreBarContainer}>
                  <View
                    style={[
                      styles.scoreBar,
                      {
                        width: `${(score as number) * 20}%`,
                        backgroundColor: getModeColor(mode),
                      },
                    ]}
                  />
                </View>
                <Text style={styles.scoreValue} numberOfLines={1}>{((score as number) * 20).toFixed(1)}%</Text>
              </View>
            ))}
          </View>

          {assessmentResult.ai_insight ? (
            <View style={styles.insightBox}>
              <View style={styles.insightHeader}>
                <Ionicons name="sparkles" size={15} color="#7C3AED" />
                <Text style={styles.insightTitle}>AI Insight</Text>
              </View>
              <Text style={styles.insightText}>{assessmentResult.ai_insight}</Text>
            </View>
          ) : (
            <TouchableOpacity
              style={styles.insightBtn}
              onPress={() => generateInsight(assessmentResult)}
              disabled={insightBusy === assessmentResult.id}
            >
              {insightBusy === assessmentResult.id
                ? <ActivityIndicator color="#7C3AED" size="small" />
                : <><Ionicons name="sparkles" size={16} color="#7C3AED" /><Text style={styles.insightBtnText}>Get personalized AI insight (8 credits)</Text></>}
            </TouchableOpacity>
          )}

          <View style={styles.shareRow}>
            <TouchableOpacity style={styles.shareBtn} onPress={() => openShare(assessmentResult)}>
              <Ionicons name="share-social" size={18} color={COLORS.primary} />
              <Text style={styles.shareBtnText}>Share (WhatsApp / Email)</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.shareBtn} onPress={() => downloadPdf(assessmentResult)} disabled={pdfBusy === assessmentResult.id}>
              {pdfBusy === assessmentResult.id ? <ActivityIndicator size="small" color="#DC2626" /> : <Ionicons name="document-text" size={18} color="#DC2626" />}
              <Text style={styles.shareBtnText}>PDF</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.retakeRow}>
            <TouchableOpacity style={styles.retakeButton} onPress={() => startQuiz('self')}>
              <Ionicons name="refresh" size={16} color={COLORS.primary} />
              <Text style={styles.retakeText}>Retake (me)</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.retakeButton} onPress={() => startQuiz('other')}>
              <Ionicons name="person-add" size={16} color={COLORS.primary} />
              <Text style={styles.retakeText}>Assess someone</Text>
            </TouchableOpacity>
          </View>
        </Card>
      ) : (
        <Card style={styles.noAssessmentCard}>
          <Ionicons name="compass-outline" size={48} color={COLORS.textMuted} />
          <Text style={styles.noAssessmentTitle}>No Assessment Yet</Text>
          <Text style={styles.noAssessmentText}>
            Discover your decision-making style by taking the assessment
          </Text>
          <GradientButton
            title="Take Assessment"
            onPress={() => startQuiz('self')}
            style={styles.takeAssessmentButton}
          />
        </Card>
      )}

      {/* Track record — Self pinned on top, others chronological */}
      {history.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Assessment Track Record</Text>
          <Card style={{ marginBottom: 16 }}>
            {[...history]
              .sort((a, b) => (a.subject_type === 'other' ? 1 : 0) - (b.subject_type === 'other' ? 1 : 0))
              .map((a, idx) => (
                <View key={a.id} style={[styles.trackRow, idx > 0 && styles.trackRowBorder]}>
                  <View style={[styles.trackDot, { backgroundColor: getModeColor(a.dominant_mode) }]} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.trackName} numberOfLines={1}>
                      {a.subject_type === 'other' ? (a.subject_name || 'Someone') : 'You'}
                      {a.subject_type === 'self' && <Text style={styles.trackSelfTag}>  • Self</Text>}
                    </Text>
                    <Text style={styles.trackMeta} numberOfLines={1}>
                      {a.dominant_mode ? a.dominant_mode.charAt(0).toUpperCase() + a.dominant_mode.slice(1) : ''}
                      {a.created_at ? `  ·  ${new Date(a.created_at).toLocaleDateString()}` : ''}
                      {a.ai_insight ? '  ·  ✨ insight' : ''}
                    </Text>
                  </View>
                  <TouchableOpacity style={styles.trackAction} onPress={() => setAssessmentResult(a)}>
                    <Ionicons name="eye-outline" size={18} color={COLORS.primary} />
                  </TouchableOpacity>
                  {a.subject_type === 'other' && !!a.subject_whatsapp && (
                    <TouchableOpacity style={styles.trackAction} onPress={() => openShare(a)}>
                      <Ionicons name="logo-whatsapp" size={18} color="#25D366" />
                    </TouchableOpacity>
                  )}
                </View>
              ))}
          </Card>
        </>
      )}

      {/* Account Security — Set / Change Password (available to all users) */}
      {!!user && (
        <>
          <Text style={styles.sectionTitle}>Account Security</Text>
          <Card style={styles.passwordCard}>
            {hasPassword ? (
              <View style={styles.passwordSetRow}>
                <View style={styles.passwordSetIcon}>
                  <Ionicons name="shield-checkmark" size={24} color={COLORS.success} />
                </View>
                <View style={styles.passwordSetInfo}>
                  <Text style={styles.passwordSetTitle}>Password Set</Text>
                  <Text style={styles.passwordSetSubtitle}>
                    You can login with both Google and email/password
                  </Text>
                </View>
                <TouchableOpacity
                  onPress={() => {
                    setShowSetPassword(!showSetPassword);
                    setPasswordError('');
                    setNewPassword('');
                    setConfirmPassword('');
                  }}
                >
                  <Text style={styles.changePasswordLink}>Change</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <>
                <View style={styles.passwordSetRow}>
                  <View style={[styles.passwordSetIcon, { backgroundColor: 'rgba(245, 158, 11, 0.1)' }]}>
                    <Ionicons name="key-outline" size={24} color={COLORS.warning} />
                  </View>
                  <View style={styles.passwordSetInfo}>
                    <Text style={styles.passwordSetTitle}>Set a Password</Text>
                    <Text style={styles.passwordSetSubtitle}>
                      Enable email login alongside Google Sign-In
                    </Text>
                  </View>
                </View>
                {!showSetPassword && (
                  <TouchableOpacity
                    style={styles.setPasswordButton}
                    onPress={() => setShowSetPassword(true)}
                  >
                    <Ionicons name="lock-closed-outline" size={16} color={COLORS.primary} />
                    <Text style={styles.setPasswordButtonText}>Set Password</Text>
                  </TouchableOpacity>
                )}
              </>
            )}

            {showSetPassword && (
              <View style={styles.setPasswordForm}>
                {passwordError ? (
                  <View style={styles.passwordErrorContainer}>
                    <Ionicons name="alert-circle" size={16} color={COLORS.error} />
                    <Text style={styles.passwordErrorText}>{passwordError}</Text>
                  </View>
                ) : null}

                <Input
                  label="New Password"
                  placeholder="Min 6 characters"
                  value={newPassword}
                  onChangeText={setNewPassword}
                  secureTextEntry
                />
                <Input
                  label="Confirm Password"
                  placeholder="Re-enter password"
                  value={confirmPassword}
                  onChangeText={setConfirmPassword}
                  secureTextEntry
                />
                <View style={styles.setPasswordActions}>
                  <TouchableOpacity
                    style={styles.cancelButton}
                    onPress={() => {
                      setShowSetPassword(false);
                      setPasswordError('');
                      setNewPassword('');
                      setConfirmPassword('');
                    }}
                  >
                    <Text style={styles.cancelButtonText}>Cancel</Text>
                  </TouchableOpacity>
                  <GradientButton
                    title={hasPassword ? 'Update Password' : 'Set Password'}
                    onPress={handleSetPassword}
                    loading={passwordLoading}
                    style={styles.savePasswordButton}
                  />
                </View>
              </View>
            )}
          </Card>
        </>
      )}

      {/* Recently Deleted (Trash) — available to all users */}
      {!!user && (
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
          onPress={() => router.push('/trash' as any)}
        >
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#64748B', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="trash-bin" size={18} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.text }}>Recently Deleted</Text>
            <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Restore deleted items within 7 days</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
        </TouchableOpacity>
      )}

      {/* Admin Console removed from User App — admin access is via the
          dedicated /admin route only. Super-admins still navigate there
          directly; we don't surface it as a profile section. */}

      {/* Knowledge Marketplace */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/marketplace' as any)}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#9333EA', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="storefront" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Knowledge Marketplace</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Publish & clone decisions · free or paid</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* My Earnings */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/earnings' as any)}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#16A34A', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="cash" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>My Earnings & Payouts</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Marketplace income · weekly payouts</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Karma & Leaderboard */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/leaderboard' as any)}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#F59E0B', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="trophy" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Karma & Fame</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Your karma points & public leaderboard</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>


      {/* Goals Execution Manager */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/tools/gem')}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#0F766E', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="flag" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Goals (GEM)</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Goals across 10 Life Areas</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* TEPFI Resource Matrix */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/tools/tepfi')}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#7C3AED', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="cube" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Capabilities & Resources Index</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Resource tracking across Self/Micro/Macro</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Calendar View */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/tools/calendar-view')}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#4285F4', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="calendar" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Calendar & Scheduling</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Deadlines & Google Calendar sync</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Lifestyle Dezider */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/tools/lifestyle')}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#065F46', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="leaf" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Lifestyle Dezider</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Routines & lifestyle effectiveness</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Privacy & Data (DPDP Act 2023) */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/tools/privacy-data')}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#1E40AF', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="shield-checkmark" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Privacy & Data</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Export, delete your data (DPDP Act)</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Logout */}
      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Ionicons name="log-out-outline" size={20} color={COLORS.error} />
        <Text style={styles.logoutText}>Logout</Text>
      </TouchableOpacity>

      {/* App Info */}
      <View style={styles.appInfo}>
        <Image
          source={{ uri: 'https://customer-assets.emergentagent.com/job_chapter2-guide/artifacts/acyqe96y_VENTURE%20BUDDHA-SqaureHD.png' }}
          style={styles.appLogo}
        />
        <Text style={styles.appName}>View Dezider</Text>
        <Text style={styles.appTagline}>Decision Intelligence by Venture Buddha</Text>
      </View>
    </>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView ref={scrollRef} style={{ flex: 1 }} showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 100 }}>
        <View style={styles.header}>
          <Text style={styles.title}>Profile</Text>
        </View>

        <View style={styles.content}>
          {showQuiz ? renderQuiz() : renderProfile()}
      <ReportShareSheet
        visible={!!shareTarget}
        onClose={() => setShareTarget(null)}
        module="assessment"
        decisionId={shareTarget?.id || ''}
        title={shareTarget ? `${shareTarget.subject_type === 'other' && shareTarget.subject_name ? shareTarget.subject_name + "'s" : 'My'} Decision-Making Style` : ''}
        defaultPhone={shareTarget?.subject_whatsapp || ''}
      />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  header: {
    padding: 16,
    paddingTop: 8,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  content: {
    padding: 16,
    paddingTop: 0,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 12,
    marginTop: 8,
  },
  userCard: {
    marginBottom: 16,
  },
  aiCreditsCard: {
    marginBottom: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  aiCreditsLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flexShrink: 1 },
  aiCreditsIcon: {
    width: 40, height: 40, borderRadius: 20, backgroundColor: COLORS.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  aiCreditsLabel: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  aiCreditsSub: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  aiCreditsRight: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  aiCreditsValue: { fontSize: 20, fontWeight: '800', color: COLORS.primary },
  userInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
  },
  avatarPlaceholder: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  userDetails: {
    marginLeft: 16,
    flex: 1,
  },
  userName: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  userEmail: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  authBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    gap: 4,
  },
  authText: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  avatarEdit: {
    position: 'absolute', right: -2, bottom: -2,
    width: 24, height: 24, borderRadius: 12,
    backgroundColor: COLORS.primary,
    alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: COLORS.white,
  },
  fieldRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingTop: 14, marginTop: 14, borderTopWidth: 1, borderTopColor: COLORS.border,
  },
  fieldLeft: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1, paddingRight: 10 },
  fieldLabel: { fontSize: 13, color: COLORS.textSecondary, fontWeight: '600' },
  optional: { fontSize: 11, color: COLORS.textMuted, fontWeight: '400' },
  fieldValue: { fontSize: 14, color: COLORS.textPrimary, fontWeight: '600', marginTop: 1 },
  fieldMuted: { fontSize: 14, color: COLORS.textMuted, marginTop: 1 },
  waValueRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  verifiedPill: { flexDirection: 'row', alignItems: 'center', gap: 2, backgroundColor: '#ECFDF5', borderRadius: 999, paddingHorizontal: 6, paddingVertical: 2 },
  verifiedText: { fontSize: 10, color: '#059669', fontWeight: '700' },
  unverifiedPill: { backgroundColor: '#FEF2F2', borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  unverifiedText: { fontSize: 10, color: '#DC2626', fontWeight: '700' },
  fieldAction: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, backgroundColor: COLORS.primary + '12' },
  fieldActionText: { fontSize: 13, color: COLORS.primary, fontWeight: '700' },
  gOverlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.5)', justifyContent: 'center', padding: 30 },
  gCard: { backgroundColor: COLORS.white, borderRadius: 16, padding: 8 },
  gTitle: { fontSize: 15, fontWeight: '800', color: COLORS.textPrimary, padding: 12 },
  gOption: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 14, paddingHorizontal: 12, borderTopWidth: 1, borderTopColor: COLORS.divider },
  gOptionText: { fontSize: 15, color: COLORS.textPrimary },
  resultCard: {
    marginBottom: 16,
  },
  subjectToggle: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  subjectBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, borderWidth: 1.5, borderColor: COLORS.border, backgroundColor: COLORS.white },
  subjectBtnActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  subjectBtnText: { fontSize: 13, fontWeight: '700', color: COLORS.textSecondary },
  subjectBtnTextActive: { color: COLORS.white },
  subjectInputs: { gap: 8, marginBottom: 12 },
  subjectInput: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  insightBox: { backgroundColor: '#F5F3FF', borderRadius: 12, padding: 12, marginTop: 14, borderLeftWidth: 3, borderLeftColor: '#7C3AED' },
  insightHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  insightTitle: { fontSize: 13, fontWeight: '800', color: '#7C3AED' },
  insightText: { fontSize: 13.5, color: '#3730A3', lineHeight: 20 },
  insightBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 14, paddingVertical: 11, borderRadius: 10, borderWidth: 1.5, borderColor: '#7C3AED', backgroundColor: '#F5F3FF' },
  insightBtnText: { fontSize: 13, fontWeight: '800', color: '#7C3AED' },
  shareRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  shareBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  shareBtnText: { fontSize: 12.5, fontWeight: '700', color: COLORS.textPrimary },
  retakeRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  trackRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12 },
  trackRowBorder: { borderTopWidth: 1, borderTopColor: COLORS.divider },
  trackDot: { width: 10, height: 10, borderRadius: 5 },
  trackName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  trackSelfTag: { fontSize: 11, fontWeight: '700', color: COLORS.primary },
  trackMeta: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  trackAction: { padding: 6 },
  resultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  modeIcon: {
    width: 56,
    height: 56,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  modeInfo: {
    marginLeft: 16,
  },
  dominantMode: {
    fontSize: 22,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  modeLabel: {
    fontSize: 14,
    color: COLORS.textSecondary,
  },
  modeDescription: {
    fontSize: 14,
    color: COLORS.textSecondary,
    lineHeight: 20,
    marginBottom: 20,
  },
  scoresContainer: {
    backgroundColor: COLORS.background,
    borderRadius: 12,
    padding: 12,
  },
  scoresTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 12,
  },
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  scoreLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    width: 90,
  },
  scoreDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  scoreLabel: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  scoreBarContainer: {
    flex: 1,
    height: 8,
    backgroundColor: COLORS.divider,
    borderRadius: 4,
    marginHorizontal: 8,
  },
  scoreBar: {
    height: '100%',
    borderRadius: 4,
  },
  scoreValue: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textPrimary,
    minWidth: 54,
    textAlign: 'right',
  },
  retakeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 16,
    gap: 6,
  },
  retakeText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
  noAssessmentCard: {
    alignItems: 'center',
    padding: 32,
    marginBottom: 16,
  },
  noAssessmentTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginTop: 12,
  },
  noAssessmentText: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    marginTop: 8,
    marginBottom: 20,
  },
  takeAssessmentButton: {
    width: '100%',
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.white,
    borderRadius: 12,
    padding: 16,
    gap: 8,
    marginBottom: 24,
  },
  logoutText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.error,
  },
  // Set Password styles
  passwordCard: {
    marginBottom: 16,
  },
  passwordSetRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  passwordSetIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  passwordSetInfo: {
    flex: 1,
    marginLeft: 12,
  },
  passwordSetTitle: {
    fontSize: 15,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  passwordSetSubtitle: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  changePasswordLink: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
  setPasswordButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
    paddingVertical: 10,
    backgroundColor: 'rgba(142, 36, 170, 0.08)',
    borderRadius: 8,
    gap: 6,
  },
  setPasswordButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
  setPasswordForm: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: COLORS.divider,
  },
  passwordErrorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    padding: 10,
    borderRadius: 8,
    marginBottom: 12,
    gap: 6,
  },
  passwordErrorText: {
    color: COLORS.error,
    fontSize: 13,
    flex: 1,
  },
  setPasswordActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginTop: 4,
  },
  cancelButton: {
    paddingVertical: 12,
    paddingHorizontal: 20,
  },
  cancelButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  savePasswordButton: {
    flex: 1,
  },
  // Admin Panel styles
  roleBadge: {
    marginTop: 4,
  },
  roleBadgeSuperAdmin: {
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
  },
  roleBadgeCoAdmin: {
    backgroundColor: 'rgba(139, 92, 246, 0.1)',
  },
  roleBadgeAdmin: {
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
  },
  adminSetupRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  adminPanelContent: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: COLORS.divider,
  },
  promoteSection: {
    marginBottom: 16,
  },
  promoteSectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  promoteInput: {
    backgroundColor: COLORS.background,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.border,
    marginBottom: 8,
  },
  promoteRoleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  roleChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: COLORS.border,
  },
  roleChipActive: {
    borderColor: COLORS.primary,
    backgroundColor: 'rgba(142, 36, 170, 0.08)',
  },
  roleChipText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.textMuted,
  },
  roleChipTextActive: {
    color: COLORS.primary,
  },
  promoteBtn: {
    flex: 1,
    backgroundColor: COLORS.primary,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
  },
  promoteBtnText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#FFF',
  },
  adminListTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  adminUserRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.divider,
  },
  adminUserInfo: {
    flex: 1,
  },
  adminUserName: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  adminUserEmail: {
    fontSize: 12,
    color: COLORS.textMuted,
  },
  adminRoleBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    marginRight: 8,
  },
  adminRoleBadgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  demoteBtn: {
    padding: 6,
  },
  noAdminsText: {
    fontSize: 13,
    color: COLORS.textMuted,
    fontStyle: 'italic',
    textAlign: 'center',
    paddingVertical: 12,
  },
  wowoSection: {
    marginTop: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.divider,
  },
  appInfo: {
    alignItems: 'center',
    paddingBottom: 32,
  },
  appLogo: {
    width: 48,
    height: 48,
    borderRadius: 12,
    marginBottom: 8,
  },
  appName: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  appTagline: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginTop: 2,
  },
  quizContainer: {
    paddingBottom: 32,
  },
  quizHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  quizTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  quizInstructions: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginBottom: 20,
  },
  questionCard: {
    marginBottom: 12,
  },
  questionNumber: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.primary,
    marginBottom: 4,
  },
  questionText: {
    fontSize: 15,
    color: COLORS.textPrimary,
    lineHeight: 22,
    marginBottom: 12,
  },
  ratingContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  ratingButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: COLORS.border,
  },
  ratingButtonActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  ratingText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  ratingTextActive: {
    color: COLORS.white,
  },
  ratingLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
  },
  ratingLabel: {
    fontSize: 11,
    color: COLORS.textMuted,
  },
  submitButton: {
    marginTop: 24,
  },
});
