/**
 * FontScaleButton.tsx — small A / A+ / A++ pill button group.
 *
 * Drop in the top-right of any header. Tap to cycle, or tap the active
 * pill to jump to a specific size. Persists via FontScaleContext.
 *
 * Visual: 3 tightly-packed pills inside a rounded container. Active pill
 * has solid background + bold weight; inactive pills are muted.
 */
import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ViewStyle } from 'react-native';
import { useFontScale, FontScaleKey } from '../contexts/FontScaleContext';

interface Props {
  /** Optional override for the container background (e.g. white on dark header) */
  variant?: 'light' | 'dark';
  /** Override container style if you need different positioning */
  style?: ViewStyle;
}

const OPTIONS: FontScaleKey[] = ['A', 'A+', 'A++'];

export const FontScaleButton: React.FC<Props> = ({ variant = 'light', style }) => {
  const { scaleKey, setScale } = useFontScale();

  const isDark = variant === 'dark';
  const containerBg = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.06)';
  const activePillBg = isDark ? '#FFFFFF' : '#1F2937';
  const activePillText = isDark ? '#1F2937' : '#FFFFFF';
  const inactivePillText = isDark ? 'rgba(255,255,255,0.85)' : '#4B5563';

  return (
    <View style={[styles.container, { backgroundColor: containerBg }, style]} accessibilityLabel="Font size">
      {OPTIONS.map((key) => {
        const active = key === scaleKey;
        return (
          <TouchableOpacity
            key={key}
            onPress={() => setScale(key)}
            style={[styles.pill, active && { backgroundColor: activePillBg }]}
            accessibilityLabel={`Set font size ${key}`}
            accessibilityState={{ selected: active }}
            hitSlop={6}
          >
            <Text
              style={[
                styles.pillText,
                {
                  color: active ? activePillText : inactivePillText,
                  fontWeight: active ? '700' : '600',
                  fontSize: key === 'A' ? 11 : key === 'A+' ? 12 : 13,
                },
              ]}
            >
              {key}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 14,
    padding: 2,
    gap: 1,
  },
  pill: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    minWidth: 26,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pillText: {
    letterSpacing: 0.2,
  },
});

export default FontScaleButton;
