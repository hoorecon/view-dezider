/**
 * /tools/expert-net/[expert_id]  — Expert detail + booking + intake form
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, Modal, KeyboardAvoidingView, Platform, Linking,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../../src/utils/api';
import { COLORS } from '../../../src/constants/colors';
import { showAlert } from '../../../src/utils/alert';

interface IntakeField {
  field_id: string; label: string;
  field_type: 'short_text' | 'long_text' | 'single_select' | 'multi_select' | 'number' | 'file' | 'consent';
  required?: boolean; options?: string[]; helper?: string; placeholder?: string;
}

export default function ExpertDetailScreen() {
  const router = useRouter();
  const { expert_id } = useLocalSearchParams();
  const [expert, setExpert] = useState<any>(null);
  const [availability, setAvailability] = useState<any>(null);
  const [intake, setIntake] = useState<any>(null);
  const [slots, setSlots] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // booking flow
  const [showBook, setShowBook] = useState(false);
  const [pickedSlot, setPickedSlot] = useState<any | null>(null);
  const [intakeAnswers, setIntakeAnswers] = useState<Record<string, any>>({});
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!expert_id) return;
    try { setLoading(true);
      const [d, sl] = await Promise.all([
        api.get(`/expert-net/experts/${expert_id}`),
        api.get(`/expert-net/experts/${expert_id}/slots?days_ahead=14`),
      ]);
      setExpert(d.data?.expert || null);
      setAvailability(d.data?.availability || null);
      setIntake(d.data?.intake_form || null);
      setSlots(sl.data?.slots || []);
    } catch (e: any) { showAlert('Load error', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, [expert_id]);

  useEffect(() => { load(); }, [load]);

  const openBooking = (slot: any) => {
    setPickedSlot(slot);
    setIntakeAnswers({});
    setNote('');
    setShowBook(true);
  };

  const submitBooking = async () => {
    if (!pickedSlot) return;
    // validate intake
    if (intake && intake.mode === 'builtin' && intake.is_required_before_booking) {
      const missing = (intake.fields || []).find((f: IntakeField) => f.required && !intakeAnswers[f.field_id]);
      if (missing) return showAlert('Required field', `Please fill: ${missing.label}`);
    }
    try {
      setSubmitting(true);
      const payload: any = {
        expert_id,
        slot_start_iso: pickedSlot.start,
        duration_minutes: pickedSlot.duration_minutes,
        intake_response: intakeAnswers,
        note: note || undefined,
      };
      const res = await api.post('/expert-net/bookings', payload);
      const status = res.data?.status;
      const msg = status === 'pending'
        ? 'Booking placed. Awaiting expert confirmation (or payment if paid).'
        : 'Booking confirmed!';
      showAlert('Success', msg);
      setShowBook(false);
      load();
    } catch (e: any) {
      showAlert('Booking failed', e?.response?.data?.detail || e.message);
    } finally { setSubmitting(false); }
  };

  if (loading || !expert) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.center}><ActivityIndicator color={COLORS.primary} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>{expert.name}</Text>
        <View style={{ width: 22 }} />
      </View>

      <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 100 }}>
        {/* Expert header card */}
        <View style={styles.card}>
          <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
            <View style={styles.avatarLg}>
              <Text style={{ color: '#FFF', fontSize: 24, fontWeight: '700' }}>{(expert.name || 'E')[0]}</Text>
              {expert.is_online && <View style={styles.onlineDot} />}
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{expert.name}</Text>
              {expert.headline && <Text style={styles.headline}>{expert.headline}</Text>}
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                {expert.hourly_rate_inr ? <Text style={styles.tag}>₹{expert.hourly_rate_inr}/hr</Text> : <Text style={styles.tag}>Free intro</Text>}
                {expert.rating_avg ? <Text style={styles.tag}>★ {expert.rating_avg.toFixed(1)} ({expert.rating_count})</Text> : null}
                {expert.accepts_instant_calls && <Text style={[styles.tag, { backgroundColor: '#10B98122', color: '#059669' }]}>⚡ Instant</Text>}
              </View>
            </View>
          </View>
        </View>

        {expert.bio && (
          <View style={styles.card}>
            <Text style={styles.sectionH}>About</Text>
            <Text style={{ color: COLORS.textSecondary, fontSize: 13, lineHeight: 20 }}>{expert.bio}</Text>
          </View>
        )}

        {/* Specializations + languages */}
        {(expert.specializations?.length || expert.languages?.length) ? (
          <View style={styles.card}>
            {expert.specializations?.length ? (
              <>
                <Text style={styles.sectionH}>Specializations</Text>
                <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                  {expert.specializations.map((s: string) => <Text key={s} style={styles.tag}>{s}</Text>)}
                </View>
              </>
            ) : null}
            {expert.languages?.length ? (
              <>
                <Text style={styles.sectionH}>Languages</Text>
                <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
                  {expert.languages.map((l: string) => <Text key={l} style={styles.tag}>{l}</Text>)}
                </View>
              </>
            ) : null}
          </View>
        ) : null}

        {/* Slots */}
        <View style={styles.card}>
          <Text style={styles.sectionH}>Available slots (next 14 days)</Text>
          {slots.length === 0 ? (
            <Text style={{ color: COLORS.textMuted, fontSize: 12 }}>
              No available slots yet. Either the expert hasn't set their availability or all slots are booked.
            </Text>
          ) : (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
              {slots.slice(0, 24).map((s, i) => {
                const d = new Date(s.start);
                const label = `${d.toLocaleDateString(undefined, { weekday: 'short' })} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
                return (
                  <TouchableOpacity
                    key={i}
                    testID={`xn-slot-${i}`}
                    onPress={() => openBooking(s)}
                    style={styles.slotBtn}
                  >
                    <Text style={styles.slotText}>{label}</Text>
                    <Text style={styles.slotSubText}>{s.duration_minutes}m</Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}
        </View>

        {/* Intake preview */}
        {intake && (
          <View style={styles.card}>
            <Text style={styles.sectionH}>Pre-session intake</Text>
            <Text style={{ fontSize: 13, color: COLORS.textPrimary, fontWeight: '600' }}>{intake.title}</Text>
            {intake.description && <Text style={{ fontSize: 12, color: COLORS.textSecondary, marginTop: 4 }}>{intake.description}</Text>}
            <Text style={{ fontSize: 11, color: COLORS.textMuted, marginTop: 6 }}>
              Mode: {intake.mode}{intake.is_required_before_booking ? ' · required' : ' · optional'}
            </Text>
          </View>
        )}
      </ScrollView>

      {/* Booking modal */}
      <Modal visible={showBook} transparent animationType="slide" onRequestClose={() => setShowBook(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.overlay}>
          <View style={styles.sheet}>
            <Text style={styles.sheetTitle}>Confirm booking</Text>
            {pickedSlot && (
              <Text style={{ fontSize: 13, color: COLORS.textPrimary, marginBottom: 12 }}>
                {new Date(pickedSlot.start).toLocaleString()} · {pickedSlot.duration_minutes} min
              </Text>
            )}

            <ScrollView style={{ maxHeight: 380 }}>
              {/* Intake — built-in fields */}
              {intake?.mode === 'builtin' && (intake?.fields || []).map((f: IntakeField) => (
                <View key={f.field_id} style={{ marginBottom: 10 }}>
                  <Text style={styles.fieldLabel}>
                    {f.label}{f.required ? ' *' : ''}
                  </Text>
                  {f.field_type === 'short_text' || f.field_type === 'number' ? (
                    <TextInput
                      style={styles.input}
                      value={String(intakeAnswers[f.field_id] || '')}
                      onChangeText={v => setIntakeAnswers({ ...intakeAnswers, [f.field_id]: v })}
                      placeholder={f.placeholder || ''}
                      placeholderTextColor={COLORS.textMuted}
                      keyboardType={f.field_type === 'number' ? 'numeric' : 'default'}
                    />
                  ) : f.field_type === 'long_text' ? (
                    <TextInput
                      style={[styles.input, { minHeight: 70 }]}
                      multiline
                      value={String(intakeAnswers[f.field_id] || '')}
                      onChangeText={v => setIntakeAnswers({ ...intakeAnswers, [f.field_id]: v })}
                    />
                  ) : f.field_type === 'single_select' ? (
                    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                      {(f.options || []).map(opt => (
                        <TouchableOpacity
                          key={opt}
                          onPress={() => setIntakeAnswers({ ...intakeAnswers, [f.field_id]: opt })}
                          style={[
                            { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#F9FAFB' },
                            intakeAnswers[f.field_id] === opt && { backgroundColor: COLORS.primary + '22', borderColor: COLORS.primary },
                          ]}
                        >
                          <Text style={[{ fontSize: 12, color: COLORS.textSecondary }, intakeAnswers[f.field_id] === opt && { color: COLORS.primary, fontWeight: '700' }]}>{opt}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  ) : f.field_type === 'consent' ? (
                    <TouchableOpacity onPress={() => setIntakeAnswers({ ...intakeAnswers, [f.field_id]: !intakeAnswers[f.field_id] })} style={{ flexDirection: 'row', gap: 8, alignItems: 'center', marginTop: 4 }}>
                      <Ionicons name={intakeAnswers[f.field_id] ? 'checkbox' : 'square-outline'} size={20} color={intakeAnswers[f.field_id] ? COLORS.primary : COLORS.textMuted} />
                      <Text style={{ fontSize: 12, color: COLORS.textPrimary, flex: 1 }}>{f.helper || 'I consent'}</Text>
                    </TouchableOpacity>
                  ) : (
                    <Text style={{ fontSize: 11, color: COLORS.textMuted }}>(field type {f.field_type} — entry placeholder)</Text>
                  )}
                </View>
              ))}

              {/* Intake — external URL */}
              {intake?.mode === 'external' && intake?.external_url && (
                <View style={{ marginBottom: 12, padding: 10, backgroundColor: '#FEF3C7', borderRadius: 8, borderWidth: 1, borderColor: '#FCD34D' }}>
                  <Text style={{ fontSize: 12, color: '#92400E', fontWeight: '700' }}>Pre-session form</Text>
                  <Text style={{ fontSize: 11, color: '#92400E', marginTop: 2 }}>The expert will require this Google Form / Typeform completed before the session.</Text>
                  <TouchableOpacity onPress={() => Linking.openURL(intake.external_url)} style={[styles.btnSecondary, { marginTop: 8 }]}>
                    <Ionicons name="open" size={14} color={COLORS.primary} />
                    <Text style={[styles.btnSecondaryText, { color: COLORS.primary }]}> Open form</Text>
                  </TouchableOpacity>
                </View>
              )}

              <Text style={styles.fieldLabel}>Note to expert (optional)</Text>
              <TextInput
                style={[styles.input, { minHeight: 60 }]}
                multiline
                value={note}
                onChangeText={setNote}
                placeholder="Anything else they should know?"
                placeholderTextColor={COLORS.textMuted}
              />
            </ScrollView>

            <View style={{ flexDirection: 'row', gap: 8, marginTop: 14 }}>
              <TouchableOpacity style={[styles.btnSecondary, { flex: 1 }]} onPress={() => setShowBook(false)}>
                <Text style={styles.btnSecondaryText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                testID="xn-confirm-booking"
                style={[styles.btnPrimary, { flex: 1, opacity: submitting ? 0.6 : 1 }]}
                disabled={submitting}
                onPress={submitBooking}
              >
                {submitting ? <ActivityIndicator color="#FFF" /> :
                  <Text style={styles.btnPrimaryText}>Confirm</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 12, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary, flex: 1, marginHorizontal: 10 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  card: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  avatarLg: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center', backgroundColor: '#7C3AED', position: 'relative' },
  onlineDot: { position: 'absolute', bottom: 2, right: 2, width: 14, height: 14, borderRadius: 7, backgroundColor: '#10B981', borderWidth: 2, borderColor: '#FFF' },
  name: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  headline: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  tag: { fontSize: 11, color: COLORS.textSecondary, paddingHorizontal: 8, paddingVertical: 3, backgroundColor: '#F3F4F6', borderRadius: 4 },
  sectionH: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  slotBtn: { paddingHorizontal: 10, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: COLORS.primary, backgroundColor: '#EFF6FF', alignItems: 'center', minWidth: 80 },
  slotText: { fontSize: 12, fontWeight: '700', color: COLORS.primary },
  slotSubText: { fontSize: 10, color: COLORS.textMuted, marginTop: 1 },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '90%' },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  fieldLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 8 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white, marginTop: 4 },
  btnPrimary: { backgroundColor: COLORS.primary, paddingVertical: 12, paddingHorizontal: 12, borderRadius: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  btnPrimaryText: { color: '#FFF', fontSize: 14, fontWeight: '700' },
  btnSecondary: { paddingVertical: 12, paddingHorizontal: 12, borderRadius: 8, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white, flexDirection: 'row', gap: 6 },
  btnSecondaryText: { color: COLORS.textPrimary, fontSize: 14, fontWeight: '600' },
});
