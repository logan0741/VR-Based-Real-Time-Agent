import math
import numpy as np
from typing import Dict, List

# COCO Keypoint Indices (for reference)
# 11: left_shoulder, 12: right_shoulder
# 23: left_hip, 24: right_hip
# 25: left_knee, 26: right_knee
# 27: left_ankle, 28: right_ankle

def calculate_angle(a: List[float], b: List[float], c: List[float]) -> float:
    """Calculates the 3D angle between three points a, b, c with b as the vertex."""
    ba = np.array(a) - np.array(b)
    bc = np.array(c) - np.array(b)
    
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    return np.degrees(angle)

class PostureAnalyzer:
    def __init__(self, exercise_type="squat"):
        self.exercise_type = exercise_type
        # 피로도 상태를 누적/저장하는 딕셔너리
        self.fatigue_state = {
            "chest": "low", "abs": "low", "lower_back": "low",
            "left_quad": "low", "right_quad": "low",
            "left_hamstring": "low", "right_hamstring": "low",
            "left_glute": "low", "right_glute": "low"
        }

    def analyze(self, keypoints_17x3: np.ndarray) -> Dict[str, str]:
        """
        사용자의 실시간 관절 좌푯값을 받아 전문가 포즈 기준(각도 오차)과 비교해 
        특정 근육의 과부하(fatigue) 상태를 반환합니다.
        """
        # 관절 좌표 추출 (COCO 17)
        l_shoulder = keypoints_17x3[5]  # Index 5 is left shoulder
        r_shoulder = keypoints_17x3[6]  # Index 6 is right shoulder
        l_hip = keypoints_17x3[11]      # Index 11 is left hip
        r_hip = keypoints_17x3[12]      # Index 12 is right hip
        l_knee = keypoints_17x3[13]     # Index 13 is left knee
        r_knee = keypoints_17x3[14]     # Index 14 is right knee
        l_ankle = keypoints_17x3[15]    # Index 15 is left ankle
        r_ankle = keypoints_17x3[16]    # Index 16 is right ankle

        if self.exercise_type == "squat":
            # 1. 무릎 각도 분석 (대퇴사두근/둔근 피로도 측정)
            l_knee_angle = calculate_angle(l_hip, l_knee, l_ankle)
            r_knee_angle = calculate_angle(r_hip, r_knee, r_ankle)
            
            # 스쿼트 하강 시 (무릎 각도가 작아질 때) 허벅지 과부하 증가
            if l_knee_angle < 100:
                self.fatigue_state["left_quad"] = "high"
                self.fatigue_state["left_glute"] = "med"
            elif l_knee_angle < 140:
                self.fatigue_state["left_quad"] = "med"
                self.fatigue_state["left_glute"] = "low"
            else:
                self.fatigue_state["left_quad"] = "low"
            
            if r_knee_angle < 100:
                self.fatigue_state["right_quad"] = "high"
                self.fatigue_state["right_glute"] = "med"
            elif r_knee_angle < 140:
                self.fatigue_state["right_quad"] = "med"
                self.fatigue_state["right_glute"] = "low"
            else:
                self.fatigue_state["right_quad"] = "low"

            # 2. 허리 굽어짐 (Back Rounded) 분석 (척추기립근/하부허리 과부하 측정)
            # 전문가 포즈: 상체 각도(어깨-골반-수직선)가 무너져 과도하게 숙여지면 안 됨
            # 코어로직: 무릎이 덜 구부러졌는데 어깨가 골반 높이에 가깝다면 "허리 무너짐(과부하)" 판정
            torso_height = (l_shoulder[1] + r_shoulder[1]) / 2.0
            hip_height = (l_hip[1] + r_hip[1]) / 2.0
            knee_height = (l_knee[1] + r_knee[1]) / 2.0
            
            # 엉덩이와 무릎이 비슷한 높이(하강 상태)가 아닌데, 상체-골반 거리가 너무 짧아지면 허리 꺾임으로 감지
            distance_shoulder_hip = abs(torso_height - hip_height)
            distance_hip_knee = abs(hip_height - knee_height)
            
            if distance_shoulder_hip < (distance_hip_knee * 0.5) and (l_knee_angle > 110):
                self.fatigue_state["lower_back"] = "high"  # 허리 부상 위험! 빨간색!
            elif distance_shoulder_hip < (distance_hip_knee * 0.8):
                self.fatigue_state["lower_back"] = "med"   # 경고
            else:
                self.fatigue_state["lower_back"] = "low"   # 정상

            # 3. 코어 상태 (Abs)
            # 허리 보호를 위해 코어는 항상 미디움 이상으로 사용됨
            if self.fatigue_state["lower_back"] == "high":
                self.fatigue_state["abs"] = "high" # 보상작용으로 코어 붕괴 위험
            elif l_knee_angle < 120:
                self.fatigue_state["abs"] = "med"
            else:
                self.fatigue_state["abs"] = "low"

        return self.fatigue_state
