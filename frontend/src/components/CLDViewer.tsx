import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
  ScrollView,
  Dimensions,
} from 'react-native';
import Svg, { Circle, Line, Defs, Marker, Path as SvgPath, Text as SvgText, G } from 'react-native-svg';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { COLORS } from '../constants/colors';
import type { Factor } from '../types/decision';

interface CLDNode {
  factor_id: string;
  name: string;
  x: number;
  y: number;
  centrality: number;
  classification: 'primary' | 'secondary';
  priority_rank: number;
  gap_multiplier: number;
}

interface CLDLink {
  from_id: string;
  to_id: string;
  type: 'reinforcing' | 'balancing';
  strength: number;
  description?: string;
}

interface CLDLoop {
  name: string;
  type: 'reinforcing' | 'balancing';
  factor_ids: string[];
}

interface FactorAnalysis {
  factor_id: string;
  factor_name: string;
  centrality: number;
  classification: 'primary' | 'secondary';
  priority_rank: number;
  gap_multiplier: number;
  reasoning: string;
}

interface CLDData {
  nodes: CLDNode[];
  links: CLDLink[];
  loops: CLDLoop[];
}

interface CLDViewerProps {
  factors: Factor[];
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

const DIAGRAM_SIZE = 380;

export default function CLDViewer({
  factors,
  decisionTitle,
  decisionContext,
  lifeArea,
  decisionType,
  onApplyResults,
  visible,
  onClose,
}: CLDViewerProps) {
  const [loading, setLoading] = useState(false);
  const [cldData, setCldData] = useState<CLDData | null>(null);
  const [factorAnalysis, setFactorAnalysis] = useState<FactorAnalysis[]>([]);
  const [showDiagram, setShowDiagram] = useState(true);
  // Edit mode state
  const [editMode, setEditMode] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [addingLink, setAddingLink] = useState(false);
  const [linkFromId, setLinkFromId] = useState<string | null>(null);

  if (!visible) return null;

  const generateCLD = async () => {
    if (factors.filter(f => !f.parent_id).length < 2) {
      Alert.alert('Need More Factors', 'At least 2 top-level factors are required for CLD analysis.');
      return;
    }
    setLoading(true);
    try {
      const token = await AsyncStorage.getItem('session_token');
      const baseUrl = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';
      const resp = await fetch(`${baseUrl}/api/cld/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          decision_title: decisionTitle,
          decision_context: decisionContext,
          life_area: lifeArea || '',
          decision_type: decisionType || '',
          factors: factors.filter(f => !f.parent_id).map(f => ({ id: f.id, name: f.name })),
        }),
      });
      const data = await resp.json();
      if (data.cld) {
        // Scale node positions to fit diagram
        const nodes = (data.cld.nodes || []).map((n: CLDNode) => ({
          ...n,
          x: Math.max(30, Math.min(DIAGRAM_SIZE - 30, n.x * (DIAGRAM_SIZE / 400))),
          y: Math.max(30, Math.min(DIAGRAM_SIZE - 30, n.y * (DIAGRAM_SIZE / 400))),
        }));
        setCldData({ nodes, links: data.cld.links || [], loops: data.cld.loops || [] });
        setFactorAnalysis(data.factor_analysis || []);
      } else {
        Alert.alert('Error', data.detail || 'CLD generation failed');
      }
    } catch (err) {
      Alert.alert('Error', 'Failed to generate CLD');
    } finally {
      setLoading(false);
    }
  };

  const applyToSteps = () => {
    if (!factorAnalysis.length) return;
    const classifications: { [key: string]: 'primary' | 'secondary' } = {};
    const priorities: { factorId: string; order: number }[] = [];
    const gapMultipliers: { [key: string]: number } = {};

    const sorted = [...factorAnalysis].sort((a, b) => a.priority_rank - b.priority_rank);
    sorted.forEach((fa, idx) => {
      classifications[fa.factor_id] = fa.classification;
      priorities.push({ factorId: fa.factor_id, order: idx });
      gapMultipliers[fa.factor_id] = fa.gap_multiplier;
    });

    onApplyResults({ classifications, priorities, gapMultipliers });
    Alert.alert('Applied', 'CLD results applied to Steps 3-5. You can review and override.');
    onClose();
  };

  const getNodeColor = (node: CLDNode) =>
    node.classification === 'primary' ? COLORS.primary : '#10B981';

  const getNodeSize = (node: CLDNode) =>
    18 + node.centrality * 14;

  const getLinkColor = (link: CLDLink) =>
    link.type === 'reinforcing' ? '#3B82F6' : '#EF4444';

  // Edit functions
  const handleNodeTap = (nodeId: string) => {
    if (!editMode) return;
    if (addingLink) {
      if (!linkFromId) {
        setLinkFromId(nodeId);
      } else if (linkFromId !== nodeId) {
        // Create new link
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
                type: 'reinforcing',
                strength: 5,
                description: 'Manual link',
              }],
            });
          }
        }
        setLinkFromId(null);
        setAddingLink(false);
      }
    } else {
      setSelectedNodeId(selectedNodeId === nodeId ? null : nodeId);
    }
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
  };

  const toggleLinkType = (fromId: string, toId: string) => {
    if (!cldData) return;
    setCldData({
      ...cldData,
      links: cldData.links.map(l =>
        l.from_id === fromId && l.to_id === toId
          ? { ...l, type: l.type === 'reinforcing' ? 'balancing' : 'reinforcing' }
          : l
      ),
    });
  };

  return (
    <View style={styles.overlay}>
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>Causal Loop Diagram</Text>
            <Text style={styles.subtitle}>Systems Thinking Analysis</Text>
          </View>
          <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
            <Ionicons name="close" size={24} color={COLORS.textPrimary} />
          </TouchableOpacity>
        </View>

        <ScrollView contentContainerStyle={styles.body}>
          {/* Generate Button */}
          {!cldData && !loading && (
            <TouchableOpacity style={styles.generateBtn} onPress={generateCLD}>
              <Ionicons name="git-network-outline" size={24} color="#FFF" />
              <Text style={styles.generateBtnText}>Generate CLD from Factors</Text>
              <Text style={styles.generateBtnSub}>AI will analyze causal relationships between your {factors.filter(f => !f.parent_id).length} factors</Text>
            </TouchableOpacity>
          )}

          {loading && (
            <View style={styles.loadingBox}>
              <ActivityIndicator size="large" color={COLORS.primary} />
              <Text style={styles.loadingText}>Analyzing causal relationships...</Text>
              <Text style={styles.loadingSubtext}>Identifying loops, centrality & influence</Text>
            </View>
          )}

          {/* CLD Diagram */}
          {cldData && (
            <>
              {/* Tab toggle */}
              <View style={styles.tabRow}>
                <TouchableOpacity
                  style={[styles.tab, showDiagram && styles.tabActive]}
                  onPress={() => setShowDiagram(true)}
                >
                  <Ionicons name="git-network-outline" size={16} color={showDiagram ? '#FFF' : COLORS.textMuted} />
                  <Text style={[styles.tabText, showDiagram && styles.tabTextActive]}>Diagram</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.tab, !showDiagram && styles.tabActive]}
                  onPress={() => setShowDiagram(false)}
                >
                  <Ionicons name="list-outline" size={16} color={!showDiagram ? '#FFF' : COLORS.textMuted} />
                  <Text style={[styles.tabText, !showDiagram && styles.tabTextActive]}>Analysis</Text>
                </TouchableOpacity>
                {showDiagram && (
                  <TouchableOpacity
                    style={[styles.tab, editMode && { backgroundColor: '#F59E0B' }]}
                    onPress={() => { setEditMode(!editMode); setSelectedNodeId(null); setAddingLink(false); setLinkFromId(null); }}
                  >
                    <Ionicons name="create-outline" size={16} color={editMode ? '#FFF' : COLORS.textMuted} />
                    <Text style={[styles.tabText, editMode && { color: '#FFF' }]}>Edit</Text>
                  </TouchableOpacity>
                )}
              </View>

              {showDiagram ? (
                <View style={styles.diagramContainer}>
                  {/* Edit Toolbar */}
                  {editMode && (
                    <View style={styles.editToolbar}>
                      <TouchableOpacity
                        style={[styles.editToolBtn, addingLink && styles.editToolBtnActive]}
                        onPress={() => { setAddingLink(!addingLink); setLinkFromId(null); setSelectedNodeId(null); }}
                      >
                        <Ionicons name="git-merge" size={16} color={addingLink ? '#FFF' : COLORS.primary} />
                        <Text style={[styles.editToolText, addingLink && { color: '#FFF' }]}>
                          {addingLink ? (linkFromId ? 'Tap Target Node' : 'Tap Source Node') : 'Add Link'}
                        </Text>
                      </TouchableOpacity>
                      {selectedNodeId && (
                        <>
                          <TouchableOpacity
                            style={[styles.editToolBtn, { borderColor: COLORS.error }]}
                            onPress={() => removeNode(selectedNodeId)}
                          >
                            <Ionicons name="trash" size={16} color={COLORS.error} />
                            <Text style={[styles.editToolText, { color: COLORS.error }]}>Remove Node</Text>
                          </TouchableOpacity>
                        </>
                      )}
                    </View>
                  )}

                  {addingLink && linkFromId && (
                    <Text style={styles.editHint}>
                      Now tap the destination node to create a link
                    </Text>
                  )}

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
                      const strokeWidth = 1 + link.strength * 0.5;
                      const markerId = link.type === 'reinforcing' ? 'url(#arrowR)' : 'url(#arrowB)';
                      // Offset end point to not overlap circle
                      const dx = toNode.x - fromNode.x;
                      const dy = toNode.y - fromNode.y;
                      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                      const toR = getNodeSize(toNode);
                      const endX = toNode.x - (dx / dist) * toR;
                      const endY = toNode.y - (dy / dist) * toR;
                      const fromR = getNodeSize(fromNode);
                      const startX = fromNode.x + (dx / dist) * fromR;
                      const startY = fromNode.y + (dy / dist) * fromR;

                      return (
                        <Line
                          key={`link-${idx}`}
                          x1={startX} y1={startY}
                          x2={endX} y2={endY}
                          stroke={color}
                          strokeWidth={strokeWidth}
                          strokeDasharray={link.type === 'balancing' ? '6,3' : undefined}
                          markerEnd={markerId}
                          opacity={0.7}
                        />
                      );
                    })}

                    {/* Nodes */}
                    {cldData.nodes.map((node) => {
                      const r = getNodeSize(node);
                      const color = getNodeColor(node);
                      return (
                        <G key={node.factor_id}>
                          <Circle
                            cx={node.x} cy={node.y} r={r}
                            fill={color} opacity={0.85}
                            stroke="#FFF" strokeWidth={2}
                          />
                          <SvgText
                            x={node.x} y={node.y + r + 12}
                            textAnchor="middle"
                            fontSize={9}
                            fontWeight="600"
                            fill={COLORS.textPrimary}
                          >
                            {node.name.length > 14 ? node.name.slice(0, 12) + '…' : node.name}
                          </SvgText>
                          <SvgText
                            x={node.x} y={node.y + 4}
                            textAnchor="middle"
                            fontSize={10}
                            fontWeight="bold"
                            fill="#FFF"
                          >
                            {node.priority_rank}
                          </SvgText>
                        </G>
                      );
                    })}
                  </Svg>

                  {/* Legend */}
                  <View style={styles.legend}>
                    <View style={styles.legendItem}>
                      <View style={[styles.legendDot, { backgroundColor: COLORS.primary }]} />
                      <Text style={styles.legendText}>Primary</Text>
                    </View>
                    <View style={styles.legendItem}>
                      <View style={[styles.legendDot, { backgroundColor: '#10B981' }]} />
                      <Text style={styles.legendText}>Secondary</Text>
                    </View>
                    <View style={styles.legendItem}>
                      <View style={[styles.legendLine, { backgroundColor: '#3B82F6' }]} />
                      <Text style={styles.legendText}>Reinforcing</Text>
                    </View>
                    <View style={styles.legendItem}>
                      <View style={[styles.legendLine, { backgroundColor: '#EF4444', borderStyle: 'dashed' }]} />
                      <Text style={styles.legendText}>Balancing</Text>
                    </View>
                  </View>

                  {/* Node touch overlay */}
                  {editMode && cldData.nodes.map((node) => {
                    const r = getNodeSize(node);
                    return (
                      <TouchableOpacity
                        key={`touch-${node.factor_id}`}
                        style={{
                          position: 'absolute',
                          left: node.x - r + 8,
                          top: node.y - r + 8,
                          width: r * 2,
                          height: r * 2,
                          borderRadius: r,
                          borderWidth: selectedNodeId === node.factor_id ? 3 : 0,
                          borderColor: '#F59E0B',
                        }}
                        onPress={() => handleNodeTap(node.factor_id)}
                      />
                    );
                  })}

                  {/* Edit mode link list */}
                  {editMode && cldData.links.length > 0 && (
                    <View style={styles.linkList}>
                      <Text style={styles.linkListTitle}>Links (tap to edit)</Text>
                      {cldData.links.map((link, idx) => {
                        const fromName = cldData.nodes.find(n => n.factor_id === link.from_id)?.name || '?';
                        const toName = cldData.nodes.find(n => n.factor_id === link.to_id)?.name || '?';
                        return (
                          <View key={idx} style={styles.linkItem}>
                            <Text style={styles.linkItemText} numberOfLines={1}>
                              {fromName} → {toName}
                            </Text>
                            <TouchableOpacity
                              style={[styles.linkTypeBadge, { backgroundColor: link.type === 'reinforcing' ? '#DBEAFE' : '#FEE2E2' }]}
                              onPress={() => toggleLinkType(link.from_id, link.to_id)}
                            >
                              <Text style={{ fontSize: 10, fontWeight: '600', color: link.type === 'reinforcing' ? '#3B82F6' : '#EF4444' }}>
                                {link.type === 'reinforcing' ? 'R' : 'B'}
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

                  {/* Loops */}
                  {cldData.loops.length > 0 && (
                    <View style={styles.loopsSection}>
                      <Text style={styles.loopsTitle}>Feedback Loops</Text>
                      {cldData.loops.map((loop, idx) => (
                        <View key={idx} style={[styles.loopBadge, loop.type === 'reinforcing' ? styles.loopR : styles.loopB]}>
                          <Text style={[styles.loopText, { color: loop.type === 'reinforcing' ? '#3B82F6' : '#EF4444' }]}>
                            {loop.name}
                          </Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>
              ) : (
                /* Analysis View */
                <View style={styles.analysisContainer}>
                  {factorAnalysis
                    .sort((a, b) => a.priority_rank - b.priority_rank)
                    .map((fa) => (
                      <View key={fa.factor_id} style={styles.analysisCard}>
                        <View style={styles.analysisHeader}>
                          <View style={[styles.rankCircle, { backgroundColor: fa.classification === 'primary' ? COLORS.primary : '#10B981' }]}>
                            <Text style={styles.rankCircleText}>{fa.priority_rank}</Text>
                          </View>
                          <View style={{ flex: 1 }}>
                            <Text style={styles.analysisName}>{fa.factor_name}</Text>
                            <View style={styles.analysisMetaRow}>
                              <View style={[styles.classBadge, fa.classification === 'primary' ? styles.classPrimary : styles.classSecondary]}>
                                <Text style={styles.classBadgeText}>{fa.classification}</Text>
                              </View>
                              <Text style={styles.centralityText}>Centrality: {(fa.centrality * 100).toFixed(0)}%</Text>
                              <Text style={styles.gapText}>Gap: {fa.gap_multiplier}x</Text>
                            </View>
                          </View>
                        </View>
                        <Text style={styles.reasoningText}>{fa.reasoning}</Text>
                      </View>
                    ))}
                </View>
              )}

              {/* Apply Button */}
              <TouchableOpacity style={styles.applyBtn} onPress={applyToSteps}>
                <Ionicons name="checkmark-circle" size={20} color="#FFF" />
                <Text style={styles.applyBtnText}>Apply CLD Results to Steps 3-5</Text>
              </TouchableOpacity>

              {/* Regenerate */}
              <TouchableOpacity style={styles.regenBtn} onPress={generateCLD}>
                <Ionicons name="refresh" size={16} color={COLORS.primary} />
                <Text style={styles.regenBtnText}>Regenerate CLD</Text>
              </TouchableOpacity>
            </>
          )}
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000, justifyContent: 'flex-end' },
  container: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, maxHeight: '92%', minHeight: '60%' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  title: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 12, color: COLORS.textMuted },
  closeBtn: { padding: 4 },
  body: { padding: 16, paddingBottom: 32 },
  generateBtn: { backgroundColor: COLORS.primary, borderRadius: 16, padding: 20, alignItems: 'center', gap: 8 },
  generateBtnText: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  generateBtnSub: { fontSize: 12, color: 'rgba(255,255,255,0.8)', textAlign: 'center' },
  loadingBox: { alignItems: 'center', paddingVertical: 40, gap: 12 },
  loadingText: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  loadingSubtext: { fontSize: 12, color: COLORS.textMuted },
  tabRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, backgroundColor: '#F1F5F9' },
  tabActive: { backgroundColor: COLORS.primary },
  tabText: { fontSize: 13, fontWeight: '600', color: COLORS.textMuted },
  tabTextActive: { color: '#FFF' },
  diagramContainer: { alignItems: 'center', backgroundColor: '#FAFAFA', borderRadius: 12, padding: 8, marginBottom: 12 },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 8, justifyContent: 'center' },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendLine: { width: 20, height: 3, borderRadius: 1 },
  legendText: { fontSize: 10, color: COLORS.textMuted },
  loopsSection: { marginTop: 10, gap: 4 },
  loopsTitle: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary, textAlign: 'center', marginBottom: 4 },
  loopBadge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 10, alignSelf: 'center' },
  loopR: { backgroundColor: '#DBEAFE' },
  loopB: { backgroundColor: '#FEE2E2' },
  loopText: { fontSize: 11, fontWeight: '600' },
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
  applyBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#16A34A', borderRadius: 12, paddingVertical: 14, marginBottom: 8 },
  applyBtnText: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  regenBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10 },
  regenBtnText: { fontSize: 13, fontWeight: '600', color: COLORS.primary },
  // Edit mode styles
  editToolbar: { flexDirection: 'row', gap: 8, marginBottom: 8, flexWrap: 'wrap' },
  editToolBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 6,
    borderRadius: 8, borderWidth: 1, borderColor: COLORS.primary,
    backgroundColor: '#FFF',
  },
  editToolBtnActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  editToolText: { fontSize: 11, fontWeight: '600', color: COLORS.primary },
  editHint: {
    fontSize: 11, fontWeight: '600', color: '#F59E0B',
    textAlign: 'center', marginBottom: 6,
  },
  linkList: { marginTop: 10, gap: 4 },
  linkListTitle: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  linkItem: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 6, paddingHorizontal: 8,
    backgroundColor: '#F8FAFC', borderRadius: 8,
  },
  linkItemText: { flex: 1, fontSize: 11, color: COLORS.textSecondary },
  linkTypeBadge: {
    width: 22, height: 22, borderRadius: 11,
    alignItems: 'center', justifyContent: 'center',
  },
});
