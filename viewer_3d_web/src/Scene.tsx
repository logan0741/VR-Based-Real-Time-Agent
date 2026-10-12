import { useEffect, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { useFBX } from '@react-three/drei';
import * as THREE from 'three';
import type { PoseFrame } from './hooks/useWebSocketPose';
import { quatFromRodrigues } from './utils/smplMath';

// Standard SMPL-X joint names in order (0-21). Pelvis is 0.
const SMPL_JOINT_NAMES = [
  'pelvis', 'left_hip', 'right_hip', 'spine1', 'left_knee', 'right_knee', 'spine2',
  'left_ankle', 'right_ankle', 'spine3', 'left_foot', 'right_foot', 'neck', 'left_collar',
  'right_collar', 'head', 'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
  'left_wrist', 'right_wrist'
];

export function Scene({ pose }: { pose: PoseFrame | null }) {
  // Load the native SMPL-X FBX model
  const scene = useFBX('/smplx.fbx');

  // Build a lookup table for quick bone access
  const [boneMap, setBoneMap] = useState<{ [key: string]: THREE.Bone }>({});
  const [restPoseMap, setRestPoseMap] = useState<{ [key: string]: THREE.Quaternion }>({});

  useEffect(() => {
    if (!scene) return;
    
    const bMap: { [key: string]: THREE.Bone } = {};
    const rMap: { [key: string]: THREE.Quaternion } = {};
    
    scene.traverse((child) => {
      if ((child as THREE.Bone).isBone) {
        // The FBX might have prefixes like "f_avg_Pelvis" or "Pelvis"
        const boneName = child.name.toLowerCase();
        
        // Find which SMPL joint this matches
        for (let i = 0; i < SMPL_JOINT_NAMES.length; i++) {
          const matchName = SMPL_JOINT_NAMES[i].replace('_', '');
          // Very simple matching heuristic for SMPL-X FBX
          if (boneName.includes(matchName) || 
              boneName.includes(SMPL_JOINT_NAMES[i].split('_').join('')) ||
              (SMPL_JOINT_NAMES[i].includes('left') && boneName.includes('l_') && boneName.includes(SMPL_JOINT_NAMES[i].split('_')[1])) ||
              (SMPL_JOINT_NAMES[i].includes('right') && boneName.includes('r_') && boneName.includes(SMPL_JOINT_NAMES[i].split('_')[1]))
             ) {
             bMap[i.toString()] = child as THREE.Bone;
             rMap[i.toString()] = child.quaternion.clone();
             break;
          }
        }
        
        // Special case for pelvis and root
        if (boneName.includes('pelvis')) {
          bMap['0'] = child as THREE.Bone;
          rMap['0'] = child.quaternion.clone();
        }
      }
    });
    
    // Fallback if matching fails: just use array order
    if (Object.keys(bMap).length < 22) {
      let boneIdx = 0;
      scene.traverse((child) => {
        if ((child as THREE.Bone).isBone && boneIdx < 22) {
          bMap[boneIdx.toString()] = child as THREE.Bone;
          rMap[boneIdx.toString()] = child.quaternion.clone();
          boneIdx++;
        }
      });
    }

    setBoneMap(bMap);
    setRestPoseMap(rMap);
  }, [scene]);

  useFrame(() => {
    if (!pose || !pose.fit || Object.keys(restPoseMap).length === 0) return;

    // Apply global_orient to Pelvis (index 0)
    const go = pose.fit.global_orient;
    if (go && go.length === 3) {
      const pelvis = boneMap['0'];
      if (pelvis) {
        const poseQuat = quatFromRodrigues(go);
        pelvis.quaternion.copy(restPoseMap['0']).multiply(poseQuat);
      }
    }

    // Apply body_pose to each child joint
    const bp = pose.fit.body_pose;
    if (bp && bp.length === 63) {
      for (let i = 0; i < 21; i++) {
        // SMPL-X body_pose index 0 maps to joint index 1 (left_hip)
        const boneIndex = (i + 1).toString();
        const bone = boneMap[boneIndex];
        
        if (bone && restPoseMap[boneIndex]) {
          const jointQuat = quatFromRodrigues([
            bp[i * 3],
            bp[i * 3 + 1],
            bp[i * 3 + 2]
          ]);
          bone.quaternion.copy(restPoseMap[boneIndex]).multiply(jointQuat);
        }
      }
    }
  });

  return (
    <group position={[0, 0, 0]}>
      <primitive object={scene} />
    </group>
  );
}

// Preload the FBX model
useFBX.preload('/smplx.fbx');
