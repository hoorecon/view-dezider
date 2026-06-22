import React, { useState, useEffect, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack } from '../../src/utils/navigation';

const ORG_ROLES = [
  { key: 'org_super_admin', label: 'Org Super Admin', level: 3, color: '#EF4444', icon: 'shield' },
  { key: 'org_co_admin', label: 'Org Co-Admin', level: 2, color: '#F59E0B', icon: 'shield-half' },
  { key: 'org_admin', label: 'Org Admin', level: 1, color: '#3B82F6', icon: 'person-circle' },
  { key: 'org_member', label: 'Org Member', level: 0, color: '#6B7280', icon: 'person' },
];

function getOrgRoleMeta(role: string) {
  return ORG_ROLES.find(r => r.key === role) || ORG_ROLES[3]; // default to org_member
}

function getOrgRoleLevel(role: string) {
  const meta = ORG_ROLES.find(r => r.key === role);
  return meta ? meta.level : 0;
}

export default function OrgMembersScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [members, setMembers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [myOrgRole, setMyOrgRole] = useState('org_member');
  const [orgId, setOrgId] = useState<string | null>(null);
  const [selectedMember, setSelectedMember] = useState<any>(null);

  useEffect(() => {
    fetchMyInfo();
  }, []);

  const fetchMyInfo = async () => {
    try {
      const meRes = await api.get('/auth/me');
      const me = meRes.data;
      setMyOrgRole(me.org_role || 'org_member');
      setOrgId(me.org_id || null);
      if (me.org_id) {
        await fetchMembers(me.org_id);
      } else {
        setLoading(false);
      }
    } catch (e) {
      console.error('Error:', e);
      setLoading(false);
    }
  };

  const fetchMembers = async (oid: string) => {
    try {
      const res = await api.get(`/organizations/${oid}/members`);
      setMembers(res.data || []);
    } catch (e) {
      console.error('Error fetching members:', e);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    if (orgId) await fetchMembers(orgId);
    setRefreshing(false);
  };

  const handleChangeRole = (member: any) => {
    const myLevel = getOrgRoleLevel(myOrgRole);
    const memberLevel = getOrgRoleLevel(member.org_role || 'org_member');

    // Can't modify self or someone at equal/higher level
    if (member.user_id === user?.user_id) {
      showAlert('Info', 'Cannot change your own role');
      return;
    }
    if (memberLevel >= myLevel) {
      showAlert('Info', 'Cannot modify a user with equal or higher org role');
      return;
    }

    // Show roles they can be assigned to (below promoter's level)
    const assignableRoles = ORG_ROLES.filter(r => r.level < myLevel && r.level !== memberLevel);

    if (assignableRoles.length === 0) {
      showAlert('Info', 'No roles available to assign');
      return;
    }

    const buttons = assignableRoles.map(r => ({
      text: r.label,
      onPress: () => updateMemberRole(member.user_id, r.key),
    }));
    buttons.push({ text: 'Cancel', onPress: () => {}, style: 'cancel' } as any);

    showAlert(
      `Change Role: ${member.name || member.email}`,
      `Current: ${getOrgRoleMeta(member.org_role || 'org_member').label}`,
      buttons
    );
  };

  const updateMemberRole = async (targetUserId: string, newRole: string) => {
    try {
      await api.put(`/organizations/${orgId}/members/${targetUserId}/role`, {
        org_role: newRole,
      });
      showAlert('Success', `Role updated to ${getOrgRoleMeta(newRole).label}`);
      if (orgId) await fetchMembers(orgId);
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to update role');
    }
  };

  const handleRemoveMember = (member: any) => {
    const myLevel = getOrgRoleLevel(myOrgRole);
    const memberLevel = getOrgRoleLevel(member.org_role || 'org_member');

    if (member.user_id === user?.user_id) {
      showAlert('Info', 'Cannot remove yourself');
      return;
    }
    if (memberLevel >= myLevel) {
      showAlert('Info', 'Cannot remove a user with equal or higher org role');
      return;
    }

    showAlert(
      'Remove Member',
      `Remove ${member.name || member.email} from the organization?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.delete(`/organizations/${orgId}/members/${member.user_id}`);
              showAlert('Removed', 'Member removed from organization');
              if (orgId) await fetchMembers(orgId);
            } catch (e: any) {
              showAlert('Error', e.response?.data?.detail || 'Failed to remove member');
            }
          },
        },
      ]
    );
  };

  const myLevel = getOrgRoleLevel(myOrgRole);

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  if (!orgId) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <LinearGradient colors={GRADIENTS.header} style={styles.header}>
          <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Org Members</Text>
        </LinearGradient>
        <View style={styles.emptyState}>
          <Ionicons name="business-outline" size={56} color={COLORS.textMuted} />
          <Text style={styles.emptyTitle}>No Organization</Text>
          <Text style={styles.emptySubtitle}>You're not part of an organization yet. Create or join one from your profile.</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={GRADIENTS.header} style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>Organization Members</Text>
          <Text style={styles.headerSub}>
            Your role: {getOrgRoleMeta(myOrgRole).label} | {members.length} members
          </Text>
        </View>
      </LinearGradient>

      {/* Role Legend */}
      <View style={styles.legendBar}>
        {ORG_ROLES.map(r => (
          <View key={r.key} style={styles.legendItem}>
            <View style={[styles.legendDot, { backgroundColor: r.color }]} />
            <Text style={styles.legendText}>{r.label.replace('Org ', '')}</Text>
          </View>
        ))}
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {members.map((member) => {
          const roleMeta = getOrgRoleMeta(member.org_role || 'org_member');
          const isMe = member.user_id === user?.user_id;
          const canManage = myLevel > 0 && !isMe && getOrgRoleLevel(member.org_role || 'org_member') < myLevel;

          return (
            <View key={member.user_id} style={[styles.memberCard, isMe && styles.memberCardMe]}>
              <View style={styles.memberMain}>
                <View style={[styles.avatar, { backgroundColor: roleMeta.color + '20' }]}>
                  <Ionicons name={roleMeta.icon as any} size={22} color={roleMeta.color} />
                </View>
                <View style={styles.memberInfo}>
                  <View style={styles.nameRow}>
                    <Text style={styles.memberName} numberOfLines={1}>
                      {member.name || 'Unnamed'}
                      {isMe ? ' (You)' : ''}
                    </Text>
                  </View>
                  <Text style={styles.memberEmail} numberOfLines={1}>{member.email}</Text>
                  <View style={[styles.roleBadge, { backgroundColor: roleMeta.color + '15', borderColor: roleMeta.color }]}>
                    <Text style={[styles.roleBadgeText, { color: roleMeta.color }]}>{roleMeta.label}</Text>
                  </View>
                </View>
              </View>

              {canManage && (
                <View style={styles.actionRow}>
                  <TouchableOpacity
                    style={styles.actionBtn}
                    onPress={() => handleChangeRole(member)}
                  >
                    <Ionicons name="swap-vertical" size={16} color={COLORS.primary} />
                    <Text style={styles.actionBtnText}>Change Role</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.actionBtn, { borderColor: COLORS.error }]}
                    onPress={() => handleRemoveMember(member)}
                  >
                    <Ionicons name="person-remove" size={16} color={COLORS.error} />
                    <Text style={[styles.actionBtnText, { color: COLORS.error }]}>Remove</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          );
        })}

        {members.length === 0 && (
          <View style={styles.emptyState}>
            <Ionicons name="people-outline" size={48} color={COLORS.textMuted} />
            <Text style={styles.emptyTitle}>No Members</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row', alignItems: 'center', padding: 16, paddingBottom: 20,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center', marginRight: 12,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  legendBar: {
    flexDirection: 'row', flexWrap: 'wrap',
    paddingHorizontal: 16, paddingVertical: 10, gap: 12,
    backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted },
  scrollView: { flex: 1 },
  scrollContent: { padding: 16 },
  memberCard: {
    backgroundColor: COLORS.white, borderRadius: 14,
    padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: COLORS.border,
  },
  memberCardMe: {
    borderColor: COLORS.primary, borderWidth: 2,
  },
  memberMain: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: {
    width: 46, height: 46, borderRadius: 23,
    justifyContent: 'center', alignItems: 'center',
  },
  memberInfo: { flex: 1 },
  nameRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  memberName: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  memberEmail: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  roleBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10, paddingVertical: 3,
    borderRadius: 10, borderWidth: 1, marginTop: 6,
  },
  roleBadgeText: { fontSize: 11, fontWeight: '700' },
  actionRow: {
    flexDirection: 'row', gap: 8, marginTop: 10,
    borderTopWidth: 1, borderTopColor: COLORS.divider, paddingTop: 10,
  },
  actionBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 8, borderWidth: 1, borderColor: COLORS.primary,
  },
  actionBtnText: { fontSize: 12, fontWeight: '600', color: COLORS.primary },
  emptyState: { alignItems: 'center', paddingTop: 60 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginTop: 16 },
  emptySubtitle: {
    fontSize: 14, color: COLORS.textSecondary, textAlign: 'center',
    marginTop: 8, paddingHorizontal: 32,
  },
});
