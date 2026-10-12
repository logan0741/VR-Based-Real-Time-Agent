/**
 * Skeleton3DCanvasV2 — geometric IK from 3D joint coordinates
 *
 * At FBX load time, for each bone we read the rest-pose bone direction
 * (child_world_pos - parent_world_pos) and rest world quaternion from the FBX.
 *
 * Per frame:
 *   Q_delta      = setFromUnitVectors(D_rest, D_actual)
 *   Q_new_world  = Q_delta × Q_bone_rest_world   ← preserves bone twist at rest
 *   Q_new_local  = inv(parent_world_current) × Q_new_world
 */
import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useFBX } from '@react-three/drei';
import * as THREE from 'three';
import type { Pose3DFrame } from '../hooks/useExpertPose3d';

const SLERP = 0.35;

const J = {
  // Lower body
  LHip: 11, RHip: 12, LKnee: 13, RKnee: 14, LAnk: 15, RAnk: 16,
  // Upper body (COCO-17)
  LSho: 5, RSho: 6, LElb: 7, RElb: 8, LWri: 9, RWri: 10,
} as const;

type BoneConfig = {
  bone: string;
  childBone: string;
  p: number | number[];  // single joint index OR array of indices to average
  c: number | number[];
};

const BONE_MAP: BoneConfig[] = [
  // Lower body
  { bone: 'left_hip',      childBone: 'left_knee',    p: J.LHip,  c: J.LKnee },
  { bone: 'right_hip',     childBone: 'right_knee',   p: J.RHip,  c: J.RKnee },
  { bone: 'left_knee',     childBone: 'left_ankle',   p: J.LKnee, c: J.LAnk  },
  { bone: 'right_knee',    childBone: 'right_ankle',  p: J.RKnee, c: J.RAnk  },
  // Upper arms only (elbow→wrist excluded: wrist moves too freely)
  { bone: 'left_shoulder',  childBone: 'left_elbow',   p: J.LSho,  c: J.LElb  },
  { bone: 'right_shoulder', childBone: 'right_elbow',  p: J.RSho,  c: J.RElb  },
];

/** Convert 3D coord from MotionBERT (x=right, y=down↓, z=depth) → Three.js (Y-up). */
function toThreeJS(pt: number[]): THREE.Vector3 {
  return new THREE.Vector3(pt[0], -pt[1], pt[2]);
}

type BoneRest = {
  worldQuat: THREE.Quaternion;
  worldDir:  THREE.Vector3;
};

type Props = {
  framesRef?: React.MutableRefObject<Pose3DFrame[]>;
  poseData3d?: Pose3DFrame | null;
  fps?: number;
  color?: string;
};

function Model3D({ framesRef, poseData3d, fps = 8, color }: Props) {
  const originalScene = useFBX(`${import.meta.env.BASE_URL}smplx.fbx`);

  const scene = useMemo(() => {
    const cloned = originalScene.clone(true);
    const clonedBones: THREE.Bone[] = [];
    cloned.traverse((child) => {
      if ((child as THREE.Bone).isBone) clonedBones.push(child as THREE.Bone);
    });
    cloned.traverse((child) => {
      if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
        const mesh = child as THREE.SkinnedMesh;
        const origBoneNames = mesh.skeleton.bones.map((b) => b.name);
        const newBones = origBoneNames
          .map((name) => clonedBones.find((b) => b.name === name)!)
          .filter(Boolean);
        if (newBones.length === origBoneNames.length) {
          mesh.skeleton = new THREE.Skeleton(newBones);
          mesh.bind(mesh.skeleton);
        }
      }
    });
    return cloned as THREE.Group;
  }, [originalScene]);

  const boneMapRef  = useRef<Record<string, THREE.Bone>>({});
  const restDataRef = useRef<Record<string, BoneRest>>({});
  const smoothRef   = useRef<Map<string, THREE.Quaternion>>(new Map());
  // Timing: start from frame 0 when frames first become available
  const startTimeRef  = useRef<number>(0);
  const hasStartedRef = useRef<boolean>(false);

  useEffect(() => {
    if (!scene) return;

    if (color) {
      scene.traverse((c) => {
        if ((c as THREE.SkinnedMesh).isSkinnedMesh) {
          const m = c as THREE.SkinnedMesh;
          if (m.material) {
            const mat = (m.material as THREE.MeshStandardMaterial).clone();
            mat.color = new THREE.Color(color); mat.needsUpdate = true; m.material = mat;
          }
        }
      });
    }

    const bm: Record<string, THREE.Bone> = {};
    scene.traverse((c) => {
      if ((c as THREE.Bone).isBone) bm[c.name.toLowerCase()] = c as THREE.Bone;
    });
    boneMapRef.current = bm;

    scene.updateMatrixWorld(true);

    const rd: Record<string, BoneRest> = {};
    const _wp = new THREE.Vector3();
    const _cp = new THREE.Vector3();
    const _wq = new THREE.Quaternion();

    for (const cfg of BONE_MAP) {
      const bone      = bm[cfg.bone];
      const childBone = bm[cfg.childBone];
      if (!bone || !childBone) {
        console.warn(`[V2] bone not found: ${cfg.bone} or ${cfg.childBone}`);
        continue;
      }
      bone.getWorldPosition(_wp);
      childBone.getWorldPosition(_cp);
      const dir = _cp.clone().sub(_wp).normalize();
      bone.getWorldQuaternion(_wq);
      rd[cfg.bone] = { worldQuat: _wq.clone(), worldDir: dir.clone() };
    }
    restDataRef.current = rd;
    smoothRef.current.clear();
    hasStartedRef.current = false;
  }, [scene, color]);

  const _actual       = useMemo(() => new THREE.Vector3(), []);
  const _deltaQuat    = useMemo(() => new THREE.Quaternion(), []);
  const _newWorldQuat = useMemo(() => new THREE.Quaternion(), []);
  const _parentWorldQ = useMemo(() => new THREE.Quaternion(), []);
  const _localQuat    = useMemo(() => new THREE.Quaternion(), []);
  const _ankleWP      = useMemo(() => new THREE.Vector3(), []);

  // Y-position of ankle bones in FBX T-pose (world space, scene at y=0)
  const FBX_ANKLE_Y = 0.076;

  const getJointPos = (frame: Pose3DFrame, idx: number | number[]): THREE.Vector3 => {
    if (Array.isArray(idx)) {
      const sum = new THREE.Vector3();
      for (const i of idx) {
        const pt = frame[i];
        if (pt) sum.add(toThreeJS(pt));
      }
      return sum.divideScalar(idx.length);
    }
    return toThreeJS(frame[idx]);
  };

  const applyFrame = (frame: Pose3DFrame) => {
    const bm = boneMapRef.current;
    const rd = restDataRef.current;
    if (!frame || Object.keys(bm).length === 0) return;
    const sm = smoothRef.current;

    for (const cfg of BONE_MAP) {
      const bone = bm[cfg.bone];
      const rest = rd[cfg.bone];
      if (!bone || !rest) continue;

      const pPos = getJointPos(frame, cfg.p);
      const cPos = getJointPos(frame, cfg.c);

      _actual.copy(cPos).sub(pPos);
      const len = _actual.length();
      if (len < 1e-6) continue;
      _actual.divideScalar(len);

      _deltaQuat.setFromUnitVectors(rest.worldDir, _actual);
      _newWorldQuat.copy(_deltaQuat).multiply(rest.worldQuat);

      if (bone.parent) {
        bone.parent.getWorldQuaternion(_parentWorldQ);
        _localQuat.copy(_parentWorldQ).invert().multiply(_newWorldQuat);
      } else {
        _localQuat.copy(_newWorldQuat);
      }

      const prev = sm.get(cfg.bone);
      bone.quaternion.copy(prev ?? _localQuat).slerp(_localQuat, SLERP);
      sm.set(cfg.bone, bone.quaternion.clone());

      bone.updateMatrix();
      bone.updateMatrixWorld(true);
    }

    // Foot grounding: translate scene so the lowest ankle stays at floor level.
    // Must reset scene Y first so getWorldPosition is scene-space-independent.
    scene.position.y = 0;
    scene.updateMatrixWorld(true);
    const ankleL = bm['left_ankle'];
    const ankleR = bm['right_ankle'];
    if (ankleL && ankleR) {
      ankleL.getWorldPosition(_ankleWP);
      const lyL = _ankleWP.y;
      ankleR.getWorldPosition(_ankleWP);
      const lyR = _ankleWP.y;
      const lowestAnkle = Math.min(lyL, lyR);
      scene.position.y = FBX_ANKLE_Y - lowestAnkle;
    }
  };

  useFrame(() => {
    if (framesRef) {
      const frames = framesRef.current;
      if (frames.length === 0) return;
      // Start from frame 0 when frames first load
      if (!hasStartedRef.current) {
        startTimeRef.current = Date.now();
        hasStartedRef.current = true;
      }
      const t  = (Date.now() - startTimeRef.current) / (1000 / fps);
      const i0 = Math.floor(t) % frames.length;
      const i1 = (i0 + 1) % frames.length;
      const a  = t - Math.floor(t);
      const interp = frames[i0].map((j, ji) =>
        j.map((v, vi) => v + (frames[i1][ji][vi] - v) * a)
      ) as Pose3DFrame;
      applyFrame(interp);
    } else if (poseData3d) {
      applyFrame(poseData3d);
    }
  });

  return (
    <group position={[0, 0, 0]}>
      <primitive object={scene} />
    </group>
  );
}

export default function Skeleton3DCanvasV2({ framesRef, poseData3d, fps, color }: Props) {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <Canvas camera={{ position: [0, 0.9, 2.5], fov: 50 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[2, 5, 2]} intensity={1.5} />
        <directionalLight position={[-2, 5, -2]} intensity={0.8} />
        <OrbitControls target={[0, 0.85, 0]} enableDamping={false} enableZoom enablePan />
        <Suspense fallback={null}>
          <Model3D framesRef={framesRef} poseData3d={poseData3d} fps={fps} color={color} />
        </Suspense>
        <gridHelper args={[4, 20, '#444', '#333']} />
      </Canvas>
    </div>
  );
}
