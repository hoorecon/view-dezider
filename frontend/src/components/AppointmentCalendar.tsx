import React, { useEffect, useMemo } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, Platform } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../constants/colors';

const DISPLAY_FONT = Platform.OS === 'web' ? 'Fraunces, Georgia, "Times New Roman", serif' : undefined;

function pad(n: number) {
  return String(n).padStart(2, '0');
}

function todayKey() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function dateKey(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function splitValue(value: string) {
  const [datePart, timePart] = (value || '').split('T');
  const [hourRaw, minuteRaw] = (timePart || '09:00').split(':');
  const hour = Math.min(23, Math.max(0, parseInt(hourRaw, 10) || 0));
  const minute = Math.min(59, Math.max(0, parseInt(minuteRaw, 10) || 0));
  const date = /^\d{4}-\d{2}-\d{2}$/.test(datePart || '') ? datePart : todayKey();
  return { date, hour, minute };
}

function joinValue(date: string, hour: number, minute: number) {
  return `${date}T${pad(hour)}:${pad(minute)}`;
}

const SLOT_START_HOUR = 8;
const SLOT_END_HOUR = 23;

function slots() {
  const items: { hour: number; minute: number; label: string }[] = [];
    for (let hour = SLOT_START_HOUR; hour <= SLOT_END_HOUR; hour += 1) {
    for (const minute of [0, 30]) {
      if (hour === SLOT_END_HOUR && minute > 30) continue;
      const sample = new Date();
      sample.setHours(hour, minute, 0, 0);
      items.push({
        hour,
        minute,
        label: sample.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' }),
      });
    }
  }
  return items;
}

const TIME_SLOTS = slots();

interface AppointmentCalendarProps {
  value: string;
  onChange: (value: string) => void;
  bookedDates?: string[];
}

/** Next three weeks as day chips, with half-hour time slots underneath. */
export default function AppointmentCalendar({ value, onChange, bookedDates = [] }: AppointmentCalendarProps) {
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    if (document.getElementById('jelcos-web-fonts')) return;
    const font = document.createElement('link');
    font.id = 'jelcos-web-fonts';
    font.rel = 'stylesheet';
    font.href = 'https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500..800;1,9..144,500..800&display=swap';
    document.head.appendChild(font);
  }, []);

  const { date, hour, minute } = splitValue(value);
  const booked = useMemo(() => new Set(bookedDates), [bookedDates]);
  const days = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    return Array.from({ length: 21 }, (_, index) => {
      const day = new Date(start);
      day.setDate(start.getDate() + index);
      return day;
    });
  }, []);
  const selected = days.find((day) => dateKey(day) === date) || days[0];
  const monthLabel = selected.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  const cutoff = Date.now() + 15 * 60 * 1000;

  return (
    <View style={styles.card}>
      <LinearGradient colors={GRADIENTS.primary} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.banner}>
        <Text style={styles.bannerKicker}>Choose a day</Text>
        <Text style={styles.month}>{monthLabel}</Text>
      </LinearGradient>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.days}>
        {days.map((day) => {
          const key = dateKey(day);
          const active = key === date;
          return (
            <TouchableOpacity
              key={key}
              style={[styles.day, active && styles.dayActive]}
              onPress={() => onChange(joinValue(key, hour, minute))}
            >
              <Text style={[styles.weekday, active && styles.dayTextActive]}>
                {day.toLocaleDateString(undefined, { weekday: 'short' })}
              </Text>
              <Text style={[styles.dayNum, active && styles.dayTextActive]}>{day.getDate()}</Text>
              {booked.has(key) ? <View style={[styles.dot, active && styles.dotActive]} /> : <View style={styles.dotSpacer} />}
            </TouchableOpacity>
          );
        })}
      </ScrollView>
      <Text style={styles.timeLabel}>Time</Text>
      <View style={styles.slots}>
        {TIME_SLOTS.map((slot) => {
          const when = new Date(`${date}T${pad(slot.hour)}:${pad(slot.minute)}`);
          const disabled = Number.isNaN(when.getTime()) || when.getTime() < cutoff;
          const active = slot.hour === hour && slot.minute === minute;
          return (
            <TouchableOpacity
              key={slot.label}
              disabled={disabled}
              style={[styles.slot, active && styles.slotActive, disabled && styles.slotDisabled]}
              onPress={() => onChange(joinValue(date, slot.hour, slot.minute))}
            >
              <Text style={[styles.slotText, active && styles.slotTextActive, disabled && styles.slotTextDisabled]}>
                {slot.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
      <Text style={styles.hint}>A dot marks a day that already has a meeting. Times are local, and must be at least 15 minutes ahead.</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderColor: '#E8DCF3',
    borderRadius: 16,
    backgroundColor: COLORS.white,
    overflow: 'hidden',
  },
  banner: { paddingHorizontal: 16, paddingVertical: 14 },
  bannerKicker: { fontSize: 13, fontWeight: '500', color: 'rgba(255,255,255,0.85)' },
  month: {
    fontSize: 22,
    fontWeight: '800',
    color: COLORS.white,
    letterSpacing: -0.4,
    fontFamily: DISPLAY_FONT,
    marginTop: 2,
  },
  days: { gap: 8, paddingHorizontal: 12, paddingTop: 12 },
  day: {
    width: 52,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    alignItems: 'center',
    paddingVertical: 8,
    backgroundColor: '#F1F5F9',
  },
  dayActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  weekday: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '600' },
  dayNum: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 2 },
  dayTextActive: { color: COLORS.white },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: COLORS.accent, marginTop: 4 },
  dotActive: { backgroundColor: COLORS.white },
  dotSpacer: { width: 6, height: 6, marginTop: 4 },
  timeLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginTop: 12, marginHorizontal: 12 },
  slots: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingHorizontal: 12, paddingTop: 8 },
  slot: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    backgroundColor: '#F1F5F9',
  },
  slotActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  slotDisabled: { backgroundColor: COLORS.divider },
  slotText: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  slotTextActive: { color: COLORS.white },
  slotTextDisabled: { color: COLORS.textMuted },
  hint: { fontSize: 11, color: COLORS.textMuted, fontStyle: 'italic', padding: 12 },
});
