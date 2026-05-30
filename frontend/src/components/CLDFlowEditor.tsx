/**
 * CLD Flow Canvas — universal SVG-based visual editor with zoom + pan + drag.
 *
 * Features:
 *  - Pan the canvas (drag empty area with mouse / touch)
 *  - Zoom in/out via floating +/− buttons or mouse wheel (web)
 *  - Tap empty area (without dragging) to add a new node
 *  - Tap a node to select; "Link from here" → tap target to link
 *  - Drag a node (mouse / touch) to move it
 *  - Long-press / "Edit Node" button → opens external edit modal via onEditNode
 *  - Polarity-aware edges (green "+" reinforcing, dashed red "−" balancing)
 *  - "Fit" button auto-scales view to all nodes
 */
import React, { useState, useRef, useCallback, useEffect, forwardRef, useImperativeHandle } from 'react';
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
  /** Custom canvas width (web). Defaults to 900. */
  width?: number;
  /** Custom canvas height. Defaults to 360. */
  height?: number;
  /** Hide internal toolbar hint (for embedding inside a custom wrapper) */
  hideToolbar?: boolean;
  /** Notify parent of zoom % changes (for displaying in external toolbar) */
  onZoomChange?: (zoomPct: number) => void;
}

export interface CLDFlowEditorHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  fitView: () => void;
  resetView: () => void;
  getZoomPercent: () => number;
}

const DEFAULT_W = Platform.OS === 'web' ? 900 : 360;
const DEFAULT_H = 360;
const NODE_R = 22;
const MIN_ZOOM = 0.3;
const MAX_ZOOM = 3;
const DRAG_THRESHOLD = 4;

const CLDFlowEditor = forwardRef<CLDFlowEditorHandle, Props>(function CLDFlowEditor(
  { nodes, links, onNodesChange, onLinksChange, onEditNode, width, height, hideToolbar, onZoomChange },
  ref,
) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [linkMode, setLinkMode] = useState<{ from?: string }>({});
  const [vx, setVx] = useState(0);
  const [vy, setVy] = useState(0);
  const [zoom, setZoom] = useState(1);

  const panStartRef = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);

  const canvasW = width ?? DEFAULT_W;
  const canvasH = height ?? DEFAULT_H;
  const viewW = canvasW / zoom;
  const viewH = canvasH / zoom;
  const viewBox = `${vx} ${vy} ${viewW} ${viewH}`;

  const screenToSvg = useCallback(
    (sx: number, sy: number) => ({
      x: vx + (sx / canvasW) * viewW,
      y: vy + (sy / canvasH) * viewH,
    }),
    [vx, vy, viewW, viewH, canvasW, canvasH],
  );

  const clampZoom = (z: number) => Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, z));

  const doZoom = useCallback(
    (factor: number, cx?: number, cy?: number) => {
      const newZoom = clampZoom(zoom * factor);
      if (newZoom === zoom) return;
      const sx = cx ?? canvasW / 2;
      const sy = cy ?? canvasH / 2;
      const svgPt = screenToSvg(sx, sy);
      const newViewW = canvasW / newZoom;
      const newViewH = canvasH / newZoom;
      setZoom(newZoom);
      setVx(svgPt.x - (sx / canvasW) * newViewW);
      setVy(svgPt.y - (sy / canvasH) * newViewH);
    },
    [zoom, screenToSvg, canvasW, canvasH],
  );

  const resetView = () => { setVx(0); setVy(0); setZoom(1); };

  // Auto-fit when nodes first arrive (or grow from 0 → many)
  const autoFitDoneRef = useRef(false);
  useEffect(() => {
    if (autoFitDoneRef.current) return;
    if (nodes.length === 0) return;
    // Defer one tick to ensure layout settled
    const t = setTimeout(() => {
      const xs = nodes.map(n => n.x ?? 0);
      const ys = nodes.map(n => n.y ?? 0);
      const minX = Math.min(...xs) - NODE_R - 20;
      const maxX = Math.max(...xs) + NODE_R + 20;
      const minY = Math.min(...ys) - NODE_R - 20;
      const maxY = Math.max(...ys) + NODE_R + 40;
      const w = Math.max(1, maxX - minX);
      const h = Math.max(1, maxY - minY);
      const fitZoom = clampZoom(Math.min(canvasW / w, canvasH / h));
      setZoom(fitZoom);
      setVx(minX);
      setVy(minY);
      autoFitDoneRef.current = true;
    }, 50);
    return () => clearTimeout(t);
  }, [nodes, canvasW, canvasH]);

  const fitView = useCallback(() => {
    if (nodes.length === 0) { setVx(0); setVy(0); setZoom(1); return; }
    const xs = nodes.map(n => n.x ?? 0);
    const ys = nodes.map(n => n.y ?? 0);
    const minX = Math.min(...xs) - NODE_R - 20;
    const maxX = Math.max(...xs) + NODE_R + 20;
    const minY = Math.min(...ys) - NODE_R - 20;
    const maxY = Math.max(...ys) + NODE_R + 40;
    const w = Math.max(1, maxX - minX);
    const h = Math.max(1, maxY - minY);
    const fitZoom = clampZoom(Math.min(canvasW / w, canvasH / h));
    setZoom(fitZoom);
    setVx(minX);
    setVy(minY);
  }, [nodes, canvasW, canvasH]);

  // Notify parent of zoom changes
  useEffect(() => {
    if (onZoomChange) onZoomChange(Math.round(zoom * 100));
  }, [zoom, onZoomChange]);

  useImperativeHandle(ref, () => ({
    zoomIn: () => doZoom(1.25),
    zoomOut: () => doZoom(0.8),
    fitView,
    resetView,
    getZoomPercent: () => Math.round(zoom * 100),
  }), [doZoom, fitView, zoom]);

  const moveNode = (id: string, x: number, y: number) => {
    onNodesChange(nodes.map(n => (n.factor_id === id ? { ...n, x, y } : n)));
  };

  const tapEmpty = (svgX: number, svgY: number) => {
    if (linkMode.from) { setLinkMode({}); return; }
    if (selectedId) { setSelectedId(null); return; }
    const id = `n_${Date.now().toString(36)}`;
    onNodesChange([
      ...nodes,
      {
        factor_id: id,
        name: `Factor ${nodes.length + 1}`,
        x: svgX,
        y: svgY,
        classification: 'secondary',
        priority_rank: nodes.length + 1,
      },
    ]);
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

  // Background pan responder (drag-to-pan / tap-to-add)
  const bgPanResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (e) => {
        panStartRef.current = {
          x: e.nativeEvent.locationX,
          y: e.nativeEvent.locationY,
          vx,
          vy,
          moved: false,
        };
      },
      onPanResponderMove: (_e, g) => {
        if (!panStartRef.current) return;
        if (Math.abs(g.dx) > DRAG_THRESHOLD || Math.abs(g.dy) > DRAG_THRESHOLD) {
          panStartRef.current.moved = true;
        }
        setVx(panStartRef.current.vx - g.dx / zoom);
        setVy(panStartRef.current.vy - g.dy / zoom);
      },
      onPanResponderRelease: (e) => {
        const wasDrag = panStartRef.current?.moved;
        panStartRef.current = null;
        if (!wasDrag) {
          const sx = e.nativeEvent.locationX;
          const sy = e.nativeEvent.locationY;
          const pt = screenToSvg(sx, sy);
          tapEmpty(pt.x, pt.y);
        }
      },
      onPanResponderTerminate: () => { panStartRef.current = null; },
    }),
  ).current;

  // Web mouse-wheel zoom
  const webWheelProps =
    Platform.OS === 'web'
      ? ({
          onWheel: (e: any) => {
            e.preventDefault?.();
            const rect = e.currentTarget?.getBoundingClientRect?.();
            const sx = e.clientX - (rect?.left ?? 0);
            const sy = e.clientY - (rect?.top ?? 0);
            const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
            doZoom(factor, sx, sy);
          },
        } as any)
      : {};

  return (
    <View style={[styles.wrap, { width: canvasW }]}>
      {!hideToolbar && (
        <View style={styles.toolBar}>
          <Text style={styles.toolHint}>
            {linkMode.from
              ? '🔗 Tap a target node to create a link'
              : selectedId
              ? '✏️ Use "Link from here" · long-press a node to edit · drag empty area to pan'
              : '👆 Tap empty area to add node · drag to pan · scroll / +/− to zoom'}
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
      )}

      {/* Mini inline action bar (always visible) — shown when a node is selected */}
      {hideToolbar && selectedId && !linkMode.from && (
        <View style={styles.miniBar}>
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
      {hideToolbar && linkMode.from && (
        <View style={styles.miniBar}>
          <Text style={styles.toolHint}>🔗 Tap a target node to create a link · tap source again to cancel</Text>
        </View>
      )}

      <View style={[styles.canvasOuter, { width: canvasW, height: canvasH }]}>
        <View style={[styles.canvasInner, { width: canvasW, height: canvasH }]} {...webWheelProps}>          <Svg width={canvasW} height={canvasH} viewBox={viewBox}>
            <Defs>
              <Marker id="arrowR" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
                <SvgPath d="M0,0 L0,6 L9,3 z" fill="#10B981" />
              </Marker>
              <Marker id="arrowB" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
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
                    markerEnd={isR ? 'url(#arrowR)' : 'url(#arrowB)'}
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

          {/* Background tap/pan overlay */}
          <View style={StyleSheet.absoluteFillObject} pointerEvents="box-none">
            <View
              style={StyleSheet.absoluteFillObject}
              {...bgPanResponder.panHandlers}
            />

            {/* Per-node hotspots (drag / tap) */}
            {nodes.map(n => {
              const cx = n.x ?? 100;
              const cy = n.y ?? 100;
              const screenX = ((cx - vx) / viewW) * canvasW;
              const screenY = ((cy - vy) / viewH) * canvasH;
              const screenR = NODE_R * zoom;

              // Skip rendering hotspot if completely off-screen
              if (screenX < -screenR || screenX > canvasW + screenR || screenY < -screenR || screenY > canvasH + screenR) {
                return null;
              }

              const nodePan = PanResponder.create({
                onStartShouldSetPanResponder: () => true,
                onMoveShouldSetPanResponder: () => true,
                onPanResponderGrant: () => {
                  panStartRef.current = { x: cx, y: cy, vx, vy, moved: false };
                },
                onPanResponderMove: (_, g) => {
                  if (!panStartRef.current) return;
                  if (Math.abs(g.dx) > DRAG_THRESHOLD || Math.abs(g.dy) > DRAG_THRESHOLD) {
                    panStartRef.current.moved = true;
                  }
                  moveNode(n.factor_id, panStartRef.current.x + g.dx / zoom, panStartRef.current.y + g.dy / zoom);
                },
                onPanResponderRelease: () => {
                  const wasDrag = panStartRef.current?.moved;
                  panStartRef.current = null;
                  if (!wasDrag) handleNodeTap(n.factor_id);
                },
                onPanResponderTerminate: () => { panStartRef.current = null; },
              });

              return (
                <View
                  key={`hit_${n.factor_id}`}
                  pointerEvents="auto"
                  style={{
                    position: 'absolute',
                    left: screenX - screenR,
                    top: screenY - screenR,
                    width: screenR * 2,
                    height: screenR * 2,
                    borderRadius: screenR,
                  }}
                  {...nodePan.panHandlers}
                />
              );
            })}
          </View>
        </View>
      </View>
    </View>
  );
});

export default CLDFlowEditor;

const styles = StyleSheet.create({
  wrap: { backgroundColor: '#FFFFFF', alignSelf: 'center' },
  toolBar: { paddingHorizontal: 12, paddingVertical: 8, backgroundColor: '#FAFAFA', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  miniBar: {
    flexDirection: 'row', gap: 6, paddingHorizontal: 12, paddingVertical: 6,
    backgroundColor: '#FAFAFA', borderBottomWidth: 1, borderBottomColor: '#E2E8F0',
  },
  toolHint: { fontSize: 11, color: COLORS.textMuted },
  toolBtnRow: { flexDirection: 'row', gap: 6, marginTop: 6 },
  toolBtn: { paddingHorizontal: 10, paddingVertical: 5, backgroundColor: '#EDE9FE', borderRadius: 6 },
  toolBtnText: { fontSize: 11, fontWeight: '700', color: '#7C3AED' },
  canvasOuter: { alignSelf: 'center', backgroundColor: '#FAFAFA', position: 'relative' },
  canvasInner: { position: 'relative', overflow: 'hidden' },
});
