import React, { useEffect, useRef } from 'react';
import { Animated, Easing, Platform, StyleSheet, Text, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

const isWeb = Platform.OS === 'web';
const useNative = !isWeb;

export default function JelcosLoader({ visible = true }: { visible?: boolean }) {
  const pulse = useRef(new Animated.Value(0)).current;
  const sweep = useRef(new Animated.Value(0)).current;
  const fade = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    // Web animates via CSS keyframes in app/+html.tsx so motion starts before the JS bundle hydrates.
    if (isWeb) return;
    const p = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 1, duration: 900, easing: Easing.inOut(Easing.ease), useNativeDriver: useNative }),
      Animated.timing(pulse, { toValue: 0, duration: 900, easing: Easing.inOut(Easing.ease), useNativeDriver: useNative }),
    ]));
    const s = Animated.loop(Animated.timing(sweep, { toValue: 1, duration: 1100, easing: Easing.inOut(Easing.cubic), useNativeDriver: useNative }));
    p.start();
    s.start();
    return () => { p.stop(); s.stop(); };
  }, []);

  useEffect(() => {
    Animated.timing(fade, { toValue: visible ? 1 : 0, duration: 280, useNativeDriver: useNative }).start();
  }, [visible]);

  const ringScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.18] });
  const ringOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.55, 0] });
  const markScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.04] });
  const barX = sweep.interpolate({ inputRange: [0, 1], outputRange: [-90, 200] });

  return (
    <Animated.View style={[styles.root, { opacity: fade }]} pointerEvents={visible ? 'auto' : 'none'}>
      <View style={[styles.orb, styles.orbPink]} />
      <View style={[styles.orb, styles.orbPurple]} />
      <View style={[styles.orb, styles.orbNavy]} />

      <View nativeID="jlCenter" style={styles.center}>
        <View style={styles.markWrap}>
          <Animated.View nativeID="jlRing" style={[styles.ring, !isWeb && { opacity: ringOpacity, transform: [{ scale: ringScale }] }]} />
          <Animated.View nativeID="jlMark" style={!isWeb && { transform: [{ scale: markScale }] }}>
            <LinearGradient colors={['#E91E63', '#8E24AA', '#1A237E']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.mark}>
              <Text style={styles.markLetter}>J</Text>
              <View style={styles.markDot} />
            </LinearGradient>
          </Animated.View>
        </View>

        <View style={styles.wordRow}>
          <Text style={styles.word}>JELCOS</Text>
          <LinearGradient colors={['#E91E63', '#8E24AA']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.aiPill}>
            <Text style={styles.aiText}>AI</Text>
          </LinearGradient>
        </View>
        <Text style={styles.tagline}>Clarity for every life decision</Text>

        <View style={styles.track}>
          <Animated.View nativeID="jlBar" style={[styles.barWrap, !isWeb && { transform: [{ translateX: barX }] }]}>
            <LinearGradient colors={['rgba(233,30,99,0)', '#E91E63', '#B388FF', 'rgba(142,36,170,0)']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.bar} />
          </Animated.View>
        </View>
        <Text style={styles.hint}>Preparing your decision workspace</Text>
      </View>
    </Animated.View>
  );
}

const glow = (c: string) => (Platform.OS === 'web' ? ({ filter: 'blur(90px)', backgroundColor: c } as any) : { backgroundColor: c, opacity: 0.25 });

const styles = StyleSheet.create({
  root: { ...StyleSheet.absoluteFillObject, backgroundColor: '#0A1A4F', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  orb: { position: 'absolute', width: 420, height: 420, borderRadius: 999, opacity: 0.45 },
  orbPink: { top: -120, left: -100, ...glow('#E91E63') },
  orbPurple: { bottom: -140, right: -80, ...glow('#8E24AA') },
  orbNavy: { top: '35%', left: '45%', width: 300, height: 300, ...glow('#1A237E') },
  center: { alignItems: 'center', paddingHorizontal: 24 },
  markWrap: { width: 108, height: 108, alignItems: 'center', justifyContent: 'center', marginBottom: 26 },
  ring: { position: 'absolute', width: 108, height: 108, borderRadius: 34, borderWidth: 2, borderColor: '#F48FB1' },
  mark: {
    width: 84, height: 84, borderRadius: 26, alignItems: 'center', justifyContent: 'center',
    ...(Platform.OS === 'web' ? ({ boxShadow: '0 20px 60px rgba(233,30,99,0.45), inset 0 1px 0 rgba(255,255,255,0.35)' } as any) : {}),
  },
  markLetter: { color: '#FFFFFF', fontSize: 44, fontWeight: '900', marginTop: -2 },
  markDot: { position: 'absolute', top: 16, right: 16, width: 10, height: 10, borderRadius: 99, backgroundColor: '#FFFFFF' },
  wordRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  word: { color: '#FFFFFF', fontSize: 40, fontWeight: '900', letterSpacing: 5 },
  aiPill: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 10 },
  aiText: { color: '#FFFFFF', fontSize: 20, fontWeight: '900', letterSpacing: 2 },
  tagline: { color: 'rgba(255,255,255,0.72)', fontSize: 15, fontWeight: '500', marginTop: 10, letterSpacing: 0.4 },
  track: { width: 200, height: 4, borderRadius: 99, backgroundColor: 'rgba(255,255,255,0.12)', marginTop: 30, overflow: 'hidden' },
  barWrap: { width: 90, height: 4 },
  bar: { flex: 1, borderRadius: 99 },
  hint: { color: 'rgba(255,255,255,0.45)', fontSize: 12, fontWeight: '600', marginTop: 14, letterSpacing: 1.6, textTransform: 'uppercase' },
});
