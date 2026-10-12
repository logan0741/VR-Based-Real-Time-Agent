# Playwright 캡처 스크립트 (2026-06-08)
서버가 `:8000` 에 떠 있고 앱이 `/app/` 로 보여야 한다 — `final_check.mjs` 는 `http://localhost:8000/app/`, 나머지는 Vite dev(`http://localhost:5173/`, `/api`·`/ws` 를 :8000 으로 프록시)를 연다. 모두 "비교" 버튼을 눌러 [방식 비교 화면](../../../docs/20_Three.js_SMPLX/02_렌더링_방식_3종.md)을 찍는다.
실행: `cd app_3d_web && npx playwright install chromium && node tools/playwright/final_check.mjs` — 저장 경로가 옛 작업 폴더 절대경로(`C:/Project/VR-Based-Real-Time-Agent/…`, `%TEMP%`)로 박혀 있으니 필요하면 고쳐 쓴다. 결과물은 [`docs/30_스크린샷/`](../../../docs/30_스크린샷/README.md).
