# Server Deployment

## 로컬 실행 (개발)

```bash
# 환경 확인
python run_steps.py --check

# 서버 시작 (포트 8000)
python run_steps.py --server
```

접속:
- PC: `http://localhost:8000/viewer/`
- Quest 3 (같은 Wi-Fi): `http://<PC_IP>:8000/viewer/`

## 외부 배포 (Cloudflare Tunnel)

```bash
python run_steps.py --cloudflare
```

출력된 `https://xxxx.trycloudflare.com` URL로 Quest 3 접속.  
Unity: `wss://xxxx.trycloudflare.com/ws/pose`

## 의존성 설치

```bash
pip install -r requirements.txt
npm install && npm run build   # React 대시보드 빌드
```

## MySQL 설정

DB: `vr_user_db` (MySQL 9.5, 127.0.0.1:3306, root)  
테이블: `exercise_sessions` (서버 시작 시 자동 생성)
