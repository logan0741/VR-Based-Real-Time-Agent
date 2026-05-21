"""Stage 03: DB 연결 테스트"""
import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

def test_db():
    from final.s03_database.database import DatabaseSettings, ExerciseSessionRepository
    settings = DatabaseSettings.from_env()
    print(f"  설정: {settings.host}:{settings.port} / {settings.database}")
    repo = ExerciseSessionRepository(settings)
    health = repo.health()
    print(f"  상태: {health}")
    if health.get("available"):
        print("[OK] DB 연결 성공")
    else:
        print(f"[WARN] DB 연결 실패: {health.get('error')}")
        print("       DB 없이도 서버는 동작합니다 (세션 저장만 비활성화)")

if __name__ == "__main__":
    print("=" * 50)
    print("  Stage 03: DB 테스트")
    print("=" * 50)
    test_db()
    print("\n[DONE] Stage 03 DB 테스트 완료")
