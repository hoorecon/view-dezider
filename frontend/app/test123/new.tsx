import React, { useState } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
  TouchableOpacity,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Input } from '../../src/components/Input';
import { GradientButton } from '../../src/components/GradientButton';
import api from '../../src/utils/api';

export default function NewTest123() {
  const router = useRouter();
  const [situation, setSituation] = useState('');
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    if (!situation.trim()) {
      showAlert('Error', 'Please describe the situation');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/test123', { situation });
      router.replace(`/test123/${response.data.id}`);
    } catch (error) {
      showAlert('Error', 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
      {/* Visible Top Bar with Back & Home */}
      <View style={styles.topBar}>
        <TouchableOpacity style={styles.topBtn} onPress={() => router.back()} accessibilityLabel="Back">
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>Instant Dezider — Quick Decision</Text>
        <TouchableOpacity
          style={[styles.topBtn, styles.topBtnPrimary]}
          onPress={() => router.push('/(tabs)/' as any)}
          accessibilityLabel="Home"
        >
          <Ionicons name="home" size={20} color="#FFF" />
        </TouchableOpacity>
      </View>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.header}>
            <View style={styles.iconContainer}>
              <Ionicons name="flash" size={32} color={COLORS.white} />
            </View>
            <Text style={styles.title}>Instant Dezider</Text>
            <Text style={styles.subtitle}>Instant Decision Making</Text>
          </View>

          <View style={styles.infoBox}>
            <Text style={styles.infoTitle}>When to use Instant Dezider?</Text>
            <Text style={styles.infoText}>
              Use this tool when you need to make an urgent decision and emotions might be clouding your judgment.
            </Text>
          </View>

          <View style={styles.stepsPreview}>
            <View style={styles.stepRow}>
              <View style={[styles.stepBadge, { backgroundColor: COLORS.accent }]}>
                <Text style={styles.stepNum}>1</Text>
              </View>
              <View style={styles.stepInfo}>
                <Text style={styles.stepTitle}>Am I Emotional?</Text>
                <Text style={styles.stepDesc}>Check if emotions are influencing you</Text>
              </View>
            </View>
            <View style={styles.stepRow}>
              <View style={[styles.stepBadge, { backgroundColor: COLORS.warning }]}>
                <Text style={styles.stepNum}>2</Text>
              </View>
              <View style={styles.stepInfo}>
                <Text style={styles.stepTitle}>Worst Case Scenario</Text>
                <Text style={styles.stepDesc}>Evaluate potential consequences</Text>
              </View>
            </View>
            <View style={styles.stepRow}>
              <View style={[styles.stepBadge, { backgroundColor: COLORS.success }]}>
                <Text style={styles.stepNum}>3</Text>
              </View>
              <View style={styles.stepInfo}>
                <Text style={styles.stepTitle}>Core Needs</Text>
                <Text style={styles.stepDesc}>Identify what you truly need</Text>
              </View>
            </View>
          </View>

          <Input
            label="Describe the Situation"
            placeholder="What urgent decision do you need to make? Describe the situation and context..."
            value={situation}
            onChangeText={setSituation}
            multiline
            numberOfLines={5}
          />

          <GradientButton
            title="Start Instant Dezider"
            onPress={handleCreate}
            loading={loading}
            variant="accent"
            style={styles.button}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
    backgroundColor: '#FFFFFF',
  },
  topBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
  },
  topBtnPrimary: { backgroundColor: COLORS.accent },
  topTitle: { flex: 1, fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center' },
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
  },
  header: {
    alignItems: 'center',
    marginBottom: 24,
  },
  iconContainer: {
    width: 64,
    height: 64,
    borderRadius: 20,
    backgroundColor: COLORS.accent,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  subtitle: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 4,
  },
  infoBox: {
    backgroundColor: 'rgba(233, 30, 99, 0.08)',
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.accent,
    marginBottom: 4,
  },
  infoText: {
    fontSize: 13,
    color: COLORS.textSecondary,
    lineHeight: 18,
  },
  stepsPreview: {
    backgroundColor: COLORS.white,
    borderRadius: 12,
    padding: 16,
    marginBottom: 24,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
  },
  stepBadge: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  stepNum: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.white,
  },
  stepInfo: {
    marginLeft: 12,
    flex: 1,
  },
  stepTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  stepDesc: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  button: {
    marginTop: 8,
    marginBottom: 32,
  },
});
