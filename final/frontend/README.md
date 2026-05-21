# Frontend

React + TypeScript + Vite 대시보드. 운동 선택 → 세션 → 결과 화면.

## 실행

```bash
npm install
npm run dev      # 개발 서버 (http://localhost:5173)
npm run build    # 빌드 → dist/ (FastAPI /app/ 에서 서빙)
```

## 화면 구성

- **Screen 0**: 운동 선택 (스쿼트/런지/푸시업), 세트 수 설정
- **Screen 1**: 운동 중 HUD (타이머, 점수, 실시간 피드백)
- **Screen 2**: 결과 (점수, 등급, 피드백 목록)

## 백엔드 연결 상태

현재 `src/services/api.ts`는 mockApi 사용 중.  
실시간 연동 시 WebSocket (`ws://host:8000/ws/pose`) 으로 교체 필요.

## 빌드 결과물

`dist/` 폴더는 `.gitignore` 처리됨. 배포 전 `npm run build` 필수.
