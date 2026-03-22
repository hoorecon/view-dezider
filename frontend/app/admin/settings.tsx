import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  TextInput,
  Switch,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import api from '../../src/utils/api';

export default function AdminSettingsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Call Config
  const [defaultDuration, setDefaultDuration] = useState('30');
  const [minDuration, setMinDuration] = useState('5');
  const [maxDuration, setMaxDuration] = useState('120');

  // Feature Flags
  const [flags, setFlags] = useState({
    solution_finder: false,
    solution_matrix: false,
  });

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const [callRes, flagRes] = await Promise.all([
        api.get('/admin/call-config'),
        api.get('/feature-flags'),
      ]);
      setDefaultDuration(String(callRes.data.default_duration || 30));
      setMinDuration(String(callRes.data.min_duration || 5));
      setMaxDuration(String(callRes.data.max_duration || 120));
      setFlags(flagRes.data || { solution_finder: false, solution_matrix: false });
    } catch (e) {
      console.error('Error fetching settings:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveCallConfig = async () => {
    setSaving(true);
    try {
      await api.put('/admin/call-config', {
        default_duration: parseInt(defaultDuration) || 30,
        min_duration: parseInt(minDuration) || 5,
        max_duration: parseInt(maxDuration) || 120,
      });
      Alert.alert('Saved', 'Call configuration updated');
    } catch (e) {
      Alert.alert('Error', 'Failed to save call config');
    } finally {
      setSaving(false);
    }
  };

  const toggleFlag = async (key: string, value: boolean) => {
    const newFlags = { ...flags, [key]: value };
    setFlags(newFlags);
    try {
      await api.put('/admin/feature-flags', newFlags);
    } catch (e) {
      Alert.alert('Error', 'Failed to update feature flag');
      setFlags(prev => ({ ...prev, [key]: !value }));
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={GRADIENTS.header} style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Admin Settings</Text>
      </LinearGradient>

      <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent}>
        {/* WOWO Feature Flags */}
        <Text style={styles.sectionTitle}>WOWO Feature Flags</Text>
        <View style={styles.card}>
          <Text style={styles.cardDescription}>
            Wire On / Wire Off — Control which solution tools are visible to all users
          </Text>

          <View style={styles.flagRow}>
            <View style={styles.flagInfo}>
              <Ionicons name="search" size={20} color={COLORS.teal} />
              <View>
                <Text style={styles.flagLabel}>Simple Solution Finder</Text>
                <Text style={styles.flagStatus}>
                  {flags.solution_finder ? 'Active — Visible to all' : 'Disabled — Hidden from users'}
                </Text>
              </View>
            </View>
            <Switch
              value={flags.solution_finder}
              onValueChange={v => toggleFlag('solution_finder', v)}
              trackColor={{ false: '#D1D5DB', true: COLORS.success + '80' }}
              thumbColor={flags.solution_finder ? COLORS.success : '#9CA3AF'}
            />
          </View>

          <View style={styles.flagRow}>
            <View style={styles.flagInfo}>
              <Ionicons name="grid" size={20} color={COLORS.accent} />
              <View>
                <Text style={styles.flagLabel}>Advanced Solution Matrix</Text>
                <Text style={styles.flagStatus}>
                  {flags.solution_matrix ? 'Active — Visible to all' : 'Disabled — Hidden from users'}
                </Text>
              </View>
            </View>
            <Switch
              value={flags.solution_matrix}
              onValueChange={v => toggleFlag('solution_matrix', v)}
              trackColor={{ false: '#D1D5DB', true: COLORS.success + '80' }}
              thumbColor={flags.solution_matrix ? COLORS.success : '#9CA3AF'}
            />
          </View>
        </View>

        {/* Call Configuration */}
        <Text style={styles.sectionTitle}>Video Call Configuration</Text>
        <View style={styles.card}>
          <Text style={styles.cardDescription}>
            Configure default and limits for expert video call durations (in minutes)
          </Text>

          <Text style={styles.inputLabel}>Default Duration (minutes)</Text>
          <TextInput
            style={styles.input}
            value={defaultDuration}
            onChangeText={setDefaultDuration}
            keyboardType="numeric"
            placeholder="30"
            placeholderTextColor={COLORS.textMuted}
          />

          <View style={styles.twoCol}>
            <View style={{ flex: 1 }}>
              <Text style={styles.inputLabel}>Min Duration</Text>
              <TextInput
                style={styles.input}
                value={minDuration}
                onChangeText={setMinDuration}
                keyboardType="numeric"
                placeholder="5"
                placeholderTextColor={COLORS.textMuted}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.inputLabel}>Max Duration</Text>
              <TextInput
                style={styles.input}
                value={maxDuration}
                onChangeText={setMaxDuration}
                keyboardType="numeric"
                placeholder="120"
                placeholderTextColor={COLORS.textMuted}
              />
            </View>
          </View>

          <TouchableOpacity
            style={[styles.saveBtn, saving && { opacity: 0.7 }]}
            onPress={handleSaveCallConfig}
            disabled={saving}
          >
            {saving ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <>
                <Ionicons name="save" size={18} color="#FFF" />
                <Text style={styles.saveBtnText}>Save Call Config</Text>
              </>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row', alignItems: 'center', padding: 16, paddingBottom: 20,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center', marginRight: 12,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  scrollView: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 40 },
  sectionTitle: {
    fontSize: 18, fontWeight: '700', color: COLORS.textPrimary,
    marginBottom: 10, marginTop: 8,
  },
  card: {
    backgroundColor: COLORS.white, borderRadius: 14,
    padding: 16, marginBottom: 16,
    borderWidth: 1, borderColor: COLORS.border,
  },
  cardDescription: {
    fontSize: 13, color: COLORS.textSecondary, marginBottom: 16,
    lineHeight: 18,
  },
  flagRow: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: COLORS.divider,
  },
  flagInfo: {
    flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1,
  },
  flagLabel: {
    fontSize: 14, fontWeight: '600', color: COLORS.textPrimary,
  },
  flagStatus: {
    fontSize: 11, color: COLORS.textMuted, marginTop: 2,
  },
  inputLabel: {
    fontSize: 13, fontWeight: '600', color: COLORS.textPrimary,
    marginTop: 12, marginBottom: 4,
  },
  input: {
    backgroundColor: COLORS.background, borderRadius: 10,
    borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 10,
    fontSize: 14, color: COLORS.textPrimary,
  },
  twoCol: {
    flexDirection: 'row', gap: 12,
  },
  saveBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, marginTop: 16,
    backgroundColor: COLORS.primary, borderRadius: 12,
    paddingVertical: 12,
  },
  saveBtnText: {
    fontSize: 14, fontWeight: '600', color: '#FFF',
  },
});
