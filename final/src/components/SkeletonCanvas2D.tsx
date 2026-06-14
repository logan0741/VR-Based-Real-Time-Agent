import { useEffect, useRef } from 'react';

const COCO_BONES: [number, number][] = [
  [0, 1], [0, 2], [1, 3], [2, 4],
  [5, 6],
  [5, 7], [7, 9],
  [6, 8], [8, 10],
  [5, 11], [6, 12],
  [11, 12],
  [11, 13], [13, 15],
  [12, 14], [14, 16],
];

const CONF_THRESHOLD = 0.05;
const JOINT_RADIUS = 4;
const BAD_JOINT_RADIUS = 8;

const LEFT_JOINTS = new Set([5, 7, 9, 11, 13, 15]);
const RIGHT_JOINTS = new Set([6, 8, 10, 12, 14, 16]);
const COLOR_CENTER = '#ffffff';
const COLOR_LEFT = '#00ff00';
const COLOR_RIGHT = '#0066ff';
const COLOR_BAD = '#ff2d2d';

function jointColor(idx: number): string {
  if (LEFT_JOINTS.has(idx)) return COLOR_LEFT;
  if (RIGHT_JOINTS.has(idx)) return COLOR_RIGHT;
  return COLOR_CENTER;
}

function boneColor(i: number, j: number, badJoints: Set<number>): string {
  if (badJoints.has(i) || badJoints.has(j)) return COLOR_BAD;
  const iL = LEFT_JOINTS.has(i), iR = RIGHT_JOINTS.has(i);
  const jL = LEFT_JOINTS.has(j), jR = RIGHT_JOINTS.has(j);
  if ((iL && jR) || (iR && jL)) return COLOR_CENTER;
  return jointColor(i);
}

function normalizeToCanvas(
  keypoints: number[][],
  canvasW: number,
  canvasH: number,
  mirror: boolean,
): { x: number; y: number; conf: number }[] {
  const col0 = keypoints.map(kp => kp[0]);
  const col1 = keypoints.map(kp => kp[1]);
  const max0 = Math.max(...col0), min0 = Math.min(...col0);
  const max1 = Math.max(...col1), min1 = Math.min(...col1);
  const allNorm = max0 <= 1.5 && max1 <= 1.5 && min0 >= -0.5 && min1 >= -0.5;
  const range0 = max0 - min0;
  const range1 = max1 - min1;
  const noseCol0 = col0[0];
  const ankleCol0 = Math.max(col0[15] ?? 0, col0[16] ?? 0);
  const yAxisLooksVertical = noseCol0 < ankleCol0 && range0 >= range1 * 1.05;
  const isMoveNetYX = allNorm ? noseCol0 < ankleCol0 : yAxisLooksVertical;

  const pts = keypoints.map(kp => ({
    rawX: isMoveNetYX ? kp[1] : kp[0],
    rawY: isMoveNetYX ? kp[0] : kp[1],
    conf: kp[2] ?? 1,
  }));

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const p of pts) {
    if (p.rawX < minX) minX = p.rawX;
    if (p.rawX > maxX) maxX = p.rawX;
    if (p.rawY < minY) minY = p.rawY;
    if (p.rawY > maxY) maxY = p.rawY;
  }

  let rangeX = maxX - minX || 0.001;
  const rangeY = maxY - minY || 0.001;
  if (rangeX / rangeY < 0.3) {
    const padAmt = (rangeY * 0.3 - rangeX) / 2;
    minX -= padAmt; maxX += padAmt; rangeX = rangeY * 0.3;
  }

  const PAD = 0.1;
  const scaleX = (canvasW * (1 - 2 * PAD)) / rangeX;
  const scaleY = (canvasH * (1 - 2 * PAD)) / rangeY;
  const scale = Math.min(scaleX, scaleY);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;

  return pts.map(p => {
    const x = (p.rawX - cx) * scale + canvasW / 2;
    return {
      x: mirror ? canvasW - x : x,
      y: (p.rawY - cy) * scale + canvasH / 2,
      conf: p.conf,
    };
  });
}

function drawFrame(
  canvas: HTMLCanvasElement,
  keypoints: number[][],
  mirror: boolean,
  badJointsInput: number[] = [],
) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const w = canvas.width, h = canvas.height;

  ctx.clearRect(0, 0, w, h);
  type GradientCanvas = HTMLCanvasElement & {
    __bgGradient?: { w: number; h: number; grad: CanvasGradient };
  };
  const gradientCanvas = canvas as GradientCanvas;
  const cached = gradientCanvas.__bgGradient;
  let grad = cached?.w === w && cached?.h === h ? cached.grad : null;
  if (!grad) {
    grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * 0.7);
    grad.addColorStop(0, '#0d0d18');
    grad.addColorStop(1, '#08080e');
    gradientCanvas.__bgGradient = { w, h, grad };
  }
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  const points = normalizeToCanvas(keypoints, w, h, mirror);
  const badJoints = new Set(badJointsInput);

  ctx.lineWidth = 1;
  ctx.lineCap = 'round';
  for (const [i, j] of COCO_BONES) {
    const p1 = points[i], p2 = points[j];
    if (!p1 || !p2) continue;
    if (p1.conf < CONF_THRESHOLD || p2.conf < CONF_THRESHOLD) continue;
    const isBad = badJoints.has(i) || badJoints.has(j);
    ctx.strokeStyle = boneColor(i, j, badJoints);
    ctx.lineWidth = isBad ? 2.5 : 1.25;
    ctx.globalAlpha = Math.min(p1.conf, p2.conf) < 0.6 ? 0.5 : 0.85;
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.stroke();
  }

  ctx.globalAlpha = 1.0;
  for (let idx = 0; idx < points.length; idx++) {
    const p = points[idx];
    if (!p || p.conf < CONF_THRESHOLD) continue;
    const alpha = p.conf < 0.3 ? 0.3 : p.conf < 0.6 ? 0.6 : 1.0;
    const isBad = badJoints.has(idx);
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    ctx.arc(p.x, p.y, isBad ? BAD_JOINT_RADIUS : JOINT_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = isBad ? COLOR_BAD : jointColor(idx);
    ctx.fill();
  }
  ctx.globalAlpha = 1.0;
}

function clearFrame(canvas: HTMLCanvasElement) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const w = canvas.width, h = canvas.height;

  ctx.clearRect(0, 0, w, h);
  const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * 0.7);
  grad.addColorStop(0, '#0d0d18');
  grad.addColorStop(1, '#08080e');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);
}

const LOGICAL_W = 320;
const LOGICAL_H = 480;

type Props = {
  framesRef?: React.MutableRefObject<number[][][]>;
  framesVersion?: number;
  playbackVersion?: number;
  playbackPhaseMs?: number;
  loading?: boolean;
  keypoints?: number[][] | null;
  badJoints?: number[];
  mirrorVersion?: number;
  fps?: number;
  mirror?: boolean;
  color?: string; // kept for API compat, unused
};

export default function SkeletonCanvas2D({
  framesRef,
  framesVersion = 0,
  playbackVersion = 0,
  playbackPhaseMs = 0,
  loading = false,
  keypoints,
  badJoints = [],
  mirrorVersion = 0,
  fps = 15,
  mirror = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const expertStartLocalMsRef = useRef(performance.now());

  // DPR scaling on mount
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = LOGICAL_W * dpr;
    canvas.height = LOGICAL_H * dpr;
  }, []);

  // Expert loop — Date.now() based so frame rate is stable regardless of interval timing
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (!framesRef) return;

    expertStartLocalMsRef.current = performance.now() - Math.max(0, playbackPhaseMs);

    const initialCanvas = canvasRef.current;
    if (initialCanvas && (loading || framesRef.current.length === 0)) {
      clearFrame(initialCanvas);
    }

    timerRef.current = setInterval(() => {
      const canvas = canvasRef.current;
      const frames = framesRef.current;
      if (!canvas) return;
      if (loading || frames.length === 0) {
        clearFrame(canvas);
        return;
      }
      const elapsedMs = Math.max(0, performance.now() - expertStartLocalMsRef.current);
      const idx = Math.floor(elapsedMs / (1000 / fps)) % frames.length;
      drawFrame(canvas, frames[idx], mirror);
    }, Math.round(1000 / fps));

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [framesRef, framesVersion, playbackVersion, playbackPhaseMs, loading, fps, mirror]);

  // Live pose — redraw on every keypoints update
  useEffect(() => {
    if (!keypoints || !canvasRef.current) return;
    drawFrame(canvasRef.current, keypoints, mirror, badJoints);
  }, [keypoints, mirror, badJoints, mirrorVersion]);

  return (
    <canvas
      ref={canvasRef}
      width={LOGICAL_W}
      height={LOGICAL_H}
      style={{
        display: 'block',
        height: '100%',
        maxHeight: '100%',
        width: 'auto',
        maxWidth: '100%',
        margin: 'auto',
      }}
    />
  );
}
