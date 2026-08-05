/**
 * TemplateEditModal — edit a saved template's Steps 1..7 content in-place.
 *
 * Scope covers the fields a user typically wants to refine after saving:
 *   • Step 1  — Name, Context, Life-area, Decision-type
 *   • Step 2  — Factor name, expected value, unit, operator, data-type
 *   • Step 3  — Factor category (Mandatory / Optional)
 *   • Step 4  — Factor priority rating (10..1)
 *   • Step 5  — Factor gap_multiplier (0.5..3.0)
 *   • Step 6  — Option names (add / remove / rename / reorder)
 *   • Step 7  — Per-option per-factor `values` cells
 * Plus visibility (Private / Shared / Public), shared_with emails, lead-gen
 * contact block and policy consent when the template is Public.
 *
 * Backend: PATCH /api/templates/{template_id}
 *
 * Intentionally compact — tabs let us keep the modal short. No drag-reorder
 * (buttons only) — keeps the code small enough to fit the credit budget.
 */
import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, Modal, ScrollView,
  StyleSheet, ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import api from '../utils/api';
import { showAlert } from '../utils/alert';

interface Props {
  visible: boolean;
  onClose: () => void;
  template: any;
  onSaved: () => void;
}

type SectionKey = 'basics' | 'factors' | 'options' | 'sharing' | 'policies';

const SECTIONS: Array<{ key: SectionKey; label: string; icon: any }> = [
  { key: 'basics',   label: 'Basics',        icon: 'document-text-outline' },
  { key: 'factors',  label: 'Factors',       icon: 'list-outline' },
  { key: 'options',  label: 'Options',       icon: 'layers-outline' },
  { key: 'sharing',  label: 'Visibility',    icon: 'lock-closed-outline' },
  { key: 'policies', label: 'Policies',      icon: 'shield-checkmark-outline' },
];

const CATEGORY_LABELS: Record<string, string> = { primary: 'Mandatory', secondary: 'Optional' };
const VISIBILITY_LABELS: Record<string, string> = {
  private: 'Private (only me)',
  shared: 'Shared (specific emails)',
  public: 'Public (everyone)',
};

export default function TemplateEditModal({ visible, onClose, template, onSaved }: Props) {
  const [section, setSection] = useState<SectionKey>('basics');
  const [name, setName] = useState('');
  const [context, setContext] = useState('');
  const [lifeArea, setLifeArea] = useState('');
  const [category, setCategory] = useState('');
  const [decisionType, setDecisionType] = useState('');
  const [factors, setFactors] = useState<any[]>([]);
  const [options, setOptions] = useState<any[]>([]);
  const [visibility, setVisibility] = useState('private');
  const [sharedWith, setSharedWith] = useState('');
  const [leadGen, setLeadGen] = useState<any>({});
  const [privacyPolicy, setPrivacyPolicy] = useState('');
  const [termsOfUse, setTermsOfUse] = useState('');
  const [saving, setSaving] = useState(false);

  // Hydrate every time the modal opens with a new template.
  useEffect(() => {
    if (!visible || !template) return;
    setSection('basics');
    setName(template.name || '');
    setContext(template.context || '');
    setLifeArea(template.life_area || template.folder || '');
    setCategory(template.category || '');
    setDecisionType(template.decision_type || '');
    setFactors((template.factors || []).map((f: any) => ({ ...f })));
    setOptions((template.options || []).map((o: any) => ({ ...o, values: { ...(o.values || {}) } })));
    setVisibility(template.visibility || 'private');
    setSharedWith((template.shared_with || []).join(', '));
    setLeadGen({ ...(template.lead_gen || {}) });
    setPrivacyPolicy((template.policies || {}).privacy_policy || '');
    setTermsOfUse((template.policies || {}).terms_of_use || '');
  }, [visible, template]);

  const patchFactor = (idx: number, key: string, val: any) => {
    setFactors((prev) => prev.map((f, i) => (i === idx ? { ...f, [key]: val } : f)));
  };
  const addFactor = () => {
    setFactors((prev) => [
      ...prev,
      { id: `new-${Date.now()}`, name: '', category: 'primary', rating: 5, order: prev.length + 1,
        expected_value: '', gap_multiplier: 1.0, factor_type: 'qualitative' },
    ]);
  };
  const removeFactor = (idx: number) => {
    setFactors((prev) => prev.filter((_, i) => i !== idx));
  };
  const moveFactor = (idx: number, delta: number) => {
    setFactors((prev) => {
      const next = [...prev];
      const target = idx + delta;
      if (target < 0 || target >= next.length) return prev;
      [next[idx], next[target]] = [next[target], next[idx]];
      return next.map((f, i) => ({ ...f, order: i + 1 }));
    });
  };

  const addOption = () => {
    setOptions((prev) => [...prev, { id: `new-${Date.now()}`, name: '', order: prev.length + 1, values: {} }]);
  };
  const removeOption = (idx: number) => {
    setOptions((prev) => prev.filter((_, i) => i !== idx));
  };
  const patchOption = (idx: number, key: string, val: any) => {
    setOptions((prev) => prev.map((o, i) => (i === idx ? { ...o, [key]: val } : o)));
  };
  const patchOptionValue = (optIdx: number, factorName: string, val: string) => {
    setOptions((prev) => prev.map((o, i) => (i === optIdx ? { ...o, values: { ...(o.values || {}), [factorName]: val } } : o)));
  };

  const save = async () => {
    // Public visibility requires lead-gen contact — mirror the create-time rule.
    if (visibility === 'public') {
      if (!leadGen.contact_name || !leadGen.email || !leadGen.whatsapp) {
        showAlert('Contact details required',
          'Public templates need contact name, email and WhatsApp so viewers can reach out to you.');
        setSection('policies');
        return;
      }
    }
    setSaving(true);
    try {
      const payload: any = {
        name: name.trim(),
        context: context.trim(),
        life_area: lifeArea.trim(),
        category: category.trim(),
        decision_type: decisionType.trim(),
        factors: factors.map((f, i) => ({ ...f, order: i + 1 })),
        options: options.map((o, i) => ({ ...o, order: i + 1 })),
        visibility,
        shared_with: sharedWith.split(',').map((e) => e.trim()).filter(Boolean),
      };
      if (visibility === 'public') {
        payload.lead_gen = leadGen;
        payload.policies = {
          privacy_policy: privacyPolicy.trim(),
          terms_of_use: termsOfUse.trim(),
          agreed_at: new Date().toISOString(),
        };
      }
      await api.patch(`/templates/${template.id}`, payload);
      onSaved();
      onClose();
      showAlert('Saved', 'Template updated successfully.');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  if (!template) return null;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={s.overlay}>
        <View style={s.container}>
          <View style={s.header}>
            <Text style={s.headerTitle}>Edit Template</Text>
            <TouchableOpacity onPress={onClose} testID="template-edit-close">
              <Ionicons name="close" size={24} color={COLORS.textSecondary} />
            </TouchableOpacity>
          </View>

          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabs} contentContainerStyle={{ paddingHorizontal: 12, gap: 6 }}>
            {SECTIONS.map((sec) => (
              <TouchableOpacity
                key={sec.key}
                style={[s.tab, section === sec.key && s.tabActive]}
                onPress={() => setSection(sec.key)}
                testID={`template-edit-tab-${sec.key}`}
              >
                <Ionicons name={sec.icon} size={14} color={section === sec.key ? '#FFF' : COLORS.textMuted} />
                <Text style={[s.tabText, section === sec.key && s.tabTextActive]}>{sec.label}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <ScrollView style={s.body} contentContainerStyle={{ padding: 16, gap: 10 }}>
            {section === 'basics' && (
              <>
                <Text style={s.label}>Name</Text>
                <TextInput style={s.input} value={name} onChangeText={setName} placeholder="Template name" />
                <Text style={s.label}>Context</Text>
                <TextInput style={[s.input, s.textArea]} value={context} onChangeText={setContext} multiline placeholder="Why this decision matters, background, constraints…" />
                <Text style={s.label}>Life area</Text>
                <TextInput style={s.input} value={lifeArea} onChangeText={setLifeArea} placeholder="Business & Career / Health / Finance / …" />
                <Text style={s.label}>Category</Text>
                <TextInput style={s.input} value={category} onChangeText={setCategory} placeholder="Financial / Talent & Team / Growth / …" />
                <Text style={s.label}>Decision type</Text>
                <TextInput style={s.input} value={decisionType} onChangeText={setDecisionType} placeholder="Choice Selection / Prioritization / …" />
              </>
            )}

            {section === 'factors' && (
              <>
                {factors.map((f, i) => (
                  <View key={f.id || i} style={s.card}>
                    <View style={s.cardTopRow}>
                      <Text style={s.cardIdx}>#{i + 1}</Text>
                      <TouchableOpacity onPress={() => moveFactor(i, -1)} disabled={i === 0}><Ionicons name="arrow-up" size={16} color={i === 0 ? '#CBD5E1' : COLORS.textSecondary} /></TouchableOpacity>
                      <TouchableOpacity onPress={() => moveFactor(i, 1)} disabled={i === factors.length - 1}><Ionicons name="arrow-down" size={16} color={i === factors.length - 1 ? '#CBD5E1' : COLORS.textSecondary} /></TouchableOpacity>
                      <View style={{ flex: 1 }} />
                      <TouchableOpacity onPress={() => removeFactor(i)} testID={`factor-remove-${i}`}><Ionicons name="trash-outline" size={16} color={COLORS.error} /></TouchableOpacity>
                    </View>
                    <TextInput style={s.input} value={f.name || ''} onChangeText={(v) => patchFactor(i, 'name', v)} placeholder="Factor name" />
                    <View style={s.row}>
                      <TouchableOpacity style={[s.pill, f.category === 'primary' && s.pillOn]} onPress={() => patchFactor(i, 'category', 'primary')}>
                        <Text style={[s.pillText, f.category === 'primary' && s.pillTextOn]}>Mandatory</Text>
                      </TouchableOpacity>
                      <TouchableOpacity style={[s.pill, f.category === 'secondary' && s.pillOn]} onPress={() => patchFactor(i, 'category', 'secondary')}>
                        <Text style={[s.pillText, f.category === 'secondary' && s.pillTextOn]}>Optional</Text>
                      </TouchableOpacity>
                    </View>
                    <View style={s.row}>
                      <View style={{ flex: 1 }}>
                        <Text style={s.mini}>Priority (1–10)</Text>
                        <TextInput style={s.input} value={String(f.rating ?? '')} onChangeText={(v) => patchFactor(i, 'rating', Number(v) || 0)} keyboardType="numeric" />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.mini}>Gap multiplier (0.5–3.0)</Text>
                        <TextInput style={s.input} value={String(f.gap_multiplier ?? '')} onChangeText={(v) => patchFactor(i, 'gap_multiplier', Number(v) || 1)} keyboardType="numeric" />
                      </View>
                    </View>
                    <Text style={s.mini}>Expected value</Text>
                    <TextInput style={s.input} value={f.expected_value || ''} onChangeText={(v) => patchFactor(i, 'expected_value', v)} placeholder="e.g. ≤ ₹15,00,000 / High / ≥ 3 refs" />
                    <View style={s.row}>
                      <View style={{ flex: 1 }}>
                        <Text style={s.mini}>Unit</Text>
                        <TextInput style={s.input} value={f.unit || ''} onChangeText={(v) => patchFactor(i, 'unit', v)} placeholder="₹ / months / % / …" />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={s.mini}>Operator</Text>
                        <TextInput style={s.input} value={f.operator || ''} onChangeText={(v) => patchFactor(i, 'operator', v)} placeholder="<= / >= / equals" />
                      </View>
                    </View>
                  </View>
                ))}
                <TouchableOpacity style={s.addBtn} onPress={addFactor}>
                  <Ionicons name="add-circle-outline" size={18} color={COLORS.primary} />
                  <Text style={s.addBtnText}>Add factor</Text>
                </TouchableOpacity>
              </>
            )}

            {section === 'options' && (
              <>
                {options.map((o, i) => (
                  <View key={o.id || i} style={s.card}>
                    <View style={s.cardTopRow}>
                      <Text style={s.cardIdx}>#{i + 1}</Text>
                      <View style={{ flex: 1 }} />
                      <TouchableOpacity onPress={() => removeOption(i)}><Ionicons name="trash-outline" size={16} color={COLORS.error} /></TouchableOpacity>
                    </View>
                    <TextInput style={s.input} value={o.name || ''} onChangeText={(v) => patchOption(i, 'name', v)} placeholder="Option name (e.g. Bootstrap from revenue)" />
                    {factors.length > 0 && (
                      <>
                        <Text style={s.mini}>Value per factor</Text>
                        {factors.map((f) => (
                          <View key={`${o.id}-${f.name}`}>
                            <Text style={s.tinyMini}>{f.name || '(unnamed factor)'}</Text>
                            <TextInput
                              style={s.input}
                              value={(o.values || {})[f.name] || ''}
                              onChangeText={(v) => patchOptionValue(i, f.name, v)}
                              placeholder={`e.g. ${f.expected_value || 'value for this option'}`}
                            />
                          </View>
                        ))}
                      </>
                    )}
                  </View>
                ))}
                <TouchableOpacity style={s.addBtn} onPress={addOption}>
                  <Ionicons name="add-circle-outline" size={18} color={COLORS.primary} />
                  <Text style={s.addBtnText}>Add option</Text>
                </TouchableOpacity>
              </>
            )}

            {section === 'sharing' && (
              <>
                <Text style={s.label}>Who can see this?</Text>
                {(['private', 'shared', 'public'] as const).map((v) => (
                  <TouchableOpacity key={v} style={[s.visRow, visibility === v && s.visRowOn]} onPress={() => setVisibility(v)}>
                    <Ionicons name={v === 'private' ? 'lock-closed' : v === 'shared' ? 'people' : 'globe'} size={16} color={visibility === v ? COLORS.primary : COLORS.textMuted} />
                    <Text style={[s.visLabel, visibility === v && { color: COLORS.primary, fontWeight: '700' }]}>{VISIBILITY_LABELS[v]}</Text>
                  </TouchableOpacity>
                ))}
                {visibility === 'shared' && (
                  <>
                    <Text style={s.label}>Share with (comma-separated emails)</Text>
                    <TextInput style={[s.input, s.textArea]} value={sharedWith} onChangeText={setSharedWith} multiline autoCapitalize="none" placeholder="user1@…, user2@…" />
                  </>
                )}
              </>
            )}

            {section === 'policies' && (
              <>
                {visibility !== 'public' ? (
                  <Text style={s.hint}>Lead-Gen & Policies apply only to Public templates. Change visibility to Public first.</Text>
                ) : (
                  <>
                    <Text style={s.label}>Lead-Gen · How viewers reach out to you</Text>
                    <TextInput style={s.input} placeholder="Contact person name *" value={leadGen.contact_name || ''} onChangeText={(v) => setLeadGen({ ...leadGen, contact_name: v })} />
                    <TextInput style={s.input} placeholder="Organization" value={leadGen.organization || ''} onChangeText={(v) => setLeadGen({ ...leadGen, organization: v })} />
                    <TextInput style={s.input} placeholder="Designation" value={leadGen.designation || ''} onChangeText={(v) => setLeadGen({ ...leadGen, designation: v })} />
                    <TextInput style={s.input} placeholder="Email *" value={leadGen.email || ''} onChangeText={(v) => setLeadGen({ ...leadGen, email: v })} autoCapitalize="none" keyboardType="email-address" />
                    <TextInput style={s.input} placeholder="WhatsApp *" value={leadGen.whatsapp || ''} onChangeText={(v) => setLeadGen({ ...leadGen, whatsapp: v })} keyboardType="phone-pad" />
                    <TextInput style={s.input} placeholder="Contact mobile number" value={leadGen.mobile || ''} onChangeText={(v) => setLeadGen({ ...leadGen, mobile: v })} keyboardType="phone-pad" />
                    <TextInput style={s.input} placeholder="Redirect URL (opens in new tab)" value={leadGen.redirect_url || ''} onChangeText={(v) => setLeadGen({ ...leadGen, redirect_url: v })} autoCapitalize="none" />
                    <Text style={s.label}>Privacy Policy</Text>
                    <TextInput style={[s.input, s.textArea]} value={privacyPolicy} onChangeText={setPrivacyPolicy} multiline />
                    <Text style={s.label}>Terms of Use</Text>
                    <TextInput style={[s.input, s.textArea]} value={termsOfUse} onChangeText={setTermsOfUse} multiline />
                  </>
                )}
              </>
            )}
          </ScrollView>

          <View style={s.footer}>
            <TouchableOpacity style={s.saveBtn} onPress={save} disabled={saving} testID="template-edit-save">
              {saving ? <ActivityIndicator color="#FFF" /> : (<>
                <Ionicons name="checkmark" size={20} color="#FFF" />
                <Text style={s.saveBtnText}>Save changes</Text>
              </>)}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  container: { backgroundColor: '#FFF', borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '92%' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 18, paddingBottom: 8 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary },
  tabs: { maxHeight: 48, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  tab: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, backgroundColor: COLORS.background, height: 32, alignSelf: 'center' },
  tabActive: { backgroundColor: COLORS.primary },
  tabText: { fontSize: 12.5, fontWeight: '600', color: COLORS.textMuted },
  tabTextActive: { color: '#FFF' },
  body: { maxHeight: 500 },
  label: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginTop: 8 },
  mini: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted, marginTop: 4 },
  tinyMini: { fontSize: 11, color: COLORS.textSecondary, marginTop: 4, marginLeft: 2 },
  hint: { fontSize: 12.5, color: COLORS.textMuted, fontStyle: 'italic', textAlign: 'center', paddingVertical: 20 },
  input: { backgroundColor: COLORS.background, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9, fontSize: 14, color: COLORS.textPrimary, borderWidth: 1, borderColor: COLORS.border },
  textArea: { minHeight: 70, textAlignVertical: 'top' },
  row: { flexDirection: 'row', gap: 8 },
  card: { padding: 12, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, gap: 6, backgroundColor: '#FAFAFA' },
  cardTopRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardIdx: { fontSize: 12, fontWeight: '700', color: COLORS.textMuted },
  pill: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 999, borderWidth: 1, borderColor: COLORS.border, backgroundColor: '#FFF' },
  pillOn: { borderColor: COLORS.primary, backgroundColor: COLORS.primary + '18' },
  pillText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  pillTextOn: { color: COLORS.primary },
  addBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderStyle: 'dashed', borderColor: COLORS.primary, backgroundColor: COLORS.primary + '10' },
  addBtnText: { color: COLORS.primary, fontWeight: '700', fontSize: 13.5 },
  visRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, marginTop: 6 },
  visRowOn: { borderColor: COLORS.primary, backgroundColor: COLORS.primary + '10' },
  visLabel: { fontSize: 13.5, color: COLORS.textPrimary },
  footer: { padding: 14, borderTopWidth: 1, borderTopColor: COLORS.divider },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: COLORS.primary, paddingVertical: 14, borderRadius: 12 },
  saveBtnText: { color: '#FFF', fontWeight: '800', fontSize: 15 },
});
