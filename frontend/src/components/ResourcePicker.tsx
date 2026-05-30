/**
 * ResourcePicker — used in Goal Setter's "Realistic" section.
 *
 * Lets the user pick contacts (Self + Others) and tag which of their
 *   - resources (finance / infrastructure / people_connects)
 *   - social_links (gmail / linkedin / x / ...)
 * are relevant to making this goal Realistic.
 *
 * Stored shape (in goal.realistic_resources[]):
 *  { contact_id, contact_name, is_self, org_type, picked_resource_types[], picked_social_links[] }
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator,
  Modal, FlatList, TextInput, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import api from '../utils/api';

export interface PickedResource {
  contact_id: string;
  contact_name: string;
  is_self?: boolean;
  org_type?: string;
  picked_resource_types: string[];   // 'finance' | 'infrastructure' | 'people_connects'
  picked_social_links: string[];     // 'gmail' | 'linkedin' | ...
}

interface Props {
  value: PickedResource[];
  onChange: (v: PickedResource[]) => void;
}

const RESOURCE_TYPES = [
  { id: 'finance', label: 'Finance', icon: 'cash' as const, color: '#10B981' },
  { id: 'infrastructure', label: 'Infrastructure', icon: 'hardware-chip' as const, color: '#3B82F6' },
  { id: 'people_connects', label: 'People Connects', icon: 'people' as const, color: '#EC4899' },
];

const SOCIAL_LINKS = [
  { id: 'gmail', label: 'Gmail', icon: 'mail' as const },
  { id: 'official_email', label: 'Official Email', icon: 'mail-open' as const },
  { id: 'whatsapp', label: 'WhatsApp', icon: 'logo-whatsapp' as const },
  { id: 'telegram', label: 'Telegram', icon: 'paper-plane' as const },
  { id: 'linkedin', label: 'LinkedIn', icon: 'logo-linkedin' as const },
  { id: 'youtube', label: 'YouTube', icon: 'logo-youtube' as const },
  { id: 'instagram', label: 'Instagram', icon: 'logo-instagram' as const },
  { id: 'facebook', label: 'Facebook', icon: 'logo-facebook' as const },
  { id: 'x', label: 'X', icon: 'logo-twitter' as const },
  { id: 'reddit', label: 'Reddit', icon: 'logo-reddit' as const },
];

export default function ResourcePicker({ value, onChange }: Props) {
  const picked = Array.isArray(value) ? value : [];
  const [contacts, setContacts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        await api.post('/contacts/ensure-self', {}).catch(() => {});
        const res = await api.get('/contacts', { params: { limit: 200 } });
        setContacts(res.data?.contacts || []);
      } catch (e) {
        setContacts([]);
      } finally { setLoading(false); }
    })();
  }, []);

  const contactsById = useMemo(() => {
    const map: Record<string, any> = {};
    contacts.forEach(c => { map[c.id] = c; });
    return map;
  }, [contacts]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return contacts;
    return contacts.filter(c => (c.name || '').toLowerCase().includes(q));
  }, [contacts, search]);

  const isContactPicked = (id: string) => picked.some(p => p.contact_id === id);

  const addContact = (c: any) => {
    if (isContactPicked(c.id)) return;
    onChange([
      ...picked,
      {
        contact_id: c.id,
        contact_name: c.name,
        is_self: !!c.is_self,
        org_type: c.org_type || '',
        picked_resource_types: [],
        picked_social_links: [],
      },
    ]);
  };

  const removeContact = (id: string) => {
    onChange(picked.filter(p => p.contact_id !== id));
  };

  const toggleResType = (id: string, t: string) => {
    onChange(picked.map(p => {
      if (p.contact_id !== id) return p;
      const has = p.picked_resource_types.includes(t);
      return {
        ...p,
        picked_resource_types: has ? p.picked_resource_types.filter(x => x !== t) : [...p.picked_resource_types, t],
      };
    }));
  };

  const toggleSocial = (id: string, s: string) => {
    onChange(picked.map(p => {
      if (p.contact_id !== id) return p;
      const has = p.picked_social_links.includes(s);
      return {
        ...p,
        picked_social_links: has ? p.picked_social_links.filter(x => x !== s) : [...p.picked_social_links, s],
      };
    }));
  };

  if (loading) {
    return (
      <View style={st.loadWrap}>
        <ActivityIndicator size="small" color={COLORS.primary} />
        <Text style={st.loadText}>Loading contacts…</Text>
      </View>
    );
  }

  return (
    <View>
      <View style={st.headerRow}>
        <Ionicons name="briefcase" size={14} color="#7C3AED" />
        <Text style={st.headerText}>Resources & Connections ({picked.length} contacts)</Text>
      </View>
      <Text style={st.hint}>
        Pick people whose resources or networks make this goal realistic.
      </Text>

      {picked.length === 0 ? (
        <View style={st.empty}>
          <Text style={st.emptyText}>No contacts picked yet.</Text>
        </View>
      ) : (
        picked.map(p => {
          const c = contactsById[p.contact_id] || {};
          const fin = c.resources?.finance;
          const infra = c.resources?.infrastructure;
          const ppl = c.resources?.people_connects;
          return (
            <View key={p.contact_id} style={st.card}>
              <View style={st.cardHead}>
                <Ionicons name={p.is_self ? 'person-circle' : 'person-outline'} size={18} color={p.is_self ? '#F59E0B' : '#7C3AED'} />
                <Text style={st.cardName}>{p.is_self ? `${p.contact_name} (You)` : p.contact_name}</Text>
                {!!p.org_type && (
                  <View style={st.orgBadge}>
                    <Text style={st.orgBadgeText}>{p.org_type}</Text>
                  </View>
                )}
                <View style={{ flex: 1 }} />
                <TouchableOpacity onPress={() => removeContact(p.contact_id)}>
                  <Ionicons name="close-circle" size={18} color={COLORS.textMuted} />
                </TouchableOpacity>
              </View>

              <Text style={st.sectionLabel}>Resources to leverage</Text>
              <View style={st.chipWrap}>
                {RESOURCE_TYPES.map(r => {
                  const on = p.picked_resource_types.includes(r.id);
                  const preview =
                    r.id === 'finance' && fin?.amount ? ` (${fin.amount} ${fin.currency || ''})` :
                    r.id === 'infrastructure' && infra?.description ? ` (${(infra.description || '').slice(0, 18)})` :
                    r.id === 'people_connects' && (ppl?.count > 0) ? ` (${ppl.count} ppl)` : '';
                  return (
                    <TouchableOpacity
                      key={r.id}
                      style={[st.chip, on && { backgroundColor: r.color, borderColor: r.color }]}
                      onPress={() => toggleResType(p.contact_id, r.id)}
                    >
                      <Ionicons name={r.icon} size={11} color={on ? '#FFF' : r.color} />
                      <Text style={[st.chipTxt, on && { color: '#FFF' }]}>{r.label}{preview}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              <Text style={st.sectionLabel}>Reach via</Text>
              <View style={st.chipWrap}>
                {SOCIAL_LINKS.map(s => {
                  const linkVal = c.social_links?.[s.id] || '';
                  const on = p.picked_social_links.includes(s.id);
                  if (!linkVal) {
                    return (
                      <View key={s.id} style={[st.chip, st.chipDisabled]}>
                        <Ionicons name={s.icon} size={11} color="#9CA3AF" />
                        <Text style={[st.chipTxt, { color: '#9CA3AF' }]}>{s.label}</Text>
                      </View>
                    );
                  }
                  return (
                    <TouchableOpacity
                      key={s.id}
                      style={[st.chip, on && { backgroundColor: '#7C3AED', borderColor: '#7C3AED' }]}
                      onPress={() => toggleSocial(p.contact_id, s.id)}
                    >
                      <Ionicons name={s.icon} size={11} color={on ? '#FFF' : '#7C3AED'} />
                      <Text style={[st.chipTxt, on && { color: '#FFF' }]}>{s.label}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>
          );
        })
      )}

      <TouchableOpacity style={st.addBtn} onPress={() => setOpen(true)}>
        <Ionicons name="add-circle" size={14} color="#7C3AED" />
        <Text style={st.addBtnTxt}>Add Contact</Text>
      </TouchableOpacity>

      {/* Contact picker modal */}
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <View style={st.modalBg}>
          <View style={st.modalCard}>
            <Text style={st.modalTitle}>Pick a Contact</Text>
            <TextInput
              style={st.input}
              placeholder="Search contacts…"
              placeholderTextColor={COLORS.textMuted}
              value={search}
              onChangeText={setSearch}
            />
            <FlatList
              data={filtered}
              keyExtractor={c => c.id}
              style={{ maxHeight: 320 }}
              renderItem={({ item }) => {
                const already = isContactPicked(item.id);
                return (
                  <TouchableOpacity
                    style={[st.row, already && { opacity: 0.5 }]}
                    disabled={already}
                    onPress={() => { addContact(item); setOpen(false); }}
                  >
                    <Ionicons
                      name={item.is_self ? 'person-circle' : 'person-outline'}
                      size={18}
                      color={item.is_self ? '#F59E0B' : '#7C3AED'}
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={st.rowName}>{item.is_self ? `${item.name} (You)` : item.name}</Text>
                      {!!item.org_type && <Text style={st.rowSub}>{item.org_type}{item.org_subtype ? ` · ${item.org_subtype}` : ''}</Text>}
                    </View>
                    {already && <Text style={st.rowSub}>added</Text>}
                  </TouchableOpacity>
                );
              }}
              ListEmptyComponent={<Text style={st.emptyText}>No matches.</Text>}
            />
            <TouchableOpacity style={st.closeBtn} onPress={() => setOpen(false)}>
              <Text style={st.closeBtnTxt}>Close</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const st = StyleSheet.create({
  loadWrap: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 10 },
  loadText: { fontSize: 11, color: COLORS.textMuted },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4 },
  headerText: { fontSize: 12, fontWeight: '700', color: '#7C3AED' },
  hint: { fontSize: 11, color: '#6D28D9', marginBottom: 8 },
  empty: { padding: 12, alignItems: 'center', borderRadius: 8, backgroundColor: '#F5F3FF' },
  emptyText: { fontSize: 11, color: '#6D28D9', fontStyle: 'italic' },
  card: { backgroundColor: '#FFFFFF', borderRadius: 10, padding: 10, borderWidth: 1, borderColor: '#E9D5FF', marginBottom: 8 },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  cardName: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary },
  orgBadge: { backgroundColor: '#EDE9FE', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8 },
  orgBadgeText: { fontSize: 10, color: '#7C3AED', fontWeight: '600' },
  sectionLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted, marginTop: 6, marginBottom: 3, textTransform: 'uppercase' },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 5 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, borderWidth: 1, borderColor: '#E9D5FF', backgroundColor: '#F5F3FF' },
  chipDisabled: { borderColor: '#E5E7EB', backgroundColor: '#F9FAFB' },
  chipTxt: { fontSize: 10, fontWeight: '600', color: '#7C3AED' },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, justifyContent: 'center', paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: '#7C3AED', borderStyle: 'dashed', marginTop: 4 },
  addBtnTxt: { fontSize: 12, fontWeight: '600', color: '#7C3AED' },

  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalCard: { backgroundColor: '#FFFFFF', borderRadius: 14, padding: 14, width: '100%', maxWidth: 420 },
  modalTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  input: { borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 8, paddingHorizontal: 10, paddingVertical: Platform.OS === 'web' ? 8 : 6, marginBottom: 8, fontSize: 12, color: COLORS.textPrimary, backgroundColor: '#F9FAFB' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, paddingHorizontal: 6, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  rowName: { fontSize: 13, color: COLORS.textPrimary, fontWeight: '600' },
  rowSub: { fontSize: 11, color: COLORS.textMuted },
  closeBtn: { marginTop: 10, padding: 10, borderRadius: 8, backgroundColor: '#F1F5F9', alignItems: 'center' },
  closeBtnTxt: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
});
