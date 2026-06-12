"""Offline TTS generation for final workout feedback.

The service intentionally stays outside the real-time pose pipeline. It is
called only after a workout ends, so synthesis latency does not affect frame
delivery or rep counting.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class TTSResult:
    status: str
    text: str
    audio_path: str | None = None
    audio_url: str | None = None
    engine: str = "pyttsx3"
    cached: bool = False
    message: str | None = None
    code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "engine": self.engine,
            "cached": self.cached,
            "text": self.text,
        }
        if self.audio_path:
            payload["audio_path"] = self.audio_path
        if self.audio_url:
            payload["audio_url"] = self.audio_url
        if self.message:
            payload["message"] = self.message
        if self.code:
            payload["code"] = self.code
        return payload


EXERCISE_LABELS = {
    "squat": "스쿼트",
    "hammer_curl": "해머 컬",
    "lateral_raise": "레터럴 레이즈",
    "pull_up": "풀업",
    "pullup": "풀업",
}


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _payload_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_final_feedback_script(payload: Mapping[str, Any]) -> str:
    exercise = _clean_text(payload.get("exercise"))
    exercise_label = EXERCISE_LABELS.get(exercise, exercise or "운동")
    score = _clean_text(payload.get("score"))
    grade = _clean_text(payload.get("grade"))
    total_reps = _clean_text(payload.get("totalReps"))
    duration = _clean_text(payload.get("durationMinutes"))
    accuracy = _clean_text(payload.get("accuracy"))

    lines = [
        f"{exercise_label} 운동 최종 분석입니다.",
    ]
    if score:
        lines.append(f"평균 점수는 {score}점입니다.")
    if grade:
        lines.append(f"등급은 {grade}입니다.")
    if total_reps:
        lines.append(f"총 반복 횟수는 {total_reps}회입니다.")
    if duration:
        lines.append(f"운동 시간은 {duration}분입니다.")
    if accuracy:
        lines.append(f"자세 정확도는 {accuracy}퍼센트입니다.")

    sections = payload.get("finalFeedback") or []
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            title = _clean_text(section.get("title"))
            message = _clean_text(section.get("message"))
            if title and message:
                lines.append(f"{title}. {message}")
            elif message:
                lines.append(message)

    return " ".join(line for line in lines if line).strip()


def synthesize_final_feedback(payload: Mapping[str, Any], output_dir: Path) -> TTSResult:
    text = build_final_feedback_script(payload)
    if not text:
        return TTSResult(
            status="error",
            text="",
            message="읽을 최종 피드백 내용이 없습니다.",
            code="empty_text",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"final_feedback_{_payload_hash(payload)}.wav"
    audio_path = output_dir / filename
    audio_url = f"/assets/tts/{filename}"

    if audio_path.exists() and audio_path.stat().st_size > 0:
        return TTSResult(
            status="ok",
            text=text,
            audio_path=str(audio_path),
            audio_url=audio_url,
            cached=True,
        )

    try:
        import pyttsx3
    except ImportError:
        return TTSResult(
            status="error",
            text=text,
            message="pyttsx3가 설치되어 있지 않습니다. requirements.txt 설치 후 다시 실행하세요.",
            code="dependency_missing",
        )

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 1.0)
        engine.save_to_file(text, str(audio_path))
        engine.runAndWait()
    except Exception as exc:
        return TTSResult(
            status="error",
            text=text,
            message=f"TTS 생성 실패: {exc}",
            code="synthesis_failed",
        )

    if not audio_path.exists() or audio_path.stat().st_size == 0:
        return TTSResult(
            status="error",
            text=text,
            message="TTS 엔진이 음성 파일을 생성하지 못했습니다.",
            code="empty_audio",
        )

    return TTSResult(
        status="ok",
        text=text,
        audio_path=str(audio_path),
        audio_url=audio_url,
        cached=False,
    )
