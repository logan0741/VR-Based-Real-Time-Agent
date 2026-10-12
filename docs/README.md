# docs — 문서 지도

이 폴더는 App 브랜치의 한국어 운영 문서다. 번호가 작은 폴더일수록 먼저 읽는다. 코드의 정본은 언제나 `final/` 이고, 문서와 코드가 다르면 코드가 맞다.

## 문서 ↔ 코드

| 문서 | 다루는 내용 | 대응 코드 |
|---|---|---|
| [00_전체흐름_단계별.md](00_전체흐름_단계별.md) | 폰 → 서버 → Quest 까지 번호 붙인 데이터 흐름과 지연 측정 위치 | `final/s05_frontend/`, `final/s02_backend/server.py`, `final/s01_preprocessing/`, `final/src/` |
| [00_환경_준비/00_처음_시작.md](00_환경_준비/00_처음_시작.md) | 빈 Windows PC 에서 Python 3.8·Node 22 설치부터 첫 실행까지 | `final/scripts/00_pipeline.ps1`, `01_install.ps1`, `final/requirements.txt`, `final/package.json`, `.env.example` |
| [00_환경_준비/01_도메인_터널.md](00_환경_준비/01_도메인_터널.md) | Cloudflare Tunnel 3 호스트, 공유 WS, CSP | `final/s05_frontend/viewer.js`, `final/src/hooks/useWebSocket.ts`, `final/s02_backend/server.py`(`NoCacheMiddleware`, `/` 리다이렉트) |
| [10_실행/00_하루_운영.md](10_실행/00_하루_운영.md) | 서버 켜기 → 폰 → Quest → 운동 → 종료·리포트·TTS → 끄기, 지연 측정 | `final/scripts/*.ps1`, `final/src/App.tsx`, `final/src/components/ResultPanel.tsx`, `final/s07_tts/` |
| [10_실행/01_트러블슈팅.md](10_실행/01_트러블슈팅.md) | 실제로 겪은 문제 10 가지와 해결 | 항목별로 표기 |
| [20_판정_규칙/01_좌표_규약.md](20_판정_규칙/01_좌표_규약.md) | `[y, x, confidence]`, 폰 세로 회전, 전문가 `.npy` 축 판별, 좌우 반전 | `viewer.js`, `final/src/components/SkeletonCanvas2D.tsx`, `final/assets/expert_videos/*.npy` |
| [20_판정_규칙/02_횟수_규칙.md](20_판정_규칙/02_횟수_규칙.md) | 각도 상태 머신과 운동별 임계값 | `final/s01_preprocessing/rep_rules.py`, `rep_signals.py`, `rep_detector.py`, `joint_angles.py` |
| [20_판정_규칙/03_피드백과_결과.md](20_판정_규칙/03_피드백과_결과.md) | 실시간 피드백, 피로도 분석, 최종 리포트 | `final/s01_preprocessing/feedback/`, `final/s02_backend/posture_analyzer.py`, `final/src/App.tsx`, `ResultPanel.tsx` |
| [20_판정_규칙/04_판정_변형_기록.md](20_판정_규칙/04_판정_변형_기록.md) | `versions/` 세 변형이 무엇이고 무엇이 채택됐나 | `versions/`, `final/s01_preprocessing/config.py`, `feedback_config.py`, `feedback_policy.py` |
| [30_지연_측정/01_측정_방법과_결과.md](30_지연_측정/01_측정_방법과_결과.md) | 합성 프레임 측정 방법, 로컬·Cloudflare 전체 표, 해석 | `final/latency_lab/` |
| [40_기록/](40_기록) | 당시 문서 원본 (경로가 옛날 그대로다) | — |

## 40_기록 안에 있는 것

| 파일 | 원래 위치 | 성격 |
|---|---|---|
| [HANDOFF_2026-05-21.md](40_기록/HANDOFF_2026-05-21.md) | 루트 `HANDOFF.md` | 2026-05-21 인계 문서. 지금은 없는 `final/07_pipeline_web.py`, `s04_webcam`, `s06_unity_vr` 를 말한다 |
| [LAST_DANCE_PIPELINE_2026-06-09.md](40_기록/LAST_DANCE_PIPELINE_2026-06-09.md) | 루트 `LAST_DANCE_PIPELINE.md` | `last-dance` 브랜치 시점 파이프라인. 앱 경로를 루트 `src/`, `dist/` 로 적고 있다(지금은 `final/src`, `final/app_dist`) |
| [last_dance/](40_기록/last_dance) | `라스트 댄스/` | 같은 시점의 단계별 코드 지도, 검증 체크리스트, 임계값 참고 JSON |
| [user_work_plan.md](40_기록/user_work_plan.md) | `vr app dev/user_work_plan.md` | 2026-06-04 Quest 3 앱 구조 검토(휴대폰 2대, 블루투스 대신 keypoints-only Wi-Fi 전송 권고) |

`20_판정_규칙/02_횟수_규칙.md` 와 `03_피드백과_결과.md` 는 `라스트 댄스/03_…`, `04_…` 를 옮겨 경로만 지금 구조에 맞게 고친 것이다.
