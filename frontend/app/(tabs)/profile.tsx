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
  TextInput,
  Switch,
  Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import { GradientButton } from '../../src/components/GradientButton';
import { Input } from '../../src/components/Input';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

interface AssessmentQuestion {
  id: string;
  text: string;
  mode: string;
}

// WOWO Feature Flag Toggle Component
function WowoToggle({ label, flagKey }: { label: string; flagKey: string }) {
  const [enabled, setEnabled] = useState(false);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    fetchFlag();
  }, []);

  const fetchFlag = async () => {
    try {
      const res = await api.get('/feature-flags');
      setEnabled(res.data?.[flagKey] || false);
    } catch (e) {
      console.error('Error fetching flag:', e);
    }
  };

  const toggleFlag = async (val: boolean) => {
    setToggling(true);
    try {
      // We need to send all flags so get current first
      const res = await api.get('/feature-flags');
      const flags = res.data || {};
      flags[flagKey] = val;
      await api.put('/admin/feature-flags', flags);
      setEnabled(val);
    } catch (e) {
      showAlert('Error', 'Failed to update feature flag');
    } finally {
      setToggling(false);
    }
  };

  return (
    <View style={{
      flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
      paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.divider,
    }}>
      <View style={{ flex: 1 }}>
        <Text style={{ fontSize: 14, fontWeight: '500', color: COLORS.textPrimary }}>{label}</Text>
        <Text style={{ fontSize: 11, color: enabled ? COLORS.success : COLORS.textMuted }}>
          {enabled ? 'Wire ON' : 'Wire OFF'}
        </Text>
      </View>
      {toggling ? (
        <ActivityIndicator size="small" color={COLORS.primary} />
      ) : (
        <Switch
          value={enabled}
          onValueChange={toggleFlag}
          trackColor={{ false: '#D1D5DB', true: COLORS.success + '80' }}
          thumbColor={enabled ? COLORS.success : '#9CA3AF'}
        />
      )}
    </View>
  );
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

  // Set Password state
  const [showSetPassword, setShowSetPassword] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [hasPassword, setHasPassword] = useState(false);

  // Admin state
  const [userRole, setUserRole] = useState('user');
  const [showAdminPanel, setShowAdminPanel] = useState(false);
  const [adminUsers, setAdminUsers] = useState<any[]>([]);
  const [promoteEmail, setPromoteEmail] = useState('');
  const [promoteRole, setPromoteRole] = useState<'admin' | 'co_admin'>('admin');
  const [adminLoading, setAdminLoading] = useState(false);

  useEffect(() => {
    fetchQuestions();
    fetchLatestAssessment();
    fetchUserInfo();
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
      showAlert('Incomplete', 'Please answer all questions');
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post('/assessment', { answers });
      setAssessmentResult(response.data);
      setShowQuiz(false);
      setAnswers({});
      showAlert('Assessment Complete', `Your dominant mode is: ${response.data.dominant_mode}`);
    } catch (error) {
      showAlert('Error', 'Failed to submit assessment');
    } finally {
      setSubmitting(false);
    }
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

  const handleAdminSetup = async () => {
    showAlert(
      'Become Super Admin',
      'This will make you the Super Admin. This can only be done once.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Confirm',
          onPress: async () => {
            try {
              await api.post('/admin/setup');
              setUserRole('super_admin');
              showAlert('Success', 'You are now Super Admin!');
            } catch (err: any) {
              showAlert('Error', err.response?.data?.detail || 'Setup failed');
            }
          },
        },
      ]
    );
  };

  const fetchAdminUsers = async () => {
    try {
      const response = await api.get('/admin/users');
      setAdminUsers(response.data || []);
    } catch (err: any) {
      console.error('Error fetching admin users:', err);
    }
  };

  const handlePromoteUser = async () => {
    if (!promoteEmail.trim()) {
      showAlert('Error', 'Please enter an email address');
      return;
    }
    setAdminLoading(true);
    try {
      await api.post('/admin/promote', { email: promoteEmail.trim(), role: promoteRole });
      showAlert('Success', `${promoteEmail} promoted to ${promoteRole === 'co_admin' ? 'Co-Admin' : 'Admin'}`);
      setPromoteEmail('');
      fetchAdminUsers();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Promotion failed');
    } finally {
      setAdminLoading(false);
    }
  };

  const handleDemoteUser = (email: string, role: string) => {
    showAlert(
      'Demote User',
      `Remove ${role} role from ${email}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Demote',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.post('/admin/demote', { email });
              fetchAdminUsers();
              showAlert('Done', `${email} demoted to regular user`);
            } catch (err: any) {
              showAlert('Error', err.response?.data?.detail || 'Demotion failed');
            }
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
            {userRole !== 'user' && (
              <View style={[styles.authBadge, styles.roleBadge, 
                userRole === 'super_admin' && styles.roleBadgeSuperAdmin,
                userRole === 'co_admin' && styles.roleBadgeCoAdmin,
                userRole === 'admin' && styles.roleBadgeAdmin,
              ]}>
                <Ionicons
                  name={userRole === 'super_admin' ? 'shield' : userRole === 'co_admin' ? 'shield-half' : 'shield-outline'}
                  size={12}
                  color={userRole === 'super_admin' ? '#F59E0B' : userRole === 'co_admin' ? '#8B5CF6' : '#3B82F6'}
                />
                <Text style={[styles.authText, { 
                  color: userRole === 'super_admin' ? '#F59E0B' : userRole === 'co_admin' ? '#8B5CF6' : '#3B82F6',
                  fontWeight: '700',
                }]}>
                  {userRole === 'super_admin' ? 'Super Admin' : userRole === 'co_admin' ? 'Co-Admin' : 'Admin'}
                </Text>
              </View>
            )}
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

      {/* Admin Panel - visible to admins and setup for regular users */}
      <Text style={styles.sectionTitle}>Administration</Text>
      <Card style={styles.passwordCard}>
        {userRole === 'user' ? (
          <TouchableOpacity style={styles.adminSetupRow} onPress={handleAdminSetup}>
            <View style={[styles.passwordSetIcon, { backgroundColor: 'rgba(245, 158, 11, 0.1)' }]}>
              <Ionicons name="shield-outline" size={24} color="#F59E0B" />
            </View>
            <View style={styles.passwordSetInfo}>
              <Text style={styles.passwordSetTitle}>Become Super Admin</Text>
              <Text style={styles.passwordSetSubtitle}>One-time setup (if no admin exists)</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color={COLORS.textMuted} />
          </TouchableOpacity>
        ) : (
          <>
            <TouchableOpacity
              style={styles.adminSetupRow}
              onPress={() => {
                setShowAdminPanel(!showAdminPanel);
                if (!showAdminPanel) fetchAdminUsers();
              }}
            >
              <View style={[styles.passwordSetIcon, { backgroundColor: 'rgba(245, 158, 11, 0.1)' }]}>
                <Ionicons
                  name={userRole === 'super_admin' ? 'shield' : userRole === 'co_admin' ? 'shield-half' : 'shield-outline'}
                  size={24}
                  color="#F59E0B"
                />
              </View>
              <View style={styles.passwordSetInfo}>
                <Text style={styles.passwordSetTitle}>Manage Admins</Text>
                <Text style={styles.passwordSetSubtitle}>
                  {userRole === 'super_admin' ? 'Full control' : userRole === 'co_admin' ? 'Can manage admins' : 'View only'}
                </Text>
              </View>
              <Ionicons name={showAdminPanel ? 'chevron-up' : 'chevron-down'} size={20} color={COLORS.textMuted} />
            </TouchableOpacity>

            {showAdminPanel && (
              <View style={styles.adminPanelContent}>
                {/* Promote section - Super Admin & Co-Admin only */}
                {(userRole === 'super_admin' || userRole === 'co_admin') && (
                  <View style={styles.promoteSection}>
                    <Text style={styles.promoteSectionTitle}>Add Admin</Text>
                    <TextInput
                      style={styles.promoteInput}
                      value={promoteEmail}
                      onChangeText={setPromoteEmail}
                      placeholder="User email..."
                      placeholderTextColor={COLORS.textMuted}
                      autoCapitalize="none"
                      keyboardType="email-address"
                    />
                    <View style={styles.promoteRoleRow}>
                      <TouchableOpacity
                        style={[styles.roleChip, promoteRole === 'admin' && styles.roleChipActive]}
                        onPress={() => setPromoteRole('admin')}
                      >
                        <Text style={[styles.roleChipText, promoteRole === 'admin' && styles.roleChipTextActive]}>Admin</Text>
                      </TouchableOpacity>
                      {userRole === 'super_admin' && (
                        <TouchableOpacity
                          style={[styles.roleChip, promoteRole === 'co_admin' && styles.roleChipActive]}
                          onPress={() => setPromoteRole('co_admin')}
                        >
                          <Text style={[styles.roleChipText, promoteRole === 'co_admin' && styles.roleChipTextActive]}>Co-Admin</Text>
                        </TouchableOpacity>
                      )}
                      <TouchableOpacity
                        style={styles.promoteBtn}
                        onPress={handlePromoteUser}
                        disabled={adminLoading}
                      >
                        {adminLoading ? (
                          <ActivityIndicator size="small" color="#FFF" />
                        ) : (
                          <Text style={styles.promoteBtnText}>Promote</Text>
                        )}
                      </TouchableOpacity>
                    </View>
                  </View>
                )}

                {/* Admin Users List */}
                <Text style={styles.adminListTitle}>Admin Team</Text>
                {adminUsers.map((admin, idx) => (
                  <View key={idx} style={styles.adminUserRow}>
                    <View style={styles.adminUserInfo}>
                      <Text style={styles.adminUserName}>{admin.name}</Text>
                      <Text style={styles.adminUserEmail}>{admin.email}</Text>
                    </View>
                    <View style={[styles.adminRoleBadge,
                      admin.role === 'super_admin' && { backgroundColor: 'rgba(245, 158, 11, 0.1)' },
                      admin.role === 'co_admin' && { backgroundColor: 'rgba(139, 92, 246, 0.1)' },
                      admin.role === 'admin' && { backgroundColor: 'rgba(59, 130, 246, 0.1)' },
                    ]}>
                      <Text style={[styles.adminRoleBadgeText,
                        admin.role === 'super_admin' && { color: '#F59E0B' },
                        admin.role === 'co_admin' && { color: '#8B5CF6' },
                        admin.role === 'admin' && { color: '#3B82F6' },
                      ]}>
                        {admin.role === 'super_admin' ? 'Super' : admin.role === 'co_admin' ? 'Co-Admin' : 'Admin'}
                      </Text>
                    </View>
                    {/* Demote button - based on hierarchy */}
                    {admin.role !== 'super_admin' && (
                      (userRole === 'super_admin' || (userRole === 'co_admin' && admin.role === 'admin')) ? (
                        <TouchableOpacity onPress={() => handleDemoteUser(admin.email, admin.role)} style={styles.demoteBtn}>
                          <Ionicons name="remove-circle-outline" size={18} color={COLORS.error} />
                        </TouchableOpacity>
                      ) : null
                    )}
                  </View>
                ))}
                {adminUsers.length === 0 && (
                  <Text style={styles.noAdminsText}>No admin users found</Text>
                )}

                {/* WOWO Feature Flags Toggle */}
                <View style={styles.wowoSection}>
                  <Text style={styles.promoteSectionTitle}>WOWO Feature Flags</Text>
                  <Text style={{ fontSize: 12, color: COLORS.textMuted, marginBottom: 10 }}>
                    Wire On / Wire Off - Toggle features for all users
                  </Text>
                  <WowoToggle label="Simple Solution Finder" flagKey="solution_finder" />
                  <WowoToggle label="Advanced Solution Matrix" flagKey="solution_matrix" />
                </View>
              </View>
            )}
          </>
        )}
      </Card>

      {/* Set Password Section - Show for Google users or users who want to change password */}
      {(user?.auth_method === 'google' || user?.auth_method === 'google_and_email') && (
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

      {/* Manage Experts */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/admin/experts')}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#6366F1', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="shield-checkmark" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.text }}>Authorized Experts</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>View and manage experts for sharing decisions</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Manage Templates */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/admin/templates')}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#10B981', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="document-text" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.text }}>Decision Templates</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Review, approve and manage decision templates</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Admin Settings */}
      {userRole !== 'user' && (
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
          onPress={() => router.push('/admin/settings')}
        >
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#F59E0B', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="settings" size={18} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Admin Settings</Text>
            <Text style={{ fontSize: 12, color: COLORS.textMuted }}>WOWO feature flags, call config & more</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
        </TouchableOpacity>
      )}

      {/* Org Members Management */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/admin/org-members')}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#6366F1', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="people" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Org Members</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Manage org roles: Super Admin, Co-Admin, Admin</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Centralized Task Tracker */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/tools/ctt')}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#1E3A5F', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="clipboard" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Task Tracker (CTT)</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Track all action items from Decisions & Solutions</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Solutions Store - Admin */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 }}
        onPress={() => router.push('/tools/solutions-store' as any)}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#7C3AED', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="storefront" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Solutions Store</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Products, services, events & contacts catalog</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Pending Approvals - Admin Only */}
      <TouchableOpacity
        style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#F59E0B30', marginBottom: 12 }}
        onPress={() => router.push('/admin/pending-approvals' as any)}
      >
        <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#F59E0B', alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="hourglass" size={18} color="#FFF" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Pending Approvals</Text>
          <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Review user-submitted public solutions</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
      </TouchableOpacity>

      {/* Documentation Hub - Admin Only */}
      {userRole !== 'user' && (
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#6366F130', marginBottom: 12 }}
          onPress={() => router.push('/admin/docs' as any)}
        >
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#1E293B', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="library" size={18} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Documentation Hub</Text>
            <Text style={{ fontSize: 12, color: COLORS.textMuted }}>PRD, SRS, Test Cases, API Catalog & more</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
        </TouchableOpacity>
      )}

      {/* Decision Making Modes - Admin Only */}
      {userRole !== 'user' && (
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#7C3AED30', marginBottom: 12 }}
          onPress={() => router.push('/admin/decision-modes' as any)}
        >
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#7C3AED', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="git-network" size={18} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Decision Making Modes</Text>
            <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Configure 6 multi-user decision modes</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
        </TouchableOpacity>
      )}

      {/* Incident Response - Admin Only */}
      {userRole !== 'user' && (
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#DC262630', marginBottom: 12 }}
          onPress={() => router.push('/admin/incident-response' as any)}
        >
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#DC2626', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="shield" size={18} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Incident Response</Text>
            <Text style={{ fontSize: 12, color: COLORS.textMuted }}>CERT-In compliance, breach alerts & audit trail</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
        </TouchableOpacity>
      )}

      {/* Social Learning Admin */}
      {userRole !== 'user' && (
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#7C3AED30', marginBottom: 12 }}
          onPress={() => router.push('/admin/social-learning-admin' as any)}
        >
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#7C3AED', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="newspaper" size={18} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>Social Learning Admin</Text>
            <Text style={{ fontSize: 12, color: COLORS.textMuted }}>Review templates, synthesize premium content</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
        </TouchableOpacity>
      )}

      {/* WOWO — Access Control Matrix */}
      {userRole !== 'user' && (
        <TouchableOpacity
          style={{ flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, padding: 14, borderRadius: 12, borderWidth: 1, borderColor: '#8B5CF630', marginBottom: 12 }}
          onPress={() => router.push('/admin/acm' as any)}
        >
          <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: '#8B5CF6', alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name="shield-checkmark" size={18} color="#FFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>WOWO — Access Control Matrix</Text>
            <Text style={{ fontSize: 12, color: COLORS.textMuted }}>User types, subscriptions, feature gating & quotas</Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
        </TouchableOpacity>
      )}

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
          <Text style={{ fontSize: 14, fontWeight: '600', color: COLORS.textPrimary }}>TEPFI Matrix</Text>
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
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: 100 }}>
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
