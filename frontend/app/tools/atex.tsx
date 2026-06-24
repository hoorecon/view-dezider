/**
 * ATEX · Effort Estimation calculator.
 * Sub-tasks, QC (SCC mandatory), IP, RS, PB, Risks → EE+MB+PB+RM=TT.
 * Start-date + holidays per week → auto end-date.
 */
import React, { useState, useMemo, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, Modal } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

interface SubTask { title: string; effort_minutes: number; ip_level: string; support_needs: string[]; notes?: string; }
interface RiskItem { category: string; description: string; mitigation_minutes: number; contingency_minutes: number; }

export default function ATEXScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const sourceModule = (params.source as string) || 'manual';
  const sourceRefId = (params.ref_id as string) || undefined;
  const initialTitle = (params.title as string) || '';

  const [taskTitle, setTaskTitle] = useState(initialTitle);
  const [priority, setPriority] = useState<'P0'|'P1'|'P2'|'P3'>('P2');
  const [scc, setScc] = useState('');
  const [selfSat, setSelfSat] = useState('');
  const [ipSummary, setIpSummary] = useState('');
  const [supportSummary, setSupportSummary] = useState('');
  const [pbMinutes, setPbMinutes] = useState(0);
  const [bufferPct, setBufferPct] = useState(7.5);
  const [startDate, setStartDate] = useState('');
  const [workHours, setWorkHours] = useState(8);
  const [holidaysPerWeek, setHolidaysPerWeek] = useState(1);
  const [subTasks, setSubTasks] = useState<SubTask[]>([{ title: '', effort_minutes: 30, ip_level: 'high', support_needs: [] }]);
  const [risks, setRisks] = useState<RiskItem[]>([]);
  const [calc, setCalc] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickTasks, setPickTasks] = useState<any[]>([]);
  const [pickLoading, setPickLoading] = useState(false);
  const openPicker = async () => {
    setPickerOpen(true); setPickLoading(true);
    try {
      // Pull from BOTH the Action Tracker (universal inbox) and the CTT
      // (project tracker) so any existing task can seed an ATEX estimate.
      const [actionRes, cttRes] = await Promise.allSettled([
        api.get('/action-items'),
        api.get('/ctt/tasks?status=all'),
      ]);
      const merged: any[] = [];
      const seen = new Set<string>();
      const push = (id: string, title: string, kind: string) => {
        const t = (title || '').trim();
        if (!t) return;
        const key = t.toLowerCase();
        if (seen.has(key)) return;
        seen.add(key);
        merged.push({ id, title: t, _kind: kind });
      };
      if (actionRes.status === 'fulfilled' && Array.isArray(actionRes.value.data)) {
        for (const a of actionRes.value.data) push(a.action_id || a.id, a.title || a.task, 'action');
      }
      if (cttRes.status === 'fulfilled' && Array.isArray(cttRes.value.data)) {
        for (const c of cttRes.value.data) push(c.task_id || c.id, c.task || c.title, c.recurrence_type === 'recurring' || c.type === 'routine' ? 'routine' : 'ctt');
      }
      setPickTasks(merged);
    } catch { setPickTasks([]); }
    finally { setPickLoading(false); }
  };
  const [templates, setTemplates] = useState<any[]>([]);
  const [saveTpl, setSaveTpl] = useState({ on: false, name: '' });

  useEffect(() => { (async () => { try { const { data } = await api.get('/atex/templates'); setTemplates(data?.templates || []); } catch{} })(); }, []);

  const totalEffort = useMemo(() => subTasks.reduce((s, t) => s + (Number(t.effort_minutes)||0), 0), [subTasks]);

  const addSub = () => setSubTasks(arr => [...arr, { title: '', effort_minutes: 30, ip_level: 'high', support_needs: [] }]);
  const updSub = (i: number, patch: Partial<SubTask>) => setSubTasks(arr => arr.map((x, j) => j===i ? { ...x, ...patch } : x));
  const delSub = (i: number) => setSubTasks(arr => arr.filter((_, j) => j !== i));

  const addRisk = () => setRisks(arr => [...arr, { category: 'RC1', description: '', mitigation_minutes: 15, contingency_minutes: 0 }]);
  const updRisk = (i: number, patch: Partial<RiskItem>) => setRisks(arr => arr.map((x, j) => j===i ? { ...x, ...patch } : x));
  const delRisk = (i: number) => setRisks(arr => arr.filter((_, j) => j !== i));

  const aiSuggest = async () => {
    if (!taskTitle.trim()) { showAlert('Task title required', 'Enter the task title first.'); return; }
    setAiBusy(true);
    try {
      const { data } = await api.post('/atex/ai-suggest', { task_title: taskTitle.trim() });
      if (data?.sub_tasks?.length) setSubTasks(data.sub_tasks.map((st: any) => ({ title: st.title || '', effort_minutes: Number(st.effort_minutes)||30, ip_level: st.ip_level || 'high', support_needs: st.support_needs || [] })));
      if (data?.scc) setScc(data.scc);
      if (data?.risks?.length) setRisks(data.risks.map((r: any) => ({ category: r.category||'RC1', description: r.description||'', mitigation_minutes: Number(r.mitigation_minutes)||0, contingency_minutes: Number(r.contingency_minutes)||0 })));
    } catch (e: any) { showAlert('AI failed', e?.response?.data?.detail || e.message); }
    finally { setAiBusy(false); }
  };

  const estimate = async () => {
    if (!scc.trim()) { showAlert('SCC required', 'Synchronized Completion Criteria (SCC) is mandatory.'); return; }
    if (!subTasks.length || !subTasks.every(t => t.title.trim())) { showAlert('Sub-tasks required', 'At least one sub-task with a title.'); return; }
    setBusy(true);
    try {
      const { data } = await api.post('/atex/estimate', {
        task_title: taskTitle.trim() || 'Untitled task',
        task_priority: priority,
        sub_tasks: subTasks,
        self_satisfaction: selfSat,
        synchronized_completion_criteria: scc,
        ip_summary: ipSummary, support_summary: supportSummary,
        practical_break_minutes: Number(pbMinutes)||0,
        risks,
        minimal_buffer_pct: Number(bufferPct)||7.5,
        start_date: startDate || null,
        work_hours_per_day: Number(workHours)||8,
        holidays_per_week: Number(holidaysPerWeek)||1,
        source_module: sourceModule, source_ref_id: sourceRefId,
        save_as_template: saveTpl.on, template_name: saveTpl.name,
      });
      setCalc(data?.calc);
    } catch (e: any) { showAlert('Estimate failed', e?.response?.data?.detail || e.message); }
    finally { setBusy(false); }
  };

  const loadTemplate = (tpl: any) => {
    const t = tpl.template || {};
    setTaskTitle(t.task_title || ''); setPriority(t.task_priority || 'P2');
    setScc(t.synchronized_completion_criteria || ''); setSelfSat(t.self_satisfaction || '');
    setIpSummary(t.ip_summary || ''); setSupportSummary(t.support_summary || '');
    setPbMinutes(t.practical_break_minutes || 0); setBufferPct(t.minimal_buffer_pct || 7.5);
    setStartDate(t.start_date || ''); setWorkHours(t.work_hours_per_day || 8);
    setHolidaysPerWeek(t.holidays_per_week || 1);
    setSubTasks(t.sub_tasks || []); setRisks(t.risks || []);
  };

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.title}>ATEX Effort Estimation</Text>
        <Text style={s.subtitle}>Accurate Task Estimation for eXcellence</Text>
      </View>
      <ScrollView contentContainerStyle={{ padding: 14 }}>
        {/* Task */}
        <View style={s.card}>
          <Text style={s.lbl}>Task title</Text>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            <TextInput style={[s.inp, { flex: 1 }]} value={taskTitle} onChangeText={setTaskTitle} placeholder="e.g. Implement Video Conferencing" placeholderTextColor="#94A3B8" />
            <TouchableOpacity style={s.aiBtn} onPress={aiSuggest} disabled={aiBusy}>
              {aiBusy ? <ActivityIndicator size="small" color="#FFF" /> : <><Ionicons name="sparkles" size={14} color="#FFF" /><Text style={s.aiBtnText}> AI</Text></>}
            </TouchableOpacity>
          </View>
          <TouchableOpacity style={s.pickBtn} onPress={openPicker}>
            <Ionicons name="list" size={14} color="#2563EB" />
            <Text style={s.pickBtnText}>Pick from existing tasks</Text>
          </TouchableOpacity>
          <Text style={s.lbl}>Priority</Text>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {(['P0','P1','P2','P3'] as const).map(p => (
              <TouchableOpacity key={p} style={[s.priBtn, priority===p && s.priBtnOn]} onPress={() => setPriority(p)}><Text style={[s.priBtnText, priority===p && { color: '#FFF' }]}>{p}</Text></TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={s.card}>
          <Text style={s.sectionH}>Quality Conditions (QC)</Text>
          <Text style={s.lbl}>SCC — Synchronized Completion Criteria *</Text>
          <TextInput style={[s.inp, s.multi]} multiline value={scc} onChangeText={setScc} placeholder="What does objectively 'done' look like to stakeholders?" placeholderTextColor="#94A3B8" />
          <Text style={s.lbl}>Self-satisfaction criteria</Text>
          <TextInput style={[s.inp, s.multi]} multiline value={selfSat} onChangeText={setSelfSat} placeholder="What does 'done' look like to YOU?" placeholderTextColor="#94A3B8" />
        </View>

        <View style={s.card}>
          <Text style={s.sectionH}>Sub-Tasks (ST) — Σ effort = {Math.round(totalEffort)} min</Text>
          {subTasks.map((t, i) => (
            <View key={i} style={s.subBox}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Text style={s.subIdx}>{i + 1}.</Text>
                <TextInput style={[s.inp, { flex: 1 }]} value={t.title} onChangeText={(v) => updSub(i, { title: v })} placeholder="Sub-task title" placeholderTextColor="#94A3B8" />
                <TouchableOpacity onPress={() => delSub(i)}><Ionicons name="close-circle" size={20} color="#EF4444" /></TouchableOpacity>
              </View>
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
                <View style={{ flex: 1 }}>
                  <Text style={s.lblSm}>Effort (min)</Text>
                  <TextInput style={s.inp} keyboardType="numeric" value={String(t.effort_minutes)} onChangeText={(v) => updSub(i, { effort_minutes: Number(v)||0 })} />
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.lblSm}>IP (knowledge)</Text>
                  <View style={{ flexDirection: 'row', gap: 4 }}>
                    {(['high','medium','low'] as const).map(l => (
                      <TouchableOpacity key={l} style={[s.miniPick, t.ip_level===l && s.miniPickOn]} onPress={() => updSub(i, { ip_level: l })}><Text style={[s.miniPickText, t.ip_level===l && { color: '#FFF' }]}>{l[0].toUpperCase()}</Text></TouchableOpacity>
                    ))}
                  </View>
                </View>
              </View>
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                {['IH','ID','EH','ED'].map(sn => {
                  const on = t.support_needs.includes(sn);
                  return (
                    <TouchableOpacity key={sn} style={[s.snBadge, on && s.snBadgeOn]} onPress={() => updSub(i, { support_needs: on ? t.support_needs.filter(x => x !== sn) : [...t.support_needs, sn] })}>
                      <Text style={[s.snBadgeText, on && { color: '#FFF' }]}>{sn}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>
          ))}
          <TouchableOpacity style={s.addBtn} onPress={addSub}><Ionicons name="add" size={16} color="#FFF" /><Text style={s.addBtnText}>Add sub-task</Text></TouchableOpacity>
        </View>

        <View style={s.card}>
          <Text style={s.sectionH}>Risks (RC) — by priority</Text>
          {risks.map((r, i) => (
            <View key={i} style={s.subBox}>
              <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
                {(['RC1','RC2','RC3'] as const).map(c => (
                  <TouchableOpacity key={c} style={[s.miniPick, r.category===c && s.miniPickOn]} onPress={() => updRisk(i, { category: c })}><Text style={[s.miniPickText, r.category===c && { color: '#FFF' }]}>{c}</Text></TouchableOpacity>
                ))}
                <TouchableOpacity onPress={() => delRisk(i)} style={{ marginLeft: 'auto' }}><Ionicons name="close-circle" size={20} color="#EF4444" /></TouchableOpacity>
              </View>
              <TextInput style={[s.inp, { marginTop: 6 }]} placeholder="Risk description" placeholderTextColor="#94A3B8" value={r.description} onChangeText={(v) => updRisk(i, { description: v })} />
              <View style={{ flexDirection: 'row', gap: 6, marginTop: 6 }}>
                <View style={{ flex: 1 }}><Text style={s.lblSm}>Mitigation min</Text><TextInput style={s.inp} keyboardType="numeric" value={String(r.mitigation_minutes)} onChangeText={(v) => updRisk(i, { mitigation_minutes: Number(v)||0 })} /></View>
                <View style={{ flex: 1 }}><Text style={s.lblSm}>Contingency min</Text><TextInput style={s.inp} keyboardType="numeric" value={String(r.contingency_minutes)} onChangeText={(v) => updRisk(i, { contingency_minutes: Number(v)||0 })} /></View>
              </View>
            </View>
          ))}
          <TouchableOpacity style={s.addBtn} onPress={addRisk}><Ionicons name="add" size={16} color="#FFF" /><Text style={s.addBtnText}>Add risk</Text></TouchableOpacity>
        </View>

        <View style={s.card}>
          <Text style={s.sectionH}>Scheduling</Text>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            <View style={{ flex: 1 }}><Text style={s.lbl}>Practical Breaks (min)</Text><TextInput style={s.inp} keyboardType="numeric" value={String(pbMinutes)} onChangeText={(v) => setPbMinutes(Number(v)||0)} /></View>
            <View style={{ flex: 1 }}><Text style={s.lbl}>Minimal Buffer %</Text><TextInput style={s.inp} keyboardType="numeric" value={String(bufferPct)} onChangeText={(v) => setBufferPct(Number(v)||7.5)} /></View>
          </View>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            <View style={{ flex: 1 }}><Text style={s.lbl}>Start date (YYYY-MM-DD)</Text><TextInput style={s.inp} value={startDate} onChangeText={setStartDate} placeholder="2026-06-20" placeholderTextColor="#94A3B8" /></View>
            <View style={{ flex: 1 }}><Text style={s.lbl}>Work hrs / day</Text><TextInput style={s.inp} keyboardType="numeric" value={String(workHours)} onChangeText={(v) => setWorkHours(Number(v)||8)} /></View>
            <View style={{ flex: 1 }}><Text style={s.lbl}>Holidays/wk</Text><TextInput style={s.inp} keyboardType="numeric" value={String(holidaysPerWeek)} onChangeText={(v) => setHolidaysPerWeek(Number(v)||1)} /></View>
          </View>
        </View>

        <View style={s.card}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Text style={s.sectionH}>Save as Template</Text>
            <TouchableOpacity style={[s.toggle, saveTpl.on && s.toggleOn]} onPress={() => setSaveTpl(p => ({ ...p, on: !p.on }))}><Text style={[s.toggleText, saveTpl.on && { color: '#FFF' }]}>{saveTpl.on ? 'ON' : 'OFF'}</Text></TouchableOpacity>
          </View>
          {saveTpl.on && <TextInput style={[s.inp, { marginTop: 6 }]} placeholder="Template name" placeholderTextColor="#94A3B8" value={saveTpl.name} onChangeText={(v) => setSaveTpl(p => ({ ...p, name: v }))} />}
          {templates.length > 0 && (<>
            <Text style={[s.lbl, { marginTop: 8 }]}>Load existing template</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {templates.map(t => (<TouchableOpacity key={t.id} style={s.tplChip} onPress={() => loadTemplate(t)}><Text style={s.tplChipText}>{t.name}</Text></TouchableOpacity>))}
            </ScrollView>
          </>)}
        </View>

        <TouchableOpacity style={s.calcBtn} onPress={estimate} disabled={busy}>
          {busy ? <ActivityIndicator color="#FFF" /> : (<><Ionicons name="calculator" size={16} color="#FFF" /><Text style={s.calcBtnText}>  Calculate Final Timeline (TT)</Text></>)}
        </TouchableOpacity>

        {calc && (
          <View style={s.resultCard}>
            <Text style={s.resTitle}>Final Timeline</Text>
            <Text style={s.resBig}>{calc.total_timeline_hours} hours ({calc.total_timeline_minutes} min)</Text>
            <View style={s.resRow}><Text style={s.resK}>EE Effort</Text><Text style={s.resV}>{Math.round(calc.effort_minutes)} min</Text></View>
            <View style={s.resRow}><Text style={s.resK}>MB Buffer ({calc.minimal_buffer_pct}%)</Text><Text style={s.resV}>{calc.minimal_buffer_minutes} min</Text></View>
            <View style={s.resRow}><Text style={s.resK}>PB Practical Breaks</Text><Text style={s.resV}>{calc.practical_break_minutes} min</Text></View>
            <View style={s.resRow}><Text style={s.resK}>RM Risk Buffer</Text><Text style={s.resV}>{calc.risk_buffer_minutes} min</Text></View>
            {calc.end_date && (<><View style={s.resRow}><Text style={s.resK}>Working days</Text><Text style={s.resV}>{calc.working_days_needed}</Text></View>
            <View style={s.resRow}><Text style={s.resK}>End date</Text><Text style={[s.resV, { color: '#10B981' }]}>{calc.end_date}</Text></View></>)}
            {calc.risks_breakdown?.length > 0 && (<View style={{ marginTop: 8 }}>
              {calc.risks_breakdown.map((r: any, i: number) => (
                <View key={i} style={[s.riskLine, !r.applied && { opacity: 0.5 }]}>
                  <Text style={[s.riskCat, r.applied && { backgroundColor: '#003087', color: '#FFF' }]}>{r.category}</Text>
                  <Text style={s.riskDesc}>{r.description}</Text>
                  {!r.applied && <Text style={s.riskSkip}>skipped · {r.reason?.split('—')[0] || 'priority mismatch'}</Text>}
                </View>
              ))}
            </View>)}
          </View>
        )}
      </ScrollView>

      <Modal visible={pickerOpen} transparent animationType="fade" onRequestClose={() => setPickerOpen(false)}>
        <View style={s.pkOverlay}>
          <View style={s.pkSheet}>
            <View style={s.pkHeader}>
              <Text style={s.pkTitle}>Pick a task</Text>
              <TouchableOpacity onPress={() => setPickerOpen(false)}><Ionicons name="close" size={22} color="#475569" /></TouchableOpacity>
            </View>
            {pickLoading ? (
              <ActivityIndicator color="#2563EB" style={{ marginVertical: 20 }} />
            ) : pickTasks.length === 0 ? (
              <Text style={s.pkEmpty}>No tasks found in your Action Tracker or Task Tracker yet.</Text>
            ) : (
              <ScrollView style={{ maxHeight: 380 }} showsVerticalScrollIndicator>
                {pickTasks.map((t) => (
                  <TouchableOpacity key={t.id || t.title} style={s.pkRow}
                    onPress={() => { setTaskTitle(t.title || ''); setPickerOpen(false); }}>
                    <Ionicons name={t._kind === 'routine' ? 'repeat' : t._kind === 'action' ? 'flag-outline' : 'ellipse-outline'} size={14} color="#2563EB" />
                    <Text style={s.pkRowText} numberOfLines={2}>{t.title || 'Untitled'}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            )}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { backgroundColor: '#003087', padding: 16 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  title: { color: '#FFF', fontSize: 20, fontWeight: '800' },
  subtitle: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  card: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: '#E2E8F0' },
  sectionH: { fontSize: 13, fontWeight: '800', color: '#003087', marginBottom: 8 },
  lbl: { fontSize: 11, fontWeight: '700', color: '#475569', marginTop: 8, marginBottom: 4 },
  lblSm: { fontSize: 10, fontWeight: '700', color: '#64748B', marginBottom: 2 },
  inp: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 8, fontSize: 13, color: '#0F172A' },
  multi: { minHeight: 64, textAlignVertical: 'top' },
  aiBtn: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#8B5CF6', paddingHorizontal: 10, borderRadius: 8 },
  pickBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', backgroundColor: '#EFF6FF', borderWidth: 1, borderColor: '#BFDBFE', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, marginTop: 8, marginBottom: 4 },
  pickBtnText: { color: '#2563EB', fontSize: 12, fontWeight: '700' },
  pkOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  pkSheet: { backgroundColor: '#FFF', borderRadius: 18, padding: 16, maxWidth: 640, width: '100%', maxHeight: '85%', alignSelf: 'center' },
  pkHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  pkTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A' },
  pkEmpty: { fontSize: 13, color: '#64748B', paddingVertical: 20, textAlign: 'center' },
  pkRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  pkRowText: { flex: 1, fontSize: 14, color: '#0F172A', fontWeight: '500' },
  aiBtnText: { color: '#FFF', fontWeight: '800', fontSize: 12 },
  priBtn: { flex: 1, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC', alignItems: 'center' },
  priBtnOn: { backgroundColor: '#003087', borderColor: '#003087' },
  priBtnText: { fontSize: 12, fontWeight: '800', color: '#475569' },
  subBox: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8, padding: 8, marginBottom: 6 },
  subIdx: { width: 22, color: '#475569', fontWeight: '800' },
  miniPick: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#FFF' },
  miniPickOn: { backgroundColor: '#003087', borderColor: '#003087' },
  miniPickText: { fontSize: 11, fontWeight: '700', color: '#475569' },
  snBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#CBD5E1' },
  snBadgeOn: { backgroundColor: '#10B981', borderColor: '#10B981' },
  snBadgeText: { fontSize: 10, fontWeight: '800', color: '#475569' },
  addBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, backgroundColor: '#10B981', borderRadius: 8, padding: 8, marginTop: 6 },
  addBtnText: { color: '#FFF', fontWeight: '700', fontSize: 12 },
  toggle: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1' },
  toggleOn: { backgroundColor: '#10B981', borderColor: '#10B981' },
  toggleText: { fontSize: 11, fontWeight: '800', color: '#475569' },
  tplChip: { backgroundColor: '#EEF2FF', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, marginRight: 6, marginTop: 4 },
  tplChipText: { fontSize: 11, fontWeight: '700', color: '#4338CA' },
  calcBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#003087', borderRadius: 12, padding: 14, marginVertical: 8 },
  calcBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  resultCard: { backgroundColor: '#F0FDF4', borderRadius: 12, padding: 14, borderWidth: 2, borderColor: '#10B981' },
  resTitle: { fontSize: 13, color: '#166534', fontWeight: '700' },
  resBig: { fontSize: 22, fontWeight: '900', color: '#0F172A', marginVertical: 6 },
  resRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  resK: { fontSize: 12, color: '#475569' },
  resV: { fontSize: 12, fontWeight: '700', color: '#0F172A' },
  riskLine: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 3 },
  riskCat: { fontSize: 10, fontWeight: '800', color: '#0F172A', backgroundColor: '#E2E8F0', paddingHorizontal: 5, paddingVertical: 2, borderRadius: 6 },
  riskDesc: { flex: 1, fontSize: 11, color: '#334155' },
  riskSkip: { fontSize: 10, color: '#94A3B8' },
});
