import React, { useEffect } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, Image, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuthStore } from '../src/store/authStore';
import { useBrandingStore } from '../src/store/brandingStore';
import { COLORS, GRADIENTS } from '../src/constants/colors';
import * as Linking from 'expo-linking';

export default function Index() {
  const router = useRouter();
  const { isLoading, isAuthenticated, checkAuth, loginWithGoogle } = useAuthStore();
  const brand = useBrandingStore(s => s.brand);

  useEffect(() => {
    const handleDeepLink = async (event: { url: string }) => {
      const url = event.url;
      // Handle OAuth callback
      if (url.includes('session_id=')) {
        const sessionId = url.split('session_id=')[1]?.split('&')[0];
        if (sessionId) {
          try {
            await loginWithGoogle(sessionId);
            router.replace('/(tabs)');
          } catch (error) {
            console.error('OAuth callback error:', error);
            router.replace('/auth/login');
          }
        }
      }
    };

    // Check initial URL (for web)
    Linking.getInitialURL().then((url) => {
      if (url) handleDeepLink({ url });
    });

    // Listen for deep links
    const subscription = Linking.addEventListener('url', handleDeepLink);

    return () => subscription.remove();
  }, []);

  useEffect(() => {
    // Check for session_id in URL hash (web)
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const hash = window.location.hash;
      if (hash.includes('session_id=')) {
        const sessionId = hash.split('session_id=')[1]?.split('&')[0];
        if (sessionId) {
          loginWithGoogle(sessionId).then(() => {
            // Clear hash and redirect
            window.history.replaceState(null, '', window.location.pathname);
            router.replace('/(tabs)');
          }).catch((error) => {
            console.error('OAuth error:', error);
            router.replace('/auth/login');
          });
          return;
        }
      }
    }

    // Normal auth check
    const timer = setTimeout(() => {
      if (!isLoading) {
        if (isAuthenticated) {
          router.replace('/(tabs)');
        } else {
          router.replace('/auth/login');
        }
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [isLoading, isAuthenticated]);

  return (
    <LinearGradient
      colors={GRADIENTS.primary}
      style={styles.container}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
    >
      <View style={styles.content}>
        <View style={styles.logoContainer}>
          <Image
            source={{ uri: 'https://customer-assets.emergentagent.com/job_chapter2-guide/artifacts/acyqe96y_VENTURE%20BUDDHA-SqaureHD.png' }}
            style={styles.logo}
            resizeMode="contain"
          />
        </View>
        <Text style={styles.title}>{brand.display_name}</Text>
        <Text style={styles.subtitle} numberOfLines={2}>{brand.full_expansion}</Text>
        <Text style={[styles.subtitle, { fontSize: 11, opacity: 0.7, marginTop: 4 }]}>by {brand.master_brand}</Text>
        <ActivityIndicator color={COLORS.white} size="large" style={styles.loader} />
      </View>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  logoContainer: {
    width: 120,
    height: 120,
    backgroundColor: COLORS.white,
    borderRadius: 24,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
    boxShadow: '0px 4px 8px rgba(0, 0, 0, 0.2)',
    elevation: 4,
  },
  logo: {
    width: 100,
    height: 100,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    color: COLORS.white,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.8)',
    marginBottom: 48,
  },
  loader: {
    marginTop: 24,
  },
});
