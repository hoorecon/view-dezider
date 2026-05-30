/**
 * CLD Flow Canvas — universal SVG-based visual editor (web + native).
 * No @xyflow/react dependency. Supports tap-to-select, drag-to-move (native PanResponder
 * & web mouse), tap-empty-area to add node, polarity-aware link rendering.
 */
import React, { useState, useRef } from 'react';
import { View, StyleSheet, PanResponder, Platform, TouchableOpacity, Text } from 'react-native';
import Svg, { Circle, Line, Defs, Marker, Path as SvgPath, Text as SvgText, G } from 'react-native-svg';
import { COLORS } from '../constants/colors';

interface CLDNode {
  factor_id: string;
  name: string;
  x?: number;
  y?: number;
  classification?: string;
  color?: string;
  priority_rank?: number;
}
interface CLDLink {
  from_id: string;
  to_id: string;
  link_type: string;
  strength?: number;
  description?: string;
}

interface Props {
  nodes: CLDNode[];
  links: CLDLink[];
  onNodesChange: (n: CLDNode[]) => void;
  onLinksChange: (l: CLDLink[]) => void;
  onEditNode?: (id: string) => void;
  onEditLink?: (from: string, to: string) => void;
}

const CANVAS_W = Platform.OS === 'web' ? 900 : 360;
const CANVAS_H = 340;
const NODE_R = 22;

export default function CLDFlowEditor({
  nodes,
  links,
  onNodesChange,
  onEditNode,
  onLinksChange,
}: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [linkMode, setLinkMode] = useState<{ from?: string }>({});
  const draggingRef = useRef<string | null>(null);

  const startDrag = (id: string) => { draggingRef.current = id; };
  const endDrag = () => { draggingRef.current = null; };

  const moveTo = (id: string, x: number, y: number) => {
    const clampedX = Math.max(NODE_R + 4, Math.min(CANVAS_W - NODE_R - 4, x));
    const clampedY = Math.max(NODE_R + 4, Math.min(CANVAS_H - NODE_R - 4, y));
    const next = nodes.map(n => (n.factor_id === id ? { ...n, x: clampedX, y: clampedY } : n));
    onNodesChange(next);
  };

  const tapEmpty = (x: number, y: number) => {
    if (linkMode.from) { setLinkMode({}); return; }
    if (selectedId) { setSelectedId(null); return; }
    const id = `n_${Date.now().toString(36)}`;
    const node: CLDNode = {
      factor_id: id,
      name: `Factor ${nodes.length + 1}`,
      x, y,
      classification: 'secondary',
      priority_rank: nodes.length + 1,
    };
    onNodesChange([...nodes, node]);
    setSelectedId(id);
  };

  const handleNodeTap = (id: string) => {
    if (linkMode.from) {
      if (linkMode.from === id) { setLinkMode({}); return; }
      if (!links.some(l => l.from_id === linkMode.from && l.to_id === id)) {
        onLinksChange([
          ...links,
          { from_id: linkMode.from!, to_id: id, link_type: 'reinforcing', strength: 5, description: '' },
        ]);
      }
      setLinkMode({});
      return;
    }
    setSelectedId(prev => (prev === id ? null : id));
  };

  const startLinkFromSelected = () => {
    if (selectedId) setLinkMode({ from: selectedId });
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.toolBar}>
        <Text style={styles.toolHint}>
          {linkMode.from
            ? '🔗 Tap a target node to create a link'
            : selectedId
            ? '✏️ Use "Link from here" to draw a link · long-press a node to edit'
            : '👆 Tap empty area to add a node · tap a node to select'}
        </Text>
        {selectedId && !linkMode.from && (
          <View style={styles.toolBtnRow}>
            <TouchableOpacity style={styles.toolBtn} onPress={startLinkFromSelected}>
              <Text style={styles.toolBtnText}>Link from here →</Text>
            </TouchableOpacity>
            {onEditNode && (
              <TouchableOpacity style={styles.toolBtn} onPress={() => onEditNode(selectedId)}>
                <Text style={styles.toolBtnText}>Edit Node</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
      </View>

      <View style={styles.canvasOuter}>
        <Svg width={CANVAS_W} height={CANVAS_H}>
          <Defs>
            <Marker id="arrowReinforcing" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
              <SvgPath d="M0,0 L0,6 L9,3 z" fill="#10B981" />
            </Marker>
            <Marker id="arrowBalancing" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
              <SvgPath d="M0,0 L0,6 L9,3 z" fill="#EF4444" />
            </Marker>
          </Defs>

          {links.map((link, idx) => {
            const from = nodes.find(n => n.factor_id === link.from_id);
            const to = nodes.find(n => n.factor_id === link.to_id);
            if (!from || !to) return null;
            const fx = from.x ?? 100;
            const fy = from.y ?? 100;
            const tx = to.x ?? 100;
            const ty = to.y ?? 100;
            const dx = tx - fx;
            const dy = ty - fy;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const sx = fx + (dx / dist) * NODE_R;
            const sy = fy + (dy / dist) * NODE_R;
            const ex = tx - (dx / dist) * (NODE_R + 4);
            const ey = ty - (dy / dist) * (NODE_R + 4);
            const isR = link.link_type === 'reinforcing';
            const color = isR ? '#10B981' : '#EF4444';
            const sw = 1 + Math.min(4, (link.strength || 5) / 2.5);
            return (
              <G key={`l_${idx}`}>
                <Line
                  x1={sx} y1={sy} x2={ex} y2={ey}
                  stroke={color} strokeWidth={sw}
                  strokeDasharray={isR ? undefined : '6,3'}
                  markerEnd={isR ? 'url(#arrowReinforcing)' : 'url(#arrowBalancing)'}
                />
                <SvgText
                  x={(sx + ex) / 2} y={(sy + ey) / 2 - 4}
                  textAnchor="middle" fontSize={14} fontWeight="bold" fill={color}
                >
                  {isR ? '+' : '−'}
                </SvgText>
              </G>
            );
          })}

          {nodes.map(n => {
            const cx = n.x ?? 100;
            const cy = n.y ?? 100;
            const isSelected = selectedId === n.factor_id;
            const isLinkFrom = linkMode.from === n.factor_id;
            const stroke = isLinkFrom ? '#F59E0B' : isSelected ? '#7C3AED' : '#FFFFFF';
            const fill = n.color || (n.classification === 'primary' ? COLORS.primary : '#94A3B8');
            return (
              <G key={n.factor_id}>
                <Circle cx={cx} cy={cy} r={NODE_R} fill={fill} stroke={stroke} strokeWidth={isSelected || isLinkFrom ? 3 : 2} />
                <SvgText x={cx} y={cy + 4} textAnchor="middle" fontSize={11} fontWeight="bold" fill="#FFF">
                  {n.priority_rank || ''}
                </SvgText>
                <SvgText x={cx} y={cy + NODE_R + 12} textAnchor="middle" fontSize={10} fontWeight="600" fill={COLORS.textPrimary}>
                  {n.name.length > 16 ? n.name.slice(0, 14) + '…' : n.name}
                </SvgText>
              </G>
            );
          })}
        </Svg>

        {/* Background tap-to-add layer */}
        <View pointerEvents="box-none" style={StyleSheet.absoluteFillObject}>
          <TouchableOpacity
            activeOpacity={1}
            style={StyleSheet.absoluteFillObject}
            onPress={(e: any) => {
              const x = e?.nativeEvent?.locationX;
              const y = e?.nativeEvent?.locationY;
              if (typeof x === 'number' && typeof y === 'number') tapEmpty(x, y);
            }}
          />

          {/* Per-node hotspots */}
          {nodes.map(n => {
            const cx = n.x ?? 100;
            const cy = n.y ?? 100;
            const pan =
              Platform.OS !== 'web'
                ? PanResponder.create({
                    onStartShouldSetPanResponder: () => true,
                    onMoveShouldSetPanResponder: () => true,
                    onPanResponderGrant: () => startDrag(n.factor_id),
                    onPanResponderMove: (_, g) => moveTo(n.factor_id, cx + g.dx, cy + g.dy),
                    onPanResponderRelease: endDrag,
                    onPanResponderTerminate: endDrag,
                  }).panHandlers
                : {};
            return (
              <TouchableOpacity
                key={`hit_${n.factor_id}`}
                onPress={() => handleNodeTap(n.factor_id)}
                onLongPress={() => onEditNode && onEditNode(n.factor_id)}
                activeOpacity={0.7}
                style={{
                  position: 'absolute',
                  left: cx - NODE_R,
                  top: cy - NODE_R,
                  width: NODE_R * 2,
                  height: NODE_R * 2,
                  borderRadius: NODE_R,
                }}
                {...pan}
              />
            );
          })}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#FFFFFF' },
  toolBar: { paddingHorizontal: 12, paddingVertical: 8, backgroundColor: '#FAFAFA', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  toolHint: { fontSize: 11, color: COLORS.textMuted },
  toolBtnRow: { flexDirection: 'row', gap: 6, marginTop: 6 },
  toolBtn: { paddingHorizontal: 10, paddingVertical: 5, backgroundColor: '#EDE9FE', borderRadius: 6 },
  toolBtnText: { fontSize: 11, fontWeight: '700', color: '#7C3AED' },
  canvasOuter: { width: CANVAS_W, alignSelf: 'center', backgroundColor: '#FAFAFA', position: 'relative' },
});
