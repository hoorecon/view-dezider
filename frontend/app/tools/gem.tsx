import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, Alert, ActivityIndicator,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import ProjectStatusPicker from '../../src/components/decisions/ProjectStatusPicker';

const LIFE_AREAS = [
  {id:'career',name:'Career',icon:'briefcase',c:'#3B82F6'},
  {id:'finance',name:'Finance',icon:'cash',c:'#10B981'},
  {id:'relationships',name:'Relationships',icon:'heart',c:'#EF4444'},
  {id:'holistic_health',name:'Health',icon:'fitness',c:'#F59E0B'},
  {id:'assets',name:'Assets',icon:'home',c:'#8B5CF6'},
  {id:'knowledge_skills',name:'Knowledge',icon:'school',c:'#06B6D4'},
  {id:'social_image',name:'Social Image',icon:'people',c:'#EC4899'},
  {id:'social_contributions',name:'Social',icon:'globe',c:'#14B8A6'},
  {id:'hobbies_entertainment',name:'Hobbies',icon:'game-controller',c:'#F97316'},
  {id:'spirituality_religion',name:'Spirituality',icon:'leaf',c:'#84CC16'},
];
const GOAL_TYPES = [
  {id:'problem',label:'Problems',icon:'alert-circle',c:'#EF4444'},
  {id:'need',label:'Needs',icon:'bulb',c:'#F59E0B'},
  {id:'aspiration',label:'Aspirations',icon:'rocket',c:'#10B981'},
];

export default function GEMScreen() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<any>(null);
  const [goals, setGoals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedArea, setSelectedArea] = useState<string|null>(null);
  const [selectedType, setSelectedType] = useState<string|null>(null);

  const fetchData = async () => {
    try {
      const params = new URLSearchParams();
      if(selectedArea) params.append('life_area', selectedArea);
      if(selectedType) params.append('goal_type', selectedType);
      const [dashRes, goalsRes] = await Promise.all([
        api.get('/gem/dashboard'),
        api.get(`/gem/goals?${params}`),
      ]);
      setDashboard(dashRes.data);
      setGoals(goalsRes.data || []);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { fetchData(); }, [selectedArea, selectedType]));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const handleDelete = (id: string) => {
    showAlert('Delete','Delete this goal?',[
      {text:'Cancel',style:'cancel'},
      {text:'Delete',style:'destructive',onPress:async()=>{
        try { await api.delete(`/gem/goals/${id}`); fetchData(); }
        catch(e) { showAlert('Error','Failed'); }
      }},
    ]);
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#0D9488','#14B8A6']} style={s.header}>
        <TouchableOpacity onPress={()=>router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{flex:1}}>
          <Text style={s.headerTitle}>Goals Execution Manager</Text>
          <Text style={s.headerSub}>Track Problems, Needs & Aspirations across Life Areas</Text>
        </View>
        <TouchableOpacity onPress={()=>router.push('/tools/gem-goal')} style={s.addBtn}>
          <Ionicons name="add" size={24} color="#FFF" />
        </TouchableOpacity>
      </LinearGradient>

      {/* Summary Cards */}
      {dashboard && (
        <View style={s.summaryRow}>
          {GOAL_TYPES.map(gt=>(
            <TouchableOpacity key={gt.id}
              style={[s.summaryCard, selectedType===gt.id && {borderColor:gt.c, borderWidth:2}]}
              onPress={()=>setSelectedType(selectedType===gt.id?null:gt.id)}>
              <Ionicons name={gt.icon as any} size={22} color={gt.c} />
              <Text style={[s.summaryNum,{color:gt.c}]}>{dashboard.by_type?.[gt.id]||0}</Text>
              <Text style={s.summaryLabel}>{gt.label}</Text>
            </TouchableOpacity>
          ))}
          <View style={s.summaryCard}>
            <Text style={[s.summaryNum,{color:COLORS.primary}]}>{dashboard.avg_progress||0}%</Text>
            <Text style={s.summaryLabel}>Avg Progress</Text>
          </View>
        </View>
      )}

      {/* Life Areas Grid */}
      <Text style={s.sectionTitle}>Life Areas</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{maxHeight:50}}>
        <View style={s.areaRow}>
          {LIFE_AREAS.map(a=>{
            const count = dashboard?.by_area?.[a.id]?.total||0;
            return (
              <TouchableOpacity key={a.id}
                style={[s.areaChip, selectedArea===a.id && {backgroundColor:a.c, borderColor:a.c}]}
                onPress={()=>setSelectedArea(selectedArea===a.id?null:a.id)}>
                <Ionicons name={a.icon as any} size={14} color={selectedArea===a.id?'#FFF':a.c} />
                <Text style={[s.areaText, selectedArea===a.id && {color:'#FFF'}]}>{a.name}</Text>
                {count>0 && <View style={[s.areaBadge,{backgroundColor:a.c}]}><Text style={s.areaBadgeText}>{count}</Text></View>}
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>

      {/* Goals List */}
      <ScrollView style={s.scroll} contentContainerStyle={s.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
        {loading ? <ActivityIndicator size="large" color={COLORS.primary} style={{marginTop:40}} /> :
         goals.length===0 ? (
          <View style={s.empty}>
            <Ionicons name="diamond-outline" size={56} color={COLORS.textMuted} />
            <Text style={s.emptyTitle}>No Goals Yet</Text>
            <Text style={s.emptySub}>Define your Problems, Needs & Aspirations across Life Areas</Text>
            <TouchableOpacity style={s.emptyBtn} onPress={()=>router.push('/tools/gem-goal')}>
              <Text style={{color:'#FFF',fontWeight:'600'}}>Create Goal</Text>
            </TouchableOpacity>
          </View>
        ) : goals.map(g=>{
          const typeMeta = GOAL_TYPES.find(t=>t.id===g.goal_type)||GOAL_TYPES[2];
          const areaMeta = LIFE_AREAS.find(a=>a.id===g.life_area);
          return (
            <TouchableOpacity key={g.goal_id} style={[s.goalCard,{borderLeftColor:typeMeta.c}]}
              onPress={()=>router.push({pathname:'/tools/gem-goal',params:{id:g.goal_id}})}>
              <View style={s.goalHeader}>
                <View style={[s.typeBadge,{backgroundColor:typeMeta.c+'15'}]}>
                  <Ionicons name={typeMeta.icon as any} size={14} color={typeMeta.c} />
                  <Text style={[s.typeText,{color:typeMeta.c}]}>{typeMeta.label.slice(0,-1)}</Text>
                </View>
                {areaMeta && <Text style={[s.areaLabel,{color:areaMeta.c}]}>{areaMeta.name}</Text>}
                <View style={{flex:1}} />
                <TouchableOpacity onPress={()=>handleDelete(g.goal_id)}>
                  <Ionicons name="trash-outline" size={16} color={COLORS.error} />
                </TouchableOpacity>
              </View>
              <Text style={s.goalTitle} numberOfLines={2}>{g.title||'Untitled'}</Text>
              {g.smart_goal ? <Text style={s.goalSmart} numberOfLines={1}>{g.smart_goal}</Text> : null}
              {/* Project Status (Enhancement #6/#7 - cascades to CTT tasks + routines) */}
              <View style={{ marginTop: 6 }}>
                <ProjectStatusPicker
                  goalId={g.goal_id}
                  currentStatus={g.project_status || 'open'}
                  onChange={() => fetchData()}
                />
              </View>
              {/* Progress */}
              <View style={s.progressRow}>
                <View style={s.progressBar}>
                  <View style={[s.progressFill,{width:`${g.progress_percent||0}%`,backgroundColor:typeMeta.c}]} />
                </View>
                <Text style={s.progressText}>{g.progress_percent||0}%</Text>
              </View>
              <View style={s.goalMeta}>
                <Text style={s.metaText}>{g.status?.toUpperCase()}</Text>
                {g.target_date && <Text style={s.metaDate}>Target: {g.target_date}</Text>}
                <Text style={s.metaLinks}>
                  {(g.linked_decisions?.length||0)+(g.linked_solution_finders?.length||0)+(g.linked_solution_matrices?.length||0)} linked items
                </Text>
              </View>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container:{flex:1,backgroundColor:COLORS.background},
  header:{flexDirection:'row',alignItems:'center',padding:16,paddingBottom:20},
  backBtn:{width:40,height:40,borderRadius:20,backgroundColor:'rgba(255,255,255,0.2)',justifyContent:'center',alignItems:'center',marginRight:12},
  headerTitle:{fontSize:18,fontWeight:'700',color: '#0F172A'},
  headerSub:{fontSize:11,color:'rgba(255,255,255,0.7)',marginTop:2},
  addBtn:{width:40,height:40,borderRadius:20,backgroundColor:'rgba(255,255,255,0.2)',justifyContent:'center',alignItems:'center'},
  summaryRow:{flexDirection:'row',padding:12,gap:8},
  summaryCard:{flex:1,backgroundColor:COLORS.white,borderRadius:12,padding:10,alignItems:'center',borderWidth:1,borderColor:COLORS.border},
  summaryNum:{fontSize:22,fontWeight:'800'},
  summaryLabel:{fontSize:9,fontWeight:'600',color:COLORS.textMuted,marginTop:2,textAlign:'center'},
  sectionTitle:{fontSize:14,fontWeight:'700',color:COLORS.textPrimary,paddingHorizontal:16,paddingTop:8},
  areaRow:{flexDirection:'row',paddingHorizontal:16,gap:6,paddingVertical:8},
  areaChip:{flexDirection:'row',alignItems:'center',gap:4,paddingHorizontal:10,paddingVertical:6,borderRadius:16,borderWidth:1,borderColor:COLORS.border,backgroundColor:COLORS.white},
  areaText:{fontSize:11,fontWeight:'600',color:COLORS.textMuted},
  areaBadge:{width:16,height:16,borderRadius:8,alignItems:'center',justifyContent:'center'},
  areaBadgeText:{fontSize:9,fontWeight:'700',color: '#0F172A'},
  scroll:{flex:1},scrollContent:{padding:16,paddingBottom:32},
  empty:{alignItems:'center',paddingTop:40},
  emptyTitle:{fontSize:18,fontWeight:'700',color:COLORS.textPrimary,marginTop:16},
  emptySub:{fontSize:14,color:COLORS.textSecondary,textAlign:'center',marginTop:8,paddingHorizontal:32},
  emptyBtn:{marginTop:20,paddingHorizontal:24,paddingVertical:12,backgroundColor:'#0D9488',borderRadius:12},
  goalCard:{backgroundColor:COLORS.white,borderRadius:14,padding:14,marginBottom:10,borderWidth:1,borderColor:COLORS.border,borderLeftWidth:4},
  goalHeader:{flexDirection:'row',alignItems:'center',gap:8,marginBottom:6},
  typeBadge:{flexDirection:'row',alignItems:'center',gap:4,paddingHorizontal:8,paddingVertical:3,borderRadius:8},
  typeText:{fontSize:11,fontWeight:'700'},
  areaLabel:{fontSize:11,fontWeight:'600'},
  goalTitle:{fontSize:15,fontWeight:'600',color:COLORS.textPrimary},
  goalSmart:{fontSize:12,color:COLORS.textSecondary,marginTop:2},
  progressRow:{flexDirection:'row',alignItems:'center',gap:8,marginTop:10},
  progressBar:{flex:1,height:6,borderRadius:3,backgroundColor:COLORS.divider},
  progressFill:{height:6,borderRadius:3},
  progressText:{fontSize:12,fontWeight:'700',color:COLORS.textPrimary,width:36},
  goalMeta:{flexDirection:'row',gap:10,marginTop:8,borderTopWidth:1,borderTopColor:COLORS.divider,paddingTop:6},
  metaText:{fontSize:10,fontWeight:'600',color:COLORS.textMuted},
  metaDate:{fontSize:10,color:COLORS.textSecondary},
  metaLinks:{fontSize:10,color:COLORS.primary,fontWeight:'500'},
});
