# Final — 실행 가이드

## 파이프라인 선택

| 파일 | 용도 | Unity 필요 |
|------|------|-----------|
| `pipeline_web_only.py` | 웹 브라우저(Quest 3)만으로 동작 | ❌ |
| `pipeline_full.py` | Unity + 웹 뷰어 전체 시스템 | ✅ |
| `pipeline_test.py` | 전체 컴포넌트 검증 | ❌ |

## 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt
npm install && npm run build

# 2. 웹 전용 실행 (Quest 3 브라우저)
python final/pipeline_web_only.py

# 3. 전체 실행 (Unity 포함)
python final/pipeline_full.py

# 4. 시스템 검증
python final/pipeline_test.py
```

## 폴더 구조

```
final/
├── pipeline_web_only.py   # Unity 없이 웹으로만 동작
├── pipeline_full.py       # 전체 파이프라인 (Unity 포함)
├── pipeline_test.py       # 컴포넌트 검증
├── backend/README.md      # 백엔드 아키텍처 및 API 문서
├── frontend/README.md     # React 앱 빌드 및 구조
├── unity/README.md        # Unity 연동 가이드 및 좌표 변환
├── server/README.md       # 서버 배포 방법
└── assets/README.md       # 모델 파일 및 데이터 안내
```
