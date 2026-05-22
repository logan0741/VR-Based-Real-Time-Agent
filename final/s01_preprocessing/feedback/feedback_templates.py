"""운동 종목별 부위·상태별 한국어 피드백 메시지 테이블."""
from __future__ import annotations

FEEDBACK_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "squat": {
        "knee": {
            "too_forward": "무릎이 너무 앞으로 나갔어요. 발뒤꿈치에 체중을 실어보세요.",
            "too_backward": "무릎을 조금 더 앞으로 보내세요.",
            "misaligned": "양쪽 무릎 정렬을 맞춰주세요.",
            "generic": "무릎 자세를 교정해주세요.",
        },
        "hip": {
            "too_high": "조금 더 앉아주세요. 허벅지가 바닥과 평행한 지점까지 내려가세요.",
            "too_low": "너무 깊게 내려가고 있어요. 허벅지가 바닥과 평행한 지점에서 멈추세요.",
            "generic": "골반 위치를 조정해주세요.",
        },
        "torso": {
            "too_forward": "상체가 앞으로 기울었어요. 발목 유연성을 함께 확인해보세요.",
            "too_upright": "상체를 조금 더 자연스럽게 숙여주세요.",
            "generic": "상체 자세를 바로잡아주세요.",
        },
        "balance": {
            "shift_left": "체중이 왼쪽으로 치우쳤어요.",
            "shift_right": "체중이 오른쪽으로 치우쳤어요.",
            "generic": "좌우 균형을 맞춰주세요.",
        },
        "ankle": {
            "too_forward": "발목이 너무 앞으로 기울었어요.",
            "limited": "발목이 충분히 굽혀지지 않으면 무릎과 상체 자세에 영향을 줘요. 뒤꿈치를 바닥에 붙이세요.",
            "generic": "발목 자세를 확인해주세요.",
        },
    },
    "hammer_curl": {
        "elbow": {
            "too_forward": "팔꿈치가 앞으로 나왔어요. 상완을 몸통에 고정하세요.",
            "too_backward": "팔꿈치가 뒤로 밀렸어요. 자연스러운 위치로 유지하세요.",
            "generic": "팔꿈치 위치를 교정해주세요.",
        },
        "torso": {
            "too_forward": "상체가 앞으로 쏠렸어요. 등을 바로 세우세요.",
            "leaning_back": "반동을 사용하고 있어요. 상체를 고정하고 팔만 움직이세요.",
            "generic": "상체 자세를 바로잡아주세요.",
        },
        "wrist": {
            "flexion": "손목이 앞으로 꺾였어요. 손목을 일직선으로 유지하세요.",
            "extension": "손목이 뒤로 꺾였어요. 손목을 일직선으로 유지하세요.",
            "generic": "손목을 중립 위치로 유지하세요.",
        },
    },
    "pullup": {
        "shoulder": {
            "misaligned": "한쪽 어깨에만 힘이 쏠리고 있어요. 양쪽 균등하게 당기세요.",
            "too_high": "어깨가 너무 올라갔어요. 힘을 빼고 자연스럽게 내려주세요.",
            "too_low": "더 높이 당겨올리세요.",
            "generic": "어깨 자세를 교정해주세요.",
        },
        "elbow": {
            "misaligned": "팔꿈치가 좌우 비대칭이에요. 양쪽 균등하게 당기세요.",
            "too_wide": "팔꿈치가 너무 벌어졌어요. 조금 좁혀주세요.",
            "too_narrow": "팔꿈치를 조금 더 벌려주세요.",
            "generic": "팔꿈치 자세를 교정해주세요.",
        },
    },
}
