# AI 업무 계획서 - Quest 3 VR/MR 테스트 앱 구현 지원

작성일: 2026-06-04

## 0. 추가 전제 - 휴대폰 2대 카메라와 저지연 구조

새 목표는 기존 서버/웹 구성의 레이턴시를 줄이고, 휴대폰 카메라 2대를 이용해 VR 앱에서 더 실시간에 가깝게 자세 피드백을 보는 것이다.

AI의 기술 판단:

- 블루투스를 주 통신로로 쓰는 설계는 권장하지 않는다.
- 영상은 절대 보내지 않고, 휴대폰 안에서 포즈 추정 후 keypoints만 보내야 한다.
- 좌표 전송도 블루투스보다 로컬 Wi-Fi 기반 UDP/WebSocket/WebRTC DataChannel이 맞다.
- 기존 `final/s01_preprocessing`의 전처리, DTW, feedback 로직은 살리되, 서버 경유 횟수와 payload를 줄이는 방향으로 간다.

권장 우선순위:

1. 휴대폰 1대 keypoints-only 저지연 송신
2. 휴대폰 2대 `camera_id + timestamp_ms` 송신
3. 서버에서 2카메라 프레임 동기화/선택 병합
4. Quest 앱에서 결과 표시
5. 이후 병목이 서버이면 전처리 일부를 Quest 앱으로 이식

## 1. AI가 맡을 수 있는 범위

AI는 현재 `final/` 서버를 기반으로 Quest 3 테스트 앱 개발에 필요한 코드, 문서, 설정, 통신 프로토콜, 테스트 절차를 만들 수 있다. 단, 실제 Quest 3 착용 테스트, 개발자 모드 활성화, Unity 에디터에서 APK 빌드 버튼을 누르는 일, 휴대폰 카메라 위치 조정은 사용자가 해야 한다.

## 2. 핵심 구현 방향

첫 버전은 "네이티브 Quest 앱 + 현재 서버 유지 + 휴대폰/외부 카메라 입력" 구조로 간다.

다만 레이턴시 개선을 위해 영상 스트림은 금지하고, 휴대폰에서 포즈 추정까지 끝낸 뒤 좌표만 전송한다.

중요한 전제:

레이턴시 감소는 보장하지 않는다. AI의 1차 작업은 구조를 바꾸기 전에 현재 병목을 숫자로 보이게 만드는 것이다.

AI가 우선 구현할 목표:

- 기존 `final/s02_backend/server.py` WebSocket 프로토콜을 그대로 사용
- Quest Unity 앱에서 서버 응답을 받아 점수/피드백/rep count 표시
- 기존 Unity 스크립트 `final/s06_unity_vr/WebSocketClient.cs`, `FitnessAvatarController.cs`를 테스트 앱 구조에 맞게 정리
- 휴대폰 브라우저 입력 페이지 또는 기존 `final/s05_frontend/viewer.js`를 입력 전용 모드로 분리
- 서버 연결 상태, latency, frame count를 디버깅 가능하게 표시
- 2카메라 입력을 위해 `camera_id`, `timestamp_ms`, `source_fps`를 프로토콜에 추가
- 각 처리 구간별 timestamp를 추가해 end-to-end latency를 측정

## 3. AI 작업 단계

## A. 문서와 구조 정리

- `vr app dev/` 아래에 개발 메모, 테스트 체크리스트, 프로토콜 문서 추가
- 현재 `final/backend/`와 `final/s02_backend/` 차이 정리
- 실행 기준을 `final/07_pipeline_web.py`, `final/08_pipeline_full.py`, `final.s02_backend.server:app`로 통일하는 권장안 작성
- WebSocket 메시지 스키마 문서화
- 2카메라 keypoints-only 프로토콜 문서화
- 블루투스는 제어 채널로만 쓰는 제한 사항 명시

산출물:

- `vr app dev/protocol.md`
- `vr app dev/test_checklist.md`
- `vr app dev/architecture.md`

## B. 서버 안정화

- `/api/health`에 현재 backend, DTW availability, loaded exercises, expert cache 상태 추가
- WebSocket 연결별 exercise type, preprocessing session 상태를 디버그 응답에 포함
- `session_start` 때 지원하지 않는 exercise가 들어오면 명확한 warning 반환
- `keypoints` 메시지에 `camera_id`, `timestamp_ms`가 들어와도 기존 단일 카메라 흐름이 깨지지 않게 처리
- 서버 수신 시각, 처리 완료 시각, inference ms, preprocessing ms를 응답 `debug`에 포함
- 2카메라 입력 버퍼를 추가해 timestamp 차이가 작은 프레임끼리 묶기
- 1차 병합은 "confidence 높은 쪽 선택" 또는 "부위별 confidence 기반 선택"으로 단순하게 시작
- `pipeline_web_only.py`, `pipeline_full.py`가 구버전 `final.backend.server:app`를 보는 문제를 정리하거나 deprecate 문구 추가
- 한글 인코딩 깨짐이 코드 문자열에 영향을 주는 부분은 새 UTF-8 메시지 상수로 분리

검증:

- `python final/01_test_preprocessing.py`
- `python final/02_test_backend.py`
- 서버 실행 후 `/api/health` 확인
- 테스트 입력 100프레임 기준 평균/최대 latency 출력

## C. 휴대폰 입력 페이지

- 기존 `final/s05_frontend/viewer.js`에서 카메라 입력 로직을 재사용
- 휴대폰 전용 페이지를 만들어 카메라 preview, 서버 URL, connection status, confidence 상태만 표시
- keypoints를 현재 서버 형식 `{ data_type: "keypoints", frame_id, payload }`로 송신
- 2카메라 모드에서는 `{ data_type, camera_id, frame_id, timestamp_ms, payload }`로 송신
- 각 휴대폰에서 카메라 역할을 `side`, `front`로 지정 가능하게 구성
- 서버가 아닌 Quest 앱에 직접 보낼 경우를 대비해 WebRTC DataChannel 또는 UDP 경로를 별도 설계
- 포즈 추정 시작/완료 시각과 송신 시각을 payload 또는 debug 로그에 포함
- 촬영 방향 안내는 문서로 분리하고 앱 화면에는 최소화

산출물 후보:

- `vr app dev/mobile_input/index.html`
- `vr app dev/mobile_input/mobile_pose_sender.js`
- 또는 `final/s05_frontend/mobile.html`

주의:

- HTTPS가 아니면 모바일 브라우저 카메라 권한이 막힐 수 있다.
- 로컬 테스트는 `localhost`가 아니면 HTTPS 또는 브라우저 예외가 필요할 수 있다.
- Cloudflare tunnel 사용 시 WebSocket URL은 `wss://.../ws/pose` 형태가 된다.
- 블루투스로 휴대폰 카메라 영상을 보내는 구현은 MVP 범위에서 제외한다.
- 블루투스로 keypoints를 보내는 구현도 마지막 fallback으로만 둔다.

## D. Quest Unity 테스트 앱

- Unity 프로젝트 생성 가이드 작성
- Android target, OpenXR/Meta XR 설정 체크리스트 작성
- 기존 `WebSocketClient.cs`를 Quest 앱용으로 개선
- `FeedbackData`에 `message`, `rep_count`, `severity`, `body_part` 필드 추가
- 서버 URL을 Inspector 또는 앱 내 입력으로 바꿀 수 있게 구성
- 연결 상태, 점수, rep count, 피드백 텍스트를 World Space Canvas로 표시
- 초기 버전에서는 복잡한 아바타보다 skeleton/텍스트 UI 우선
- 2카메라 모드에서는 현재 사용 중인 카메라 소스와 timestamp drift를 디버그 UI에 표시

산출물 후보:

- `vr app dev/unity/Scripts/QuestPoseWebSocketClient.cs`
- `vr app dev/unity/Scripts/QuestFeedbackPanel.cs`
- `vr app dev/unity/UNITY_SETUP.md`

## E. MR/Passthrough 단계

1차는 VR 공간에서 동작 확인.

2차에서 Quest 3 passthrough MR로 전환:

- Passthrough 배경 활성화
- 점수 UI를 사용자 전방 1.5~2m에 고정
- 바닥 기준 anchor 또는 simple world-lock UI 구성
- 손/controller interaction은 최소 기능만 구현

주의:

- Quest 3 passthrough camera access는 가능하지만, 착용자 전신 자세 인식 용도로 쓰기 어렵다.
- 공식 문서상 Passthrough Camera API는 Quest 3/3S와 Horizon OS v74 이상, camera permission, passthrough feature enable 조건이 있다.
- 카메라 이미지 처리는 개인정보와 성능 리스크가 크므로 1차 MVP에서는 쓰지 않는 편이 낫다.

## F. 성능과 안정성 테스트

- Quest 앱은 72 FPS 아래로 자주 떨어지면 실패로 간주
- WebSocket reconnect 처리
- 서버 지연 시간 `debug.inference_ms` 표시
- 휴대폰 1대 송신 FPS 15/24/30 비교
- 휴대폰 2대 동시 송신 FPS 15/24/30 비교
- timestamp drift와 frame drop 측정
- 5분, 10분 연속 테스트 로그 정리

테스트 순서:

1. 기존 웹/서버 구조 latency 측정
2. 휴대폰 1대 keypoints-only 구조 측정
3. 휴대폰 2대 keypoints-only 구조 측정
4. 서버 처리 최적화 후 재측정
5. 필요할 때만 Quest 앱 내 전처리 이식 검토

측정 항목:

- keypoints send FPS
- server inference ms
- Quest receive FPS
- end-to-end 체감 지연
- WebSocket reconnect 횟수
- rep count 정확도
- 두 카메라 timestamp 차이
- 카메라별 keypoints confidence 평균

## 4. AI가 하지 못하는 일

- Quest 3 개발자 모드 직접 활성화
- Meta 계정/개발자 조직 생성
- Unity 에디터 GUI에서 패키지 설치 버튼 직접 클릭
- 실제 APK를 Quest 3에서 착용 테스트
- 휴대폰 카메라 물리 위치 조정
- Meta Store/App Lab 심사 통과 보장
- 운동 자세 정확도 보장

## 5. 우선순위

1. 서버와 Quest 앱 WebSocket 연결
2. Quest 앱에서 점수/피드백 표시
3. 휴대폰 입력 페이지 분리
4. 스쿼트 10회 테스트
5. MR passthrough UI 적용
6. 아바타/SMPL-X 표현 개선
7. 다른 운동 종목 확장

## 6. 리스크

- 현재 `squat` 외 종목은 `implemented=False`
- 현재 피드백 메시지 일부가 인코딩 깨짐 상태
- 휴대폰 브라우저 카메라 권한은 HTTPS 조건에 걸릴 수 있음
- 같은 Wi-Fi라도 학교/공공망에서는 기기 간 통신이 막힐 수 있음
- 블루투스는 영상 스트리밍용으로 부적합하고, keypoints 전송용으로도 구현 난이도 대비 이득이 작음
- 휴대폰 2대는 카메라 시간 동기화 문제가 생김
- 2카메라 좌표를 섞으면 오히려 노이즈가 늘 수 있으므로 단순 병합부터 검증해야 함
- Quest 앱은 VR comfort 때문에 72 FPS 유지가 중요함
- 서버가 PC에 있으면 외부 이동 환경에서는 바로 쓰기 어려움

## 7. 참고 공식 문서

- Unity Meta Quest 개발 워크플로: https://docs.unity.cn/Manual/xr-meta-quest-develop.html
- Unity Quest 3 Mixed Reality/OpenXR 안내: https://unity.com/blog/engine-platform/cross-platform-mixed-reality-development-on-meta-quest-3
- Meta Passthrough Camera API 개요: https://developers.meta.com/horizon/documentation/unity/unity-pca-overview/
- Meta Quest 앱 성능 기준: https://developers.meta.com/horizon/documentation/unreal/po-perf-opt-mobile/
