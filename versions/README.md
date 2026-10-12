# versions — 판정 규칙 변형 기록

이 폴더의 세 하위 폴더는 **실행 코드가 아니라 기록**이다. 각각 "판정 규칙을 이렇게 바꿔 봤다" 는 실험 메모(`README.md`)와 바뀐 흐름(`pipeline.md`)만 들어 있다. 채택된 동작은 이미 `final/` 코드에 들어 있고, 앱은 `final/` 만 읽는다.

세 변형 모두 docs-archive 스냅샷(2026-10-12 커밋)에 한꺼번에 들어와 있어 정확한 작성일은 남아 있지 않다. `feedback_hold_mirror_v1` 이 `scoring_normalization_lenient_v1` 을 "실험 기록으로 남긴다" 고 적고 있으므로 lenient → hold 순서였던 것은 확실하다.

| 변형 | 무엇을 바꿨나 | `final/` 에서의 결과 |
|---|---|---|
| [camera_quality_feedback_v1](camera_quality_feedback_v1/README.md) | 카메라 가시성 게이트 도입: 판정 관절의 confidence `0.25` 미만이거나 화면 `0.02~0.98` 밖이면 그 프레임은 `countable=false` — 안내 문장만 보내고 점수·횟수·최종 샘플에서 뺀다. 피드백 엔진 실행 간격 `FEEDBACK_INTERVAL_FRAMES=8` | **채택, 기준만 완화.** 게이트와 `countable` 은 그대로이고 기본값이 `CAMERA_MIN_CONFIDENCE=0.12`, `CAMERA_EDGE_MARGIN=0.01` 로 낮아졌다(인식이 너무 엄격하다는 문제). 판정 관절은 `confidence_joints` 버그를 고쳐 `keypoints_used` 를 쓴다. 간격 8 유지 |
| [scoring_normalization_lenient_v1](scoring_normalization_lenient_v1/README.md) | 점수·피드백 기준 완화: `max_distance 1.0 → 1.35`, 피드백 threshold `0.10/0.12 → 0.16/0.18`, `axis_tolerance 0.02 → 0.04`, `gap_threshold` 약 +0.03. 횟수 규칙은 그대로 | **채택 안 함.** 현재 `config.py` 의 `max_distance` 는 `1.0`, `feedback_config.py` 의 threshold 는 `0.10`/`0.12`, `axis_tolerance` 는 `0.02` 다 |
| [feedback_hold_mirror_v1](feedback_hold_mirror_v1/README.md) | 기준을 낮추는 대신 위 완화를 원복하고, ① 피드백 hold(의미 있는 피드백 1 개를 `target_fps × 3` 프레임 유지) ② `feedback_event` 플래그(새로 수락된 것만 `true`, 앱은 이것만 로그·최종 샘플에 쌓음) ③ 앱 `좌우 반전` 버튼 | **채택.** `feedback/feedback_policy.py` 의 `FeedbackPolicy`, `server.py` 의 `FEEDBACK_HOLD_FRAMES`, `final/src/App.tsx` 의 `feedback_event` 처리와 `userMirror` 가 이 내용이다 |

## 읽을 때 주의

- 문서 안 경로 `src/App.tsx` 는 당시 루트 `src/` 다. 지금은 `final/src/App.tsx` 다.
- 문서 안 수치(예: 게이트 `0.25`)는 그 변형 당시 값이다. 현재 값은 위 표의 오른쪽 열과 `final/` 코드가 정본이다.

같은 내용을 판정 규칙 문서 쪽에서 본 요약: [docs/20_판정_규칙/04_판정_변형_기록.md](../docs/20_판정_규칙/04_판정_변형_기록.md)
