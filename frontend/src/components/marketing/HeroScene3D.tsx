import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Platform } from 'react-native';

/**
 * 3D Project-Themed Interactive Hero Background for JELCOS AI / ViewDezider.
 * Built with Three.js WebGL rendering for Web.
 * 
 * Project-Specific Features:
 * - Central 3D Holographic JELCOS Emblem (Glowing 'J' Glass Prism with Inner Core)
 * - 6 Orbiting 3D Decision System Nodes with custom icons & text:
 *    1. 🎯 "My Dezider" (10-Step Score)
 *    2. ⚖️ "Pros & Cons" (Weighted Analysis)
 *    3. 🧭 "SWOT Engine" (Clarity Verdict)
 *    4. 💼 "Career & Finance" (Life Balance)
 *    5. ❤️ "Health & Family" (Life Balance)
 *    6. ⚡ "Action Plan" (Who · What · When)
 * - Dynamic Laser Synapse Beams connecting the Decision Nodes to the JELCOS core with flowing pulses
 * - Cybernetic Decision Dial & Radar grid floor
 * - Ambient Stardust particles with smooth depth-of-field
 * - Smooth lerped mouse / touch 3D parallax with natural idle oscillation
 * - Zero click interference (pointer-events: none, transparent WebGL)
 */
export default function HeroScene3D() {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;

    let isMounted = true;
    let animId: number;
    let renderer: any = null;
    let scene: any = null;
    let camera: any = null;
    let THREE: any = null;

    // Mouse parallax tracking
    let targetMouseX = 0;
    let targetMouseY = 0;
    let mouseX = 0;
    let mouseY = 0;

    const onMouseMove = (e: MouseEvent) => {
      const { innerWidth, innerHeight } = window;
      targetMouseX = (e.clientX / innerWidth - 0.5) * 2;
      targetMouseY = (e.clientY / innerHeight - 0.5) * 2;
    };

    const onTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        const touch = e.touches[0];
        const { innerWidth, innerHeight } = window;
        targetMouseX = (touch.clientX / innerWidth - 0.5) * 1.5;
        targetMouseY = (touch.clientY / innerHeight - 0.5) * 1.5;
      }
    };

    // Helper to generate crisp Canvas textures for the central JELCOS logo badge
    function createJelcosBadgeTexture(size = 512) {
      const canvas = document.createElement('canvas');
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d');
      if (!ctx) return null;

      // Rounded rect background with brand gradient
      const r = 80;
      const grad = ctx.createLinearGradient(0, 0, size, size);
      grad.addColorStop(0, '#E91E63');
      grad.addColorStop(0.5, '#8E24AA');
      grad.addColorStop(1, '#1A237E');

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(40, 40, size - 80, size - 80, r);
      ctx.fill();

      // Outer Glowing Border
      ctx.lineWidth = 10;
      ctx.strokeStyle = '#F48FB1';
      ctx.stroke();

      // Bold "J" Letter
      ctx.fillStyle = '#FFFFFF';
      ctx.font = 'bold 240px Inter, system-ui, -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('J', size / 2 - 10, size / 2);

      // J Dot (top-right highlight)
      ctx.fillStyle = '#FFFFFF';
      ctx.beginPath();
      ctx.arc(size - 130, 130, 24, 0, Math.PI * 2);
      ctx.fill();

      // Subtle "JELCOS AI" bottom pill badge
      ctx.fillStyle = 'rgba(255, 255, 255, 0.22)';
      ctx.beginPath();
      ctx.roundRect(size / 2 - 90, size - 110, 180, 42, 21);
      ctx.fill();

      ctx.fillStyle = '#FFFFFF';
      ctx.font = 'bold 22px Inter, system-ui, sans-serif';
      ctx.letterSpacing = '3px';
      ctx.fillText('JELCOS AI', size / 2, size - 88);

      return canvas;
    }

    // Helper to generate 3D Decision Node Badges (My Dezider, Pros & Cons, SWOT, etc.)
    function createDecisionNodeTexture(icon: string, title: string, sub: string, color: string) {
      const canvas = document.createElement('canvas');
      canvas.width = 320;
      canvas.height = 140;
      const ctx = canvas.getContext('2d');
      if (!ctx) return null;

      // Dark translucent glass background
      ctx.fillStyle = 'rgba(10, 26, 79, 0.88)';
      ctx.beginPath();
      ctx.roundRect(10, 10, 300, 120, 28);
      ctx.fill();

      // Glowing border
      ctx.lineWidth = 4;
      ctx.strokeStyle = color;
      ctx.stroke();

      // Icon circle
      const grad = ctx.createLinearGradient(30, 30, 90, 90);
      grad.addColorStop(0, color);
      grad.addColorStop(1, '#8E24AA');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(65, 70, 32, 0, Math.PI * 2);
      ctx.fill();

      // Emoji/Icon text
      ctx.fillStyle = '#FFFFFF';
      ctx.font = '28px "Segoe UI Emoji", AppleColorEmoji, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(icon, 65, 71);

      // Title
      ctx.fillStyle = '#FFFFFF';
      ctx.font = 'bold 24px Inter, system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(title, 115, 56);

      // Subtitle / Tag
      ctx.fillStyle = color;
      ctx.font = '600 16px Inter, system-ui, sans-serif';
      ctx.fillText(sub, 115, 86);

      return canvas;
    }

    async function init() {
      try {
        THREE = await import('three');
        if (!isMounted || !containerRef.current) return;

        const container = containerRef.current;
        const width = container.clientWidth || window.innerWidth;
        const height = container.clientHeight || 750;

        // Scene
        scene = new THREE.Scene();
        scene.fog = new THREE.FogExp2(0x0a1a4f, 0.032);

        // Camera
        camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 100);
        camera.position.set(0, 0, 15);

        // WebGL Renderer
        renderer = new THREE.WebGLRenderer({
          alpha: true,
          antialias: true,
          powerPreference: 'high-performance',
        });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(width, height);
        renderer.setClearColor(0x000000, 0);

        const canvas = renderer.domElement;
        canvas.style.position = 'absolute';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.style.pointerEvents = 'none';

        while (container.firstChild) {
          container.removeChild(container.firstChild);
        }
        container.appendChild(canvas);

        // --- Lighting ---
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
        scene.add(ambientLight);

        const pointLight1 = new THREE.PointLight(0xe91e63, 5, 25);
        pointLight1.position.set(4, 4, 6);
        scene.add(pointLight1);

        const pointLight2 = new THREE.PointLight(0x8e24aa, 4, 25);
        pointLight2.position.set(-4, -3, 4);
        scene.add(pointLight2);

        const pointLight3 = new THREE.PointLight(0x00e5ff, 3, 20);
        pointLight3.position.set(0, 5, -2);
        scene.add(pointLight3);

        // --- Main Brand Group ---
        const mainGroup = new THREE.Group();
        const isWideScreen = width >= 1020;
        mainGroup.position.set(isWideScreen ? 3.4 : 0, isWideScreen ? 0.3 : 0, 0);
        scene.add(mainGroup);

        // ==========================================
        // 1. CENTRAL 3D JELCOS LOGO BADGE / PRISM
        // ==========================================
        const badgeCanvas = createJelcosBadgeTexture(512);
        let badgeTexture: any = null;
        if (badgeCanvas) {
          badgeTexture = new THREE.CanvasTexture(badgeCanvas);
          badgeTexture.generateMipmaps = true;
          badgeTexture.minFilter = THREE.LinearMipMapLinearFilter;
        }

        const badgeGeo = new THREE.BoxGeometry(2.4, 2.4, 0.4);
        const badgeSideMat = new THREE.MeshStandardMaterial({
          color: 0x8e24aa,
          metalness: 0.85,
          roughness: 0.2,
          emissive: 0x4a148c,
          emissiveIntensity: 0.4,
        });

        const badgeFaceMat = badgeTexture
          ? new THREE.MeshStandardMaterial({
              map: badgeTexture,
              metalness: 0.4,
              roughness: 0.2,
              transparent: true,
              emissive: 0x221040,
              emissiveIntensity: 0.2,
            })
          : badgeSideMat;

        // Multi-material box: front/back get logo texture, sides get metallic purple
        const badgeMaterials = [
          badgeSideMat, // right
          badgeSideMat, // left
          badgeSideMat, // top
          badgeSideMat, // bottom
          badgeFaceMat, // front
          badgeFaceMat, // back
        ];

        const centralBadge = new THREE.Mesh(badgeGeo, badgeMaterials);
        mainGroup.add(centralBadge);

        // Crystalline Wireframe Cage around the central logo
        const wireGeo = new THREE.IcosahedronGeometry(2.2, 1);
        const wireMat = new THREE.MeshBasicMaterial({
          color: 0xf48fb1,
          wireframe: true,
          transparent: true,
          opacity: 0.35,
        });
        const wireCage = new THREE.Mesh(wireGeo, wireMat);
        mainGroup.add(wireCage);

        // Pulsing light inside central logo
        const innerGlowGeo = new THREE.SphereGeometry(0.8, 16, 16);
        const innerGlowMat = new THREE.MeshBasicMaterial({
          color: 0xff4081,
          transparent: true,
          opacity: 0.4,
        });
        const innerGlow = new THREE.Mesh(innerGlowGeo, innerGlowMat);
        mainGroup.add(innerGlow);

        // Gyroscopic Outer Decision Rings
        const ringGeo = new THREE.TorusGeometry(3.6, 0.022, 16, 100);
        const ring1 = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color: 0xe91e63, transparent: true, opacity: 0.5 }));
        ring1.rotation.x = Math.PI / 3;
        mainGroup.add(ring1);

        const ring2 = new THREE.Mesh(new THREE.TorusGeometry(4.2, 0.022, 16, 100), new THREE.MeshBasicMaterial({ color: 0x8e24aa, transparent: true, opacity: 0.45 }));
        ring2.rotation.y = Math.PI / 4;
        ring2.rotation.z = Math.PI / 6;
        mainGroup.add(ring2);

        const ring3 = new THREE.Mesh(new THREE.TorusGeometry(4.8, 0.022, 16, 100), new THREE.MeshBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.4 }));
        ring3.rotation.x = -Math.PI / 5;
        ring3.rotation.y = Math.PI / 3;
        mainGroup.add(ring3);

        // ==========================================
        // 2. 3D ORBITING DECISION SYSTEM NODES
        // ==========================================
        const decisionModules = [
          { icon: '🎯', title: 'My Dezider', sub: '10-Step Engine', color: '#E91E63', radius: 4.6, speed: 0.007, angle: 0 },
          { icon: '⚖️', title: 'Pros & Cons', sub: 'Weighted Matrix', color: '#00E5FF', radius: 4.8, speed: 0.006, angle: (Math.PI * 2) / 6 },
          { icon: '🧭', title: 'SWOT Analysis', sub: 'Clarity Verdict', color: '#B388FF', radius: 5.0, speed: 0.0075, angle: (Math.PI * 4) / 6 },
          { icon: '💼', title: 'Career & Growth', sub: 'Life Area Score', color: '#FFD740', radius: 4.7, speed: 0.0065, angle: (Math.PI * 6) / 6 },
          { icon: '❤️', title: 'Health & Family', sub: 'Life Area Score', color: '#FF4081', radius: 4.9, speed: 0.007, angle: (Math.PI * 8) / 6 },
          { icon: '⚡', title: 'Action Tracker', sub: 'Who · What · When', color: '#69F0AE', radius: 5.1, speed: 0.008, angle: (Math.PI * 10) / 6 },
        ];

        const nodeSprites: any[] = [];
        const beamLines: any[] = [];

        decisionModules.forEach((mod, idx) => {
          const cvs = createDecisionNodeTexture(mod.icon, mod.title, mod.sub, mod.color);
          if (!cvs) return;

          const tex = new THREE.CanvasTexture(cvs);
          tex.generateMipmaps = true;

          const spriteMat = new THREE.SpriteMaterial({
            map: tex,
            transparent: true,
            opacity: 0.92,
            depthWrite: false,
          });

          const sprite = new THREE.Sprite(spriteMat);
          // Scale proportional to canvas aspect ratio (320x140)
          sprite.scale.set(1.9, 0.83, 1);
          mainGroup.add(sprite);

          // Glowing Synapse Beams connecting from Central Logo to Node
          const lineGeo = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(0, 0, 0),
          ]);
          const lineMat = new THREE.LineBasicMaterial({
            color: new THREE.Color(mod.color),
            transparent: true,
            opacity: 0.45,
            linewidth: 2,
          });
          const line = new THREE.Line(lineGeo, lineMat);
          mainGroup.add(line);

          nodeSprites.push({
            sprite,
            line,
            mod,
            heightOffset: (idx % 2 === 0 ? 0.9 : -0.9) + (Math.sin(idx) * 0.4),
          });
        });

        // ==========================================
        // 3. AMBIENT PARTICLES & NEURAL CONSTELLATION
        // ==========================================
        const starCount = 380;
        const starGeo = new THREE.BufferGeometry();
        const starPos = new Float32Array(starCount * 3);
        for (let i = 0; i < starCount; i++) {
          starPos[i * 3] = (Math.random() - 0.5) * 38;
          starPos[i * 3 + 1] = (Math.random() - 0.5) * 28;
          starPos[i * 3 + 2] = (Math.random() - 0.5) * 20 - 4;
        }
        starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
        const starMat = new THREE.PointsMaterial({
          size: 0.2,
          color: 0xc4b5fd,
          transparent: true,
          opacity: 0.6,
          blending: THREE.AdditiveBlending,
        });
        const starField = new THREE.Points(starGeo, starMat);
        scene.add(starField);

        // ==========================================
        // 4. CYBERNETIC RADAR / DECISION FLOOR
        // ==========================================
        const floorGeo = new THREE.RingGeometry(2.5, 6.5, 32, 4);
        const floorMat = new THREE.MeshBasicMaterial({
          color: 0x8e24aa,
          wireframe: true,
          transparent: true,
          opacity: 0.12,
          side: THREE.DoubleSide,
        });
        const floorMesh = new THREE.Mesh(floorGeo, floorMat);
        floorMesh.rotation.x = Math.PI / 2;
        floorMesh.position.y = -3.8;
        mainGroup.add(floorMesh);

        // Resize Listener
        const handleResize = () => {
          if (!containerRef.current || !renderer || !camera) return;
          const newW = containerRef.current.clientWidth || window.innerWidth;
          const newH = containerRef.current.clientHeight || 750;
          camera.aspect = newW / newH;
          camera.updateProjectionMatrix();
          renderer.setSize(newW, newH);

          const wide = newW >= 1020;
          mainGroup.position.set(wide ? 3.4 : 0, wide ? 0.3 : 0, 0);
        };

        window.addEventListener('resize', handleResize);
        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('touchmove', onTouchMove, { passive: true });

        // ==========================================
        // 5. ANIMATION LOOP
        // ==========================================
        let clock = new THREE.Clock();

        const animate = () => {
          if (!isMounted) return;
          animId = requestAnimationFrame(animate);

          const elapsedTime = clock.getElapsedTime();

          // Smooth lerp mouse tracking
          mouseX += (targetMouseX - mouseX) * 0.04;
          mouseY += (targetMouseY - mouseY) * 0.04;

          // Camera parallax & natural floating oscillation
          camera.position.x = mouseX * 1.6 + Math.sin(elapsedTime * 0.3) * 0.25;
          camera.position.y = -mouseY * 1.1 + Math.cos(elapsedTime * 0.35) * 0.2;
          camera.lookAt(0, 0, 0);

          // Rotate Central JELCOS 3D Badge Prism
          centralBadge.rotation.y = elapsedTime * 0.35 + mouseX * 0.5;
          centralBadge.rotation.x = Math.sin(elapsedTime * 0.5) * 0.12 - mouseY * 0.3;
          centralBadge.rotation.z = Math.cos(elapsedTime * 0.4) * 0.08;

          // Wireframe cage counter-rotation
          wireCage.rotation.x = -elapsedTime * 0.2;
          wireCage.rotation.y = -elapsedTime * 0.3;

          // Pulse inner glow
          const glowScale = 0.85 + Math.sin(elapsedTime * 2.8) * 0.2;
          innerGlow.scale.set(glowScale, glowScale, glowScale);

          // Orbit Rings Rotation
          ring1.rotation.x += 0.007;
          ring1.rotation.y += 0.005;

          ring2.rotation.y += 0.008;
          ring2.rotation.z += 0.006;

          ring3.rotation.x -= 0.006;
          ring3.rotation.z -= 0.008;

          // Rotate floor radar
          floorMesh.rotation.z = elapsedTime * 0.06;

          // Animate Orbiting Decision System Nodes & Laser Synapses
          nodeSprites.forEach((item) => {
            const currentAngle = item.mod.angle + elapsedTime * item.mod.speed * 60;
            const x = Math.cos(currentAngle) * item.mod.radius;
            const z = Math.sin(currentAngle) * (item.mod.radius * 0.7);
            const y = item.heightOffset + Math.sin(elapsedTime * 1.5 + currentAngle) * 0.25;

            item.sprite.position.set(x, y, z);

            // Update Synapse Line from Central Logo (0,0,0) to Node position
            const posAttr = item.line.geometry.attributes.position;
            posAttr.setXYZ(0, 0, 0, 0);
            posAttr.setXYZ(1, x, y, z);
            posAttr.needsUpdate = true;

            // Pulse line opacity
            item.line.material.opacity = 0.25 + Math.sin(elapsedTime * 3 + currentAngle) * 0.2;
          });

          // Gentle ambient stardust drift
          starField.rotation.y = elapsedTime * 0.015;

          renderer.render(scene, camera);
        };

        animate();

        return () => {
          window.removeEventListener('resize', handleResize);
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('touchmove', onTouchMove);
        };
      } catch (err) {
        console.warn('Three.js HeroScene3D initialization failed:', err);
      }
    }

    const cleanupPromise = init();

    return () => {
      isMounted = false;
      if (animId) cancelAnimationFrame(animId);
      cleanupPromise?.then((cleanFn) => cleanFn && cleanFn());
      if (renderer) {
        try {
          renderer.dispose();
          if (renderer.domElement && renderer.domElement.parentNode) {
            renderer.domElement.parentNode.removeChild(renderer.domElement.parentNode);
          }
        } catch {
          // ignore cleanup errors
        }
      }
    };
  }, []);

  if (Platform.OS !== 'web') {
    return null;
  }

  return (
    <View
      style={styles.container}
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    >
      <div
        ref={containerRef as any}
        style={{
          width: '100%',
          height: '100%',
          position: 'absolute',
          top: 0,
          left: 0,
          pointerEvents: 'none',
          overflow: 'hidden',
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    overflow: 'hidden',
    zIndex: 0,
    pointerEvents: 'none',
  },
});
