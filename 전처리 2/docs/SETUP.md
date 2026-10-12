# SETUP.md — 환경 세팅

## 사전 요구사항

- Python 3.11+
- uv 설치 완료
- 전문가 영상 파일 준비: `assets/expert_videos/squat.mp4`

---

## 디렉터리 구조 생성

```
project/
├── CLAUDE.md
├── pyproject.toml
├── docs/
├── backend/
├── frontend/
└── assets/
    ├── expert_videos/
    │   └── squat.mp4
    └── test_videos/
        └── test_squat.mp4
```

---

## 패키지 설치

```bash
uv venv
uv sync
```

### 의존성 목록 (pyproject.toml 기준)

```toml
[project]
name = "pose"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "tensorflow==2.*",
    "tensorflow-hub>=0.16",
    "opencv-python>=4.10",
    "numpy>=1.26",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "dtaidistance>=2.3",
    "python-multipart>=0.0.9",
    "setuptools>=68,<81",
    "websockets",
]
```

### 주의 사항

`tensorflow-hub`가 내부적으로 `pkg_resources`를 참조하므로, `setuptools<81` 제약을 유지해야 합니다.
`pyproject.toml`을 수정했다면 아래 순서로 lock/sync를 다시 실행하세요.

```bash
uv lock
uv sync
```

### 테스트 실행 예시

```bash
uv run python -c "import tensorflow as tf; print(tf.__version__)"
```

---

## 실행 (필요할 때 실행)

```bash
# 백엔드 서버 실행
uv run uvicorn backend.main:app --reload

# 브라우저에서 접속
http://localhost:8000
```
