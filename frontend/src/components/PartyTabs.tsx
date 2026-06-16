import React from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, TextInput } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

export interface Party {
  id: string;
  name: string;
  color?: string;
}

interface PartyTabsProps {
  parties: Party[];
  activePartyId: string;
  onChange: (partyId: string) => void;
  onAddParty?: () => void;
  onRenameParty?: (partyId: string, newName: string) => void;
  onRemoveParty?: (partyId: string) => void;
  maxParties?: number;
  showManageControls?: boolean;
  collectiveLabel?: string;
  isCollective?: boolean;
}

const PARTY_COLORS = ['#6366F1', '#F59E0B', '#10B981', '#EF4444', '#8B5CF6', '#EC4899', '#0EA5E9'];

export function defaultPartyColor(idx: number): string {
  return PARTY_COLORS[idx % PARTY_COLORS.length];
}

/**
 * Chip-tab row for switching the active party inside a multi-party question.
 * Sits above the question's text input and visually conveys *whose* answer is
 * being captured. Per the v3.23 spec, supports up to 7 parties.
 */
export const PartyTabs: React.FC<PartyTabsProps> = ({
  parties, activePartyId, onChange, onAddParty, onRemoveParty, onRenameParty,
  maxParties = 7, showManageControls = false, isCollective = false, collectiveLabel = 'Shared',
}) => {
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [draftName, setDraftName] = React.useState('');

  if (isCollective) {
    return (
      <View style={styles.collectiveTag}>
        <Ionicons name="people" size={12} color="#475569" />
        <Text style={styles.collectiveText}>{collectiveLabel} — one answer for everyone</Text>
      </View>
    );
  }
  return (
    <View style={styles.row}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
        {parties.map((p, idx) => {
          const color = p.color || defaultPartyColor(idx);
          const active = p.id === activePartyId;
          const editing = editingId === p.id;
          if (editing) {
            return (
              <View key={p.id} style={[styles.chip, { borderColor: color, backgroundColor: '#FFF' }]}>
                <TextInput
                  value={draftName}
                  onChangeText={setDraftName}
                  autoFocus
                  onBlur={() => { if (draftName.trim() && onRenameParty) onRenameParty(p.id, draftName.trim()); setEditingId(null); }}
                  onSubmitEditing={() => { if (draftName.trim() && onRenameParty) onRenameParty(p.id, draftName.trim()); setEditingId(null); }}
                  style={[styles.chipText, { color, minWidth: 80 }]}
                />
              </View>
            );
          }
          return (
            <TouchableOpacity
              key={p.id}
              onPress={() => onChange(p.id)}
              onLongPress={() => { if (showManageControls && onRenameParty) { setEditingId(p.id); setDraftName(p.name); } }}
              style={[styles.chip, active ? { backgroundColor: color, borderColor: color } : { borderColor: color }]}
            >
              <Text style={[styles.chipText, { color: active ? '#FFF' : color }]} numberOfLines={1}>{p.name}</Text>
              {showManageControls && parties.length > 2 && onRemoveParty && active && (
                <TouchableOpacity onPress={() => onRemoveParty(p.id)} hitSlop={{ top: 6, right: 6, bottom: 6, left: 6 }}>
                  <Ionicons name="close-circle" size={14} color="#FFF" />
                </TouchableOpacity>
              )}
            </TouchableOpacity>
          );
        })}
        {showManageControls && onAddParty && parties.length < maxParties && (
          <TouchableOpacity onPress={onAddParty} style={styles.addChip}>
            <Ionicons name="add" size={14} color="#475569" />
            <Text style={styles.addText}>Add party</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1.5, borderRadius: 18, paddingHorizontal: 12, paddingVertical: 6, backgroundColor: '#FFFFFF' },
  chipText: { fontSize: 12, fontWeight: '700', maxWidth: 120 },
  addChip: { flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, borderColor: '#CBD5E1', borderStyle: 'dashed', borderRadius: 18, paddingHorizontal: 10, paddingVertical: 6, backgroundColor: '#F8FAFC' },
  addText: { fontSize: 11, color: '#475569', fontWeight: '600' },
  collectiveTag: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#F1F5F9', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 4, alignSelf: 'flex-start', marginBottom: 6 },
  collectiveText: { fontSize: 11, fontWeight: '600', color: '#475569' },
});

export default PartyTabs;
