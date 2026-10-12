> 🇬🇧 English version: (없음 — main README 참고)

# App — 최종 실시간 자세 피드백 앱 브랜치

**스마트폰 카메라 → FastAPI → Quest 3 브라우저. 2D 관절점 17개만으로 횟수·점수·피드백·TTS 를 실시간으로 준다.**

이 브랜치 하나만 받으면 앱이 끝까지 돈다. 3D 리프팅 학습은 [`Pose3D`](../../tree/Pose3D), 3D 아바타 시도(중단)는 [`Avatar3D`](../../tree/Avatar3D), 프로젝트 전체 서사는 [`main`](../../tree/main), 재편 이전 전체 스냅샷은 [`docs-archive`](../../tree/docs-archive) 에 있다.

전체 그림은 이렇다. 폰 브라우저(`final/s05_frontend`)가 TF.js MoveNet 으로 카메라에서 COCO-17 관절점 `[y, x, confidence]` 를 뽑아 WebSocket `/ws/pose` 로 보낸다. FastAPI 서버(`final/s02_backend`)는 받은 프레임을 **그대로 즉시 중계(relay)** 하고, 따로 **최신 프레임 하나만** 골라 카메라 게이트 → 정규화 → 횟수 → DTW 점수 → 피드백을 계산해 한 번 더 보낸다(processed). Quest 3 브라우저의 React 앱(`final/src` → `final/app_dist`)은 relay 로 내 자세를, processed 로 점수·횟수·빨간 관절·피드백을 그리고, 목표 세트×횟수에 닿으면 스스로 끝내고 최종 리포트와 TTS 음성을 보여준다. 단계마다 번호를 붙인 흐름은 [docs/00_전체흐름_단계별.md](docs/00_전체흐름_단계별.md), 프로젝트 전체 흐름도는 main 브랜치의 [project_flow_ko.png](../../blob/main/assets/project_flow_ko.png) 에 있다.

---

## 이 README 하나로 돌아간다

명령은 모두 **Windows PowerShell, 저장소 루트**에서 친다. `final/scripts/*.ps1` 은 자기 위치에서 `..\..` 를 루트로 잡고 `python -m uvicorn final.s02_backend.server:app` 을 띄우므로 `final/` 폴더의 이름과 위치를 바꾸면 안 된다.

### 0) 지금 내 상황이 무엇인가

| 상황 | 갈 곳 |
|---|---|
| 아무것도 없는 PC 에 처음 받았다 | **A** → B |
| 설치는 끝났고 오늘 운동·시연만 하면 된다 | **B** |
| 폰·Quest 를 HTTPS 도메인으로 붙이려 한다 (폰 카메라는 사실상 이 경우다) | **C** → B |
| 지연 시간을 다시 재고 싶다 | **D** |

### A. 처음 세우기 (한 번만)

자세한 설명과 실패 시 대처는 [docs/00_환경_준비/00_처음_시작.md](docs/00_환경_준비/00_처음_시작.md) 에 있다.

```powershell
# A-1 브랜치 받기 (App 브랜치만)
git clone -b App https://github.com/logan0741/VR-Based-Real-Time-Agent.git
cd VR-Based-Real-Time-Agent

# A-2 Python 3.8 가상환경 (작성자 환경: Python 3.8.10, Node v22.20.0, npm 10.9.3)
py -3.8 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # 이 창에서만 .ps1 실행 허용
.\.venv\Scripts\Activate.ps1                                  # 스크립트는 그냥 `python` 을 부른다 → 반드시 활성화

# A-3 환경 변수 파일 (MySQL 이 없으면 DB_ENABLED=false 그대로 둔다)
Copy-Item .env.example .env

# A-4 의존성 설치 + 검증 + 앱 빌드 (서버는 아직 띄우지 않는다)
#     = pip install -r final\requirements.txt → npm --prefix final install
#       → py_compile → npm --prefix final run build (final\app_dist 재생성)
.\final\scripts\00_pipeline.ps1 -Install -NoServer

# A-5 DTW 라이브러리 확인 — 없으면 DTW 점수가 꺼진다(점수가 기본값 50 또는 피로도 값으로만 나옴)
python -c "import dtaidistance; print('dtaidistance ok')"
```

전문가 영상(`final/assets/expert_videos/*.mp4`)과 관절점 캐시(`*.npy`)는 커밋돼 있어 따로 받을 것이 없다.

### B. 하루 실행

자세한 순서는 [docs/10_실행/00_하루_운영.md](docs/10_실행/00_하루_운영.md) 에 있다.

```powershell
# B-1 서버 켜기 (검증·빌드 후 0.0.0.0:8000 으로 uvicorn 실행, 이 창은 열어 둔다)
.\.venv\Scripts\Activate.ps1
.\final\scripts\00_pipeline.ps1
#   빌드를 건너뛰고 바로 띄우려면:  .\final\scripts\03_run_server.ps1
```

- **B-2 폰에서 viewer 를 연다.** `https://viewer.<내 도메인>/viewer/` → `📷 웹캠 시작` → 카메라 허용. WebSocket 이 열려 있으면 MoveNet 결과를 서버 응답을 기다리지 않고 폰 화면에 바로 그리고, 약 15fps(`SEND_INTERVAL_MS = 66`)로 서버에 보낸다. 카메라 아래 상태 줄이 `detect N / send N / ws open …` 이면 정상, `waiting: ws …` 이면 WS 가 아직 안 붙은 것이다. viewer 는 `localhost`·`127.0.0.1` 이 아니면 **HTTPS 에서만** 카메라를 연다(`viewer.js` 의 `needsHttps` 검사). 그래서 폰은 C 의 터널 주소로 여는 것이 기본이다.
- **B-3 Quest 3 브라우저에서 app 을 연다.** `https://app.<내 도메인>/app/` 이 작성자가 쓴 방식이다. 앱은 카메라를 쓰지 않으므로 같은 Wi-Fi 에서 `http://<PC_IP>:8000/app/` 로도 열 수는 있다 — 이 조합은 이 문서를 쓰며 다시 확인하지 않았다.
- **B-4 운동을 고른다.** 스쿼트 / 해머 컬 / 레터럴 레이즈 / 풀업 중 하나와 `세트 수`(기본 3), `세트당 횟수`(기본 8)를 정하고 `운동 시작`. 앱이 `session_config`·`session_start` 를 보내면 서버가 폰 viewer 에 방송해 전문가 포즈가 같은 운동으로 바뀐다.
- **B-5 끝낸다.** 서버가 센 총 횟수가 `세트 수 × 세트당 횟수` 에 닿으면 앱이 스스로 종료 흐름을 탄다(수동 `운동 종료` 버튼과 같은 흐름). 결과 화면에 점수·등급·총 횟수·운동 시간·자세 정확도·최종 자세 분석이 나오고 TTS 음성을 자동으로 요청·재생한다. 서버 창에서 `Ctrl+C` 로 끈다.

### C. 도메인(터널)으로 쓰기

작성자는 Cloudflare Tunnel 하나로 세 호스트를 모두 `http://localhost:8000` 에 붙였다. **아래 `gun-hee.com` 은 작성자의 도메인이다. 반드시 자기 도메인으로 바꾼다.** 설정 파일 예시와 코드에서 고칠 두 곳은 [docs/00_환경_준비/01_도메인_터널.md](docs/00_환경_준비/01_도메인_터널.md) 에 있다.

| 호스트 (작성자) | 여는 주소 | 역할 |
|---|---|---|
| `viewer.gun-hee.com` | `/viewer/` | 폰 카메라 페이지 |
| `app.gun-hee.com` | `/app/` | Quest 앱 |
| `pt.gun-hee.com` | `/api/health`, `wss://pt.gun-hee.com/ws/pose` | API + **두 페이지가 함께 쓰는 WebSocket** |

```powershell
cloudflared tunnel run <터널이름>     # 서버(B-1)와 다른 창에서
```

두 페이지가 같은 WS 호스트를 써야 앱의 운동 선택 방송이 폰 viewer 에 닿는다. 이 호스트 이름은 `final/s05_frontend/viewer.js` 와 `final/src/hooks/useWebSocket.ts` 에 박혀 있어서, 자기 도메인을 쓰려면 두 파일을 고치고 `npm --prefix final run build` 를 다시 해야 한다.

### D. 지연을 잰다

```powershell
.\final\scripts\04_latency_check.ps1
#  = python final\latency_lab\run_latency_suite.py --frames 90 --fps 30 --exercise squat
#  로컬(ws://127.0.0.1:8000) → Cloudflare(wss://pt.gun-hee.com) 순서로 잰다.
#  터널이 없으면 로컬 보고서만 저장되고 Cloudflare 단계에서 에러로 멈춘다.

# 로컬만 재기
python final\latency_lab\measure_latency.py --ws-url ws://127.0.0.1:8000/ws/pose --label local
```

결과는 `final/latency_lab/results/` 의 커밋된 보고서를 덮어쓴다. 방법과 2026-06-13 측정값 전체는 [docs/30_지연_측정/01_측정_방법과_결과.md](docs/30_지연_측정/01_측정_방법과_결과.md) 에 있다.

### E. 무엇이 나오면 정상인가

`http://127.0.0.1:8000/api/health` (MySQL 없이 `DB_ENABLED=false`):

```json
{"status":"ok","database":{"enabled":false,"available":false,"error":"DB_ENABLED=false"}}
```

MySQL 을 켰고 연결됐다면 `"database":{"enabled":true,"available":true,"database":"vr_fitness"}` 가 나온다.

`http://127.0.0.1:8000/` → `{"service":"VR Pose Estimation Server","websocket":"/ws/pose","react_app":"/app/","viewer":"/viewer/"}`

서버 시작 로그. 2026-10-12 에 이 브랜치를 `DB_ENABLED=false` 로 실제로 띄워 받은 줄이다. 운동마다 한 줄씩 나오는 `[Pipeline] …` 줄은 `server.py` 소스 안의 한글 문자열이 이미 깨져 있어서 깨져 보인다(동작과 무관하므로 여기서는 생략).

```text
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
[Retargeter] Smoothing enabled: True
[Lifter] No checkpoint found. Running with initialized weights.
[ExpertPoseCache] .npy 로드: squat_full.npy (256프레임)
[ExpertPoseCache] .npy 로드: hammer_curl.npy (138프레임)
[ExpertPoseCache] .npy 로드: pull_up.npy (575프레임)
[ExpertPoseCache] .npy 로드: lateral_raise.npy (122프레임)
[Lifter] Pipeline Ready. Device: cpu
```

- `[Lifter] No checkpoint found…` 는 **정상**이다. 3D 리프터 잔재이고, 실시간 경로는 `REALTIME_2D_ONLY=true` 라서 2D 만 쓴다.
- 로그 앞쪽에 `[Pipeline] dtaidistance … pip install dtaidistance==2.3.12` 가 보이면 **비정상**이다. DTW 가 꺼져 점수가 기본값 50 이나 피로도 기반 값으로만 나온다.
- 화면: 폰 viewer 상태 줄에 `detect … / send … / ws open` 이 늘어나고, 내 뼈대가 바로 그려지며 전문가 포즈가 반복 재생된다. Quest 앱은 처음에 `측정 중입니다.` 를 띄우다가 프레임이 들어오면 교정 문장(교정할 것이 없을 때는 피로도 요약 `양호`·`주의: …`)·빨간 관절·점수·횟수가 바뀐다. 몸이 화면 밖이면 `전신이 카메라 …` 로 시작하는 안내가 뜨고 점수·횟수는 멈춘다(정상 동작).

### F. 막혔을 때 어디를 보나

모두 [docs/10_실행/01_트러블슈팅.md](docs/10_실행/01_트러블슈팅.md) 에 번호로 있다.

| 증상 | 트러블슈팅 항목 |
|---|---|
| 서버가 `[Errno 10048]` 으로 안 뜬다 / 8000 포트 충돌 | 1. 포트 8000 |
| `pip install` 이 dtaidistance 에서 실패, 또는 점수가 50 근처에서 DTW 와 무관하게 나온다 | 2. dtaidistance |
| Python 3.8 에서 `'type' object is not subscriptable` | 3. Python 3.8 타입 힌트 |
| 폰에서 카메라가 안 켜진다 / `Camera requires HTTPS` | 4. HTTPS |
| 카메라는 켜졌는데 관절점이 안 나온다 (MoveNet 모델 fetch 실패) | 5. CSP |
| 앱에서 운동을 바꿔도 폰 전문가 포즈가 안 바뀐다 / 도메인에서 WS 가 끊긴다 | 6. WS 호스트 |
| 앱의 내 뼈대가 끊기고 늦다 | 7. relay·processed 분리 |
| 실시간 피드백이 전혀 안 나온다 / 계속 `전신이 카메라…` | 8. 카메라 게이트 |
| 뼈대가 눕거나 뒤집혀 보인다 | 9. 좌표 회귀 |
| `.ps1` 실행이 막힌다 | 10. ExecutionPolicy |

---

## 무엇을 하는 브랜치인가

최종 제출물이다. 2D 관절점만으로 운동 자세를 실시간 교정한다. 설계의 핵심은 **경로 두 개**다.

| 경로 | 서버에서 하는 일 | 앱에서 쓰는 곳 | 로컬 평균 / p95 | Cloudflare 평균 / p95 |
|---|---|---|---:|---:|
| relay | 받자마자 `data_type: "pose"` 로 방송 | 내 자세 뼈대 | 4.235 / 5.607 ms | 201.012 / 235.606 ms |
| processed | 최신 프레임만 골라 게이트·정규화·횟수·DTW·피드백 | 점수·횟수·피드백·빨간 관절 | 9.509 / 35.33 ms | 205.692 / 247.397 ms |

(2026-06-13, 합성 COCO-17 90 프레임 @30fps, 앱 수신 기준. 네 경로 모두 90/90 프레임이 도착했다.) 로컬에서는 서버 처리가 병목이 아니고, 도메인 경유 지연은 대부분 Cloudflare·네트워크 구간에서 생긴다. 브라우저의 MoveNet 추론과 캔버스 그리기 시간은 이 수치에 들어 있지 않다.

**일부러 넣지 않은 것**

- 3D 리프팅·SMPL-X — [`Pose3D`](../../tree/Pose3D). `server.py` 에 `PoseLifterNet`·`/api/expert-smplx` 같은 잔재가 남아 있지만 실시간 경로에서는 쓰지 않는다. 다만 `server.py` 가 `torch` 를 import 하므로 설치는 필요하다.
- Unity 아바타 — [`Avatar3D`](../../tree/Avatar3D) (중단).
- LLM — 최종 피드백은 프롬프트 생성이 아니라 운동 중 쌓인 피드백 샘플을 집계하는 결정적(deterministic) 로직이다(`final/src/App.tsx` 의 `buildFinalFeedback`).

## 코드 구성

| 경로 | 한 줄 설명 |
|---|---|
| [`final/s01_preprocessing/`](final/s01_preprocessing) | 운동 설정(`config.py`), 정규화, 횟수 상태 머신(`rep_rules.py`·`rep_signals.py`·`rep_detector.py`), DTW·점수, 피드백 엔진·hold 정책 |
| [`final/s02_backend/`](final/s02_backend) | FastAPI 서버(`server.py`): `/ws/pose` relay·processed, 세션 진행(`session_progress.py`), `/viewer/`·`/app/`·`/assets/` 정적 서빙, viewer CSP |
| [`final/s03_database/`](final/s03_database) | 선택 MySQL 저장 (`exercise_sessions` 테이블) |
| [`final/s05_frontend/`](final/s05_frontend) | 폰 viewer: TF.js MoveNet Lightning, 로컬 뼈대, 전문가 포즈, WS 전송 |
| [`final/s07_tts/`](final/s07_tts) | 최종 피드백 TTS (pyttsx3 → `final/assets/tts/*.wav`) |
| [`final/src/`](final/src) | Quest 앱 React 소스 (Vite + TypeScript) |
| [`final/app_dist/`](final/app_dist) | 위 소스의 빌드 결과. 서버가 `/app/` 으로 바로 서빙하므로 커밋한다 |
| [`final/assets/expert_videos/`](final/assets/expert_videos) | 전문가 영상 + 관절점 캐시 `.npy` (서버 시작 시 로드) |
| [`final/latency_lab/`](final/latency_lab) | WebSocket 지연 측정 도구와 결과 |
| [`final/scripts/`](final/scripts) | `00_pipeline`(한 번에) · `01_install` · `02_build_app` · `03_run_server` · `04_latency_check` · `05_verify` |
| [`tools/extract_expert_keypoints.py`](tools/extract_expert_keypoints.py) | MediaPipe 로 영상에서 관절점 JSON 을 뽑던 이전 도구. 지금 앱이 읽는 `.npy` 캐시를 만드는 도구는 아니다(출력은 이전 3D 경로용 픽셀 좌표 JSON). 기록용으로 둔다 |
| [`versions/`](versions) | 판정 규칙 변형 3 개의 기록. 채택된 동작은 `final/` 에 들어 있다 → [versions/README.md](versions/README.md) |

`final/` 안의 영문 원본 문서: [FINAL_ARCHITECTURE.md](final/FINAL_ARCHITECTURE.md) · [PIPELINE.md](final/PIPELINE.md) · [FINAL_HANDOFF_REPORT.md](final/FINAL_HANDOFF_REPORT.md) · [REPORT_SYSTEM_STRUCTURE.md](final/REPORT_SYSTEM_STRUCTURE.md) · [REPORT_COMPONENT_STRUCTURES.md](final/REPORT_COMPONENT_STRUCTURES.md)

## 판정 규칙 요약

- **좌표**: 어디서나 COCO-17 `[y, x, confidence]`, 0~1 정규화다. 좌우 반전은 그릴 때만 한다. 폰 세로 화면 회전은 viewer 로컬 미리보기에만 적용하고 서버로 가는 값은 원본이다. → [01_좌표_규약](docs/20_판정_규칙/01_좌표_규약.md)
- **카메라 게이트**: 운동별 `keypoints_used` 관절 중 하나라도 confidence 가 `0.12` 미만이거나 화면 가장자리 `0.01` 안쪽이면 `countable=false` — 안내 문장만 보내고 점수·횟수는 올리지 않는다.
- **횟수**: 피드백이 아니라 관절 각도 상태 머신 `WAIT_READY → WAIT_TARGET → WAIT_RETURN` 으로 센다. 예: 스쿼트는 무릎 각도 155° 이상 → 125° 이하 → 150° 이상, 최소 가동범위 25°. → [02_횟수_규칙](docs/20_판정_규칙/02_횟수_규칙.md)
- **피드백 hold**: 의미 있는 피드백 1 개를 받으면 기본 `target_fps × 3` 프레임(약 3 초) 유지하고 그동안 새 이벤트를 쌓지 않는다. `feedback_event=true` 인 것만 최종 분석 샘플이 된다. → [03_피드백과_결과](docs/20_판정_규칙/03_피드백과_결과.md)
- **자동 종료**: 앱이 보낸 `sets`·`reps_per_set` 으로 서버가 `total_target_reps = sets × reps_per_set` 를 계산하고, 도달하면 `completed=true` → 앱이 종료 흐름을 실행한다. 앱에 따로 도는 더미 카운터는 없다.
- **최종 리포트**: 결정적 집계(평균·최고·최저 점수, 반복된 문제 부위·문장, 피로 부위) + TTS. LLM 이 아니다.
- **변형 기록**: [04_판정_변형_기록](docs/20_판정_규칙/04_판정_변형_기록.md)

## 기록이 쌓이는 모양

| 무엇 | 어디 | 커밋 |
|---|---|---|
| 최종 피드백 음성 | `final/assets/tts/final_feedback_<payload 해시 16자>.wav`. 같은 내용이면 다시 만들지 않고 재사용한다(`cached: true`) | 안 함 (`.gitignore`) |
| 운동 세션 요약 | MySQL `vr_fitness.exercise_sessions` (session_id, user_id, exercise_type, 시작·끝 시각, duration_ms, frame_count, avg/best/worst_score, final_label, summary_json). `DB_ENABLED=true` 이고 연결될 때만 | — |
| 지연 측정 | `final/latency_lab/results/latency_report_{local,cloudflare}.{json,md}`, `latency_suite_summary.{json,md}`, 마지막 단발 측정 `latency_report.{json,md}`. 돌릴 때마다 덮어쓴다 | 함 (현재 2026-06-13 값) |
| 서버·터널 로그 | 콘솔 출력. 파일로 남기면 `*.log`, `server_*.txt`, `cloudflared_*.txt` 는 무시된다 | 안 함 |

## 문서

| 위치 | 무엇을 찾나 |
|---|---|
| [docs/README.md](docs/README.md) | 문서 ↔ 코드 폴더 지도 |
| [docs/00_전체흐름_단계별.md](docs/00_전체흐름_단계별.md) | viewer 5 → relay 3 → processing 8 → app 7 → 지연, 번호 붙은 데이터 흐름 |
| [docs/00_환경_준비/](docs/00_환경_준비) | 빈 Windows PC 설치, Cloudflare 터널 |
| [docs/10_실행/](docs/10_실행) | 하루 운영 순서, 트러블슈팅 |
| [docs/20_판정_규칙/](docs/20_판정_규칙) | 좌표 규약, 횟수 규칙, 피드백·결과, 판정 변형 |
| [docs/30_지연_측정/](docs/30_지연_측정) | 측정 방법과 전체 결과 표 |
| [docs/40_기록/](docs/40_기록) | 인계 문서(2026-05-21), Last Dance 파이프라인(2026-06-09), last_dance 작업 노트, 사용자 업무 계획서 — 당시 경로 그대로 둔 역사 기록 |

## 다른 브랜치

| 브랜치 | 내용 |
|---|---|
| [`main`](../../tree/main) | 프로젝트 전체 서사와 브랜치 안내 |
| [`Pose3D`](../../tree/Pose3D) | 2D → 3D 리프팅(PoseLifterMLP) 학습·실험 |
| [`Avatar3D`](../../tree/Avatar3D) | Unity·SMPL-X 3D 아바타 시도 (중단) |
| [`docs-archive`](../../tree/docs-archive) | 재편 이전 작업 공간 전체 스냅샷 (2026-03 ~ 2026-06) |
