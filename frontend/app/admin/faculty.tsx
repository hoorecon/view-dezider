/**
 * Admin → Faculty Management Module
 * Comprehensive directory for Academic & Research Faculty.
 * Supports CRUD, Search & Filtering (by Department, Designation, Institution),
 * Status toggling, and Bulk JSON Upload.
 */
import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Modal,
  FlatList,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';
import { COLORS } from '../../src/constants/colors';

interface FacultyOrg {
  org_name: string;
  role?: string;
  department?: string;
  contact_email?: string;
  phone?: string;
  city?: string;
}

interface Faculty {
  faculty_id: string;
  name: string;
  email: string;
  department?: string;
  designation?: string;
  institution?: string;
  qualification?: string;
  experience_years?: string;
  headline?: string;
  bio?: string;
  phone?: string;
  whatsapp?: string;
  languages?: string[];
  specializations?: string[];
  subjects?: string[];
  is_active: boolean;
  is_verified?: boolean;
  organizations?: FacultyOrg[];
  created_at?: string;
}

const EMPTY_FORM = {
  name: '',
  email: '',
  department: '',
  designation: '',
  institution: '',
  qualification: '',
  experience_years: '',
  headline: '',
  bio: '',
  phone: '',
  whatsapp: '',
  specializationsText: '',
  subjectsText: '',
  languagesText: '',
  is_active: true,
};

const COMMON_DEPARTMENTS = [
  'Computer Science & Engineering',
  'Management & Business Studies',
  'Health & Medical Sciences',
  'Economics & Finance',
  'Psychology & Behavioral Science',
  'Law & Public Policy',
  'Electrical & Electronics',
  'Mechanical Engineering',
  'Life Sciences & Biotechnology',
  'Humanities & Social Sciences',
];

const COMMON_DESIGNATIONS = [
  'Professor',
  'Associate Professor',
  'Assistant Professor',
  'Dean / Director',
  'Head of Department (HOD)',
  'Visiting Facilitator',
  'Adjunct Professor',
  'Senior Lecturer',
  'Research Fellow',
];

export default function FacultyScreen() {
  const router = useRouter();
  const [facultyList, setFacultyList] = useState<Faculty[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedDept, setSelectedDept] = useState<string>('All');

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Faculty | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const [showBulk, setShowBulk] = useState(false);
  const [bulkText, setBulkText] = useState('');
  const [bulkResult, setBulkResult] = useState<any>(null);

  const fetchFaculty = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/faculty?include_inactive=true&limit=500');
      setFacultyList(res.data?.items || []);
    } catch {
      setFacultyList([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFaculty();
  }, [fetchFaculty]);

  const departmentsList = useMemo(() => {
    const fromData = Array.from(new Set(facultyList.map((f) => f.department).filter(Boolean))) as string[];
    const combined = Array.from(new Set(['All', ...fromData, ...COMMON_DEPARTMENTS]));
    return combined;
  }, [facultyList]);

  const filteredFaculty = useMemo(() => {
    const q = search.trim().toLowerCase();
    return facultyList.filter((item) => {
      if (selectedDept !== 'All' && item.department !== selectedDept) return false;
      if (!q) return true;
      const haystack = `${item.name} ${item.email} ${item.department || ''} ${item.designation || ''} ${item.institution || ''} ${(item.specializations || []).join(' ')}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [facultyList, search, selectedDept]);

  const openAdd = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setShowForm(true);
  };

  const openEdit = (f: Faculty) => {
    setEditing(f);
    setForm({
      name: f.name || '',
      email: f.email || '',
      department: f.department || '',
      designation: f.designation || '',
      institution: f.institution || '',
      qualification: f.qualification || '',
      experience_years: f.experience_years || '',
      headline: f.headline || '',
      bio: f.bio || '',
      phone: f.phone || '',
      whatsapp: f.whatsapp || '',
      specializationsText: (f.specializations || []).join(', '),
      subjectsText: (f.subjects || []).join(', '),
      languagesText: (f.languages || []).join(', '),
      is_active: f.is_active,
    });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.email.trim() || !form.email.includes('@')) {
      showAlert('Validation Error', 'A valid name and email are required');
      return;
    }

    setSaving(true);
    const payload = {
      name: form.name.trim(),
      email: form.email.trim().toLowerCase(),
      department: form.department.trim() || null,
      designation: form.designation.trim() || null,
      institution: form.institution.trim() || null,
      qualification: form.qualification.trim() || null,
      experience_years: form.experience_years.trim() || null,
      headline: form.headline.trim() || null,
      bio: form.bio.trim() || null,
      phone: form.phone.trim() || null,
      whatsapp: form.whatsapp.trim() || null,
      specializations: form.specializationsText.split(',').map((s) => s.trim()).filter(Boolean),
      subjects: form.subjectsText.split(',').map((s) => s.trim()).filter(Boolean),
      languages: form.languagesText.split(',').map((s) => s.trim()).filter(Boolean),
      is_active: form.is_active,
    };

    try {
      if (editing) {
        await api.put(`/faculty/${editing.faculty_id}`, payload);
        showAlert('Success', 'Facilitator profile updated successfully');
      } else {
        await api.post('/faculty', payload);
        showAlert('Success', 'Facilitator added successfully');
      }
      setShowForm(false);
      fetchFaculty();
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Failed to save facilitator');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (f: Faculty) => {
    showAlert('Delete Facilitator', `Are you sure you want to remove ${f.name}?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.delete(`/faculty/${f.faculty_id}`);
            fetchFaculty();
          } catch (err: any) {
            showAlert('Error', err?.response?.data?.detail || 'Delete failed');
          }
        },
      },
    ]);
  };

  const toggleActive = async (f: Faculty) => {
    try {
      await api.put(`/faculty/${f.faculty_id}`, { is_active: !f.is_active });
      fetchFaculty();
    } catch {
      showAlert('Error', 'Failed to update active status');
    }
  };

  const runBulk = async () => {
    let parsed: any;
    try {
      parsed = JSON.parse(bulkText);
      if (!Array.isArray(parsed)) throw new Error('Not an array');
    } catch {
      showAlert('Invalid JSON', 'Please paste a JSON array of facilitator objects.');
      return;
    }

    setSaving(true);
    try {
      const res = await api.post('/faculty/bulk', { faculty_list: parsed });
      setBulkResult(res.data);
      fetchFaculty();
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Bulk upload failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <TouchableOpacity onPress={() => safeBack(router, '/admin')} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={20} color={COLORS.textPrimary} />
          </TouchableOpacity>
          <View>
            <Text style={styles.headerTitle}>Facilitators Management</Text>
            <Text style={styles.headerSub}>
              {facultyList.length} facilitators · Academic, Research & Institutional directory
            </Text>
          </View>
        </View>

        <View style={{ flexDirection: 'row', gap: 8 }}>
          <TouchableOpacity style={styles.secondaryBtn} onPress={() => setShowBulk(true)}>
            <Ionicons name="cloud-upload-outline" size={16} color={COLORS.primary} />
            <Text style={styles.secondaryBtnText}>Bulk Upload</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.primaryBtn} onPress={openAdd}>
            <LinearGradient
              colors={['#7C3AED', '#9333EA']}
              style={styles.btnGrad}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
            >
              <Ionicons name="add" size={18} color="#fff" />
              <Text style={styles.primaryBtnText}>Add Facilitator</Text>
            </LinearGradient>
          </TouchableOpacity>
        </View>
      </View>

      {/* Search & Department Filters */}
      <View style={styles.filterSection}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={18} color={COLORS.textMuted} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search by name, email, department, designation, subject..."
            placeholderTextColor={COLORS.textMuted}
            value={search}
            onChangeText={setSearch}
          />
          {search ? (
            <TouchableOpacity onPress={() => setSearch('')}>
              <Ionicons name="close-circle" size={18} color={COLORS.textMuted} />
            </TouchableOpacity>
          ) : null}
        </View>

        {/* Horizontal Department Pill Filter */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.deptScroll}>
          {departmentsList.map((dept) => (
            <TouchableOpacity
              key={dept}
              style={[styles.deptPill, selectedDept === dept && styles.deptPillActive]}
              onPress={() => setSelectedDept(dept)}
            >
              <Text style={[styles.deptPillText, selectedDept === dept && styles.deptPillTextActive]}>
                {dept}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* List */}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={styles.loadingText}>Loading facilitators directory...</Text>
        </View>
      ) : filteredFaculty.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="school-outline" size={56} color={COLORS.textMuted} />
          <Text style={styles.emptyTitle}>No Facilitators Found</Text>
          <Text style={styles.emptySub}>
            {facultyList.length === 0
              ? 'Click "Add Facilitator" to create your first facilitator profile.'
              : 'Try clearing your search query or department filter.'}
          </Text>
        </View>
      ) : (
        <FlatList
          data={filteredFaculty}
          keyExtractor={(item) => item.faculty_id}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>{(item.name || 'F')[0].toUpperCase()}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <Text style={styles.facultyName}>{item.name}</Text>
                    {item.is_verified && (
                      <Ionicons name="checkmark-circle" size={16} color="#10B981" />
                    )}
                    <View style={[styles.statusBadge, { backgroundColor: item.is_active ? '#10B98115' : '#EF444415' }]}>
                      <Text style={[styles.statusText, { color: item.is_active ? '#10B981' : '#EF4444' }]}>
                        {item.is_active ? 'Active' : 'Inactive'}
                      </Text>
                    </View>
                  </View>

                  <Text style={styles.facultyRole}>
                    {[item.designation, item.department, item.institution].filter(Boolean).join(' · ')}
                  </Text>
                  <Text style={styles.facultyEmail}>{item.email}</Text>
                </View>

                {/* Actions */}
                <View style={styles.cardActions}>
                  <TouchableOpacity
                    style={styles.iconBtn}
                    onPress={() => toggleActive(item)}
                    title={item.is_active ? 'Deactivate' : 'Activate'}
                  >
                    <Ionicons
                      name={item.is_active ? 'pause-circle-outline' : 'play-circle-outline'}
                      size={20}
                      color={item.is_active ? '#F59E0B' : '#10B981'}
                    />
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.iconBtn} onPress={() => openEdit(item)}>
                    <Ionicons name="pencil-outline" size={19} color={COLORS.primary} />
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.iconBtn} onPress={() => handleDelete(item)}>
                    <Ionicons name="trash-outline" size={19} color="#EF4444" />
                  </TouchableOpacity>
                </View>
              </View>

              {/* Specializations & Subjects tags */}
              {((item.specializations && item.specializations.length > 0) || (item.subjects && item.subjects.length > 0)) && (
                <View style={styles.tagWrap}>
                  {(item.specializations || []).map((spec, i) => (
                    <View key={`spec-${i}`} style={styles.specTag}>
                      <Text style={styles.specTagText}>⭐ {spec}</Text>
                    </View>
                  ))}
                  {(item.subjects || []).map((subj, i) => (
                    <View key={`subj-${i}`} style={styles.subjTag}>
                      <Text style={styles.subjTagText}>📚 {subj}</Text>
                    </View>
                  ))}
                </View>
              )}

              {item.bio ? (
                <Text style={styles.bioText} numberOfLines={2}>
                  {item.bio}
                </Text>
              ) : null}
            </View>
          )}
        />
      )}

      {/* Add / Edit Modal */}
      <Modal visible={showForm} animationType="slide" transparent>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                {editing ? 'Edit Facilitator' : 'Add New Facilitator'}
              </Text>
              <TouchableOpacity onPress={() => setShowForm(false)}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>

            <ScrollView contentContainerStyle={styles.formBody}>
              <View style={styles.fieldRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Full Name *</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="e.g. Dr. Rajesh Kumar"
                    placeholderTextColor={COLORS.textMuted}
                    value={form.name}
                    onChangeText={(v) => setForm({ ...form, name: v })}
                  />
                </View>

                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Email Address *</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="e.g. rkumar@university.edu"
                    placeholderTextColor={COLORS.textMuted}
                    keyboardType="email-address"
                    autoCapitalize="none"
                    value={form.email}
                    onChangeText={(v) => setForm({ ...form, email: v })}
                  />
                </View>
              </View>

              <View style={styles.fieldRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Designation / Title</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="e.g. Professor & Dean"
                    placeholderTextColor={COLORS.textMuted}
                    value={form.designation}
                    onChangeText={(v) => setForm({ ...form, designation: v })}
                  />
                </View>

                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Department</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="e.g. Computer Science"
                    placeholderTextColor={COLORS.textMuted}
                    value={form.department}
                    onChangeText={(v) => setForm({ ...form, department: v })}
                  />
                </View>
              </View>

              <View style={styles.fieldRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Institution / University</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="e.g. National Institute of Tech"
                    placeholderTextColor={COLORS.textMuted}
                    value={form.institution}
                    onChangeText={(v) => setForm({ ...form, institution: v })}
                  />
                </View>

                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Highest Qualification</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="e.g. Ph.D (AI & Systems)"
                    placeholderTextColor={COLORS.textMuted}
                    value={form.qualification}
                    onChangeText={(v) => setForm({ ...form, qualification: v })}
                  />
                </View>
              </View>

              <View style={styles.fieldRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Experience (Years)</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="e.g. 15 years"
                    placeholderTextColor={COLORS.textMuted}
                    value={form.experience_years}
                    onChangeText={(v) => setForm({ ...form, experience_years: v })}
                  />
                </View>

                <View style={{ flex: 1 }}>
                  <Text style={styles.fieldLabel}>Phone / WhatsApp</Text>
                  <TextInput
                    style={styles.input}
                    placeholder="e.g. +91 9876543210"
                    placeholderTextColor={COLORS.textMuted}
                    value={form.phone}
                    onChangeText={(v) => setForm({ ...form, phone: v, whatsapp: v })}
                  />
                </View>
              </View>

              <Text style={styles.fieldLabel}>Specializations (comma separated)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Artificial Intelligence, Decision Frameworks, Operations"
                placeholderTextColor={COLORS.textMuted}
                value={form.specializationsText}
                onChangeText={(v) => setForm({ ...form, specializationsText: v })}
              />

              <Text style={styles.fieldLabel}>Subjects Taught (comma separated)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Data Structures, Strategic Analysis, Economics"
                placeholderTextColor={COLORS.textMuted}
                value={form.subjectsText}
                onChangeText={(v) => setForm({ ...form, subjectsText: v })}
              />

              <Text style={styles.fieldLabel}>Languages (comma separated)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. English, Hindi, Tamil"
                placeholderTextColor={COLORS.textMuted}
                value={form.languagesText}
                onChangeText={(v) => setForm({ ...form, languagesText: v })}
              />

              <Text style={styles.fieldLabel}>Professional Bio</Text>
              <TextInput
                style={[styles.input, { height: 70 }]}
                placeholder="Brief summary of research, academic background, and publications..."
                placeholderTextColor={COLORS.textMuted}
                multiline
                value={form.bio}
                onChangeText={(v) => setForm({ ...form, bio: v })}
              />

              <TouchableOpacity
                style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 }}
                onPress={() => setForm({ ...form, is_active: !form.is_active })}
              >
                <Ionicons
                  name={form.is_active ? 'checkbox' : 'square-outline'}
                  size={22}
                  color={form.is_active ? COLORS.primary : COLORS.textMuted}
                />
                <Text style={{ fontSize: 14, color: COLORS.textPrimary, fontWeight: '600' }}>
                  Active & Available for Decision Sharing & Collaboration
                </Text>
              </TouchableOpacity>
            </ScrollView>

            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => setShowForm(false)}
                disabled={saving}
              >
                <Text style={styles.cancelBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.saveBtn}
                onPress={handleSave}
                disabled={saving}
              >
                {saving ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.saveBtnText}>
                    {editing ? 'Save Changes' : 'Create Profile'}
                  </Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Bulk Upload Modal */}
      <Modal visible={showBulk} animationType="fade" transparent>
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxHeight: '85%' }]}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Bulk Upload Facilitators (JSON)</Text>
              <TouchableOpacity onPress={() => { setShowBulk(false); setBulkResult(null); }}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </TouchableOpacity>
            </View>

            <ScrollView contentContainerStyle={styles.formBody}>
              <Text style={{ fontSize: 13, color: COLORS.textSecondary, marginBottom: 8 }}>
                Paste a JSON array of facilitator objects. Example:
              </Text>
              <View style={styles.codeBox}>
                <Text style={styles.codeText}>
                  {JSON.stringify(
                    [
                      {
                        name: 'Dr. Ananya Roy',
                        email: 'ananya.roy@univ.edu',
                        department: 'Management & Business Studies',
                        designation: 'Professor',
                        institution: 'IIM Ahmedabad',
                        qualification: 'Ph.D in Strategy',
                        specializations: ['Decision Sciences', 'Organizational Behavior'],
                      },
                    ],
                    null,
                    2
                  )}
                </Text>
              </View>

              <TextInput
                style={[styles.input, { height: 160, fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace', fontSize: 12 }]}
                placeholder="[ { ... }, { ... } ]"
                placeholderTextColor={COLORS.textMuted}
                multiline
                value={bulkText}
                onChangeText={setBulkText}
              />

              {bulkResult && (
                <View style={styles.bulkResultBox}>
                  <Text style={{ fontSize: 14, fontWeight: '700', color: '#10B981' }}>
                    Uploaded {bulkResult.created_count} facilitator profiles successfully!
                  </Text>
                  {bulkResult.error_count > 0 && (
                    <Text style={{ fontSize: 12, color: '#EF4444', marginTop: 4 }}>
                      {bulkResult.error_count} records had errors (duplicates/invalid emails).
                    </Text>
                  )}
                </View>
              )}
            </ScrollView>

            <View style={styles.modalFooter}>
              <TouchableOpacity
                style={styles.cancelBtn}
                onPress={() => { setShowBulk(false); setBulkResult(null); }}
              >
                <Text style={styles.cancelBtnText}>Close</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.saveBtn}
                onPress={runBulk}
                disabled={saving || !bulkText.trim()}
              >
                {saving ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.saveBtnText}>Process Upload</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
    flexWrap: 'wrap',
    gap: 12,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: '800', color: COLORS.textPrimary },
  headerSub: { fontSize: 12.5, color: COLORS.textSecondary, marginTop: 2 },
  primaryBtn: { borderRadius: 10, overflow: 'hidden' },
  btnGrad: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  primaryBtnText: { color: '#fff', fontSize: 13, fontWeight: '700' },
  secondaryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 9,
    borderWidth: 1.2,
    borderColor: COLORS.primary + '40',
    backgroundColor: COLORS.primary + '08',
  },
  secondaryBtnText: { color: COLORS.primary, fontSize: 13, fontWeight: '700' },
  filterSection: { paddingHorizontal: 20, paddingVertical: 12, gap: 10 },
  searchBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  searchInput: { flex: 1, fontSize: 13.5, color: COLORS.textPrimary },
  deptScroll: { gap: 8, paddingVertical: 2 },
  deptPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  deptPillActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  deptPillText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  deptPillTextActive: { color: '#fff', fontWeight: '700' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  loadingText: { marginTop: 12, fontSize: 13, color: COLORS.textSecondary },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary, marginTop: 12 },
  emptySub: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', marginTop: 4, maxWidth: 320 },
  listContent: { paddingHorizontal: 20, paddingBottom: 60, gap: 12 },
  card: {
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    gap: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
  },
  cardHeader: { flexDirection: 'row', gap: 12 },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#7C3AED18',
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontSize: 18, fontWeight: '800', color: '#7C3AED' },
  facultyName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  statusBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  statusText: { fontSize: 10.5, fontWeight: '700' },
  facultyRole: { fontSize: 12.5, fontWeight: '600', color: COLORS.textSecondary, marginTop: 2 },
  facultyEmail: { fontSize: 12, color: COLORS.textMuted, marginTop: 1 },
  cardActions: { flexDirection: 'row', gap: 4 },
  iconBtn: { padding: 6, borderRadius: 6 },
  tagWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  specTag: {
    backgroundColor: '#F3E8FF',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  specTagText: { fontSize: 11, fontWeight: '600', color: '#7C3AED' },
  subjTag: {
    backgroundColor: '#E0F2FE',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  subjTagText: { fontSize: 11, fontWeight: '600', color: '#0284C7' },
  bioText: { fontSize: 12.5, color: COLORS.textSecondary, lineHeight: 18 },
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalCard: {
    width: '100%',
    maxWidth: 680,
    backgroundColor: '#fff',
    borderRadius: 18,
    maxHeight: '90%',
    overflow: 'hidden',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  modalTitle: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary },
  formBody: { padding: 20, gap: 12 },
  fieldRow: { flexDirection: 'row', gap: 12 },
  fieldLabel: { fontSize: 12.5, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 13.5,
    color: COLORS.textPrimary,
    backgroundColor: '#F9FAFB',
  },
  modalFooter: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    backgroundColor: '#F9FAFB',
  },
  cancelBtn: { paddingHorizontal: 16, paddingVertical: 9, borderRadius: 8 },
  cancelBtnText: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  saveBtn: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 18,
    paddingVertical: 9,
    borderRadius: 8,
    minWidth: 110,
    alignItems: 'center',
  },
  saveBtnText: { color: '#fff', fontSize: 13, fontWeight: '700' },
  codeBox: {
    backgroundColor: '#1E293B',
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
  },
  codeText: { color: '#38BDF8', fontSize: 11, fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace' },
  bulkResultBox: {
    backgroundColor: '#F0FDF4',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#BBF7D0',
    marginTop: 8,
  },
});
