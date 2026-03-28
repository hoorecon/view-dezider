import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert, TextInput,
  Switch, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const AWARENESS_LEVELS = [
  { level: 1, name: 'Thought Level', icon: 'bulb', color: '#818CF8', desc: 'Awareness of thoughts' },
  { level: 2, name: 'Breath Level', icon: 'leaf', color: '#3B82F6', desc: 'Awareness of breathing' },
  { level: 3, name: 'Bodily Sensations', icon: 'body', color: '#10B981', desc: 'Awareness of body signals' },
  { level: 4, name: 'Individual Action', icon: 'flash', color: '#F59E0B', desc: 'Auto-calculated from diary' },
  { level: 5, name: 'Interaction Level', icon: 'people', color: '#EC4899', desc: 'Awareness in social contexts' },
  { level: 6, name: 'Intense Action', icon: 'flame', color: '#EF4444', desc: 'Awareness under pressure' },
];

export default function ConsciousnessDiaryScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'diary' | 'awareness' | 'wellness'>('diary');
  const [todayDate] = useState(new Date().toISOString().split('T')[0]);
  const [entry, setEntry] = useState<any>(null);
  const [dailyContext, setDailyContext] = useState<any>(null);
  const [selfAwareness, setSelfAwareness] = useState<any>(null);
  const [wellness, setWellness] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);

  // Form state for diary entry
  const [form, setForm] = useState({
    anger: { count: 0, avg_duration_mins: 0, avg_intensity: 0 },
    sadness: { count: 0, avg_duration_mins: 0, avg_intensity: 0 },
    fear: { count: 0, avg_duration_mins: 0, avg_intensity: 0 },
    emotional_outlets: { time_impact_pct: 0, money_impact_pct: 0, health_impact_pct: 0, relationships_impact_pct: 0 },
    ads: { time_impact_pct: 0, money_impact_pct: 0, health_impact_pct: 0, relationships_impact_pct: 0 },
    sit_still: { achieved: false, comfort_score: 5 },
    peacefulness: { peaceful_hours: 0, depth_score: 5 },
    solution_leadership: { problems_with_solutions: 0, problems_without_solutions: 0 },
    overall_reflection: '',
  });

  // Self-awareness ratings
  const [saRatings, setSaRatings] = useState<Record<string, number>>({
    '1': 5, '2': 5, '3': 5, '5': 5, '6': 5,
  });

  const fetchAll = async () => {
    try {
      const [entryRes, saRes, wellRes, histRes] = await Promise.all([
        api.get(`/consciousness-diary/entries?date=${todayDate}`),
        api.get('/consciousness-diary/self-awareness'),
        api.get('/consciousness-diary/emotional-wellness?days=7'),
        api.get('/consciousness-diary/history?days=14'),
      ]);

      const data = entryRes.data;
      setEntry(data.entry);
      setDailyContext(data.daily_context);

      if (data.entry) {
        const m = data.entry.metrics || {};
        setForm({
          anger: m.anger || { count: 0, avg_duration_mins: 0, avg_intensity: 0 },
          sadness: m.sadness || { count: 0, avg_duration_mins: 0, avg_intensity: 0 },
          fear: m.fear || { count: 0, avg_duration_mins: 0, avg_intensity: 0 },
          emotional_outlets: m.emotional_outlets || { time_impact_pct: 0, money_impact_pct: 0, health_impact_pct: 0, relationships_impact_pct: 0 },
          ads: m.ads || { time_impact_pct: 0, money_impact_pct: 0, health_impact_pct: 0, relationships_impact_pct: 0 },
          sit_still: m.sit_still || { achieved: false, comfort_score: 5 },
          peacefulness: m.peacefulness || { peaceful_hours: 0, depth_score: 5 },
          solution_leadership: m.solution_leadership || { problems_with_solutions: 0, problems_without_solutions: 0 },
          overall_reflection: data.entry.overall_reflection || '',
        });
      }

      setSelfAwareness(saRes.data);
      if (saRes.data?.levels) {
        const ratings: Record<string, number> = {};
        for (const k of ['1', '2', '3', '5', '6']) {
          ratings[k] = saRes.data.levels[k]?.score || 5;
        }
        setSaRatings(ratings);
      }

      setWellness(wellRes.data);
      setHistory(histRes.data?.entries || []);
    } catch (e) {
      console.error('Fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchAll(); }, []));
  const onRefresh = async () => { setRefreshing(true); await fetchAll(); setRefreshing(false); };

  const saveDiaryEntry = async () => {
    setSaving(true);
    try {
      await api.post('/consciousness-diary/entries', {
        date: todayDate,
        ...form,
      });
      Alert.alert('Saved', 'Diary entry saved successfully');
      fetchAll();
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const saveSelfAwareness = async () => {
    setSaving(true);
    try {
      const levels: Record<string, any> = {};
      for (const [k, v] of Object.entries(saRatings)) {
        levels[k] = { score: v };
      }
      await api.put('/consciousness-diary/self-awareness', { levels });
      Alert.alert('Saved', 'Self-awareness levels updated');
      fetchAll();
    } catch (e: any) {
      Alert.alert('Error', 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const updateNum = (section: string, field: string, val: string) => {
    const num = parseFloat(val) || 0;
    setForm((prev: any) => ({
      ...prev,
      [section]: { ...prev[section], [field]: num },
    }));
  };

  if (loading) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.loadWrap}><ActivityIndicator size="large" color="#818CF8" /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#1E1B4B', '#312E81', '#3730A3']} style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Consciousness Diary</Text>
          <Text style={s.headerSub}>Inner Self-Awareness & Emotional Tracking</Text>
        </View>
      </LinearGradient>

      {/* Tab Switcher */}
      <View style={s.tabRow}>
        {(['diary', 'awareness', 'wellness'] as const).map(tab => (
          <TouchableOpacity
            key={tab}
            style={[s.tab, activeTab === tab && s.tabActive]}
            onPress={() => setActiveTab(tab)}
          >
            <Ionicons
              name={tab === 'diary' ? 'journal' : tab === 'awareness' ? 'eye' : 'heart'}
              size={16}
              color={activeTab === tab ? '#FFF' : COLORS.textMuted}
            />
            <Text style={[s.tabText, activeTab === tab && s.tabTextActive]}>
              {tab === 'diary' ? 'Daily Diary' : tab === 'awareness' ? 'Self Awareness' : 'Wellness'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <ScrollView
          style={s.scroll}
          contentContainerStyle={s.scrollContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {activeTab === 'diary' && (
            <DiaryTab
              form={form}
              setForm={setForm}
              updateNum={updateNum}
              dailyContext={dailyContext}
              todayDate={todayDate}
              saving={saving}
              onSave={saveDiaryEntry}
              history={history}
              hasEntry={!!entry}
            />
          )}
          {activeTab === 'awareness' && (
            <AwarenessTab
              selfAwareness={selfAwareness}
              saRatings={saRatings}
              setSaRatings={setSaRatings}
              saving={saving}
              onSave={saveSelfAwareness}
            />
          )}
          {activeTab === 'wellness' && (
            <WellnessTab wellness={wellness} history={history} />
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ========================
// DIARY TAB
// ========================
function DiaryTab({ form, setForm, updateNum, dailyContext, todayDate, saving, onSave, history, hasEntry }: any) {
  return (
    <View>
      <Text style={s.dateLabel}>{todayDate} {hasEntry ? '(Saved)' : '(New)'}</Text>

      {/* Daily Context */}
      {dailyContext && (
        <View style={s.contextCard}>
          <Text style={s.contextTitle}>Today's Context</Text>
          <View style={s.contextRow}>
            <View style={s.contextItem}>
              <Ionicons name="clipboard" size={18} color="#3B82F6" />
              <Text style={s.contextNum}>{dailyContext.tasks_count}</Text>
              <Text style={s.contextLabel}>Tasks</Text>
            </View>
            <View style={s.contextItem}>
              <Ionicons name="repeat" size={18} color="#10B981" />
              <Text style={s.contextNum}>{dailyContext.routines_count}</Text>
              <Text style={s.contextLabel}>Routines</Text>
            </View>
            <View style={s.contextItem}>
              <Ionicons name="flash" size={18} color="#F59E0B" />
              <Text style={s.contextNum}>{dailyContext.unplanned_count}</Text>
              <Text style={s.contextLabel}>Unplanned</Text>
            </View>
          </View>
        </View>
      )}

      {/* 1. Anger */}
      <MetricSection
        title="1. Anger Incidents"
        icon="flame"
        color="#EF4444"
        fields={[
          { label: 'Times today', key: 'count', value: form.anger.count },
          { label: 'Avg Duration (min)', key: 'avg_duration_mins', value: form.anger.avg_duration_mins },
          { label: 'Avg Intensity (0-10)', key: 'avg_intensity', value: form.anger.avg_intensity },
        ]}
        onUpdate={(k: string, v: string) => updateNum('anger', k, v)}
      />

      {/* 2. Sadness */}
      <MetricSection
        title="2. Sadness Incidents"
        icon="sad"
        color="#3B82F6"
        fields={[
          { label: 'Times today', key: 'count', value: form.sadness.count },
          { label: 'Avg Duration (min)', key: 'avg_duration_mins', value: form.sadness.avg_duration_mins },
          { label: 'Avg Intensity (0-10)', key: 'avg_intensity', value: form.sadness.avg_intensity },
        ]}
        onUpdate={(k: string, v: string) => updateNum('sadness', k, v)}
      />

      {/* 3. Fear */}
      <MetricSection
        title="3. Fear Incidents"
        icon="alert-circle"
        color="#8B5CF6"
        fields={[
          { label: 'Times today', key: 'count', value: form.fear.count },
          { label: 'Avg Duration (min)', key: 'avg_duration_mins', value: form.fear.avg_duration_mins },
          { label: 'Avg Intensity (0-10)', key: 'avg_intensity', value: form.fear.avg_intensity },
        ]}
        onUpdate={(k: string, v: string) => updateNum('fear', k, v)}
      />

      {/* 4. Emotional Outlets */}
      <View style={s.metricCard}>
        <View style={s.metricHeader}>
          <Ionicons name="warning" size={20} color="#F59E0B" />
          <Text style={s.metricTitle}>4. Emotional Outlets Impact (%)</Text>
        </View>
        <View style={s.fieldsRow}>
          {[
            { label: 'Time', key: 'time_impact_pct' },
            { label: 'Money', key: 'money_impact_pct' },
            { label: 'Health', key: 'health_impact_pct' },
            { label: 'Relations', key: 'relationships_impact_pct' },
          ].map(f => (
            <View key={f.key} style={s.fieldSmall}>
              <Text style={s.fieldSmallLabel}>{f.label}</Text>
              <TextInput
                style={s.fieldSmallInput}
                keyboardType="numeric"
                value={String(form.emotional_outlets[f.key] || 0)}
                onChangeText={(v) => updateNum('emotional_outlets', f.key, v)}
                placeholderTextColor={COLORS.textMuted}
              />
            </View>
          ))}
        </View>
      </View>

      {/* 5. ADS */}
      <View style={s.metricCard}>
        <View style={s.metricHeader}>
          <Ionicons name="eye-off" size={20} color="#EC4899" />
          <Text style={s.metricTitle}>5. Attention Deficiency Impact (Weekly %)</Text>
        </View>
        <View style={s.fieldsRow}>
          {[
            { label: 'Time', key: 'time_impact_pct' },
            { label: 'Money', key: 'money_impact_pct' },
            { label: 'Health', key: 'health_impact_pct' },
            { label: 'Relations', key: 'relationships_impact_pct' },
          ].map(f => (
            <View key={f.key} style={s.fieldSmall}>
              <Text style={s.fieldSmallLabel}>{f.label}</Text>
              <TextInput
                style={s.fieldSmallInput}
                keyboardType="numeric"
                value={String(form.ads[f.key] || 0)}
                onChangeText={(v) => updateNum('ads', f.key, v)}
                placeholderTextColor={COLORS.textMuted}
              />
            </View>
          ))}
        </View>
      </View>

      {/* 6. Sit Still */}
      <View style={s.metricCard}>
        <View style={s.metricHeader}>
          <Ionicons name="body" size={20} color="#14B8A6" />
          <Text style={s.metricTitle}>6. Ability to Sit Still (15 min)</Text>
        </View>
        <View style={s.switchRow}>
          <Text style={s.switchLabel}>Achieved today?</Text>
          <Switch
            value={form.sit_still.achieved}
            onValueChange={(v) => setForm((p: any) => ({ ...p, sit_still: { ...p.sit_still, achieved: v } }))}
            trackColor={{ false: '#ccc', true: '#10B981' }}
          />
        </View>
        <View style={s.fieldRow}>
          <Text style={s.fieldLabel}>Comfort Level (0-10)</Text>
          <TextInput
            style={s.fieldInput}
            keyboardType="numeric"
            value={String(form.sit_still.comfort_score)}
            onChangeText={(v) => updateNum('sit_still', 'comfort_score', v)}
          />
        </View>
      </View>

      {/* 7. Peacefulness */}
      <View style={s.metricCard}>
        <View style={s.metricHeader}>
          <Ionicons name="leaf" size={20} color="#10B981" />
          <Text style={s.metricTitle}>7. Peacefulness Throughout Day</Text>
        </View>
        <View style={s.fieldRow}>
          <Text style={s.fieldLabel}>Peaceful Hours</Text>
          <TextInput
            style={s.fieldInput}
            keyboardType="numeric"
            value={String(form.peacefulness.peaceful_hours)}
            onChangeText={(v) => updateNum('peacefulness', 'peaceful_hours', v)}
          />
        </View>
        <View style={s.fieldRow}>
          <Text style={s.fieldLabel}>Depth of Peace (0-10)</Text>
          <TextInput
            style={s.fieldInput}
            keyboardType="numeric"
            value={String(form.peacefulness.depth_score)}
            onChangeText={(v) => updateNum('peacefulness', 'depth_score', v)}
          />
        </View>
      </View>

      {/* 8. Solution Leadership */}
      <View style={s.metricCard}>
        <View style={s.metricHeader}>
          <Ionicons name="bulb" size={20} color="#F59E0B" />
          <Text style={s.metricTitle}>8. Solution-Oriented Leadership (Weekly)</Text>
        </View>
        <View style={s.fieldRow}>
          <Text style={s.fieldLabel}>Problems WITH solutions</Text>
          <TextInput
            style={s.fieldInput}
            keyboardType="numeric"
            value={String(form.solution_leadership.problems_with_solutions)}
            onChangeText={(v) => updateNum('solution_leadership', 'problems_with_solutions', v)}
          />
        </View>
        <View style={s.fieldRow}>
          <Text style={s.fieldLabel}>Problems WITHOUT solutions</Text>
          <TextInput
            style={s.fieldInput}
            keyboardType="numeric"
            value={String(form.solution_leadership.problems_without_solutions)}
            onChangeText={(v) => updateNum('solution_leadership', 'problems_without_solutions', v)}
          />
        </View>
      </View>

      {/* Overall Reflection */}
      <View style={s.metricCard}>
        <View style={s.metricHeader}>
          <Ionicons name="journal" size={20} color="#818CF8" />
          <Text style={s.metricTitle}>Overall Reflection</Text>
        </View>
        <TextInput
          style={s.reflectionInput}
          multiline
          placeholder="Reflect on your inner experience today..."
          value={form.overall_reflection}
          onChangeText={(v) => setForm((p: any) => ({ ...p, overall_reflection: v }))}
          placeholderTextColor={COLORS.textMuted}
        />
      </View>

      {/* Save Button */}
      <TouchableOpacity style={s.saveBtn} onPress={onSave} disabled={saving}>
        <LinearGradient colors={['#4F46E5', '#7C3AED']} style={s.saveBtnGradient}>
          {saving ? <ActivityIndicator color="#FFF" /> :
            <><Ionicons name="save" size={20} color="#FFF" /><Text style={s.saveBtnText}>Save Entry</Text></>
          }
        </LinearGradient>
      </TouchableOpacity>

      {/* History */}
      {history.length > 0 && (
        <View style={{ marginTop: 24 }}>
          <Text style={s.sectionTitle}>Recent Entries</Text>
          {history.slice(0, 7).map((h: any) => (
            <View key={h.entry_id} style={s.historyRow}>
              <Text style={s.historyDate}>{h.date}</Text>
              <View style={s.historyMetrics}>
                <Text style={s.historyChip}>😡 {h.metrics?.anger?.count || 0}</Text>
                <Text style={s.historyChip}>😢 {h.metrics?.sadness?.count || 0}</Text>
                <Text style={s.historyChip}>😰 {h.metrics?.fear?.count || 0}</Text>
                <Text style={s.historyChip}>☮️ {h.metrics?.peacefulness?.depth_score || 0}/10</Text>
              </View>
            </View>
          ))}
        </View>
      )}
    </View>
  );
}

// ========================
// METRIC SECTION COMPONENT
// ========================
function MetricSection({ title, icon, color, fields, onUpdate }: any) {
  return (
    <View style={s.metricCard}>
      <View style={s.metricHeader}>
        <Ionicons name={icon} size={20} color={color} />
        <Text style={s.metricTitle}>{title}</Text>
      </View>
      {fields.map((f: any) => (
        <View key={f.key} style={s.fieldRow}>
          <Text style={s.fieldLabel}>{f.label}</Text>
          <TextInput
            style={s.fieldInput}
            keyboardType="numeric"
            value={String(f.value || 0)}
            onChangeText={(v) => onUpdate(f.key, v)}
            placeholderTextColor={COLORS.textMuted}
          />
        </View>
      ))}
    </View>
  );
}

// ========================
// AWARENESS TAB
// ========================
function AwarenessTab({ selfAwareness, saRatings, setSaRatings, saving, onSave }: any) {
  const levels = selfAwareness?.levels || {};
  const overall = selfAwareness?.overall_level || 0;

  return (
    <View>
      <Text style={s.sectionTitle}>6 Levels of Self-Awareness</Text>
      <Text style={s.sectionDesc}>Progressive levels from Thought to Intense Action. Rate yourself honestly. Level 4 is auto-calculated from your diary.</Text>

      {/* Overall Level */}
      <View style={s.overallCard}>
        <Text style={s.overallLabel}>Current Overall Level</Text>
        <Text style={s.overallScore}>{overall}/10</Text>
        <View style={s.overallBar}>
          <View style={[s.overallBarFill, { width: `${(overall / 10) * 100}%` }]} />
        </View>
      </View>

      {/* Level Cards */}
      {AWARENESS_LEVELS.map(level => {
        const score = levels[String(level.level)]?.score || saRatings[String(level.level)] || 5;
        const isAuto = level.level === 4;
        const source = levels[String(level.level)]?.source || (isAuto ? 'auto_calculated' : 'self_rated');

        return (
          <View key={level.level} style={[s.levelCard, { borderLeftColor: level.color }]}>
            <View style={s.levelHeader}>
              <View style={[s.levelIcon, { backgroundColor: level.color + '20' }]}>
                <Ionicons name={level.icon as any} size={20} color={level.color} />
              </View>
              <View style={{ flex: 1, marginLeft: 10 }}>
                <Text style={s.levelName}>Level {level.level}: {level.name}</Text>
                <Text style={s.levelDesc}>{level.desc}</Text>
              </View>
              <View style={s.levelScoreWrap}>
                <Text style={[s.levelScore, { color: level.color }]}>{score}</Text>
                <Text style={s.levelScoreMax}>/10</Text>
              </View>
            </View>

            {isAuto ? (
              <View style={s.autoTag}>
                <Ionicons name="sync" size={12} color="#F59E0B" />
                <Text style={s.autoTagText}>Auto-calculated from 8 diary metrics</Text>
              </View>
            ) : (
              <View style={s.ratingRow}>
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => (
                  <TouchableOpacity
                    key={n}
                    style={[s.ratingDot, n <= (saRatings[String(level.level)] || 5) && { backgroundColor: level.color }]}
                    onPress={() => setSaRatings((prev: any) => ({ ...prev, [String(level.level)]: n }))}
                  >
                    <Text style={[s.ratingDotText, n <= (saRatings[String(level.level)] || 5) && { color: '#FFF' }]}>{n}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}

            {source === 'auto_calculated' && levels[String(level.level)]?.notes ? (
              <Text style={s.levelNotes}>{levels[String(level.level)].notes}</Text>
            ) : null}
          </View>
        );
      })}

      {/* Save */}
      <TouchableOpacity style={s.saveBtn} onPress={onSave} disabled={saving}>
        <LinearGradient colors={['#4F46E5', '#7C3AED']} style={s.saveBtnGradient}>
          {saving ? <ActivityIndicator color="#FFF" /> :
            <><Ionicons name="save" size={20} color="#FFF" /><Text style={s.saveBtnText}>Save Ratings</Text></>
          }
        </LinearGradient>
      </TouchableOpacity>
    </View>
  );
}

// ========================
// WELLNESS TAB
// ========================
function WellnessTab({ wellness, history }: any) {
  if (!wellness || wellness.status === 'no_data') {
    return (
      <View style={s.emptyWrap}>
        <Ionicons name="heart-outline" size={48} color={COLORS.textMuted} />
        <Text style={s.emptyTitle}>No Wellness Data Yet</Text>
        <Text style={s.emptyDesc}>Start logging your Consciousness Diary to see emotional wellness insights.</Text>
      </View>
    );
  }

  const ms = wellness.metrics_summary || {};

  return (
    <View>
      {/* Wellness Score */}
      <View style={s.wellnessCard}>
        <Text style={s.wellnessLabel}>Emotional Wellness Score</Text>
        <Text style={[s.wellnessScore, {
          color: wellness.wellness_score > 7 ? '#10B981' : wellness.wellness_score > 4 ? '#F59E0B' : '#EF4444'
        }]}>{wellness.wellness_score}/10</Text>
        <View style={s.wellnessBar}>
          <View style={[s.wellnessBarFill, {
            width: `${(wellness.wellness_score / 10) * 100}%`,
            backgroundColor: wellness.wellness_score > 7 ? '#10B981' : wellness.wellness_score > 4 ? '#F59E0B' : '#EF4444',
          }]} />
        </View>
        <Text style={s.wellnessTrend}>
          {wellness.trend_direction === 'improving' ? '📈 Improving' : '➡️ Stable'} • {wellness.entries_count} entries ({wellness.days_range}d)
        </Text>
      </View>

      {/* Negative Emotions */}
      <Text style={s.sectionTitle}>Emotional Patterns</Text>
      <View style={s.metricsGrid}>
        {[
          { key: 'anger', label: 'Anger', emoji: '😡', color: '#EF4444', data: ms.anger },
          { key: 'sadness', label: 'Sadness', emoji: '😢', color: '#3B82F6', data: ms.sadness },
          { key: 'fear', label: 'Fear', emoji: '😰', color: '#8B5CF6', data: ms.fear },
        ].map(e => (
          <View key={e.key} style={[s.metricSummaryCard, { borderLeftColor: e.color }]}>
            <Text style={s.metricSummaryEmoji}>{e.emoji}</Text>
            <Text style={s.metricSummaryName}>{e.label}</Text>
            <Text style={s.metricSummaryVal}>Count: {e.data?.avg_count || 0}/day</Text>
            <Text style={s.metricSummaryVal}>Duration: {e.data?.avg_duration_mins || 0}m</Text>
            <Text style={s.metricSummaryVal}>Intensity: {e.data?.avg_intensity || 0}/10</Text>
          </View>
        ))}
      </View>

      {/* Positive Indicators */}
      <Text style={s.sectionTitle}>Positive Indicators</Text>
      <View style={s.metricsGrid}>
        <View style={[s.metricSummaryCard, { borderLeftColor: '#14B8A6' }]}>
          <Text style={s.metricSummaryEmoji}>🧘</Text>
          <Text style={s.metricSummaryName}>Sit Still</Text>
          <Text style={s.metricSummaryVal}>Rate: {ms.sit_still?.achievement_rate_pct || 0}%</Text>
          <Text style={s.metricSummaryVal}>Comfort: {ms.sit_still?.avg_comfort || 0}/10</Text>
        </View>
        <View style={[s.metricSummaryCard, { borderLeftColor: '#10B981' }]}>
          <Text style={s.metricSummaryEmoji}>☮️</Text>
          <Text style={s.metricSummaryName}>Peace</Text>
          <Text style={s.metricSummaryVal}>{ms.peacefulness?.avg_peaceful_hours || 0} hrs/day</Text>
          <Text style={s.metricSummaryVal}>Depth: {ms.peacefulness?.avg_depth || 0}/10</Text>
        </View>
        <View style={[s.metricSummaryCard, { borderLeftColor: '#F59E0B' }]}>
          <Text style={s.metricSummaryEmoji}>💡</Text>
          <Text style={s.metricSummaryName}>Solution Focus</Text>
          <Text style={s.metricSummaryVal}>Ratio: {ms.solution_leadership?.solution_ratio || 0}%</Text>
          <Text style={s.metricSummaryVal}>w/ solutions: {ms.solution_leadership?.avg_with_solutions || 0}</Text>
        </View>
      </View>

      {/* Impact Scores */}
      <Text style={s.sectionTitle}>Negative Impact Areas</Text>
      <View style={s.impactRow}>
        <View style={s.impactCard}>
          <Text style={s.impactLabel}>Emotional Outlets</Text>
          <Text style={s.impactVal}>{ms.emotional_outlets?.avg_negative_impact_pct || 0}%</Text>
        </View>
        <View style={s.impactCard}>
          <Text style={s.impactLabel}>ADS (Attention)</Text>
          <Text style={s.impactVal}>{ms.ads?.avg_negative_impact_pct || 0}%</Text>
        </View>
      </View>
    </View>
  );
}

// ========================
// STYLES
// ========================
const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  loadWrap: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { paddingHorizontal: 16, paddingVertical: 14, flexDirection: 'row', alignItems: 'center' },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.15)', justifyContent: 'center', alignItems: 'center', marginRight: 10 },
  headerTitle: { fontSize: 20, fontWeight: '800', color: '#FFF' },
  headerSub: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  tabRow: { flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 8, gap: 6, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8, borderRadius: 10, backgroundColor: COLORS.background },
  tabActive: { backgroundColor: '#4F46E5' },
  tabText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },
  tabTextActive: { color: '#FFF' },
  scroll: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 40 },
  dateLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginTop: 20, marginBottom: 10 },
  sectionDesc: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 12, lineHeight: 18 },

  // Context
  contextCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  contextTitle: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10 },
  contextRow: { flexDirection: 'row', justifyContent: 'space-around' },
  contextItem: { alignItems: 'center', gap: 4 },
  contextNum: { fontSize: 20, fontWeight: '800', color: COLORS.textPrimary },
  contextLabel: { fontSize: 11, color: COLORS.textSecondary },

  // Metric Card
  metricCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  metricHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  metricTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, flex: 1 },
  fieldRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6 },
  fieldLabel: { fontSize: 13, color: COLORS.textSecondary, flex: 1 },
  fieldInput: { width: 70, textAlign: 'center', fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, backgroundColor: COLORS.background, borderRadius: 8, paddingVertical: 6, paddingHorizontal: 10 },
  fieldsRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  fieldSmall: { flex: 1, minWidth: 70, alignItems: 'center' },
  fieldSmallLabel: { fontSize: 10, color: COLORS.textMuted, marginBottom: 4 },
  fieldSmallInput: { width: '100%', textAlign: 'center', fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, backgroundColor: COLORS.background, borderRadius: 8, paddingVertical: 6 },
  switchRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8 },
  switchLabel: { fontSize: 13, color: COLORS.textSecondary },
  reflectionInput: { backgroundColor: COLORS.background, borderRadius: 10, padding: 12, fontSize: 14, color: COLORS.textPrimary, minHeight: 80, textAlignVertical: 'top' },

  // Save
  saveBtn: { marginTop: 16, borderRadius: 14, overflow: 'hidden' },
  saveBtnGradient: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, gap: 8 },
  saveBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },

  // History
  historyRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  historyDate: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  historyMetrics: { flexDirection: 'row', gap: 8 },
  historyChip: { fontSize: 11, color: COLORS.textSecondary },

  // Awareness
  overallCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 16, marginBottom: 16, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  overallLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  overallScore: { fontSize: 36, fontWeight: '800', color: '#4F46E5', marginVertical: 8 },
  overallBar: { width: '100%', height: 6, backgroundColor: COLORS.divider, borderRadius: 3, overflow: 'hidden' },
  overallBarFill: { height: '100%', backgroundColor: '#4F46E5', borderRadius: 3 },
  levelCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 10, borderLeftWidth: 4, borderWidth: 1, borderColor: COLORS.border },
  levelHeader: { flexDirection: 'row', alignItems: 'center' },
  levelIcon: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center' },
  levelName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  levelDesc: { fontSize: 11, color: COLORS.textSecondary, marginTop: 2 },
  levelScoreWrap: { flexDirection: 'row', alignItems: 'baseline' },
  levelScore: { fontSize: 22, fontWeight: '800' },
  levelScoreMax: { fontSize: 12, color: COLORS.textMuted },
  autoTag: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 8, backgroundColor: '#FEF3C7', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, alignSelf: 'flex-start' },
  autoTagText: { fontSize: 10, fontWeight: '600', color: '#92400E' },
  ratingRow: { flexDirection: 'row', gap: 4, marginTop: 10, justifyContent: 'space-between' },
  ratingDot: { width: 28, height: 28, borderRadius: 14, backgroundColor: COLORS.divider, justifyContent: 'center', alignItems: 'center' },
  ratingDotText: { fontSize: 10, fontWeight: '700', color: COLORS.textMuted },
  levelNotes: { fontSize: 10, color: COLORS.textMuted, marginTop: 6, fontStyle: 'italic' },

  // Wellness
  emptyWrap: { alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptyDesc: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', paddingHorizontal: 32 },
  wellnessCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 16, alignItems: 'center', marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  wellnessLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  wellnessScore: { fontSize: 40, fontWeight: '800', marginVertical: 8 },
  wellnessBar: { width: '100%', height: 8, backgroundColor: COLORS.divider, borderRadius: 4, overflow: 'hidden' },
  wellnessBarFill: { height: '100%', borderRadius: 4 },
  wellnessTrend: { fontSize: 12, color: COLORS.textSecondary, marginTop: 8 },
  metricsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  metricSummaryCard: { width: '31%', flexGrow: 1, backgroundColor: COLORS.white, borderRadius: 12, padding: 12, borderLeftWidth: 3, borderWidth: 1, borderColor: COLORS.border },
  metricSummaryEmoji: { fontSize: 20 },
  metricSummaryName: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary, marginTop: 4 },
  metricSummaryVal: { fontSize: 10, color: COLORS.textSecondary, marginTop: 2 },
  impactRow: { flexDirection: 'row', gap: 10, marginTop: 4 },
  impactCard: { flex: 1, backgroundColor: COLORS.white, borderRadius: 12, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  impactLabel: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },
  impactVal: { fontSize: 22, fontWeight: '800', color: '#EF4444', marginTop: 4 },
});
