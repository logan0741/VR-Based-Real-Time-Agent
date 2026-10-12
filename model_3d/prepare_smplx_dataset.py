"""Prepare SMPL-X training dataset (v2) for PoseLifterNet.

Reads the 013.피트니스자세 fitness dataset (2D pixel keypoints + 3D joint
coordinates) and produces (17x3 COCO-17 normalized 2D input, 66-dim SMPL-X
parameter target) pairs.

Output target layout (66,) = global_orient[3] + body_pose[63]
  global_orient is fixed to [0, 0, 0] (avoids the 3D data camera-frame issue).
  body_pose is 21 joints x 3 axis-angle params, derived from bone directions.

Usage:
    python model_3d/prepare_smplx_dataset.py
"""

from __future__ import annotations

import glob
import json
import os
import pickle
from typing import Dict, List, Optional, Tuple

import numpy as np

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_ROOT = os.path.join(
    PROJECT_ROOT,
    "013.피트니스자세",
    "prepared_train_eval_body01_compact",
    "labels",
)
SUBSET_DIR = "Day05_200925_F"
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "model_3d", "artifacts", "training", "smplx_v2")

# Pixel resolution used for 2D normalization.
IMG_WIDTH = 1920.0
IMG_HEIGHT = 1080.0

# --------------------------------------------------------------------------- #
# Joint definitions
# --------------------------------------------------------------------------- #
# COCO-17 ordering for the 2D model input.
COCO17_NAMES = [
    "Nose",
    "Left Eye",
    "Right Eye",
    "Left Ear",
    "Right Ear",
    "Left Shoulder",
    "Right Shoulder",
    "Left Elbow",
    "Right Elbow",
    "Left Wrist",
    "Right Wrist",
    "Left Hip",
    "Right Hip",
    "Left Knee",
    "Right Knee",
    "Left Ankle",
    "Right Ankle",
]

# SMPL-X body_pose joints (21 joints, indices 0..20). Each entry:
#   index -> (rest_direction, bone_start_joint, bone_end_joint)
# Special bones (spine2, spine3) are handled with midpoint logic below.
# rest_direction is the T-pose bone direction in SMPL-X frame.
BODY_POSE_JOINTS: List[Tuple[int, str, Tuple[float, float, float], str, str]] = [
    (0, "left_hip", (0, -1, 0), "Left Hip", "Left Knee"),
    (1, "right_hip", (0, -1, 0), "Right Hip", "Right Knee"),
    (2, "spine1", (0, 1, 0), "__pelvis_center__", "Waist"),
    (3, "left_knee", (0, -1, 0), "Left Knee", "Left Ankle"),
    (4, "right_knee", (0, -1, 0), "Right Knee", "Right Ankle"),
    (5, "spine2", (0, 1, 0), "Back", "Neck"),
    (6, "left_ankle", (0, -1, 0), "Left Ankle", "Left Foot"),
    (7, "right_ankle", (0, -1, 0), "Right Ankle", "Right Foot"),
    (8, "spine3", (0, 1, 0), "Waist", "Neck"),
    (9, "left_foot", (0, 0, 1), "Left Ankle", "Left Foot"),
    (10, "right_foot", (0, 0, 1), "Right Ankle", "Right Foot"),
    (11, "neck", (0, 1, 0), "Neck", "Nose"),
    (12, "left_collar", (-1, 0, 0), "Neck", "Left Shoulder"),
    (13, "right_collar", (1, 0, 0), "Neck", "Right Shoulder"),
    (14, "head", (0, 1, 0), "Neck", "Nose"),
    (15, "left_shoulder", (-1, 0, 0), "Left Shoulder", "Left Elbow"),
    (16, "right_shoulder", (1, 0, 0), "Right Shoulder", "Right Elbow"),
    (17, "left_elbow", (-1, 0, 0), "Left Elbow", "Left Wrist"),
    (18, "right_elbow", (1, 0, 0), "Right Elbow", "Right Wrist"),
    (19, "left_wrist", (-1, 0, 0), "Left Wrist", "Left Palm"),
    (20, "right_wrist", (1, 0, 0), "Right Wrist", "Right Palm"),
]


# --------------------------------------------------------------------------- #
# Math helpers
# --------------------------------------------------------------------------- #
def rotation_matrix_between(v1: np.ndarray, v2: np.ndarray) -> np.ndarray:
    """3x3 rotation matrix that rotates unit vector v1 onto unit vector v2."""
    v1 = v1 / (np.linalg.norm(v1) + 1e-8)
    v2 = v2 / (np.linalg.norm(v2) + 1e-8)
    axis = np.cross(v1, v2)
    norm = np.linalg.norm(axis)
    if norm < 1e-8:
        if np.dot(v1, v2) > 0:
            return np.eye(3)
        perp = np.array([1.0, 0.0, 0.0]) if abs(v1[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        axis = np.cross(v1, perp)
        axis = axis / np.linalg.norm(axis)
        norm = 1.0
    axis = axis / norm
    angle = np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0))
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)


def rotation_matrix_to_axis_angle(R: np.ndarray) -> np.ndarray:
    """Convert 3x3 rotation matrix to axis-angle vector."""
    angle = np.arccos(np.clip((np.trace(R) - 1) / 2, -1.0, 1.0))
    if angle < 1e-8:
        return np.zeros(3, dtype=np.float64)
    axis = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * np.sin(angle))
    return axis * angle


# --------------------------------------------------------------------------- #
# Per-frame conversion
# --------------------------------------------------------------------------- #
def build_input_2d(view_pts: Dict[str, Dict[str, float]]) -> Optional[np.ndarray]:
    """Convert a view's pixel keypoints into normalized COCO-17 (17, 3)."""
    out = np.zeros((17, 3), dtype=np.float32)
    for idx, name in enumerate(COCO17_NAMES):
        pt = view_pts.get(name)
        if pt is None:
            return None
        # raw_sequence / 실제 서버 입력은 MoveNet [y, x, conf] 형식 → 맞춤
        out[idx, 0] = float(pt["y"]) / IMG_HEIGHT
        out[idx, 1] = float(pt["x"]) / IMG_WIDTH
        out[idx, 2] = 1.0
    return out


def joint_xyz(pts: Dict[str, Dict[str, float]], name: str) -> Optional[np.ndarray]:
    pt = pts.get(name)
    if pt is None:
        return None
    return np.array([float(pt["x"]), float(pt["y"]), float(pt["z"])], dtype=np.float64)


def build_target_smplx(pts3d: Dict[str, Dict[str, float]]) -> Optional[np.ndarray]:
    """Convert 24-joint 3D coordinates into a 66-dim SMPL-X parameter vector.

    Uses hierarchical local rotations: each joint's rotation is relative to its
    parent bone's world orientation, matching how SMPL-X body_pose is defined.
    """
    lhip = joint_xyz(pts3d, "Left Hip")
    rhip = joint_xyz(pts3d, "Right Hip")
    if lhip is None or rhip is None:
        return None
    pelvis_center = (lhip + rhip) / 2.0

    # T-pose reference directions (world Y-up)
    DN = np.array([0.0, -1.0, 0.0])   # down  (leg bones)
    UP = np.array([0.0,  1.0, 0.0])   # up    (spine/neck)
    LF = np.array([-1.0, 0.0, 0.0])  # left  (left arm)
    RT = np.array([1.0,  0.0, 0.0])  # right (right arm)
    FW = np.array([0.0,  0.0, 1.0])  # forward (feet)

    # world rotation matrices for each named joint (accumulated hierarchically)
    W: Dict[str, np.ndarray] = {"pelvis": np.eye(3)}

    body_pose = np.zeros(63, dtype=np.float64)

    def _bone_dir(a: np.ndarray, b_name: str) -> Optional[np.ndarray]:
        b = joint_xyz(pts3d, b_name)
        if b is None:
            return None
        d = b - a
        n = np.linalg.norm(d)
        return d / n if n > 1e-6 else None

    def compute(idx: int, jname: str, parent: str, tpose: np.ndarray,
                start: np.ndarray, end_name: str) -> None:
        actual = _bone_dir(start, end_name)
        parent_W = W.get(parent, np.eye(3))
        if actual is None:
            W[jname] = parent_W.copy()
            return
        world_R = rotation_matrix_between(tpose, actual)
        W[jname] = world_R
        local_R = parent_W.T @ world_R
        aa = rotation_matrix_to_axis_angle(local_R)
        body_pose[idx * 3: idx * 3 + 3] = aa

    def jv(name: str) -> Optional[np.ndarray]:
        return joint_xyz(pts3d, name)

    # --- lower body (parent = pelvis) ---
    lh = jv("Left Hip");   rh = jv("Right Hip")
    lk = jv("Left Knee");  rk = jv("Right Knee")
    la = jv("Left Ankle"); ra = jv("Right Ankle")
    lf = jv("Left Foot");  rf = jv("Right Foot")
    wa = jv("Waist");      bk = jv("Back")
    nk = jv("Neck");       ns = jv("Nose")
    ls = jv("Left Shoulder");  rs = jv("Right Shoulder")
    le = jv("Left Elbow");     re = jv("Right Elbow")
    lw = jv("Left Wrist");     rw = jv("Right Wrist")
    lp = jv("Left Palm");      rp = jv("Right Palm")

    if any(v is None for v in [lh, rh, lk, rk, la, ra]):
        return None

    # i=0 left_hip, i=1 right_hip, i=2 spine1
    compute(0, "left_hip",  "pelvis", DN, lh, "Left Knee")
    compute(1, "right_hip", "pelvis", DN, rh, "Right Knee")
    compute(2, "spine1",    "pelvis", UP, pelvis_center, "Waist")
    # i=3,4 knees, i=5 spine2
    compute(3, "left_knee",  "left_hip",  DN, lk, "Left Ankle")
    compute(4, "right_knee", "right_hip", DN, rk, "Right Ankle")
    if bk is not None and nk is not None:
        compute(5, "spine2", "spine1", UP, bk, "Neck")
    else:
        W["spine2"] = W["spine1"].copy()
    # i=6,7 ankles, i=8 spine3
    compute(6, "left_ankle",  "left_knee",  DN, la, "Left Foot")
    compute(7, "right_ankle", "right_knee", DN, ra, "Right Foot")
    if wa is not None and nk is not None:
        compute(8, "spine3", "spine2", UP, wa, "Neck")
    else:
        W["spine3"] = W["spine2"].copy()
    # i=9,10 feet
    if lf is not None:
        compute(9,  "left_foot",  "left_ankle",  FW, la, "Left Foot")
    if rf is not None:
        compute(10, "right_foot", "right_ankle", FW, ra, "Right Foot")
    # i=11 neck, i=12,13 collars, i=14 head
    if nk is not None and ns is not None:
        compute(11, "neck",         "spine3", UP, nk, "Nose")
        compute(14, "head",         "neck",   UP, nk, "Nose")
    if nk is not None and ls is not None:
        compute(12, "left_collar",  "spine3", LF, nk, "Left Shoulder")
    if nk is not None and rs is not None:
        compute(13, "right_collar", "spine3", RT, nk, "Right Shoulder")
    # i=15,16 shoulders, i=17,18 elbows, i=19,20 wrists
    if ls is not None and le is not None:
        compute(15, "left_shoulder",  "left_collar",  LF, ls, "Left Elbow")
    if rs is not None and re is not None:
        compute(16, "right_shoulder", "right_collar", RT, rs, "Right Elbow")
    if le is not None and lw is not None:
        compute(17, "left_elbow",  "left_shoulder",  LF, le, "Left Wrist")
    if re is not None and rw is not None:
        compute(18, "right_elbow", "right_shoulder", RT, re, "Right Wrist")
    if lw is not None and lp is not None:
        compute(19, "left_wrist",  "left_elbow",  LF, lw, "Left Palm")
    if rw is not None and rp is not None:
        compute(20, "right_wrist", "right_elbow", RT, rw, "Right Palm")

    global_orient = np.zeros(3, dtype=np.float64)
    return np.concatenate([global_orient, body_pose]).astype(np.float32)


# --------------------------------------------------------------------------- #
# Dataset assembly
# --------------------------------------------------------------------------- #
def process_split(split: str) -> List[Dict[str, np.ndarray]]:
    """Build the sample list for a split ("train" or "val")."""
    split_dir = os.path.join(DATASET_ROOT, split, SUBSET_DIR)
    pattern = os.path.join(split_dir, "*-3d.json")
    files_3d = sorted(glob.glob(pattern))

    samples: List[Dict[str, np.ndarray]] = []
    skipped_files = 0
    skipped_frames = 0

    for path_3d in files_3d:
        path_2d = path_3d[: -len("-3d.json")] + ".json"
        if not os.path.exists(path_2d):
            skipped_files += 1
            continue

        try:
            with open(path_2d, "r", encoding="utf-8") as fh:
                data_2d = json.load(fh)
            with open(path_3d, "r", encoding="utf-8") as fh:
                data_3d = json.load(fh)
        except (OSError, json.JSONDecodeError):
            skipped_files += 1
            continue

        frames_2d = data_2d.get("frames", [])
        frames_3d = data_3d.get("frames", [])
        n = min(len(frames_2d), len(frames_3d))

        for i in range(n):
            view = frames_2d[i].get("view1")
            if view is None or "pts" not in view:
                skipped_frames += 1
                continue
            inp = build_input_2d(view["pts"])
            if inp is None:
                skipped_frames += 1
                continue

            pts3d = frames_3d[i].get("pts")
            if pts3d is None:
                skipped_frames += 1
                continue
            target = build_target_smplx(pts3d)
            if target is None:
                skipped_frames += 1
                continue

            samples.append({"input": inp, "target": target})

    print(
        f"[{split}] files={len(files_3d)} samples={len(samples)} "
        f"skipped_files={skipped_files} skipped_frames={skipped_frames}"
    )
    return samples


def report_statistics(split: str, samples: List[Dict[str, np.ndarray]]) -> None:
    if not samples:
        print(f"[{split}] no samples to summarize")
        return
    targets = np.stack([s["target"] for s in samples])  # (N, 66)
    inputs = np.stack([s["input"] for s in samples])  # (N, 17, 3)
    body_pose = targets[:, 3:]  # (N, 63)
    print(f"[{split}] STATISTICS")
    print(f"    samples            : {len(samples)}")
    print(f"    input shape        : {inputs.shape[1:]} (per sample)")
    print(f"    target shape       : {targets.shape[1:]} (per sample)")
    print(f"    input  x range     : [{inputs[..., 0].min():.4f}, {inputs[..., 0].max():.4f}]")
    print(f"    input  y range     : [{inputs[..., 1].min():.4f}, {inputs[..., 1].max():.4f}]")
    print(f"    body_pose mean     : {body_pose.mean():.6f}")
    print(f"    body_pose std      : {body_pose.std():.6f}")
    print(f"    body_pose abs max  : {np.abs(body_pose).max():.6f}")
    print(f"    global_orient mean : {targets[:, :3].mean():.6f}  (expected 0)")


def save_pickle(split: str, samples: List[Dict[str, np.ndarray]]) -> str:
    out_path = os.path.join(OUTPUT_DIR, f"{split}.pkl")
    with open(out_path, "wb") as fh:
        pickle.dump(samples, fh)
    return out_path


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Dataset root : {DATASET_ROOT}")
    print(f"Output dir   : {OUTPUT_DIR}")
    print("-" * 60)

    for split in ("train", "val"):
        samples = process_split(split)
        report_statistics(split, samples)
        out_path = save_pickle(split, samples)
        print(f"[{split}] saved -> {out_path}")
        print("-" * 60)

    print("Done.")


if __name__ == "__main__":
    main()
