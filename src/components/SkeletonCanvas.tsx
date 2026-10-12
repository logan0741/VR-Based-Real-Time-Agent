import { useEffect, useRef } from 'react';

const EDGES: [number, number][] = [
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
const PAD = 0.1;
const LOGICAL_W = 320;
const LOGICAL_H = 480;

type Props = {
  keypoints: number[][] | null;
  color?: string;
  mirror?: boolean;
};

export default function SkeletonCanvas({ keypoints, color, mirror = false }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Scale canvas buffer to device pixel ratio once on mount
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    canvas.width = LOGICAL_W * dpr;
    canvas.height = LOGICAL_H * dpr;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    if (!keypoints || keypoints.length < 17) return;
    const kp = keypoints;

    // Bounding-box normalization — centers and fits skeleton with padding.
    // Keypoints are MoveNet [y, x, conf] format (normalized 0–1).
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    for (const p of kp) {
      if (!p || (p[2] ?? 1) < CONF_THRESHOLD) continue;
      const px = p[1]; // x
      const py = p[0]; // y
      if (px < minX) minX = px;
      if (px > maxX) maxX = px;
      if (py < minY) minY = py;
      if (py > maxY) maxY = py;
    }
    if (minX === Infinity) return;

    let rangeX = maxX - minX || 0.001;
    let rangeY = maxY - minY || 0.001;

    // Ensure minimum aspect ratio so side-view poses don't become a thin line
    if (rangeX / rangeY < 0.3) {
      const padX = (rangeY * 0.3 - rangeX) / 2;
      minX -= padX;
      rangeX = rangeY * 0.3;
    }

    const scale = Math.min(
      (w * (1 - 2 * PAD)) / rangeX,
      (h * (1 - 2 * PAD)) / rangeY,
    );
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const toXY = (py: number, px: number) => {
      const x = (px - cx) * scale + w / 2;
      return {
        x: mirror ? w - x : x,
        y: (py - cy) * scale + h / 2,
      };
    };

    // Draw edges
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.globalAlpha = 0.85;
    for (const [a, b] of EDGES) {
      const pa = kp[a];
      const pb = kp[b];
      if (!pa || !pb) continue;
      if ((pa[2] ?? 1) < CONF_THRESHOLD || (pb[2] ?? 1) < CONF_THRESHOLD) continue;
      const { x: ax, y: ay } = toXY(pa[0], pa[1]);
      const { x: bx, y: by } = toXY(pb[0], pb[1]);
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(bx, by);
      ctx.strokeStyle = color ?? '#94a3b8';
      ctx.stroke();
    }

    // Draw joints
    ctx.globalAlpha = 1;
    for (let i = 0; i < 17; i++) {
      const p = kp[i];
      if (!p || (p[2] ?? 1) < CONF_THRESHOLD) continue;
      const { x, y } = toXY(p[0], p[1]);
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fillStyle = color ?? '#94a3b8';
      ctx.fill();
    }
  }, [keypoints, color, mirror]);

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
