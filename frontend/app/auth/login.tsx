import React, { useState, useEffect, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import { BrandFooter } from '../../src/components/BrandFooter';
import { useBrandingStore } from '../../src/store/brandingStore';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  Image,
  Alert,
  Modal,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import { useAuthStore } from '../../src/store/authStore';
import { getPostAuthRoute } from '../../src/utils/postAuthRedirect';
import { useAppLogo } from '../../src/contexts/FontFamilyContext';
import { COLORS } from '../../src/constants/colors';
import { Input } from '../../src/components/Input';
import { GradientButton } from '../../src/components/GradientButton';

const ORG_TYPES = [
  { key: 'BUSINESS', label: 'Business', icon: 'briefcase', color: '#3B82F6' },
  { key: 'NONPROFIT', label: 'NonProfit', icon: 'heart', color: '#10B981' },
  { key: 'GOVERNMENT', label: 'Government', icon: 'globe', color: '#8B5CF6' },
];

export default function LoginScreen() {
  const router = useRouter();
  const { login, loginWithGoogle, isAuthenticated, fetchOrgBranding, orgBranding, user } = useAuthStore();
  const appLogo = useAppLogo();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [orgSlug, setOrgSlug] = useState('');
  const [showOrgInput, setShowOrgInput] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedOrgType, setSelectedOrgType] = useState('BUSINESS');

  // OTP state
  const [showOtpModal, setShowOtpModal] = useState(false);
  const [otpCode, setOtpCode] = useState('');
  const [verificationId, setVerificationId] = useState('');
  const [maskedPhone, setMaskedPhone] = useState('');
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpError, setOtpError] = useState('');
  const [resendLoading, setResendLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      const role = (user?.role || '').toLowerCase();
      const adminLike = user?.is_admin || role === 'admin' || role === 'super_admin' || role === 'co_admin';
      if (adminLike) {
        router.replace('/admin' as any);
      } else {
        // Honour a pending shared-report deep link (lead-magnet onboarding):
        // route the recipient straight to the report instead of the dashboard.
        getPostAuthRoute().then((route) => router.replace(route as any));
      }
    }
  }, [isAuthenticated, user]);

  const handleOrgLookup = async () => {
    if (!orgSlug.trim()) return;
    const branding = await fetchOrgBranding(orgSlug.trim().toLowerCase());
    if (!branding) {
      setError('Organization not found');
    } else {
      setError('');
      // Set org type from branding if available
      if (branding.org_type) {
        setSelectedOrgType(branding.org_type);
      }
    }
  };

  const handleOrgLogin = async () => {
    if (!orgSlug.trim() || !email.trim() || !password) {
      setError('Please fill in all org login fields');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const r = await import('../../src/utils/api').then(m => m.default.post('/org-auth/login', {
        org_slug: orgSlug.trim().toLowerCase(),
        email: email.trim().toLowerCase(),
        password,
      }));
      const data = r.data;
      if (data.requires_otp) {
        // Show OTP modal
        setVerificationId(data.verification_id);
        setMaskedPhone(data.masked_phone);
        setShowOtpModal(true);
        if (!data.otp_sent) {
          setOtpError('OTP could not be sent. Please check your WhatsApp number.');
        }
      } else {
        // Direct login (NonProfit)
        useAuthStore.getState().setSession(data.session_token, data.user);
        router.replace('/(tabs)');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Org login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async () => {
    if (!otpCode.trim() || otpCode.length < 6) {
      setOtpError('Please enter a valid 6-digit OTP');
      return;
    }
    setOtpLoading(true);
    setOtpError('');
    try {
      const api = (await import('../../src/utils/api')).default;
      const r = await api.post('/org-auth/verify-otp', {
        verification_id: verificationId,
        otp: otpCode.trim(),
      });
      const data = r.data;
      useAuthStore.getState().setSession(data.session_token, data.user);
      setShowOtpModal(false);
      router.replace('/(tabs)');
    } catch (err: any) {
      setOtpError(err.response?.data?.detail || 'Invalid OTP');
    } finally {
      setOtpLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setResendLoading(true);
    try {
      const api = (await import('../../src/utils/api')).default;
      await api.post(`/org-auth/resend-otp?verification_id=${verificationId}`);
      setOtpError('');
      showAlert('OTP Resent', 'A new code has been sent to your WhatsApp.');
    } catch (err: any) {
      setOtpError(err.response?.data?.detail || 'Failed to resend');
    } finally {
      setResendLoading(false);
    }
  };

  const handleLogin = async () => {
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await login(email, password, orgBranding?.id);
      // NOTE: navigation is handled by the `useEffect` watching
      // `isAuthenticated` + `user` (line ~58). Calling `router.replace`
      // here in addition raced with the effect and — combined with the
      // async hydration of the auth store — caused the well-known
      // "first attempt fails, second works" bug. It ALSO sent admins
      // to /(tabs) instead of /admin. Removing the duplicate call
      // fixes both issues. Do not re-add a router call here.
    } catch (err: any) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = useCallback(async () => {
    setGoogleLoading(true);
    setError('');

    try {
      // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
      let redirectUrl: string;
      
      if (Platform.OS === 'web') {
        redirectUrl = window.location.origin;
      } else {
        redirectUrl = Linking.createURL('/');
      }

      const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;

      if (Platform.OS === 'web') {
        window.location.href = authUrl;
      } else {
        const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUrl);
        
        if (result.type === 'success' && result.url) {
          const sessionId = result.url.split('session_id=')[1]?.split('&')[0];
          if (sessionId) {
            await loginWithGoogle(sessionId);
            router.replace((await getPostAuthRoute()) as any);
          }
        }
      }
    } catch (err: any) {
      setError(err.message || 'Google login failed');
      setGoogleLoading(false);
    }
  }, [loginWithGoogle, router]);

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.header}>
            <Image
              source={{ uri: 'https://customer-assets.emergentagent.com/job_chapter2-guide/artifacts/acyqe96y_VENTURE%20BUDDHA-SqaureHD.png' }}
              style={styles.logo}
              resizeMode="contain"
            />
            <Text style={styles.title}>{useBrandingStore.getState().brand.display_name}</Text>
            <Text style={styles.subtitle} numberOfLines={3}>{useBrandingStore.getState().brand.full_expansion}</Text>
          </View>

          {error ? (
            <View style={styles.errorContainer}>
              <Ionicons name="alert-circle" size={20} color={COLORS.error} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          ) : null}

          <View style={styles.form}>
            {/* Organization ID Section */}
            <TouchableOpacity
              style={styles.orgToggle}
              onPress={() => setShowOrgInput(!showOrgInput)}
            >
              <Ionicons name="business-outline" size={16} color={COLORS.primary} />
              <Text style={styles.orgToggleText}>
                {orgBranding ? orgBranding.name : 'Organization Login'}
              </Text>
              <Ionicons name={showOrgInput ? 'chevron-up' : 'chevron-down'} size={16} color={COLORS.textMuted} />
            </TouchableOpacity>

            {showOrgInput && (
              <View style={styles.orgSection}>
                {orgBranding ? (
                  <View style={styles.orgBrandingCard}>
                    <View style={[styles.orgColorDot, { backgroundColor: orgBranding.primary_color || COLORS.primary }]} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.orgBrandingName}>{orgBranding.name}</Text>
                      {orgBranding.tagline ? <Text style={styles.orgBrandingTagline}>{orgBranding.tagline}</Text> : null}
                    </View>
                    <TouchableOpacity onPress={() => { useAuthStore.getState().setOrgBranding(null); setOrgSlug(''); }}>
                      <Ionicons name="close-circle" size={20} color={COLORS.textMuted} />
                    </TouchableOpacity>
                  </View>
                ) : (
                  <View style={styles.orgInputRow}>
                    <Input
                      label="Organization ID"
                      placeholder="Enter org slug (e.g., acme-corp)"
                      value={orgSlug}
                      onChangeText={setOrgSlug}
                      autoCapitalize="none"
                    />
                    <GradientButton
                      title="Verify"
                      onPress={handleOrgLookup}
                      style={styles.orgVerifyBtn}
                      variant="secondary"
                    />
                  </View>
                )}

                {/* Org Type Selector */}
                <Text style={styles.orgTypeLabel}>Organization Type</Text>
                <View style={styles.orgTypeRow}>
                  {ORG_TYPES.map(ot => (
                    <TouchableOpacity
                      key={ot.key}
                      style={[styles.orgTypeChip, selectedOrgType === ot.key && { borderColor: ot.color, backgroundColor: ot.color + '10' }]}
                      onPress={() => setSelectedOrgType(ot.key)}
                    >
                      <Ionicons name={ot.icon as any} size={14} color={selectedOrgType === ot.key ? ot.color : COLORS.textMuted} />
                      <Text style={[styles.orgTypeChipText, selectedOrgType === ot.key && { color: ot.color, fontWeight: '700' }]}>{ot.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
                {selectedOrgType !== 'NONPROFIT' && (
                  <View style={styles.otpNote}>
                    <Ionicons name="logo-whatsapp" size={14} color="#25D366" />
                    <Text style={styles.otpNoteText}>WhatsApp OTP verification required for {selectedOrgType.toLowerCase()} orgs</Text>
                  </View>
                )}
              </View>
            )}

            <Input
              label="Email"
              placeholder="Enter your email"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              testID="login-email"
            />

            <Input
              label="Password"
              placeholder="Enter your password"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              testID="login-password"
            />

            <TouchableOpacity
              style={styles.forgotPassword}
              onPress={() => router.push('/auth/forgot-password')}
            >
              <Text style={styles.forgotPasswordText}>Forgot Password?</Text>
            </TouchableOpacity>

            <GradientButton
              title={showOrgInput && orgSlug ? "Org Sign In" : "Sign In"}
              onPress={showOrgInput && orgSlug ? handleOrgLogin : handleLogin}
              loading={loading}
              style={styles.loginButton}
              testID="login-submit"
            />

            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>or</Text>
              <View style={styles.dividerLine} />
            </View>

            <TouchableOpacity
              style={styles.googleButton}
              onPress={handleGoogleLogin}
              disabled={googleLoading}
              activeOpacity={0.7}
            >
              <Ionicons name="logo-google" size={20} color={COLORS.textPrimary} />
              <Text style={styles.googleText}>
                {googleLoading ? 'Connecting...' : 'Continue with Google'}
              </Text>
            </TouchableOpacity>
          </View>

          <View style={styles.footer}>
            <Text style={styles.footerText}>Don&apos;t have an account? </Text>
            <TouchableOpacity onPress={() => router.push('/auth/register')}>
              <Text style={styles.footerLink}>Sign Up</Text>
            </TouchableOpacity>
          </View>

          {/* Earth Dezider master-brand imprint */}
          <BrandFooter />
        </ScrollView>
      </KeyboardAvoidingView>

      {/* WhatsApp OTP Verification Modal */}
      <Modal visible={showOtpModal} animationType="slide" transparent onRequestClose={() => setShowOtpModal(false)}>
        <View style={styles.otpOverlay}>
          <View style={styles.otpModal}>
            <View style={styles.otpModalHeader}>
              <Ionicons name="logo-whatsapp" size={36} color="#25D366" />
              <Text style={styles.otpModalTitle}>WhatsApp Verification</Text>
              <Text style={styles.otpModalSubtitle}>
                Enter the 6-digit code sent to {maskedPhone}
              </Text>
            </View>

            {otpError ? (
              <View style={styles.otpErrorBox}>
                <Ionicons name="alert-circle" size={16} color={COLORS.error} />
                <Text style={styles.otpErrorText}>{otpError}</Text>
              </View>
            ) : null}

            <Input
              label="OTP Code"
              placeholder="Enter 6-digit code"
              value={otpCode}
              onChangeText={setOtpCode}
              keyboardType="number-pad"
              maxLength={6}
            />

            <GradientButton
              title="Verify & Login"
              onPress={handleVerifyOtp}
              loading={otpLoading}
              style={{ marginTop: 16 }}
            />

            <View style={styles.otpActions}>
              <TouchableOpacity onPress={handleResendOtp} disabled={resendLoading}>
                <Text style={styles.otpResendText}>
                  {resendLoading ? 'Sending...' : 'Resend OTP'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity onPress={() => { setShowOtpModal(false); setOtpCode(''); setOtpError(''); }}>
                <Text style={styles.otpCancelText}>Cancel</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    padding: 24,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: 32,
  },
  logo: {
    width: 80,
    height: 80,
    marginBottom: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: COLORS.textSecondary,
    textAlign: 'center',
  },
  errorContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    gap: 8,
  },
  errorText: {
    color: COLORS.error,
    fontSize: 14,
    flex: 1,
  },
  form: {
    marginBottom: 24,
  },
  loginButton: {
    marginTop: 8,
  },
  forgotPassword: {
    alignSelf: 'flex-end',
    marginBottom: 4,
    marginTop: -4,
  },
  forgotPasswordText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 24,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: COLORS.border,
  },
  dividerText: {
    marginHorizontal: 16,
    color: COLORS.textSecondary,
    fontSize: 14,
  },
  googleButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.white,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    paddingVertical: 16,
    gap: 12,
  },
  googleText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  footerText: {
    color: COLORS.textSecondary,
    fontSize: 14,
  },
  footerLink: {
    color: COLORS.primary,
    fontSize: 14,
    fontWeight: '600',
  },
  orgToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 10,
    paddingHorizontal: 12,
    backgroundColor: '#F5F3FF',
    borderRadius: 10,
    marginBottom: 16,
  },
  orgToggleText: {
    flex: 1,
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
  orgSection: {
    marginBottom: 16,
  },
  orgInputRow: {
    gap: 8,
  },
  orgVerifyBtn: {
    marginTop: 4,
  },
  orgBrandingCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    padding: 12,
    backgroundColor: '#F0FDF4',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#BBF7D0',
  },
  orgColorDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
  },
  orgBrandingName: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  orgBrandingTagline: {
    fontSize: 12,
    color: COLORS.textSecondary,
  },
  // Org Type selector
  orgTypeLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginTop: 14,
    marginBottom: 8,
  },
  orgTypeRow: {
    flexDirection: 'row',
    gap: 8,
  },
  orgTypeChip: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 5,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    backgroundColor: COLORS.white,
  },
  orgTypeChipText: {
    fontSize: 12,
    fontWeight: '500',
    color: COLORS.textSecondary,
  },
  otpNote: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: '#ECFDF5',
    borderRadius: 8,
  },
  otpNoteText: {
    fontSize: 11,
    color: '#065F46',
  },
  // OTP Modal
  otpOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  otpModal: {
    backgroundColor: COLORS.white,
    borderRadius: 20,
    padding: 24,
    width: '100%',
    maxWidth: 380,
  },
  otpModalHeader: {
    alignItems: 'center',
    marginBottom: 20,
  },
  otpModalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginTop: 10,
  },
  otpModalSubtitle: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 20,
  },
  otpErrorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#FEF2F2',
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },
  otpErrorText: {
    fontSize: 13,
    color: COLORS.error,
    flex: 1,
  },
  otpActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 16,
  },
  otpResendText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#25D366',
  },
  otpCancelText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textMuted,
  },
});
