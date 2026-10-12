import { useEffect, useRef } from 'react';

// COCO-17 joint index → name
export const COCO17 = [
  'Nose','LeftEye','RightEye','LeftEar','RightEar',
  'LeftShoulder','RightShoulder','LeftElbow','RightElbow',
  'LeftWrist','RightWrist','LeftHip','RightHip',
  'LeftKnee','RightKnee','LeftAnkle','RightAnkle',
] as const;

export type Pose3DFrame = number[][]; // shape (17, 3): [x, y, z] per joint

export function useExpertPose3d() {
  const framesRef = useRef<Pose3DFrame[]>([]);

  useEffect(() => {
    fetch('/api/expert-pose3d')
      .then((r) => r.json())
      .then((data) => {
        if (data.status === 'ok' && Array.isArray(data.frames)) {
          framesRef.current = data.frames as Pose3DFrame[];
        }
      })
      .catch(() => {});
  }, []);

  return framesRef;
}
