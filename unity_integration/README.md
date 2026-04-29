# 🚀 Unity 초보자를 위한 3D 아바타 연동 가이드 (Step-by-Step)

이 가이드는 Unity를 **처음 켜보는 분**들도 차근차근 따라 하실 수 있도록 작성되었습니다. 
천천히 순서대로 진행해 주세요!

---

## 1단계: Unity Hub 켜기 및 프로젝트 준비

1. **Unity Hub**를 실행합니다.
2. 기존에 다운로드해 둔 `SMPLX-Unity` 파일이 포함된 프로젝트가 있다면 **해당 프로젝트를 클릭해서 엽니다.**
   * _(만약 그런 프로젝트가 어딘지 모르겠거나 없다면)_ 우측 상단의 **[New Project (새 프로젝트)]** 버튼을 누르고, **3D (Core)** 템플릿을 선택한 뒤 적당한 이름(예: `FitnessVR`)을 지어서 새로 만듭니다.

## 2단계: 스크립트 복사하기

파이썬 서버와 통신하게 해줄 3개의 C# 파일을 Unity 안으로 가져와야 합니다.

1. Unity 화면 맨 아래에 있는 **Project(프로젝트)** 창을 봅니다.
2. `Assets` 폴더 빈 공간에 마우스 우클릭 -> **Create(만들기)** -> **Folder(폴더)**를 누릅니다.
3. 새 폴더 이름을 `Scripts`라고 짓습니다.
4. 방금 만든 `Scripts` 폴더를 더블 클릭해서 들어갑니다.
5. 바탕화면의 파일 탐색기를 열고, 우리가 작업한 `c:\Project\VR-Based-Real-Time-Agent\unity_integration\` 폴더 안으로 들어갑니다.
6. 그 안에 있는 `AvatarController.cs`, `UIManager.cs`, `WebSocketClient.cs` 세 파일을 드래그해서 Unity의 `Scripts` 폴더 안으로 쏙(Drop) 집어넣습니다.

## 3단계: 화면(씬)에 요소들 배치하기

1. **매니저 만들기:**
   - Unity 화면 왼쪽의 **Hierarchy(계층 구조)** 창 빈 공간에 우클릭 -> **Create Empty (빈 게임오브젝트 만들기)**를 누릅니다.
   - 방금 생긴 투명한 객체의 이름을 `NetworkManager`로 바꿉니다.
   - `Scripts` 폴더에 있는 `WebSocketClient`와 `UIManager`를 드래그해서 `NetworkManager` 위에 덮어씌우듯 떨어뜨립니다. (이렇게 하면 스크립트가 부착됩니다!)

2. **아바타 올리기:**
   - 만약 기존 `SMPLX` 프로젝트를 여셨다면, `Assets` 어딘가에 있는 SMPL-X 프리팹(파란색 정육면체 아이콘의 3D 모델)을 드래그해서 **Hierarchy** 창에 올려놓습니다.
   - (만약 새로 만든 프로젝트라서 아바타가 없다면, 일단 Hierarchy 빈 공간 우클릭 -> 3D Object -> Capsule을 하나 만들어서 연습용으로 쓰셔도 됩니다.)
   - 방금 올린 아바타(또는 Capsule)를 선택하고, `Scripts` 폴더에 있는 `AvatarController`를 드래그해서 부착합니다.

3. **글씨(UI) 만들기:**
   - Hierarchy 창 빈 공간 우클릭 -> **UI** -> **Text (또는 Text - TextMeshPro)**를 클릭합니다. (Canvas라는 도화지 위에 글씨가 생깁니다.)
   - 이 글씨 객체의 이름을 `ScoreText`로 바꿉니다.
   - 같은 방법으로 하나 더 만들어서 이름을 `FeedbackText`로 바꿉니다.

## 4단계: 선 연결해주기 (Inspector 세팅)

스크립트들이 서로, 그리고 아바타의 뼈와 연결될 수 있도록 지정해 주는 단계입니다.

1. **UIManager 세팅:**
   - Hierarchy에서 `NetworkManager`를 클릭합니다.
   - 오른쪽 **Inspector(인스펙터)** 창을 보면 UIManager 컴포넌트가 보입니다.
   - `Score Text` 칸에 방금 만든 `ScoreText`를 드래그해서 넣습니다.
   - `Feedback Label Text` 칸에 방금 만든 `FeedbackText`를 드래그해서 넣습니다.

2. **WebSocketClient 세팅:**
   - 마찬가지로 `NetworkManager`의 인스펙터를 봅니다.
   - `User Avatar` 칸에 Hierarchy에 있는 내 3D 아바타를 드래그해서 넣습니다.
   - `Ui Manager` 칸에 Hierarchy에 있는 `NetworkManager` 자신을 드래그해서 넣습니다.

3. **AvatarController 세팅 (제일 중요 ⭐️):**
   - Hierarchy에서 **내 3D 아바타**를 클릭합니다.
   - 인스펙터의 Avatar Controller 부분을 봅니다.
   - **Root Bone** 칸에 아바타의 골반 뼈(주로 Pelvis 또는 Hips라고 적힌 자식 오브젝트)를 드래그해서 넣습니다.
   - **Smpl Bones** 라는 글씨 옆의 화살표(▶)를 누르면 펼쳐집니다. **Size(크기)를 21**로 적고 엔터를 칩니다.
   - 0번부터 20번까지 빈칸이 생깁니다. 아바타의 뼈대(계층 구조에서 ▶를 눌러서 계속 파고들어야 보입니다)를 아래 순서에 맞게 하나하나 드래그해서 넣어주세요.

**[뼈대(Bone) 넣는 순서]**
* Element 0: Pelvis (골반)
* Element 1: L_Hip (왼쪽 엉덩이 관절)
* Element 2: R_Hip (오른쪽 엉덩이 관절)
* Element 3: Spine1 (척추 1번 - 허리 쪽)
* Element 4: L_Knee (왼쪽 무릎)
* Element 5: R_Knee (오른쪽 무릎)
* Element 6: Spine2 (척추 2번 - 가슴 쪽)
* Element 7: L_Ankle (왼쪽 발목)
* Element 8: R_Ankle (오른쪽 발목)
* Element 9: Spine3 (척추 3번 - 위쪽 가슴)
* Element 10: L_Foot (왼쪽 발끝/발볼)
* Element 11: R_Foot (오른쪽 발끝/발볼)
* Element 12: Neck (목)
* Element 13: L_Collar (왼쪽 쇄골)
* Element 14: R_Collar (오른쪽 쇄골)
* Element 15: Head (머리)
* Element 16: L_Shoulder (왼쪽 어깨 관절)
* Element 17: R_Shoulder (오른쪽 어깨 관절)
* Element 18: L_Elbow (왼쪽 팔꿈치)
* Element 19: R_Elbow (오른쪽 팔꿈치)
* Element 20: L_Wrist (왼쪽 손목)
* Element 21: R_Wrist (오른쪽 손목) *(주의: Size를 22로 늘려서 넣으셔도 됩니다)*

## 5단계: 드디어 실행!

모든 연결이 끝났습니다.

1. PC의 파이썬 터미널 창을 열고, 기존에 하시던 것처럼 서버를 켭니다.
   `python run_steps.py --server`
2. 파이썬 터미널 창을 하나 더 열고, 더미 스쿼트 데이터를 쏩니다.
   `python play_squat.py --loops 100`
3. **Unity로 돌아와서 화면 맨 위에 있는 재생(▶) 버튼을 누릅니다!**
4. 3D 아바타가 스쿼트를 시작하고, 화면에 점수와 피드백 글씨가 바뀌는지 확인하세요!
