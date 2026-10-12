# CLAUDE.md — PT 운동 분석 프로그램

## 작업 규칙

1. 단계별 `.md`가 제공된 경우에만 해당 모듈 코드를 작성한다. 제공되지 않은 모듈은 임의로 작성하지 않는다.
2. 코드 작성 전, 구현 의도·방향·예상 문제를 5줄 이내로 설명하고 허락을 구한다.
3. 사용자가 "코드 작성해줘"라고 명시한 경우에만 코드를 작성한다.
4. 구현 중 선택이 필요하거나 문제가 예상되면 코드 작성을 중단하고 먼저 질문한다.

---

## 기술 스택

- **언어**: Python 3.11
- **추론**: TensorFlow 2.x + tensorflow-hub, dtaidistance, NumPy
- **카메라·렌더링**: OpenCV (cv2) — 카메라 직접 접근 및 윈도우 출력 담당
- **패키지 관리**: uv + pyproject.toml
- **실행**: `uv run python main.py`

---

## 인터페이스 규칙

### 관절 좌표 (공통 타입)
- shape `(17, 3)`, dtype `float32`, 각 행: `[y, x, confidence]`
- 관절 인덱스 상수: `backend/utils/keypoints.py` 참조

### 파이프라인 결과 (Python dict)
```python
{
    "keypoints": np.ndarray,   # shape (17, 3), dtype float32
    "score":     int | None,    # 0~100, 프레임 누적 중(n_frames 미만)이면 None
    "rep_scores": list[int],   # 회차별 점수 누적 목록
    "fps":       float,        # 캡처 → PoseEstimator → PoseNormalizer 구간 fps
}
```

---

## 코드 작성 규칙

### Python
- 모든 함수에 타입 힌트 + 한 줄 docstring (한국어) 필수, 본문 주석 금지
- `np.ndarray` 사용 시 shape·dtype을 docstring에 명시
- 매직 넘버 금지 — 상수는 `utils/keypoints.py` 또는 모듈 상단에 정의
- 예외 처리 명시 — 추론 실패·신뢰도 미달 관절을 조용히 무시하지 않는다

---

## 성능 제약

- 목표: 15 FPS 이상
- MoveNet 모델 앱 시작 시 1회만 로드
- 전문가 영상 정규화 시퀀스 앱 시작 시 1회만 계산

---

## 금지 사항

- `Any` 타입 힌트 금지
- 전역 변수로 상태 관리 금지 — 클래스 인스턴스 사용
