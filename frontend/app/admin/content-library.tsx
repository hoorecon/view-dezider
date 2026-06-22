/**
 * Admin · Content Library CMS
 * Edit verbatim coaching scripts for any module (starting with Tenses & Feels).
 *
 * Flow:
 *   1. Pick a module from the chip row.
 *   2. (Optional) Pick locale tabs (en / hi / ta / te / mr / kn).
 *   3. See all blocks for that (module, locale); click one to edit.
 *   4. Dynamic form rendered from /content-library/schema/{module}.
 *   5. Save → PUT /content-library/{id}. Soft-delete = active=false.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput,
  ActivityIndicator, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

interface ModuleInfo { module: string; label: string; blocks: number; }
interface FieldDef { key: string; label: string; type: string; options?: string[]; required?: boolean; }
interface SchemaInfo { module: string; schema: { label: string; fields: FieldDef[] }; }
interface Block {
  id?: string; module: string; key: string; locale: string;
  title?: string; short?: string; order?: number; active?: boolean;
  fields?: Record<string, any>;
  version?: number;
}

const LOCALES = ['en', 'hi', 'ta', 'te', 'mr', 'kn'];

export default function AdminContentLibrary() {
  const router = useRouter();
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [moduleKey, setModuleKey] = useState<string>('tenses_feels');
  const [locale, setLocale] = useState<string>('en');
  const [schema, setSchema] = useState<SchemaInfo | null>(null);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [editing, setEditing] = useState<Block | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadModules = async () => {
    try {
      const { data } = await api.get('/content-library/modules');
      setModules(data?.modules || []);
    } catch (e: any) {
      showAlert('Load modules failed', e?.response?.data?.detail || e.message);
    }
  };

  const loadSchema = async (m: string) => {
    try {
      const { data } = await api.get(`/content-library/schema/${m}`);
      setSchema(data);
    } catch (e: any) {
      showAlert('Load schema failed', e?.response?.data?.detail || e.message);
    }
  };

  const loadBlocks = async () => {
    setBusy(true);
    try {
      const { data } = await api.get(`/content-library?module=${moduleKey}&locale=${locale}`);
      setBlocks(data?.items || []);
    } catch (e: any) {
      showAlert('Load blocks failed', e?.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  };

  useEffect(() => { loadModules(); }, []);
  useEffect(() => { loadSchema(moduleKey); loadBlocks(); /* eslint-disable-next-line */ }, [moduleKey, locale]);

  const seedTensesFeels = async (force = false) => {
    try {
      const { data } = await api.post(`/content-library/seed/tenses_feels?force=${force}`);
      showAlert('Seeded', `Inserted ${data.inserted}, updated ${data.updated} of ${data.total_seed_entries} entries.`);
      await loadBlocks();
      await loadModules();
    } catch (e: any) {
      showAlert('Seed failed', e?.response?.data?.detail || e.message);
    }
  };

  const startNew = () => setEditing({
    module: moduleKey, key: '', locale, title: '', short: '', order: 100, active: true, fields: {},
  });

  const setFieldVal = (k: string, v: any) => {
    if (!editing) return;
    setEditing({ ...editing, fields: { ...(editing.fields || {}), [k]: v } });
  };
  const setTop = (k: string, v: any) => {
    if (!editing) return;
    setEditing({ ...editing, [k]: v } as Block);
  };

  const save = async () => {
    if (!editing) return;
    if (!editing.key) { showAlert('Missing key', 'Key is required (e.g. "clinging")'); return; }
    if (!editing.title) { showAlert('Missing title', 'Title is required'); return; }
    setSaving(true);
    try {
      if (editing.id) {
        await api.put(`/content-library/${editing.id}`, editing);
      } else {
        await api.post('/content-library', editing);
      }
      setEditing(null);
      await loadBlocks();
      await loadModules();
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || e.message);
    } finally { setSaving(false); }
  };

  const removeBlock = async (b: Block) => {
    if (!b.id) return;
    if (!confirm(`Deactivate '${b.title || b.key}'?`)) return;
    try {
      await api.delete(`/content-library/${b.id}`);
      await loadBlocks();
    } catch (e: any) { showAlert('Delete failed', e?.response?.data?.detail || e.message); }
  };

  const fields = schema?.schema?.fields || [];
  const isTensesFeels = moduleKey === 'tenses_feels';

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>Content Library · Admin CMS</Text>
          <Text style={s.subtitle}>{blocks.length} blocks · locale: {locale}</Text>
        </View>
      </View>

      {/* Module picker */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.modRow} contentContainerStyle={{ paddingHorizontal: 12 }}>
        {modules.map(m => (
          <TouchableOpacity key={m.module} onPress={() => setModuleKey(m.module)} style={[s.modChip, moduleKey === m.module && s.modChipOn]}>
            <Text style={[s.modChipText, moduleKey === m.module && s.modChipTextOn]}>{m.label}</Text>
            <Text style={s.modChipCount}>{m.blocks}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Locale tabs */}
      <View style={s.localeRow}>
        {LOCALES.map(l => (
          <TouchableOpacity key={l} onPress={() => setLocale(l)} style={[s.locChip, locale === l && s.locChipOn]}>
            <Text style={[s.locText, locale === l && s.locTextOn]}>{l}</Text>
          </TouchableOpacity>
        ))}
        <View style={{ flex: 1 }} />
        {isTensesFeels && (
          <TouchableOpacity onPress={() => seedTensesFeels(false)} style={s.seedBtn}>
            <Ionicons name="download" size={14} color="#FFF" />
            <Text style={s.seedBtnText}>Seed Defaults</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity onPress={startNew} style={s.addBtn}>
          <Ionicons name="add" size={18} color="#FFF" />
          <Text style={s.addBtnText}>New</Text>
        </TouchableOpacity>
      </View>

      {/* Editor pane */}
      {editing ? (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
          <View style={s.editCard}>
            <View style={s.editHeader}>
              <Text style={s.editTitle}>{editing.id ? 'Edit Block' : 'New Block'}</Text>
              <TouchableOpacity onPress={() => setEditing(null)}><Ionicons name="close" size={22} color="#8A95B0" /></TouchableOpacity>
            </View>

            <Text style={s.lbl}>Key (slug, unique per locale) *</Text>
            <TextInput style={s.txt} value={editing.key} onChangeText={(v) => setTop('key', v)} placeholder="e.g. clinging" placeholderTextColor="#5b6478" editable={!editing.id} />

            <Text style={s.lbl}>Locale</Text>
            <View style={{ flexDirection: 'row', gap: 6, marginBottom: 10 }}>
              {LOCALES.map(l => (
                <TouchableOpacity key={l} onPress={() => setTop('locale', l)} style={[s.locChip, editing.locale === l && s.locChipOn]}>
                  <Text style={[s.locText, editing.locale === l && s.locTextOn]}>{l}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={s.lbl}>Title (display label) *</Text>
            <TextInput style={s.txt} value={editing.title || ''} onChangeText={(v) => setTop('title', v)} placeholder="e.g. Clinging" placeholderTextColor="#5b6478" />

            <Text style={s.lbl}>Short (1-line)</Text>
            <TextInput style={s.txt} value={editing.short || ''} onChangeText={(v) => setTop('short', v)} placeholderTextColor="#5b6478" />

            <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center', marginVertical: 8 }}>
              <Text style={s.lbl}>Order</Text>
              <TextInput style={[s.txt, { width: 80 }]} keyboardType="numeric" value={String(editing.order ?? 100)} onChangeText={(v) => setTop('order', parseInt(v || '0', 10) || 0)} />
              <View style={{ flex: 1 }} />
              <Text style={s.lbl}>Active</Text>
              <Switch value={!!editing.active} onValueChange={(v) => setTop('active', v)} />
            </View>

            <View style={s.divider} />

            {fields.map(f => (
              <View key={f.key}>
                <Text style={s.lbl}>{f.label}{f.required ? ' *' : ''}</Text>
                {f.type === 'select' ? (
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                    {(f.options || []).map(opt => (
                      <TouchableOpacity key={opt} onPress={() => setFieldVal(f.key, opt)} style={[s.optChip, editing.fields?.[f.key] === opt && s.optChipOn]}>
                        <Text style={[s.optText, editing.fields?.[f.key] === opt && s.optTextOn]}>{opt}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                ) : f.type === 'textarea_large' ? (
                  <TextInput style={[s.txt, { minHeight: 160, textAlignVertical: 'top' }]} multiline value={editing.fields?.[f.key] || ''} onChangeText={(v) => setFieldVal(f.key, v)} placeholderTextColor="#5b6478" />
                ) : f.type === 'textarea' ? (
                  <TextInput style={[s.txt, { minHeight: 70, textAlignVertical: 'top' }]} multiline value={editing.fields?.[f.key] || ''} onChangeText={(v) => setFieldVal(f.key, v)} placeholderTextColor="#5b6478" />
                ) : (
                  <TextInput style={s.txt} value={editing.fields?.[f.key] || ''} onChangeText={(v) => setFieldVal(f.key, v)} placeholderTextColor="#5b6478" />
                )}
              </View>
            ))}

            <TouchableOpacity style={[s.saveBtn, saving && { opacity: 0.5 }]} disabled={saving} onPress={save}>
              {saving ? <ActivityIndicator color="#FFF" /> : (
                <>
                  <Ionicons name="save" size={18} color="#FFF" />
                  <Text style={s.saveBtnText}>Save Block</Text>
                </>
              )}
            </TouchableOpacity>
          </View>
        </ScrollView>
      ) : (
        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          {busy ? <ActivityIndicator style={{ marginTop: 40 }} /> : blocks.length === 0 ? (
            <View style={s.empty}>
              <Text style={s.emptyText}>No blocks for this module/locale yet.</Text>
              {isTensesFeels && (
                <TouchableOpacity onPress={() => seedTensesFeels(false)} style={[s.addBtn, { marginTop: 16 }]}>
                  <Ionicons name="download" size={16} color="#FFF" />
                  <Text style={s.addBtnText}>Seed 12 Tenses & Feels defaults</Text>
                </TouchableOpacity>
              )}
            </View>
          ) : blocks.map((b) => (
            <TouchableOpacity key={b.id} onPress={() => setEditing(b)} style={s.row}>
              <View style={{ flex: 1 }}>
                <Text style={s.rowKey}>{b.order || '·'} · {b.key}</Text>
                <Text style={s.rowTitle}>{b.title || '—'}</Text>
                {b.short ? <Text style={s.rowShort} numberOfLines={1}>{b.short}</Text> : null}
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={[s.pill, b.active ? s.pillOk : s.pillDim]}>{b.active ? 'active' : 'inactive'}</Text>
                <Text style={s.ver}>v{b.version || 1}</Text>
                <TouchableOpacity onPress={(e) => { e.stopPropagation?.(); removeBlock(b); }} style={{ marginTop: 4 }}>
                  <Ionicons name="trash" size={16} color="#EF4444" />
                </TouchableOpacity>
              </View>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#0B1220' },
  header: { paddingHorizontal: 16, paddingVertical: 14, backgroundColor: '#111B2F', borderBottomColor: '#1F2A44', borderBottomWidth: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  backBtn: { padding: 6 },
  title: { color: '#FFF', fontSize: 17, fontWeight: '700' },
  subtitle: { color: '#8A95B0', fontSize: 12, marginTop: 2 },
  modRow: { backgroundColor: '#0E172A', borderBottomColor: '#1F2A44', borderBottomWidth: 1, maxHeight: 56 },
  modChip: { flexDirection: 'column', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderRadius: 10, marginRight: 8, marginVertical: 6, backgroundColor: '#111B2F', borderColor: '#1F2A44', borderWidth: 1 },
  modChipOn: { backgroundColor: '#5B7CFA', borderColor: '#5B7CFA' },
  modChipText: { color: '#8A95B0', fontSize: 12, fontWeight: '600' },
  modChipTextOn: { color: '#FFF' },
  modChipCount: { color: '#5b6478', fontSize: 10, marginTop: 1 },
  localeRow: { flexDirection: 'row', gap: 6, alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, backgroundColor: '#0E172A', borderBottomColor: '#1F2A44', borderBottomWidth: 1 },
  locChip: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, backgroundColor: '#111B2F', borderColor: '#1F2A44', borderWidth: 1 },
  locChipOn: { backgroundColor: '#5B7CFA', borderColor: '#5B7CFA' },
  locText: { color: '#8A95B0', fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  locTextOn: { color: '#FFF' },
  seedBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#10B981', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  seedBtnText: { color: '#FFF', fontSize: 11, fontWeight: '700' },
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#5B7CFA', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8 },
  addBtnText: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  row: { backgroundColor: '#111B2F', padding: 12, borderRadius: 10, marginBottom: 8, borderColor: '#1F2A44', borderWidth: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  rowKey: { color: '#8A95B0', fontSize: 11, fontWeight: '700', textTransform: 'uppercase' },
  rowTitle: { color: '#FFF', fontSize: 14, fontWeight: '700', marginTop: 2 },
  rowShort: { color: '#8A95B0', fontSize: 12, marginTop: 2 },
  pill: { fontSize: 10, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8, overflow: 'hidden' },
  pillOk: { color: '#10B981', backgroundColor: '#10B98122' },
  pillDim: { color: '#8A95B0', backgroundColor: '#1F2A44' },
  ver: { color: '#5b6478', fontSize: 10, marginTop: 4 },
  editCard: { backgroundColor: '#111B2F', padding: 16, borderRadius: 12, borderColor: '#1F2A44', borderWidth: 1 },
  editHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  editTitle: { color: '#FFF', fontWeight: '700', fontSize: 16 },
  lbl: { color: '#CED4E5', fontSize: 12, marginBottom: 4, marginTop: 6 },
  txt: { backgroundColor: '#0B1220', color: '#FFF', borderColor: '#1F2A44', borderWidth: 1, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, marginBottom: 6 },
  divider: { height: 1, backgroundColor: '#1F2A44', marginVertical: 10 },
  optChip: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, backgroundColor: '#0B1220', borderColor: '#1F2A44', borderWidth: 1 },
  optChipOn: { backgroundColor: '#5B7CFA', borderColor: '#5B7CFA' },
  optText: { color: '#8A95B0', fontSize: 11 },
  optTextOn: { color: '#FFF', fontWeight: '700' },
  saveBtn: { backgroundColor: '#5B7CFA', flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 8, padding: 14, borderRadius: 12, marginTop: 16 },
  saveBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },
  empty: { alignItems: 'center', padding: 24 },
  emptyText: { color: '#8A95B0', textAlign: 'center' },
});
