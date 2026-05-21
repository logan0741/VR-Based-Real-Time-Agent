"""Stage 02: 백엔드 서버 임포트 및 파이프라인 초기화 테스트"""
import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# .env 로드
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

def test_imports():
    from final.s02_backend.config import env_bool
    from final.s02_backend.pose_retargeting import PoseRetargeter
    from final.s02_backend.posture_analyzer import PostureAnalyzer
    from final.s03_database.database import DatabaseSettings
    print("[OK] 모듈 임포트")

def test_retargeter():
    import numpy as np
    from final.s02_backend.pose_retargeting import PoseRetargeter
    retargeter = PoseRetargeter()
    body_pose = np.zeros(63, dtype=np.float32)
    global_orient = np.zeros(3, dtype=np.float32)
    result = retargeter.smooth_all(body_pose, global_orient)
    assert "body_pose" in result and "global_orient" in result
    print("[OK] PoseRetargeter")

def test_posture_analyzer():
    import numpy as np
    from final.s02_backend.posture_analyzer import PostureAnalyzer
    analyzer = PostureAnalyzer(exercise_type="squat")
    kpts = np.random.rand(17, 3).astype(np.float32)
    result = analyzer.analyze(kpts)
    assert isinstance(result, dict)
    print("[OK] PostureAnalyzer: fatigue keys =", list(result.keys()))

if __name__ == "__main__":
    print("=" * 50)
    print("  Stage 02: 백엔드 테스트")
    print("=" * 50)
    test_imports()
    test_retargeter()
    test_posture_analyzer()
    print("\n[DONE] Stage 02 백엔드 테스트 완료")
