# Unity Integration

SMPL-X 아바타를 서버 WebSocket 데이터로 실시간 구동.

## 스크립트 위치

`unity_integration/` 폴더의 파일을 Unity 프로젝트 `Assets/Scripts/`에 복사.

- `FitnessAvatarController.cs` — SMPL-X 아바타 bone 회전 적용
- `WebSocketClient.cs` — 서버 연결 및 JSON 역직렬화

## 서버 연결

Unity Inspector에서 `WebSocketClient` 컴포넌트:
- `serverUrl`: `ws://<PC_IP>:8000/ws/pose` 또는 Cloudflare URL의 `wss://`
- `userId`: 사용자 ID
- `exerciseType`: 운동 종류 (squat 등)

## Axis-Angle → Unity Quaternion 변환 (공식 SMPLX.cs 기준)

```csharp
Vector3 axis = new Vector3(-axisAngle.x, axisAngle.y, axisAngle.z); // X축 반전
float angleDeg = -axis.magnitude * Mathf.Rad2Deg;                   // 각도 부호 반전
axis.Normalize();
return Quaternion.AngleAxis(angleDeg, axis);
```

## SMPL-X body_pose 관절 순서 (인덱스 0~20)

```
0:left_hip, 1:right_hip, 2:spine1, 3:left_knee, 4:right_knee,
5:spine2, 6:left_ankle, 7:right_ankle, 8:spine3, 9:left_foot,
10:right_foot, 11:neck, 12:left_collar, 13:right_collar, 14:head,
15:left_shoulder, 16:right_shoulder, 17:left_elbow, 18:right_elbow,
19:left_wrist, 20:right_wrist
```
