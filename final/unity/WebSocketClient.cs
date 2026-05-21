using System;
using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

[Serializable]
public class ServerResponse
{
    public string status;
    public string data_type;
    public string frame_id;
    public string session_id;
    public FitData fit;
    public FeedbackData feedback;
}

[Serializable]
public class FitData
{
    public string backend;
    public float[] global_orient;
    public float[] body_pose;
}

[Serializable]
public class FeedbackData
{
    public string label;
    public int score;
}

public class WebSocketClient : MonoBehaviour
{
    [Header("Connection Settings")]
    public string serverUrl = "ws://127.0.0.1:8000/ws/pose";
    public string userId = "anonymous";
    public string exerciseType = "squat";

    [Header("References")]
    public FitnessAvatarController userAvatar;
    public UIManager uiManager;

    [Header("Debug")]
    public bool logMessages = false;

    private ClientWebSocket ws;
    private CancellationTokenSource cts;
    private readonly ConcurrentQueue<Action> mainThreadActions = new ConcurrentQueue<Action>();
    private int receivedFrames = 0;

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
            Debug.Log($"[WS] Connecting to {serverUrl}...");
            await ws.ConnectAsync(new Uri(serverUrl), cts.Token);
            Debug.Log("[WS] Connected to server.");

            if (uiManager != null)
                mainThreadActions.Enqueue(() => uiManager.UpdateScore(0, "server connected"));

            _ = ReceiveLoop();
        }
        catch (Exception e)
        {
            Debug.LogError($"[WS] Connection failed: {e.Message}");
            if (uiManager != null)
                mainThreadActions.Enqueue(() => uiManager.UpdateScore(0, "server connection failed"));
        }
    }

    private async Task ReceiveLoop()
    {
        var buffer = new byte[65536];

        while (ws.State == WebSocketState.Open && !cts.IsCancellationRequested)
        {
            try
            {
                var messageBuilder = new StringBuilder();
                WebSocketReceiveResult result;

                do
                {
                    result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
                    messageBuilder.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                }
                while (!result.EndOfMessage);

                if (result.MessageType != WebSocketMessageType.Text)
                    continue;

                string jsonString = messageBuilder.ToString();
                if (logMessages && receivedFrames < 3)
                    Debug.Log($"[WS] Raw JSON: {jsonString.Substring(0, Math.Min(500, jsonString.Length))}");

                ServerResponse data = JsonUtility.FromJson<ServerResponse>(jsonString);
                if (data == null || data.status != "ok")
                    continue;

                if (data.fit == null)
                {
                    if (data.data_type == "session_end" && uiManager != null)
                        mainThreadActions.Enqueue(() => uiManager.UpdateScore(0, "session saved"));
                    continue;
                }

                receivedFrames++;
                mainThreadActions.Enqueue(() =>
                {
                    if (data.fit.global_orient != null && data.fit.body_pose != null && userAvatar != null)
                        userAvatar.UpdatePose(data.fit.global_orient, data.fit.body_pose);

                    if (uiManager != null)
                    {
                        string label = data.feedback != null ? data.feedback.label : "receiving";
                        int score = data.feedback != null ? data.feedback.score : receivedFrames;
                        uiManager.UpdateScore(score, label + $" (#{receivedFrames})");
                    }
                });
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[WS] Receive error: {e.Message}");
                break;
            }
        }

        Debug.Log("[WS] Receive loop ended.");
    }

    public async void StartExerciseSession()
    {
        await SendJsonAsync(
            "{\"data_type\":\"session_start\",\"user_id\":\"" + EscapeJson(userId) +
            "\",\"exercise_type\":\"" + EscapeJson(exerciseType) + "\"}"
        );
    }

    public async void EndExerciseSession()
    {
        await SendJsonAsync("{\"data_type\":\"session_end\"}");
    }

    public async void SendKeypoints(float[][] keypoints17x3, string frameId = null)
    {
        if (keypoints17x3 == null) return;

        StringBuilder sb = new StringBuilder();
        sb.Append("{\"data_type\":\"keypoints\"");
        if (frameId != null)
            sb.Append(",\"frame_id\":\"").Append(EscapeJson(frameId)).Append("\"");
        sb.Append(",\"payload\":[");
        for (int i = 0; i < keypoints17x3.Length; i++)
        {
            if (i > 0) sb.Append(",");
            sb.Append("[").Append(keypoints17x3[i][0])
              .Append(",").Append(keypoints17x3[i][1])
              .Append(",").Append(keypoints17x3[i][2]).Append("]");
        }
        sb.Append("]}");

        await SendJsonAsync(sb.ToString());
    }

    private async Task SendJsonAsync(string json)
    {
        if (ws == null || ws.State != WebSocketState.Open) return;

        byte[] msg = Encoding.UTF8.GetBytes(json);
        await ws.SendAsync(new ArraySegment<byte>(msg), WebSocketMessageType.Text, true, cts.Token);
    }

    private static string EscapeJson(string value)
    {
        return (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
    }

    void Update()
    {
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
            try { ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Client closing", CancellationToken.None); }
            catch { /* ignore */ }
        }
    }
}
