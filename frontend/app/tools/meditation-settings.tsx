import React, { useState, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import { AudioGuidePlayer } from '../../src/components/AudioGuidePlayer';
import * as DocumentPicker from 'expo-document-picker';
import api from '../../src/utils/api';

interface MeditationSlot {
  id: string;
  name: string;
  description: string;
  default_url: string;
  default_type: string;
  icon: string;
  color: string;
  source_type: string;
  resolved_url: string;
  custom_url: string;
  filename: string;
  original_name: string;
}

export default function MeditationSettingsScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [meditations, setMeditations] = useState<Record<string, MeditationSlot>>({});
  const [editingId, setEditingId] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [uploading, setUploading] = useState('');
  const [saving, setSaving] = useState('');

  useEffect(() => { fetchPrefs(); }, []);

  const fetchPrefs = async () => {
    setLoading(true);
    try {
      const res = await api.get('/meditation-settings/preferences');
      setMeditations(res.data?.meditations || {});
    } catch (e) { console.error('Meditation prefs error:', e); }
    finally { setLoading(false); }
  };

  const handleSetUrl = async (medId: string) => {
    if (!urlInput.trim()) { showAlert('Required', 'Please enter a URL'); return; }
    setSaving(medId);
    try {
      await api.put('/meditation-settings/preferences', {
        meditation_id: medId,
        source_type: 'custom_url',
        custom_url: urlInput.trim(),
      });
      showAlert('Saved', 'Custom URL set successfully');
      setEditingId('');
      setUrlInput('');
      fetchPrefs();
    } catch (e) { showAlert('Error', 'Failed to save'); }
    finally { setSaving(''); }
  };

  const handleUpload = async (medId: string) => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'audio/*',
        copyToCacheDirectory: true,
      });

      if (result.canceled || !result.assets?.length) return;

      const file = result.assets[0];
      if (file.size && file.size > 50 * 1024 * 1024) {
        showAlert('Too Large', 'Max file size is 50MB');
        return;
      }

      setUploading(medId);

      const formData = new FormData();
      formData.append('meditation_id', medId);
      formData.append('file', {
        uri: file.uri,
        name: file.name || `meditation_${medId}.mp3`,
        type: file.mimeType || 'audio/mpeg',
      } as any);

      await api.post('/meditation-settings/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
      });

      showAlert('Uploaded', `${file.name} uploaded successfully!`);
      fetchPrefs();
    } catch (e: any) {
      console.error('Upload error:', e);
      showAlert('Upload Failed', e?.response?.data?.detail || 'Failed to upload file');
    } finally { setUploading(''); }
  };

  const handleReset = (medId: string) => {
    showAlert('Reset', 'Revert to default meditation?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Reset', onPress: async () => {
        try {
          await api.delete(`/meditation-settings/preferences/${medId}`);
          showAlert('Reset', 'Reverted to default');
          fetchPrefs();
        } catch (e) { showAlert('Error', 'Failed to reset'); }
      }},
    ]);
  };

  const sourceLabel = (s: string) => {
    if (s === 'custom_url') return 'Custom URL';
    if (s === 'uploaded') return 'Uploaded File';
    return 'Default';
  };

  const sourceColor = (s: string) => {
    if (s === 'custom_url') return '#3B82F6';
    if (s === 'uploaded') return '#10B981';
    return '#6B7280';
  };

  if (loading) {
    return (
      <SafeAreaView style={st.container}>
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#7C3AED" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.container} edges={['top']}>
      <LinearGradient colors={['#7C3AED', '#9333EA']} style={st.header}>
        <TouchableOpacity onPress={() => router.back()} style={st.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={st.headerTitle}>Meditation Settings</Text>
          <Text style={st.headerSub}>Customize your meditation audio guides</Text>
        </View>
      </LinearGradient>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 32 }}>
        <Text style={st.infoText}>
          Customize the 3 meditation guides used in Goal Manifestation. You can paste a URL or upload your own MP3 file.
        </Text>

        {Object.values(meditations).map((med) => {
          const isEditing = editingId === med.id;
          const isUploading = uploading === med.id;
          const isSaving = saving === med.id;

          return (
            <View key={med.id} style={[st.medCard, { borderLeftColor: med.color }]}>
              {/* Header */}
              <View style={st.medHeader}>
                <View style={[st.medIcon, { backgroundColor: med.color }]}>
                  <Ionicons name={med.icon as any} size={18} color="#FFF" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={st.medName}>{med.name}</Text>
                  <Text style={st.medDesc}>{med.description}</Text>
                </View>
                <View style={[st.sourceBadge, { backgroundColor: sourceColor(med.source_type) + '20' }]}>
                  <Text style={[st.sourceText, { color: sourceColor(med.source_type) }]}>
                    {sourceLabel(med.source_type)}
                  </Text>
                </View>
              </View>

              {/* Current source info */}
              {med.source_type === 'uploaded' && med.original_name ? (
                <View style={st.currentInfo}>
                  <Ionicons name="document" size={14} color="#10B981" />
                  <Text style={st.currentText} numberOfLines={1}>{med.original_name}</Text>
                </View>
              ) : med.source_type === 'custom_url' && med.custom_url ? (
                <View style={st.currentInfo}>
                  <Ionicons name="link" size={14} color="#3B82F6" />
                  <Text style={st.currentText} numberOfLines={1}>{med.custom_url}</Text>
                </View>
              ) : null}

              {/* Audio preview */}
              {med.resolved_url && med.default_type === 'audio' && (
                <View style={{ marginTop: 8 }}>
                  <AudioGuidePlayer uri={med.resolved_url} title={`Preview: ${med.name}`} color={med.color} />
                </View>
              )}

              {/* URL input mode */}
              {isEditing && (
                <View style={st.editSection}>
                  <Text style={st.editLabel}>Paste Audio URL</Text>
                  <TextInput style={st.editInput} value={urlInput} onChangeText={setUrlInput}
                    placeholder="https://example.com/my-meditation.mp3"
                    placeholderTextColor={COLORS.textMuted} autoCapitalize="none" autoCorrect={false} />
                  <View style={st.editActions}>
                    <TouchableOpacity style={st.cancelBtn} onPress={() => { setEditingId(''); setUrlInput(''); }}>
                      <Text style={st.cancelText}>Cancel</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={[st.applyBtn, isSaving && { opacity: 0.7 }]}
                      onPress={() => handleSetUrl(med.id)} disabled={isSaving}>
                      {isSaving ? <ActivityIndicator size="small" color="#FFF" /> :
                        <Text style={st.applyText}>Apply URL</Text>}
                    </TouchableOpacity>
                  </View>
                </View>
              )}

              {/* Action buttons */}
              <View style={st.actionRow}>
                <TouchableOpacity style={st.actionBtn}
                  onPress={() => { setEditingId(med.id); setUrlInput(med.custom_url || ''); }}>
                  <Ionicons name="link" size={14} color="#3B82F6" />
                  <Text style={[st.actionText, { color: '#3B82F6' }]}>Set URL</Text>
                </TouchableOpacity>

                <TouchableOpacity style={st.actionBtn}
                  onPress={() => handleUpload(med.id)} disabled={isUploading}>
                  {isUploading ? <ActivityIndicator size="small" color="#10B981" /> : (
                    <>
                      <Ionicons name="cloud-upload" size={14} color="#10B981" />
                      <Text style={[st.actionText, { color: '#10B981' }]}>Upload MP3</Text>
                    </>
                  )}
                </TouchableOpacity>

                {med.source_type !== 'default' && (
                  <TouchableOpacity style={st.actionBtn} onPress={() => handleReset(med.id)}>
                    <Ionicons name="refresh" size={14} color="#EF4444" />
                    <Text style={[st.actionText, { color: '#EF4444' }]}>Reset</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, paddingBottom: 18 },
  backBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },

  infoText: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 20, marginBottom: 16, backgroundColor: '#F5F3FF', padding: 12, borderRadius: 10, borderLeftWidth: 3, borderLeftColor: '#7C3AED' },

  medCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border, borderLeftWidth: 4 },
  medHeader: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  medIcon: { width: 38, height: 38, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  medName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  medDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  sourceBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  sourceText: { fontSize: 9, fontWeight: '700', textTransform: 'uppercase' },

  currentInfo: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8, paddingHorizontal: 4 },
  currentText: { fontSize: 12, color: COLORS.textSecondary, flex: 1 },

  editSection: { marginTop: 10, padding: 10, backgroundColor: '#F8FAFC', borderRadius: 10 },
  editLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },
  editInput: { backgroundColor: COLORS.white, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary },
  editActions: { flexDirection: 'row', gap: 8, marginTop: 8 },
  cancelBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  cancelText: { fontSize: 13, fontWeight: '600', color: COLORS.textMuted },
  applyBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, backgroundColor: '#3B82F6', alignItems: 'center' },
  applyText: { fontSize: 13, fontWeight: '700', color: '#FFF' },

  actionRow: { flexDirection: 'row', gap: 8, marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: COLORS.divider },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  actionText: { fontSize: 11, fontWeight: '600' },
});
