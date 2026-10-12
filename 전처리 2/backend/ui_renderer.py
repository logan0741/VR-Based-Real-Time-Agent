"""Render expert and user poses with a compact center status panel."""

import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.utils.keypoints import (
    LEFT_ANKLE,
    LEFT_EAR,
    LEFT_ELBOW,
    LEFT_EYE,
    LEFT_HIP,
    LEFT_KNEE,
    LEFT_SHOULDER,
    LEFT_WRIST,
    NOSE,
    RIGHT_ANKLE,
    RIGHT_EAR,
    RIGHT_ELBOW,
    RIGHT_EYE,
    RIGHT_HIP,
    RIGHT_KNEE,
    RIGHT_SHOULDER,
    RIGHT_WRIST,
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
MAX_FEEDBACK_WIDTH: int = 28
FONT_PATH = Path(r"C:\Windows\Fonts\malgun.ttf")
FEEDBACK_FONT_SIZE: int = 20

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
    if confidence < CONF_MID_THRESH:
        return ALPHA_LOW
    if confidence < CONF_HIGH_THRESH:
        return ALPHA_MID
    return ALPHA_HIGH


def _joint_color(joint_idx: int) -> tuple[int, int, int]:
    if joint_idx in LEFT_JOINT_SET:
        return COLOR_LEFT
    if joint_idx in RIGHT_JOINT_SET:
        return COLOR_RIGHT
    return COLOR_CENTER


def _apply_alpha(color: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return (int(color[0] * alpha), int(color[1] * alpha), int(color[2] * alpha))


def _wrap_feedback(text: str, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _load_feedback_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if FONT_PATH.exists():
        return ImageFont.truetype(str(FONT_PATH), FEEDBACK_FONT_SIZE)
    return ImageFont.load_default()


def _draw_korean_text(
    image: np.ndarray,
    text: str,
    position: tuple[int, int],
    color: tuple[int, int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> np.ndarray:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb)
    drawer = ImageDraw.Draw(pil_image)
    drawer.text(position, text, font=font, fill=(color[2], color[1], color[0]))
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


class UIRenderer:
    def __init__(
        self,
        expert_frames: list[np.ndarray],
        expert_keypoints: np.ndarray,
        target_fps: int,
    ) -> None:
        if len(expert_frames) == 0:
            raise ValueError("expert_frames must not be empty.")
        if expert_keypoints.shape[0] != len(expert_frames):
            raise ValueError("expert_frames and expert_keypoints length mismatch.")
        self._expert_frames = expert_frames
        self._expert_keypoints = expert_keypoints
        self._target_fps = target_fps
        self._n_expert: int = len(expert_frames)
        self._start_time: float | None = None
        self._feedback_font = _load_feedback_font()

    def start(self) -> None:
        self._start_time = time.time()

    def render(self, user_frame: np.ndarray, result: dict) -> np.ndarray:
        if self._start_time is None:
            raise RuntimeError("start() must be called before render().")

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
        elapsed = time.time() - self._start_time  # type: ignore[operator]
        return int(elapsed * self._target_fps) % self._n_expert

    def _build_expert_panel(self, target_height: int, frame_idx: int) -> np.ndarray:
        frame = self._expert_frames[frame_idx].copy()
        h, w = frame.shape[:2]
        scale = target_height / h
        new_w = int(w * scale)
        resized = cv2.resize(frame, (new_w, target_height))
        self._draw_skeleton(resized, self._expert_keypoints[frame_idx], target_height, new_w)
        return resized

    def _build_user_panel(self, user_frame: np.ndarray, keypoints: np.ndarray) -> np.ndarray:
        panel = user_frame.copy()
        h, w = panel.shape[:2]
        self._draw_skeleton(panel, keypoints, h, w)
        return panel

    def _build_center_panel(self, height: int, result: dict) -> np.ndarray:
        panel = np.zeros((height, CENTER_PANEL_WIDTH, 3), dtype=np.uint8)
        score = result["score"]
        rep_scores: list[int] = result["rep_scores"]
        fps: float = result["fps"]
        feedback: str = str(result.get("feedback", "측정 중입니다."))

        y = MARGIN + LINE_HEIGHT
        cv2.putText(panel, f"FPS: {fps:.1f}", (MARGIN, y), FONT, FONT_SCALE, COLOR_CENTER, FONT_THICKNESS)

        y += LINE_HEIGHT
        score_text = "Measuring..." if score is None else str(score)
        cv2.putText(panel, f"Score: {score_text}", (MARGIN, y), FONT, FONT_SCALE, COLOR_CENTER, FONT_THICKNESS)

        y += LINE_HEIGHT * 2
        cv2.putText(panel, "Feedback:", (MARGIN, y), FONT, FONT_SCALE, COLOR_CENTER, FONT_THICKNESS)
        for line in _wrap_feedback(feedback, MAX_FEEDBACK_WIDTH)[:2]:
            y += LINE_HEIGHT
            panel = _draw_korean_text(panel, line, (MARGIN, y - 18), COLOR_CENTER, self._feedback_font)

        y += LINE_HEIGHT * 2
        cv2.putText(panel, "Rep Scores (latest 5):", (MARGIN, y), FONT, FONT_SCALE, COLOR_CENTER, FONT_THICKNESS)

        recent = list(reversed(rep_scores[-MAX_REP_DISPLAY:]))
        total_reps = len(rep_scores)
        for i, rep_score in enumerate(recent):
            y += LINE_HEIGHT
            cv2.putText(
                panel,
                f"  Rep {total_reps - i}: {rep_score}",
                (MARGIN, y),
                FONT,
                FONT_SCALE,
                COLOR_CENTER,
                FONT_THICKNESS,
            )

        return panel

    def _draw_skeleton(
        self,
        frame: np.ndarray,
        keypoints: np.ndarray,
        height: int,
        width: int,
    ) -> None:
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
