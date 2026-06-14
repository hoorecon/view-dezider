/**
 * AiConsumptionPie — donut chart of AI credit spend grouped by touchpoint,
 * driven by GET /api/ai-wallet/consumption?since=&until=. Mounted on
 * /ai-wallet just above 'Recent Activity'.
 *
 * Has its OWN date-range selector (Last 7d / 30d / 90d / All-time / Custom)
 * — the parent passes the chosen range down to the ledger filter too so the
 * pie and the activity feed stay in sync if the user picks the same range.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import Svg, { Path, G, Circle, Text as SvgText } from 'react-native-svg';
import api from '../utils/api';

type Bucket = { feature: string; credits: number; runs: number; pct: number };

interface Props {
  /** Pretty label lookup for each ai_estimates feature key. */
  labelMap?: Record<string, string>;
  /** Optional callback so the parent can sync its Recent-Activity filter. */
  onRangeChange?: (since: string | null, until: string | null) => void;
}

const PALETTE = ['#7C3AED', '#EC4899', '#F59E0B', '#10B981', '#3B82F6',
                 '#EF4444', '#06B6D4', '#A78BFA', '#84CC16', '#F97316'];

const RANGES: { key: string; label: string; days: number | null }[] = [
  { key: '7d',  label: 'Last 7d',   days: 7 },
  { key: '30d', label: 'Last 30d',  days: 30 },
  { key: '90d', label: 'Last 90d',  days: 90 },
  { key: 'all', label: 'All-time',  days: null },
];

const isoDaysAgo = (n: number) => {
  const d = new Date(Date.now() - n * 86400000);
  return d.toISOString();
};

/** Polar → cartesian for SVG donut arc maths. */
const polar = (cx: number, cy: number, r: number, angleDeg: number) => {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
};
const arcPath = (cx: number, cy: number, rOuter: number, rInner: number,
                 startDeg: number, endDeg: number) => {
  const o1 = polar(cx, cy, rOuter, endDeg);
  const o2 = polar(cx, cy, rOuter, startDeg);
  const i1 = polar(cx, cy, rInner, startDeg);
  const i2 = polar(cx, cy, rInner, endDeg);
  const large = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${o2.x} ${o2.y} A ${rOuter} ${rOuter} 0 ${large} 1 ${o1.x} ${o1.y} L ${i2.x} ${i2.y} A ${rInner} ${rInner} 0 ${large} 0 ${i1.x} ${i1.y} Z`;
};

export const AiConsumptionPie: React.FC<Props> = ({ labelMap = {}, onRangeChange }) => {
  const [rangeKey, setRangeKey] = useState('30d');
  const [data, setData] = useState<{ total_credits: number; buckets: Bucket[] } | null>(null);
  const [loading, setLoading] = useState(true);

  const since = useMemo(() => {
    const r = RANGES.find(x => x.key === rangeKey);
    return r?.days ? isoDaysAgo(r.days) : null;
  }, [rangeKey]);

  useEffect(() => {
    setLoading(true);
    api.get('/ai-wallet/consumption', { params: since ? { since } : {} })
      .then(r => setData(r.data))
      .catch(() => setData({ total_credits: 0, buckets: [] }))
      .finally(() => setLoading(false));
    onRangeChange?.(since, null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rangeKey]);

  const buckets = data?.buckets || [];
  const total = data?.total_credits || 0;
  const cx = 90, cy = 90, rOuter = 78, rInner = 48;

  let cumDeg = 0;
  const slices = buckets.map((b, i) => {
    const sweep = total ? (b.credits / total) * 360 : 0;
    const slice = { start: cumDeg, end: cumDeg + sweep, color: PALETTE[i % PALETTE.length], bucket: b };
    cumDeg += sweep;
    return slice;
  });

  return (
    <View style={st.card}>
      <View style={st.headerRow}>
        <Text style={st.h1}>AI Meter Consumption</Text>
        <View style={st.rangeRow}>
          {RANGES.map(r => (
            <TouchableOpacity key={r.key}
              testID={`ai-pie-range-${r.key}`}
              style={[st.rangeChip, rangeKey === r.key && st.rangeChipActive]}
              onPress={() => setRangeKey(r.key)}>
              <Text style={[st.rangeText, rangeKey === r.key && st.rangeTextActive]}>{r.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {loading ? (
        <View style={st.loadingWrap}><ActivityIndicator color="#7C3AED" /></View>
      ) : buckets.length === 0 ? (
        <Text style={st.emptyTxt}>No AI spend in this period yet.</Text>
      ) : (
        <View style={st.chartRow}>
          <Svg width={180} height={180} testID="ai-consumption-pie">
            <G>
              {slices.map((s, i) =>
                s.end > s.start && (
                  <Path key={i} d={arcPath(cx, cy, rOuter, rInner, s.start, Math.min(s.end, s.start + 359.999))}
                        fill={s.color} />
                )
              )}
              {/* Center hole label */}
              <Circle cx={cx} cy={cy} r={rInner - 2} fill="#FFF" />
              <SvgText x={cx} y={cy - 4} textAnchor="middle" fontSize="14" fontWeight="800" fill="#0F172A">
                {Math.round(total)} cr
              </SvgText>
              <SvgText x={cx} y={cy + 14} textAnchor="middle" fontSize="9.5" fill="#64748B">
                spent
              </SvgText>
            </G>
          </Svg>

          {/* Legend (top 8 sliced + grouped tail) */}
          <View style={st.legendCol}>
            {slices.slice(0, 8).map((s, i) => (
              <View key={i} style={st.legendRow}>
                <View style={[st.swatch, { backgroundColor: s.color }]} />
                <Text style={st.legendLabel} numberOfLines={1}>
                  {labelMap[s.bucket.feature] || s.bucket.feature}
                </Text>
                <Text style={st.legendPct}>{s.bucket.pct}%</Text>
                <Text style={st.legendCr}>{Math.round(s.bucket.credits)} cr</Text>
              </View>
            ))}
            {slices.length > 8 && (
              <Text style={st.moreTxt}>+{slices.length - 8} more</Text>
            )}
          </View>
        </View>
      )}
    </View>
  );
};

const st = StyleSheet.create({
  card: {
    backgroundColor: '#FFF', borderRadius: 14, padding: 14,
    borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 16,
  },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  h1: { fontSize: 14, fontWeight: '800', color: '#0F172A' },
  rangeRow: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  rangeChip: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, borderWidth: 1, borderColor: '#E2E8F0', backgroundColor: '#F8FAFC' },
  rangeChipActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  rangeText: { fontSize: 11, fontWeight: '700', color: '#64748B' },
  rangeTextActive: { color: '#FFF' },
  loadingWrap: { alignItems: 'center', padding: 24 },
  emptyTxt: { textAlign: 'center', color: '#94A3B8', fontStyle: 'italic', padding: 16 },
  chartRow: { flexDirection: 'row', alignItems: 'center', gap: 16, flexWrap: 'wrap' },
  legendCol: { flex: 1, minWidth: 200, gap: 4 },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  swatch: { width: 11, height: 11, borderRadius: 3 },
  legendLabel: { flex: 1, fontSize: 11.5, color: '#1F2937' },
  legendPct: { fontSize: 11, fontWeight: '700', color: '#7C3AED', minWidth: 40, textAlign: 'right' },
  legendCr: { fontSize: 11, fontWeight: '600', color: '#64748B', minWidth: 48, textAlign: 'right' },
  moreTxt: { fontSize: 11, color: '#94A3B8', fontStyle: 'italic', marginTop: 4 },
});

export default AiConsumptionPie;
