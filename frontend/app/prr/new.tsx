import React, { useState } from 'react';
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

const FOLDERS = [
  { id: 'holistic_health', name: 'Holistic Health', icon: 'fitness', color: '#10B981' },
  { id: 'knowledge_skills', name: 'Knowledge & Skills', icon: 'book', color: '#3B82F6' },
  { id: 'relationships', name: 'Relationships', icon: 'heart', color: '#EC4899' },
  { id: 'finance', name: 'Finance', icon: 'cash', color: '#F59E0B' },
  { id: 'assets', name: 'Assets', icon: 'home', color: '#8B5CF6' },
  { id: 'career', name: 'Career', icon: 'briefcase', color: '#6366F1' },
  { id: 'hobbies_entertainment', name: 'Hobbies & Entertainment', icon: 'game-controller', color: '#14B8A6' },
  { id: 'social_image', name: 'Social Image & Influence', icon: 'star', color: '#F97316' },
  { id: 'social_contributions', name: 'Social Contributions', icon: 'people', color: '#06B6D4' },
  { id: 'spirituality_religion', name: 'Spirituality & Religion', icon: 'leaf', color: '#A855F7' },
];

export default function NewPRRDecision() {
  const router = useRouter();
  const [title, setTitle] = useState('');
  const [context, setContext] = useState('');
  const [selectedFolder, setSelectedFolder] = useState('');
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
      const response = await api.post('/decisions', {
        title,
        context,
        folder: selectedFolder,
      });
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
            {/* Folder Selection */}
            <View style={styles.folderSection}>
              <Text style={styles.folderLabel}>Life Area Folder</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.folderScroll}>
                {FOLDERS.map((folder) => (
                  <TouchableOpacity
                    key={folder.id}
                    style={[
                      styles.folderChip,
                      { borderColor: folder.color + '50' },
                      selectedFolder === folder.id && {
                        borderColor: folder.color,
                        backgroundColor: folder.color + '15',
                      },
                    ]}
                    onPress={() => setSelectedFolder(selectedFolder === folder.id ? '' : folder.id)}
                    activeOpacity={0.7}
                  >
                    <Ionicons
                      name={folder.icon as any}
                      size={14}
                      color={selectedFolder === folder.id ? folder.color : COLORS.textMuted}
                    />
                    <Text
                      style={[
                        styles.folderChipText,
                        selectedFolder === folder.id && { color: folder.color, fontWeight: '600' },
                      ]}
                      numberOfLines={1}
                    >
                      {folder.name}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>

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
  container: { flex: 1, backgroundColor: COLORS.background },
  keyboardView: { flex: 1 },
  scrollContent: { padding: 16 },
  header: { marginBottom: 24 },
  stepLabel: { fontSize: 14, fontWeight: '600', color: COLORS.primary, marginBottom: 8 },
  title: { fontSize: 24, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  description: { fontSize: 14, color: COLORS.textSecondary, lineHeight: 20 },
  form: { marginBottom: 24 },
  // Folder selection
  folderSection: { marginBottom: 16 },
  folderLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 8 },
  folderScroll: { flexGrow: 0 },
  folderChip: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    paddingHorizontal: 10, paddingVertical: 7,
    borderRadius: 16, borderWidth: 1.5, borderColor: COLORS.border,
    marginRight: 7, backgroundColor: COLORS.white,
  },
  folderChipText: { fontSize: 12, color: COLORS.textSecondary },
  tip: {
    backgroundColor: 'rgba(142,36,170,0.08)', borderRadius: 12, padding: 16, marginTop: 8,
  },
  tipTitle: { fontSize: 14, fontWeight: '600', color: COLORS.primary, marginBottom: 4 },
  tipText: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18 },
  button: { marginBottom: 32 },
});
