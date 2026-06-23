/**
 * Admin → Platform Experts (Collaboration Epic B2).
 * Vetted expert directory. Masters-driven (Expert Type / Languages / Experience /
 * Fees-per-min / Timings), Central-Catalog-linked, multi-Org associations,
 * manual entry + JSON bulk-upload.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

interface Org {
  org_name: string; role?: string; fees_per_min_inr?: number | null;
  contact_email?: string; whatsapp?: string; mobile?: string; address?: string;
  available_timings?: string[]; country?: string; state?: string; city?: string;
}
interface Expert {
  expert_id: string; name: string; email: string; expert_type?: string;
  languages?: string[]; experience_range?: string; fees_per_min_inr?: number | null;
  available_timings?: string[]; specializations?: string[]; catalog_node_ids?: string[];
  organizations?: Org[]; is_active: boolean; is_verified?: boolean;
}

const EMPTY_FORM = {
  name: '', email: '', headline: '', bio: '', expert_type: '',
  experience_range: '', fees_per_min_inr: '', specializationsText: '',
  languages: [] as string[], available_timings: [] as string[],
  catalog_node_ids: [] as string[], organizations: [] as Org[],
  is_active: true,
};

export default function PlatformExpertsScreen() {
  const router = useRouter();
  const [experts, setExperts] = useState<Expert[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // master option lists
  const [mExpertTypes, setMExpertTypes] = useState<string[]>([]);
  const [mExperience, setMExperience] = useState<string[]>([]);
  const [mLanguages, setMLanguages] = useState<string[]>([]);
  const [mTimings, setMTimings] = useState<string[]>([]);
  const [catalogNodes, setCatalogNodes] = useState<any[]>([]);

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Expert | null>(null);
  const [form, setForm] = useState<any>({ ...EMPTY_FORM });

  // picker overlays
  const [picker, setPicker] = useState<null | 'expert_type' | 'experience_range' | 'languages' | 'available_timings' | 'catalog'>(null);
  const [catalogSearch, setCatalogSearch] = useState('');

  const [showBulk, setShowBulk] = useState(false);
  const [bulkText, setBulkText] = useState('');
  const [bulkResult, setBulkResult] = useState<any>(null);

  const fetchExperts = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/platform-experts?include_inactive=true');
      setExperts(r.data?.items || []);
    } catch { setExperts([]); }
    finally { setLoading(false); }
  }, []);

  const fetchMasters = useCallback(async () => {
    const get = async (t: string) => {
      try { const r = await api.get(`/masters/${t}?limit=500`); return (r.data?.items || []).map((i: any) => i.value); }
      catch { return []; }
    };
    setMExpertTypes(await get('expert_type'));
    setMExperience(await get('experience_range'));
    setMLanguages(await get('language'));
    setMTimings(await get('available_timing'));
    try { const r = await api.get('/catalog/nodes'); setCatalogNodes(r.data?.items || []); }
    catch { setCatalogNodes([]); }
  }, []);

  useEffect(() => { fetchExperts(); fetchMasters(); }, [fetchExperts, fetchMasters]);

  const openAdd = () => { setEditing(null); setForm({ ...EMPTY_FORM, organizations: [] }); setShowForm(true); };
  const openEdit = (e: Expert) => {
    setEditing(e);
    setForm({
      name: e.name || '', email: e.email || '', headline: (e as any).headline || '', bio: (e as any).bio || '',
      expert_type: e.expert_type || '', experience_range: e.experience_range || '',
      fees_per_min_inr: e.fees_per_min_inr != null ? String(e.fees_per_min_inr) : '',
      specializationsText: (e.specializations || []).join(', '),
      languages: e.languages || [], available_timings: e.available_timings || [],
      catalog_node_ids: e.catalog_node_ids || [], organizations: e.organizations || [],
      is_active: e.is_active,
    });
    setShowForm(true);
  };

  const buildPayload = () => ({
    name: form.name.trim(), email: form.email.trim(), headline: form.headline || null, bio: form.bio || null,
    expert_type: form.expert_type || null, experience_range: form.experience_range || null,
    fees_per_min_inr: form.fees_per_min_inr ? parseInt(form.fees_per_min_inr, 10) : null,
    languages: form.languages, available_timings: form.available_timings,
    specializations: form.specializationsText.split(',').map((s: string) => s.trim()).filter(Boolean),
    catalog_node_ids: form.catalog_node_ids, organizations: form.organizations,
    is_active: form.is_active,
  });

  const save = async () => {
    if (!form.name.trim() || !form.email.trim() || !form.email.includes('@')) {
      showAlert('Required', 'Name and a valid email are required'); return;
    }
    setSaving(true);
    try {
      if (editing) await api.put(`/platform-experts/${editing.expert_id}`, buildPayload());
      else await api.post('/platform-experts', buildPayload());
      setShowForm(false); fetchExperts();
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Save failed'); }
    finally { setSaving(false); }
  };

  const remove = (e: Expert) => showAlert('Delete Expert', `Remove ${e.name}?`, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Delete', style: 'destructive', onPress: async () => {
      try { await api.delete(`/platform-experts/${e.expert_id}`); fetchExperts(); }
      catch { showAlert('Error', 'Delete failed'); }
    } },
  ]);

  const toggleActive = async (e: Expert) => {
    try { await api.put(`/platform-experts/${e.expert_id}`, { is_active: !e.is_active }); fetchExperts(); }
    catch { showAlert('Error', 'Failed'); }
  };

  const runBulk = async () => {
    let parsed: any;
    try {
      parsed = JSON.parse(bulkText);
      if (!Array.isArray(parsed)) throw new Error('not array');
    } catch { showAlert('Invalid JSON', 'Paste a JSON array of expert objects.'); return; }
    setSaving(true);
    try {
      const r = await api.post('/platform-experts/bulk', { experts: parsed });
      setBulkResult(r.data); fetchExperts();
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Bulk upload failed'); }
    finally { setSaving(false); }
  };

  // --- org subform helpers ---
  const addOrg = () => setForm({ ...form, organizations: [...form.organizations, { org_name: '' }] });
  const updateOrg = (i: number, patch: Partial<Org>) => {
    const orgs = [...form.organizations]; orgs[i] = { ...orgs[i], ...patch }; setForm({ ...form, organizations: orgs });
  };
  const removeOrg = (i: number) => setForm({ ...form, organizations: form.organizations.filter((_: any, j: number) => j !== i) });

  const toggleArr = (key: 'languages' | 'available_timings' | 'catalog_node_ids', v: string) => {
    const arr: string[] = form[key] || [];
    setForm({ ...form, [key]: arr.includes(v) ? arr.filter(x => x !== v) : [...arr, v] });
  };

  const nodeName = (id: string) => {
    const n = catalogNodes.find((x: any) => x.node_id === id);
    return n ? `${n.name}${n.level != null ? ` · L${n.level}` : ''}` : id;
  };

  const filteredNodes = catalogSearch.trim()
    ? catalogNodes.filter((n: any) => (n.name || '').toLowerCase().includes(catalogSearch.trim().toLowerCase()))
    : catalogNodes;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#D946EF', '#A21CAF']} style={styles.header}>
        <TouchableOpacity style={styles.iconHdr} onPress={() => safeBack(router)}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Platform Experts</Text>
        <TouchableOpacity style={styles.iconHdr} onPress={() => { setBulkResult(null); setBulkText(''); setShowBulk(true); }}>
          <Ionicons name="cloud-upload-outline" size={21} color="#FFF" />
        </TouchableOpacity>
        <TouchableOpacity style={styles.iconHdr} onPress={openAdd}>
          <Ionicons name="add" size={24} color="#FFF" />
        </TouchableOpacity>
      </LinearGradient>

      {loading ? (
        <ActivityIndicator style={{ marginTop: 40 }} color="#A21CAF" />
      ) : (
        <FlatList
          data={experts}
          keyExtractor={(i) => i.expert_id}
          contentContainerStyle={{ padding: 14, paddingBottom: 60 }}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="ribbon-outline" size={46} color="#C4B5FD" />
              <Text style={styles.emptyTitle}>No Platform Experts yet</Text>
              <Text style={styles.emptyDesc}>Add vetted experts users can share decision steps with. Link them to Central Catalog topics so they appear for relevant decisions.</Text>
              <TouchableOpacity style={styles.emptyBtn} onPress={openAdd}>
                <Ionicons name="add" size={18} color="#FFF" /><Text style={styles.emptyBtnText}>Add Expert</Text>
              </TouchableOpacity>
            </View>
          }
          renderItem={({ item }) => (
            <View style={[styles.card, !item.is_active && { opacity: 0.55 }]}>
              <View style={styles.cardTop}>
                <View style={styles.avatar}><Ionicons name="ribbon" size={18} color="#FFF" /></View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.name}>{item.name}</Text>
                  <Text style={styles.email}>{item.email}</Text>
                  <View style={styles.badgeRow}>
                    {!!item.expert_type && <View style={styles.badge}><Text style={styles.badgeText}>{item.expert_type}</Text></View>}
                    {!!item.experience_range && <View style={styles.badgeAlt}><Text style={styles.badgeAltText}>{item.experience_range}</Text></View>}
                    {item.fees_per_min_inr != null && <View style={styles.badgeFee}><Text style={styles.badgeFeeText}>₹{item.fees_per_min_inr}/min</Text></View>}
                  </View>
                </View>
                <TouchableOpacity onPress={() => toggleActive(item)}>
                  <Ionicons name={item.is_active ? 'toggle' : 'toggle-outline'} size={30} color={item.is_active ? '#16A34A' : '#94A3B8'} />
                </TouchableOpacity>
              </View>
              {(item.languages?.length || item.catalog_node_ids?.length || item.organizations?.length) ? (
                <Text style={styles.metaLine}>
                  {item.languages?.length ? `🗣 ${item.languages.join(', ')}  ` : ''}
                  {item.catalog_node_ids?.length ? `🔗 ${item.catalog_node_ids.length} topic(s)  ` : ''}
                  {item.organizations?.length ? `🏢 ${item.organizations.length} org(s)` : ''}
                </Text>
              ) : null}
              <View style={styles.cardActions}>
                <TouchableOpacity style={styles.actBtn} onPress={() => openEdit(item)}>
                  <Ionicons name="create-outline" size={16} color="#A21CAF" /><Text style={styles.actText}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.actBtn} onPress={() => remove(item)}>
                  <Ionicons name="trash-outline" size={16} color="#EF4444" /><Text style={[styles.actText, { color: '#EF4444' }]}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        />
      )}

      {/* ---- Add/Edit form ---- */}
      <Modal visible={showForm} transparent animationType="slide" onRequestClose={() => setShowForm(false)}>
        <View style={styles.modalBg}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>{editing ? 'Edit' : 'Add'} Platform Expert</Text>
              <TouchableOpacity onPress={() => setShowForm(false)}><Ionicons name="close" size={24} color="#0F172A" /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: '88%' }} showsVerticalScrollIndicator={false}>
              <Label t="Name *" />
              <TextInput style={styles.input} value={form.name} onChangeText={(t) => setForm({ ...form, name: t })} placeholder="Full name" />
              <Label t="Email *" />
              <TextInput style={styles.input} value={form.email} onChangeText={(t) => setForm({ ...form, email: t })} placeholder="expert@email.com" autoCapitalize="none" keyboardType="email-address" />
              <Label t="Headline" />
              <TextInput style={styles.input} value={form.headline} onChangeText={(t) => setForm({ ...form, headline: t })} placeholder="e.g. Cardiac surgeon, 12 yrs" />

              <Label t="Expert Type" />
              <PickerField value={form.expert_type} placeholder="Select expert type" onPress={() => setPicker('expert_type')} />
              <Label t="Experience" />
              <PickerField value={form.experience_range} placeholder="Select experience range" onPress={() => setPicker('experience_range')} />
              <Label t="Fees per minute (₹)" />
              <TextInput style={styles.input} value={form.fees_per_min_inr} onChangeText={(t) => setForm({ ...form, fees_per_min_inr: t.replace(/[^0-9]/g, '') })} placeholder="e.g. 50" keyboardType="numeric" />

              <Label t={`Languages (${form.languages.length})`} />
              <PickerField value={form.languages.join(', ')} placeholder="Select languages" onPress={() => setPicker('languages')} />
              <Label t={`Available Timings (${form.available_timings.length})`} />
              <PickerField value={form.available_timings.join(', ')} placeholder="Select timings" onPress={() => setPicker('available_timings')} />

              <Label t="Specializations (comma-separated)" />
              <TextInput style={styles.input} value={form.specializationsText} onChangeText={(t) => setForm({ ...form, specializationsText: t })} placeholder="Cardiology, Pediatrics" />

              <Label t={`Catalog Topics (${form.catalog_node_ids.length})`} />
              <PickerField value={form.catalog_node_ids.map(nodeName).join(', ')} placeholder="Link to catalog topics" onPress={() => setPicker('catalog')} />

              {/* Organizations */}
              <View style={styles.orgHeader}>
                <Text style={styles.orgTitle}>Organizations ({form.organizations.length})</Text>
                <TouchableOpacity style={styles.addOrgBtn} onPress={addOrg}>
                  <Ionicons name="add" size={16} color="#FFF" /><Text style={styles.addOrgText}>Add Org</Text>
                </TouchableOpacity>
              </View>
              {form.organizations.map((o: Org, i: number) => (
                <View key={i} style={styles.orgCard}>
                  <View style={styles.orgCardHead}>
                    <Text style={styles.orgIdx}>Org #{i + 1}</Text>
                    <TouchableOpacity onPress={() => removeOrg(i)}><Ionicons name="trash-outline" size={16} color="#EF4444" /></TouchableOpacity>
                  </View>
                  <TextInput style={styles.orgInput} value={o.org_name} onChangeText={(t) => updateOrg(i, { org_name: t })} placeholder="Org name *" />
                  <TextInput style={styles.orgInput} value={o.role || ''} onChangeText={(t) => updateOrg(i, { role: t })} placeholder="Role (e.g. Senior Surgeon)" />
                  <View style={styles.orgRow}>
                    <TextInput style={[styles.orgInput, styles.orgHalf]} value={o.fees_per_min_inr != null ? String(o.fees_per_min_inr) : ''} onChangeText={(t) => updateOrg(i, { fees_per_min_inr: t ? parseInt(t.replace(/[^0-9]/g, ''), 10) : null })} placeholder="Fees/min ₹" keyboardType="numeric" />
                    <TextInput style={[styles.orgInput, styles.orgHalf]} value={o.mobile || ''} onChangeText={(t) => updateOrg(i, { mobile: t })} placeholder="Mobile" keyboardType="phone-pad" />
                  </View>
                  <View style={styles.orgRow}>
                    <TextInput style={[styles.orgInput, styles.orgHalf]} value={o.contact_email || ''} onChangeText={(t) => updateOrg(i, { contact_email: t })} placeholder="Contact email" autoCapitalize="none" />
                    <TextInput style={[styles.orgInput, styles.orgHalf]} value={o.whatsapp || ''} onChangeText={(t) => updateOrg(i, { whatsapp: t })} placeholder="WhatsApp" keyboardType="phone-pad" />
                  </View>
                  <TextInput style={styles.orgInput} value={o.address || ''} onChangeText={(t) => updateOrg(i, { address: t })} placeholder="Physical address" />
                  <View style={styles.orgRow}>
                    <TextInput style={[styles.orgInput, styles.orgThird]} value={o.city || ''} onChangeText={(t) => updateOrg(i, { city: t })} placeholder="City" />
                    <TextInput style={[styles.orgInput, styles.orgThird]} value={o.state || ''} onChangeText={(t) => updateOrg(i, { state: t })} placeholder="State" />
                    <TextInput style={[styles.orgInput, styles.orgThird]} value={o.country || ''} onChangeText={(t) => updateOrg(i, { country: t })} placeholder="Country" />
                  </View>
                </View>
              ))}

              <TouchableOpacity style={styles.activeToggle} onPress={() => setForm({ ...form, is_active: !form.is_active })}>
                <Ionicons name={form.is_active ? 'checkbox' : 'square-outline'} size={20} color="#A21CAF" />
                <Text style={styles.activeLabel}>Active (visible in Share modal)</Text>
              </TouchableOpacity>
            </ScrollView>
            <TouchableOpacity style={styles.saveBtn} onPress={save} disabled={saving}>
              {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>{editing ? 'Update Expert' : 'Add Expert'}</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* ---- Multi/Single picker overlay ---- */}
      <Modal visible={!!picker} transparent animationType="fade" onRequestClose={() => setPicker(null)}>
        <View style={styles.pickerBg}>
          <View style={styles.pickerCard}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>
                {picker === 'expert_type' ? 'Expert Type' : picker === 'experience_range' ? 'Experience' :
                 picker === 'languages' ? 'Languages' : picker === 'available_timings' ? 'Available Timings' : 'Catalog Topics'}
              </Text>
              <TouchableOpacity onPress={() => { setPicker(null); setCatalogSearch(''); }}><Ionicons name="close" size={22} color="#0F172A" /></TouchableOpacity>
            </View>
            {picker === 'catalog' && (
              <TextInput style={[styles.input, { marginBottom: 8 }]} value={catalogSearch} onChangeText={setCatalogSearch} placeholder="Search topics…" />
            )}
            <ScrollView style={{ maxHeight: 420 }}>
              {picker === 'expert_type' && mExpertTypes.map(v => (
                <SingleRow key={v} v={v} active={form.expert_type === v} onPress={() => { setForm({ ...form, expert_type: v }); setPicker(null); }} />
              ))}
              {picker === 'experience_range' && mExperience.map(v => (
                <SingleRow key={v} v={v} active={form.experience_range === v} onPress={() => { setForm({ ...form, experience_range: v }); setPicker(null); }} />
              ))}
              {picker === 'languages' && mLanguages.map(v => (
                <MultiRow key={v} v={v} active={form.languages.includes(v)} onPress={() => toggleArr('languages', v)} />
              ))}
              {picker === 'available_timings' && mTimings.map(v => (
                <MultiRow key={v} v={v} active={form.available_timings.includes(v)} onPress={() => toggleArr('available_timings', v)} />
              ))}
              {picker === 'catalog' && filteredNodes.map((n: any) => (
                <MultiRow key={n.node_id} v={`${n.name}  · L${n.level}`} active={form.catalog_node_ids.includes(n.node_id)} onPress={() => toggleArr('catalog_node_ids', n.node_id)} />
              ))}
            </ScrollView>
            {(picker === 'languages' || picker === 'available_timings' || picker === 'catalog') && (
              <TouchableOpacity style={styles.doneBtn} onPress={() => { setPicker(null); setCatalogSearch(''); }}>
                <Text style={styles.doneBtnText}>Done</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      </Modal>

      {/* ---- Bulk upload ---- */}
      <Modal visible={showBulk} transparent animationType="slide" onRequestClose={() => setShowBulk(false)}>
        <View style={styles.modalBg}>
          <View style={styles.sheet}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>Bulk Upload (JSON)</Text>
              <TouchableOpacity onPress={() => setShowBulk(false)}><Ionicons name="close" size={24} color="#0F172A" /></TouchableOpacity>
            </View>
            <Text style={styles.bulkHint}>Paste a JSON array. Each object needs at least name + email. Optional: expert_type, languages[], experience_range, fees_per_min_inr, available_timings[], specializations[], catalog_node_ids[], organizations[].</Text>
            <TextInput
              style={styles.bulkInput} value={bulkText} onChangeText={setBulkText} multiline
              placeholder={'[\n  {"name":"Dr A","email":"a@x.com","expert_type":"Surgeon","catalog_node_ids":["cn_l0_la_health"]}\n]'}
              autoCapitalize="none"
            />
            {bulkResult && (
              <View style={styles.bulkResult}>
                <Text style={styles.bulkResultText}>✅ Created {bulkResult.created_count} · ⚠️ {bulkResult.error_count} error(s)</Text>
                {(bulkResult.errors || []).slice(0, 5).map((e: any, i: number) => (
                  <Text key={i} style={styles.bulkErr}>• [{e.index}] {e.email}: {e.error}</Text>
                ))}
              </View>
            )}
            <TouchableOpacity style={styles.saveBtn} onPress={runBulk} disabled={saving}>
              {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>Upload</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const Label = ({ t }: { t: string }) => <Text style={styles.label}>{t}</Text>;
const PickerField = ({ value, placeholder, onPress }: { value: string; placeholder: string; onPress: () => void }) => (
  <TouchableOpacity style={styles.pickerField} onPress={onPress}>
    <Text style={[styles.pickerFieldText, !value && { color: '#94A3B8' }]} numberOfLines={1}>{value || placeholder}</Text>
    <Ionicons name="chevron-down" size={16} color="#94A3B8" />
  </TouchableOpacity>
);
const SingleRow = ({ v, active, onPress }: { v: string; active: boolean; onPress: () => void }) => (
  <TouchableOpacity style={styles.optRow} onPress={onPress}>
    <Text style={styles.optText}>{v}</Text>
    {active && <Ionicons name="checkmark-circle" size={18} color="#16A34A" />}
  </TouchableOpacity>
);
const MultiRow = ({ v, active, onPress }: { v: string; active: boolean; onPress: () => void }) => (
  <TouchableOpacity style={styles.optRow} onPress={onPress}>
    <Ionicons name={active ? 'checkbox' : 'square-outline'} size={18} color={active ? '#A21CAF' : '#94A3B8'} />
    <Text style={[styles.optText, { marginLeft: 8 }]}>{v}</Text>
  </TouchableOpacity>
);

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 14, gap: 4 },
  iconHdr: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: '#FFF', marginLeft: 6 },
  empty: { alignItems: 'center', paddingTop: 60, gap: 8 },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: '#0F172A' },
  emptyDesc: { fontSize: 13, color: '#64748B', textAlign: 'center', paddingHorizontal: 28, lineHeight: 18 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#A21CAF', paddingHorizontal: 16, paddingVertical: 10, borderRadius: 12, marginTop: 10 },
  emptyBtnText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: '#EEF2F7' },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  avatar: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#D946EF', alignItems: 'center', justifyContent: 'center' },
  name: { fontSize: 15, fontWeight: '700', color: '#0F172A' },
  email: { fontSize: 12, color: '#64748B' },
  badgeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 5, marginTop: 5 },
  badge: { backgroundColor: '#FAE8FF', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  badgeText: { fontSize: 10.5, fontWeight: '700', color: '#A21CAF' },
  badgeAlt: { backgroundColor: '#EEF2FF', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  badgeAltText: { fontSize: 10.5, fontWeight: '700', color: '#4338CA' },
  badgeFee: { backgroundColor: '#DCFCE7', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  badgeFeeText: { fontSize: 10.5, fontWeight: '700', color: '#16A34A' },
  metaLine: { fontSize: 11.5, color: '#475569', marginTop: 8 },
  cardActions: { flexDirection: 'row', gap: 18, borderTopWidth: 1, borderTopColor: '#F1F5F9', paddingTop: 8, marginTop: 8 },
  actBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  actText: { fontSize: 12.5, fontWeight: '700', color: '#A21CAF' },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 18, maxHeight: '94%' },
  sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sheetTitle: { fontSize: 17, fontWeight: '800', color: '#0F172A' },
  label: { fontSize: 12, fontWeight: '700', color: '#475569', marginBottom: 4, marginTop: 10 },
  input: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A', backgroundColor: '#FAFAFA' },
  pickerField: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11, backgroundColor: '#FAFAFA' },
  pickerFieldText: { fontSize: 14, color: '#0F172A', flex: 1, marginRight: 8 },
  orgHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 18, marginBottom: 6 },
  orgTitle: { fontSize: 14, fontWeight: '800', color: '#0F172A' },
  addOrgBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#A21CAF', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  addOrgText: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  orgCard: { backgroundColor: '#F8FAFC', borderRadius: 12, padding: 10, marginBottom: 8, borderWidth: 1, borderColor: '#E2E8F0' },
  orgCardHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  orgIdx: { fontSize: 12, fontWeight: '700', color: '#A21CAF' },
  orgInput: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: '#0F172A', backgroundColor: '#FFF', marginBottom: 6 },
  orgRow: { flexDirection: 'row', gap: 6 },
  orgHalf: { flex: 1 },
  orgThird: { flex: 1 },
  activeToggle: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 14, marginBottom: 6 },
  activeLabel: { fontSize: 13, fontWeight: '600', color: '#475569' },
  saveBtn: { backgroundColor: '#A21CAF', paddingVertical: 14, borderRadius: 12, alignItems: 'center', marginTop: 12 },
  saveBtnText: { color: '#FFF', fontSize: 15, fontWeight: '800' },
  pickerBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 18 },
  pickerCard: { backgroundColor: '#FFF', borderRadius: 16, padding: 16, maxHeight: '80%' },
  optRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 11, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  optText: { fontSize: 14, color: '#0F172A', flex: 1 },
  doneBtn: { backgroundColor: '#A21CAF', paddingVertical: 12, borderRadius: 10, alignItems: 'center', marginTop: 10 },
  doneBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  bulkHint: { fontSize: 12, color: '#64748B', lineHeight: 17, marginBottom: 10 },
  bulkInput: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, padding: 12, fontSize: 12.5, color: '#0F172A', backgroundColor: '#FAFAFA', minHeight: 180, textAlignVertical: 'top', fontFamily: 'monospace' },
  bulkResult: { backgroundColor: '#F0FDF4', borderRadius: 10, padding: 10, marginTop: 10 },
  bulkResultText: { fontSize: 13, fontWeight: '700', color: '#166534' },
  bulkErr: { fontSize: 11.5, color: '#B91C1C', marginTop: 3 },
});
