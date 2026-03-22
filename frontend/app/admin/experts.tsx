import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  ActivityIndicator,
  Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

interface Expert {
  id: string;
  name: string;
  email: string;
  specialization: string;
  bio: string;
  is_active: boolean;
}

export default function ExpertsScreen() {
  const router = useRouter();
  const [experts, setExperts] = useState<Expert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingExpert, setEditingExpert] = useState<Expert | null>(null);
  const [form, setForm] = useState({ name: '', email: '', specialization: '', bio: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchExperts();
  }, []);

  const fetchExperts = async () => {
    setLoading(true);
    try {
      const resp = await api.get('/experts?include_inactive=true');
      setExperts(resp.data || []);
    } catch { setExperts([]); }
    finally { setLoading(false); }
  };

  const openAdd = () => {
    setEditingExpert(null);
    setForm({ name: '', email: '', specialization: '', bio: '' });
    setShowForm(true);
  };

  const openEdit = (expert: Expert) => {
    setEditingExpert(expert);
    setForm({ name: expert.name, email: expert.email, specialization: expert.specialization, bio: expert.bio });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.email.trim()) {
      Alert.alert('Error', 'Name and email are required');
      return;
    }
    setSaving(true);
    try {
      if (editingExpert) {
        await api.put(`/experts/${editingExpert.id}`, form);
        Alert.alert('Success', 'Expert updated');
      } else {
        await api.post('/experts', form);
        Alert.alert('Success', 'Expert added');
      }
      setShowForm(false);
      fetchExperts();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const handleDelete = (expert: Expert) => {
    Alert.alert('Delete Expert', `Remove ${expert.name}?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete', style: 'destructive', onPress: async () => {
          try {
            await api.delete(`/experts/${expert.id}`);
            fetchExperts();
          } catch { Alert.alert('Error', 'Failed to delete'); }
        }
      },
    ]);
  };

  const toggleActive = async (expert: Expert) => {
    try {
      await api.put(`/experts/${expert.id}`, { is_active: !expert.is_active });
      fetchExperts();
    } catch { Alert.alert('Error', 'Failed to update'); }
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Authorized Experts</Text>
        <TouchableOpacity onPress={openAdd} style={styles.addBtn}>
          <Ionicons name="add-circle" size={26} color={COLORS.primary} />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        {loading ? (
          <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
        ) : experts.length === 0 ? (
          <View style={styles.emptyState}>
            <Ionicons name="shield-checkmark-outline" size={48} color={COLORS.textMuted} />
            <Text style={styles.emptyTitle}>No Experts Yet</Text>
            <Text style={styles.emptyDesc}>Add authorized experts that users can share steps with for professional guidance.</Text>
            <TouchableOpacity onPress={openAdd} style={styles.emptyAddBtn}>
              <Ionicons name="add" size={18} color={COLORS.white} />
              <Text style={styles.emptyAddText}>Add Expert</Text>
            </TouchableOpacity>
          </View>
        ) : (
          experts.map((expert) => (
            <View key={expert.id} style={[styles.card, !expert.is_active && styles.cardInactive]}>
              <View style={styles.cardHeader}>
                <View style={[styles.avatar, { backgroundColor: expert.is_active ? '#6366F1' : COLORS.textMuted }]}>
                  <Ionicons name="shield-checkmark" size={18} color="#FFF" />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.expertName}>{expert.name}</Text>
                  <Text style={styles.expertEmail}>{expert.email}</Text>
                  {expert.specialization ? (
                    <View style={styles.specBadge}>
                      <Text style={styles.specText}>{expert.specialization}</Text>
                    </View>
                  ) : null}
                </View>
                <TouchableOpacity onPress={() => toggleActive(expert)} style={styles.toggleBtn}>
                  <Ionicons name={expert.is_active ? 'toggle' : 'toggle-outline'} size={28} color={expert.is_active ? '#16A34A' : COLORS.textMuted} />
                </TouchableOpacity>
              </View>
              {expert.bio ? <Text style={styles.bio}>{expert.bio}</Text> : null}
              <View style={styles.cardActions}>
                <TouchableOpacity onPress={() => openEdit(expert)} style={styles.actionBtn}>
                  <Ionicons name="create-outline" size={16} color={COLORS.primary} />
                  <Text style={styles.actionText}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => handleDelete(expert)} style={styles.actionBtn}>
                  <Ionicons name="trash-outline" size={16} color="#EF4444" />
                  <Text style={[styles.actionText, { color: '#EF4444' }]}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))
        )}
      </ScrollView>

      {/* Add/Edit Modal */}
      <Modal visible={showForm} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{editingExpert ? 'Edit Expert' : 'Add Expert'}</Text>
              <TouchableOpacity onPress={() => setShowForm(false)}>
                <Ionicons name="close" size={24} color={COLORS.text} />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 400 }}>
              <Text style={styles.inputLabel}>Name *</Text>
              <TextInput style={styles.input} value={form.name} onChangeText={(t) => setForm({ ...form, name: t })} placeholder="Expert name" placeholderTextColor={COLORS.textMuted} />
              <Text style={styles.inputLabel}>Email *</Text>
              <TextInput style={styles.input} value={form.email} onChangeText={(t) => setForm({ ...form, email: t })} placeholder="expert@email.com" placeholderTextColor={COLORS.textMuted} keyboardType="email-address" autoCapitalize="none" />
              <Text style={styles.inputLabel}>Specialization</Text>
              <TextInput style={styles.input} value={form.specialization} onChangeText={(t) => setForm({ ...form, specialization: t })} placeholder="e.g., Career Coaching, Finance" placeholderTextColor={COLORS.textMuted} />
              <Text style={styles.inputLabel}>Bio</Text>
              <TextInput style={[styles.input, { minHeight: 80, textAlignVertical: 'top' }]} value={form.bio} onChangeText={(t) => setForm({ ...form, bio: t })} placeholder="Brief description..." placeholderTextColor={COLORS.textMuted} multiline />
            </ScrollView>
            <TouchableOpacity onPress={handleSave} disabled={saving} style={styles.saveBtn}>
              {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.saveBtnText}>{editingExpert ? 'Update' : 'Add Expert'}</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  backBtn: { padding: 4 },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '700', color: COLORS.text, marginLeft: 12 },
  addBtn: { padding: 4 },
  content: { padding: 16 },
  emptyState: { alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  emptyDesc: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', paddingHorizontal: 32 },
  emptyAddBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: COLORS.primary, paddingHorizontal: 16, paddingVertical: 10, borderRadius: 12, marginTop: 12 },
  emptyAddText: { fontSize: 14, fontWeight: '600', color: COLORS.white },
  card: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  cardInactive: { opacity: 0.6 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 },
  avatar: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  expertName: { fontSize: 15, fontWeight: '600', color: COLORS.text },
  expertEmail: { fontSize: 12, color: COLORS.textMuted },
  specBadge: { backgroundColor: '#EDE9FE', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8, alignSelf: 'flex-start', marginTop: 3 },
  specText: { fontSize: 11, fontWeight: '600', color: COLORS.primary },
  toggleBtn: { padding: 4 },
  bio: { fontSize: 12, color: COLORS.textSecondary, lineHeight: 17, marginBottom: 8 },
  cardActions: { flexDirection: 'row', gap: 16, borderTopWidth: 1, borderTopColor: COLORS.border, paddingTop: 8 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  actionText: { fontSize: 12, fontWeight: '600', color: COLORS.primary },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: COLORS.white, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, maxHeight: '80%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  inputLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 4, marginTop: 10 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.text, backgroundColor: '#FAFAFA' },
  saveBtn: { backgroundColor: COLORS.primary, paddingVertical: 14, borderRadius: 12, alignItems: 'center', marginTop: 16 },
  saveBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
});
