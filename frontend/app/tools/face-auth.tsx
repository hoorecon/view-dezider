import React, { useState, useRef, useEffect, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator,
  Platform, Dimensions, Animated,
} from 'react-native';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Conditionally import CameraView
let CameraView: any = null;
try {
  const cam = require('expo-camera');
  CameraView = cam.CameraView || cam.Camera;
} catch (e) {}

type Mode = 'register' | 'verify' | 'presence';

const LIVENESS_PROMPTS = [
  { key: 'center', label: 'Look at the camera', icon: 'eye', duration: 2000 },
  { key: 'blink', label: 'Blink your eyes', icon: 'eye-off', duration: 2500 },
  { key: 'left', label: 'Turn head slightly left', icon: 'arrow-back', duration: 2000 },
  { key: 'right', label: 'Turn head slightly right', icon: 'arrow-forward', duration: 2000 },
  { key: 'capture', label: 'Hold still — capturing...', icon: 'camera', duration: 1500 },
];

export default function FaceAuthScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const mode = (params.mode as Mode) || 'register';
  const sessionId = params.sessionId as string | undefined;

  const cameraRef = useRef<any>(null);
  const pulseAnim = useRef(new Animated.Value(1)).current;

  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [facing, setFacing] = useState<'front' | 'back'>('front');
  const [processing, setProcessing] = useState(false);
  const [status, setStatus] = useState<any>(null);
  const [currentPrompt, setCurrentPrompt] = useState(0);
  const [livenessActive, setLivenessActive] = useState(false);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [webCameraStream, setWebCameraStream] = useState<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Fetch face registration status
  const fetchStatus = async () => {
    try {
      const res = await api.get('/face-auth/status');
      setStatus(res.data);
    } catch (e) {}
  };

  useFocusEffect(useCallback(() => { fetchStatus(); }, []));

  // Request camera permission
  useEffect(() => {
    (async () => {
      if (Platform.OS === 'web') {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } });
          setWebCameraStream(stream);
          setHasPermission(true);
        } catch (e) {
          setHasPermission(false);
        }
      } else if (CameraView) {
        try {
          const { Camera } = require('expo-camera');
          const { status: camStatus } = await Camera.requestCameraPermissionsAsync();
          setHasPermission(camStatus === 'granted');
        } catch (e) {
          setHasPermission(false);
        }
      }
    })();
    return () => {
      if (webCameraStream) webCameraStream.getTracks().forEach(t => t.stop());
    };
  }, []);

  // Attach web camera to video element
  useEffect(() => {
    if (Platform.OS === 'web' && webCameraStream && videoRef.current) {
      videoRef.current.srcObject = webCameraStream;
      videoRef.current.play();
    }
  }, [webCameraStream]);

  // Pulse animation for face guide
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, { toValue: 1.05, duration: 800, useNativeDriver: true }),
        Animated.timing(pulseAnim, { toValue: 1, duration: 800, useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, []);

  const capturePhoto = async (): Promise<string | null> => {
    if (Platform.OS === 'web') {
      // Web: capture from video via canvas
      if (!videoRef.current || !canvasRef.current) return null;
      const canvas = canvasRef.current;
      const video = videoRef.current;
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext('2d');
      if (!ctx) return null;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL('image/jpeg', 0.8);
    } else if (cameraRef.current) {
      // Native: use expo-camera
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.7, base64: true });
      return `data:image/jpeg;base64,${photo.base64}`;
    }
    return null;
  };

  const startLivenessFlow = () => {
    setLivenessActive(true);
    setCurrentPrompt(0);
    setCapturedImage(null);
    setResult(null);
    runLivenessStep(0);
  };

  const runLivenessStep = async (stepIndex: number) => {
    if (stepIndex >= LIVENESS_PROMPTS.length) {
      // All prompts done — capture final image
      await handleCapture();
      return;
    }
    setCurrentPrompt(stepIndex);
    setTimeout(() => runLivenessStep(stepIndex + 1), LIVENESS_PROMPTS[stepIndex].duration);
  };

  const handleCapture = async () => {
    setProcessing(true);
    try {
      const b64 = await capturePhoto();
      if (!b64) {
        showAlert('Error', 'Failed to capture image from camera');
        setProcessing(false);
        setLivenessActive(false);
        return;
      }
      setCapturedImage(b64);

      if (mode === 'register') {
        const res = await api.post('/face-auth/register', { image_base64: b64 });
        setResult(res.data);
        showAlert('Face Registered', res.data.message || 'Face biometric registered successfully!');
        fetchStatus();
      } else {
        // verify or presence
        const res = await api.post('/face-auth/verify', {
          image_base64: b64,
          session_id: sessionId || null,
        });
        setResult(res.data);
        if (res.data.verified) {
          showAlert('Verified', `Face verified! Similarity: ${(res.data.similarity * 100).toFixed(1)}%`);
        } else {
          showAlert('Not Verified', `Face does not match. Similarity: ${(res.data.similarity * 100).toFixed(1)}% (threshold: ${(res.data.threshold * 100).toFixed(0)}%)`);
        }
      }
    } catch (err: any) {
      showAlert('Error', err.response?.data?.detail || 'Face processing failed');
    } finally {
      setProcessing(false);
      setLivenessActive(false);
    }
  };

  // No permission
  if (hasPermission === false) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.centerContent}>
          <Ionicons name="camera-outline" size={64} color="#DC2626" />
          <Text style={styles.permTitle}>Camera Access Required</Text>
          <Text style={styles.permDesc}>Face authentication requires camera access to verify your identity.</Text>
          <TouchableOpacity style={styles.backButton} onPress={() => safeBack(router)}>
            <Text style={styles.backButtonText}>Go Back</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // Loading permission
  if (hasPermission === null) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.centerContent}>
          <ActivityIndicator size="large" color="#059669" />
          <Text style={styles.permDesc}>Requesting camera access...</Text>
        </View>
      </SafeAreaView>
    );
  }

  const title = mode === 'register' ? 'Register Face' : mode === 'presence' ? 'Presence Check' : 'Verify Identity';
  const subtitle = mode === 'register'
    ? 'Position your face in the guide and follow the prompts'
    : 'Look at the camera for identity verification';

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.headerBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>{title}</Text>
          <Text style={styles.headerSub}>{subtitle}</Text>
        </View>
        {status?.registered && mode === 'register' && (
          <View style={styles.registeredBadge}>
            <Ionicons name="checkmark-circle" size={14} color="#059669" />
            <Text style={styles.registeredText}>Registered</Text>
          </View>
        )}
      </View>

      {/* Camera View */}
      <View style={styles.cameraContainer}>
        {Platform.OS === 'web' ? (
          <View style={styles.webCamera}>
            <video ref={videoRef as any} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' } as any} playsInline autoPlay muted />
            <canvas ref={canvasRef as any} style={{ display: 'none' } as any} />
          </View>
        ) : CameraView ? (
          <CameraView ref={cameraRef} style={styles.camera} facing={facing} />
        ) : (
          <View style={styles.noCameraFallback}>
            <Ionicons name="camera-off" size={48} color="#6B7280" />
            <Text style={styles.noCameraText}>Camera not available</Text>
          </View>
        )}

        {/* Face Guide Overlay */}
        <View style={styles.overlay}>
          <Animated.View style={[styles.faceGuide, { transform: [{ scale: pulseAnim }] }]}>
            <View style={styles.guideCorner} />
            <View style={[styles.guideCorner, styles.guideTopRight]} />
            <View style={[styles.guideCorner, styles.guideBottomLeft]} />
            <View style={[styles.guideCorner, styles.guideBottomRight]} />
          </Animated.View>

          {/* Liveness Prompt */}
          {livenessActive && currentPrompt < LIVENESS_PROMPTS.length && (
            <View style={styles.promptBanner}>
              <Ionicons name={LIVENESS_PROMPTS[currentPrompt].icon as any} size={20} color="#FFF" />
              <Text style={styles.promptText}>{LIVENESS_PROMPTS[currentPrompt].label}</Text>
              <View style={styles.promptProgress}>
                {LIVENESS_PROMPTS.map((_, i) => (
                  <View key={i} style={[styles.promptDot, i <= currentPrompt && styles.promptDotActive]} />
                ))}
              </View>
            </View>
          )}

          {/* Processing Indicator */}
          {processing && (
            <View style={styles.processingOverlay}>
              <ActivityIndicator size="large" color="#FFF" />
              <Text style={styles.processingText}>Analyzing face...</Text>
            </View>
          )}
        </View>
      </View>

      {/* Result Panel */}
      {result && (
        <View style={[styles.resultPanel, result.verified !== undefined && (result.verified ? styles.resultSuccess : styles.resultFail)]}>
          <Ionicons
            name={result.registered ? 'checkmark-circle' : result.verified ? 'shield-checkmark' : 'close-circle'}
            size={24}
            color={result.registered || result.verified ? '#059669' : '#DC2626'}
          />
          <View style={{ flex: 1 }}>
            <Text style={styles.resultTitle}>
              {result.registered ? 'Face Registered' : result.verified ? 'Identity Verified' : 'Verification Failed'}
            </Text>
            {result.similarity !== undefined && (
              <Text style={styles.resultDetail}>Match: {(result.similarity * 100).toFixed(1)}% (min {(result.threshold * 100).toFixed(0)}%)</Text>
            )}
            {result.liveness && (
              <Text style={styles.resultDetail}>
                EAR: {result.liveness.eye_aspect_ratio} • Yaw: {result.liveness.head_yaw.toFixed(2)}
              </Text>
            )}
          </View>
        </View>
      )}

      {/* Controls */}
      <View style={styles.controls}>
        {!livenessActive && !processing && (
          <>
            <TouchableOpacity style={styles.captureBtn} onPress={startLivenessFlow}>
              <View style={styles.captureBtnInner}>
                <Ionicons name={mode === 'register' ? 'person-add' : 'shield-checkmark'} size={28} color="#FFF" />
              </View>
            </TouchableOpacity>
            <Text style={styles.captureHint}>
              {mode === 'register' ? 'Tap to register face' : 'Tap to verify'}
            </Text>
          </>
        )}

        {result && (
          <View style={styles.actionRow}>
            {mode === 'register' && result.registered && (
              <TouchableOpacity style={styles.actionBtnGreen}
                onPress={() => router.replace({ pathname: '/tools/face-auth', params: { mode: 'verify' } } as any)}>
                <Ionicons name="shield-checkmark" size={16} color="#FFF" />
                <Text style={styles.actionBtnText}>Test Verify</Text>
              </TouchableOpacity>
            )}
            <TouchableOpacity style={styles.actionBtnGray}
              onPress={() => { setResult(null); setCapturedImage(null); }}>
              <Ionicons name="refresh" size={16} color="#FFF" />
              <Text style={styles.actionBtnText}>Retry</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionBtnGray} onPress={() => safeBack(router)}>
              <Text style={styles.actionBtnText}>Done</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  centerContent: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, gap: 12 },
  permTitle: { fontSize: 18, fontWeight: '700', color: '#0F172A', marginTop: 8 },
  permDesc: { fontSize: 13, color: '#9CA3AF', textAlign: 'center' },
  backButton: { paddingHorizontal: 24, paddingVertical: 10, borderRadius: 8, backgroundColor: '#374151', marginTop: 16 },
  backButtonText: { fontSize: 14, fontWeight: '600', color: '#0F172A' },

  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#FFFFFF', gap: 10 },
  headerBtn: { width: 38, height: 38, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.1)', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A' },
  headerSub: { fontSize: 11, color: '#9CA3AF', marginTop: 1 },
  registeredBadge: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#ECFDF5', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  registeredText: { fontSize: 10, fontWeight: '600', color: '#059669' },

  cameraContainer: { flex: 1, position: 'relative', overflow: 'hidden' },
  webCamera: { flex: 1, backgroundColor: '#000' },
  camera: { flex: 1 },
  noCameraFallback: { flex: 1, backgroundColor: '#FFFFFF', justifyContent: 'center', alignItems: 'center', gap: 8 },
  noCameraText: { fontSize: 14, color: '#9CA3AF' },

  overlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, justifyContent: 'center', alignItems: 'center' },
  faceGuide: { width: 220, height: 280, borderRadius: 110, position: 'relative' },
  guideCorner: { position: 'absolute', top: 0, left: 0, width: 40, height: 40, borderTopWidth: 3, borderLeftWidth: 3, borderColor: '#059669', borderTopLeftRadius: 20 },
  guideTopRight: { left: undefined, right: 0, borderLeftWidth: 0, borderRightWidth: 3, borderTopLeftRadius: 0, borderTopRightRadius: 20 },
  guideBottomLeft: { top: undefined, bottom: 0, borderTopWidth: 0, borderBottomWidth: 3, borderTopLeftRadius: 0, borderBottomLeftRadius: 20 },
  guideBottomRight: { top: undefined, bottom: 0, left: undefined, right: 0, borderTopWidth: 0, borderLeftWidth: 0, borderBottomWidth: 3, borderRightWidth: 3, borderTopLeftRadius: 0, borderBottomRightRadius: 20 },

  promptBanner: { position: 'absolute', top: 40, alignItems: 'center', backgroundColor: 'rgba(0,0,0,0.7)', paddingHorizontal: 24, paddingVertical: 12, borderRadius: 12, gap: 6 },
  promptText: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  promptProgress: { flexDirection: 'row', gap: 6 },
  promptDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.3)' },
  promptDotActive: { backgroundColor: '#059669' },

  processingOverlay: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'center', alignItems: 'center', gap: 12 },
  processingText: { fontSize: 14, fontWeight: '600', color: '#0F172A' },

  resultPanel: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#FFFFFF', borderTopWidth: 1, borderTopColor: '#374151' },
  resultSuccess: { borderTopColor: '#059669', borderTopWidth: 2 },
  resultFail: { borderTopColor: '#DC2626', borderTopWidth: 2 },
  resultTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  resultDetail: { fontSize: 11, color: '#9CA3AF', marginTop: 2 },

  controls: { alignItems: 'center', paddingVertical: 16, backgroundColor: '#FFFFFF' },
  captureBtn: { width: 72, height: 72, borderRadius: 36, borderWidth: 3, borderColor: '#059669', justifyContent: 'center', alignItems: 'center' },
  captureBtnInner: { width: 56, height: 56, borderRadius: 28, backgroundColor: '#059669', justifyContent: 'center', alignItems: 'center' },
  captureHint: { fontSize: 12, color: '#9CA3AF', marginTop: 8 },
  actionRow: { flexDirection: 'row', gap: 10 },
  actionBtnGreen: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#059669', paddingHorizontal: 16, paddingVertical: 10, borderRadius: 8 },
  actionBtnGray: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#374151', paddingHorizontal: 16, paddingVertical: 10, borderRadius: 8 },
  actionBtnText: { fontSize: 13, fontWeight: '600', color: '#0F172A' },
});
