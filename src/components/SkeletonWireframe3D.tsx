/**
 * SkeletonWireframe3D — pure geometric skeleton renderer (Approach V3)
 *
 * Renders COCO-17 3D joint coordinates directly as spheres (joints) + lines
 * (bones) using R3F/Three.js. No FBX avatar, no IK — just the raw lifted pose.
 *
 * 3D coord system from MotionBERT:  x=right, y=down↓, z=depth
 * Three.js coord system:            Y-up
 * Mapping: [3d_x → Tx, -3d_y → Ty, 3d_z → Tz]
 */
import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { Pose3DFrame } from '../hooks/useExpertPose3d';

// COCO-17 bone connections (pairs of joint indices)
const BONES: [number, number][] = [
  [5, 6], [5, 7], [7, 9], [6, 8], [8, 10], // arms
  [5, 11], [6, 12], [11, 12],              // torso
  [11, 13], [13, 15], [12, 14], [14, 16],  // legs
  [0, 5], [0, 6],                          // head-to-shoulders (simplified)
];

const NUM_JOINTS = 17;

const SCALE = 1.0; // MotionBERT output is already in ~meters

/** Convert 3D coord from MotionBERT (x=right, y=down↓, z=depth) → Three.js (Y-up).
 *  origin: pelvis center of the frame (subtracted before scaling). */
function toThreeJS(pt: number[], origin: number[], out?: THREE.Vector3): THREE.Vector3 {
  const v = out ?? new THREE.Vector3();
  return v.set(
    (pt[0] - origin[0]) * SCALE,
    -(pt[1] - origin[1]) * SCALE,
    (pt[2] - origin[2]) * SCALE,
  );
}

function pelvisCenter(frame: Pose3DFrame): number[] {
  const lh = frame[11]; const rh = frame[12];
  return [(lh[0] + rh[0]) / 2, (lh[1] + rh[1]) / 2, (lh[2] + rh[2]) / 2];
}

type Props = {
  framesRef?: React.MutableRefObject<Pose3DFrame[]>;
  poseData3d?: Pose3DFrame | null;
  fps?: number;
  color?: string;
};

function WireframeModel({ framesRef, poseData3d, fps = 8, color }: Props) {
  const groupRef = useRef<THREE.Group>(null);
  const jointMeshesRef = useRef<THREE.Mesh[]>([]);
  const boneLinesRef = useRef<THREE.Line[]>([]);

  const resolvedColor = color ?? '#60a5fa';

  // Reusable temp vectors to avoid GC churn in useFrame
  const _a = useMemo(() => new THREE.Vector3(), []);
  const _b = useMemo(() => new THREE.Vector3(), []);

  // Build the joint meshes + bone lines once on mount (and when color changes).
  useEffect(() => {
    const group = groupRef.current;
    if (!group) return;

    // Clear any previous children (e.g. on color change / hot reload)
    for (const m of jointMeshesRef.current) {
      m.geometry.dispose();
      (m.material as THREE.Material).dispose();
    }
    for (const l of boneLinesRef.current) {
      l.geometry.dispose();
      (l.material as THREE.Material).dispose();
    }
    group.clear();

    const threeColor = new THREE.Color(resolvedColor);

    // Joints as spheres
    const joints: THREE.Mesh[] = [];
    const sphereGeo = new THREE.SphereGeometry(0.03, 8, 8);
    for (let i = 0; i < NUM_JOINTS; i++) {
      const mat = new THREE.MeshStandardMaterial({ color: threeColor });
      const mesh = new THREE.Mesh(sphereGeo, mat);
      mesh.visible = false;
      group.add(mesh);
      joints.push(mesh);
    }
    jointMeshesRef.current = joints;

    // Bones as lines
    const lines: THREE.Line[] = [];
    for (let b = 0; b < BONES.length; b++) {
      const geo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(),
        new THREE.Vector3(),
      ]);
      const mat = new THREE.LineBasicMaterial({
        color: threeColor,
        opacity: 0.8,
        transparent: true,
      });
      const line = new THREE.Line(geo, mat);
      line.visible = false;
      group.add(line);
      lines.push(line);
    }
    boneLinesRef.current = lines;

    return () => {
      sphereGeo.dispose();
      for (const m of joints) (m.material as THREE.Material).dispose();
      for (const l of lines) {
        l.geometry.dispose();
        (l.material as THREE.Material).dispose();
      }
      group.clear();
      jointMeshesRef.current = [];
      boneLinesRef.current = [];
    };
  }, [resolvedColor]);

  const applyFrame = (frame: Pose3DFrame | null | undefined) => {
    const joints = jointMeshesRef.current;
    const lines = boneLinesRef.current;
    if (!frame || joints.length === 0) {
      for (const m of joints) m.visible = false;
      for (const l of lines) l.visible = false;
      return;
    }

    const origin = pelvisCenter(frame);

    // Update joint sphere positions
    for (let i = 0; i < NUM_JOINTS; i++) {
      const mesh = joints[i];
      const pt = frame[i];
      if (!mesh) continue;
      if (!pt) {
        mesh.visible = false;
        continue;
      }
      toThreeJS(pt, origin, mesh.position);
      mesh.visible = true;
    }

    // Update bone line endpoints
    for (let b = 0; b < BONES.length; b++) {
      const line = lines[b];
      if (!line) continue;
      const [i, j] = BONES[b];
      const pi = frame[i];
      const pj = frame[j];
      if (!pi || !pj) {
        line.visible = false;
        continue;
      }
      toThreeJS(pi, origin, _a);
      toThreeJS(pj, origin, _b);
      const pos = line.geometry.getAttribute('position') as THREE.BufferAttribute;
      pos.setXYZ(0, _a.x, _a.y, _a.z);
      pos.setXYZ(1, _b.x, _b.y, _b.z);
      pos.needsUpdate = true;
      line.geometry.computeBoundingSphere();
      line.visible = true;
    }
  };

  useFrame(() => {
    if (framesRef) {
      const frames = framesRef.current;
      if (frames.length === 0) {
        applyFrame(null);
        return;
      }
      const t = Date.now() / (1000 / fps);
      const i0 = Math.floor(t) % frames.length;
      const i1 = (i0 + 1) % frames.length;
      const a = t - Math.floor(t);
      const interp = frames[i0].map((j, ji) =>
        j.map((v, vi) => v + (frames[i1][ji][vi] - v) * a)
      ) as Pose3DFrame;
      applyFrame(interp);
    } else {
      applyFrame(poseData3d ?? null);
    }
  });

  return <group ref={groupRef} position={[0, 0, 0]} />;
}

export default function SkeletonWireframe3D({ framesRef, poseData3d, fps, color }: Props) {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <Canvas camera={{ position: [0, 0, 3.5], fov: 50 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[2, 5, 2]} intensity={1.5} />
        <directionalLight position={[-2, -5, -2]} intensity={0.5} />
        <OrbitControls target={[0, 0, 0]} enableDamping={false} enableZoom enablePan />
        <Suspense fallback={null}>
          <WireframeModel framesRef={framesRef} poseData3d={poseData3d} fps={fps} color={color} />
        </Suspense>
        <gridHelper args={[4, 20, '#444', '#333']} />
      </Canvas>
    </div>
  );
}
