import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  Image,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import { GradientButton } from '../../src/components/GradientButton';
import api from '../../src/utils/api';

interface AssessmentQuestion {
  id: string;
  text: string;
  mode: string;
}

export default function ProfileScreen() {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const [questions, setQuestions] = useState<AssessmentQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [assessmentResult, setAssessmentResult] = useState<any>(null);
  const [showQuiz, setShowQuiz] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchQuestions();
    fetchLatestAssessment();
  }, []);

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
      if (response.data.length > 0) {
        setAssessmentResult(response.data[0]);
      }
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
      Alert.alert('Incomplete', 'Please answer all questions');
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post('/assessment', { answers });
      setAssessmentResult(response.data);
      setShowQuiz(false);
      setAnswers({});
      Alert.alert('Assessment Complete', `Your dominant mode is: ${response.data.dominant_mode}`);
    } catch (error) {
      Alert.alert('Error', 'Failed to submit assessment');
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = () => {
    Alert.alert(
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

  const getModeColor = (mode: string) => {
    switch (mode) {
      case 'emotional': return COLORS.emotional;
      case 'logical': return COLORS.logical;
      case 'intuitive': return COLORS.intuitive;
      case 'awareness': return COLORS.awareness;
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
      case 'awareness':
        return 'You can observe situations with clarity and detachment. This is the highest form of decision-making with near-perfect accuracy.';
      default:
        return '';
    }
  };

  const renderQuiz = () => (
    <View style={styles.quizContainer}>
      <View style={styles.quizHeader}>
        <Text style={styles.quizTitle}>Decision Mode Assessment</Text>
        <TouchableOpacity onPress={() => setShowQuiz(false)}>
          <Ionicons name="close" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
      </View>
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

  const renderProfile = () => (
    <>
      {/* User Info */}
      <Card style={styles.userCard}>
        <View style={styles.userInfo}>
          {user?.picture ? (
            <Image source={{ uri: user.picture }} style={styles.avatar} />
          ) : (
            <View style={styles.avatarPlaceholder}>
              <Ionicons name="person" size={32} color={COLORS.white} />
            </View>
          )}
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
      </Card>

      {/* Assessment Result */}
      <Text style={styles.sectionTitle}>Your Decision Mode</Text>
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
                <Text style={styles.scoreValue}>{(score as number).toFixed(1)}</Text>
              </View>
            ))}
          </View>

          <TouchableOpacity
            style={styles.retakeButton}
            onPress={() => setShowQuiz(true)}
          >
            <Ionicons name="refresh" size={16} color={COLORS.primary} />
            <Text style={styles.retakeText}>Retake Assessment</Text>
          </TouchableOpacity>
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
            onPress={() => setShowQuiz(true)}
            style={styles.takeAssessmentButton}
          />
        </Card>
      )}

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
      <ScrollView showsVerticalScrollIndicator={false}>
        <View style={styles.header}>
          <Text style={styles.title}>Profile</Text>
        </View>

        <View style={styles.content}>
          {showQuiz ? renderQuiz() : renderProfile()}
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
  resultCard: {
    marginBottom: 16,
  },
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
    width: 24,
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
