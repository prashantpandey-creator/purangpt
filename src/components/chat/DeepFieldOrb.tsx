"use client";

/**
 * DeepFieldOrb — the bindu rendered as a real r3f scene (iOS-gated, lazy-loaded).
 *
 * We do NOT throw away the tuned bindu: the proven ITER_E2 fragment shader is
 * reused verbatim on a 3D plane, given only a standard MVP vertex shader so the
 * camera can move around it. Around that we add the genuinely game-grade layer:
 * an instanced particle depth field, a slow camera drift (parallax), and Bloom +
 * Vignette post-processing. This is the one place r3f earns its bundle weight.
 *
 * Perf notes for the iOS WebView: ONE Canvas, dpr capped at 2, no DepthOfField
 * (its blur pass is the expensive one and meaningless on a flat orb), particles
 * are a single Points draw. Honours Reduce Motion (still frame, no drift).
 */

import { useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { EffectComposer, Bloom, Vignette } from "@react-three/postprocessing";
import * as THREE from "three";
import { ITER_GURUJI_LATENT } from "@/lib/binduShaders";

// Standard MVP vertex shader — three binds position/uv/matrices for a
// RawShaderMaterial when they're declared by these names. Passes v_uv to ITER_GURUJI_LATENT.
// NOTE: no `#version` here — three prepends `#version 300 es` itself when
// glslVersion: GLSL3 is set; a second one is a compile error.
const ORB_VS = /* glsl */ `
in vec3 position;
in vec2 uv;
uniform mat4 modelViewMatrix;
uniform mat4 projectionMatrix;
out vec2 v_uv;
void main() {
  v_uv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const ORB_FS = ITER_GURUJI_LATENT.replace(/^\s*#version[^\n]*\n/, "");

/** The bindu plane — proven shader, seated slightly high so the core rides the
 *  upper signal band, never dead-centre behind the reading column. */
function OrbPlane({ level, reduceMotion, latentVector }: { level: number; reduceMotion: boolean; latentVector?: number[] | null }) {
  // We map the 384-dimensional embedding to a 24x16 floating-point texture.
  const texWidth = 24;
  const texHeight = 16;
  const texSize = texWidth * texHeight; // 384 floats
  
  // Ref to hold the current GPU-side float data for lerping
  const latentDataRef = useRef<Float32Array>(new Float32Array(texSize));
  
  const latentTexture = useMemo(() => {
    // Initialize with zeros
    const data = new Float32Array(texSize);
    // Use RedFormat/FloatType since we're just passing raw single floats per pixel
    const texture = new THREE.DataTexture(data, texWidth, texHeight, THREE.RedFormat, THREE.FloatType);
    texture.minFilter = THREE.LinearFilter;
    texture.magFilter = THREE.LinearFilter;
    texture.needsUpdate = true;
    return texture;
  }, [texSize]);

  const material = useMemo(
    () =>
      new THREE.RawShaderMaterial({
        vertexShader: ORB_VS,
        fragmentShader: ORB_FS,
        glslVersion: THREE.GLSL3,
        uniforms: { 
          u_t: { value: 0 }, 
          u_lv: { value: 0 },
          u_latent: { value: latentTexture }
        },
        transparent: true,
        depthWrite: false,
        depthTest: false,
      }),
    [latentTexture]
  );

  useFrame((state) => {
    if (!reduceMotion) material.uniforms.u_t.value = state.clock.elapsedTime;
    // Ease the intelligence level toward the target (brighten on think).
    material.uniforms.u_lv.value +=
      (level - material.uniforms.u_lv.value) * 0.05;

    // Smoothly morph the latent space texture
    if (latentVector && latentVector.length >= texSize) {
      const currentData = latentDataRef.current;
      let changed = false;
      for (let i = 0; i < texSize; i++) {
        const target = latentVector[i];
        const diff = target - currentData[i];
        // Only update if there's a meaningful delta, lerp by 2% per frame (~1 sec transition at 60fps)
        if (Math.abs(diff) > 0.001) {
          currentData[i] += diff * 0.02;
          changed = true;
        }
      }
      if (changed) {
        latentTexture.image.data.set(currentData);
        latentTexture.needsUpdate = true;
      }
    }
  });
  // Sized so the orb RECEDES into the void (Deep Field), framed by dark + the
  // particle field — not filling the screen. Seated high (y=+0.5). renderOrder
  // -10 keeps it behind the particles.
  // Sized to fill the viewport: the plane's UV edges (where the gravity-wave
  // crests travel) sit near the screen corners, so the reverberation washes the
  // whole UI. The bindu/plasma stays focal — it lives in the centre of the UV.
  return (
    <mesh material={material} position={[0, 0.35, 0]} renderOrder={-10} frustumCulled={false}>
      <planeGeometry args={[4.0, 4.0]} />
    </mesh>
  );
}

/** An instanced ember/star field giving the void real depth + parallax. One
 *  Points draw, additive, gently rotating. */
function ParticleField({ reduceMotion }: { reduceMotion: boolean }) {
  const ref = useRef<THREE.Points>(null);
  const geometry = useMemo(() => {
    const N = 320;
    const pos = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      // Spread across a wide, deep box around the orb.
      pos[i * 3 + 0] = (Math.sin(i * 12.9898) * 43758.5453 % 1) * 8 - 4;
      pos[i * 3 + 1] = (Math.sin(i * 78.233) * 12543.4321 % 1) * 8 - 3.5;
      pos[i * 3 + 2] = (Math.sin(i * 39.425) * 23421.6313 % 1) * 5 - 4;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return g;
  }, []);
  const material = useMemo(
    () =>
      new THREE.PointsMaterial({
        size: 0.022,
        color: new THREE.Color(0xcba455),
        transparent: true,
        opacity: 0.55,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        sizeAttenuation: true,
      }),
    []
  );
  useFrame((state) => {
    if (ref.current && !reduceMotion) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.01;
      ref.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.05) * 0.04;
    }
  });
  return <points ref={ref} geometry={geometry} material={material} />;
}

/** Slow parallax camera drift — the "standing before it" feel. */
function CameraDrift({ reduceMotion }: { reduceMotion: boolean }) {
  const { camera } = useThree();
  useFrame((state) => {
    if (reduceMotion) return;
    const t = state.clock.elapsedTime;
    camera.position.x = Math.sin(t * 0.06) * 0.18;
    camera.position.y = 0.55 + Math.cos(t * 0.05) * 0.12;
    camera.lookAt(0, 0.55, 0);
  });
  return null;
}

export default function DeepFieldOrb({
  level,
  reduceMotion = false,
  latentVector,
}: {
  level: number;
  reduceMotion?: boolean;
  latentVector?: number[] | null;
}) {
  return (
    <Canvas
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ position: [0, 0.55, 4.2], fov: 44 }}
      dpr={[1, 2]}
      style={{ width: "100%", height: "100%" }}
    >
      <OrbPlane level={level} reduceMotion={reduceMotion} latentVector={latentVector} />
      <ParticleField reduceMotion={reduceMotion} />
      <CameraDrift reduceMotion={reduceMotion} />
      <EffectComposer>
        <Bloom
          intensity={0.5}
          luminanceThreshold={0.34}
          luminanceSmoothing={0.25}
          mipmapBlur
        />
        <Vignette eskil={false} offset={0.42} darkness={0.5} />
      </EffectComposer>
    </Canvas>
  );
}
