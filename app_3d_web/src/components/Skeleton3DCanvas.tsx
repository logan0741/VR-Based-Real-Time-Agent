import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useFBX } from '@react-three/drei';
import * as THREE from 'three';
import { quatFromRodrigues } from '../utils/smplMath';
import type { ExpertSmplxFrame } from '../hooks/useExpertPose';

const SMPL_JOINT_NAMES = [
  'pelvis', 'left_hip', 'right_hip', 'spine1', 'left_knee', 'right_knee', 'spine2',
  'left_ankle', 'right_ankle', 'spine3', 'left_foot', 'right_foot', 'neck', 'left_collar',
  'right_collar', 'head', 'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
  'left_wrist', 'right_wrist'
];

// 매 렌더 프레임마다 현재 쿼터니언에서 목표로 이 비율만큼 이동 (60fps 기준 약 0.2초에 안정)
const SLERP_FACTOR = 0.18;

type Props = {
  poseData?: { global_orient?: number[]; body_pose?: number[]; } | null;
  framesRef?: React.MutableRefObject<ExpertSmplxFrame[]>;
  fps?: number;
  color?: string;
};

function Model({ poseData, framesRef, fps = 8, color }: Props) {
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
    return cloned;
  }, [originalScene]);

  const [boneMap, setBoneMap] = useState<{ [key: string]: THREE.Bone }>({});
  const [restPoseMap, setRestPoseMap] = useState<{ [key: string]: THREE.Quaternion }>({});

  // 이전 프레임의 쿼터니언 — SLERP 기준점
  const smoothedQuatRef = useRef<Map<string, THREE.Quaternion>>(new Map());

  useEffect(() => {
    if (!scene) return;

    if (color) {
      scene.traverse((child) => {
        if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
          const mesh = child as THREE.SkinnedMesh;
          if (mesh.material) {
            const mat = (mesh.material as THREE.MeshStandardMaterial).clone();
            mat.color = new THREE.Color(color);
            mat.needsUpdate = true;
            mesh.material = mat;
          }
        }
      });
    }

    const bMap: { [key: string]: THREE.Bone } = {};
    const rMap: { [key: string]: THREE.Quaternion } = {};
    scene.traverse((child) => {
      if ((child as THREE.Bone).isBone) {
        const boneName = child.name.toLowerCase();
        for (let i = 0; i < SMPL_JOINT_NAMES.length; i++) {
          if (boneName === SMPL_JOINT_NAMES[i]) {
            bMap[i.toString()] = child as THREE.Bone;
            rMap[i.toString()] = child.quaternion.clone();
            break;
          }
        }
      }
    });

    setBoneMap(bMap);
    setRestPoseMap(rMap);
    smoothedQuatRef.current.clear();
  }, [scene, color]);

  const applyPoseSlerp = (data: { global_orient?: number[]; body_pose?: number[] } | null) => {
    if (!data || Object.keys(restPoseMap).length === 0) return;
    const smoothed = smoothedQuatRef.current;

    const applyBone = (key: string, targetQuat: THREE.Quaternion) => {
      const bone = boneMap[key];
      if (!bone) return;
      const prev = smoothed.get(key);
      if (prev) {
        bone.quaternion.copy(prev).slerp(targetQuat, SLERP_FACTOR);
      } else {
        bone.quaternion.copy(targetQuat);
      }
      smoothed.set(key, bone.quaternion.clone());
    };

    // global_orient: 도메인 불일치(학습 카메라 vs 추론 카메라)로 부정확 — pelvis 수직 고정
    const pelvis = boneMap['0'];
    if (pelvis) {
      const rest0 = restPoseMap['0'];
      if (rest0) {
        const prev = smoothedQuatRef.current.get('0');
        const target = rest0.clone();
        pelvis.quaternion.copy(prev ?? target).slerp(target, SLERP_FACTOR);
        smoothedQuatRef.current.set('0', pelvis.quaternion.clone());
      }
    }

    const bp = data.body_pose;
    if (bp && bp.length === 63) {
      for (let i = 0; i < 21; i++) {
        const key = (i + 1).toString();
        const rest = restPoseMap[key];
        if (!rest) continue;
        const target = rest.clone().multiply(
          quatFromRodrigues([bp[i * 3], bp[i * 3 + 1], bp[i * 3 + 2]])
        );
        applyBone(key, target);
      }
    }
  };

  useFrame(() => {
    if (framesRef) {
      const frames = framesRef.current;
      if (frames.length === 0) return;
      // 프레임 보간: 두 keyframe 사이를 alpha로 lerp 후 SLERP 적용
      const t = Date.now() / (1000 / fps);
      const idx = Math.floor(t) % frames.length;
      const nextIdx = (idx + 1) % frames.length;
      const alpha = t - Math.floor(t);
      const curr = frames[idx];
      const next = frames[nextIdx];
      applyPoseSlerp({
        global_orient: curr.global_orient.map((v, i) => v + (next.global_orient[i] - v) * alpha),
        body_pose: curr.body_pose.map((v, i) => v + (next.body_pose[i] - v) * alpha),
      });
    } else {
      applyPoseSlerp(poseData ?? null);
    }
  });

  return (
    <group position={[0, 0, 0]}>
      <primitive object={scene} />
    </group>
  );
}

export default function Skeleton3DCanvas({ poseData, framesRef, fps, color }: Props) {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <Canvas camera={{ position: [0, 0.9, 2.5], fov: 50 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[2, 5, 2]} intensity={1.5} />
        <directionalLight position={[-2, -5, -2]} intensity={0.5} />
        <OrbitControls target={[0, 0.85, 0]} enableDamping={false} enableZoom={true} enablePan={true} />
        <Suspense fallback={null}>
          <Model poseData={poseData} framesRef={framesRef} fps={fps} color={color} />
        </Suspense>
        <gridHelper args={[4, 20, '#444', '#333']} />
      </Canvas>
    </div>
  );
}
