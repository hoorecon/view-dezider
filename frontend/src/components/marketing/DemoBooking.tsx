/**
 * Book-a-demo block used on the landing page.
 * Submitting opens a real email to the support address.
 */
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, Linking, useWindowDimensions, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { GRADIENTS } from '../../constants/colors';
import { useCompany } from '../../contexts/FontFamilyContext';

const accentGradient = GRADIENTS.accent as unknown as readonly [string, string];
const MODULES = ['My Dezider', 'Pros & Cons', 'SWOT', 'Action Center', 'Life-Area Balance', 'Full walkthrough'];

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const WEEKDAYS = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
const SLOTS = Array.from({ length: 16 }, (_, i) => 10 * 60 + i * 30);

const nowIST = () => {
  const d = new Date(Date.now() + 330 * 60000);
  return { y: d.getUTCFullYear(), m: d.getUTCMonth(), d: d.getUTCDate(), minutes: d.getUTCHours() * 60 + d.getUTCMinutes() };
};
const dayKey = (y: number, m: number, d: number) => y * 10000 + m * 100 + d;
const pad = (n: number) => String(n).padStart(2, '0');
const slotLabel = (mins: number) => {
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${((h + 11) % 12) + 1}:${pad(m)} ${h < 12 ? 'AM' : 'PM'}`;
};

export default function DemoBooking() {
  const company = useCompany();
  const { width } = useWindowDimensions();
  const split = width >= 980;
  const [name, setName] = React.useState('');
  const [email, setEmail] = React.useState('');
  const [service, setService] = React.useState('');
  const [openList, setOpenList] = React.useState(false);
  const [date, setDate] = React.useState<{ y: number; m: number; d: number } | null>(null);
  const [time, setTime] = React.useState<number | null>(null);
  const [picker, setPicker] = React.useState<'date' | 'time' | null>(null);
  const today = nowIST();
  const [view, setView] = React.useState({ y: today.y, m: today.m });

  const openSaturday = /sat/i.test(company.supportHours || '');
  const todayKey = dayKey(today.y, today.m, today.d);
  const isToday = !!date && dayKey(date.y, date.m, date.d) === todayKey;
  const slotPast = (mins: number) => isToday && mins <= today.minutes + 30;
  const dateLabel = date
    ? `${new Date(Date.UTC(date.y, date.m, date.d)).toLocaleDateString('en-IN', { weekday: 'short', timeZone: 'UTC' })}, ${date.d} ${MONTHS[date.m].slice(0, 3)} ${date.y}`
    : '';

  const lead = (new Date(Date.UTC(view.y, view.m, 1)).getUTCDay() + 6) % 7;
  const daysInMonth = new Date(Date.UTC(view.y, view.m + 1, 0)).getUTCDate();
  const cells: (number | null)[] = [...Array(lead).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];
  while (cells.length % 7) cells.push(null);
  const canPrev = view.y > today.y || view.m > today.m;
  const shiftMonth = (by: number) => setView((v) => {
    const t = new Date(Date.UTC(v.y, v.m + by, 1));
    return { y: t.getUTCFullYear(), m: t.getUTCMonth() };
  });

  const pickDate = (d: number) => {
    const next = { y: view.y, m: view.m, d };
    setDate(next);
    if (time !== null && dayKey(next.y, next.m, next.d) === todayKey && time <= today.minutes + 30) setTime(null);
    setPicker('time');
  };
  const [message, setMessage] = React.useState('');
  const [error, setError] = React.useState('');
  const [sent, setSent] = React.useState(false);

  const submit = () => {
    if (!name.trim() || !email.trim() || !email.includes('@')) {
      setError('Add your name and a real email so we know who to reply to.');
      setSent(false);
      return;
    }
    setError('');
    const body = [
      `Name: ${name.trim()}`,
      `Email: ${email.trim()}`,
      `Module: ${service || 'Not chosen'}`,
      `Preferred date: ${dateLabel || 'Not chosen'}`,
      `Preferred time (IST): ${time !== null ? slotLabel(time) : 'Not chosen'}`,
      '',
      message.trim() || 'No note added.',
    ].join('\n');
    Linking.openURL(`mailto:${company.email}?subject=${encodeURIComponent(`Demo request · ${name.trim()}`)}&body=${encodeURIComponent(body)}`);
    setSent(true);
  };

  return (
    <View nativeID="demo" collapsable={false} style={styles.root}>
      <View style={[styles.stage, split && styles.stageSplit]}>
        <View style={[styles.copy, split && { flex: 1 }]}>
          <View style={styles.eyebrow}>
            <Text style={styles.eyebrowText}>LET'S LOOK AT A REAL DECISION</Text>
          </View>
          <Text style={styles.h1}>
            Book a demo{'\n'}
            <Text style={styles.h1Accent}>of the modules</Text>
            {'\n'}you will actually use.
          </Text>
          <Text style={styles.lead}>
            A career choice, a purchase, or the module you already have in mind. Share the brief and {company.product} will walk through it with you.
          </Text>
          <View style={styles.infoRow}>
            <TouchableOpacity style={styles.infoCard} onPress={() => Linking.openURL(`mailto:${company.email}`)}>
              <View style={styles.infoIcon}>
                <Ionicons name="mail" size={18} color="#FFFFFF" />
              </View>
              <Text style={styles.infoLabel}>EMAIL US</Text>
              <Text style={styles.infoValue}>{company.email}</Text>
            </TouchableOpacity>
            <View style={styles.infoCard}>
              <View style={styles.infoIcon}>
                <Ionicons name="location" size={18} color="#FFFFFF" />
              </View>
              <Text style={styles.infoLabel}>HEADQUARTERS</Text>
              <Text style={styles.infoValue}>Chennai, India</Text>
            </View>
          </View>
        </View>

        <View style={[styles.formCard, split && { flex: 1.05 }]}>
          <View style={styles.fieldRow}>
            <View style={styles.field}>
              <Text style={styles.label}>NAME *</Text>
              <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Your name" placeholderTextColor="rgba(255,255,255,0.35)" />
            </View>
            <View style={styles.field}>
              <Text style={styles.label}>EMAIL *</Text>
              <TextInput style={styles.input} value={email} onChangeText={setEmail} placeholder="you@company.com" placeholderTextColor="rgba(255,255,255,0.35)" autoCapitalize="none" keyboardType="email-address" />
            </View>
          </View>

          <Text style={styles.label}>INTERESTED MODULE</Text>
          <TouchableOpacity style={styles.input} onPress={() => setOpenList((v) => !v)}>
            <Text style={[styles.inputText, !service && { color: 'rgba(255,255,255,0.35)' }]}>{service || 'Select a module…'}</Text>
          </TouchableOpacity>
          {openList && (
            <View style={styles.menu}>
              {MODULES.map((item) => (
                <TouchableOpacity key={item} style={styles.menuItem} onPress={() => { setService(item); setOpenList(false); }}>
                  <Text style={styles.menuText}>{item}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

          <View style={styles.fieldRow}>
            <View style={styles.field}>
              <Text style={styles.label}>PREFERRED DATE</Text>
              <TouchableOpacity style={[styles.input, styles.pickField, picker === 'date' && styles.pickFieldOn]} onPress={() => setPicker((p) => (p === 'date' ? null : 'date'))}>
                <Ionicons name="calendar-outline" size={17} color={date ? '#F48FB1' : 'rgba(255,255,255,0.45)'} />
                <Text style={[styles.inputText, { flex: 1 }, !date && styles.placeholder]} numberOfLines={1}>{dateLabel || 'Pick a date'}</Text>
                <Ionicons name={picker === 'date' ? 'chevron-up' : 'chevron-down'} size={16} color="rgba(255,255,255,0.5)" />
              </TouchableOpacity>
            </View>
            <View style={styles.field}>
              <Text style={styles.label}>PREFERRED TIME (IST)</Text>
              <TouchableOpacity style={[styles.input, styles.pickField, picker === 'time' && styles.pickFieldOn]} onPress={() => setPicker((p) => (p === 'time' ? null : 'time'))}>
                <Ionicons name="time-outline" size={17} color={time !== null ? '#F48FB1' : 'rgba(255,255,255,0.45)'} />
                <Text style={[styles.inputText, { flex: 1 }, time === null && styles.placeholder]} numberOfLines={1}>{time !== null ? `${slotLabel(time)} IST` : 'Pick a time'}</Text>
                <Ionicons name={picker === 'time' ? 'chevron-up' : 'chevron-down'} size={16} color="rgba(255,255,255,0.5)" />
              </TouchableOpacity>
            </View>
          </View>

          {picker === 'date' && (
            <View style={styles.panel}>
              <View style={styles.calHead}>
                <TouchableOpacity disabled={!canPrev} onPress={() => shiftMonth(-1)} style={[styles.calNav, !canPrev && { opacity: 0.3 }]}>
                  <Ionicons name="chevron-back" size={16} color="#FFFFFF" />
                </TouchableOpacity>
                <Text style={styles.calTitle}>{MONTHS[view.m]} {view.y}</Text>
                <TouchableOpacity onPress={() => shiftMonth(1)} style={styles.calNav}>
                  <Ionicons name="chevron-forward" size={16} color="#FFFFFF" />
                </TouchableOpacity>
              </View>
              <View style={styles.calGrid}>
                {WEEKDAYS.map((w) => (
                  <Text key={w} style={[styles.calCell, styles.calWeekday]}>{w}</Text>
                ))}
                {cells.map((d, i) => {
                  if (d === null) return <View key={`e${i}`} style={styles.calCell} />;
                  const key = dayKey(view.y, view.m, d);
                  const closed = i % 7 === 6 || (i % 7 === 5 && !openSaturday);
                  const off = key < todayKey || closed;
                  const on = !!date && key === dayKey(date.y, date.m, date.d);
                  return (
                    <TouchableOpacity key={key} disabled={off} onPress={() => pickDate(d)} style={styles.calCell}>
                      <View style={[styles.calDay, key === todayKey && styles.calToday, on && styles.calDayOn]}>
                        <Text style={[styles.calDayText, off && styles.calDayOff, on && { color: '#FFFFFF' }]}>{d}</Text>
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </View>
              <Text style={styles.panelHint}>Demos run Monday to {openSaturday ? 'Saturday' : 'Friday'}. Past dates are unavailable.</Text>
            </View>
          )}

          {picker === 'time' && (
            <View style={styles.panel}>
              <Text style={styles.panelTitle}>{date ? `Slots on ${dateLabel}` : 'Choose a 30-minute slot'}</Text>
              <View style={styles.slotGrid}>
                {SLOTS.map((mins) => {
                  const past = slotPast(mins);
                  const on = time === mins;
                  return (
                    <TouchableOpacity key={mins} disabled={past} onPress={() => { setTime(mins); setPicker(null); }} style={[styles.slot, on && styles.slotOn, past && { opacity: 0.3 }]}>
                      <Text style={[styles.slotText, on && { color: '#FFFFFF' }]}>{slotLabel(mins)}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
              <Text style={styles.panelHint}>All times are India Standard Time (IST).</Text>
            </View>
          )}

          <Text style={styles.label}>MESSAGE</Text>
          <TextInput
            style={[styles.input, styles.area]}
            value={message}
            onChangeText={setMessage}
            placeholder="Which decision do you want to walk through?"
            placeholderTextColor="rgba(255,255,255,0.35)"
            multiline
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}
          {sent ? <Text style={styles.sent}>Your email app should open with this note addressed to {company.email}. Send it and we will reply in support hours.</Text> : null}

          <TouchableOpacity activeOpacity={0.9} onPress={submit} style={{ marginTop: 8 }}>
            <LinearGradient colors={accentGradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.submit}>
              <Ionicons name="paper-plane" size={16} color="#FFFFFF" />
              <Text style={styles.submitText}>Book your demo</Text>
            </LinearGradient>
          </TouchableOpacity>
          <Text style={styles.fine}>Support hours: {company.supportHours}. We reply from {company.email}.</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: '#0A1A4F', paddingTop: 72, paddingBottom: 24 },
  stage: { width: '100%', maxWidth: 1120, alignSelf: 'center', paddingHorizontal: 24, paddingTop: 18, paddingBottom: 48, gap: 28 },
  stageSplit: { flexDirection: 'row', alignItems: 'flex-start', gap: 36 },
  copy: { paddingTop: 12 },
  eyebrow: {
    alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6,
    backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.12)', marginBottom: 16,
  },
  eyebrowText: { color: 'rgba(255,255,255,0.72)', fontSize: 11, fontWeight: '800', letterSpacing: 1.1 },
  h1: { fontSize: 46, lineHeight: 52, fontWeight: '800', color: '#FFFFFF', letterSpacing: -1.2 },
  h1Accent: Platform.OS === 'web' ? {
    color: '#F48FB1',
    backgroundImage: 'linear-gradient(100deg, #F48FB1 0%, #CE93D8 55%, #9FA8DA 100%)',
    backgroundClip: 'text',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  } as any : { color: '#F48FB1' },
  lead: { fontSize: 15.5, lineHeight: 24, color: 'rgba(255,255,255,0.72)', marginTop: 16, maxWidth: 460 },
  infoRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 28 },
  infoCard: {
    flexGrow: 1, minWidth: 160, borderRadius: 18, padding: 16,
    backgroundColor: 'rgba(255,255,255,0.05)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
  },
  infoIcon: {
    width: 36, height: 36, borderRadius: 12, alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(142,36,170,0.45)', marginBottom: 12,
  },
  infoLabel: { fontSize: 11, fontWeight: '800', letterSpacing: 1, color: 'rgba(255,255,255,0.55)' },
  infoValue: { fontSize: 15, fontWeight: '700', color: '#FFFFFF', marginTop: 4 },
  formCard: {
    borderRadius: 28, padding: 22,
    backgroundColor: 'rgba(28, 22, 58, 0.92)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
    ...(Platform.OS === 'web' ? { boxShadow: '0 24px 60px rgba(0,0,0,0.35)' } as any : { elevation: 6 }),
  },
  fieldRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  field: { flexGrow: 1, flexBasis: 180 },
  label: { fontSize: 11, fontWeight: '800', letterSpacing: 0.8, color: 'rgba(255,255,255,0.55)', marginBottom: 8, marginTop: 12 },
  input: {
    borderRadius: 14, paddingHorizontal: 14, paddingVertical: 14,
    backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
    color: '#FFFFFF', fontSize: 15,
  },
  inputText: { color: '#FFFFFF', fontSize: 15 },
  placeholder: { color: 'rgba(255,255,255,0.35)' },
  pickField: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  pickFieldOn: { borderColor: '#E91E63', backgroundColor: 'rgba(233,30,99,0.08)' },
  panel: {
    marginTop: 10, borderRadius: 18, padding: 16,
    backgroundColor: '#14307D', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
  },
  panelTitle: { color: '#FFFFFF', fontSize: 14, fontWeight: '700', marginBottom: 12 },
  panelHint: { color: 'rgba(255,255,255,0.45)', fontSize: 12, marginTop: 12 },
  calHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  calNav: { width: 32, height: 32, borderRadius: 999, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.08)' },
  calTitle: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  calGrid: { flexDirection: 'row', flexWrap: 'wrap' },
  calCell: { width: `${100 / 7}%` as any, height: 40, alignItems: 'center', justifyContent: 'center' },
  calWeekday: { color: 'rgba(255,255,255,0.45)', fontSize: 11, fontWeight: '800', textAlign: 'center', lineHeight: 40 },
  calDay: { width: 34, height: 34, borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  calToday: { borderWidth: 1, borderColor: 'rgba(244,143,177,0.6)' },
  calDayOn: { backgroundColor: '#E91E63', borderColor: '#E91E63' },
  calDayText: { color: '#FFFFFF', fontSize: 13.5, fontWeight: '600' },
  calDayOff: { color: 'rgba(255,255,255,0.22)' },
  slotGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  slot: {
    flexGrow: 1, flexBasis: '22%', alignItems: 'center', paddingVertical: 10, borderRadius: 12,
    backgroundColor: 'rgba(255,255,255,0.05)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
  },
  slotOn: { backgroundColor: '#8E24AA', borderColor: '#CE93D8' },
  slotText: { color: 'rgba(255,255,255,0.85)', fontSize: 13, fontWeight: '700' },
  area: { minHeight: 110, textAlignVertical: 'top' },
  menu: {
    marginTop: 6, borderRadius: 14, overflow: 'hidden',
    backgroundColor: '#14307D', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)',
  },
  menuItem: { paddingHorizontal: 14, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.06)' },
  menuText: { color: '#FFFFFF', fontSize: 14, fontWeight: '600' },
  error: { color: '#F9A8D4', fontSize: 13, marginTop: 12 },
  sent: { color: 'rgba(255,255,255,0.8)', fontSize: 13, lineHeight: 20, marginTop: 12 },
  submit: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 999, paddingVertical: 14, marginTop: 8 },
  submitText: { color: '#FFFFFF', fontSize: 15, fontWeight: '800' },
  fine: { fontSize: 12, lineHeight: 18, color: 'rgba(255,255,255,0.45)', marginTop: 12, textAlign: 'center' },
});
