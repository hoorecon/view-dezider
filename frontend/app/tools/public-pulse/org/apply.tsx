import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system';
import { COLORS } from '../../../../src/constants/colors';
import api from '../../../../src/utils/api';
import { showAlert } from '../../../../src/utils/alert';
import { safeBack } from '../../../../src/utils/navigation';

type OrgType = { code: string; label: string; icon: string };

const DEFAULT_MAX_MB = 5;

type PickedDoc = { name: string; size: number; mime: string; b64: string } | null;
type Limit = { max_size_mb: number; allowed_mime_types: string[]; label?: string };

export default function OrgApplyScreen() {
  const router = useRouter();
  const [types, setTypes] = useState<OrgType[]>([]);
  const [orgType, setOrgType] = useState('ngo');
  const [displayName, setDisplayName] = useState('');
  const [legalName, setLegalName] = useState('');
  const [about, setAbout] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [website, setWebsite] = useState('');
  const [state, setState] = useState('');
  const [district, setDistrict] = useState('');
  const [categoriesInput, setCategoriesInput] = useState('');
  const [eligible, setEligible] = useState<boolean | null>(null);
  const [blockers, setBlockers] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  // Uploaded docs
  const [verificationDoc, setVerificationDoc] = useState<PickedDoc>(null);
  const [authorizedId, setAuthorizedId] = useState<PickedDoc>(null);
  const [brandLogo, setBrandLogo] = useState<PickedDoc>(null);

  // Upload limits from server (admin-tunable)
  const [limits, setLimits] = useState<Record<string, Limit>>({});

  useEffect(() => {
    api.get('/public-pulse/orgs/types').then((r) => setTypes(r.data.types || [])).catch(() => {});
    api.get('/public-pulse/upload-limits')
      .then((r) => setLimits(r.data.limits || {}))
      .catch(() => {});
  }, []);

  useEffect(() => {
    api.get(`/public-pulse/orgs/eligibility/${orgType}`).then((r) => {
      setEligible(r.data.eligible);
      setBlockers(r.data.blockers || []);
    }).catch(() => setEligible(null));
  }, [orgType]);

  const pickFile = async (setter: (d: PickedDoc) => void, category: string) => {
    const limit = limits[category] || { max_size_mb: DEFAULT_MAX_MB, allowed_mime_types: ['*/*'] };
    const maxBytes = limit.max_size_mb * 1024 * 1024;
    const accept = limit.allowed_mime_types.length && !limit.allowed_mime_types.includes('*/*')
      ? limit.allowed_mime_types : '*/*';
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: accept as any,
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (res.canceled) return;
      const asset = res.assets[0];
      if (!asset) return;
      if (asset.size && asset.size > maxBytes) {
        showAlert(
          'File too large',
          `Maximum allowed size for ${limit.label || category} is ${limit.max_size_mb} MB. Your file is ${(asset.size / 1024 / 1024).toFixed(1)} MB.`,
        );
        return;
      }
      // MIME validation client-side (server will also validate)
      const mime = asset.mimeType || 'application/octet-stream';
      if (limit.allowed_mime_types.length && !limit.allowed_mime_types.includes('*/*')
          && !limit.allowed_mime_types.includes(mime)) {
        showAlert(
          'File type not allowed',
          `Allowed types: ${limit.allowed_mime_types.join(', ')}. Your file is ${mime}.`,
        );
        return;
      }

      let b64: string;
      if (Platform.OS === 'web') {
        const response = await fetch(asset.uri);
        const blob = await response.blob();
        b64 = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            const result = reader.result as string;
            resolve(result.split(',')[1] || result);
          };
          reader.onerror = reject;
          reader.readAsDataURL(blob);
        });
      } else {
        b64 = await FileSystem.readAsStringAsync(asset.uri, { encoding: FileSystem.EncodingType.Base64 });
      }
      setter({ name: asset.name, size: asset.size || 0, mime, b64 });
    } catch (e: any) {
      showAlert('Pick error', e?.message || 'Could not pick file');
    }
  };

  const submit = async () => {
    if (!displayName.trim() || !email.trim()) {
      showAlert('Required', 'Display name and email are required');
      return;
    }
    setSubmitting(true);
    try {
      const categories = categoriesInput.split(',').map((c) => c.trim()).filter(Boolean);
      const body: any = {
        org_type: orgType,
        display_name: displayName,
        legal_name: legalName || undefined,
        about: about || undefined,
        website: website || undefined,
        email,
        phone: phone || undefined,
        state: state || undefined,
        district: district || undefined,
        categories,
      };
      if (verificationDoc) {
        body.verification_doc_b64 = verificationDoc.b64;
        body.verification_doc_name = verificationDoc.name;
      }
      if (authorizedId) {
        body.authorized_id_b64 = authorizedId.b64;
        body.authorized_id_name = authorizedId.name;
      }
      if (brandLogo) {
        body.brand_logo_b64 = brandLogo.b64;
      }
      await api.post('/public-pulse/orgs/apply', body);
      showAlert('Submitted', 'Your application is in the admin queue. You will be notified when reviewed.');
      router.replace('/tools/public-pulse/org' as any);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (typeof detail === 'object' && detail?.blockers) {
        showAlert('Not eligible', detail.blockers.join('\n'));
      } else {
        showAlert('Error', typeof detail === 'string' ? detail : 'Failed to submit');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const renderUploadRow = (label: string, doc: PickedDoc, setter: (d: PickedDoc) => void, category: string, isImage = false) => {
    const limit = limits[category];
    const sizeStr = limit ? `max ${limit.max_size_mb} MB` : `max ${DEFAULT_MAX_MB} MB`;
    const typeStr = limit?.allowed_mime_types?.length && !limit.allowed_mime_types.includes('*/*')
      ? limit.allowed_mime_types.map((t) => t.split('/')[1]).join(' / ')
      : 'PDF / image';
    return (
      <View style={styles.uploadBlock}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.hint}>{typeStr} · {sizeStr}</Text>
        {doc ? (
          <View style={styles.docCard}>
            <Ionicons name={isImage ? 'image' : 'document'} size={22} color={COLORS.primary} />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={styles.docName} numberOfLines={1}>{doc.name}</Text>
              <Text style={styles.docSize}>{(doc.size / 1024).toFixed(0)} KB · {doc.mime}</Text>
            </View>
            <TouchableOpacity onPress={() => setter(null)} style={styles.removeBtn}>
              <Ionicons name="close-circle" size={22} color="#EF4444" />
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity style={styles.uploadBtn} onPress={() => pickFile(setter, category)}>
            <Ionicons name="cloud-upload" size={20} color={COLORS.primary} />
            <Text style={styles.uploadBtnTxt}>Upload file</Text>
          </TouchableOpacity>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => safeBack(router)}>
            <Ionicons name="chevron-back" size={28} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Apply to Register Org</Text>
          <View style={{ width: 28 }} />
        </View>

        <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
          <Text style={styles.label}>Organization type</Text>
          <View style={styles.typeGrid}>
            {types.map((t) => {
              const sel = orgType === t.code;
              return (
                <TouchableOpacity
                  key={t.code}
                  style={[styles.typeBtn, sel && styles.typeBtnSel]}
                  onPress={() => setOrgType(t.code)}
                >
                  <Ionicons name={t.icon as any} size={20} color={sel ? '#FFF' : COLORS.primary} />
                  <Text style={[styles.typeTxt, sel && { color: '#FFF' }]}>{t.label}</Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {eligible === false && blockers.length > 0 && (
            <View style={styles.blockerBanner}>
              <Ionicons name="warning" size={20} color="#DC2626" />
              <View style={{ flex: 1, marginLeft: 8 }}>
                <Text style={styles.blockerTitle}>Not eligible for this org type</Text>
                {blockers.map((b, i) => (
                  <Text key={i} style={styles.blockerItem}>• {b}</Text>
                ))}
              </View>
            </View>
          )}

          <Text style={styles.label}>Display name *</Text>
          <TextInput style={styles.input} value={displayName} onChangeText={setDisplayName} placeholder="E.g., Coimbatore Skills Foundation" placeholderTextColor="#9CA3AF" />

          <Text style={styles.label}>Legal name</Text>
          <TextInput style={styles.input} value={legalName} onChangeText={setLegalName} placeholder="Registered legal name (optional)" placeholderTextColor="#9CA3AF" />

          <Text style={styles.label}>Short pitch / what you do</Text>
          <TextInput style={[styles.input, { minHeight: 80, textAlignVertical: 'top' }]} value={about} onChangeText={setAbout} placeholder="2-3 sentences on your mission" placeholderTextColor="#9CA3AF" multiline />

          <Text style={styles.label}>Official email *</Text>
          <TextInput style={styles.input} value={email} onChangeText={setEmail} placeholder="info@yourorg.org" placeholderTextColor="#9CA3AF" keyboardType="email-address" autoCapitalize="none" />

          <Text style={styles.label}>Phone</Text>
          <TextInput style={styles.input} value={phone} onChangeText={setPhone} placeholder="+91 ..." placeholderTextColor="#9CA3AF" keyboardType="phone-pad" />

          <Text style={styles.label}>Website</Text>
          <TextInput style={styles.input} value={website} onChangeText={setWebsite} placeholder="https://..." placeholderTextColor="#9CA3AF" autoCapitalize="none" />

          <View style={styles.row}>
            <View style={{ flex: 1, marginRight: 8 }}>
              <Text style={styles.label}>State</Text>
              <TextInput style={styles.input} value={state} onChangeText={setState} placeholder="Tamil Nadu" placeholderTextColor="#9CA3AF" />
            </View>
            <View style={{ flex: 1, marginLeft: 8 }}>
              <Text style={styles.label}>District</Text>
              <TextInput style={styles.input} value={district} onChangeText={setDistrict} placeholder="Coimbatore" placeholderTextColor="#9CA3AF" />
            </View>
          </View>

          <Text style={styles.label}>Categories (comma-separated)</Text>
          <TextInput
            style={styles.input}
            value={categoriesInput}
            onChangeText={setCategoriesInput}
            placeholder="education, skills, employment"
            placeholderTextColor="#9CA3AF"
          />
          <Text style={styles.hint}>Used for auto-routing feedback + filtering on org dashboard</Text>

          {/* Document uploads */}
          <View style={styles.docsSection}>
            <Text style={styles.sectionHeading}>Verification Documents</Text>
            <Text style={styles.sectionSub}>Helps admins verify your org faster. All files are encrypted at rest.</Text>
            {renderUploadRow(
              'Registration certificate',
              verificationDoc,
              setVerificationDoc,
              'pp_org_verification_doc',
            )}
            {renderUploadRow(
              "Your photo ID (as authorized applicant)",
              authorizedId,
              setAuthorizedId,
              'pp_org_authorized_id',
            )}
            {renderUploadRow(
              'Brand logo (optional)',
              brandLogo,
              setBrandLogo,
              'pp_org_brand_logo',
              true,
            )}
          </View>

          <View style={styles.noticeCard}>
            <Ionicons name="information-circle" size={18} color="#3B82F6" />
            <Text style={styles.noticeTxt}>
              An admin will review your application (typically within 2-3 business days). You'll be notified by in-app notification.
            </Text>
          </View>

          <TouchableOpacity
            style={[styles.submitBtn, (!eligible || submitting) && { opacity: 0.5 }]}
            onPress={submit}
            disabled={!eligible || submitting}
          >
            {submitting ? <ActivityIndicator color="#FFF" /> : <Text style={styles.submitTxt}>Submit Application</Text>}
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  label: { fontSize: 13, fontWeight: '600', color: COLORS.text, marginTop: 16, marginBottom: 8 },
  input: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 10, padding: 12, fontSize: 14, color: COLORS.text },
  hint: { fontSize: 11, color: '#6B7280', marginTop: 4 },
  typeGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  typeBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 16, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#D1D5DB' },
  typeBtnSel: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  typeTxt: { fontSize: 12, color: COLORS.text, fontWeight: '600' },
  blockerBanner: { flexDirection: 'row', alignItems: 'flex-start', backgroundColor: '#FEE2E2', padding: 14, borderRadius: 12, marginTop: 16, borderWidth: 1, borderColor: '#FCA5A5' },
  blockerTitle: { fontSize: 13, fontWeight: '700', color: '#991B1B' },
  blockerItem: { fontSize: 12, color: '#991B1B', marginTop: 4 },
  noticeCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#EFF6FF', padding: 12, borderRadius: 10, marginTop: 16, gap: 10, borderWidth: 1, borderColor: '#BFDBFE' },
  noticeTxt: { flex: 1, fontSize: 12, color: '#1E40AF', lineHeight: 16 },
  row: { flexDirection: 'row' },
  submitBtn: { backgroundColor: COLORS.primary, padding: 16, borderRadius: 12, alignItems: 'center', marginTop: 20 },
  submitTxt: { color: '#FFF', fontSize: 15, fontWeight: '700' },

  docsSection: { marginTop: 24, backgroundColor: '#FAFAFA', padding: 16, borderRadius: 14, borderWidth: 1, borderColor: '#E5E7EB' },
  sectionHeading: { fontSize: 14, fontWeight: '700', color: COLORS.text },
  sectionSub: { fontSize: 12, color: '#6B7280', marginTop: 4 },
  uploadBlock: { marginTop: 14 },
  uploadBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 14, borderWidth: 1, borderColor: '#C7D2FE', borderStyle: 'dashed', borderRadius: 10, backgroundColor: '#FFF', marginTop: 4 },
  uploadBtnTxt: { color: COLORS.primary, fontSize: 13, fontWeight: '600' },
  docCard: { flexDirection: 'row', alignItems: 'center', padding: 12, backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E5E7EB', marginTop: 4 },
  docName: { fontSize: 13, fontWeight: '600', color: COLORS.text },
  docSize: { fontSize: 11, color: '#6B7280', marginTop: 2 },
  removeBtn: { padding: 4 },
});
