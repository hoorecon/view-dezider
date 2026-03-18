import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { COLORS } from '../../src/constants/colors';
import { Input } from '../../src/components/Input';
import { GradientButton } from '../../src/components/GradientButton';
import api from '../../src/utils/api';

export default function NewPRRDecision() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [context, setContext] = useState('');
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    if (!title.trim()) {
      Alert.alert('Error', 'Please enter a decision title');
      return;
    }
    if (!context.trim()) {
      Alert.alert('Error', 'Please describe the decision context');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/decisions', { title, context });
      router.replace(`/prr/${response.data.id}`);
    } catch (error) {
      Alert.alert('Error', 'Failed to create decision');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.header}>
            <Text style={styles.stepLabel}>Step 1 of 10</Text>
            <Text style={styles.title}>State Context & Options</Text>
            <Text style={styles.description}>
              Begin by clearly defining what decision you need to make and the context surrounding it.
            </Text>
          </View>

          <View style={styles.form}>
            <Input
              label="Decision Title"
              placeholder="e.g., Career choice between Company A and B"
              value={title}
              onChangeText={setTitle}
            />

            <Input
              label="Context Description"
              placeholder="Describe the situation, why this decision is important, any constraints or considerations..."
              value={context}
              onChangeText={setContext}
              multiline
              numberOfLines={6}
            />

            <View style={styles.tip}>
              <Text style={styles.tipTitle}>PRR Tip:</Text>
              <Text style={styles.tipText}>
                Be specific about your context. Include timelines, constraints, and what success looks like for you.
              </Text>
            </View>
          </View>

          <GradientButton
            title="Create & Continue"
            onPress={handleCreate}
            loading={loading}
            style={styles.button}
          />
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
    padding: 16,
  },
  header: {
    marginBottom: 24,
  },
  stepLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
    marginBottom: 8,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  description: {
    fontSize: 14,
    color: COLORS.textSecondary,
    lineHeight: 20,
  },
  form: {
    marginBottom: 24,
  },
  tip: {
    backgroundColor: 'rgba(142, 36, 170, 0.08)',
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
  },
  tipTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
    marginBottom: 4,
  },
  tipText: {
    fontSize: 13,
    color: COLORS.textSecondary,
    lineHeight: 18,
  },
  button: {
    marginBottom: 32,
  },
});
