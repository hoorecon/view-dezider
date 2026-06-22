import React, { useState, useCallback, useRef, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert, Modal, TextInput,
  Animated, Dimensions, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

// ========================
// TYPE DEFINITIONS
// ========================
interface FlightDynamics {
  altitude: number;
  altitude_label: string;
  max_altitude: number;
  speed: number;
  speed_label: string;
  max_speed: number;
  turbulence: number;
  turbulence_label: string;
  fuel: number;
  fuel_label: string;
  eta_days: number;
  deadline: string | null;
  days_to_deadline: number | null;
  on_time: boolean;
  crash_risk: number;
  crash_label: string;
  phase: string;
  heading: string;
  weather: string;
  weather_label: string;
  current_step: number;
  current_gear: number;
  progress_percent: number;
  tasks_summary: { total: number; done: number; in_progress: number; blocked: number };
  routines_summary: { total: number; avg_streak: number };
}

interface SecretConfig {
  key: string; num: string; name: string; flight_part: string; icon: string; color: string;
}

interface StepConfig {
  step: number; name: string; mnemonic: string; desc: string; icon: string;
}

interface GearConfig {
  gear: number; name: string; desc: string; icon: string;
}

interface FlightProject {
  project_id: string;
  title: string;
  vision: string;
  goal: string;
  goal_smart: Record<string, string>;
  point_a: string;
  point_b: string;
  life_area: string;
  current_step: number;
  current_gear: number;
  progress_percent: number;
  status: string;
  steps: Record<string, any>;
  secrets_scores: Record<string, any>;
  gis: Record<string, any>;
  igis: Record<string, any>;
  linked_ctt_tasks: any[];
  linked_routines: string[];
  linked_decisions: string[];
  created_at: string;
}

interface FlightScores {
  scores: Record<string, number>;
  overall_health: number;
  gis: Record<string, any>;
  igis: Record<string, any>;
}

interface DashboardData {
  project: FlightProject;
  linked_tasks: any[];
  linked_routines: any[];
  linked_decisions: any[];
  config: { secrets: SecretConfig[]; seven_steps: StepConfig[]; gears: GearConfig[] };
}

// ========================
// WEATHER BACKGROUNDS
// ========================
const WEATHER_GRADIENTS: Record<string, string[]> = {
  clear: ['#0C1445', '#1A237E', '#283593'],
  partly_cloudy: ['#1A237E', '#37474F', '#455A64'],
  overcast: ['#263238', '#37474F', '#546E7A'],
  stormy: ['#1A1A2E', '#2D2D44', '#4A1942'],
};

const PHASE_LABELS: Record<string, { emoji: string; label: string }> = {
  pre_flight: { emoji: '🔧', label: 'Pre-Flight' },
  takeoff: { emoji: '🛫', label: 'Takeoff' },
  climbing: { emoji: '📈', label: 'Climbing' },
  cruise: { emoji: '✈️', label: 'Cruising' },
  descent: { emoji: '📉', label: 'Descending' },
  landed: { emoji: '🏁', label: 'Landed!' },
  taxiing: { emoji: '🚶', label: 'Taxiing' },
};

const TURBULENCE_COLORS: Record<string, string> = {
  Smooth: '#10B981',
  Light: '#22C55E',
  Moderate: '#F59E0B',
  Severe: '#EF4444',
};

// ========================
// MAIN COMPONENT
// ========================
export default function GemFlightDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [dynamics, setDynamics] = useState<FlightDynamics | null>(null);
  const [scores, setScores] = useState<FlightScores | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<'cockpit' | 'steps' | 'secrets' | 'modules'>('cockpit');
  const [showStepModal, setShowStepModal] = useState(false);
  const [editingStep, setEditingStep] = useState<number | null>(null);
  const [stepNotes, setStepNotes] = useState('');
  const [showIgisModal, setShowIgisModal] = useState<string | null>(null);
  const [igisData, setIgisData] = useState<any>(null);

  // Animations
  const planeY = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    // Airplane bobbing animation (simulates turbulence)
    const turbLevel = dynamics?.turbulence || 0;
    const amplitude = Math.max(2, turbLevel * 1.5);
    const speed = Math.max(600, 2000 - turbLevel * 150);
    Animated.loop(
      Animated.sequence([
        Animated.timing(planeY, { toValue: -amplitude, duration: speed, useNativeDriver: true }),
        Animated.timing(planeY, { toValue: amplitude, duration: speed, useNativeDriver: true }),
      ])
    ).start();

    // Pulse for critical alerts
    if (dynamics && dynamics.crash_risk > 40) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, { toValue: 0.3, duration: 500, useNativeDriver: true }),
          Animated.timing(pulseAnim, { toValue: 1, duration: 500, useNativeDriver: true }),
        ])
      ).start();
    }
  }, [dynamics?.turbulence, dynamics?.crash_risk]);

  const fetchAll = async () => {
    if (!id) return;
    try {
      const [dashRes, dynRes, scoreRes] = await Promise.all([
        api.get(`/gem-flight/projects/${id}/dashboard`),
        api.get(`/gem-flight/projects/${id}/flight-dynamics`),
        api.get(`/gem-flight/projects/${id}/flight-score`),
      ]);
      setDashboard(dashRes.data);
      setDynamics(dynRes.data);
      setScores(scoreRes.data);
    } catch (e: any) {
      console.error('Flight fetch error:', e);
      if (e?.response?.status === 404) {
        showAlert('Not Found', 'Flight project not found');
        safeBack(router);
      }
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchAll(); }, [id]));
  const onRefresh = async () => { setRefreshing(true); await fetchAll(); setRefreshing(false); };

  const updateStep = async (stepNum: number, status: string) => {
    try {
      await api.put(`/gem-flight/projects/${id}/step/${stepNum}`, {
        status,
        notes: stepNotes,
      });
      setShowStepModal(false);
      setStepNotes('');
      fetchAll();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to update step');
    }
  };

  const updateGear = async (gear: number) => {
    try {
      await api.put(`/gem-flight/projects/${id}/gear/${gear}`, {});
      fetchAll();
    } catch (e: any) {
      showAlert('Error', 'Failed to update gear');
    }
  };

  const fetchIgis = async (module: string) => {
    try {
      const res = await api.get(`/gem-flight/projects/${id}/igis/${module}`);
      setIgisData(res.data);
      setShowIgisModal(module);
    } catch (e) {
      showAlert('Error', 'Failed to load module');
    }
  };

  if (loading || !dashboard || !dynamics) {
    return (
      <SafeAreaView style={s.container} edges={['top']}>
        <View style={s.loadingWrap}>
          <ActivityIndicator size="large" color="#818CF8" />
          <Text style={s.loadingText}>Initializing flight systems...</Text>
        </View>
      </SafeAreaView>
    );
  }

  const project = dashboard.project;
  const config = dashboard.config;
  const weather = dynamics.weather || 'clear';
  const phaseInfo = PHASE_LABELS[dynamics.phase] || PHASE_LABELS.taxiing;

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={WEATHER_GRADIENTS[weather] || WEATHER_GRADIENTS.clear} style={{ flex: 1 }}>
        {/* Header Bar */}
        <View style={s.headerBar}>
          <TouchableOpacity onPress={() => safeBack(router)} style={s.headerBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1, marginHorizontal: 12 }}>
            <Text style={s.headerTitle} numberOfLines={1}>{project.title}</Text>
            <Text style={s.headerPhase}>{phaseInfo.emoji} {phaseInfo.label} • {dynamics.weather_label}</Text>
          </View>
          <TouchableOpacity onPress={onRefresh} style={s.headerBtn}>
            <Ionicons name="refresh" size={20} color="#FFF" />
          </TouchableOpacity>
        </View>

        {/* Sky / Airplane Visualization */}
        <View style={s.skySection}>
          {/* Stars */}
          <View style={s.starsRow}>
            {Array.from({ length: 12 }).map((_, i) => (
              <View key={i} style={[s.star, {
                left: `${(i * 8.3) + Math.random() * 3}%`,
                top: `${10 + Math.random() * 50}%`,
                opacity: 0.3 + Math.random() * 0.5,
                width: 2 + Math.random() * 2,
                height: 2 + Math.random() * 2,
              }]} />
            ))}
          </View>

          {/* Altitude Bar (Left) */}
          <View style={s.altBar}>
            <Text style={s.altLabel}>{dynamics.altitude_label}</Text>
            <View style={s.altTrack}>
              <View style={[s.altFill, { height: `${(dynamics.altitude / dynamics.max_altitude) * 100}%` }]} />
            </View>
            <Text style={s.altMinLabel}>0 ft</Text>
          </View>

          {/* Central Airplane */}
          <View style={s.planeArea}>
            <Animated.View style={[s.planeWrap, { transform: [{ translateY: planeY }] }]}>
              <Text style={s.planeIcon}>✈️</Text>
            </Animated.View>

            {/* Speed Under Plane */}
            <Text style={s.speedLabel}>{dynamics.speed_label}</Text>

            {/* Crash Risk Warning */}
            {dynamics.crash_risk > 15 && (
              <Animated.View style={[s.crashBanner, { opacity: dynamics.crash_risk > 40 ? pulseAnim : 1 }]}>
                <Ionicons name="warning" size={14} color={dynamics.crash_risk > 70 ? '#EF4444' : '#F59E0B'} />
                <Text style={[s.crashText, { color: dynamics.crash_risk > 70 ? '#EF4444' : '#F59E0B' }]}>
                  {dynamics.crash_label} ({dynamics.crash_risk}%)
                </Text>
              </Animated.View>
            )}
          </View>

          {/* Fuel Bar (Right) */}
          <View style={s.fuelBar}>
            <Text style={s.fuelLabel}>⛽ {dynamics.fuel_label}</Text>
            <View style={s.fuelTrack}>
              <View style={[s.fuelFill, {
                height: `${dynamics.fuel}%`,
                backgroundColor: dynamics.fuel < 20 ? '#EF4444' : dynamics.fuel < 50 ? '#F59E0B' : '#10B981',
              }]} />
            </View>
          </View>
        </View>

        {/* Flight Path Progress */}
        <View style={s.flightPathSection}>
          <View style={s.pathRow}>
            <View style={s.pathPoint}>
              <Text style={s.pathEmoji}>🏠</Text>
              <Text style={s.pathLabel}>A</Text>
            </View>
            <View style={s.pathTrack}>
              <View style={[s.pathFill, { width: `${dynamics.progress_percent}%` }]} />
              {/* Step Markers */}
              {config.seven_steps.map((step) => {
                const pct = ((step.step - 1) / 6) * 100;
                const completed = (project.steps[String(step.step)]?.status === 'completed');
                const current = project.current_step === step.step;
                return (
                  <View key={step.step} style={[s.stepMarker, { left: `${pct}%` }]}>
                    <View style={[
                      s.stepDot,
                      completed && s.stepDotCompleted,
                      current && s.stepDotCurrent,
                    ]}>
                      <Text style={s.stepDotText}>{step.step}</Text>
                    </View>
                  </View>
                );
              })}
            </View>
            <View style={s.pathPoint}>
              <Text style={s.pathEmoji}>🎯</Text>
              <Text style={s.pathLabel}>B</Text>
            </View>
          </View>

          {/* ETA Row */}
          <View style={s.etaRow}>
            <Text style={s.etaText}>
              ETA: {dynamics.eta_days < 999 ? `${dynamics.eta_days} days` : 'Stalled'}
            </Text>
            {dynamics.days_to_deadline !== null && (
              <Text style={[s.etaText, { color: dynamics.on_time ? '#10B981' : '#EF4444' }]}>
                {dynamics.on_time ? '✓ On Schedule' : `⚠ ${Math.abs(dynamics.days_to_deadline)}d ${dynamics.days_to_deadline < 0 ? 'overdue' : 'left'}`}
              </Text>
            )}
            <Text style={s.etaText}>
              Turbulence: <Text style={{ color: TURBULENCE_COLORS[dynamics.turbulence_label] || '#FFF' }}>{dynamics.turbulence_label}</Text>
            </Text>
          </View>
        </View>

        {/* Tab Switcher */}
        <View style={s.tabRow}>
          {(['cockpit', 'steps', 'secrets', 'modules'] as const).map(tab => (
            <TouchableOpacity
              key={tab}
              style={[s.tab, activeTab === tab && s.tabActive]}
              onPress={() => setActiveTab(tab)}
            >
              <Ionicons
                name={tab === 'cockpit' ? 'speedometer' : tab === 'steps' ? 'map' : tab === 'secrets' ? 'key' : 'apps'}
                size={16}
                color={activeTab === tab ? '#FFF' : 'rgba(255,255,255,0.5)'}
              />
              <Text style={[s.tabText, activeTab === tab && s.tabTextActive]}>
                {tab === 'cockpit' ? 'Cockpit' : tab === 'steps' ? 'Journey' : tab === 'secrets' ? '12 Secrets' : 'Modules'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Tab Content */}
        <ScrollView
          style={s.tabContent}
          contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {activeTab === 'cockpit' && (
            <CockpitTab dynamics={dynamics} project={project} scores={scores} />
          )}
          {activeTab === 'steps' && (
            <StepsTab
              steps={project.steps}
              config={config}
              currentStep={project.current_step}
              currentGear={project.current_gear}
              onEditStep={(step: number) => {
                setEditingStep(step);
                setStepNotes(project.steps[String(step)]?.notes || '');
                setShowStepModal(true);
              }}
              onUpdateGear={updateGear}
            />
          )}
          {activeTab === 'secrets' && (
            <SecretsTab secrets={config.secrets} scores={scores} project={project} />
          )}
          {activeTab === 'modules' && (
            <ModulesTab
              dashboard={dashboard}
              dynamics={dynamics}
              onFetchIgis={fetchIgis}
              gis={scores?.gis}
              igis={scores?.igis}
            />
          )}
        </ScrollView>
      </LinearGradient>

      {/* Step Edit Modal */}
      <Modal visible={showStepModal} animationType="slide" transparent>
        <View style={s.modalOverlay}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
            <View style={s.modalCard}>
              <Text style={s.modalTitle}>
                Step {editingStep}: {config.seven_steps.find(s => s.step === editingStep)?.name}
              </Text>
              <Text style={s.modalDesc}>
                {config.seven_steps.find(s => s.step === editingStep)?.desc}
              </Text>

              <Text style={s.modalLabel}>Notes</Text>
              <TextInput
                style={s.modalInput}
                multiline
                value={stepNotes}
                onChangeText={setStepNotes}
                placeholder="Add notes for this step..."
                placeholderTextColor={COLORS.textMuted}
              />

              <View style={s.modalActions}>
                <TouchableOpacity style={s.modalBtn} onPress={() => setShowStepModal(false)}>
                  <Text style={s.modalBtnText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[s.modalBtn, { backgroundColor: '#F59E0B' }]}
                  onPress={() => editingStep && updateStep(editingStep, 'in_progress')}
                >
                  <Text style={[s.modalBtnText, { color: '#FFF' }]}>In Progress</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[s.modalBtn, { backgroundColor: '#10B981' }]}
                  onPress={() => editingStep && updateStep(editingStep, 'completed')}
                >
                  <Text style={[s.modalBtnText, { color: '#FFF' }]}>Complete</Text>
                </TouchableOpacity>
              </View>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>

      {/* iGIS Module Modal */}
      <Modal visible={!!showIgisModal} animationType="fade" transparent>
        <View style={s.modalOverlay}>
          <View style={[s.modalCard, { maxHeight: '70%' }]}>
            <View style={s.igisHeader}>
              <Text style={s.modalTitle}>
                {showIgisModal === 'astrology' ? '🔮 Astrology' :
                  showIgisModal === 'energy-healing' ? '💫 Energy Healing' : '🧘 Manifestation'}
              </Text>
              <TouchableOpacity onPress={() => { setShowIgisModal(null); setIgisData(null); }}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>
            {igisData && (
              <ScrollView>
                <View style={s.stubBanner}>
                  <Ionicons name="construct" size={20} color="#F59E0B" />
                  <Text style={s.stubText}>{igisData.message}</Text>
                </View>
                {igisData.placeholder_data && (
                  <View style={s.stubData}>
                    {Object.entries(igisData.placeholder_data).map(([key, val]) => (
                      <View key={key} style={s.stubRow}>
                        <Text style={s.stubKey}>{key.replace(/_/g, ' ')}</Text>
                        <Text style={s.stubVal}>
                          {typeof val === 'string' ? val :
                            Array.isArray(val) ? val.map((v: any) =>
                              typeof v === 'string' ? v : (v.label || v.name || JSON.stringify(v))
                            ).join(', ') :
                              JSON.stringify(val)}
                        </Text>
                      </View>
                    ))}
                  </View>
                )}
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

// ========================
// COCKPIT TAB
// ========================
function CockpitTab({ dynamics, project, scores }: { dynamics: FlightDynamics; project: FlightProject; scores: FlightScores | null }) {
  const gauges = [
    { label: 'Altitude', value: dynamics.altitude, max: dynamics.max_altitude, display: dynamics.altitude_label, icon: 'trending-up', color: '#818CF8' },
    { label: 'Speed', value: dynamics.speed, max: dynamics.max_speed, display: dynamics.speed_label, icon: 'speedometer', color: '#3B82F6' },
    { label: 'Fuel', value: dynamics.fuel, max: 100, display: dynamics.fuel_label, icon: 'battery-charging', color: dynamics.fuel < 20 ? '#EF4444' : '#10B981' },
    { label: 'Turbulence', value: dynamics.turbulence, max: 10, display: dynamics.turbulence_label, icon: 'pulse', color: TURBULENCE_COLORS[dynamics.turbulence_label] || '#F59E0B' },
  ];

  return (
    <View>
      {/* Instrument Gauges */}
      <Text style={s.sectionTitle}>Flight Instruments</Text>
      <View style={s.gaugeGrid}>
        {gauges.map(g => (
          <View key={g.label} style={s.gaugeCard}>
            <View style={s.gaugeHeader}>
              <Ionicons name={g.icon as any} size={18} color={g.color} />
              <Text style={s.gaugeLabel}>{g.label}</Text>
            </View>
            <Text style={[s.gaugeValue, { color: g.color }]}>{g.display}</Text>
            <View style={s.gaugeTrack}>
              <View style={[s.gaugeFill, { width: `${Math.min(100, (g.value / g.max) * 100)}%`, backgroundColor: g.color }]} />
            </View>
          </View>
        ))}
      </View>

      {/* Status Cards */}
      <Text style={s.sectionTitle}>Flight Status</Text>
      <View style={s.statusGrid}>
        <View style={s.statusCard}>
          <Ionicons name="time" size={22} color="#818CF8" />
          <Text style={s.statusValue}>{dynamics.eta_days < 999 ? `${dynamics.eta_days}d` : '--'}</Text>
          <Text style={s.statusLabel}>ETA</Text>
        </View>
        <View style={s.statusCard}>
          <Ionicons name="alert-circle" size={22} color={dynamics.crash_risk > 40 ? '#EF4444' : '#F59E0B'} />
          <Text style={[s.statusValue, { color: dynamics.crash_risk > 40 ? '#EF4444' : '#FFF' }]}>{dynamics.crash_risk}%</Text>
          <Text style={s.statusLabel}>Crash Risk</Text>
        </View>
        <View style={s.statusCard}>
          <Ionicons name="checkbox" size={22} color="#10B981" />
          <Text style={s.statusValue}>{dynamics.tasks_summary.done}/{dynamics.tasks_summary.total}</Text>
          <Text style={s.statusLabel}>Tasks Done</Text>
        </View>
        <View style={s.statusCard}>
          <Ionicons name="flame" size={22} color="#F59E0B" />
          <Text style={s.statusValue}>{dynamics.routines_summary.avg_streak}</Text>
          <Text style={s.statusLabel}>Avg Streak</Text>
        </View>
      </View>

      {/* Overall Health */}
      {scores && (
        <View style={s.healthCard}>
          <Text style={s.healthTitle}>Overall Flight Health</Text>
          <View style={s.healthRow}>
            <Text style={s.healthScore}>{scores.overall_health}/10</Text>
            <View style={s.healthBarTrack}>
              <View style={[s.healthBarFill, {
                width: `${(scores.overall_health / 10) * 100}%`,
                backgroundColor: scores.overall_health > 7 ? '#10B981' : scores.overall_health > 4 ? '#F59E0B' : '#EF4444',
              }]} />
            </View>
          </View>
        </View>
      )}

      {/* Journey Overview */}
      {project.point_a || project.point_b ? (
        <View style={s.journeyCard}>
          <Text style={s.journeyTitle}>Journey Map</Text>
          <View style={s.journeyRow}>
            <View style={s.journeyPoint}>
              <Text style={s.journeyEmoji}>🏠</Text>
              <Text style={s.journeyLabel}>Point A</Text>
              <Text style={s.journeyDesc} numberOfLines={3}>{project.point_a || 'Not set'}</Text>
            </View>
            <View style={s.journeyArrow}>
              <Ionicons name="airplane" size={24} color="#818CF8" />
            </View>
            <View style={s.journeyPoint}>
              <Text style={s.journeyEmoji}>🎯</Text>
              <Text style={s.journeyLabel}>Point B</Text>
              <Text style={s.journeyDesc} numberOfLines={3}>{project.point_b || 'Not set'}</Text>
            </View>
          </View>
        </View>
      ) : null}
    </View>
  );
}

// ========================
// STEPS TAB
// ========================
function StepsTab({ steps, config, currentStep, currentGear, onEditStep, onUpdateGear }: {
  steps: Record<string, any>;
  config: DashboardData['config'];
  currentStep: number;
  currentGear: number;
  onEditStep: (s: number) => void;
  onUpdateGear: (g: number) => void;
}) {
  return (
    <View>
      <Text style={s.sectionTitle}>7-Step Journey (SMART iPOD)</Text>
      {config.seven_steps.map((step) => {
        const data = steps[String(step.step)] || {};
        const isCompleted = data.status === 'completed';
        const isCurrent = currentStep === step.step;
        const isPending = data.status === 'pending';

        return (
          <TouchableOpacity
            key={step.step}
            style={[s.stepCard, isCurrent && s.stepCardCurrent, isCompleted && s.stepCardCompleted]}
            onPress={() => onEditStep(step.step)}
            activeOpacity={0.7}
          >
            <View style={[s.stepIcon, {
              backgroundColor: isCompleted ? '#10B981' : isCurrent ? '#818CF8' : 'rgba(255,255,255,0.1)'
            }]}>
              {isCompleted ?
                <Ionicons name="checkmark" size={20} color="#FFF" /> :
                <Ionicons name={step.icon as any} size={20} color={isCurrent ? '#FFF' : 'rgba(255,255,255,0.5)'} />
              }
            </View>
            <View style={{ flex: 1, marginLeft: 12 }}>
              <View style={s.stepNameRow}>
                <Text style={s.stepName}>{step.mnemonic} — {step.name}</Text>
                {isCurrent && <View style={s.currentBadge}><Text style={s.currentBadgeText}>CURRENT</Text></View>}
              </View>
              <Text style={s.stepDesc}>{step.desc}</Text>
              {data.notes ? <Text style={s.stepNotes}>📝 {data.notes}</Text> : null}
              {isCompleted && data.completed_at && (
                <Text style={s.stepDate}>✓ Completed {new Date(data.completed_at).toLocaleDateString()}</Text>
              )}
            </View>
          </TouchableOpacity>
        );
      })}

      {/* Gear System (Active during Step 6) */}
      {currentStep >= 6 && (
        <View style={s.gearSection}>
          <Text style={s.sectionTitle}>Drive Phase — 4 Gears</Text>
          <View style={s.gearGrid}>
            {config.gears.map(gear => {
              const isActive = currentGear >= gear.gear;
              const isCurrent = currentGear === gear.gear;
              return (
                <TouchableOpacity
                  key={gear.gear}
                  style={[s.gearCard, isActive && s.gearCardActive, isCurrent && s.gearCardCurrent]}
                  onPress={() => onUpdateGear(gear.gear)}
                >
                  <Text style={s.gearNum}>G{gear.gear}</Text>
                  <Ionicons name={gear.icon as any} size={22} color={isActive ? '#FFF' : 'rgba(255,255,255,0.4)'} />
                  <Text style={[s.gearName, isActive && { color: '#FFF' }]}>{gear.name}</Text>
                  <Text style={s.gearDesc} numberOfLines={2}>{gear.desc}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      )}
    </View>
  );
}

// ========================
// SECRETS TAB (12 Secrets = Airplane Parts)
// ========================
function SecretsTab({ secrets, scores, project }: { secrets: SecretConfig[]; scores: FlightScores | null; project: FlightProject }) {
  return (
    <View>
      <Text style={s.sectionTitle}>12 Secrets — Airplane Parts</Text>
      <Text style={s.sectionDesc}>Each secret maps to a part of your airplane. Higher scores = stronger flight.</Text>

      {/* Airplane Diagram Representation */}
      <View style={s.planeDigram}>
        <Text style={s.planeDiagramLabel}>Your Aircraft Health</Text>
        <View style={s.planeDiagramRow}>
          <Text style={{ fontSize: 48 }}>✈️</Text>
          {scores && (
            <View style={s.overallScoreWrap}>
              <Text style={s.overallScoreNum}>{scores.overall_health}</Text>
              <Text style={s.overallScoreLabel}>/10</Text>
            </View>
          )}
        </View>
      </View>

      {/* Secrets Grid */}
      {secrets.map(secret => {
        const auto = scores?.scores?.[secret.key] || 0;
        const manual = project.secrets_scores?.[secret.key]?.manual_score;
        const score = manual ?? auto;
        const pct = (score / 10) * 100;

        return (
          <View key={secret.key} style={s.secretCard}>
            <View style={s.secretLeft}>
              <View style={[s.secretIconWrap, { backgroundColor: secret.color + '20' }]}>
                <Ionicons name={secret.icon as any} size={20} color={secret.color} />
              </View>
              <View style={{ flex: 1, marginLeft: 12 }}>
                <View style={s.secretNameRow}>
                  <Text style={s.secretNum}>{secret.num}</Text>
                  <Text style={s.secretName}>{secret.name}</Text>
                </View>
                <Text style={s.secretPart}>✈ {secret.flight_part}</Text>
              </View>
              <Text style={[s.secretScore, { color: secret.color }]}>{score}/10</Text>
            </View>
            <View style={s.secretBar}>
              <View style={[s.secretBarFill, { width: `${pct}%`, backgroundColor: secret.color }]} />
            </View>
          </View>
        );
      })}
    </View>
  );
}

// ========================
// MODULES TAB (GIS, iGIS, Linked Data)
// ========================
function ModulesTab({ dashboard, dynamics, onFetchIgis, gis, igis }: {
  dashboard: DashboardData;
  dynamics: FlightDynamics;
  onFetchIgis: (mod: string) => void;
  gis?: Record<string, any>;
  igis?: Record<string, any>;
}) {
  const router = useRouter();
  const [ewData, setEwData] = useState<any>(null);
  const [saData, setSaData] = useState<any>(null);
  const [loadingLive, setLoadingLive] = useState(true);

  useEffect(() => {
    const fetchLive = async () => {
      try {
        const pid = dashboard.project.project_id;
        const [ewRes, saRes] = await Promise.all([
          api.get(`/gem-flight/projects/${pid}/igis/emotional-wellness`),
          api.get(`/gem-flight/projects/${pid}/igis/self-awareness`),
        ]);
        setEwData(ewRes.data);
        setSaData(saRes.data);
      } catch (e) {
        console.log('Live iGIS fetch error:', e);
      } finally {
        setLoadingLive(false);
      }
    };
    fetchLive();
  }, [dashboard.project.project_id]);

  return (
    <View>
      {/* GIS Model */}
      <Text style={s.sectionTitle}>GIS Model (External)</Text>
      <View style={s.gisGrid}>
        <View style={s.gisCard}>
          <Ionicons name="sparkles" size={24} color="#F59E0B" />
          <Text style={s.gisLabel}>Grace</Text>
          <Text style={s.gisScore}>{gis?.grace ?? 0}/10</Text>
          <Text style={s.gisDesc}>External support & luck</Text>
        </View>
        <View style={s.gisCard}>
          <Ionicons name="body" size={24} color="#3B82F6" />
          <Text style={s.gisLabel}>Involvement</Text>
          <Text style={s.gisScore}>{gis?.involvement ?? 0}/10</Text>
          <Text style={s.gisDesc}>Your active effort</Text>
        </View>
        <View style={s.gisCard}>
          <Ionicons name="people" size={24} color="#10B981" />
          <Text style={s.gisLabel}>Support</Text>
          <Text style={s.gisScore}>{Math.round(((gis?.support_micro ?? 0) + (gis?.support_macro ?? 0)) / 2)}/10</Text>
          <Text style={s.gisDesc}>Micro + Macro support</Text>
        </View>
      </View>

      {/* iGIS Model (Inner) — LIVE Modules */}
      <Text style={s.sectionTitle}>iGIS Model (Inner Awareness)</Text>
      <Text style={s.sectionDesc}>Inner dimensions complementing your external efforts</Text>

      {/* Emotional Wellness — LIVE */}
      <TouchableOpacity
        style={s.liveIgisCard}
        onPress={() => router.push('/tools/consciousness-diary' as any)}
        activeOpacity={0.7}
      >
        <LinearGradient colors={['#1E1B4B', '#312E81']} style={s.liveIgisGradient}>
          <View style={s.liveIgisHeader}>
            <Text style={s.liveIgisEmoji}>💚</Text>
            <View style={{ flex: 1 }}>
              <Text style={s.liveIgisTitle}>Emotional Wellness</Text>
              <Text style={s.liveIgisDesc}>Tracked from your Consciousness Diary</Text>
            </View>
            <View style={s.liveBadge}>
              <View style={s.liveDot} />
              <Text style={s.liveBadgeText}>LIVE</Text>
            </View>
          </View>
          {loadingLive ? (
            <ActivityIndicator size="small" color="#818CF8" style={{ marginTop: 10 }} />
          ) : ewData?.status === 'ok' ? (
            <View style={s.liveMetricsRow}>
              <View style={s.liveMetric}>
                <Text style={[s.liveMetricVal, { color: ewData.wellness_score > 7 ? '#10B981' : ewData.wellness_score > 4 ? '#F59E0B' : '#EF4444' }]}>
                  {ewData.wellness_score}
                </Text>
                <Text style={s.liveMetricLabel}>Wellness</Text>
              </View>
              <View style={s.liveMetric}>
                <Text style={s.liveMetricVal}>{ewData.avg_peacefulness || 0}</Text>
                <Text style={s.liveMetricLabel}>Peace</Text>
              </View>
              <View style={s.liveMetric}>
                <Text style={[s.liveMetricVal, { color: '#EF4444' }]}>{ewData.avg_anger_intensity || 0}</Text>
                <Text style={s.liveMetricLabel}>Anger</Text>
              </View>
              <View style={s.liveMetric}>
                <Text style={s.liveMetricVal}>{ewData.entries_count}</Text>
                <Text style={s.liveMetricLabel}>Entries</Text>
              </View>
            </View>
          ) : (
            <Text style={s.liveNoData}>Tap to start your Consciousness Diary →</Text>
          )}
        </LinearGradient>
      </TouchableOpacity>

      {/* Self Awareness — LIVE */}
      <TouchableOpacity
        style={s.liveIgisCard}
        onPress={() => router.push('/tools/consciousness-diary' as any)}
        activeOpacity={0.7}
      >
        <LinearGradient colors={['#1C1917', '#292524']} style={s.liveIgisGradient}>
          <View style={s.liveIgisHeader}>
            <Text style={s.liveIgisEmoji}>👁️</Text>
            <View style={{ flex: 1 }}>
              <Text style={s.liveIgisTitle}>Self Awareness @ Conscious Leadership</Text>
              <Text style={s.liveIgisDesc}>6 progressive levels of inner awareness</Text>
            </View>
            <View style={s.liveBadge}>
              <View style={s.liveDot} />
              <Text style={s.liveBadgeText}>LIVE</Text>
            </View>
          </View>
          {loadingLive ? (
            <ActivityIndicator size="small" color="#818CF8" style={{ marginTop: 10 }} />
          ) : saData?.status === 'ok' ? (
            <View style={{ marginTop: 10 }}>
              <View style={s.liveMetricsRow}>
                <View style={s.liveMetric}>
                  <Text style={[s.liveMetricVal, { color: '#818CF8' }]}>{saData.overall_level}</Text>
                  <Text style={s.liveMetricLabel}>Overall</Text>
                </View>
                {Object.entries(saData.levels || {}).slice(0, 4).map(([k, v]: [string, any]) => (
                  <View key={k} style={s.liveMetric}>
                    <Text style={s.liveMetricVal}>{v.score || 0}</Text>
                    <Text style={s.liveMetricLabel}>L{k}</Text>
                  </View>
                ))}
              </View>
              <View style={s.saLevelBar}>
                {[1, 2, 3, 4, 5, 6].map(l => {
                  const score = saData.levels?.[String(l)]?.score || 0;
                  return (
                    <View key={l} style={s.saLevelSegment}>
                      <View style={[s.saLevelFill, { height: `${(score / 10) * 100}%`, backgroundColor: l === 4 ? '#F59E0B' : '#818CF8' }]} />
                      <Text style={s.saLevelNum}>{l}</Text>
                    </View>
                  );
                })}
              </View>
            </View>
          ) : (
            <Text style={s.liveNoData}>Tap to set your self-awareness levels →</Text>
          )}
        </LinearGradient>
      </TouchableOpacity>

      {/* Stub Modules */}
      <View style={s.igisGrid}>
        {[
          { key: 'astrology', label: 'Astrology', emoji: '🔮', color: '#8B5CF6', desc: 'Timing & grace insights' },
          { key: 'energy-healing', label: 'Energy Healing', emoji: '💫', color: '#EC4899', desc: 'Chakra & energy balance' },
          { key: 'manifestation', label: 'Manifestation', emoji: '🧘', color: '#14B8A6', desc: 'Visualization & affirmations' },
        ].map(mod => (
          <TouchableOpacity key={mod.key} style={s.igisCard} onPress={() => onFetchIgis(mod.key)}>
            <Text style={s.igisEmoji}>{mod.emoji}</Text>
            <Text style={s.igisLabel}>{mod.label}</Text>
            <Text style={s.igisDesc}>{mod.desc}</Text>
            <View style={[s.igisStub, { backgroundColor: mod.color + '20' }]}>
              <Ionicons name="construct" size={12} color={mod.color} />
              <Text style={[s.igisStubText, { color: mod.color }]}>Coming Soon</Text>
            </View>
          </TouchableOpacity>
        ))}
      </View>

      {/* Linked Modules Summary */}
      <Text style={s.sectionTitle}>Linked Modules</Text>

      {/* Tasks */}
      <View style={s.linkedCard}>
        <View style={s.linkedHeader}>
          <Ionicons name="clipboard" size={20} color="#3B82F6" />
          <Text style={s.linkedTitle}>CTT Tasks ({dashboard.linked_tasks.length})</Text>
        </View>
        {dashboard.linked_tasks.length === 0 ? (
          <Text style={s.linkedEmpty}>No tasks linked yet</Text>
        ) : (
          dashboard.linked_tasks.slice(0, 5).map((task: any) => (
            <View key={task.task_id} style={s.linkedItem}>
              <View style={[s.linkedDot, {
                backgroundColor: task.status === 'done' ? '#10B981' : task.status === 'blocked' ? '#EF4444' : '#F59E0B'
              }]} />
              <Text style={s.linkedItemText} numberOfLines={1}>{task.title}</Text>
              <Text style={s.linkedItemStatus}>{task.status}</Text>
            </View>
          ))
        )}
      </View>

      {/* Routines */}
      <View style={s.linkedCard}>
        <View style={s.linkedHeader}>
          <Ionicons name="leaf" size={20} color="#10B981" />
          <Text style={s.linkedTitle}>Routines ({dashboard.linked_routines.length})</Text>
        </View>
        {dashboard.linked_routines.length === 0 ? (
          <Text style={s.linkedEmpty}>No routines linked yet</Text>
        ) : (
          dashboard.linked_routines.slice(0, 5).map((r: any) => (
            <View key={r.routine_id} style={s.linkedItem}>
              <Ionicons name="flame" size={14} color="#F59E0B" />
              <Text style={s.linkedItemText} numberOfLines={1}>{r.title}</Text>
              <Text style={s.linkedItemStatus}>🔥 {r.streak || 0}</Text>
            </View>
          ))
        )}
      </View>

      {/* Decisions */}
      <View style={s.linkedCard}>
        <View style={s.linkedHeader}>
          <Ionicons name="git-branch" size={20} color="#8B5CF6" />
          <Text style={s.linkedTitle}>PRR Decisions ({dashboard.linked_decisions.length})</Text>
        </View>
        {dashboard.linked_decisions.length === 0 ? (
          <Text style={s.linkedEmpty}>No decisions linked yet</Text>
        ) : (
          dashboard.linked_decisions.slice(0, 5).map((d: any) => (
            <View key={d.decision_id} style={s.linkedItem}>
              <View style={[s.linkedDot, { backgroundColor: '#8B5CF6' }]} />
              <Text style={s.linkedItemText} numberOfLines={1}>{d.title}</Text>
              <Text style={s.linkedItemStatus}>{d.status}</Text>
            </View>
          ))
        )}
      </View>
    </View>
  );
}


// ========================
// STYLES
// ========================
const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { fontSize: 14, color: 'rgba(255,255,255,0.5)' },

  // Header
  headerBar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10 },
  headerBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.12)', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 17, fontWeight: '700', color: '#0F172A' },
  headerPhase: { fontSize: 12, color: 'rgba(255,255,255,0.6)', marginTop: 1 },

  // Sky Section
  skySection: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, height: 140 },

  starsRow: { ...StyleSheet.absoluteFillObject },
  star: { position: 'absolute', borderRadius: 4, backgroundColor: '#FFF' },

  altBar: { alignItems: 'center', width: 50 },
  altLabel: { fontSize: 9, color: 'rgba(255,255,255,0.7)', fontWeight: '700' },
  altTrack: { width: 8, height: 80, backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 4, marginVertical: 4, overflow: 'hidden', justifyContent: 'flex-end' },
  altFill: { width: '100%', backgroundColor: '#818CF8', borderRadius: 4 },
  altMinLabel: { fontSize: 8, color: 'rgba(255,255,255,0.4)' },

  planeArea: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  planeWrap: { alignItems: 'center' },
  planeIcon: { fontSize: 48 },
  speedLabel: { fontSize: 13, color: 'rgba(255,255,255,0.7)', fontWeight: '700', marginTop: 4 },
  crashBanner: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 6, paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, backgroundColor: 'rgba(0,0,0,0.4)' },
  crashText: { fontSize: 11, fontWeight: '700' },

  fuelBar: { alignItems: 'center', width: 50 },
  fuelLabel: { fontSize: 9, color: 'rgba(255,255,255,0.7)', fontWeight: '700' },
  fuelTrack: { width: 8, height: 80, backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 4, marginVertical: 4, overflow: 'hidden', justifyContent: 'flex-end' },
  fuelFill: { width: '100%', borderRadius: 4 },

  // Flight Path
  flightPathSection: { paddingHorizontal: 16, marginTop: 4 },
  pathRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  pathPoint: { alignItems: 'center' },
  pathEmoji: { fontSize: 18 },
  pathLabel: { fontSize: 10, color: 'rgba(255,255,255,0.6)', fontWeight: '700' },
  pathTrack: { flex: 1, height: 6, backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 3, position: 'relative', overflow: 'visible' },
  pathFill: { height: '100%', backgroundColor: '#818CF8', borderRadius: 3 },
  stepMarker: { position: 'absolute', top: -8, marginLeft: -8 },
  stepDot: { width: 20, height: 20, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },
  stepDotCompleted: { backgroundColor: '#10B981' },
  stepDotCurrent: { backgroundColor: '#818CF8', borderWidth: 2, borderColor: '#FFF' },
  stepDotText: { fontSize: 9, fontWeight: '800', color: '#0F172A' },

  etaRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8, flexWrap: 'wrap', gap: 4 },
  etaText: { fontSize: 11, color: 'rgba(255,255,255,0.6)', fontWeight: '600' },

  // Tabs
  tabRow: { flexDirection: 'row', paddingHorizontal: 12, marginTop: 12, gap: 6 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.06)' },
  tabActive: { backgroundColor: 'rgba(129,140,248,0.3)' },
  tabText: { fontSize: 11, fontWeight: '600', color: 'rgba(255,255,255,0.5)' },
  tabTextActive: { color: '#0F172A' },
  tabContent: { flex: 1 },

  // Section
  sectionTitle: { fontSize: 16, fontWeight: '700', color: '#0F172A', marginBottom: 12, marginTop: 8 },
  sectionDesc: { fontSize: 12, color: 'rgba(255,255,255,0.5)', marginBottom: 12, marginTop: -8 },

  // Cockpit Gauges
  gaugeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  gaugeCard: { width: '48%', flexGrow: 1, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 14 },
  gaugeHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  gaugeLabel: { fontSize: 12, fontWeight: '600', color: 'rgba(255,255,255,0.7)' },
  gaugeValue: { fontSize: 22, fontWeight: '800', marginBottom: 8 },
  gaugeTrack: { height: 4, backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' },
  gaugeFill: { height: '100%', borderRadius: 2 },

  // Status Grid
  statusGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 16 },
  statusCard: { width: '47%', flexGrow: 1, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 14, alignItems: 'center', gap: 4 },
  statusValue: { fontSize: 20, fontWeight: '800', color: '#0F172A' },
  statusLabel: { fontSize: 11, color: 'rgba(255,255,255,0.5)', fontWeight: '600' },

  // Health
  healthCard: { backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 16, marginBottom: 16 },
  healthTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A', marginBottom: 10 },
  healthRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  healthScore: { fontSize: 28, fontWeight: '800', color: '#0F172A', width: 60 },
  healthBarTrack: { flex: 1, height: 8, backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 4, overflow: 'hidden' },
  healthBarFill: { height: '100%', borderRadius: 4 },

  // Journey
  journeyCard: { backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 16 },
  journeyTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A', marginBottom: 12 },
  journeyRow: { flexDirection: 'row', alignItems: 'center' },
  journeyPoint: { flex: 1, alignItems: 'center' },
  journeyEmoji: { fontSize: 24 },
  journeyLabel: { fontSize: 12, fontWeight: '700', color: 'rgba(255,255,255,0.7)', marginTop: 4 },
  journeyDesc: { fontSize: 11, color: 'rgba(255,255,255,0.5)', textAlign: 'center', marginTop: 4 },
  journeyArrow: { paddingHorizontal: 12 },

  // Steps
  stepCard: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 14, marginBottom: 10, borderLeftWidth: 3, borderLeftColor: 'transparent' },
  stepCardCurrent: { borderLeftColor: '#818CF8', backgroundColor: 'rgba(129,140,248,0.1)' },
  stepCardCompleted: { borderLeftColor: '#10B981', backgroundColor: 'rgba(16,185,129,0.08)' },
  stepIcon: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  stepNameRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  stepName: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  currentBadge: { backgroundColor: '#818CF8', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  currentBadgeText: { fontSize: 9, fontWeight: '800', color: '#0F172A' },
  stepDesc: { fontSize: 12, color: 'rgba(255,255,255,0.5)', marginTop: 4, lineHeight: 18 },
  stepNotes: { fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 6, fontStyle: 'italic' },
  stepDate: { fontSize: 10, color: '#10B981', marginTop: 4 },

  // Gears
  gearSection: { marginTop: 16 },
  gearGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  gearCard: { width: '47%', flexGrow: 1, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 14, alignItems: 'center', gap: 6, borderWidth: 1.5, borderColor: 'transparent' },
  gearCardActive: { backgroundColor: 'rgba(129,140,248,0.12)' },
  gearCardCurrent: { borderColor: '#818CF8' },
  gearNum: { fontSize: 20, fontWeight: '800', color: 'rgba(255,255,255,0.3)' },
  gearName: { fontSize: 12, fontWeight: '700', color: 'rgba(255,255,255,0.6)', textAlign: 'center' },
  gearDesc: { fontSize: 10, color: 'rgba(255,255,255,0.4)', textAlign: 'center' },

  // Secrets
  planeDigram: { backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 20, alignItems: 'center', marginBottom: 16 },
  planeDiagramLabel: { fontSize: 13, fontWeight: '600', color: 'rgba(255,255,255,0.6)', marginBottom: 8 },
  planeDiagramRow: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  overallScoreWrap: { flexDirection: 'row', alignItems: 'baseline' },
  overallScoreNum: { fontSize: 36, fontWeight: '800', color: '#818CF8' },
  overallScoreLabel: { fontSize: 18, fontWeight: '600', color: 'rgba(255,255,255,0.5)' },
  secretCard: { backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 12, padding: 12, marginBottom: 8 },
  secretLeft: { flexDirection: 'row', alignItems: 'center' },
  secretIconWrap: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center' },
  secretNameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  secretNum: { fontSize: 11, fontWeight: '800', color: 'rgba(255,255,255,0.4)', backgroundColor: 'rgba(255,255,255,0.1)', paddingHorizontal: 5, paddingVertical: 1, borderRadius: 4 },
  secretName: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  secretPart: { fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 2 },
  secretScore: { fontSize: 16, fontWeight: '800' },
  secretBar: { height: 3, backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 2, marginTop: 8, overflow: 'hidden' },
  secretBarFill: { height: '100%', borderRadius: 2 },

  // GIS
  gisGrid: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  gisCard: { flex: 1, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 14, alignItems: 'center', gap: 6 },
  gisLabel: { fontSize: 12, fontWeight: '700', color: '#0F172A' },
  gisScore: { fontSize: 18, fontWeight: '800', color: '#818CF8' },
  gisDesc: { fontSize: 10, color: 'rgba(255,255,255,0.4)', textAlign: 'center' },

  // iGIS
  igisGrid: { flexDirection: 'row', gap: 10, marginBottom: 16, flexWrap: 'wrap' },
  igisCard: { width: '31%', flexGrow: 1, backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 12, alignItems: 'center', gap: 4 },
  igisEmoji: { fontSize: 28 },
  igisLabel: { fontSize: 11, fontWeight: '700', color: '#0F172A', textAlign: 'center' },
  igisDesc: { fontSize: 9, color: 'rgba(255,255,255,0.4)', textAlign: 'center' },
  igisStub: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 6, paddingVertical: 3, borderRadius: 6, marginTop: 4 },
  igisStubText: { fontSize: 9, fontWeight: '700' },

  // Live iGIS Cards
  liveIgisCard: { marginBottom: 12, borderRadius: 14, overflow: 'hidden' },
  liveIgisGradient: { padding: 14 },
  liveIgisHeader: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  liveIgisEmoji: { fontSize: 28 },
  liveIgisTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  liveIgisDesc: { fontSize: 11, color: 'rgba(255,255,255,0.5)', marginTop: 2 },
  liveBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: 'rgba(16,185,129,0.2)', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#10B981' },
  liveBadgeText: { fontSize: 9, fontWeight: '800', color: '#10B981' },
  liveMetricsRow: { flexDirection: 'row', justifyContent: 'space-around', marginTop: 10, paddingTop: 10, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.1)' },
  liveMetric: { alignItems: 'center' },
  liveMetricVal: { fontSize: 18, fontWeight: '800', color: '#0F172A' },
  liveMetricLabel: { fontSize: 9, color: 'rgba(255,255,255,0.5)', fontWeight: '600', marginTop: 2 },
  liveNoData: { fontSize: 12, color: 'rgba(255,255,255,0.4)', marginTop: 10, fontStyle: 'italic' },
  saLevelBar: { flexDirection: 'row', gap: 6, marginTop: 10, height: 50, alignItems: 'flex-end' },
  saLevelSegment: { flex: 1, height: '100%', backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 4, justifyContent: 'flex-end', alignItems: 'center', overflow: 'hidden' },
  saLevelFill: { width: '100%', borderRadius: 4 },
  saLevelNum: { fontSize: 8, fontWeight: '700', color: 'rgba(255,255,255,0.5)', marginBottom: 2, position: 'absolute', bottom: -1 },

  // Linked Modules
  linkedCard: { backgroundColor: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: 14, marginBottom: 12 },
  linkedHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  linkedTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  linkedEmpty: { fontSize: 12, color: 'rgba(255,255,255,0.4)' },
  linkedItem: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: 'rgba(255,255,255,0.05)' },
  linkedDot: { width: 8, height: 8, borderRadius: 4 },
  linkedItemText: { flex: 1, fontSize: 12, color: 'rgba(255,255,255,0.7)' },
  linkedItemStatus: { fontSize: 11, color: 'rgba(255,255,255,0.5)', fontWeight: '600' },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', padding: 20 },
  modalCard: { backgroundColor: COLORS.surface, borderRadius: 20, padding: 20 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  modalDesc: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 20, marginBottom: 16 },
  modalLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 6 },
  modalInput: { backgroundColor: COLORS.background, borderRadius: 12, padding: 14, fontSize: 14, color: COLORS.textPrimary, minHeight: 80, textAlignVertical: 'top', borderWidth: 1, borderColor: COLORS.border },
  modalActions: { flexDirection: 'row', gap: 10, marginTop: 16 },
  modalBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, alignItems: 'center', backgroundColor: COLORS.background },
  modalBtnText: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },

  // iGIS Modal
  igisHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  stubBanner: { flexDirection: 'row', gap: 8, backgroundColor: '#FEF3C7', padding: 12, borderRadius: 10, marginBottom: 12 },
  stubText: { flex: 1, fontSize: 12, color: '#92400E', lineHeight: 18 },
  stubData: { gap: 8 },
  stubRow: { backgroundColor: COLORS.background, padding: 10, borderRadius: 8 },
  stubKey: { fontSize: 11, fontWeight: '700', color: COLORS.textSecondary, textTransform: 'capitalize', marginBottom: 4 },
  stubVal: { fontSize: 13, color: COLORS.textPrimary, lineHeight: 20 },
});
