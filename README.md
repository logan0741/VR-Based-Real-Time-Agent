# PSvR Design Frontend

이 프로젝트는 `formcheck.html`을 React + Vite + TypeScript 기반 프론트엔드 앱으로 구성한 것입니다.

## 실행

1. `npm install`
2. `npm run dev`
3. 브라우저에서 `http://localhost:5173` 열기

## 구조

- `src/App.tsx` — 화면 전환, 상태 관리, 백엔드 연동 포인트
- `src/components` — 재사용 가능한 UI 컴포넌트
- `src/services/mockApi.ts` — 더미 백엔드 데이터 공급
- `src/services/api.ts` — 실제 API로 교체할 인터페이스
- `src/hooks/useTimer.ts` — 타이머 로직
- `src/styles/global.css` — 디자인 시스템과 글로벌 스타일
- `src/types.ts` — 타입 정의

## 백엔드 연동 포인트

- `src/services/api.ts`에서 실제 API 호출을 추가하세요.
- `src/services/mockApi.ts`는 현재 더미 데이터를 반환합니다.
- 3D 렌더는 `src/components/RenderSlot.tsx` 컴포넌트를 통해 삽입할 수 있습니다.

## 협업

- UI는 컴포넌트 단위로 분리되어 있습니다.
- 각 컴포넌트는 독립적으로 개발/테스트 가능합니다.
- `README.md` (이 파일)에 협업 문서를 작성하세요.
