import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../src/constants/colors';
import api from '../../../src/utils/api';
import { showAlert } from '../../../src/utils/alert';

const TYPES = [
  { code: 'service', label: 'Service Issue', icon: 'business' },
  { code: 'scheme', label: 'Scheme Problem', icon: 'document-text' },
  { code: 'local_problem', label: 'Local Problem', icon: 'location' },
  { code: 'department_experience', label: 'Department Experience', icon: 'people' },
  { code: 'policy_suggestion', label: 'Policy Suggestion', icon: 'bulb' },
];

const STATUS_LABEL: Record<string, string> = {
  new: 'New', acknowledged: 'Acknowledged', responded: 'Responded',
  action_pending: 'Action Pending', action_taken: 'Action Taken',
  resolution_review: 'Resolution Review', closed: 'Closed', reopened: 'Reopened',
};

const STATUS_COLOR: Record<string, string> = {
  new: '#3B82F6', acknowledged: '#F59E0B', responded: '#8B5CF6',
  action_pending: '#F97316', action_taken: '#10B981',
  resolution_review: '#06B6D4', closed: '#6B7280', reopened: '#EF4444',
};

export default function FeedbackScreen() {
  const router = useRouter();
  const [type, setType] = useState('service');
  const [text, setText] = useState('');
  const [district, setDistrict] = useState('');
  const [entity, setEntity] = useState('');
  const [severity, setSeverity] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await api.get('/public-pulse/feedback/me');
      setItems(res.data.items || []);
    } catch {} finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const submit = async () => {
    if (!text.trim()) {
      showAlert('Required', 'Please describe your feedback');
      return;
    }
    setSubmitting(true);
    try {
      await api.post('/public-pulse/feedback', {
        feedback_text: text,
        feedback_type: type,
        related_entity: entity || undefined,
        district: district || undefined,
        severity,
      });
      setText(''); setEntity(''); setDistrict(''); setSeverity(3);
      showAlert('Submitted', 'Thank you. Your feedback helps improve services for everyone.');
      load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to submit');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={28} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Feedback & Issues</Text>
          <View style={{ width: 28 }} />
        </View>

        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          {/* Type selector */}
          <Text style={styles.label}>Type</Text>
          <View style={styles.typeRow}>
            {TYPES.map((t) => {
              const sel = type === t.code;
              return (
                <TouchableOpacity
                  key={t.code}
                  style={[styles.typeBtn, sel && styles.typeBtnSel]}
                  onPress={() => setType(t.code)}
                >
                  <Ionicons name={t.icon as any} size={18} color={sel ? '#FFF' : COLORS.primary} />
                  <Text style={[styles.typeTxt, sel && { color: '#FFF' }]}>{t.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {/* District */}
          <Text style={styles.label}>District / Location (optional)</Text>
          <TextInput style={styles.input} value={district} onChangeText={setDistrict} placeholder="e.g., Coimbatore" placeholderTextColor="#9CA3AF" />

          {/* Related entity */}
          <Text style={styles.label}>Related to (department / scheme name, optional)</Text>
          <TextInput style={styles.input} value={entity} onChangeText={setEntity} placeholder="e.g., Revenue Dept, PMAY" placeholderTextColor="#9CA3AF" />

          {/* Description */}
          <Text style={styles.label}>Describe the issue / suggestion</Text>
          <TextInput
            style={[styles.input, { minHeight: 120, textAlignVertical: 'top' }]}
            value={text} onChangeText={setText}
            placeholder="Be specific. The more clearly you describe it, the easier it is to act on."
            placeholderTextColor="#9CA3AF"
            multiline
          />

          {/* Severity */}
          <Text style={styles.label}>Severity (1-5)</Text>
          <View style={styles.severityRow}>
            {[1, 2, 3, 4, 5].map((n) => {
              const sel = severity === n;
              return (
                <TouchableOpacity
                  key={n}
                  style={[styles.sevDot, sel && styles.sevDotSel]}
                  onPress={() => setSeverity(n)}
                >
                  <Text style={[styles.sevTxt, sel && { color: '#FFF' }]}>{n}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <TouchableOpacity style={styles.submitBtn} onPress={submit} disabled={submitting}>
            {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={styles.submitTxt}>Submit Feedback</Text>}
          </TouchableOpacity>

          {/* My past feedback */}
          {items.length > 0 && (
            <>
              <Text style={[styles.label, { marginTop: 28 }]}>My Past Feedback</Text>
              {items.map((it) => (
                <View key={it.feedback_id} style={styles.itemCard}>
                  <View style={styles.itemHead}>
                    <View style={[styles.statusPill, { backgroundColor: `${STATUS_COLOR[it.status]}20` }]}>
                      <Text style={[styles.statusTxt, { color: STATUS_COLOR[it.status] }]}>
                        {STATUS_LABEL[it.status] || it.status}
                      </Text>
                    </View>
                    <Text style={styles.itemDate}>{new Date(it.created_at).toLocaleDateString()}</Text>
                  </View>
                  <Text style={styles.itemTxt} numberOfLines={3}>{it.feedback_text}</Text>
                  {it.related_entity && (
                    <Text style={styles.itemEntity}>Related to: {it.related_entity}</Text>
                  )}
                  {it.response_text && (
                    <View style={styles.responseBox}>
                      <Text style={styles.responseLabel}>Response:</Text>
                      <Text style={styles.responseTxt}>{it.response_text}</Text>
                    </View>
                  )}
                </View>
              ))}
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  label: { fontSize: 13, fontWeight: '600', color: COLORS.text, marginTop: 16, marginBottom: 8 },
  input: {
    backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E5E7EB',
    borderRadius: 10, padding: 12, fontSize: 14, color: COLORS.text,
  },
  typeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  typeBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20,
    backgroundColor: '#FFF', borderWidth: 1, borderColor: '#D1D5DB',
  },
  typeBtnSel: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  typeTxt: { fontSize: 12, color: COLORS.text, fontWeight: '600' },
  severityRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  sevDot: { width: 50, height: 50, borderRadius: 25, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#D1D5DB', alignItems: 'center', justifyContent: 'center' },
  sevDotSel: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  sevTxt: { fontSize: 16, fontWeight: '700', color: COLORS.text },
  submitBtn: { backgroundColor: COLORS.primary, padding: 16, borderRadius: 12, alignItems: 'center', marginTop: 24 },
  submitTxt: { color: '#FFF', fontSize: 15, fontWeight: '700' },
  itemCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 14, marginBottom: 10 },
  itemHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  statusPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  statusTxt: { fontSize: 11, fontWeight: '700' },
  itemDate: { fontSize: 11, color: '#9CA3AF' },
  itemTxt: { fontSize: 13, color: '#374151', lineHeight: 19 },
  itemEntity: { fontSize: 11, color: '#6B7280', marginTop: 6, fontStyle: 'italic' },
  responseBox: { backgroundColor: '#F9FAFB', padding: 10, borderRadius: 8, marginTop: 10 },
  responseLabel: { fontSize: 11, fontWeight: '700', color: COLORS.primary },
  responseTxt: { fontSize: 13, color: '#374151', marginTop: 4 },
});
