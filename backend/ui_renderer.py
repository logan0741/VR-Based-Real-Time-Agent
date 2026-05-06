"""파이프라인 결과를 전문가·사용자 영상과 함께 OpenCV 윈도우에 렌더링한다."""

import time

import cv2
import numpy as np

from backend.utils.keypoints import (
    NOSE, LEFT_EYE, RIGHT_EYE, LEFT_EAR, RIGHT_EAR,
    LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE,
    RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE,
    SKELETON_EDGES,
)

WINDOW_TITLE: str = "PT Analysis"
PANEL_HEIGHT: int = 480
CENTER_PANEL_WIDTH: int = 300
FONT: int = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE: float = 0.6
FONT_THICKNESS: int = 1
LINE_HEIGHT: int = 30
MARGIN: int = 15
MAX_REP_DISPLAY: int = 5
JOINT_RADIUS: int = 4

COLOR_CENTER: tuple[int, int, int] = (255, 255, 255)
COLOR_LEFT: tuple[int, int, int] = (0, 255, 0)
COLOR_RIGHT: tuple[int, int, int] = (255, 0, 0)

CENTER_JOINT_SET: frozenset[int] = frozenset({NOSE, LEFT_EYE, RIGHT_EYE, LEFT_EAR, RIGHT_EAR})
LEFT_JOINT_SET: frozenset[int] = frozenset({
    LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE,
})
RIGHT_JOINT_SET: frozenset[int] = frozenset({
    RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE,
})

CONF_MID_THRESH: float = 0.3
CONF_HIGH_THRESH: float = 0.6
ALPHA_LOW: float = 0.3
ALPHA_MID: float = 0.6
ALPHA_HIGH: float = 1.0


def _conf_to_alpha(confidence: float) -> float:
    """신뢰도를 알파값으로 변환한다."""
    if confidence < CONF_MID_THRESH:
        return ALPHA_LOW
    if confidence < CONF_HIGH_THRESH:
        return ALPHA_MID
    return ALPHA_HIGH


def _joint_color(joint_idx: int) -> tuple[int, int, int]:
    """관절 인덱스에 해당하는 BGR 색상을 반환한다."""
    if joint_idx in LEFT_JOINT_SET:
        return COLOR_LEFT
    if joint_idx in RIGHT_JOINT_SET:
        return COLOR_RIGHT
    return COLOR_CENTER


def _apply_alpha(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    """색상에 알파를 곱해 반환한다."""
    return (int(color[0] * alpha), int(color[1] * alpha), int(color[2] * alpha))


class UIRenderer:
    """전문가·사용자 프레임과 파이프라인 결과를 단일 OpenCV 윈도우에 출력하는 클래스."""

    def __init__(
        self,
        expert_frames: list[np.ndarray],
        expert_keypoints: np.ndarray,
        target_fps: int,
    ) -> None:
        """전문가 영상 프레임 버퍼, 원본 keypoints, 재생 fps를 설정한다. expert_keypoints shape=(N,17,3), dtype=float32."""
        if len(expert_frames) == 0:
            raise ValueError("expert_frames가 비어 있습니다.")
        if expert_keypoints.shape[0] != len(expert_frames):
            raise ValueError(
                f"expert_frames 수({len(expert_frames)})와 "
                f"expert_keypoints 프레임 수({expert_keypoints.shape[0]})가 다릅니다."
            )
        self._expert_frames = expert_frames
        self._expert_keypoints = expert_keypoints
        self._target_fps = target_fps
        self._n_expert: int = len(expert_frames)
        self._start_time: float | None = None

    def start(self) -> None:
        """전문가 영상 재생 시작 시각을 기록한다."""
        self._start_time = time.time()

    def render(self, user_frame: np.ndarray, result: dict) -> np.ndarray:
        """파이프라인 결과와 프레임을 OpenCV 윈도우에 출력하고 렌더링된 프레임을 반환한다. user_frame shape=(H,W,3), dtype=uint8."""
        if self._start_time is None:
            raise RuntimeError("render() 호출 전 start()를 먼저 호출하세요.")

        expert_idx = self._current_expert_index()
        h, w = user_frame.shape[:2]
        scale = PANEL_HEIGHT / h
        user_resized = cv2.resize(user_frame, (int(w * scale), PANEL_HEIGHT))

        expert_panel = self._build_expert_panel(PANEL_HEIGHT, expert_idx)
        center_panel = self._build_center_panel(PANEL_HEIGHT, result)
        user_panel = self._build_user_panel(user_resized, result["keypoints"])

        canvas = np.hstack([expert_panel, center_panel, user_panel])
        cv2.imshow(WINDOW_TITLE, canvas)
        return canvas

    def _current_expert_index(self) -> int:
        """경과 시간 기반으로 현재 전문가 영상 프레임 인덱스를 반환한다."""
        elapsed = time.time() - self._start_time  # type: ignore[operator]
        return int(elapsed * self._target_fps) % self._n_expert

    def _build_expert_panel(self, target_height: int, frame_idx: int) -> np.ndarray:
        """전문가 프레임을 target_height로 리사이즈하고 스켈레톤을 그려 반환한다. 출력 shape=(target_height,W,3)."""
        frame = self._expert_frames[frame_idx].copy()
        h, w = frame.shape[:2]
        scale = target_height / h
        new_w = int(w * scale)
        resized = cv2.resize(frame, (new_w, target_height))
        self._draw_skeleton(resized, self._expert_keypoints[frame_idx], target_height, new_w)
        return resized

    def _build_user_panel(self, user_frame: np.ndarray, keypoints: np.ndarray) -> np.ndarray:
        """사용자 프레임에 스켈레톤을 그려 반환한다. 출력 shape=(H,W,3)."""
        panel = user_frame.copy()
        h, w = panel.shape[:2]
        self._draw_skeleton(panel, keypoints, h, w)
        return panel

    def _build_center_panel(self, height: int, result: dict) -> np.ndarray:
        """FPS·점수·회차 점수를 담은 가운데 패널을 반환한다. 출력 shape=(height,CENTER_PANEL_WIDTH,3)."""
        panel = np.zeros((height, CENTER_PANEL_WIDTH, 3), dtype=np.uint8)
        score = result["score"]
        rep_scores: list[int] = result["rep_scores"]
        fps: float = result["fps"]

        y = MARGIN + LINE_HEIGHT
        cv2.putText(panel, f"FPS: {fps:.1f}", (MARGIN, y), FONT, FONT_SCALE, COLOR_CENTER, FONT_THICKNESS)

        y += LINE_HEIGHT
        score_text = "Measuring..." if score is None else str(score)
        cv2.putText(panel, f"Score: {score_text}", (MARGIN, y), FONT, FONT_SCALE, COLOR_CENTER, FONT_THICKNESS)

        y += LINE_HEIGHT * 2
        cv2.putText(panel, "Rep Scores (latest 5):", (MARGIN, y), FONT, FONT_SCALE, COLOR_CENTER, FONT_THICKNESS)

        recent = list(reversed(rep_scores[-MAX_REP_DISPLAY:]))
        total_reps = len(rep_scores)
        for i, s in enumerate(recent):
            y += LINE_HEIGHT
            cv2.putText(
                panel,
                f"  Rep {total_reps - i}: {s}",
                (MARGIN, y),
                FONT, FONT_SCALE, COLOR_CENTER, FONT_THICKNESS,
            )

        return panel

    def _draw_skeleton(
        self,
        frame: np.ndarray,
        keypoints: np.ndarray,
        height: int,
        width: int,
    ) -> None:
        """프레임에 관절과 연결선을 그린다. keypoints shape=(17,3), dtype=float32."""
        for start_idx, end_idx in SKELETON_EDGES:
            ys, xs, cs = keypoints[start_idx]
            ye, xe, ce = keypoints[end_idx]
            alpha = min(_conf_to_alpha(float(cs)), _conf_to_alpha(float(ce)))

            is_cross = (
                (start_idx in LEFT_JOINT_SET and end_idx in RIGHT_JOINT_SET) or
                (start_idx in RIGHT_JOINT_SET and end_idx in LEFT_JOINT_SET)
            )
            base_color = COLOR_CENTER if is_cross else _joint_color(start_idx)
            color = _apply_alpha(base_color, alpha)

            pt1 = (int(xs * width), int(ys * height))
            pt2 = (int(xe * width), int(ye * height))
            cv2.line(frame, pt1, pt2, color, 1)

        for idx in range(keypoints.shape[0]):
            y, x, conf = keypoints[idx]
            color = _apply_alpha(_joint_color(idx), _conf_to_alpha(float(conf)))
            cv2.circle(frame, (int(x * width), int(y * height)), JOINT_RADIUS, color, -1)
