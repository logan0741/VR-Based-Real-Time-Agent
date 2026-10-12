# 스크린샷 (2026-06-08, PSVR 3D 웹앱)

전부 [`app_3d_web/`](../../app_3d_web/) 를 브라우저(대부분 Playwright, [`tools/playwright/`](../../app_3d_web/tools/playwright/))로 캡처한 것이다. 원래 파일명은 오른쪽 열에 남겼다. 렌더링 방식 설명은 [`../20_Three.js_SMPLX/02_렌더링_방식_3종.md`](../20_Three.js_SMPLX/02_렌더링_방식_3종.md).

## 운동 화면 (강사 vs 내 자세, SMPL-X 메시)

| 파일 | 보이는 것 | 원래 이름 |
|---|---|---|
| [`web3d_expert_vs_user_smplx_20260608.png`](web3d_expert_vs_user_smplx_20260608.png) | 좌 "강사 모델"(보라) · 우 "내 자세"(초록) SMPL-X 메시 나란히. 두 체 모두 상체를 숙이고 팔을 벌린 비정상 자세, 하단 "측정 중입니다." 배지와 "운동 종료" 버튼 | `스크린 사진.png` |
| [`web3d_expert_vs_user_with_hud_20260608.png`](web3d_expert_vs_user_with_hud_20260608.png) | 같은 화면에 상단 HUD(TIME 00:12 · SET 1/3 · REPS 0 · SCORE 0/100). 강사는 한 팔을 앞으로 뻗은 선 자세, 내 자세는 몸통이 부풀고 뒤로 젖혀진 깨진 자세 | `스크린 2.png` |
| [`web3d_expert_model_only_20260608.png`](web3d_expert_model_only_20260608.png) | HUD(TIME 00:06 · SET 1/3 · REPS 0) + 강사 모델 단독. 공중에 앉은 듯한 자세, 한 팔이 머리 뒤로 꺾임 | `스크린 4.png` |

## 랜딩

| 파일 | 보이는 것 | 원래 이름 |
|---|---|---|
| [`web3d_landing_psvr_20260608.png`](web3d_landing_psvr_20260608.png) | "VR PERSONAL TRAINER / PSVR" 랜딩. 운동 카드 SQ 스쿼트 · LG 런지 · PU 푸시업, 세트 수 3(−/+), "운동 시작", "방식 비교" 버튼 | `screenshot_landing.png` |
| [`web3d_render_methods_screenshot_compare_v2fixed_20260608.png`](web3d_render_methods_screenshot_compare_v2fixed_20260608.png) | **랜딩과 바이트 단위로 동일**(md5 `1932e9a8…`). 이름과 달리 비교 화면이 아니라 랜딩이 찍혔다 | `screenshot_compare_v2fixed.png` |

## 렌더링 방식 비교 (V1 SMPL-X MLP · V2 3D Geometric IK · V3 3D Wireframe, 3분할)

| 파일 | 보이는 것 | 원래 이름 |
|---|---|---|
| [`web3d_render_methods_v2check_0s_20260608.png`](web3d_render_methods_v2check_0s_20260608.png) | V1 보라: 뒤로 젖혀진 몸·고개. V2 초록: 똑바로 서서 오른팔만 아래로. V3 주황: 선 자세 관절 | `v2_check_0s.png` |
| [`web3d_render_methods_v2check_3s_20260608.png`](web3d_render_methods_v2check_3s_20260608.png) | 3초 뒤. V1 여전히 젖혀짐, V2 거의 동일, V3 무릎이 약간 굽음 | `v2_check_3s.png` |
| [`web3d_render_methods_v2check_7s_20260608.png`](web3d_render_methods_v2check_7s_20260608.png) | 7초. V1 팔 벌리고 젖혀짐, V2 무릎 살짝 굽음, V3 스쿼트 내려가는 중(무릎 굽힘 뚜렷) | `v2_check_7s.png` |
| [`web3d_render_methods_v2check_11s_20260608.png`](web3d_render_methods_v2check_11s_20260608.png) | 11초. V2 가 무릎을 굽힌 반쪼그림 자세 — V2 가 하체를 따라간 유일한 캡처. V3 도 굽힘 | `v2_check_11s.png` |
| [`web3d_render_methods_osctest_6s_20260608.png`](web3d_render_methods_osctest_6s_20260608.png) | V1 상체 숙이고 팔 벌림(한쪽 팔 뼈가 등 뒤로 튐), V2 **T-pose 정지** + 머리 위 빨간 디버그 상자, V3 정면 선 자세(바닥 그리드) | `screenshot_osctest_6s.png` |
| [`web3d_render_methods_screenshot_compare_after_click_20260608.png`](web3d_render_methods_screenshot_compare_after_click_20260608.png) | "방식 비교" 클릭 직후. V1 숙인 자세, V2 T-pose, V3 정면 선 자세 | `screenshot_compare_after_click.png` |
| [`web3d_render_methods_screenshot_frame160_20260608.png`](web3d_render_methods_screenshot_frame160_20260608.png) | 같은 구도(프레임 160 부근). V2 T-pose 그대로 | `screenshot_frame160.png` |
| [`web3d_render_methods_screenshot_debug_20260608.png`](web3d_render_methods_screenshot_debug_20260608.png) | 디버그 실행 캡처. 구성 동일, V2 T-pose | `screenshot_debug.png` |
| [`web3d_render_methods_screenshot_v2_skelutils_20260608.png`](web3d_render_methods_screenshot_v2_skelutils_20260608.png) | 파일명상 V2 의 `SkeletonUtils` 복제 변형을 시험한 캡처(그 변형 코드는 남아 있지 않다). 클릭 후 8초(스크립트 주석상 ≈64프레임). V2 여전히 T-pose | `screenshot_v2_skelutils.png` |
| [`web3d_render_methods_screenshot_v2_skelutils_deep_20260608.png`](web3d_render_methods_screenshot_v2_skelutils_deep_20260608.png) | 같은 실행의 24초 시점(주석상 ≈224프레임, 깊은 스쿼트를 노림). V2 변화 없음 | `screenshot_v2_skelutils_deep.png` |

여기 없는 것: `스크린 3.png`, `viewer_live_check_*.png` 는 2D 뷰어 캡처라 [`Pose3D`](../../../../tree/Pose3D) 브랜치 쪽에 둔다(원본은 [`docs-archive`](../../../../tree/docs-archive)).
