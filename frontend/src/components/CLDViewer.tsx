import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  ScrollView,
  TextInput,
  Modal,
  Dimensions,
  Platform,
} from 'react-native';
import Svg, { Circle, Line, Defs, Marker, Path as SvgPath, Text as SvgText, G, Rect } from 'react-native-svg';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import Slider from '@react-native-community/slider';
import { COLORS } from '../constants/colors';
import type { Factor } from '../types/decision';

// ========================
// TYPES
// ========================

interface CLDNode {
  factor_id: string;
  name: string;
  x: number;
  y: number;
  centrality: number;
  classification: 'primary' | 'secondary';
  priority_rank: number;
  gap_multiplier: number;
  base_value: number;
  locked: boolean;
}

interface CLDLink {
  from_id: string;
  to_id: string;
  link_type: string;
  strength: number;
  delay: number;
  description: string;
}

interface CLDLoop {
  name: string;
  loop_type: string;
  factor_ids: string[];
}

interface FactorAnalysis {
  factor_id: string;
  factor_name: string;
  centrality: number;
  classification: 'primary' | 'secondary';
  priority_rank: number;
  gap_multiplier: number;
  base_value: number;
  reasoning: string;
}

interface CLDData {
  nodes: CLDNode[];
  links: CLDLink[];
  loops: CLDLoop[];
}

interface SimulationStep {
  step: number;
  values: { [key: string]: number };
  deltas: { [key: string]: number };
}

interface SimulationResult {
  timeline: SimulationStep[];
  final_values: { [key: string]: number };
  total_impact: { [key: string]: number };
  stability: string;
  most_affected: string[];
  baseline: { [key: string]: number };
}

interface CLDViewerProps {
  factors: Factor[];
  decisionId: string;
  decisionTitle: string;
  decisionContext: string;
  lifeArea?: string;
  decisionType?: string;
  onApplyResults: (results: {
    classifications: { [factorId: string]: 'primary' | 'secondary' };
    priorities: { factorId: string; order: number }[];
    gapMultipliers: { [factorId: string]: number };
  }) => void;
  visible: boolean;
  onClose: () => void;
}

type TabType = 'diagram' | 'analysis' | 'simulate';

const DIAGRAM_SIZE = 380;

// ========================
// HELPERS
// ========================

const getBaseUrl = () => {
  return Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
};

const getAuthHeaders = async () => {
  const token = await AsyncStorage.getItem('session_token');
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
};

// ========================
// MAIN COMPONENT
// ========================

export default function CLDViewer({
  factors,
  decisionId,
  decisionTitle,
  decisionContext,
  lifeArea,
  decisionType,
  onApplyResults,
  visible,
  onClose,
}: CLDViewerProps) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [cldData, setCldData] = useState<CLDData | null>(null);
  const [factorAnalysis, setFactorAnalysis] = useState<FactorAnalysis[]>([]);
  const [activeTab, setActiveTab] = useState<TabType>('diagram');
  const [isSaved, setIsSaved] = useState(false);

  // Edit mode
  const [editMode, setEditMode] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedLink, setSelectedLink] = useState<{ from: string; to: string } | null>(null);
  const [addingLink, setAddingLink] = useState(false);
  const [linkFromId, setLinkFromId] = useState<string | null>(null);

  // Node edit modal
  const [nodeEditVisible, setNodeEditVisible] = useState(false);
  const [editingNode, setEditingNode] = useState<CLDNode | null>(null);

  // Link edit modal
  const [linkEditVisible, setLinkEditVisible] = useState(false);
  const [editingLink, setEditingLink] = useState<CLDLink | null>(null);

  // Simulation state
  const [simShockFactorId, setSimShockFactorId] = useState<string>('');
  const [simDelta, setSimDelta] = useState<number>(20);
  const [simSteps, setSimSteps] = useState<number>(5);
  const [simDampening, setSimDampening] = useState<number>(0.7);
  const [simResult, setSimResult] = useState<SimulationResult | null>(null);
  const [simLoading, setSimLoading] = useState(false);
  const [simViewStep, setSimViewStep] = useState<number>(0);

  // Layout
  const [layoutType, setLayoutType] = useState<string>('circular');

  if (!visible) return null;

  // ========================
  // LOAD SAVED CLD
  // ========================

  const loadSavedCLD = async () => {
    try {
      const headers = await getAuthHeaders();
      const resp = await fetch(`${getBaseUrl()}/api/cld/${decisionId}`, { headers });
      const data = await resp.json();
      if (data.cld && data.cld.nodes && data.cld.nodes.length > 0) {
        const nodes = (data.cld.nodes || []).map((n: any) => ({
          ...n,
          x: Math.max(30, Math.min(DIAGRAM_SIZE - 30, (n.x || 200) * (DIAGRAM_SIZE / 400))),
          y: Math.max(30, Math.min(DIAGRAM_SIZE - 30, (n.y || 200) * (DIAGRAM_SIZE / 400))),
        }));
        setCldData({
          nodes,
          links: data.cld.links || [],
          loops: data.cld.loops || [],
        });
        setIsSaved(true);
        setLayoutType(data.cld.layout_type || 'circular');
        // Set first factor as default simulation target
        if (nodes.length > 0 && !simShockFactorId) {
          setSimShockFactorId(nodes[0].factor_id);
        }
      }
    } catch {
      // No saved CLD, that's fine
    }
  };

  useEffect(() => {
    if (visible && decisionId) {
      loadSavedCLD();
    }
  }, [visible, decisionId]);

  // ========================
  // GENERATE CLD
  // ========================

  const generateCLD = async () => {
    if (factors.filter(f => !f.parent_id).length < 2) {
      Alert.alert('Need More Factors', 'At least 2 top-level factors are required for CLD analysis.');
      return;
    }
    setLoading(true);
    try {
      const headers = await getAuthHeaders();
      const resp = await fetch(`${getBaseUrl()}/api/cld/${decisionId}/generate`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          decision_title: decisionTitle,
          decision_context: decisionContext,
          life_area: lifeArea || '',
          decision_type: decisionType || '',
          factors: factors.filter(f => !f.parent_id).map(f => ({ id: f.id, name: f.name })),
          auto_save: true,
        }),
      });
      const data = await resp.json();
      if (data.cld) {
        const nodes = (data.cld.nodes || []).map((n: CLDNode) => ({
          ...n,
          x: Math.max(30, Math.min(DIAGRAM_SIZE - 30, (n.x || 200) * (DIAGRAM_SIZE / 400))),
          y: Math.max(30, Math.min(DIAGRAM_SIZE - 30, (n.y || 200) * (DIAGRAM_SIZE / 400))),
        }));
        setCldData({ nodes, links: data.cld.links || [], loops: data.cld.loops || [] });
        setFactorAnalysis(data.factor_analysis || []);
        setIsSaved(data.auto_saved || false);
        if (nodes.length > 0) {
          setSimShockFactorId(nodes[0].factor_id);
        }
      } else {
        Alert.alert('Error', data.detail || 'CLD generation failed');
      }
    } catch (err) {
      Alert.alert('Error', 'Failed to generate CLD');
    } finally {
      setLoading(false);
    }
  };

  // ========================
  // SAVE CLD
  // ========================

  const saveCLD = async () => {
    if (!cldData) return;
    setSaving(true);
    try {
      const headers = await getAuthHeaders();
      // Scale positions back to 400x400 coordinate system for storage
      const scaledNodes = cldData.nodes.map(n => ({
        ...n,
        x: n.x * (400 / DIAGRAM_SIZE),
        y: n.y * (400 / DIAGRAM_SIZE),
      }));
      const resp = await fetch(`${getBaseUrl()}/api/cld/${decisionId}/save`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          nodes: scaledNodes,
          links: cldData.links,
          loops: cldData.loops,
          layout_type: layoutType,
        }),
      });
      const data = await resp.json();
      if (resp.ok) {
        setIsSaved(true);
      } else {
        Alert.alert('Error', data.detail || 'Failed to save CLD');
      }
    } catch {
      Alert.alert('Error', 'Failed to save CLD');
    } finally {
      setSaving(false);
    }
  };

  // ========================
  // CHANGE LAYOUT
  // ========================

  const changeLayout = async (type: string) => {
    if (!cldData) return;
    // First save current state
    await saveCLD();
    setLoading(true);
    try {
      const headers = await getAuthHeaders();
      const resp = await fetch(`${getBaseUrl()}/api/cld/${decisionId}/layout`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ layout_type: type }),
      });
      const data = await resp.json();
      if (data.nodes) {
        const nodes = data.nodes.map((n: any) => ({
          ...n,
          x: Math.max(30, Math.min(DIAGRAM_SIZE - 30, (n.x || 200) * (DIAGRAM_SIZE / 400))),
          y: Math.max(30, Math.min(DIAGRAM_SIZE - 30, (n.y || 200) * (DIAGRAM_SIZE / 400))),
        }));
        setCldData(prev => prev ? { ...prev, nodes } : prev);
        setLayoutType(type);
      }
    } catch {
      Alert.alert('Error', 'Failed to compute layout');
    } finally {
      setLoading(false);
    }
  };

  // ========================
  // SIMULATION
  // ========================

  const runSimulation = async () => {
    if (!cldData || !simShockFactorId) {
      Alert.alert('Select Factor', 'Please select a factor to simulate.');
      return;
    }
    if (!isSaved) {
      // Auto-save before simulating
      await saveCLD();
    }
    setSimLoading(true);
    setSimResult(null);
    try {
      const headers = await getAuthHeaders();
      const resp = await fetch(`${getBaseUrl()}/api/cld/${decisionId}/simulate`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          shock_factor_id: simShockFactorId,
          shock_delta: simDelta,
          time_steps: simSteps,
          dampening: simDampening,
        }),
      });
      const data = await resp.json();
      if (resp.ok) {
        setSimResult(data);
        setSimViewStep(data.timeline.length - 1);
      } else {
        Alert.alert('Error', data.detail || 'Simulation failed');
      }
    } catch {
      Alert.alert('Error', 'Failed to run simulation');
    } finally {
      setSimLoading(false);
    }
  };

  // ========================
  // APPLY TO STEPS
  // ========================

  const applyToSteps = () => {
    if (!factorAnalysis.length && !cldData?.nodes?.length) return;

    const sourceData = factorAnalysis.length > 0
      ? factorAnalysis
      : cldData?.nodes?.map(n => ({
          factor_id: n.factor_id,
          classification: n.classification,
          priority_rank: n.priority_rank,
          gap_multiplier: n.gap_multiplier,
        })) || [];

    const classifications: { [key: string]: 'primary' | 'secondary' } = {};
    const priorities: { factorId: string; order: number }[] = [];
    const gapMultipliers: { [key: string]: number } = {};

    const sorted = [...sourceData].sort((a: any, b: any) => a.priority_rank - b.priority_rank);
    sorted.forEach((fa: any, idx: number) => {
      classifications[fa.factor_id] = fa.classification;
      priorities.push({ factorId: fa.factor_id, order: idx });
      gapMultipliers[fa.factor_id] = fa.gap_multiplier;
    });

    onApplyResults({ classifications, priorities, gapMultipliers });
    Alert.alert('Applied', 'CLD results applied to Steps 3-5.');
    onClose();
  };

  // ========================
  // EDIT FUNCTIONS
  // ========================

  const handleNodeTap = (nodeId: string) => {
    if (!editMode) return;
    if (addingLink) {
      if (!linkFromId) {
        setLinkFromId(nodeId);
      } else if (linkFromId !== nodeId) {
        if (cldData) {
          const exists = cldData.links.some(l =>
            (l.from_id === linkFromId && l.to_id === nodeId) ||
            (l.from_id === nodeId && l.to_id === linkFromId)
          );
          if (!exists) {
            setCldData({
              ...cldData,
              links: [...cldData.links, {
                from_id: linkFromId,
                to_id: nodeId,
                link_type: 'reinforcing',
                strength: 5,
                delay: 0,
                description: 'Manual link',
              }],
            });
            setIsSaved(false);
          }
        }
        setLinkFromId(null);
        setAddingLink(false);
      }
    } else {
      setSelectedNodeId(selectedNodeId === nodeId ? null : nodeId);
      setSelectedLink(null);
    }
  };

  const openNodeEdit = (nodeId: string) => {
    if (!cldData) return;
    const node = cldData.nodes.find(n => n.factor_id === nodeId);
    if (node) {
      setEditingNode({ ...node });
      setNodeEditVisible(true);
    }
  };

  const saveNodeEdit = () => {
    if (!cldData || !editingNode) return;
    setCldData({
      ...cldData,
      nodes: cldData.nodes.map(n =>
        n.factor_id === editingNode.factor_id ? editingNode : n
      ),
    });
    setIsSaved(false);
    setNodeEditVisible(false);
    setEditingNode(null);
  };

  const openLinkEdit = (fromId: string, toId: string) => {
    if (!cldData) return;
    const link = cldData.links.find(l => l.from_id === fromId && l.to_id === toId);
    if (link) {
      setEditingLink({ ...link });
      setLinkEditVisible(true);
    }
  };

  const saveLinkEdit = () => {
    if (!cldData || !editingLink) return;
    setCldData({
      ...cldData,
      links: cldData.links.map(l =>
        l.from_id === editingLink.from_id && l.to_id === editingLink.to_id ? editingLink : l
      ),
    });
    setIsSaved(false);
    setLinkEditVisible(false);
    setEditingLink(null);
  };

  const removeNode = (nodeId: string) => {
    if (!cldData) return;
    Alert.alert('Remove Node', 'Remove this node and all its links?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove', style: 'destructive', onPress: () => {
          setCldData({
            ...cldData,
            nodes: cldData.nodes.filter(n => n.factor_id !== nodeId),
            links: cldData.links.filter(l => l.from_id !== nodeId && l.to_id !== nodeId),
          });
          setFactorAnalysis(prev => prev.filter(fa => fa.factor_id !== nodeId));
          setSelectedNodeId(null);
          setIsSaved(false);
        },
      },
    ]);
  };

  const removeLink = (fromId: string, toId: string) => {
    if (!cldData) return;
    setCldData({
      ...cldData,
      links: cldData.links.filter(l => !(l.from_id === fromId && l.to_id === toId)),
    });
    setIsSaved(false);
  };

  const toggleLinkType = (fromId: string, toId: string) => {
    if (!cldData) return;
    setCldData({
      ...cldData,
      links: cldData.links.map(l =>
        l.from_id === fromId && l.to_id === toId
          ? { ...l, link_type: l.link_type === 'reinforcing' ? 'balancing' : 'reinforcing' }
          : l
      ),
    });
    setIsSaved(false);
  };

  // ========================
  // RENDERING HELPERS
  // ========================

  const getNodeColor = (node: CLDNode, simValues?: { [key: string]: number }) => {
    if (simResult && simValues) {
      const impact = (simValues[node.factor_id] || 0) - (simResult.baseline[node.factor_id] || 0);
      if (Math.abs(impact) < 1) return '#94A3B8'; // gray = no change
      if (impact > 0) return '#22C55E'; // green = positive
      return '#EF4444'; // red = negative
    }
    return node.classification === 'primary' ? COLORS.primary : '#10B981';
  };

  const getNodeSize = (node: CLDNode) => 18 + node.centrality * 14;

  const getLinkColor = (link: CLDLink) =>
    link.link_type === 'reinforcing' ? '#3B82F6' : '#EF4444';

  const getSimImpactColor = (impact: number) => {
    if (Math.abs(impact) < 1) return '#94A3B8';
    if (impact > 10) return '#16A34A';
    if (impact > 0) return '#22C55E';
    if (impact < -10) return '#DC2626';
    return '#EF4444';
  };

  // ========================
  // RENDER DIAGRAM
  // ========================

  const renderDiagram = () => {
    if (!cldData) return null;
    const simValues = simResult && simViewStep >= 0 && simViewStep < simResult.timeline.length
      ? simResult.timeline[simViewStep].values
      : undefined;

    return (
      <View style={s.diagramContainer}>
        {/* Layout controls */}
        <View style={s.layoutRow}>
          {['circular', 'force', 'hierarchical'].map(lt => (
            <TouchableOpacity
              key={lt}
              style={[s.layoutBtn, layoutType === lt && s.layoutBtnActive]}
              onPress={() => changeLayout(lt)}
            >
              <Ionicons
                name={lt === 'circular' ? 'radio-button-on' : lt === 'force' ? 'git-merge' : 'git-branch'}
                size={12}
                color={layoutType === lt ? '#FFF' : COLORS.textMuted}
              />
              <Text style={[s.layoutBtnText, layoutType === lt && s.layoutBtnTextActive]}>
                {lt === 'circular' ? 'Circle' : lt === 'force' ? 'Force' : 'Hierarchy'}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Edit Toolbar */}
        {editMode && (
          <View style={s.editToolbar}>
            <TouchableOpacity
              style={[s.editToolBtn, addingLink && s.editToolBtnActive]}
              onPress={() => { setAddingLink(!addingLink); setLinkFromId(null); setSelectedNodeId(null); }}
            >
              <Ionicons name="git-merge" size={14} color={addingLink ? '#FFF' : COLORS.primary} />
              <Text style={[s.editToolText, addingLink && { color: '#FFF' }]}>
                {addingLink ? (linkFromId ? 'Tap Target' : 'Tap Source') : 'Add Link'}
              </Text>
            </TouchableOpacity>
            {selectedNodeId && (
              <>
                <TouchableOpacity style={s.editToolBtn} onPress={() => openNodeEdit(selectedNodeId)}>
                  <Ionicons name="settings-outline" size={14} color={COLORS.primary} />
                  <Text style={s.editToolText}>Properties</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[s.editToolBtn, { borderColor: COLORS.error }]}
                  onPress={() => removeNode(selectedNodeId)}
                >
                  <Ionicons name="trash" size={14} color={COLORS.error} />
                  <Text style={[s.editToolText, { color: COLORS.error }]}>Remove</Text>
                </TouchableOpacity>
              </>
            )}
          </View>
        )}

        {/* SVG Diagram */}
        <Svg width={DIAGRAM_SIZE} height={DIAGRAM_SIZE} viewBox={`0 0 ${DIAGRAM_SIZE} ${DIAGRAM_SIZE}`}>
          <Defs>
            <Marker id="arrowR" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
              <SvgPath d="M0,0 L0,6 L9,3 z" fill="#3B82F6" />
            </Marker>
            <Marker id="arrowB" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
              <SvgPath d="M0,0 L0,6 L9,3 z" fill="#EF4444" />
            </Marker>
          </Defs>

          {/* Links */}
          {cldData.links.map((link, idx) => {
            const fromNode = cldData.nodes.find(n => n.factor_id === link.from_id);
            const toNode = cldData.nodes.find(n => n.factor_id === link.to_id);
            if (!fromNode || !toNode) return null;
            const color = getLinkColor(link);
            const strokeWidth = 1 + link.strength * 0.3;
            const markerId = link.link_type === 'reinforcing' ? 'url(#arrowR)' : 'url(#arrowB)';
            const dx = toNode.x - fromNode.x;
            const dy = toNode.y - fromNode.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const toR = getNodeSize(toNode);
            const fromR = getNodeSize(fromNode);
            const endX = toNode.x - (dx / dist) * toR;
            const endY = toNode.y - (dy / dist) * toR;
            const startX = fromNode.x + (dx / dist) * fromR;
            const startY = fromNode.y + (dy / dist) * fromR;

            return (
              <Line
                key={`link-${idx}`}
                x1={startX} y1={startY}
                x2={endX} y2={endY}
                stroke={color}
                strokeWidth={strokeWidth}
                strokeDasharray={link.link_type === 'balancing' ? '6,3' : undefined}
                markerEnd={markerId}
                opacity={0.7}
              />
            );
          })}

          {/* Nodes */}
          {cldData.nodes.map((node) => {
            const r = getNodeSize(node);
            const color = getNodeColor(node, simValues);
            const isSelected = selectedNodeId === node.factor_id;
            return (
              <G key={node.factor_id}>
                {isSelected && (
                  <Circle cx={node.x} cy={node.y} r={r + 4} fill="none" stroke="#F59E0B" strokeWidth={3} />
                )}
                <Circle
                  cx={node.x} cy={node.y} r={r}
                  fill={color} opacity={node.locked ? 0.5 : 0.85}
                  stroke={node.locked ? '#F59E0B' : '#FFF'} strokeWidth={2}
                />
                <SvgText
                  x={node.x} y={node.y + r + 12}
                  textAnchor="middle" fontSize={9} fontWeight="600"
                  fill={COLORS.textPrimary}
                >
                  {node.name.length > 14 ? node.name.slice(0, 12) + '…' : node.name}
                </SvgText>
                <SvgText
                  x={node.x} y={node.y + 4}
                  textAnchor="middle" fontSize={10} fontWeight="bold" fill="#FFF"
                >
                  {simValues
                    ? Math.round(simValues[node.factor_id] || node.base_value)
                    : node.priority_rank}
                </SvgText>
              </G>
            );
          })}
        </Svg>

        {/* Node touch overlays */}
        {cldData.nodes.map((node) => {
          const r = getNodeSize(node);
          return (
            <TouchableOpacity
              key={`touch-${node.factor_id}`}
              style={{
                position: 'absolute',
                left: node.x - r + 8,
                top: node.y - r + (editMode ? 60 : 40),
                width: r * 2,
                height: r * 2,
                borderRadius: r,
              }}
              onPress={() => editMode ? handleNodeTap(node.factor_id) : openNodeEdit(node.factor_id)}
            />
          );
        })}

        {/* Legend */}
        <View style={s.legend}>
          <View style={s.legendItem}>
            <View style={[s.legendDot, { backgroundColor: COLORS.primary }]} />
            <Text style={s.legendText}>Primary</Text>
          </View>
          <View style={s.legendItem}>
            <View style={[s.legendDot, { backgroundColor: '#10B981' }]} />
            <Text style={s.legendText}>Secondary</Text>
          </View>
          <View style={s.legendItem}>
            <View style={[s.legendLine, { backgroundColor: '#3B82F6' }]} />
            <Text style={s.legendText}>Reinforcing</Text>
          </View>
          <View style={s.legendItem}>
            <View style={[s.legendLine, { backgroundColor: '#EF4444' }]} />
            <Text style={s.legendText}>Balancing</Text>
          </View>
          {simResult && (
            <>
              <View style={s.legendItem}>
                <View style={[s.legendDot, { backgroundColor: '#22C55E' }]} />
                <Text style={s.legendText}>+Impact</Text>
              </View>
              <View style={s.legendItem}>
                <View style={[s.legendDot, { backgroundColor: '#EF4444' }]} />
                <Text style={s.legendText}>-Impact</Text>
              </View>
            </>
          )}
        </View>

        {/* Loops */}
        {cldData.loops.length > 0 && (
          <View style={s.loopsSection}>
            <Text style={s.loopsTitle}>Feedback Loops</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
              {cldData.loops.map((loop, idx) => (
                <View key={idx} style={[s.loopBadge, loop.loop_type === 'reinforcing' ? s.loopR : s.loopB]}>
                  <Text style={[s.loopText, { color: loop.loop_type === 'reinforcing' ? '#3B82F6' : '#EF4444' }]}>
                    {loop.name}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Links list (edit mode) */}
        {editMode && cldData.links.length > 0 && (
          <View style={s.linkList}>
            <Text style={s.linkListTitle}>Links (tap to edit)</Text>
            {cldData.links.map((link, idx) => {
              const fromName = cldData.nodes.find(n => n.factor_id === link.from_id)?.name || '?';
              const toName = cldData.nodes.find(n => n.factor_id === link.to_id)?.name || '?';
              return (
                <View key={idx} style={s.linkItem}>
                  <TouchableOpacity style={{ flex: 1 }} onPress={() => openLinkEdit(link.from_id, link.to_id)}>
                    <Text style={s.linkItemText} numberOfLines={1}>
                      {fromName} → {toName} (S:{link.strength})
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[s.linkTypeBadge, { backgroundColor: link.link_type === 'reinforcing' ? '#DBEAFE' : '#FEE2E2' }]}
                    onPress={() => toggleLinkType(link.from_id, link.to_id)}
                  >
                    <Text style={{ fontSize: 10, fontWeight: '600', color: link.link_type === 'reinforcing' ? '#3B82F6' : '#EF4444' }}>
                      {link.link_type === 'reinforcing' ? 'R' : 'B'}
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => removeLink(link.from_id, link.to_id)}>
                    <Ionicons name="close-circle" size={18} color={COLORS.error} />
                  </TouchableOpacity>
                </View>
              );
            })}
          </View>
        )}
      </View>
    );
  };

  // ========================
  // RENDER ANALYSIS
  // ========================

  const renderAnalysis = () => {
    const sourceData = factorAnalysis.length > 0
      ? factorAnalysis
      : cldData?.nodes?.map(n => ({
          factor_id: n.factor_id,
          factor_name: n.name,
          centrality: n.centrality,
          classification: n.classification,
          priority_rank: n.priority_rank,
          gap_multiplier: n.gap_multiplier,
          base_value: n.base_value,
          reasoning: '',
        })) || [];

    return (
      <View style={s.analysisContainer}>
        {sourceData
          .sort((a: any, b: any) => a.priority_rank - b.priority_rank)
          .map((fa: any) => (
            <View key={fa.factor_id} style={s.analysisCard}>
              <View style={s.analysisHeader}>
                <View style={[s.rankCircle, { backgroundColor: fa.classification === 'primary' ? COLORS.primary : '#10B981' }]}>
                  <Text style={s.rankCircleText}>{fa.priority_rank}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={s.analysisName}>{fa.factor_name || fa.name}</Text>
                  <View style={s.analysisMetaRow}>
                    <View style={[s.classBadge, fa.classification === 'primary' ? s.classPrimary : s.classSecondary]}>
                      <Text style={s.classBadgeText}>{fa.classification}</Text>
                    </View>
                    <Text style={s.centralityText}>Centrality: {(fa.centrality * 100).toFixed(0)}%</Text>
                    <Text style={s.gapText}>Gap: {fa.gap_multiplier}x</Text>
                    <Text style={s.gapText}>Base: {Math.round(fa.base_value || 50)}</Text>
                  </View>
                </View>
              </View>
              {fa.reasoning ? <Text style={s.reasoningText}>{fa.reasoning}</Text> : null}
            </View>
          ))}
      </View>
    );
  };

  // ========================
  // RENDER SIMULATION
  // ========================

  const renderSimulation = () => {
    if (!cldData) return null;

    return (
      <View style={s.simContainer}>
        <Text style={s.simTitle}>What-If Simulation</Text>
        <Text style={s.simSubtitle}>
          Explore how changing one factor ripples through your decision system
        </Text>

        {/* Shock Factor Selection */}
        <Text style={s.simLabel}>Factor to Change</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.factorChipRow}>
          {cldData.nodes.map(node => (
            <TouchableOpacity
              key={node.factor_id}
              style={[s.factorChip, simShockFactorId === node.factor_id && s.factorChipActive]}
              onPress={() => setSimShockFactorId(node.factor_id)}
            >
              <Text style={[s.factorChipText, simShockFactorId === node.factor_id && s.factorChipTextActive]} numberOfLines={1}>
                {node.name}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Delta Slider */}
        <View style={s.sliderRow}>
          <Text style={s.simLabel}>Change Amount</Text>
          <Text style={[s.simValue, { color: simDelta >= 0 ? '#16A34A' : '#DC2626' }]}>
            {simDelta >= 0 ? '+' : ''}{simDelta.toFixed(0)}%
          </Text>
        </View>
        <Slider
          style={s.slider}
          minimumValue={-50}
          maximumValue={50}
          step={5}
          value={simDelta}
          onValueChange={setSimDelta}
          minimumTrackTintColor={simDelta >= 0 ? '#16A34A' : '#DC2626'}
          maximumTrackTintColor="#E5E7EB"
          thumbTintColor={COLORS.primary}
        />

        {/* Time Steps */}
        <View style={s.sliderRow}>
          <Text style={s.simLabel}>Time Steps</Text>
          <Text style={s.simValue}>{simSteps}</Text>
        </View>
        <Slider
          style={s.slider}
          minimumValue={1}
          maximumValue={15}
          step={1}
          value={simSteps}
          onValueChange={setSimSteps}
          minimumTrackTintColor={COLORS.primary}
          maximumTrackTintColor="#E5E7EB"
          thumbTintColor={COLORS.primary}
        />

        {/* Dampening */}
        <View style={s.sliderRow}>
          <Text style={s.simLabel}>Dampening</Text>
          <Text style={s.simValue}>{(simDampening * 100).toFixed(0)}%</Text>
        </View>
        <Slider
          style={s.slider}
          minimumValue={0.1}
          maximumValue={1.0}
          step={0.1}
          value={simDampening}
          onValueChange={setSimDampening}
          minimumTrackTintColor={COLORS.primary}
          maximumTrackTintColor="#E5E7EB"
          thumbTintColor={COLORS.primary}
        />

        {/* Run Button */}
        <TouchableOpacity style={s.simRunBtn} onPress={runSimulation} disabled={simLoading}>
          {simLoading ? (
            <ActivityIndicator size="small" color="#FFF" />
          ) : (
            <>
              <Ionicons name="play-circle" size={20} color="#FFF" />
              <Text style={s.simRunBtnText}>Run Simulation</Text>
            </>
          )}
        </TouchableOpacity>

        {/* Simulation Results */}
        {simResult && (
          <View style={s.simResults}>
            {/* Stability Badge */}
            <View style={[s.stabilityBadge, {
              backgroundColor: simResult.stability === 'stable' ? '#DCFCE7' :
                simResult.stability === 'oscillating' ? '#FEF3C7' : '#FEE2E2',
            }]}>
              <Ionicons
                name={simResult.stability === 'stable' ? 'checkmark-circle' :
                  simResult.stability === 'oscillating' ? 'swap-horizontal' : 'warning'}
                size={16}
                color={simResult.stability === 'stable' ? '#16A34A' :
                  simResult.stability === 'oscillating' ? '#D97706' : '#DC2626'}
              />
              <Text style={[s.stabilityText, {
                color: simResult.stability === 'stable' ? '#16A34A' :
                  simResult.stability === 'oscillating' ? '#D97706' : '#DC2626',
              }]}>
                System: {simResult.stability.charAt(0).toUpperCase() + simResult.stability.slice(1)}
              </Text>
            </View>

            {/* Time Step Scrubber */}
            <View style={s.sliderRow}>
              <Text style={s.simLabel}>Time Step</Text>
              <Text style={s.simValue}>
                {simViewStep}/{simResult.timeline.length - 1}
              </Text>
            </View>
            <Slider
              style={s.slider}
              minimumValue={0}
              maximumValue={simResult.timeline.length - 1}
              step={1}
              value={simViewStep}
              onValueChange={(v: number) => setSimViewStep(Math.round(v))}
              minimumTrackTintColor={COLORS.primary}
              maximumTrackTintColor="#E5E7EB"
              thumbTintColor={COLORS.primary}
            />

            {/* Impact Table */}
            <Text style={s.simSectionTitle}>Impact Analysis</Text>
            {Object.entries(simResult.total_impact)
              .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
              .map(([factorId, impact]) => {
                const node = cldData?.nodes.find(n => n.factor_id === factorId);
                const isShock = factorId === simShockFactorId;
                const currentVal = simResult.timeline[simViewStep]?.values[factorId] || 0;
                const baseVal = simResult.baseline[factorId] || 50;
                return (
                  <View key={factorId} style={[s.impactRow, isShock && { backgroundColor: '#F5F3FF' }]}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.impactName} numberOfLines={1}>
                        {isShock ? '⚡ ' : ''}{node?.name || factorId}
                      </Text>
                      <View style={s.impactBarBg}>
                        <View style={[
                          s.impactBar,
                          {
                            width: `${Math.min(100, Math.abs(currentVal))}%`,
                            backgroundColor: getSimImpactColor(impact),
                          },
                        ]} />
                      </View>
                    </View>
                    <View style={s.impactValues}>
                      <Text style={s.impactBase}>{Math.round(baseVal)}</Text>
                      <Ionicons name="arrow-forward" size={10} color={COLORS.textMuted} />
                      <Text style={[s.impactFinal, { color: getSimImpactColor(impact) }]}>
                        {Math.round(currentVal)}
                      </Text>
                      <Text style={[s.impactDelta, { color: getSimImpactColor(impact) }]}>
                        ({impact >= 0 ? '+' : ''}{impact.toFixed(1)})
                      </Text>
                    </View>
                  </View>
                );
              })}
          </View>
        )}
      </View>
    );
  };

  // ========================
  // NODE EDIT MODAL
  // ========================

  const renderNodeEditModal = () => (
    <Modal visible={nodeEditVisible} transparent animationType="slide">
      <View style={s.modalOverlay}>
        <View style={s.modalContent}>
          <View style={s.modalHeader}>
            <Text style={s.modalTitle}>Node Properties</Text>
            <TouchableOpacity onPress={() => setNodeEditVisible(false)}>
              <Ionicons name="close" size={22} color={COLORS.textPrimary} />
            </TouchableOpacity>
          </View>
          {editingNode && (
            <ScrollView style={s.modalBody}>
              <Text style={s.modalLabel}>Name</Text>
              <Text style={s.modalValue}>{editingNode.name}</Text>

              <Text style={s.modalLabel}>Classification</Text>
              <View style={s.modalBtnRow}>
                {(['primary', 'secondary'] as const).map(cls => (
                  <TouchableOpacity
                    key={cls}
                    style={[s.modalBtn, editingNode.classification === cls && s.modalBtnActive]}
                    onPress={() => setEditingNode({ ...editingNode, classification: cls })}
                  >
                    <Text style={[s.modalBtnText, editingNode.classification === cls && { color: '#FFF' }]}>
                      {cls}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={s.modalLabel}>Base Value (for Simulation): {Math.round(editingNode.base_value)}</Text>
              <Slider
                style={s.slider}
                minimumValue={0}
                maximumValue={100}
                step={1}
                value={editingNode.base_value}
                onValueChange={(v: number) => setEditingNode({ ...editingNode, base_value: v })}
                minimumTrackTintColor={COLORS.primary}
                maximumTrackTintColor="#E5E7EB"
                thumbTintColor={COLORS.primary}
              />

              <Text style={s.modalLabel}>Centrality: {(editingNode.centrality * 100).toFixed(0)}%</Text>
              <Slider
                style={s.slider}
                minimumValue={0}
                maximumValue={1}
                step={0.05}
                value={editingNode.centrality}
                onValueChange={(v: number) => setEditingNode({ ...editingNode, centrality: v })}
                minimumTrackTintColor={COLORS.primary}
                maximumTrackTintColor="#E5E7EB"
                thumbTintColor={COLORS.primary}
              />

              <Text style={s.modalLabel}>Gap Multiplier: {editingNode.gap_multiplier.toFixed(1)}x</Text>
              <Slider
                style={s.slider}
                minimumValue={0.5}
                maximumValue={3}
                step={0.25}
                value={editingNode.gap_multiplier}
                onValueChange={(v: number) => setEditingNode({ ...editingNode, gap_multiplier: v })}
                minimumTrackTintColor={COLORS.primary}
                maximumTrackTintColor="#E5E7EB"
                thumbTintColor={COLORS.primary}
              />

              <View style={s.lockRow}>
                <Text style={s.modalLabel}>Lock (exclude from simulation)</Text>
                <TouchableOpacity
                  style={[s.lockToggle, editingNode.locked && s.lockToggleActive]}
                  onPress={() => setEditingNode({ ...editingNode, locked: !editingNode.locked })}
                >
                  <Ionicons name={editingNode.locked ? 'lock-closed' : 'lock-open'} size={16} color={editingNode.locked ? '#FFF' : COLORS.textMuted} />
                </TouchableOpacity>
              </View>

              <TouchableOpacity style={s.modalSaveBtn} onPress={saveNodeEdit}>
                <Text style={s.modalSaveBtnText}>Save Changes</Text>
              </TouchableOpacity>
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );

  // ========================
  // LINK EDIT MODAL
  // ========================

  const renderLinkEditModal = () => (
    <Modal visible={linkEditVisible} transparent animationType="slide">
      <View style={s.modalOverlay}>
        <View style={s.modalContent}>
          <View style={s.modalHeader}>
            <Text style={s.modalTitle}>Link Properties</Text>
            <TouchableOpacity onPress={() => setLinkEditVisible(false)}>
              <Ionicons name="close" size={22} color={COLORS.textPrimary} />
            </TouchableOpacity>
          </View>
          {editingLink && (
            <ScrollView style={s.modalBody}>
              <Text style={s.modalLabel}>
                {cldData?.nodes.find(n => n.factor_id === editingLink.from_id)?.name || '?'}
                {' → '}
                {cldData?.nodes.find(n => n.factor_id === editingLink.to_id)?.name || '?'}
              </Text>

              <Text style={s.modalLabel}>Type</Text>
              <View style={s.modalBtnRow}>
                {(['reinforcing', 'balancing'] as const).map(lt => (
                  <TouchableOpacity
                    key={lt}
                    style={[s.modalBtn, editingLink.link_type === lt && s.modalBtnActive, {
                      borderColor: lt === 'reinforcing' ? '#3B82F6' : '#EF4444',
                    }]}
                    onPress={() => setEditingLink({ ...editingLink, link_type: lt })}
                  >
                    <Text style={[s.modalBtnText, editingLink.link_type === lt && { color: '#FFF' }]}>
                      {lt === 'reinforcing' ? 'R - Reinforcing' : 'B - Balancing'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={s.modalLabel}>Strength: {editingLink.strength.toFixed(1)}</Text>
              <Slider
                style={s.slider}
                minimumValue={1}
                maximumValue={10}
                step={0.5}
                value={editingLink.strength}
                onValueChange={(v: number) => setEditingLink({ ...editingLink, strength: v })}
                minimumTrackTintColor={COLORS.primary}
                maximumTrackTintColor="#E5E7EB"
                thumbTintColor={COLORS.primary}
              />

              <Text style={s.modalLabel}>Time Delay: {editingLink.delay} steps</Text>
              <Slider
                style={s.slider}
                minimumValue={0}
                maximumValue={5}
                step={1}
                value={editingLink.delay}
                onValueChange={(v: number) => setEditingLink({ ...editingLink, delay: v })}
                minimumTrackTintColor={COLORS.primary}
                maximumTrackTintColor="#E5E7EB"
                thumbTintColor={COLORS.primary}
              />

              <Text style={s.modalLabel}>Description</Text>
              <TextInput
                style={s.modalInput}
                value={editingLink.description}
                onChangeText={t => setEditingLink({ ...editingLink, description: t })}
                placeholder="Describe this relationship..."
                placeholderTextColor={COLORS.textMuted}
                multiline
              />

              <TouchableOpacity style={s.modalSaveBtn} onPress={saveLinkEdit}>
                <Text style={s.modalSaveBtnText}>Save Changes</Text>
              </TouchableOpacity>
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );

  // ========================
  // MAIN RENDER
  // ========================

  return (
    <View style={s.overlay}>
      <View style={s.container}>
        {/* Header */}
        <View style={s.header}>
          <View style={{ flex: 1 }}>
            <Text style={s.title}>CLD Engine</Text>
            <Text style={s.subtitle}>Causal Loop Diagram · Systems Thinking</Text>
          </View>
          <View style={s.headerActions}>
            {cldData && (
              <>
                <TouchableOpacity
                  style={[s.headerBtn, editMode && { backgroundColor: '#FEF3C7' }]}
                  onPress={() => { setEditMode(!editMode); setSelectedNodeId(null); setAddingLink(false); }}
                >
                  <Ionicons name="create-outline" size={16} color={editMode ? '#D97706' : COLORS.textMuted} />
                </TouchableOpacity>
                <TouchableOpacity
                  style={[s.headerBtn, { backgroundColor: isSaved ? '#DCFCE7' : '#FEE2E2' }]}
                  onPress={saveCLD}
                  disabled={saving}
                >
                  {saving ? (
                    <ActivityIndicator size="small" color={COLORS.primary} />
                  ) : (
                    <Ionicons
                      name={isSaved ? 'checkmark-circle' : 'save-outline'}
                      size={16}
                      color={isSaved ? '#16A34A' : '#DC2626'}
                    />
                  )}
                </TouchableOpacity>
              </>
            )}
            <TouchableOpacity onPress={onClose} style={s.closeBtn}>
              <Ionicons name="close" size={22} color={COLORS.textPrimary} />
            </TouchableOpacity>
          </View>
        </View>

        {/* Tabs */}
        {cldData && (
          <View style={s.tabRow}>
            {(['diagram', 'analysis', 'simulate'] as TabType[]).map(tab => (
              <TouchableOpacity
                key={tab}
                style={[s.tab, activeTab === tab && s.tabActive]}
                onPress={() => setActiveTab(tab)}
              >
                <Ionicons
                  name={tab === 'diagram' ? 'git-network-outline' : tab === 'analysis' ? 'list-outline' : 'flask-outline'}
                  size={14}
                  color={activeTab === tab ? '#FFF' : COLORS.textMuted}
                />
                <Text style={[s.tabText, activeTab === tab && s.tabTextActive]}>
                  {tab === 'diagram' ? 'Diagram' : tab === 'analysis' ? 'Analysis' : 'Simulate'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <ScrollView contentContainerStyle={s.body}>
          {/* Generate Button */}
          {!cldData && !loading && (
            <TouchableOpacity style={s.generateBtn} onPress={generateCLD}>
              <Ionicons name="git-network-outline" size={28} color="#FFF" />
              <Text style={s.generateBtnText}>Generate CLD from Factors</Text>
              <Text style={s.generateBtnSub}>
                AI will analyze causal relationships between your {factors.filter(f => !f.parent_id).length} factors
              </Text>
            </TouchableOpacity>
          )}

          {loading && (
            <View style={s.loadingBox}>
              <ActivityIndicator size="large" color={COLORS.primary} />
              <Text style={s.loadingText}>Analyzing causal relationships...</Text>
              <Text style={s.loadingSubtext}>Identifying loops, centrality & influence</Text>
            </View>
          )}

          {/* Content by tab */}
          {cldData && !loading && (
            <>
              {activeTab === 'diagram' && renderDiagram()}
              {activeTab === 'analysis' && renderAnalysis()}
              {activeTab === 'simulate' && renderSimulation()}

              {/* Action Buttons */}
              <View style={s.actionRow}>
                <TouchableOpacity style={s.applyBtn} onPress={applyToSteps}>
                  <Ionicons name="checkmark-circle" size={18} color="#FFF" />
                  <Text style={s.applyBtnText}>Apply to Steps 3-5</Text>
                </TouchableOpacity>
                <TouchableOpacity style={s.regenBtn} onPress={generateCLD}>
                  <Ionicons name="refresh" size={16} color={COLORS.primary} />
                  <Text style={s.regenBtnText}>Regenerate</Text>
                </TouchableOpacity>
              </View>
            </>
          )}
        </ScrollView>
      </View>

      {/* Modals */}
      {renderNodeEditModal()}
      {renderLinkEditModal()}
    </View>
  );
}

// ========================
// STYLES
// ========================

const s = StyleSheet.create({
  overlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000, justifyContent: 'flex-end' },
  container: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '95%', minHeight: '60%' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 14, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  title: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  headerBtn: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F1F5F9' },
  closeBtn: { padding: 4 },
  body: { padding: 14, paddingBottom: 32 },

  // Tabs
  tabRow: { flexDirection: 'row', gap: 6, paddingHorizontal: 14, paddingVertical: 8 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8, borderRadius: 10, backgroundColor: '#F1F5F9' },
  tabActive: { backgroundColor: COLORS.primary },
  tabText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },
  tabTextActive: { color: '#FFF' },

  // Generate
  generateBtn: { backgroundColor: COLORS.primary, borderRadius: 16, padding: 24, alignItems: 'center', gap: 8 },
  generateBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  generateBtnSub: { fontSize: 12, color: 'rgba(255,255,255,0.8)', textAlign: 'center' },
  loadingBox: { alignItems: 'center', paddingVertical: 40, gap: 12 },
  loadingText: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  loadingSubtext: { fontSize: 12, color: COLORS.textMuted },

  // Diagram
  diagramContainer: { alignItems: 'center', backgroundColor: '#FAFAFA', borderRadius: 12, padding: 8, marginBottom: 12 },
  layoutRow: { flexDirection: 'row', gap: 6, marginBottom: 8 },
  layoutBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, backgroundColor: '#F1F5F9' },
  layoutBtnActive: { backgroundColor: COLORS.primary },
  layoutBtnText: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted },
  layoutBtnTextActive: { color: '#FFF' },

  // Legend
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 8, justifyContent: 'center' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendLine: { width: 18, height: 3, borderRadius: 1 },
  legendText: { fontSize: 10, color: COLORS.textMuted },

  // Loops
  loopsSection: { marginTop: 10, gap: 4 },
  loopsTitle: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary, textAlign: 'center', marginBottom: 4 },
  loopBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10 },
  loopR: { backgroundColor: '#DBEAFE' },
  loopB: { backgroundColor: '#FEE2E2' },
  loopText: { fontSize: 11, fontWeight: '600' },

  // Edit
  editToolbar: { flexDirection: 'row', gap: 6, marginBottom: 8, flexWrap: 'wrap' },
  editToolBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, borderWidth: 1, borderColor: COLORS.primary, backgroundColor: '#FFF' },
  editToolBtnActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  editToolText: { fontSize: 11, fontWeight: '600', color: COLORS.primary },
  linkList: { marginTop: 10, gap: 4, width: '100%' },
  linkListTitle: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  linkItem: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 5, paddingHorizontal: 8, backgroundColor: '#F8FAFC', borderRadius: 8 },
  linkItemText: { flex: 1, fontSize: 11, color: COLORS.textSecondary },
  linkTypeBadge: { width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },

  // Analysis
  analysisContainer: { gap: 8, marginBottom: 12 },
  analysisCard: { backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12 },
  analysisHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 6 },
  rankCircle: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  rankCircleText: { fontSize: 13, fontWeight: '700', color: '#FFF' },
  analysisName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  analysisMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
  classBadge: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 6 },
  classPrimary: { backgroundColor: '#EDE9FE' },
  classSecondary: { backgroundColor: '#D1FAE5' },
  classBadgeText: { fontSize: 10, fontWeight: '600', color: COLORS.textPrimary },
  centralityText: { fontSize: 10, color: COLORS.textMuted },
  gapText: { fontSize: 10, color: COLORS.textMuted },
  reasoningText: { fontSize: 11, color: COLORS.textSecondary, lineHeight: 16 },

  // Simulation
  simContainer: { gap: 8, marginBottom: 12 },
  simTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  simSubtitle: { fontSize: 12, color: COLORS.textMuted, marginBottom: 4 },
  simLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  simValue: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  sliderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 },
  slider: { width: '100%', height: 32 },
  factorChipRow: { maxHeight: 40, marginBottom: 4 },
  factorChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: '#F1F5F9', marginRight: 6 },
  factorChipActive: { backgroundColor: COLORS.primary },
  factorChipText: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  factorChipTextActive: { color: '#FFF' },
  simRunBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#3B82F6', borderRadius: 12, paddingVertical: 12, marginTop: 8 },
  simRunBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },

  // Simulation Results
  simResults: { marginTop: 12, gap: 8 },
  stabilityBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, alignSelf: 'flex-start' },
  stabilityText: { fontSize: 13, fontWeight: '700' },
  simSectionTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginTop: 4 },
  impactRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, paddingHorizontal: 8, backgroundColor: '#F8FAFC', borderRadius: 8 },
  impactName: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 2 },
  impactBarBg: { height: 4, backgroundColor: '#E5E7EB', borderRadius: 2, overflow: 'hidden' },
  impactBar: { height: 4, borderRadius: 2 },
  impactValues: { flexDirection: 'row', alignItems: 'center', gap: 3, minWidth: 100 },
  impactBase: { fontSize: 11, color: COLORS.textMuted },
  impactFinal: { fontSize: 12, fontWeight: '700' },
  impactDelta: { fontSize: 10, fontWeight: '600' },

  // Actions
  actionRow: { flexDirection: 'row', gap: 8, marginTop: 8, alignItems: 'center' },
  applyBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#16A34A', borderRadius: 12, paddingVertical: 12 },
  applyBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  regenBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingVertical: 10, paddingHorizontal: 12 },
  regenBtnText: { fontSize: 12, fontWeight: '600', color: COLORS.primary },

  // Modals
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', paddingHorizontal: 20 },
  modalContent: { backgroundColor: '#FFF', borderRadius: 16, maxHeight: '80%' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 14, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  modalTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  modalBody: { padding: 14 },
  modalLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10, marginBottom: 4 },
  modalValue: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  modalBtnRow: { flexDirection: 'row', gap: 8 },
  modalBtn: { flex: 1, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  modalBtnActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  modalBtnText: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  modalInput: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, padding: 10, fontSize: 13, color: COLORS.textPrimary, minHeight: 60, textAlignVertical: 'top' },
  modalSaveBtn: { backgroundColor: COLORS.primary, borderRadius: 10, paddingVertical: 12, alignItems: 'center', marginTop: 16, marginBottom: 12 },
  modalSaveBtnText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  lockRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 },
  lockToggle: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center' },
  lockToggleActive: { backgroundColor: '#F59E0B' },
});
