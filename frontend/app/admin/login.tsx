/**
 * /admin/login — Dedicated Admin Portal Login
 *
 * A branded entry-point for administrators. Functionally identical to
 * /auth/login but with admin-only styling and an extra role-check after
 * successful auth. Non-admin users get a clear error and are signed out.
 */
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuthStore } from '../../src/store/authStore';
import { COLORS } from '../../src/constants/colors';

const ADMIN_ROLES = ['admin', 'super_admin', 'co_admin'];

export default function AdminLoginScreen() {
  const router = useRouter();
  const { login, isAuthenticated, user, logout } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Already-logged-in handler
  useEffect(() => {
    if (isAuthenticated && user) {
      const role = (user.role || '').toLowerCase();
      const isAdmin = user.is_admin || ADMIN_ROLES.includes(role);
      if (isAdmin) {
        router.replace('/admin' as any);
      } else {
        // Logged in but not admin — explain & sign out
        setError('Your account does not have admin access. Please use the standard login.');
        logout();
      }
    }
  }, [isAuthenticated, user]);

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      setError('Please enter both email and password.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result: any = await login(email.trim().toLowerCase(), password);
      // After login, the useEffect above will route based on role.
      if (result && result.user) {
        const role = (result.user.role || '').toLowerCase();
        const isAdmin = result.user.is_admin || ADMIN_ROLES.includes(role);
        if (!isAdmin) {
          setError('Your account does not have admin access. Please use the standard login.');
          logout();
        }
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Login failed. Check credentials and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <LinearGradient
        colors={['#0F172A', '#1E293B', '#0F172A']}
        style={StyleSheet.absoluteFillObject}
      />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.kbav}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.shieldWrap}>
              <Ionicons name="shield-checkmark" size={56} color="#F59E0B" />
            </View>
            <Text style={styles.title}>Admin Portal</Text>
            <Text style={styles.subtitle}>Restricted access — administrators only</Text>
          </View>

          {/* Form */}
          <View style={styles.card}>
            {!!error && (
              <View style={styles.errorBox}>
                <Ionicons name="alert-circle" size={18} color="#FCA5A5" />
                <Text style={styles.errorText}>{error}</Text>
              </View>
            )}

            <Text style={styles.label}>Admin email</Text>
            <View style={styles.inputRow}>
              <Ionicons name="mail-outline" size={18} color="#94A3B8" style={styles.inputIcon} />
              <TextInput
                value={email}
                onChangeText={setEmail}
                placeholder="admin@example.com"
                placeholderTextColor="#64748B"
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                style={styles.input}
                editable={!loading}
              />
            </View>

            <Text style={[styles.label, { marginTop: 16 }]}>Password</Text>
            <View style={styles.inputRow}>
              <Ionicons name="lock-closed-outline" size={18} color="#94A3B8" style={styles.inputIcon} />
              <TextInput
                value={password}
                onChangeText={setPassword}
                placeholder="Enter your password"
                placeholderTextColor="#64748B"
                secureTextEntry={!showPassword}
                style={[styles.input, { paddingRight: 38 }]}
                editable={!loading}
                onSubmitEditing={handleLogin}
              />
              <TouchableOpacity
                onPress={() => setShowPassword((s) => !s)}
                style={styles.eyeBtn}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              >
                <Ionicons
                  name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={18}
                  color="#94A3B8"
                />
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              onPress={handleLogin}
              disabled={loading}
              style={styles.primaryBtn}
              activeOpacity={0.85}
            >
              <LinearGradient
                colors={loading ? ['#475569', '#475569'] : ['#F59E0B', '#D97706']}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.btnGradient}
              >
                {loading ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <>
                    <Ionicons name="key" size={18} color="#fff" style={{ marginRight: 8 }} />
                    <Text style={styles.btnText}>Sign in to Admin</Text>
                  </>
                )}
              </LinearGradient>
            </TouchableOpacity>

            <TouchableOpacity
              onPress={() => router.push('/auth/forgot-password' as any)}
              style={styles.linkBtn}
            >
              <Text style={styles.linkText}>Forgot password?</Text>
            </TouchableOpacity>
          </View>

          {/* Footer */}
          <View style={styles.footer}>
            <TouchableOpacity onPress={() => router.replace('/auth/login' as any)}>
              <Text style={styles.footerLink}>
                <Ionicons name="arrow-back" size={12} color="#94A3B8" /> Not an admin? Use standard login
              </Text>
            </TouchableOpacity>
            <Text style={styles.footerNote}>
              All admin sign-ins are logged for audit purposes.
            </Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0F172A' },
  kbav: { flex: 1 },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 32,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: 28,
  },
  shieldWrap: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.35)',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#F8FAFC',
    letterSpacing: 0.4,
  },
  subtitle: {
    fontSize: 13,
    color: '#94A3B8',
    marginTop: 6,
    textAlign: 'center',
  },
  card: {
    backgroundColor: 'rgba(15, 23, 42, 0.7)',
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.18)',
    borderRadius: 20,
    padding: 22,
    width: '100%',
    maxWidth: 440,
    alignSelf: 'center',
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderColor: 'rgba(239, 68, 68, 0.35)',
    borderWidth: 1,
    padding: 12,
    borderRadius: 10,
    marginBottom: 14,
    gap: 8,
  },
  errorText: {
    flex: 1,
    color: '#FCA5A5',
    fontSize: 13,
    lineHeight: 18,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: '#CBD5E1',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 6,
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(30, 41, 59, 0.7)',
    borderWidth: 1,
    borderColor: 'rgba(148, 163, 184, 0.22)',
    borderRadius: 12,
    paddingHorizontal: 12,
    height: 48,
    position: 'relative',
  },
  inputIcon: { marginRight: 8 },
  input: {
    flex: 1,
    color: '#F1F5F9',
    fontSize: 15,
    paddingVertical: 0,
  },
  eyeBtn: {
    position: 'absolute',
    right: 12,
    height: 48,
    justifyContent: 'center',
  },
  primaryBtn: {
    marginTop: 22,
    borderRadius: 12,
    overflow: 'hidden',
  },
  btnGradient: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    height: 48,
  },
  btnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  linkBtn: {
    marginTop: 14,
    alignSelf: 'center',
  },
  linkText: {
    color: '#94A3B8',
    fontSize: 13,
  },
  footer: {
    marginTop: 28,
    alignItems: 'center',
    gap: 10,
  },
  footerLink: {
    color: '#94A3B8',
    fontSize: 13,
    fontWeight: '500',
  },
  footerNote: {
    color: '#475569',
    fontSize: 11,
    textAlign: 'center',
    maxWidth: 320,
  },
});
