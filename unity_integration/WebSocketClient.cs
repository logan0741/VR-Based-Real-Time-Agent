using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

// JSON 데이터 구조체 정의 (파이썬 서버에서 보내는 규격)
[Serializable]
public class PoseData
{
    public FitData fit;
    public FeedbackData feedback;
}

[Serializable]
public class FitData
{
    public float[] global_orient;
    public float[] body_pose;
}

[Serializable]
public class FeedbackData
{
    public int score;
    public string label;
    // 근육 피로도는 Dictionary(C#) 처리가 필요하므로, 여기서는 기본 파싱 가능한 항목만 둡니다.
}

public class WebSocketClient : MonoBehaviour
{
    [Header("Connection Settings")]
    public string serverUrl = "ws://127.0.0.1:8000/ws/pose";
    
    [Header("References")]
    public AvatarController userAvatar;
    public UIManager uiManager;

    private ClientWebSocket ws;
    private CancellationTokenSource cts;
    
    // 메인 쓰레드에서 실행할 동작들을 담는 큐 (Unity API는 메인 쓰레드에서만 호출 가능)
    private ConcurrentQueue<Action> mainThreadActions = new ConcurrentQueue<Action>();

    async void Start()
    {
        await ConnectToServer();
    }

    private async Task ConnectToServer()
    {
        ws = new ClientWebSocket();
        cts = new CancellationTokenSource();

        try
        {
            Debug.Log($"Connecting to {serverUrl}...");
            await ws.ConnectAsync(new Uri(serverUrl), cts.Token);
            Debug.Log("Connected to Server!");

            // 백그라운드 수신 루프 시작
            _ = ReceiveLoop();
        }
        catch (Exception e)
        {
            Debug.LogError($"Connection failed: {e.Message}");
        }
    }

    private async Task ReceiveLoop()
    {
        var buffer = new byte[8192];

        while (ws.State == WebSocketState.Open && !cts.IsCancellationRequested)
        {
            try
            {
                WebSocketReceiveResult result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
                
                if (result.MessageType == WebSocketMessageType.Text)
                {
                    string jsonString = Encoding.UTF8.GetString(buffer, 0, result.Count);
                    
                    // JSON 파싱 후 메인 쓰레드 큐에 등록
                    PoseData data = JsonUtility.FromJson<PoseData>(jsonString);
                    
                    mainThreadActions.Enqueue(() => {
                        ProcessPoseData(data);
                    });
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"Receive error: {e.Message}");
                break;
            }
        }
    }

    private void ProcessPoseData(PoseData data)
    {
        if (data == null) return;

        // 1. 아바타 리타겟팅
        if (data.fit != null && userAvatar != null)
        {
            userAvatar.UpdatePose(data.fit.global_orient, data.fit.body_pose);
        }

        // 2. UI 업데이트
        if (data.feedback != null && uiManager != null)
        {
            uiManager.UpdateScore(data.feedback.score, data.feedback.label);
        }
    }

    void Update()
    {
        // 백그라운드 쓰레드에서 큐에 넣은 작업들을 메인 쓰레드에서 실행
        while (mainThreadActions.TryDequeue(out Action action))
        {
            action?.Invoke();
        }
    }

    private void OnDestroy()
    {
        cts?.Cancel();
        if (ws != null && ws.State == WebSocketState.Open)
        {
            ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Client closing", CancellationToken.None);
        }
    }
}
