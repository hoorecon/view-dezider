/**
 * /admin/payments — Admin Console for Payments, Coupons & Org-Type master.
 *
 * Three sections in one screen:
 *   1. Skip-Payment master toggle (Razorpay bypass for production testing)
 *   2. Coupons (CRUD over coupons collection — implements SP_GetDiscount + new fields)
 *   3. Org-Type master (single source of truth for all org_type pickers)
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  Switch, ActivityIndicator, Modal, Platform, Alert, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

type Coupon = {
  coupon_code: string;
  coupon_desc?: string;
  user_type?: 'User'|'Org'|'Expert'|null;
  discount_type: 'Percentage'|'Value'|'NetValue';
  discount_value: number;
  max_usage_limit?: number|null;
  current_usage_limit?: number;
  max_usage_limit_per_user?: number|null;
  valid_from?: string;
  valid_until?: string;
  is_active: 'Y'|'N';
  applicable_org_types?: string[]|null;
  applicable_flows?: string[]|null;
  created_at?: string;
};
type OrgType = { key:string; label:string; icon?:string; color?:string; description?:string; is_org?:boolean; active?:boolean; sort_order?:number; is_system?:boolean };

const FLOW_OPTS = ['DECISION_FLOW','SUBSCRIPTION','TOPUP','SKU'];

export default function AdminPaymentsScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isWide = width >= 900;

  // ── Skip toggle state ────────────────────────────────────────────────
  const [skip, setSkip] = useState(false);
  const [skipReason, setSkipReason] = useState('');
  const [skipEnabledAt, setSkipEnabledAt] = useState<string|null>(null);
  const [skipLoading, setSkipLoading] = useState(false);

  // ── Coupons state ────────────────────────────────────────────────────
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [couponsLoading, setCouponsLoading] = useState(true);
  const [editingCoupon, setEditingCoupon] = useState<Coupon|null>(null);
  const [couponModalOpen, setCouponModalOpen] = useState(false);

  // ── Org-types state ──────────────────────────────────────────────────
  const [orgTypes, setOrgTypes] = useState<OrgType[]>([]);
  const [orgTypesLoading, setOrgTypesLoading] = useState(true);
  const [orgModalOpen, setOrgModalOpen] = useState(false);
  const [editingOrgType, setEditingOrgType] = useState<OrgType|null>(null);

  // ────────────────────────────────────────────────────────────────────
  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    await Promise.all([loadSkip(), loadCoupons(), loadOrgTypes()]);
  };

  const loadSkip = async () => {
    try {
      const r = await api.get('/admin/payment-settings');
      setSkip(!!r.data.skip_payment_all_flows);
      setSkipReason(r.data.skip_payment_reason || '');
      setSkipEnabledAt(r.data.skip_payment_enabled_at || null);
    } catch (e) { console.error('skip load', e); }
  };

  const toggleSkip = async (v: boolean) => {
    setSkipLoading(true);
    try {
      const r = await api.put('/admin/payment-settings', {
        skip_payment_all_flows: v,
        skip_payment_reason: skipReason,
      });
      setSkip(!!r.data.skip_payment_all_flows);
      setSkipEnabledAt(r.data.skip_payment_enabled_at || null);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to update');
      setSkip(!v); // revert
    } finally { setSkipLoading(false); }
  };

  const saveSkipReason = async () => {
    try {
      await api.put('/admin/payment-settings', { skip_payment_reason: skipReason });
      showAlert('Saved', 'Reason updated');
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  const loadCoupons = async () => {
    setCouponsLoading(true);
    try {
      const r = await api.get('/admin/coupons');
      setCoupons(r.data || []);
    } catch (e) { console.error('coupons load', e); }
    finally { setCouponsLoading(false); }
  };

  const loadOrgTypes = async () => {
    setOrgTypesLoading(true);
    try {
      const r = await api.get('/admin/org-types');
      setOrgTypes(r.data || []);
    } catch (e) { console.error('org types load', e); }
    finally { setOrgTypesLoading(false); }
  };

  const openNewCoupon = () => {
    setEditingCoupon({
      coupon_code: '',
      coupon_desc: '',
      discount_type: 'Percentage',
      discount_value: 10,
      is_active: 'Y',
      max_usage_limit: null,
      max_usage_limit_per_user: null,
      valid_from: new Date().toISOString().slice(0,10),
      valid_until: new Date(Date.now()+90*86400000).toISOString().slice(0,10),
      applicable_org_types: [],
      applicable_flows: [],
    } as Coupon);
    setCouponModalOpen(true);
  };
  const openEditCoupon = (c: Coupon) => { setEditingCoupon({ ...c }); setCouponModalOpen(true); };

  const saveCoupon = async () => {
    if (!editingCoupon) return;
    const payload: any = { ...editingCoupon };
    if (payload.valid_from && payload.valid_from.length <= 10) payload.valid_from = payload.valid_from + 'T00:00:00+00:00';
    if (payload.valid_until && payload.valid_until.length <= 10) payload.valid_until = payload.valid_until + 'T23:59:59+00:00';
    payload.coupon_code = (payload.coupon_code || '').trim().toUpperCase();
    if (!payload.coupon_code) return showAlert('Required', 'Coupon code is required');
    try {
      const existing = coupons.find(c => c.coupon_code === payload.coupon_code);
      if (existing) await api.put(`/admin/coupons/${payload.coupon_code}`, payload);
      else await api.post('/admin/coupons', payload);
      setCouponModalOpen(false);
      loadCoupons();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Save failed');
    }
  };

  const toggleCouponActive = async (c: Coupon) => {
    try {
      await api.put(`/admin/coupons/${c.coupon_code}`, { is_active: c.is_active === 'Y' ? 'N' : 'Y' });
      loadCoupons();
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  const deactivateCoupon = async (c: Coupon) => {
    showAlert('Deactivate coupon?', `${c.coupon_code} — usage history preserved.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Deactivate', style: 'destructive', onPress: async () => {
        try { await api.delete(`/admin/coupons/${c.coupon_code}`); loadCoupons(); }
        catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
      } },
    ]);
  };

  const openNewOrgType = () => {
    setEditingOrgType({ key: '', label: '', icon: 'business', color: '#64748B', is_org: true, active: true, sort_order: 99 });
    setOrgModalOpen(true);
  };
  const openEditOrgType = (o: OrgType) => { setEditingOrgType({ ...o }); setOrgModalOpen(true); };

  const saveOrgType = async () => {
    if (!editingOrgType) return;
    const payload = { ...editingOrgType };
    payload.key = (payload.key || '').trim().toUpperCase().replace(/\s+/g, '_');
    if (!payload.key) return showAlert('Required', 'key is required');
    try {
      const existing = orgTypes.find(o => o.key === payload.key);
      if (existing) await api.put(`/admin/org-types/${payload.key}`, payload);
      else await api.post('/admin/org-types', payload);
      setOrgModalOpen(false);
      loadOrgTypes();
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Save failed'); }
  };

  const deleteOrgType = async (o: OrgType) => {
    if (o.is_system) {
      showAlert('System OrgType', `'${o.label}' is a system row — toggling its 'active' flag instead of deleting.`, [
        { text: 'OK', onPress: async () => { try { await api.delete(`/admin/org-types/${o.key}`); loadOrgTypes(); } catch (e) {} } },
      ]);
      return;
    }
    showAlert('Delete OrgType?', `${o.label}`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/admin/org-types/${o.key}`); loadOrgTypes(); }
        catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
      } },
    ]);
  };

  return (
    <SafeAreaView style={s.root}>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
        {/* Header */}
        <View style={s.headerRow}>
          <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}>
            <Ionicons name="chevron-back" size={22} color="#0F172A" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={s.headerTitle}>Payments &amp; Coupons</Text>
            <Text style={s.headerSub}>Razorpay bypass · Coupon CRUD · Org-Type master</Text>
          </View>
        </View>

        {/* ────────── SECTION 1: SKIP TOGGLE ────────── */}
        <View style={[s.card, skip && { borderColor: '#F59E0B', backgroundColor: '#FFFBEB' }]}>
          <View style={s.cardHead}>
            <View style={[s.iconBox, { backgroundColor: skip ? '#FEF3C7' : '#E0F2FE' }]}>
              <Ionicons name={skip ? 'warning' : 'card'} size={20} color={skip ? '#B45309' : '#0369A1'} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.cardTitle}>Skip Payment for ALL Decision Flows</Text>
              <Text style={s.cardSub}>Bypasses Razorpay for Decision Flows, Subscriptions, Top-ups &amp; SKUs. Use only for production testing while Razorpay credentials are being procured.</Text>
            </View>
            <Switch
              value={skip}
              onValueChange={toggleSkip}
              disabled={skipLoading}
              trackColor={{ false: '#CBD5E1', true: '#F59E0B' }}
              thumbColor="#FFFFFF"
            />
          </View>
          {skip && (
            <View style={s.warnBanner}>
              <Ionicons name="warning-outline" size={14} color="#B45309" />
              <Text style={s.warnText}>
                ⚠ Payment skip is ACTIVE{skipEnabledAt ? ` since ${new Date(skipEnabledAt).toLocaleString()}` : ''}.
                Users will NOT be redirected to Razorpay.
              </Text>
            </View>
          )}
          <View style={{ marginTop: 12 }}>
            <Text style={s.fieldLabel}>Reason (audit-logged)</Text>
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <TextInput
                style={[s.input, { flex: 1 }]}
                value={skipReason}
                onChangeText={setSkipReason}
                placeholder="e.g. Razorpay credentials pending KYC"
                placeholderTextColor="#94A3B8"
              />
              <TouchableOpacity style={s.smallBtn} onPress={saveSkipReason}>
                <Text style={s.smallBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        {/* ────────── SECTION 2: COUPONS ────────── */}
        <View style={s.card}>
          <View style={s.cardHead}>
            <View style={[s.iconBox, { backgroundColor: '#ECFDF5' }]}>
              <Ionicons name="pricetag" size={20} color="#059669" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.cardTitle}>Coupons</Text>
              <Text style={s.cardSub}>{coupons.length} configured · Percentage / Value / NetValue · Org-Type &amp; flow scoped</Text>
            </View>
            <TouchableOpacity style={s.primaryBtn} onPress={openNewCoupon}>
              <Ionicons name="add" size={16} color="#FFF" />
              <Text style={s.primaryBtnText}>New</Text>
            </TouchableOpacity>
          </View>

          {couponsLoading ? (
            <ActivityIndicator style={{ marginTop: 12 }} color="#7C3AED" />
          ) : coupons.length === 0 ? (
            <Text style={s.empty}>No coupons yet. Tap “New” to add one.</Text>
          ) : (
            <View style={{ marginTop: 8 }}>
              {coupons.map(c => (
                <View key={c.coupon_code} style={s.row}>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <Text style={s.code}>{c.coupon_code}</Text>
                      <View style={[s.pill, c.is_active === 'Y' ? s.pillOk : s.pillOff]}>
                        <Text style={[s.pillText, c.is_active === 'Y' ? { color: '#065F46' } : { color: '#7F1D1D' }]}>
                          {c.is_active === 'Y' ? 'Active' : 'Inactive'}
                        </Text>
                      </View>
                      <View style={[s.pill, { backgroundColor: '#EEF2FF' }]}>
                        <Text style={[s.pillText, { color: '#4338CA' }]}>
                          {c.discount_type === 'Percentage' ? `${Math.min(100, Math.max(0, Number(c.discount_value)||0))}%` :
                           c.discount_type === 'Value' ? `−₹${Math.max(0, Number(c.discount_value)||0)}` : `=₹${Math.max(0, Number(c.discount_value)||0)}`}
                        </Text>
                      </View>
                    </View>
                    {c.coupon_desc ? <Text style={s.rowSub} numberOfLines={1}>{c.coupon_desc}</Text> : null}
                    <Text style={s.rowMeta}>
                      Used {c.current_usage_limit||0}{c.max_usage_limit ? `/${c.max_usage_limit}`:''} · Per-user max {c.max_usage_limit_per_user ?? '∞'} · {c.applicable_org_types?.length ? `${c.applicable_org_types.length} OrgTypes` : 'All OrgTypes'} · {c.applicable_flows?.length ? c.applicable_flows.join(',') : 'All flows'}
                    </Text>
                  </View>
                  <View style={{ flexDirection: 'row', gap: 6 }}>
                    <TouchableOpacity onPress={() => toggleCouponActive(c)} style={s.iconBtn}>
                      <Ionicons name={c.is_active === 'Y' ? 'pause' : 'play'} size={16} color="#4338CA" />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => openEditCoupon(c)} style={s.iconBtn}>
                      <Ionicons name="create-outline" size={16} color="#4338CA" />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => deactivateCoupon(c)} style={s.iconBtn}>
                      <Ionicons name="trash-outline" size={16} color="#DC2626" />
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>

        {/* ────────── SECTION 3: ORG TYPES MASTER ────────── */}
        <View style={s.card}>
          <View style={s.cardHead}>
            <View style={[s.iconBox, { backgroundColor: '#FEF3C7' }]}>
              <Ionicons name="layers" size={20} color="#D97706" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={s.cardTitle}>Org-Type Master</Text>
              <Text style={s.cardSub}>Single source of truth — used by Decision Flow, Coupons, Contacts &amp; Reports.</Text>
            </View>
            <TouchableOpacity style={s.primaryBtn} onPress={openNewOrgType}>
              <Ionicons name="add" size={16} color="#FFF" />
              <Text style={s.primaryBtnText}>New</Text>
            </TouchableOpacity>
          </View>

          {orgTypesLoading ? (
            <ActivityIndicator style={{ marginTop: 12 }} color="#7C3AED" />
          ) : (
            <View style={{ marginTop: 8 }}>
              {orgTypes.map(o => (
                <View key={o.key} style={s.row}>
                  <View style={[s.dot, { backgroundColor: o.color || '#64748B' }]} />
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <Text style={s.code}>{o.label}</Text>
                      {o.is_system && <View style={[s.pill, { backgroundColor: '#F1F5F9' }]}><Text style={[s.pillText, { color: '#475569' }]}>system</Text></View>}
                      {!o.active && <View style={[s.pill, s.pillOff]}><Text style={[s.pillText, { color: '#7F1D1D' }]}>disabled</Text></View>}
                    </View>
                    <Text style={s.rowMeta}>{o.key} · {o.is_org ? 'Organisation' : 'Individual'}</Text>
                  </View>
                  <View style={{ flexDirection: 'row', gap: 6 }}>
                    <TouchableOpacity onPress={() => openEditOrgType(o)} style={s.iconBtn}>
                      <Ionicons name="create-outline" size={16} color="#4338CA" />
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => deleteOrgType(o)} style={s.iconBtn}>
                      <Ionicons name="trash-outline" size={16} color="#DC2626" />
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>
      </ScrollView>

      {/* ────────── COUPON EDIT MODAL ────────── */}
      <Modal visible={couponModalOpen} transparent animationType="slide" onRequestClose={() => setCouponModalOpen(false)}>
        <View style={s.modalOverlay}>
          <View style={[s.modalBox, isWide && { maxWidth: 640 }]}>
            <View style={s.modalHead}>
              <Text style={s.modalTitle}>{editingCoupon && coupons.find(c => c.coupon_code === editingCoupon.coupon_code) ? 'Edit Coupon' : 'New Coupon'}</Text>
              <TouchableOpacity onPress={() => setCouponModalOpen(false)}>
                <Ionicons name="close" size={22} color="#475569" />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 520 }}>
              {editingCoupon && (
                <>
                  <Text style={s.fieldLabel}>Code *</Text>
                  <TextInput style={s.input} value={editingCoupon.coupon_code} onChangeText={t => setEditingCoupon({ ...editingCoupon, coupon_code: t.toUpperCase() })} placeholder="LAUNCH50" autoCapitalize="characters" />

                  <Text style={s.fieldLabel}>Description</Text>
                  <TextInput style={s.input} value={editingCoupon.coupon_desc || ''} onChangeText={t => setEditingCoupon({ ...editingCoupon, coupon_desc: t })} placeholder="50% off launch promo" />

                  <Text style={s.fieldLabel}>Discount Type *</Text>
                  <View style={s.chipRow}>
                    {(['Percentage','Value','NetValue'] as const).map(t => (
                      <TouchableOpacity key={t} style={[s.chip, editingCoupon.discount_type === t && s.chipActive]} onPress={() => setEditingCoupon({ ...editingCoupon, discount_type: t })}>
                        <Text style={[s.chipText, editingCoupon.discount_type === t && { color: '#FFF' }]}>{t}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>

                  <Text style={s.fieldLabel}>Discount Value *</Text>
                  <TextInput style={s.input} value={String(editingCoupon.discount_value ?? '')} onChangeText={t => setEditingCoupon({ ...editingCoupon, discount_value: Number(t)||0 })} keyboardType="numeric" placeholder={editingCoupon.discount_type === 'Percentage' ? '0 – 100 (%)' : 'amount in ₹'} />

                  <View style={{ flexDirection: 'row', gap: 12 }}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.fieldLabel}>Valid From</Text>
                      <TextInput style={s.input} value={(editingCoupon.valid_from || '').slice(0,10)} onChangeText={t => setEditingCoupon({ ...editingCoupon, valid_from: t })} placeholder="YYYY-MM-DD" />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.fieldLabel}>Valid Until</Text>
                      <TextInput style={s.input} value={(editingCoupon.valid_until || '').slice(0,10)} onChangeText={t => setEditingCoupon({ ...editingCoupon, valid_until: t })} placeholder="YYYY-MM-DD" />
                    </View>
                  </View>

                  <View style={{ flexDirection: 'row', gap: 12 }}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.fieldLabel}>Global Max Usage</Text>
                      <TextInput style={s.input} value={editingCoupon.max_usage_limit?.toString() || ''} onChangeText={t => setEditingCoupon({ ...editingCoupon, max_usage_limit: t ? Number(t) : null })} keyboardType="numeric" placeholder="∞ (leave blank)" />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={s.fieldLabel}>Per-User Max</Text>
                      <TextInput style={s.input} value={editingCoupon.max_usage_limit_per_user?.toString() || ''} onChangeText={t => setEditingCoupon({ ...editingCoupon, max_usage_limit_per_user: t ? Number(t) : null })} keyboardType="numeric" placeholder="∞" />
                    </View>
                  </View>

                  <Text style={s.fieldLabel}>Applicable Org Types <Text style={s.hint}>(empty = ALL)</Text></Text>
                  <View style={s.chipRow}>
                    {orgTypes.filter(o => o.active).map(o => {
                      const active = (editingCoupon.applicable_org_types || []).includes(o.key);
                      return (
                        <TouchableOpacity key={o.key} style={[s.chip, active && s.chipActive]} onPress={() => {
                          const cur = new Set(editingCoupon.applicable_org_types || []);
                          if (active) cur.delete(o.key); else cur.add(o.key);
                          setEditingCoupon({ ...editingCoupon, applicable_org_types: Array.from(cur) });
                        }}>
                          <Text style={[s.chipText, active && { color: '#FFF' }]}>{o.label}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>

                  <Text style={s.fieldLabel}>Applicable Flows <Text style={s.hint}>(empty = ALL)</Text></Text>
                  <View style={s.chipRow}>
                    {FLOW_OPTS.map(f => {
                      const active = (editingCoupon.applicable_flows || []).includes(f);
                      return (
                        <TouchableOpacity key={f} style={[s.chip, active && s.chipActive]} onPress={() => {
                          const cur = new Set(editingCoupon.applicable_flows || []);
                          if (active) cur.delete(f); else cur.add(f);
                          setEditingCoupon({ ...editingCoupon, applicable_flows: Array.from(cur) });
                        }}>
                          <Text style={[s.chipText, active && { color: '#FFF' }]}>{f}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>

                  <View style={s.toggleRow}>
                    <Text style={s.fieldLabel}>Active</Text>
                    <Switch
                      value={editingCoupon.is_active === 'Y'}
                      onValueChange={v => setEditingCoupon({ ...editingCoupon, is_active: v ? 'Y' : 'N' })}
                      trackColor={{ false: '#CBD5E1', true: '#10B981' }}
                    />
                  </View>
                </>
              )}
            </ScrollView>
            <View style={s.modalActions}>
              <TouchableOpacity style={s.secondaryBtn} onPress={() => setCouponModalOpen(false)}>
                <Text style={s.secondaryBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.primaryBtn} onPress={saveCoupon}>
                <Ionicons name="checkmark" size={16} color="#FFF" />
                <Text style={s.primaryBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ────────── ORG-TYPE EDIT MODAL ────────── */}
      <Modal visible={orgModalOpen} transparent animationType="slide" onRequestClose={() => setOrgModalOpen(false)}>
        <View style={s.modalOverlay}>
          <View style={[s.modalBox, isWide && { maxWidth: 480 }]}>
            <View style={s.modalHead}>
              <Text style={s.modalTitle}>{editingOrgType && orgTypes.find(o => o.key === editingOrgType.key) ? 'Edit Org Type' : 'New Org Type'}</Text>
              <TouchableOpacity onPress={() => setOrgModalOpen(false)}>
                <Ionicons name="close" size={22} color="#475569" />
              </TouchableOpacity>
            </View>
            {editingOrgType && (
              <View>
                <Text style={s.fieldLabel}>Key * <Text style={s.hint}>(UPPER_CASE)</Text></Text>
                <TextInput style={s.input} value={editingOrgType.key} editable={!editingOrgType.is_system} onChangeText={t => setEditingOrgType({ ...editingOrgType, key: t.toUpperCase() })} placeholder="STARTUP" autoCapitalize="characters" />

                <Text style={s.fieldLabel}>Label *</Text>
                <TextInput style={s.input} value={editingOrgType.label} onChangeText={t => setEditingOrgType({ ...editingOrgType, label: t })} placeholder="Startup" />

                <Text style={s.fieldLabel}>Description (shown under the Decision-Flow card)</Text>
                <TextInput style={s.input} value={editingOrgType.description || ''} onChangeText={t => setEditingOrgType({ ...editingOrgType, description: t })} placeholder="e.g. Family / household" />

                <View style={{ flexDirection: 'row', gap: 12 }}>
                  <View style={{ flex: 1 }}>
                    <Text style={s.fieldLabel}>Icon (Ionicon)</Text>
                    <TextInput style={s.input} value={editingOrgType.icon || ''} onChangeText={t => setEditingOrgType({ ...editingOrgType, icon: t })} placeholder="business" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={s.fieldLabel}>Color (hex)</Text>
                    <TextInput style={s.input} value={editingOrgType.color || ''} onChangeText={t => setEditingOrgType({ ...editingOrgType, color: t })} placeholder="#64748B" />
                  </View>
                </View>

                <View style={s.toggleRow}>
                  <Text style={s.fieldLabel}>Is an Organisation (vs Individual)</Text>
                  <Switch value={!!editingOrgType.is_org} onValueChange={v => setEditingOrgType({ ...editingOrgType, is_org: v })} trackColor={{ false: '#CBD5E1', true: '#0EA5E9' }} />
                </View>
                <View style={s.toggleRow}>
                  <Text style={s.fieldLabel}>Active</Text>
                  <Switch value={!!editingOrgType.active} onValueChange={v => setEditingOrgType({ ...editingOrgType, active: v })} trackColor={{ false: '#CBD5E1', true: '#10B981' }} />
                </View>

                <Text style={s.fieldLabel}>Sort Order</Text>
                <TextInput style={s.input} value={String(editingOrgType.sort_order ?? '')} onChangeText={t => setEditingOrgType({ ...editingOrgType, sort_order: Number(t) || 99 })} keyboardType="numeric" />
              </View>
            )}
            <View style={s.modalActions}>
              <TouchableOpacity style={s.secondaryBtn} onPress={() => setOrgModalOpen(false)}>
                <Text style={s.secondaryBtnText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={s.primaryBtn} onPress={saveOrgType}>
                <Ionicons name="checkmark" size={16} color="#FFF" />
                <Text style={s.primaryBtnText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 16 },
  backBtn: { padding: 6 },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#0F172A' },
  headerSub: { fontSize: 12, color: '#64748B', marginTop: 2 },

  card: { backgroundColor: '#FFFFFF', borderRadius: 14, padding: 14, marginBottom: 14, borderWidth: 1, borderColor: '#E2E8F0' },
  cardHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  cardTitle: { fontSize: 15, fontWeight: '700', color: '#0F172A' },
  cardSub: { fontSize: 12, color: '#64748B', marginTop: 2, lineHeight: 16 },
  iconBox: { width: 40, height: 40, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },

  warnBanner: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 8, marginTop: 10, borderRadius: 8, backgroundColor: '#FEF3C7', borderWidth: 1, borderColor: '#FDE68A' },
  warnText: { flex: 1, fontSize: 11, color: '#B45309', lineHeight: 16 },

  fieldLabel: { fontSize: 12, fontWeight: '600', color: '#0F172A', marginTop: 10, marginBottom: 4 },
  hint: { fontSize: 11, color: '#64748B', fontWeight: '400' },
  input: { borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: '#0F172A', backgroundColor: '#FFFFFF' },

  smallBtn: { backgroundColor: '#0F172A', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, justifyContent: 'center' },
  smallBtnText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },

  primaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#0D9488', paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8 },
  primaryBtnText: { color: '#FFFFFF', fontSize: 12, fontWeight: '700' },
  secondaryBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#F1F5F9', paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8 },
  secondaryBtnText: { color: '#475569', fontSize: 12, fontWeight: '700' },

  empty: { fontSize: 12, color: '#64748B', fontStyle: 'italic', paddingVertical: 12 },

  row: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  dot: { width: 10, height: 10, borderRadius: 5 },
  code: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  rowSub: { fontSize: 11, color: '#64748B', marginTop: 2 },
  rowMeta: { fontSize: 10, color: '#64748B', marginTop: 3 },

  pill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  pillText: { fontSize: 10, fontWeight: '700' },
  pillOk: { backgroundColor: '#D1FAE5' },
  pillOff: { backgroundColor: '#FEE2E2' },

  iconBtn: { width: 30, height: 30, borderRadius: 6, justifyContent: 'center', alignItems: 'center', backgroundColor: '#F1F5F9' },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#FFFFFF' },
  chipActive: { backgroundColor: '#0D9488', borderColor: '#0D9488' },
  chipText: { fontSize: 11, color: '#0F172A', fontWeight: '600' },

  toggleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 },

  modalOverlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.5)', justifyContent: 'flex-end' },
  modalBox: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 18, maxHeight: '92%', width: '100%', alignSelf: 'center' },
  modalHead: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  modalTitle: { flex: 1, fontSize: 16, fontWeight: '700', color: '#0F172A' },
  modalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 14, borderTopWidth: 1, borderTopColor: '#F1F5F9', paddingTop: 12 },
});
