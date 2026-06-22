import React, { useState, useEffect } from 'react';
import { showAlert } from '../../src/utils/alert';
import { useLifeAreas } from '../../src/utils/useLifeAreas';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, Alert, ActivityIndicator, Platform, KeyboardAvoidingView, Modal,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import Slider from '@react-native-community/slider';
import LinkedGoalMilestonesView from '../../src/components/LinkedGoalMilestonesView';
import { safeBack } from '../../src/utils/navigation';

// LIFE_AREAS array moved into the component (catalog-driven).
const GOAL_TYPES = [{id:'problem',label:'Problem',icon:'alert-circle',c:'#EF4444'},{id:'need',label:'Need',icon:'bulb',c:'#F59E0B'},{id:'aspiration',label:'Aspiration',icon:'rocket',c:'#10B981'}];
const PRIORITIES = [{id:'critical',c:'#EF4444'},{id:'high',c:'#F59E0B'},{id:'medium',c:'#3B82F6'},{id:'low',c:'#6B7280'}];
const STATUSES = ['active','completed','on_hold','cancelled'];

export default function GEMGoalScreen() {
  // LIFE_AREAS now flows from the Admin Central Catalog via the
  // useLifeAreas() hook (single source of truth across the app).
  // Adapter preserves both old (`c`, `name`) and new (`color`,
  // `label`, `slug`, `node_id`) field names so the rest of this file
  // continues to compile without ripple-effect edits.
  const { items: _laItems } = useLifeAreas();
  const LIFE_AREAS = _laItems.map(a => ({
    id: a.id,
    node_id: a.node_id,
    slug: a.slug,
    name: a.name,
    label: a.name,
    short: a.name,
    icon: a.icon,
    color: a.color,
    c: a.color,
  }));

  const router = useRouter();
  const { id } = useLocalSearchParams();
  const editId = id as string|undefined;
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [smartGoal, setSmartGoal] = useState('');
  const [lifeArea, setLifeArea] = useState('');
  const [goalType, setGoalType] = useState('aspiration');
  const [priority, setPriority] = useState('medium');
  const [status, setStatus] = useState('active');
  const [targetDate, setTargetDate] = useState('');
  const [progress, setProgress] = useState(0);

  // ── Phase 5: Linked SMART Goal (from Goal Setter) ──
  const [linkedSmartGoalId, setLinkedSmartGoalId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [smartGoalsList, setSmartGoalsList] = useState<any[]>([]);
  const [smartGoalsLoading, setSmartGoalsLoading] = useState(false);

  useEffect(() => { if(editId) loadGoal(); }, [editId]);

  const loadSmartGoals = async () => {
    setSmartGoalsLoading(true);
    try {
      const res = await api.get('/goal-setter/goals');
      setSmartGoalsList(res.data || []);
    } catch (e) { console.error('Load SMART goals', e); }
    finally { setSmartGoalsLoading(false); }
  };

  const loadGoal = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/gem/goals/${editId}`);
      const d = res.data;
      setTitle(d.title||''); setDescription(d.description||''); setSmartGoal(d.smart_goal||'');
      setLifeArea(d.life_area||'');
      // Backward-compat: PNA used to write goal_type as 'project'/'objective'/'task',
      // and earlier GEM versions used 'long_term'. Normalise to the canonical 3-way
      // vocabulary supported by GOAL_TYPES.
      const rawType = (d.goal_type || 'aspiration') as string;
      const typeMap: Record<string, string> = {
        project: 'problem', task: 'problem',
        objective: 'need',
        long_term: 'aspiration', short_term: 'need',
        problem: 'problem', need: 'need', aspiration: 'aspiration',
      };
      setGoalType(typeMap[rawType] || 'aspiration');
      setPriority(d.priority||'medium'); setStatus(d.status||'active');
      setTargetDate(d.target_date||''); setProgress(d.progress_percent||0);
      setLinkedSmartGoalId(d.linked_smart_goal_id || null);
    } catch(e) { showAlert('Error','Failed to load'); }
    finally { setLoading(false); }
  };

  const handleSave = async () => {
    if(!title.trim()) { showAlert('Required','Goal title is required'); return; }
    if(!lifeArea) { showAlert('Required','Select a life area'); return; }
    setSaving(true);
    try {
      const payload = {
        title, description, smart_goal: smartGoal, life_area: lifeArea,
        goal_type: goalType, priority, status,
        target_date: targetDate||null, progress_percent: Math.round(progress),
        linked_smart_goal_id: linkedSmartGoalId,
      };
      if(editId) await api.put(`/gem/goals/${editId}`, payload);
      else await api.post('/gem/goals', payload);
      showAlert('Saved','Goal saved!', [{text:'OK',onPress:()=>safeBack(router)}]);
    } catch(e) { showAlert('Error','Failed to save'); }
    finally { setSaving(false); }
  };

  const openPicker = () => { loadSmartGoals(); setPickerOpen(true); };
  const selectSmartGoal = (id: string) => { setLinkedSmartGoalId(id); setPickerOpen(false); };
  const unlinkSmartGoal = () => {
    showAlert('Unlink SMART Goal', 'Remove the link to this SMART Goal? Milestone progress already saved is preserved in Goal Setter.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Unlink', style: 'destructive', onPress: () => setLinkedSmartGoalId(null) },
    ]);
  };

  // Quick launch actions
  // The "Launch Decision" CTA used to route to /prr/new (the duplicate dezider
  // module that was removed). It now seeds a fresh entry in the main MyDezider
  // flow with the current GEM goal pre-linked.
  const launchDecision = () => router.push({
    pathname: '/tools/new-decision',
    params: {
      module: 'dezider',
      linked_goal_id: editId || '',
      linked_goal_title: title || '',
    },
  } as any);
  const launchSolutionFinder = () => router.push('/tools/solution-finder');
  const launchSolutionMatrix = () => router.push('/tools/solution-matrix');

  if(loading) return <SafeAreaView style={st.c}><ActivityIndicator size="large" color={COLORS.primary} style={{marginTop:40}} /></SafeAreaView>;

  const typeMeta = GOAL_TYPES.find(t=>t.id===goalType)||GOAL_TYPES[2];

  return (
    <SafeAreaView style={st.c} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS==='ios'?'padding':'height'} style={{flex:1}}>
        <LinearGradient colors={['#0D9488','#14B8A6']} style={st.hdr}>
          <TouchableOpacity onPress={()=>safeBack(router)} style={st.back}>
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <Text style={st.hdrT}>{editId?'Edit Goal':'New Goal'}</Text>
        </LinearGradient>
        <ScrollView style={{flex:1}} contentContainerStyle={{padding:16,paddingBottom:40}} showsVerticalScrollIndicator={false}>
          {/* Goal Type */}
          <Text style={st.lbl}>Goal Type</Text>
          <View style={st.typeRow}>
            {GOAL_TYPES.map(gt=>(
              <TouchableOpacity key={gt.id}
                style={[st.typeCard, goalType===gt.id && {backgroundColor:gt.c, borderColor:gt.c}]}
                onPress={()=>setGoalType(gt.id)}>
                <Ionicons name={gt.icon as any} size={22} color={goalType===gt.id?'#FFF':gt.c} />
                <Text style={[st.typeLabel, goalType===gt.id && {color:'#FFF'}]}>{gt.label}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Life Area */}
          <Text style={st.lbl}>Life Area *</Text>
          <View style={st.chipRow}>
            {LIFE_AREAS.map(a=>(
              <TouchableOpacity key={a.id} style={[st.chip, lifeArea===a.id && st.chipA]} onPress={()=>setLifeArea(a.id)}>
                <Ionicons name={a.icon as any} size={14} color={lifeArea===a.id?'#FFF':COLORS.primary} />
                <Text style={[st.chipT, lifeArea===a.id && {color:'#FFF'}]}>{a.name}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Title & Description */}
          <Text style={st.lbl}>Title *</Text>
          <TextInput style={st.inp} value={title} onChangeText={setTitle} placeholder="Goal title" placeholderTextColor={COLORS.textMuted} />
          <Text style={st.lbl}>Description</Text>
          <TextInput style={st.ta} value={description} onChangeText={setDescription} placeholder="Describe your goal..." placeholderTextColor={COLORS.textMuted} multiline numberOfLines={3} />
          <Text style={st.lbl}>SMART Goal</Text>
          <TextInput style={st.ta} value={smartGoal} onChangeText={setSmartGoal} placeholder="Specific, Measurable, Achievable, Relevant, Time-bound" placeholderTextColor={COLORS.textMuted} multiline numberOfLines={3} />

          {/* ── Phase 5: Linked SMART Goal (Goal Setter ↔ GEM) ── */}
          <Text style={st.lbl}>Linked SMART Goal</Text>
          {linkedSmartGoalId ? (
            <LinkedGoalMilestonesView
              smartGoalId={linkedSmartGoalId}
              onUnlink={unlinkSmartGoal}
            />
          ) : (
            <TouchableOpacity style={st.linkBtn} onPress={openPicker}>
              <Ionicons name="link" size={16} color="#059669" />
              <View style={{ flex: 1 }}>
                <Text style={st.linkBtnText}>Link a SMART Goal</Text>
                <Text style={st.linkBtnSub}>Surface its milestones here for execution</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color="#059669" />
            </TouchableOpacity>
          )}

          {/* Priority */}
          <Text style={st.lbl}>Priority</Text>
          <View style={st.chipRow}>
            {PRIORITIES.map(p=>(
              <TouchableOpacity key={p.id} style={[st.chip, priority===p.id && {backgroundColor:p.c,borderColor:p.c}]} onPress={()=>setPriority(p.id)}>
                <Text style={[st.chipT, priority===p.id && {color:'#FFF'}]}>{p.id.toUpperCase()}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Status */}
          <Text style={st.lbl}>Status</Text>
          <View style={st.chipRow}>
            {STATUSES.map(s=>(
              <TouchableOpacity key={s} style={[st.chip, status===s && st.chipA]} onPress={()=>setStatus(s)}>
                <Text style={[st.chipT, status===s && {color:'#FFF'}]}>{s.replace('_',' ').toUpperCase()}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Target Date */}
          <Text style={st.lbl}>Target Date</Text>
          <TextInput style={st.inp} value={targetDate} onChangeText={setTargetDate} placeholder="DD/MM/YYYY" placeholderTextColor={COLORS.textMuted} />

          {/* Progress */}
          <Text style={st.lbl}>Progress: {Math.round(progress)}%</Text>
          <View style={st.sliderRow}>
            <Slider
              style={{flex:1,height:40}}
              minimumValue={0} maximumValue={100} step={5}
              value={progress} onValueChange={setProgress}
              minimumTrackTintColor={typeMeta.c} maximumTrackTintColor={COLORS.divider}
              thumbTintColor={typeMeta.c}
            />
          </View>

          {/* Quick Launch (only in edit mode) */}
          {editId && (
            <View style={st.launchSection}>
              <Text style={st.sec}>Launch Action</Text>
              <Text style={{fontSize:12,color:COLORS.textMuted,marginBottom:8}}>Start a new Decision or Solution Finder for this goal</Text>
              <View style={st.launchRow}>
                <TouchableOpacity style={[st.launchBtn,{backgroundColor:'#8E24AA'}]} onPress={launchDecision}>
                  <Ionicons name="git-branch" size={18} color="#FFF" />
                  <Text style={st.launchText}>Decision</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[st.launchBtn,{backgroundColor:'#00BCD4'}]} onPress={launchSolutionFinder}>
                  <Ionicons name="search" size={18} color="#FFF" />
                  <Text style={st.launchText}>Sol. Finder</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[st.launchBtn,{backgroundColor:'#E91E63'}]} onPress={launchSolutionMatrix}>
                  <Ionicons name="grid" size={18} color="#FFF" />
                  <Text style={st.launchText}>Sol. Matrix</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        </ScrollView>
        <View style={st.bottom}>
          <TouchableOpacity style={[st.saveBtn, saving && {opacity:0.7}]} onPress={handleSave} disabled={saving}>
            {saving ? <ActivityIndicator size="small" color="#FFF" /> :
              <><Ionicons name="checkmark-circle" size={18} color="#FFF" /><Text style={st.saveTxt}>Save Goal</Text></>}
          </TouchableOpacity>
        </View>

        {/* ── SMART Goal Picker Modal ── */}
        <Modal visible={pickerOpen} transparent animationType="slide" onRequestClose={() => setPickerOpen(false)}>
          <View style={st.modalOverlay}>
            <View style={st.modalBox}>
              <View style={st.modalHead}>
                <Ionicons name="link" size={18} color="#059669" />
                <Text style={st.modalTitle}>Select SMART Goal to Link</Text>
                <TouchableOpacity onPress={() => setPickerOpen(false)}>
                  <Ionicons name="close" size={22} color={COLORS.textSecondary} />
                </TouchableOpacity>
              </View>
              <Text style={st.modalHelp}>
                Linking surfaces the goal&apos;s milestones inside this GEM card. Structure stays read-only; status &amp; progress remain editable.
              </Text>
              {smartGoalsLoading ? (
                <ActivityIndicator color={COLORS.primary} style={{ padding: 20 }} />
              ) : smartGoalsList.length === 0 ? (
                <View style={st.emptyPick}>
                  <Ionicons name="flag-outline" size={36} color={COLORS.textMuted} />
                  <Text style={st.emptyPickText}>No SMART Goals yet. Create one in Goal Setter first.</Text>
                  <TouchableOpacity style={st.gotoBtn} onPress={() => { setPickerOpen(false); router.push('/tools/goal-setter'); }}>
                    <Text style={st.gotoBtnText}>Open Goal Setter</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <ScrollView style={{ maxHeight: 420 }}>
                  {smartGoalsList.map((g: any) => (
                    <TouchableOpacity key={g.goal_id} style={st.pickRow} onPress={() => selectSmartGoal(g.goal_id)}>
                      <View style={{ flex: 1 }}>
                        <Text style={st.pickTitle} numberOfLines={1}>{g.title}</Text>
                        <Text style={st.pickSub}>
                          {(g.milestones || []).length} milestones · {(g.metrics || []).length} metrics · {g.status || 'active'}
                        </Text>
                      </View>
                      <Ionicons name="chevron-forward" size={16} color={COLORS.textMuted} />
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              )}
            </View>
          </View>
        </Modal>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  c:{flex:1,backgroundColor:COLORS.background},
  hdr:{flexDirection:'row',alignItems:'center',padding:16,paddingBottom:20},
  back:{width:40,height:40,borderRadius:20,backgroundColor:'rgba(255,255,255,0.2)',justifyContent:'center',alignItems:'center',marginRight:12},
  hdrT:{fontSize:18,fontWeight:'700',color: '#0F172A'},
  lbl:{fontSize:13,fontWeight:'600',color:COLORS.textPrimary,marginTop:14,marginBottom:4},
  sec:{fontSize:15,fontWeight:'700',color:COLORS.primary,marginBottom:2},
  inp:{backgroundColor:COLORS.white,borderRadius:10,borderWidth:1,borderColor:COLORS.border,paddingHorizontal:14,paddingVertical:10,fontSize:14,color:COLORS.textPrimary,marginBottom:4},
  ta:{backgroundColor:COLORS.white,borderRadius:10,borderWidth:1,borderColor:COLORS.border,paddingHorizontal:14,paddingVertical:10,fontSize:14,color:COLORS.textPrimary,minHeight:70,textAlignVertical:'top',marginBottom:4},
  typeRow:{flexDirection:'row',gap:10},
  typeCard:{flex:1,alignItems:'center',gap:6,paddingVertical:14,borderRadius:12,borderWidth:1,borderColor:COLORS.border,backgroundColor:COLORS.white},
  typeLabel:{fontSize:12,fontWeight:'700',color:COLORS.textPrimary},
  chipRow:{flexDirection:'row',flexWrap:'wrap',gap:6,marginBottom:4},
  chip:{flexDirection:'row',alignItems:'center',gap:4,paddingHorizontal:12,paddingVertical:6,borderRadius:16,borderWidth:1,borderColor:COLORS.border,backgroundColor:COLORS.white},
  chipA:{backgroundColor:COLORS.primary,borderColor:COLORS.primary},
  chipT:{fontSize:11,fontWeight:'600',color:COLORS.textMuted},
  sliderRow:{paddingHorizontal:4},
  launchSection:{marginTop:20,padding:14,backgroundColor:COLORS.white,borderRadius:14,borderWidth:1,borderColor:COLORS.border},
  launchRow:{flexDirection:'row',gap:8},
  launchBtn:{flex:1,flexDirection:'row',alignItems:'center',justifyContent:'center',gap:6,paddingVertical:12,borderRadius:10},
  launchText:{fontSize:11,fontWeight:'700',color: '#0F172A'},
  bottom:{padding:16,borderTopWidth:1,borderTopColor:COLORS.border,backgroundColor:COLORS.white},
  saveBtn:{flexDirection:'row',alignItems:'center',justifyContent:'center',gap:6,backgroundColor:'#0D9488',borderRadius:12,paddingVertical:14},
  saveTxt:{fontSize:15,fontWeight:'700',color: '#0F172A'},

  // ── Phase 5: Linked SMART Goal ──
  linkBtn: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, borderRadius: 12, backgroundColor: '#F0FDF4', borderWidth: 1, borderColor: '#A7F3D0', marginTop: 6 },
  linkBtnText: { fontSize: 14, fontWeight: '700', color: '#065F46' },
  linkBtnSub: { fontSize: 11, color: '#047857', marginTop: 1 },

  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalBox: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 18, maxHeight: '85%' },
  modalHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  modalTitle: { flex: 1, fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  modalHelp: { fontSize: 12, color: COLORS.textMuted, marginBottom: 12, lineHeight: 16 },
  pickRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, marginBottom: 6, backgroundColor: '#FAFAFA' },
  pickTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  pickSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  emptyPick: { alignItems: 'center', padding: 30, gap: 10 },
  emptyPickText: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center' },
  gotoBtn: { paddingHorizontal: 18, paddingVertical: 10, borderRadius: 10, backgroundColor: '#059669' },
  gotoBtnText: { fontSize: 13, fontWeight: '700', color: '#FFFFFF' },
});
