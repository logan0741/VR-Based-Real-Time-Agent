"""
MotionBERT-Lite로 squat_expert_keypoints.json을 3D로 변환.
출력: squat_expert_keypoints_3d_mb.json  (COCO-17 순서, H36M 좌표계)

H36M 좌표계: x=lateral(right+), y=height(up+), z=depth(forward-)
toThreeJS(pt): new THREE.Vector3(pt[0], pt[1], pt[2])  ← Y-up 그대로 사용
"""

import sys, json, os
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MotionBERT'))

from lib.utils.tools import get_config
from lib.utils.learning import load_backbone
from lib.utils.utils_data import flip_data

# ────────────────────────────────────────────────────────────────────────────
# 1. COCO-17 → H36M-17 변환
# H36M: 0=Pelvis,1=RHip,2=RKnee,3=RAnkle,4=LHip,5=LKnee,6=LAnkle,
#       7=Spine,8=Thorax,9=Nose,10=Head,
#       11=LShoulder,12=LElbow,13=LWrist,14=RShoulder,15=RElbow,16=RWrist
# ────────────────────────────────────────────────────────────────────────────
def coco_to_h36m(x):
    """x: [T, 17, 3] COCO-17  →  [T, 17, 3] H36M-17"""
    T, V, C = x.shape
    y = np.zeros([T, 17, C], dtype=x.dtype)

    y[:, 0] = (x[:, 11] + x[:, 12]) / 2   # Pelvis = mean(LHip, RHip)
    y[:, 1] = x[:, 12]                     # RHip
    y[:, 2] = x[:, 14]                     # RKnee
    y[:, 3] = x[:, 16]                     # RAnkle
    y[:, 4] = x[:, 11]                     # LHip
    y[:, 5] = x[:, 13]                     # LKnee
    y[:, 6] = x[:, 15]                     # LAnkle

    thorax = (x[:, 5] + x[:, 6]) / 2      # mean(LShoulder, RShoulder)
    y[:, 8] = thorax                        # Thorax
    y[:, 7] = (y[:, 0] + thorax) / 2       # Spine = mean(Pelvis, Thorax)

    y[:, 9]  = x[:, 0]   # Nose
    y[:, 10] = x[:, 0]   # Head (approx = Nose, no head-top in COCO-17)
    y[:, 11] = x[:, 5]   # LShoulder
    y[:, 12] = x[:, 7]   # LElbow
    y[:, 13] = x[:, 9]   # LWrist
    y[:, 14] = x[:, 6]   # RShoulder
    y[:, 15] = x[:, 8]   # RElbow
    y[:, 16] = x[:, 10]  # RWrist
    return y


def h36m_to_coco(x):
    """x: [T, 17, 3] H36M-17  →  [T, 17, 3] COCO-17 (approx)"""
    T, V, C = x.shape
    y = np.zeros([T, 17, C], dtype=x.dtype)

    # Head / face (approx to Nose)
    y[:, 0]  = x[:, 9]    # Nose
    y[:, 1]  = x[:, 9]    # LeftEye ≈ Nose
    y[:, 2]  = x[:, 9]    # RightEye ≈ Nose
    y[:, 3]  = x[:, 9]    # LeftEar ≈ Nose
    y[:, 4]  = x[:, 9]    # RightEar ≈ Nose
    # Upper body
    y[:, 5]  = x[:, 11]   # LShoulder
    y[:, 6]  = x[:, 14]   # RShoulder
    y[:, 7]  = x[:, 12]   # LElbow
    y[:, 8]  = x[:, 15]   # RElbow
    y[:, 9]  = x[:, 13]   # LWrist
    y[:, 10] = x[:, 16]   # RWrist
    # Lower body
    y[:, 11] = x[:, 4]    # LHip
    y[:, 12] = x[:, 1]    # RHip
    y[:, 13] = x[:, 5]    # LKnee
    y[:, 14] = x[:, 2]    # RKnee
    y[:, 15] = x[:, 6]    # LAnkle
    y[:, 16] = x[:, 3]    # RAnkle
    return y


# ────────────────────────────────────────────────────────────────────────────
# 2. 키포인트 로드 및 전처리
# extract_expert_keypoints.py: 가상 캔버스 1920×1080, hip 중심=(960,540)
# ────────────────────────────────────────────────────────────────────────────
print("Loading keypoints...")
with open('squat_expert_keypoints.json') as f:
    raw = json.load(f)

kpts = np.array(raw, dtype=np.float32)  # [131, 17, 3]
T_src = kpts.shape[0]
print(f"  Input: {T_src} frames, {kpts.shape[1]} joints")

# COCO-17 → H36M-17
kpts_h36m = coco_to_h36m(kpts)  # [131, 17, 3]

# 정규화: W=1920, H=1080 (가상 캔버스)
W, H = 1920, 1080
scale = min(W, H) / 2.0  # 540
kpts_norm = kpts_h36m.copy()
kpts_norm[:, :, 0] = (kpts_h36m[:, :, 0] - W / 2) / scale  # x: [-1, 1]
kpts_norm[:, :, 1] = (kpts_h36m[:, :, 1] - H / 2) / scale  # y: [-h/w, h/w]
kpts_norm[:, :, 2] = 1.0  # confidence=1 (z는 MediaPipe depth, conf로 대체)

# 243프레임으로 패딩 (MotionBERT 입력 길이)
CLIP = 243
if T_src < CLIP:
    pad = np.tile(kpts_norm[-1:], (CLIP - T_src, 1, 1))
    kpts_padded = np.concatenate([kpts_norm, pad], axis=0)
else:
    kpts_padded = kpts_norm[:CLIP]

batch = torch.from_numpy(kpts_padded[np.newaxis]).float()  # [1, 243, 17, 3]
print(f"  Batch shape: {batch.shape}, x range [{kpts_norm[:,:,0].min():.2f}, {kpts_norm[:,:,0].max():.2f}]")


# ────────────────────────────────────────────────────────────────────────────
# 3. 모델 로드
# ────────────────────────────────────────────────────────────────────────────
print("Loading MotionBERT-Lite...")
cfg_path  = 'MotionBERT/configs/pose3d/MB_ft_h36m_global_lite.yaml'
ckpt_path = 'MotionBERT/checkpoint/pose3d/FT_MB_lite_MB_ft_h36m_global_lite/best_epoch.bin'

args_mb = get_config(cfg_path)
model = load_backbone(args_mb)
model = nn.DataParallel(model).cuda()

ckpt = torch.load(ckpt_path, map_location='cuda')
model.load_state_dict(ckpt['model_pos'], strict=True)
model.eval()
print("  Model loaded.")


# ────────────────────────────────────────────────────────────────────────────
# 4. 추론 (flip augmentation 적용)
# ────────────────────────────────────────────────────────────────────────────
print("Running inference...")
batch_cuda = batch.cuda()
with torch.no_grad():
    pred1 = model(batch_cuda)                           # [1, 243, 17, 3]
    pred2 = flip_data(model(flip_data(batch_cuda)))     # flip augmentation
    pred  = (pred1 + pred2) / 2.0

# 루트 Z=0 고정 (rootrel=False 설정에 맞춤)
pred[:, 0, 0, 2] = 0

result_h36m = pred[0, :T_src].cpu().numpy()  # [131, 17, 3] H36M 좌표계
print(f"  Output shape: {result_h36m.shape}")


# ────────────────────────────────────────────────────────────────────────────
# 5. H36M-17 → COCO-17 변환 후 저장
# 좌표계: MotionBERT H36M = (x=right, y=up, z=forward)
#   → 이 그대로 저장. toThreeJS: new Vector3(pt[0], pt[1], pt[2]) 사용 가능
# 단위: ~meter scale (Human3.6M 기준). 시각화용으로 *1000하여 mm 단위로 저장.
# ────────────────────────────────────────────────────────────────────────────
result_coco = h36m_to_coco(result_h36m)  # [131, 17, 3] COCO-17 순서

# MotionBERT output 좌표계 확인
print("\n[Sample frame 0]")
joints_h36m = ['Pelvis','RHip','RKnee','RAnkle','LHip','LKnee','LAnkle',
               'Spine','Thorax','Nose','Head','LSho','LElb','LWri','RSho','RElb','RWri']
for i, name in enumerate(joints_h36m):
    v = result_h36m[0, i]
    print(f"  H36M[{i:2d}] {name:8s}: ({v[0]:6.3f}, {v[1]:6.3f}, {v[2]:6.3f})")

print("\nCOCO-17 [11=LHip, 13=LKnee, 15=LAnk]:")
for idx, name in [(11,'LHip'),(13,'LKnee'),(15,'LAnk')]:
    v = result_coco[0, idx]
    print(f"  COCO[{idx}] {name}: ({v[0]:6.3f}, {v[1]:6.3f}, {v[2]:6.3f})")

# 저장 (리스트로 변환)
# 단위: MotionBERT 원본 (~meters). Three.js 매핑: toThreeJS = (pt[0], -pt[1], pt[2])
out_path = 'squat_expert_keypoints_3d_mb.json'
frames_out = result_coco.tolist()
meta = {
    'total_frames': len(frames_out),
    'frames': frames_out,
    'source': 'motionbert-lite',
    'coord_note': 'x=right, y=down(negate for ThreeJS Y-up), z=depth',
    'scale': 'meters'
}
with open(out_path, 'w') as f:
    json.dump(meta, f)

print(f"\nSaved → {out_path}  ({len(frames_out)} frames)")
