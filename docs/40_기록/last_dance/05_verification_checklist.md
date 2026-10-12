# 05 Verification Checklist

푸시 전에는 같은 종류의 확인을 최소 2회 이상 반복한다.

## 1. 기본 빌드

```powershell
npm run build
```

성공 기준:

- TypeScript error 없음
- Vite build 성공
- `dist/index.html`이 새 asset hash를 참조

## 2. Python 문법 검사

```powershell
python -m py_compile final\s01_preprocessing\rep_detector.py final\s02_backend\server.py
```

성공 기준:

- 출력 없이 종료

## 3. 서버 실행 확인

```powershell
python -m uvicorn final.s02_backend.server:app --host 0.0.0.0 --port 8000
```

별도 창 또는 hidden process로 띄운 뒤:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/session-control
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/session-control
```

성공 기준:

- 두 번 모두 `status: ok`
- `control.exercise_type`, `sets`, `reps_per_set` 확인 가능

## 4. WebSocket progress 확인

확인해야 하는 값:

- `feedback.rep_count`
- `feedback.current_set`
- `feedback.rep_in_set`
- `progress.total_reps`
- `progress.total_target_reps`

성공 기준:

- 같은 테스트를 2회 보냈을 때 같은 결과
- 2회 동작 시 `rep_count=2`

## 5. 세트 경계값 확인

3세트, 8회 기준:

| total reps | expected |
| ---: | --- |
| 7 | 1세트 7/8 |
| 8 | 1세트 8/8 |
| 9 | 2세트 1/8 |
| 16 | 2세트 8/8 |
| 17 | 3세트 1/8 |
| 24 | 3세트 8/8 완료 |

## 6. 실제 화면 확인

viewer:

- 카메라 켜짐
- detect/send 증가
- 내 자세 skeleton 움직임
- 선택한 운동의 전문가 포즈 표시

app:

- 내 자세 skeleton 움직임
- 강사 모델 운동 변경 반영
- reps가 현재 세트 기준으로 보임
- total reps가 누적 기준으로 보임
- score/feedback이 한국어로 보임

## 7. 푸시 전 금지

다음 상태에서는 푸시하지 않는다.

- 서버가 Python 3.8에서 시작하지 않음
- `npm run build` 실패
- WebSocket 응답에 `progress` 없음
- 실제 화면에서 내 자세가 멈춤
- rep count가 작은 흔들림을 세거나 확실한 움직임을 못 셈
- 임시 로그와 테스트 파일이 stage됨

