/**
 * HoverTooltip — wraps a pressable target and shows a small help-text bubble
 * on mouse hover (web). On native it falls back to the OS long-press tooltip
 * via accessibilityLabel. Also sets the native `title` attribute on web so the
 * standard browser tooltip works even before the custom bubble appears.
 */
import React, { useState } from 'react';
import { Pressable, View, Text, StyleSheet, Platform, GestureResponderEvent } from 'react-native';

interface Props {
  label: string;
  onPress?: (e: GestureResponderEvent) => void;
  children: React.ReactNode;
  style?: any;
  /** Where the bubble appears relative to the icon. Default 'top'. */
  placement?: 'top' | 'bottom';
}

export default function HoverTooltip({ label, onPress, children, style, placement = 'top' }: Props) {
  const [hover, setHover] = useState(false);
  const isWeb = Platform.OS === 'web';

  return (
    <View style={[styles.wrap, style]}>
      <Pressable
        onPress={onPress}
        onHoverIn={() => setHover(true)}
        onHoverOut={() => setHover(false)}
        accessibilityLabel={label}
        hitSlop={10}
        {...(isWeb ? ({ title: label } as any) : {})}
      >
        {children}
      </Pressable>
      {isWeb && hover ? (
        <View
          pointerEvents="none"
          style={[styles.bubble, placement === 'top' ? styles.bubbleTop : styles.bubbleBottom]}
        >
          <Text style={styles.bubbleText} numberOfLines={1}>{label}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: 'relative', alignItems: 'center', justifyContent: 'center' },
  bubble: {
    position: 'absolute',
    right: 0,
    backgroundColor: '#111827',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    zIndex: 1000,
    maxWidth: 220,
  },
  bubbleTop: { bottom: '120%' },
  bubbleBottom: { top: '120%' },
  bubbleText: { color: '#FFFFFF', fontSize: 11, fontWeight: '600' },
});
