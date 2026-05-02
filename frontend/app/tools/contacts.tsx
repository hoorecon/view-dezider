import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, TextInput, Modal,
  KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const GENDER_OPTIONS = ['male', 'female', 'non_binary', 'prefer_not_to_say'];
const AGE_GROUPS = ['18-25', '26-35', '36-45', '46-55', '56-65', '65+'];
const SOCIAL_STATUS = ['student', 'employed', 'self_employed', 'business_owner', 'retired', 'homemaker'];
const REL_STATUS = ['single', 'married', 'divorced', 'widowed', 'in_relationship', 'prefer_not_to_say'];

export default function ContactsScreen() {
  const router = useRouter();
  const [contacts, setContacts] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [filterOptions, setFilterOptions] = useState<any>({});
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({});

  // Create/Edit modal
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formStep, setFormStep] = useState(0); // 0=basic, 1=demographics, 2=professional, 3=social
  const [form, setForm] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [skillInput, setSkillInput] = useState('');

  const fetchContacts = async () => {
    try {
      let url = '/contacts?limit=100';
      if (search) url += `&search=${encodeURIComponent(search)}`;
      Object.entries(activeFilters).forEach(([k, v]) => {
        if (v) url += `&${k}=${encodeURIComponent(v)}`;
      });
      const res = await api.get(url);
      setContacts(res.data.contacts || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error('Error fetching contacts:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchFilterOptions = async () => {
    try {
      const res = await api.get('/contacts/filter-options');
      setFilterOptions(res.data);
    } catch (err) { /* ignore */ }
  };

  useFocusEffect(useCallback(() => { fetchContacts(); fetchFilterOptions(); }, []));

  React.useEffect(() => {
    const t = setTimeout(fetchContacts, 300);
    return () => clearTimeout(t);
  }, [search, activeFilters]);

  const onRefresh = async () => { setRefreshing(true); await fetchContacts(); setRefreshing(false); };

  const openCreate = () => {
    setEditingId(null);
    setForm({ name: '', email: '', phone: '', whatsapp: '', gender: '', age_group: '', country: '', language: '',
      profession: '', skills: [], organization: '', designation: '', business_network: '',
      social_status: '', relationship_status: '', caste: '', religion: '', political_party: '',
      tags: [], notes: '', is_sme: false, sme_domains: [] });
    setFormStep(0);
    setShowModal(true);
  };

  const openEdit = async (id: string) => {
    try {
      const res = await api.get(`/contacts/${id}`);
      setForm(res.data);
      setEditingId(id);
      setFormStep(0);
      setShowModal(true);
    } catch (err) { showAlert('Error', 'Failed to load contact'); }
  };

  const handleSave = async () => {
    if (!form.name?.trim()) { showAlert('Required', 'Name is required'); return; }
    setSaving(true);
    try {
      if (editingId) {
        await api.put(`/contacts/${editingId}`, form);
      } else {
        await api.post('/contacts', form);
      }
      setShowModal(false);
      fetchContacts();
      fetchFilterOptions();
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const handleDelete = (id: string) => {
    showAlert('Delete Contact', 'Are you sure?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/contacts/${id}`); fetchContacts(); } catch (err) { showAlert('Error', 'Failed to delete'); }
      }},
    ]);
  };

  const addSkill = () => {
    if (skillInput.trim()) {
      setForm({ ...form, skills: [...(form.skills || []), skillInput.trim()] });
      setSkillInput('');
    }
  };

  const removeSkill = (idx: number) => {
    const skills = [...(form.skills || [])];
    skills.splice(idx, 1);
    setForm({ ...form, skills });
  };

  const FORM_STEPS = ['Basic Info', 'Demographics', 'Professional', 'Social'];

  const renderFormStep = () => {
    switch (formStep) {
      case 0: return (
        <View>
          <Text style={styles.inputLabel}>Name *</Text>
          <TextInput style={styles.textInput} placeholder="Full name" value={form.name || ''} onChangeText={v => setForm({...form, name: v})} autoFocus />
          <Text style={styles.inputLabel}>Email</Text>
          <TextInput style={styles.textInput} placeholder="email@example.com" value={form.email || ''} onChangeText={v => setForm({...form, email: v})} keyboardType="email-address" autoCapitalize="none" />
          <Text style={styles.inputLabel}>Phone</Text>
          <TextInput style={styles.textInput} placeholder="+91 9876543210" value={form.phone || ''} onChangeText={v => setForm({...form, phone: v})} keyboardType="phone-pad" />
          <Text style={styles.inputLabel}>WhatsApp</Text>
          <TextInput style={styles.textInput} placeholder="+91 9876543210" value={form.whatsapp || ''} onChangeText={v => setForm({...form, whatsapp: v})} keyboardType="phone-pad" />
          <Text style={styles.inputLabel}>LinkedIn URL</Text>
          <TextInput style={styles.textInput} placeholder="https://linkedin.com/in/..." value={form.linkedin_url || ''} onChangeText={v => setForm({...form, linkedin_url: v})} autoCapitalize="none" />
          <Text style={styles.inputLabel}>Notes</Text>
          <TextInput style={[styles.textInput, {height: 60}]} placeholder="Any notes..." value={form.notes || ''} onChangeText={v => setForm({...form, notes: v})} multiline />
        </View>
      );
      case 1: return (
        <View>
          <Text style={styles.inputLabel}>Gender</Text>
          <View style={styles.chipRow}>
            {GENDER_OPTIONS.map(g => (
              <TouchableOpacity key={g} style={[styles.chip, form.gender === g && styles.chipActive]}
                onPress={() => setForm({...form, gender: form.gender === g ? '' : g})}>
                <Text style={[styles.chipText, form.gender === g && {color:'#FFF'}]}>{g.replace('_',' ')}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.inputLabel}>Age Group</Text>
          <View style={styles.chipRow}>
            {AGE_GROUPS.map(a => (
              <TouchableOpacity key={a} style={[styles.chip, form.age_group === a && styles.chipActive]}
                onPress={() => setForm({...form, age_group: form.age_group === a ? '' : a})}>
                <Text style={[styles.chipText, form.age_group === a && {color:'#FFF'}]}>{a}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.inputLabel}>Country</Text>
          <TextInput style={styles.textInput} placeholder="e.g., India" value={form.country || ''} onChangeText={v => setForm({...form, country: v})} />
          <Text style={styles.inputLabel}>Language</Text>
          <TextInput style={styles.textInput} placeholder="e.g., English, Hindi" value={form.language || ''} onChangeText={v => setForm({...form, language: v})} />
        </View>
      );
      case 2: return (
        <View>
          <Text style={styles.inputLabel}>Profession</Text>
          <TextInput style={styles.textInput} placeholder="e.g., Engineer" value={form.profession || ''} onChangeText={v => setForm({...form, profession: v})} />
          <Text style={styles.inputLabel}>Organization</Text>
          <TextInput style={styles.textInput} placeholder="e.g., Venture Buddha" value={form.organization || ''} onChangeText={v => setForm({...form, organization: v})} />
          <Text style={styles.inputLabel}>Designation</Text>
          <TextInput style={styles.textInput} placeholder="e.g., CTO" value={form.designation || ''} onChangeText={v => setForm({...form, designation: v})} />
          <Text style={styles.inputLabel}>Business Network</Text>
          <TextInput style={styles.textInput} placeholder="e.g., TiE, BNI" value={form.business_network || ''} onChangeText={v => setForm({...form, business_network: v})} />
          <Text style={styles.inputLabel}>Skills</Text>
          <View style={{flexDirection:'row', gap: 8, marginBottom: 8}}>
            <TextInput style={[styles.textInput, {flex: 1, marginBottom: 0}]} placeholder="Add a skill" value={skillInput} onChangeText={setSkillInput} onSubmitEditing={addSkill} />
            <TouchableOpacity style={styles.addSkillBtn} onPress={addSkill}>
              <Ionicons name="add" size={20} color="#FFF" />
            </TouchableOpacity>
          </View>
          <View style={styles.chipRow}>
            {(form.skills || []).map((s: string, i: number) => (
              <TouchableOpacity key={i} style={[styles.chip, styles.chipActive]} onPress={() => removeSkill(i)}>
                <Text style={{color:'#FFF', fontSize:12}}>{s} ×</Text>
              </TouchableOpacity>
            ))}
          </View>
          <TouchableOpacity style={styles.smeToggle} onPress={() => setForm({...form, is_sme: !form.is_sme})}>
            <Ionicons name={form.is_sme ? 'checkbox' : 'square-outline'} size={22} color={form.is_sme ? '#8B5CF6' : COLORS.textMuted} />
            <Text style={styles.smeLabel}>Mark as Subject Matter Expert (SME)</Text>
          </TouchableOpacity>
        </View>
      );
      case 3: return (
        <View>
          <Text style={styles.inputLabel}>Social Status</Text>
          <View style={styles.chipRow}>
            {SOCIAL_STATUS.map(s => (
              <TouchableOpacity key={s} style={[styles.chip, form.social_status === s && styles.chipActive]}
                onPress={() => setForm({...form, social_status: form.social_status === s ? '' : s})}>
                <Text style={[styles.chipText, form.social_status === s && {color:'#FFF'}]}>{s.replace('_',' ')}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.inputLabel}>Relationship Status</Text>
          <View style={styles.chipRow}>
            {REL_STATUS.map(r => (
              <TouchableOpacity key={r} style={[styles.chip, form.relationship_status === r && styles.chipActive]}
                onPress={() => setForm({...form, relationship_status: form.relationship_status === r ? '' : r})}>
                <Text style={[styles.chipText, form.relationship_status === r && {color:'#FFF'}]}>{r.replace('_',' ')}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.inputLabel}>Caste</Text>
          <TextInput style={styles.textInput} placeholder="Optional" value={form.caste || ''} onChangeText={v => setForm({...form, caste: v})} />
          <Text style={styles.inputLabel}>Religion</Text>
          <TextInput style={styles.textInput} placeholder="Optional" value={form.religion || ''} onChangeText={v => setForm({...form, religion: v})} />
          <Text style={styles.inputLabel}>Political Party</Text>
          <TextInput style={styles.textInput} placeholder="Optional" value={form.political_party || ''} onChangeText={v => setForm({...form, political_party: v})} />
        </View>
      );
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <LinearGradient colors={['#1E293B','#475569']} start={{x:0,y:0}} end={{x:1,y:1}} style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{flex:1}}>
          <Text style={styles.headerTitle}>Contacts</Text>
          <Text style={styles.headerSub}>{total} contacts • Filter & select participants</Text>
        </View>
        <TouchableOpacity style={styles.createHdrBtn} onPress={openCreate}>
          <Ionicons name="person-add" size={20} color="#1E293B" />
        </TouchableOpacity>
      </LinearGradient>

      {/* Search + Filter bar */}
      <View style={styles.searchBar}>
        <View style={styles.searchInputWrap}>
          <Ionicons name="search" size={18} color={COLORS.textMuted} />
          <TextInput style={styles.searchInput} placeholder="Search name, email, org..." value={search} onChangeText={setSearch} />
          {search ? <TouchableOpacity onPress={() => setSearch('')}><Ionicons name="close-circle" size={18} color={COLORS.textMuted} /></TouchableOpacity> : null}
        </View>
        <TouchableOpacity style={[styles.filterToggle, showFilters && {backgroundColor: '#6366F1'}]} onPress={() => setShowFilters(!showFilters)}>
          <Ionicons name="funnel" size={16} color={showFilters ? '#FFF' : COLORS.textSecondary} />
          {Object.values(activeFilters).filter(Boolean).length > 0 && (
            <View style={styles.filterBadge}><Text style={styles.filterBadgeText}>{Object.values(activeFilters).filter(Boolean).length}</Text></View>
          )}
        </TouchableOpacity>
      </View>

      {/* Filter chips */}
      {showFilters && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterBar} contentContainerStyle={{gap: 6, paddingHorizontal: 16}}>
          {[
            {key: 'gender', label: 'Gender', options: filterOptions.gender || GENDER_OPTIONS},
            {key: 'country', label: 'Country', options: filterOptions.country || []},
            {key: 'language', label: 'Language', options: filterOptions.language || []},
            {key: 'profession', label: 'Profession', options: filterOptions.profession || []},
            {key: 'organization', label: 'Org', options: filterOptions.organization || []},
            {key: 'age_group', label: 'Age', options: AGE_GROUPS},
            {key: 'religion', label: 'Religion', options: filterOptions.religion || []},
            {key: 'is_sme', label: 'SME Only', options: ['true']},
          ].map(f => (
            <TouchableOpacity key={f.key}
              style={[styles.filterChip, activeFilters[f.key] && {backgroundColor: '#6366F1', borderColor: '#6366F1'}]}
              onPress={() => {
                if (f.key === 'is_sme') {
                  setActiveFilters(prev => ({...prev, is_sme: prev.is_sme ? '' : 'true'}));
                } else if (f.options.length > 0) {
                  const current = activeFilters[f.key] || '';
                  const idx = f.options.indexOf(current);
                  const next = idx < f.options.length - 1 ? f.options[idx + 1] : '';
                  setActiveFilters(prev => ({...prev, [f.key]: next}));
                }
              }}
            >
              <Text style={[styles.filterChipText, activeFilters[f.key] && {color:'#FFF'}]}>
                {activeFilters[f.key] ? `${f.label}: ${activeFilters[f.key]}` : f.label}
              </Text>
              {activeFilters[f.key] && (
                <TouchableOpacity onPress={() => setActiveFilters(prev => ({...prev, [f.key]: ''}))}>
                  <Ionicons name="close" size={14} color="#FFF" />
                </TouchableOpacity>
              )}
            </TouchableOpacity>
          ))}
          {Object.values(activeFilters).some(Boolean) && (
            <TouchableOpacity style={[styles.filterChip, {backgroundColor: '#EF4444', borderColor: '#EF4444'}]}
              onPress={() => setActiveFilters({})}>
              <Text style={[styles.filterChipText, {color:'#FFF'}]}>Clear All</Text>
            </TouchableOpacity>
          )}
        </ScrollView>
      )}

      {/* Contact List */}
      {loading ? (
        <View style={styles.centered}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : (
        <ScrollView contentContainerStyle={{padding: 16, paddingBottom: 100}}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          showsVerticalScrollIndicator={false}>
          {contacts.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="people-outline" size={48} color="#D1D5DB" />
              <Text style={styles.emptyTitle}>No Contacts</Text>
              <Text style={styles.emptyText}>Add contacts to select participants for group decisions.</Text>
              <TouchableOpacity style={styles.emptyBtn} onPress={openCreate}>
                <Ionicons name="person-add" size={18} color="#FFF" />
                <Text style={{color:'#FFF', fontWeight:'600'}}>Add Contact</Text>
              </TouchableOpacity>
            </View>
          ) : (
            contacts.map(c => (
              <TouchableOpacity key={c.id} style={styles.contactCard} onPress={() => openEdit(c.id)} activeOpacity={0.7}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>{(c.name || '?')[0].toUpperCase()}</Text>
                  {c.is_sme && <View style={styles.smeBadge}><Ionicons name="star" size={8} color="#FFF" /></View>}
                </View>
                <View style={{flex:1}}>
                  <Text style={styles.contactName} numberOfLines={1}>{c.name}</Text>
                  <View style={{flexDirection:'row', gap: 8, marginTop: 2}}>
                    {c.profession ? <Text style={styles.contactMeta}>{c.profession}</Text> : null}
                    {c.organization ? <Text style={styles.contactMeta}>• {c.organization}</Text> : null}
                  </View>
                  <View style={styles.tagRow}>
                    {c.country ? <View style={styles.miniTag}><Text style={styles.miniTagText}>{c.country}</Text></View> : null}
                    {c.language ? <View style={styles.miniTag}><Text style={styles.miniTagText}>{c.language}</Text></View> : null}
                    {c.linked_user_id ? <View style={[styles.miniTag, {backgroundColor: '#ECFDF5'}]}><Ionicons name="link" size={10} color="#059669" /><Text style={[styles.miniTagText, {color: '#059669'}]}>Linked</Text></View> : null}
                  </View>
                </View>
                <TouchableOpacity style={{padding: 6}} onPress={() => handleDelete(c.id)}>
                  <Ionicons name="trash-outline" size={16} color="#9CA3AF" />
                </TouchableOpacity>
              </TouchableOpacity>
            ))
          )}
        </ScrollView>
      )}

      {/* Create/Edit Modal */}
      <Modal visible={showModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{width:'100%', alignItems:'center'}}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>{editingId ? 'Edit Contact' : 'New Contact'}</Text>
                <TouchableOpacity onPress={() => setShowModal(false)}><Ionicons name="close" size={24} color={COLORS.textSecondary} /></TouchableOpacity>
              </View>

              {/* Step tabs */}
              <View style={styles.stepTabs}>
                {FORM_STEPS.map((s, i) => (
                  <TouchableOpacity key={i} style={[styles.stepTab, formStep === i && styles.stepTabActive]}
                    onPress={() => setFormStep(i)}>
                    <Text style={[styles.stepTabText, formStep === i && {color:'#FFF'}]}>{s}</Text>
                  </TouchableOpacity>
                ))}
              </View>

              <ScrollView style={{maxHeight: 400}} showsVerticalScrollIndicator={false}>
                {renderFormStep()}
              </ScrollView>

              <View style={styles.modalFooter}>
                {formStep > 0 && (
                  <TouchableOpacity style={styles.prevBtn} onPress={() => setFormStep(formStep - 1)}>
                    <Text style={styles.prevBtnText}>Previous</Text>
                  </TouchableOpacity>
                )}
                <View style={{flex: 1}} />
                {formStep < 3 ? (
                  <TouchableOpacity style={styles.nextBtn} onPress={() => setFormStep(formStep + 1)}>
                    <Text style={styles.nextBtnText}>Next</Text>
                    <Ionicons name="arrow-forward" size={16} color="#FFF" />
                  </TouchableOpacity>
                ) : (
                  <TouchableOpacity style={styles.saveBtn} onPress={handleSave} disabled={saving}>
                    {saving ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={styles.saveBtnText}>Save Contact</Text>}
                  </TouchableOpacity>
                )}
              </View>
            </View>
          </KeyboardAvoidingView>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {flex:1, backgroundColor: COLORS.background},
  centered: {flex:1, justifyContent:'center', alignItems:'center'},
  header: {flexDirection:'row', alignItems:'center', padding:16, paddingTop:12, paddingBottom:18, gap:12},
  backBtn: {width:40, height:40, borderRadius:20, backgroundColor:'rgba(255,255,255,0.15)', justifyContent:'center', alignItems:'center'},
  headerTitle: {fontSize:20, fontWeight:'700', color:'#FFF'},
  headerSub: {fontSize:11, color:'rgba(255,255,255,0.7)', marginTop:2},
  createHdrBtn: {width:40, height:40, borderRadius:20, backgroundColor:'#FFF', justifyContent:'center', alignItems:'center'},
  searchBar: {flexDirection:'row', alignItems:'center', paddingHorizontal:16, paddingVertical:10, gap:8, backgroundColor:'#FFF', borderBottomWidth:1, borderBottomColor:'#E5E7EB'},
  searchInputWrap: {flex:1, flexDirection:'row', alignItems:'center', gap:8, backgroundColor:'#F9FAFB', borderRadius:10, paddingHorizontal:12, paddingVertical:8, borderWidth:1, borderColor:'#E5E7EB'},
  searchInput: {flex:1, fontSize:14, color: COLORS.textPrimary},
  filterToggle: {width:40, height:40, borderRadius:10, backgroundColor:'#F3F4F6', justifyContent:'center', alignItems:'center'},
  filterBadge: {position:'absolute', top:-2, right:-2, width:16, height:16, borderRadius:8, backgroundColor:'#EF4444', justifyContent:'center', alignItems:'center'},
  filterBadgeText: {fontSize:9, fontWeight:'800', color:'#FFF'},
  filterBar: {paddingVertical:8, backgroundColor:'#F9FAFB', borderBottomWidth:1, borderBottomColor:'#E5E7EB'},
  filterChip: {flexDirection:'row', alignItems:'center', gap:4, paddingHorizontal:12, paddingVertical:6, borderRadius:16, backgroundColor:'#FFF', borderWidth:1, borderColor:'#E5E7EB'},
  filterChipText: {fontSize:12, fontWeight:'600', color: COLORS.textSecondary},
  emptyState: {alignItems:'center', paddingVertical:48, gap:10},
  emptyTitle: {fontSize:18, fontWeight:'700', color: COLORS.textPrimary},
  emptyText: {fontSize:13, color: COLORS.textSecondary, textAlign:'center', paddingHorizontal:32},
  emptyBtn: {flexDirection:'row', alignItems:'center', gap:8, backgroundColor:'#1E293B', paddingHorizontal:20, paddingVertical:12, borderRadius:12, marginTop:8},
  contactCard: {flexDirection:'row', alignItems:'center', gap:12, backgroundColor:'#FFF', borderRadius:12, padding:14, marginBottom:10, borderWidth:1, borderColor:'#F3F4F6'},
  avatar: {width:44, height:44, borderRadius:22, backgroundColor:'#6366F1', justifyContent:'center', alignItems:'center'},
  avatarText: {fontSize:18, fontWeight:'700', color:'#FFF'},
  smeBadge: {position:'absolute', bottom:-2, right:-2, width:16, height:16, borderRadius:8, backgroundColor:'#F59E0B', justifyContent:'center', alignItems:'center', borderWidth:2, borderColor:'#FFF'},
  contactName: {fontSize:15, fontWeight:'600', color: COLORS.textPrimary},
  contactMeta: {fontSize:12, color: COLORS.textSecondary},
  tagRow: {flexDirection:'row', gap:4, marginTop:4, flexWrap:'wrap'},
  miniTag: {flexDirection:'row', alignItems:'center', gap:2, backgroundColor:'#F3F4F6', paddingHorizontal:6, paddingVertical:2, borderRadius:4},
  miniTagText: {fontSize:10, fontWeight:'600', color: COLORS.textMuted},
  modalOverlay: {flex:1, backgroundColor:'rgba(0,0,0,0.5)', justifyContent:'flex-end', alignItems:'center'},
  modalContent: {width:'100%', maxWidth:500, backgroundColor:'#FFF', borderTopLeftRadius:24, borderTopRightRadius:24, padding:24, maxHeight:'90%'},
  modalHeader: {flexDirection:'row', justifyContent:'space-between', alignItems:'center', marginBottom:16},
  modalTitle: {fontSize:18, fontWeight:'700', color: COLORS.textPrimary},
  stepTabs: {flexDirection:'row', gap:4, marginBottom:16},
  stepTab: {flex:1, paddingVertical:8, borderRadius:8, backgroundColor:'#F3F4F6', alignItems:'center'},
  stepTabActive: {backgroundColor:'#1E293B'},
  stepTabText: {fontSize:11, fontWeight:'600', color: COLORS.textSecondary},
  inputLabel: {fontSize:13, fontWeight:'600', color: COLORS.textSecondary, marginBottom:6, marginTop:8},
  textInput: {backgroundColor:'#F9FAFB', borderRadius:10, padding:12, fontSize:14, color: COLORS.textPrimary, borderWidth:1, borderColor:'#E5E7EB', marginBottom:8},
  chipRow: {flexDirection:'row', flexWrap:'wrap', gap:6, marginBottom:8},
  chip: {paddingHorizontal:12, paddingVertical:6, borderRadius:16, backgroundColor:'#F3F4F6', borderWidth:1, borderColor:'#E5E7EB'},
  chipActive: {backgroundColor:'#6366F1', borderColor:'#6366F1'},
  chipText: {fontSize:12, fontWeight:'600', color: COLORS.textSecondary, textTransform:'capitalize'},
  addSkillBtn: {width:40, height:44, borderRadius:10, backgroundColor:'#6366F1', justifyContent:'center', alignItems:'center'},
  smeToggle: {flexDirection:'row', alignItems:'center', gap:10, paddingVertical:12, marginTop:8},
  smeLabel: {fontSize:14, fontWeight:'600', color: COLORS.textPrimary},
  modalFooter: {flexDirection:'row', alignItems:'center', marginTop:16, gap:12},
  prevBtn: {paddingHorizontal:16, paddingVertical:12, borderRadius:10, backgroundColor:'#F3F4F6'},
  prevBtnText: {fontSize:14, fontWeight:'600', color: COLORS.textSecondary},
  nextBtn: {flexDirection:'row', alignItems:'center', gap:6, paddingHorizontal:20, paddingVertical:12, borderRadius:10, backgroundColor:'#6366F1'},
  nextBtnText: {fontSize:14, fontWeight:'600', color:'#FFF'},
  saveBtn: {paddingHorizontal:24, paddingVertical:12, borderRadius:10, backgroundColor:'#059669'},
  saveBtnText: {fontSize:14, fontWeight:'700', color:'#FFF'},
});
