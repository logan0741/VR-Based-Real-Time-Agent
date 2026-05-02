"""종목별 운동 설정 딕셔너리."""

from backend.utils.keypoints import (
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_HIP, RIGHT_HIP,
    LEFT_KNEE, RIGHT_KNEE,
    LEFT_ANKLE, RIGHT_ANKLE,
)

EXERCISES: dict[str, dict] = {
    "squat": {
        # 전문가 영상 파일 경로
        "video_path": "assets/expert_videos/squat_full.mp4",

        # 정규화 기준 방향: "front"(정면) / "side_left"(좌측면) / "side_right"(우측면)
        "normalizer_type": "side_left",

        # DTW 비교에 사용할 관절 인덱스 목록 (스쿼트는 상체 끝 관절 제외)
        "keypoints_used": [
            LEFT_SHOULDER, RIGHT_SHOULDER,
            LEFT_HIP, RIGHT_HIP,
            LEFT_KNEE, RIGHT_KNEE,
            LEFT_ANKLE, RIGHT_ANKLE,
        ],

        # 관절별 DTW 거리 가중치 (keypoints_used 순서와 1:1 대응, 동일 가중치는 1.0)
        "weights": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],

        # 전문가 영상 샘플링 및 사용자 처리 목표 fps
        "target_fps": 24,

        # 실시간 점수 산출에 사용할 최근 프레임 수 (target_fps × 3초)
        "n_frames": 30,

        # 점수 선형 변환 기준 최대 거리 — 정규화된 몸통 길이 단위, 이 값 이상이면 0점
        "max_distance": 1.0,

        # 운동 1회 감지 방법 식별자 (RepDetector에서 종목별 로직 선택에 사용)
        "rep_detector_type": "squat",

        # 정규화 기준값(원점·스케일) 평활화에 사용할 프레임 수 (5~10 권장)
        "norm_buffer_size": 7,

        # 1회 감지용 기울기 계산 윈도우 프레임 수 — 이 구간의 평균 기울기로 상승/하강 판정
        "rep_slope_window": 15,

        # 유효 rep 최소 프레임 수 — 이 값 미만 구간은 노이즈로 버림 (target_fps × 1초 권장)
        "min_rep_frames": 24,
    }
}
