import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Input } from '../../src/components/Input';
import { GradientButton } from '../../src/components/GradientButton';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

type Step = 'email' | 'otp' | 'success';

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [otpHint, setOtpHint] = useState('');

  const handleRequestOTP = async () => {
    if (!email.trim()) {
      setError('Please enter your email');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await api.post('/auth/forgot-password', { email: email.trim() });
      // MVP: Show OTP from response (in production, this would be sent via email)
      if (response.data.otp) {
        setOtpHint(response.data.otp);
      }
      setStep('otp');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send reset code');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (!otp.trim()) {
      setError('Please enter the OTP code');
      return;
    }
    if (!newPassword) {
      setError('Please enter a new password');
      return;
    }
    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await api.post('/auth/reset-password', {
        email: email.trim(),
        otp: otp.trim(),
        new_password: newPassword,
      });
      setStep('success');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset password');
    } finally {
      setLoading(false);
    }
  };

  const renderEmailStep = () => (
    <>
      <View style={styles.iconContainer}>
        <View style={styles.iconCircle}>
          <Ionicons name="lock-closed-outline" size={40} color={COLORS.primary} />
        </View>
      </View>

      <Text style={styles.title}>Forgot Password?</Text>
      <Text style={styles.subtitle}>
        Enter your email address and we'll send you a verification code to reset your password.
      </Text>

      {error ? (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={20} color={COLORS.error} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <Input
        label="Email"
        placeholder="Enter your registered email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
      />

      <GradientButton
        title="Send Reset Code"
        onPress={handleRequestOTP}
        loading={loading}
        style={styles.actionButton}
      />
    </>
  );

  const renderOTPStep = () => (
    <>
      <View style={styles.iconContainer}>
        <View style={styles.iconCircle}>
          <Ionicons name="keypad-outline" size={40} color={COLORS.primary} />
        </View>
      </View>

      <Text style={styles.title}>Enter Verification Code</Text>
      <Text style={styles.subtitle}>
        We've sent a 6-digit code to {email}. Enter it below along with your new password.
      </Text>

      {/* MVP OTP Hint */}
      {otpHint ? (
        <View style={styles.otpHintContainer}>
          <Ionicons name="information-circle" size={18} color={COLORS.info} />
          <Text style={styles.otpHintText}>
            MVP Mode: Your OTP is <Text style={styles.otpHintCode}>{otpHint}</Text>
          </Text>
        </View>
      ) : null}

      {error ? (
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={20} color={COLORS.error} />
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <Input
        label="Verification Code"
        placeholder="Enter 6-digit code"
        value={otp}
        onChangeText={setOtp}
        keyboardType="numeric"
      />

      <Input
        label="New Password"
        placeholder="Enter new password (min 6 characters)"
        value={newPassword}
        onChangeText={setNewPassword}
        secureTextEntry
      />

      <Input
        label="Confirm Password"
        placeholder="Confirm your new password"
        value={confirmPassword}
        onChangeText={setConfirmPassword}
        secureTextEntry
      />

      <GradientButton
        title="Reset Password"
        onPress={handleResetPassword}
        loading={loading}
        style={styles.actionButton}
      />

      <TouchableOpacity style={styles.resendRow} onPress={handleRequestOTP}>
        <Ionicons name="refresh" size={16} color={COLORS.primary} />
        <Text style={styles.resendText}>Resend Code</Text>
      </TouchableOpacity>
    </>
  );

  const renderSuccessStep = () => (
    <>
      <View style={styles.iconContainer}>
        <View style={[styles.iconCircle, { backgroundColor: 'rgba(16, 185, 129, 0.1)' }]}>
          <Ionicons name="checkmark-circle" size={48} color={COLORS.success} />
        </View>
      </View>

      <Text style={styles.title}>Password Reset!</Text>
      <Text style={styles.subtitle}>
        Your password has been reset successfully. You can now login with your new password.
      </Text>

      <GradientButton
        title="Back to Login"
        onPress={() => router.replace('/auth/login')}
        style={styles.actionButton}
      />
    </>
  );

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
          {/* Back button */}
          {step !== 'success' && (
            <TouchableOpacity
              style={styles.backButton}
              onPress={() => {
                if (step === 'otp') {
                  setStep('email');
                  setError('');
                } else {
                  safeBack(router);
                }
              }}
            >
              <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
              <Text style={styles.backText}>
                {step === 'otp' ? 'Change Email' : 'Back to Login'}
              </Text>
            </TouchableOpacity>
          )}

          <View style={styles.content}>
            {step === 'email' && renderEmailStep()}
            {step === 'otp' && renderOTPStep()}
            {step === 'success' && renderSuccessStep()}
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
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
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 24,
  },
  backText: {
    fontSize: 16,
    color: COLORS.textPrimary,
    fontWeight: '500',
  },
  content: {
    flex: 1,
    justifyContent: 'center',
  },
  iconContainer: {
    alignItems: 'center',
    marginBottom: 24,
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(142, 36, 170, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: COLORS.textPrimary,
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 24,
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
  otpHintContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    gap: 8,
  },
  otpHintText: {
    color: COLORS.info,
    fontSize: 13,
    flex: 1,
  },
  otpHintCode: {
    fontWeight: '700',
    fontSize: 15,
    letterSpacing: 2,
  },
  actionButton: {
    marginTop: 8,
  },
  resendRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    gap: 6,
  },
  resendText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
});
