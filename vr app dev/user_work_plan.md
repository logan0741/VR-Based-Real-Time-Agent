# 사용자 업무 계획서 - Quest 3 VR/MR 테스트 앱

작성일: 2026-06-04

## 0. 추가 전제 - 휴대폰 2대 + 블루투스 카메라 연결

사용자 의도는 기존 서버/웹 구조를 완전히 버리는 것이 아니라, 기존 전처리와 좌표 기반 로직은 가져가되 레이턴시를 줄이기 위해 휴대폰 카메라 2개를 VR 앱 쪽에 더 직접 연결하는 것이다.

냉정하게 말하면, "블루투스로 휴대폰 카메라 2대의 영상 또는 실시간 좌표를 Quest 3에 안정적으로 보내는 구조"는 1차 MVP 주 통신 방식으로 부적합하다.

- 영상 스트림을 블루투스로 보내는 것은 대역폭과 지연 시간 측면에서 사실상 맞지 않는다.
- keypoints 좌표만 보내면 데이터량은 작지만, 휴대폰 2대 동기화, Quest Unity 앱의 Android Bluetooth 처리, 연결 복구, 권한 처리, 패킷 순서 보장까지 직접 만들어야 한다.
- 블루투스는 설정/페어링/권한에서 막히는 시간이 길고, 실시간 운동 피드백의 주 경로로 쓰기에는 디버깅 비용이 크다.
- 서버 경유 레이턴시가 문제라면, 먼저 서버를 제거하는 것이 아니라 "영상 전송을 없애고 keypoints만 로컬망으로 전송"하는 쪽이 더 효과적이다.

따라서 권장 구조는 다음 순서다.

1. 휴대폰 2대에서 각자 포즈 추정 실행
2. 영상은 보내지 않고 `[y, x, confidence] x 17` 좌표만 전송
3. 전송은 블루투스가 아니라 같은 Wi-Fi의 UDP/WebSocket/WebRTC DataChannel 중 하나로 처리
4. Quest 앱 또는 PC 로컬 서버에서 두 카메라 좌표를 시간 기준으로 병합
5. 기존 전처리, DTW, 피드백 로직은 최대한 유지

블루투스는 나중에 버튼, 시작/정지, 기기 상태, 간단한 센서값 같은 저용량 제어 채널로 쓰는 편이 맞다.

## 1. 냉정한 가능 여부

가능하다. 단, "Quest 3 하나만 쓰면 전신 운동 자세를 정확히 인식한다"는 방향은 현실성이 낮다.

현재 서버는 17개 2D keypoints를 받아서 3D pose, DTW 점수, 피드백, rep count를 계산하는 구조다. 이 구조를 VR 앱으로 옮기는 가장 현실적인 방식은 다음과 같다.

- Quest 3 앱: VR/MR 화면, 아바타, 점수, 피드백, 운동 UI 표시
- 휴대폰 또는 외부 카메라: 사용자의 전신을 촬영하고 2D keypoints 생성
- 현재 FastAPI 서버: WebSocket으로 keypoints 수신, 점수/피드백 계산, Quest 앱에 결과 송신

Quest 3 자체 passthrough 카메라는 MR 배경과 일부 컴퓨터 비전에는 쓸 수 있지만, 착용자 본인의 전신을 안정적으로 볼 수 없다. 그래서 스쿼트 같은 자세 교정은 휴대폰 카메라나 PC 웹캠 같은 외부 시점이 필요하다.

무료 테스트 앱 구성은 가능하다. Meta Quest 개발자 모드, Unity Personal, 로컬 Wi-Fi, APK sideload 방식으로 Store 출시 없이 테스트할 수 있다. 다만 실제 배포, 계정 정책, 스토어 심사, 개인정보 고지는 별도 과제다.

## 2. 추천 아키텍처

### 2.1 기존 권장안

1. 휴대폰과 Quest 3를 같은 Wi-Fi에 연결한다.
2. PC에서 현재 FastAPI 서버를 실행한다.
3. 휴대폰은 웹 페이지 또는 간단한 모바일 입력 앱으로 사용자의 전신을 촬영한다.
4. 휴대폰에서 MoveNet/MediaPipe로 `[y, x, confidence] x 17` keypoints를 만든다.
5. 휴대폰이 서버 `/ws/pose`로 keypoints를 보낸다.
6. 서버가 기존 `final/s02_backend/server.py` 파이프라인으로 점수와 피드백을 계산한다.
7. Quest 3 Unity 앱이 같은 WebSocket 서버에 연결해 결과를 받아 VR/MR 공간에 표시한다.

### 2.2 레이턴시 개선용 2카메라 권장안

최종 목표가 "VR 앱에서 거의 실시간으로 보는 것"이면 다음 구조가 더 맞다.

```text
Phone A Camera ─┐
                ├─ keypoints only ─ local Wi-Fi ─ Quest 3 app or local aggregator ─ preprocessing/score
Phone B Camera ─┘
```

운영 방식:

- 휴대폰 A: 측면 촬영
- 휴대폰 B: 정면 또는 45도 보조 촬영
- 각 휴대폰에서 MoveNet 또는 MediaPipe 실행
- 각 프레임에 `camera_id`, `frame_id`, `timestamp_ms`, `keypoints` 포함
- Quest 앱 또는 PC 로컬 프로세스가 timestamp 기준으로 두 카메라 프레임을 맞춤
- 처음에는 3D triangulation까지 가지 말고, 더 신뢰도 높은 카메라의 keypoints를 선택하거나 부위별로 병합

1차 MVP에서는 PC 서버를 완전히 없애지 말고, 다음 두 단계로 줄이는 것을 권장한다.

1. 서버는 유지하되 영상 전송 없이 좌표만 받도록 최적화
2. 충분히 안정화되면 전처리/점수 로직 일부를 Quest 앱 또는 로컬 Android 플러그인으로 옮김

## 2.3 레이턴시 감소 보장 여부

보장할 수 없다. 구조를 바꾼다고 자동으로 레이턴시가 줄어드는 것은 아니다.

레이턴시는 다음 구간의 합이다.

```text
카메라 캡처
+ 휴대폰 포즈 추정
+ 좌표 전송
+ 서버/Quest 수신
+ 전처리/DTW/피드백 계산
+ Quest 렌더링
= 전체 체감 지연
```

현재 구조에서 병목이 "서버 계산"이면 휴대폰 2대를 붙여도 빨라지지 않을 수 있다. 병목이 "웹/서버 간 영상 또는 좌표 전달", "브라우저 렌더링", "네트워크 왕복"이면 keypoints-only 구조가 빨라질 가능성이 크다.

따라서 목표는 보장이 아니라 측정 기반 검증이다.

1차 측정 기준:

- 휴대폰 카메라 프레임 생성 시각
- 포즈 추정 완료 시각
- 서버 수신 시각
- 서버 처리 완료 시각
- Quest 수신 시각
- Quest 화면 표시 시각

성공으로 볼 수 있는 수치:

- 휴대폰 1대 기준 end-to-end 150ms 이하
- 휴대폰 2대 기준 end-to-end 200ms 이하
- 서버 `debug.inference_ms`가 30ms 이하
- Quest 앱 프레임이 72 FPS 유지

실패 또는 재설계 기준:

- 휴대폰 포즈 추정만 100ms 이상 걸림
- 2카메라 동기화 때문에 100ms 이상 기다려야 함
- 서버 DTW 계산이 프레임마다 밀림
- Quest 앱 표시가 안정적이지 않음

결론적으로 1차 목표는 "서버 제거"가 아니라 "영상 전송 제거, 좌표만 전송, 각 구간 timestamp 측정"이다.

## 3. 사용자가 직접 해야 하는 일

## A. 장비와 계정 준비

- Meta Quest 3 충전 및 Horizon OS 업데이트
- 개발용 PC 준비
- Android 빌드 가능한 Unity 설치
- Meta 개발자 계정 생성 및 개발자 조직 생성
- Meta Horizon 모바일 앱에서 Quest 3 개발자 모드 활성화
- USB-C 케이블 또는 같은 Wi-Fi 환경 준비
- Meta Quest Developer Hub 또는 ADB로 APK 설치 테스트

## B. 테스트 환경 준비

- PC, 휴대폰, Quest 3를 같은 네트워크에 연결
- PC 방화벽에서 FastAPI 서버 포트 허용, 기본은 `8000`
- 서버 접속 주소 확정: 예시 `ws://<PC_IP>:8000/ws/pose`
- 휴대폰 2대 사용 시 각 기기의 카메라 위치와 IP를 기록
- 두 휴대폰의 시간 오차를 줄이기 위해 테스트 시작 전에 서버 시간 기준 ping 또는 handshake 수행
- `.env`에서 `DB_ENABLED=false`로 먼저 시작 권장
- `LIFTER_CHECKPOINT` 파일 존재 여부 확인
- `final/assets/expert_videos/squat_full.npy` 존재 여부 확인

## C. 촬영 환경 준비

- 휴대폰을 사용자의 전신이 보이도록 2~3m 거리, 허리 높이 근처에 고정
- 스쿼트 기준으로 측면 촬영 권장
- 휴대폰 2대 구성에서는 한 대는 측면, 한 대는 정면 또는 대각선 전방 배치
- 두 카메라 모두 머리부터 발까지 들어오게 고정
- 조명 확보
- 배경이 복잡하지 않은 공간 확보
- 카메라 프레임 안에 머리부터 발까지 들어오는지 확인

## D. Quest 3 테스트

- Unity로 만든 APK를 Quest 3에 sideload
- 앱 실행 후 서버 URL 입력 또는 고정 설정 확인
- WebSocket 연결 상태 확인
- 휴대폰에서 카메라 입력 시작
- Quest 3 화면에서 점수, rep count, 피드백, 아바타 움직임 확인
- 10분 이상 착용 테스트로 멀미, 발열, 네트워크 끊김 확인

## E. 판단 기준

1차 성공 기준:

- 휴대폰 keypoints가 서버로 안정적으로 들어간다.
- Quest 3 앱이 서버 피드백을 1초 이내로 표시한다.
- 스쿼트 rep count가 대략 맞는다.
- 점수 변화가 동작 변화와 눈에 띄게 연동된다.
- 앱이 10분 테스트 동안 꺼지지 않는다.

실패로 봐야 하는 기준:

- Quest 단독 카메라만으로 전신 자세 분석을 하려는 경우
- 휴대폰 2대 영상을 블루투스로 Quest에 직접 스트리밍하려는 경우
- 휴대폰 영상이 계속 끊기거나 keypoints confidence가 낮은 경우
- 서버와 Quest가 같은 네트워크에서도 WebSocket 연결을 유지하지 못하는 경우
- VR 앱 프레임이 72 FPS 아래로 자주 떨어지는 경우

## 4. 사용자 의사결정이 필요한 부분

- 입력 카메라를 휴대폰으로 할지, PC 웹캠으로 할지
- 첫 테스트를 VR 공간으로 할지, passthrough MR 공간으로 할지
- Quest 앱을 Unity로 만들지, WebXR/브라우저 기반으로 최대한 유지할지
- 서버를 PC 로컬에서 돌릴지, 추후 클라우드/터널로 뺄지
- 개인정보 처리 방침을 어느 수준까지 문서화할지

## 5. 권장 일정

### 1일차

- Quest 개발자 모드 설정
- Unity Android 빌드 환경 구성
- 기존 서버 실행 확인
- 휴대폰/Quest/PC 같은 Wi-Fi 연결 확인

### 2일차

- Quest Unity 빈 앱 APK 설치
- WebSocket 연결 테스트
- 서버 health check 및 `/ws/pose` 연결 확인

### 3일차

- 휴대폰 카메라 입력 연결
- keypoints 송신 확인
- Quest 앱에서 점수와 피드백 표시

### 4일차

- VR/MR UI 배치
- 아바타 또는 간단 skeleton 표시
- 스쿼트 10회 테스트

### 5일차

- 지연 시간, 프레임, 연결 안정성 측정
- 문제 목록 정리
- 다음 단계 결정

## 6. 참고 공식 문서

- Unity Meta Quest 개발 워크플로: https://docs.unity.cn/Manual/xr-meta-quest-develop.html
- Unity Quest 3 Mixed Reality/OpenXR 안내: https://unity.com/blog/engine-platform/cross-platform-mixed-reality-development-on-meta-quest-3
- Meta Passthrough Camera API 개요: https://developers.meta.com/horizon/documentation/unity/unity-pca-overview/
- Meta Quest 앱 성능 기준: https://developers.meta.com/horizon/documentation/unreal/po-perf-opt-mobile/
