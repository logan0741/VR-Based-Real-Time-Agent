import { useCallback, useRef, useState } from 'react';

const SEND_INTERVAL_MS = 33;

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    tf: any;
    poseDetection: any;
  }
}

export function useCamera(onKeypoints: (payload: number[][]) => void) {
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraStatus, setCameraStatus] = useState<string>('');
  const detectorRef = useRef<any>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const runningRef = useRef(false);
  const lastSendRef = useRef(0);
  const onKeypointsRef = useRef(onKeypoints);
  onKeypointsRef.current = onKeypoints;

  const startCamera = useCallback(async (videoEl: HTMLVideoElement) => {
    if (runningRef.current) return;
    setCameraStatus('모델 로딩...');
    try {
      if (!detectorRef.current) {
        await window.tf.ready();
        detectorRef.current = await window.poseDetection.createDetector(
          window.poseDetection.SupportedModels.MoveNet,
          { modelType: window.poseDetection.movenet.modelType.SINGLEPOSE_LIGHTNING },
        );
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
      });
      videoEl.srcObject = stream;
      await new Promise<void>((res, rej) => {
        videoEl.onloadeddata = () => res();
        videoEl.onerror = () => rej(new Error('Video load error'));
      });
      await videoEl.play();

      videoRef.current = videoEl;
      runningRef.current = true;
      setCameraActive(true);
      setCameraStatus('카메라 ON');

      const detect = async () => {
        if (!runningRef.current || !detectorRef.current) return;
        const now = performance.now();
        if (now - lastSendRef.current >= SEND_INTERVAL_MS && videoEl.readyState >= 2) {
          try {
            const poses = await detectorRef.current.estimatePoses(videoEl);
            if (poses && poses.length > 0) {
              const vw = videoEl.videoWidth || 640;
              const vh = videoEl.videoHeight || 480;
              const payload = poses[0].keypoints.map((kp: any) => [
                kp.y / vh,
                kp.x / vw,
                kp.score ?? 0.9,
              ]);
              onKeypointsRef.current(payload);
              lastSendRef.current = now;
            }
          } catch {
            // inference error on single frame — continue loop
          }
        }
        requestAnimationFrame(detect);
      };
      detect();
    } catch (err: any) {
      setCameraStatus(`오류: ${err.message ?? '알 수 없는 오류'}`);
      runningRef.current = false;
      setCameraActive(false);
    }
  }, []);

  const stopCamera = useCallback(() => {
    runningRef.current = false;
    const video = videoRef.current;
    if (video?.srcObject) {
      (video.srcObject as MediaStream).getTracks().forEach((t) => t.stop());
      video.srcObject = null;
    }
    setCameraActive(false);
    setCameraStatus('');
  }, []);

  return { cameraActive, cameraStatus, startCamera, stopCamera };
}
