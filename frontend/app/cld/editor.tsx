/**
 * CLD Engine — Phase A Visual Editor + Manual CRUD
 *
 * Supports both:
 *  - Decision-scoped CLDs:  /cld/editor?decision_id=XXX
 *  - Module-scoped CLDs:    /cld/editor?module_type=tepfi
 *
 * On web: rich React Flow (@xyflow/react) visual editor (drag, connect, polarity toggle).
 * On native: structured tabular list editor with same CRUD operations.
 */
import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Platform,
  Modal,
  Alert,
  useWindowDimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';
import CLDFlowEditor, { type CLDFlowEditorHandle } from '../../src/components/CLDFlowEditor';

interface CLDNode {
  factor_id: string;
  name: string;
  x?: number;
  y?: number;
  base_value?: number;
  centrality?: number;
  classification?: string;
  priority_rank?: number;
  gap_multiplier?: number;
  locked?: boolean;
  color?: string;
}

interface CLDLink {
  from_id: string;
  to_id: string;
  link_type: string; // 'reinforcing' | 'balancing'
  strength: number;
  delay?: number;
  description?: string;
}

const MODULE_LABEL: Record<string, string> = {
  master: 'Master',
  tepfi: 'TEPFI Resource Matrix',
  time_dezider: 'Time Dezider',
  decision: 'Decisions',
  pna: 'PNA',
  goal: 'Goals',
  lifestyle: 'Lifestyle',
  aala: 'AALA',
  ctt: 'CTT Tasks',
  unconditional_happiness: 'Happiness',
  conflict_breaker: 'Conflict Breaker',
  emotional_gatekeeper: 'Emotional Gatekeeper',
  solutions_store: 'Solutions Store',
  consciousness: 'Consciousness',
  ai_assistant: 'AI Assistant',
  meditation: 'Meditation',
};

export default function CLDEditorScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ decision_id?: string; module_type?: string; context_id?: string }>();
  const decisionId = (Array.isArray(params.decision_id) ? params.decision_id[0] : params.decision_id) || '';
  const moduleType = (Array.isArray(params.module_type) ? params.module_type[0] : params.module_type) || '';
  const contextId = (Array.isArray(params.context_id) ? params.context_id[0] : params.context_id) || 'default';

  const [nodes, setNodes] = useState<CLDNode[]>([]);
  const [links, setLinks] = useState<CLDLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [editingNode, setEditingNode] = useState<CLDNode | null>(null);
  const [editingLink, setEditingLink] = useState<CLDLink | null>(null);
  const [linkPicker, setLinkPicker] = useState<{ from?: string; to?: string } | null>(null);
  const [zoomPct, setZoomPct] = useState(100);
  const [fullscreenZoomPct, setFullscreenZoomPct] = useState(100);
  const [fullscreen, setFullscreen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const flowRef = useRef<CLDFlowEditorHandle>(null);
  const fullscreenRef = useRef<CLDFlowEditorHandle>(null);
  const win = useWindowDimensions();

  const titleSuffix = useMemo(() => {
    if (moduleType) return MODULE_LABEL[moduleType] || moduleType;
    if (decisionId) return `Decision · ${decisionId.slice(0, 6)}`;
    return 'New';
  }, [moduleType, decisionId]);

  const fetchCld = useCallback(async () => {
    setLoading(true);
    try {
      let cld: any = null;
      if (moduleType) {
        const res = await api.get(`/cld/module/${moduleType}`, { params: { context_id: contextId } });
        // Some endpoints wrap the doc in { cld: {...} }; others return the doc directly.
        cld = res.data?.cld ?? (res.data?.nodes ? res.data : null);
      } else if (decisionId) {
        const res = await api.get(`/cld/${decisionId}`);
        cld = res.data?.cld ?? (res.data?.nodes ? res.data : null);
      }
      const safeNodes = Array.isArray(cld?.nodes) ? cld.nodes : [];
      const safeLinks = Array.isArray(cld?.links) ? cld.links : [];
      setNodes(safeNodes);
      setLinks(safeLinks);
    } catch (e: any) {
      console.warn('Fetch CLD failed', e?.response?.data || e.message);
      setNodes([]);
      setLinks([]);
    } finally {
      setLoading(false);
    }
  }, [decisionId, moduleType, contextId]);

  useEffect(() => {
    fetchCld();
  }, [fetchCld]);

  const persist = async () => {
    setSaving(true);
    try {
      const payload = {
        nodes,
        links,
        loops: [],
        layout_type: 'manual',
        notes: '',
        context_id: contextId,
      };
      if (moduleType) {
        await api.post(`/cld/module/${moduleType}/save`, payload);
      } else if (decisionId) {
        await api.post(`/cld/${decisionId}/save`, payload);
      }
      setDirty(false);
      showAlert('Saved', 'CLD diagram saved successfully.');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not save CLD');
    } finally {
      setSaving(false);
    }
  };

  const addNode = () => {
    const id = `n_${Date.now().toString(36)}`;
    const n: CLDNode = {
      factor_id: id,
      name: `Factor ${nodes.length + 1}`,
      x: 100 + ((nodes.length * 60) % 400),
      y: 80 + Math.floor(nodes.length / 6) * 90,
      base_value: 50,
      centrality: 0.5,
      classification: 'secondary',
      priority_rank: nodes.length + 1,
      gap_multiplier: 1.0,
      locked: false,
    };
    setNodes(prev => [...prev, n]);
    setEditingNode(n);
    setDirty(true);
  };

  const updateNode = (id: string, patch: Partial<CLDNode>) => {
    setNodes(prev => prev.map(n => (n.factor_id === id ? { ...n, ...patch } : n)));
    setDirty(true);
  };

  const deleteNode = (id: string) => {
    setNodes(prev => prev.filter(n => n.factor_id !== id));
    setLinks(prev => prev.filter(l => l.from_id !== id && l.to_id !== id));
    setDirty(true);
  };

  const addLink = (fromId: string, toId: string) => {
    if (!fromId || !toId || fromId === toId) {
      showAlert('Invalid link', 'Choose two different nodes.');
      return;
    }
    if (links.some(l => l.from_id === fromId && l.to_id === toId)) {
      showAlert('Duplicate', 'A link between these nodes already exists.');
      return;
    }
    setLinks(prev => [
      ...prev,
      { from_id: fromId, to_id: toId, link_type: 'reinforcing', strength: 5, delay: 0, description: '' },
    ]);
    setDirty(true);
  };

  const updateLink = (from: string, to: string, patch: Partial<CLDLink>) => {
    setLinks(prev => prev.map(l => (l.from_id === from && l.to_id === to ? { ...l, ...patch } : l)));
    setDirty(true);
  };

  const deleteLink = (from: string, to: string) => {
    setLinks(prev => prev.filter(l => !(l.from_id === from && l.to_id === to)));
    setDirty(true);
  };

  const togglePolarity = (from: string, to: string) => {
    setLinks(prev =>
      prev.map(l =>
        l.from_id === from && l.to_id === to
          ? { ...l, link_type: l.link_type === 'reinforcing' ? 'balancing' : 'reinforcing' }
          : l,
      ),
    );
    setDirty(true);
  };

  const autoLayout = () => {
    // Circular auto-layout (deterministic, no backend call required)
    if (nodes.length === 0) return;
    const cx = 250;
    const cy = 230;
    const r = Math.max(120, 25 * nodes.length);
    setNodes(prev =>
      prev.map((n, i) => {
        const a = (2 * Math.PI * i) / prev.length - Math.PI / 2;
        return { ...n, x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
      }),
    );
    setDirty(true);
  };

  const aiGenerate = async () => {
    try {
      setSaving(true);
      if (moduleType === 'tepfi') {
        await api.post(`/cld/module/tepfi/generate-structured`, { context_id: contextId });
      } else if (moduleType === 'time_dezider') {
        await api.post(`/cld/module/time_dezider/generate-structured`, { context_id: contextId });
      } else if (moduleType === 'master') {
        await api.post(`/cld/module/master/generate-bridge`, { context_id: contextId });
      } else if (moduleType === 'decision') {
        showAlert('Decision module',
          'Decision CLDs are generated automatically from your PRR decisions. Open a specific decision and use its CLD tab instead.');
        return;
      } else if (moduleType) {
        await api.post(`/cld/module/${moduleType}/generate`, { context_id: contextId });
      } else if (decisionId) {
        await api.post(`/cld/${decisionId}/generate`, {});
      }
      await fetchCld();
      showAlert('Generated', 'CLD generated successfully.');
    } catch (e: any) {
      showAlert('Generation failed', e?.response?.data?.detail || 'Could not generate CLD');
    } finally {
      setSaving(false);
    }
  };

  const confirmDeleteAll = () => {
    if (nodes.length === 0 && links.length === 0) return;
    if (Platform.OS === 'web') {
      // eslint-disable-next-line no-alert
      if (!window.confirm('Clear all nodes and links from this CLD?')) return;
      setNodes([]); setLinks([]); setDirty(true);
    } else {
      Alert.alert('Clear CLD', 'Remove all nodes and links?', [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Clear', style: 'destructive', onPress: () => { setNodes([]); setLinks([]); setDirty(true); } },
      ]);
    }
  };

  // ─── Render Helpers ─────────────────────────────────────

  const renderNodeRow = (n: CLDNode) => (
    <View key={n.factor_id} style={styles.row}>
      <View style={[styles.colorDot, { backgroundColor: n.color || COLORS.primary }]} />
      <View style={{ flex: 1 }}>
        <Text style={styles.rowTitle} numberOfLines={1}>{n.name}</Text>
        <Text style={styles.rowMeta}>
          {n.classification} · rank {n.priority_rank} · base {Math.round(n.base_value || 0)}
        </Text>
      </View>
      <TouchableOpacity style={styles.iconBtn} onPress={() => setEditingNode(n)}>
        <Ionicons name="create-outline" size={18} color={COLORS.primary} />
      </TouchableOpacity>
      <TouchableOpacity style={styles.iconBtn} onPress={() => deleteNode(n.factor_id)}>
        <Ionicons name="trash-outline" size={18} color={COLORS.error} />
      </TouchableOpacity>
    </View>
  );

  const renderLinkRow = (l: CLDLink) => {
    const fromNode = nodes.find(n => n.factor_id === l.from_id);
    const toNode = nodes.find(n => n.factor_id === l.to_id);
    const polarityColor = l.link_type === 'reinforcing' ? '#10B981' : '#EF4444';
    const polaritySym = l.link_type === 'reinforcing' ? '+' : '−';
    return (
      <View key={`${l.from_id}_${l.to_id}`} style={styles.row}>
        <View style={[styles.polarityBadge, { backgroundColor: polarityColor }]}>
          <Text style={styles.polaritySym}>{polaritySym}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.rowTitle} numberOfLines={1}>
            {fromNode?.name || l.from_id} → {toNode?.name || l.to_id}
          </Text>
          <Text style={styles.rowMeta}>
            {l.link_type} · strength {l.strength.toFixed(1)} · delay {l.delay || 0}
          </Text>
        </View>
        <TouchableOpacity style={styles.iconBtn} onPress={() => togglePolarity(l.from_id, l.to_id)}>
          <Ionicons name="swap-horizontal" size={18} color={COLORS.primary} />
        </TouchableOpacity>
        <TouchableOpacity style={styles.iconBtn} onPress={() => setEditingLink(l)}>
          <Ionicons name="create-outline" size={18} color={COLORS.primary} />
        </TouchableOpacity>
        <TouchableOpacity style={styles.iconBtn} onPress={() => deleteLink(l.from_id, l.to_id)}>
          <Ionicons name="trash-outline" size={18} color={COLORS.error} />
        </TouchableOpacity>
      </View>
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.center}><ActivityIndicator color={COLORS.primary} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.headerBtn} onPress={() => router.back()}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textPrimary} />
          <Text style={styles.headerBtnText}>Back</Text>
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>CLD Editor</Text>
          <Text style={styles.subtitle} numberOfLines={1}>
            {titleSuffix} · {nodes.length} nodes · {links.length} links
          </Text>
        </View>
        <TouchableOpacity
          style={[styles.saveBtn, !dirty && { opacity: 0.5 }]}
          disabled={!dirty || saving}
          onPress={persist}
        >
          {saving ? <ActivityIndicator size="small" color="#FFF" /> : (
            <>
              <Ionicons name="save" size={16} color="#FFF" />
              <Text style={styles.saveBtnText}>Save</Text>
            </>
          )}
        </TouchableOpacity>
      </View>

      {/* Toolbar — plain View with wrap so it CANNOT collapse no matter what state. */}
      <View style={styles.toolbar}>
        <TouchableOpacity style={styles.toolBtn} onPress={addNode}>
          <Ionicons name="add-circle" size={16} color={COLORS.primary} />
          <Text style={styles.toolBtnText}>Add Node</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.toolBtn}
          onPress={() => setLinkPicker({})}
          disabled={nodes.length < 2}
        >
          <Ionicons name="git-network" size={16} color={nodes.length < 2 ? COLORS.textMuted : COLORS.primary} />
          <Text style={[styles.toolBtnText, nodes.length < 2 && { color: COLORS.textMuted }]}>Add Link</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.toolBtn} onPress={autoLayout} disabled={nodes.length === 0}>
          <Ionicons name="grid" size={16} color={nodes.length === 0 ? COLORS.textMuted : COLORS.primary} />
          <Text style={[styles.toolBtnText, nodes.length === 0 && { color: COLORS.textMuted }]}>Layout</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.toolBtn} onPress={aiGenerate}>
          <Ionicons name="sparkles" size={16} color="#7C3AED" />
          <Text style={[styles.toolBtnText, { color: '#7C3AED' }]}>Generate</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.toolBtn} onPress={confirmDeleteAll}>
          <Ionicons name="trash" size={16} color={COLORS.error} />
          <Text style={[styles.toolBtnText, { color: COLORS.error }]}>Clear</Text>
        </TouchableOpacity>

        {/* Visual separator */}
        <View style={styles.toolSep} />

        {/* Zoom controls — placed in main toolbar so they cannot be intercepted */}
        <TouchableOpacity style={styles.zoomBtn} onPress={() => flowRef.current?.zoomOut()}>
          <Text style={styles.zoomBtnTxt}>−</Text>
        </TouchableOpacity>
        <View style={styles.zoomPctWrap}><Text style={styles.zoomPctTxt}>{zoomPct}%</Text></View>
        <TouchableOpacity style={styles.zoomBtn} onPress={() => flowRef.current?.zoomIn()}>
          <Text style={styles.zoomBtnTxt}>+</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.toolBtn, styles.fitBtn]} onPress={() => flowRef.current?.fitView()}>
          <Text style={[styles.toolBtnText, { color: '#7C3AED' }]}>Fit</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.toolBtn, styles.fitBtn]} onPress={() => flowRef.current?.resetView()}>
          <Text style={[styles.toolBtnText, { color: '#7C3AED' }]}>1:1</Text>
        </TouchableOpacity>

        <View style={styles.toolSep} />

        <TouchableOpacity style={styles.toolBtn} onPress={() => setFullscreen(true)}>
          <Ionicons name="expand" size={16} color="#0EA5E9" />
          <Text style={[styles.toolBtnText, { color: '#0EA5E9' }]}>Fullscreen</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.toolBtn} onPress={() => setHelpOpen(true)}>
          <Ionicons name="help-circle" size={16} color="#F59E0B" />
          <Text style={[styles.toolBtnText, { color: '#F59E0B' }]}>Help</Text>
        </TouchableOpacity>
      </View>

      {/* Visual canvas — works on both web and native via SVG */}
      <View style={styles.flowWrap}>
        <CLDFlowEditor
          ref={flowRef}
          nodes={nodes as any}
          links={links as any}
          onNodesChange={(updated) => { setNodes(updated as any); setDirty(true); }}
          onLinksChange={(updated) => { setLinks(updated as any); setDirty(true); }}
          onZoomChange={setZoomPct}
          hideToolbar
          onEditNode={(id) => {
            const n = nodes.find(x => x.factor_id === id);
            if (n) setEditingNode(n);
          }}
          onEditLink={(from, to) => {
            const l = links.find(x => x.from_id === from && x.to_id === to);
            if (l) setEditingLink(l);
          }}
        />
      </View>

      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
        <Text style={styles.section}>Nodes ({nodes.length})</Text>
        {nodes.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="ellipse-outline" size={32} color={COLORS.textMuted} />
            <Text style={styles.emptyText}>No nodes yet. Tap “Add Node” or “Generate”.</Text>
          </View>
        ) : (
          nodes.map(renderNodeRow)
        )}

        <Text style={[styles.section, { marginTop: 18 }]}>Links ({links.length})</Text>
        {links.length === 0 ? (
          <View style={styles.empty}>
            <Ionicons name="git-network-outline" size={32} color={COLORS.textMuted} />
            <Text style={styles.emptyText}>No links yet. Add at least two nodes, then tap “Add Link”.</Text>
          </View>
        ) : (
          links.map(renderLinkRow)
        )}
      </ScrollView>

      {/* Node Editor Modal */}
      <Modal
        visible={!!editingNode}
        transparent
        animationType="fade"
        onRequestClose={() => setEditingNode(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Edit Node</Text>
            {editingNode && (
              <>
                <Text style={styles.fieldLabel}>Name</Text>
                <TextInput
                  style={styles.input}
                  value={editingNode.name}
                  onChangeText={(t) => setEditingNode({ ...editingNode, name: t })}
                  placeholder="Factor name"
                />
                <Text style={styles.fieldLabel}>Classification</Text>
                <View style={styles.segment}>
                  {(['primary', 'secondary'] as const).map(c => (
                    <TouchableOpacity
                      key={c}
                      style={[styles.segmentBtn, editingNode.classification === c && styles.segmentActive]}
                      onPress={() => setEditingNode({ ...editingNode, classification: c })}
                    >
                      <Text style={[styles.segmentText, editingNode.classification === c && { color: '#FFF' }]}>
                        {c}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <Text style={styles.fieldLabel}>Base Value (0–100)</Text>
                <TextInput
                  style={styles.input}
                  value={String(editingNode.base_value ?? 50)}
                  keyboardType="numeric"
                  onChangeText={(t) => setEditingNode({ ...editingNode, base_value: Math.max(0, Math.min(100, parseFloat(t) || 0)) })}
                />
                <Text style={styles.fieldLabel}>Priority Rank</Text>
                <TextInput
                  style={styles.input}
                  value={String(editingNode.priority_rank ?? 1)}
                  keyboardType="numeric"
                  onChangeText={(t) => setEditingNode({ ...editingNode, priority_rank: parseInt(t) || 1 })}
                />
              </>
            )}
            <View style={styles.modalRow}>
              <TouchableOpacity style={[styles.modalBtn, styles.modalBtnGhost]} onPress={() => setEditingNode(null)}>
                <Text style={styles.modalBtnGhostText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnPrimary]}
                onPress={() => {
                  if (editingNode) {
                    updateNode(editingNode.factor_id, editingNode);
                  }
                  setEditingNode(null);
                }}
              >
                <Text style={styles.modalBtnPrimaryText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Link Editor Modal */}
      <Modal
        visible={!!editingLink}
        transparent
        animationType="fade"
        onRequestClose={() => setEditingLink(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Edit Link</Text>
            {editingLink && (
              <>
                <Text style={styles.fieldLabel}>Polarity</Text>
                <View style={styles.segment}>
                  {(['reinforcing', 'balancing'] as const).map(p => (
                    <TouchableOpacity
                      key={p}
                      style={[styles.segmentBtn, editingLink.link_type === p && styles.segmentActive]}
                      onPress={() => setEditingLink({ ...editingLink, link_type: p })}
                    >
                      <Text style={[styles.segmentText, editingLink.link_type === p && { color: '#FFF' }]}>
                        {p === 'reinforcing' ? '+ Reinforcing' : '− Balancing'}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <Text style={styles.fieldLabel}>Strength (1–10)</Text>
                <TextInput
                  style={styles.input}
                  keyboardType="numeric"
                  value={String(editingLink.strength)}
                  onChangeText={(t) => setEditingLink({ ...editingLink, strength: Math.max(1, Math.min(10, parseFloat(t) || 1)) })}
                />
                <Text style={styles.fieldLabel}>Delay (steps)</Text>
                <TextInput
                  style={styles.input}
                  keyboardType="numeric"
                  value={String(editingLink.delay || 0)}
                  onChangeText={(t) => setEditingLink({ ...editingLink, delay: Math.max(0, parseInt(t) || 0) })}
                />
                <Text style={styles.fieldLabel}>Description</Text>
                <TextInput
                  style={[styles.input, { height: 60 }]}
                  multiline
                  value={editingLink.description || ''}
                  onChangeText={(t) => setEditingLink({ ...editingLink, description: t })}
                />
              </>
            )}
            <View style={styles.modalRow}>
              <TouchableOpacity style={[styles.modalBtn, styles.modalBtnGhost]} onPress={() => setEditingLink(null)}>
                <Text style={styles.modalBtnGhostText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnPrimary]}
                onPress={() => {
                  if (editingLink) {
                    updateLink(editingLink.from_id, editingLink.to_id, editingLink);
                  }
                  setEditingLink(null);
                }}
              >
                <Text style={styles.modalBtnPrimaryText}>Save</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Link Picker Modal */}
      <Modal
        visible={!!linkPicker}
        transparent
        animationType="fade"
        onRequestClose={() => setLinkPicker(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Add Link</Text>
            <Text style={styles.fieldLabel}>From</Text>
            <ScrollView style={{ maxHeight: 130 }}>
              {nodes.map(n => (
                <TouchableOpacity
                  key={'from_' + n.factor_id}
                  style={[styles.pickerRow, linkPicker?.from === n.factor_id && styles.pickerRowActive]}
                  onPress={() => setLinkPicker({ ...(linkPicker || {}), from: n.factor_id })}
                >
                  <Text style={styles.pickerText}>{n.name}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <Text style={styles.fieldLabel}>To</Text>
            <ScrollView style={{ maxHeight: 130 }}>
              {nodes.map(n => (
                <TouchableOpacity
                  key={'to_' + n.factor_id}
                  style={[styles.pickerRow, linkPicker?.to === n.factor_id && styles.pickerRowActive]}
                  onPress={() => setLinkPicker({ ...(linkPicker || {}), to: n.factor_id })}
                >
                  <Text style={styles.pickerText}>{n.name}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <View style={styles.modalRow}>
              <TouchableOpacity style={[styles.modalBtn, styles.modalBtnGhost]} onPress={() => setLinkPicker(null)}>
                <Text style={styles.modalBtnGhostText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalBtn, styles.modalBtnPrimary]}
                onPress={() => {
                  if (linkPicker?.from && linkPicker?.to) {
                    addLink(linkPicker.from, linkPicker.to);
                    setLinkPicker(null);
                  }
                }}
              >
                <Text style={styles.modalBtnPrimaryText}>Add</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ── Fullscreen Editor Modal ─────────────────────────── */}
      <Modal visible={fullscreen} animationType="slide" onRequestClose={() => setFullscreen(false)}>
        <SafeAreaView style={{ flex: 1, backgroundColor: '#FFF' }} edges={['top']}>
          <View style={styles.header}>
            <TouchableOpacity style={styles.headerBtn} onPress={() => setFullscreen(false)}>
              <Ionicons name="contract" size={20} color={COLORS.textPrimary} />
              <Text style={styles.headerBtnText}>Exit Fullscreen</Text>
            </TouchableOpacity>
            <View style={{ flex: 1 }}>
              <Text style={styles.title}>CLD Editor — Fullscreen</Text>
              <Text style={styles.subtitle} numberOfLines={1}>
                {titleSuffix} · {nodes.length} nodes · {links.length} links
              </Text>
            </View>
            <TouchableOpacity style={styles.toolBtn} onPress={() => fullscreenRef.current?.zoomOut()}>
              <Text style={styles.zoomBtnTxt}>−</Text>
            </TouchableOpacity>
            <Text style={styles.zoomPctTxt}>{fullscreenZoomPct}%</Text>
            <TouchableOpacity style={styles.toolBtn} onPress={() => fullscreenRef.current?.zoomIn()}>
              <Text style={styles.zoomBtnTxt}>+</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.toolBtn} onPress={() => fullscreenRef.current?.fitView()}>
              <Text style={[styles.toolBtnText, { color: '#7C3AED' }]}>Fit</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.toolBtn} onPress={() => setHelpOpen(true)}>
              <Ionicons name="help-circle" size={18} color="#F59E0B" />
            </TouchableOpacity>
          </View>
          <View style={{ flex: 1 }}>
            <CLDFlowEditor
              ref={fullscreenRef}
              nodes={nodes as any}
              links={links as any}
              width={Math.max(800, win.width - 20)}
              height={Math.max(400, win.height - 130)}
              hideToolbar
              onZoomChange={setFullscreenZoomPct}
              onNodesChange={(updated) => { setNodes(updated as any); setDirty(true); }}
              onLinksChange={(updated) => { setLinks(updated as any); setDirty(true); }}
              onEditNode={(id) => {
                const n = nodes.find(x => x.factor_id === id);
                if (n) setEditingNode(n);
              }}
              onEditLink={(from, to) => {
                const l = links.find(x => x.from_id === from && x.to_id === to);
                if (l) setEditingLink(l);
              }}
            />
          </View>
        </SafeAreaView>
      </Modal>

      {/* ── Help / Usage Guide Modal ────────────────────────── */}
      <Modal visible={helpOpen} transparent animationType="fade" onRequestClose={() => setHelpOpen(false)}>
        <View style={styles.modalBackdrop}>
          <View style={[styles.modalCard, { maxWidth: 520 }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <Text style={styles.modalTitle}>📘 How to use the CLD Editor</Text>
              <TouchableOpacity onPress={() => setHelpOpen(false)}>
                <Ionicons name="close" size={22} color={COLORS.textMuted} />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 460 }}>
              <Text style={styles.helpHeading}>🟢 Add a Node</Text>
              <Text style={styles.helpText}>• Click the <Text style={styles.helpBold}>“Add Node”</Text> toolbar button — appears at canvas center.{"\n"}• OR tap any empty area of the canvas — a node is created where you tapped.</Text>

              <Text style={styles.helpHeading}>🔗 Add a Link (with direction)</Text>
              <Text style={styles.helpText}>1. Tap a node on the canvas — it becomes <Text style={{ color: '#7C3AED', fontWeight: '700' }}>highlighted purple</Text>.{"\n"}2. A floating bar appears with <Text style={styles.helpBold}>“Link from here →”</Text>. Tap it.{"\n"}3. The source node turns <Text style={{ color: '#F59E0B', fontWeight: '700' }}>orange</Text>. Tap any other node — that becomes the <Text style={styles.helpBold}>target</Text>.{"\n"}4. The arrow points from source → target.</Text>
              <Text style={styles.helpText}>OR click the <Text style={styles.helpBold}>“Add Link”</Text> toolbar button to pick source & target from a list.</Text>

              <Text style={styles.helpHeading}>⚙️ Polarity (+ / −)</Text>
              <Text style={styles.helpText}>• <Text style={{ color: '#10B981', fontWeight: '700' }}>+ Green solid</Text> = <Text style={styles.helpBold}>reinforcing</Text> (same direction){"\n"}• <Text style={{ color: '#EF4444', fontWeight: '700' }}>− Red dashed</Text> = <Text style={styles.helpBold}>balancing</Text> (opposite direction){"\n"}• Toggle via the swap icon ↔ in the link row below, or open the link editor.</Text>

              <Text style={styles.helpHeading}>✏️ Edit a Node or Link</Text>
              <Text style={styles.helpText}>• Long-press a node on canvas, OR tap to select then “Edit Node”.{"\n"}• Use the rows in the “Nodes” and “Links” lists below — pencil icon edits, trash deletes.</Text>

              <Text style={styles.helpHeading}>🖱️ Pan, Zoom & Fit</Text>
              <Text style={styles.helpText}>• <Text style={styles.helpBold}>Pan</Text>: drag any empty area of the canvas.{"\n"}• <Text style={styles.helpBold}>Zoom</Text>: use the toolbar <Text style={styles.helpBold}>+ / −</Text> buttons, or scroll the mouse wheel.{"\n"}• <Text style={styles.helpBold}>Fit</Text>: auto-zoom to show all nodes.{"\n"}• <Text style={styles.helpBold}>1:1</Text>: reset to 100% zoom.</Text>

              <Text style={styles.helpHeading}>🔄 Move a Node</Text>
              <Text style={styles.helpText}>Drag a node directly — release where you want it.</Text>

              <Text style={styles.helpHeading}>🪄 Generate (AI / Deterministic)</Text>
              <Text style={styles.helpText}>The <Text style={styles.helpBold}>“Generate”</Text> button asks the backend to populate the CLD based on the module data (TEPFI grid, Time Dezider radial, Master bridge, etc.).</Text>

              <Text style={styles.helpHeading}>🖥️ Fullscreen</Text>
              <Text style={styles.helpText}>Click <Text style={styles.helpBold}>“Fullscreen”</Text> in the toolbar for a much larger editing area.</Text>

              <Text style={styles.helpHeading}>💾 Save</Text>
              <Text style={styles.helpText}>The purple Save button at top-right becomes active when you make changes. Click to persist.</Text>
            </ScrollView>
            <TouchableOpacity style={[styles.modalBtn, styles.modalBtnPrimary, { marginTop: 12 }]} onPress={() => setHelpOpen(false)}>
              <Text style={styles.modalBtnPrimaryText}>Got it</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFF' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: '#F1F5F9',
    gap: 10,
  },
  headerBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, padding: 6 },
  headerBtnText: { color: COLORS.textPrimary, fontWeight: '600', fontSize: 13 },
  title: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted },
  saveBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 8, minWidth: 80, justifyContent: 'center',
  },
  saveBtnText: { color: '#FFF', fontWeight: '700', fontSize: 13 },
  toolbar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    minHeight: 60,
    backgroundColor: '#F8FAFC',
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
    flexShrink: 0,
  },
  toolBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 10, paddingVertical: 6,
    backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E2E8F0',
    borderRadius: 8,
  },
  toolBtnText: { color: COLORS.primary, fontWeight: '600', fontSize: 12 },
  toolSep: { width: 1, height: 22, backgroundColor: '#E2E8F0', marginHorizontal: 4 },
  zoomBtn: {
    width: 30, height: 30, borderRadius: 6,
    backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E2E8F0',
    justifyContent: 'center', alignItems: 'center',
  },
  zoomBtnTxt: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, lineHeight: 18 },
  zoomPctWrap: { minWidth: 44, alignItems: 'center' },
  zoomPctTxt: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted, paddingHorizontal: 6 },
  fitBtn: { backgroundColor: '#EDE9FE' },
  helpHeading: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, marginTop: 10, marginBottom: 4 },
  helpText: { fontSize: 12, color: COLORS.textSecondary, lineHeight: 18, marginBottom: 4 },
  helpBold: { fontWeight: '700', color: COLORS.textPrimary },
  flowWrap: { height: 360, borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  section: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  row: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingHorizontal: 10, paddingVertical: 10,
    backgroundColor: '#FFF', borderRadius: 10,
    borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 6,
  },
  colorDot: { width: 12, height: 12, borderRadius: 6 },
  polarityBadge: { width: 26, height: 26, borderRadius: 13, justifyContent: 'center', alignItems: 'center' },
  polaritySym: { color: '#FFF', fontWeight: '800', fontSize: 16 },
  rowTitle: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  rowMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  iconBtn: { padding: 6 },
  empty: { alignItems: 'center', gap: 6, padding: 18, backgroundColor: '#F8FAFC', borderRadius: 10 },
  emptyText: { color: COLORS.textMuted, fontSize: 12, textAlign: 'center' },

  // Modals
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalCard: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, width: '100%', maxWidth: 440 },
  modalTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  fieldLabel: { fontSize: 12, color: COLORS.textMuted, marginTop: 6, marginBottom: 4, fontWeight: '600' },
  input: {
    borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary,
    backgroundColor: '#FFF',
  },
  segment: { flexDirection: 'row', gap: 6 },
  segmentBtn: { flex: 1, paddingVertical: 8, alignItems: 'center', borderRadius: 8, backgroundColor: '#F1F5F9' },
  segmentActive: { backgroundColor: COLORS.primary },
  segmentText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },
  modalRow: { flexDirection: 'row', gap: 8, marginTop: 14 },
  modalBtn: { flex: 1, paddingVertical: 10, borderRadius: 8, alignItems: 'center' },
  modalBtnGhost: { backgroundColor: '#F1F5F9' },
  modalBtnGhostText: { color: COLORS.textPrimary, fontWeight: '600' },
  modalBtnPrimary: { backgroundColor: COLORS.primary },
  modalBtnPrimaryText: { color: '#FFF', fontWeight: '700' },
  pickerRow: { padding: 8, borderRadius: 6, marginBottom: 4, backgroundColor: '#F8FAFC' },
  pickerRowActive: { backgroundColor: '#DDD6FE' },
  pickerText: { color: COLORS.textPrimary, fontSize: 12 },
});
