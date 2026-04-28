/*
 * KKLL - PoseReceiver.cs
 * 역할: Python WebSocket → keypoint 수신 → 스켈레톤 렌더링 → latency 측정
 *
 * 사용법:
 *   1. 빈 GameObject "PoseManager" 생성 → 이 스크립트 추가
 *   2. Inspector → serverUrl 에 맥 IP 입력 (ws://맥IP:8765)
 *   3. Python 서버 먼저 실행 → Unity Play
 *   4. 화면 좌상단 HUD에서 latency 실시간 확인
 */

using System;
using System.Collections.Generic;
using UnityEngine;
using NativeWebSocket;

[Serializable]
public class KeypointData
{
    public string name;
    public float x, y;
    public float x_norm, y_norm;
    public float confidence;
}

[Serializable]
public class LatencyData
{
    public float capture_ms;
    public float infer_ms;
    public float send_ms;
    public float total_ms;
}

[Serializable]
public class PosePayload
{
    public long timestamp_ms;
    public LatencyData latency;
    public KeypointData[] keypoints;
}

public class PoseReceiver : MonoBehaviour
{
    [Header("Connection")]
    public string serverUrl = "ws://192.168.0.x:8765";

    [Header("Skeleton")]
    public float confidenceThreshold = 0.3f;
    public float skeletonScale = 3.0f;
    public Vector3 skeletonOrigin = new Vector3(0f, 1f, 2f);
    public Color skeletonColor = new Color(0f, 0.9f, 0.63f);
    public Color lowConfColor  = new Color(0.4f, 0.4f, 0.4f);

    [Header("HUD")]
    public bool showHUD = true;

    private WebSocket _ws;
    private PosePayload _latestPose;
    private readonly object _lock = new object();

    private Dictionary<string, GameObject>    _joints = new Dictionary<string, GameObject>();
    private Dictionary<string, LineRenderer>  _bones  = new Dictionary<string, LineRenderer>();

    private float _guiCapture, _guiInfer, _guiSend, _guiPythonTotal, _guiUnityRender, _guiE2E;
    private float _fps;
    private int   _frameCount;
    private float _fpsTimer;

    private static readonly string[] KP_NAMES = {
        "nose","left_eye","right_eye","left_ear","right_ear",
        "left_shoulder","right_shoulder","left_elbow","right_elbow",
        "left_wrist","right_wrist","left_hip","right_hip",
        "left_knee","right_knee","left_ankle","right_ankle"
    };

    private static readonly int[,] BONE_PAIRS = {
        {0,1},{0,2},{1,3},{2,4},
        {5,6},
        {5,7},{7,9},
        {6,8},{8,10},
        {5,11},{6,12},{11,12},
        {11,13},{13,15},
        {12,14},{14,16}
    };

    async void Start()
    {
        BuildSkeleton();

        _ws = new WebSocket(serverUrl);
        _ws.OnOpen    += () => Debug.Log($"[WS] 연결됨: {serverUrl}");
        _ws.OnError   += (e) => Debug.LogWarning($"[WS] 에러: {e}");
        _ws.OnClose   += (e) => Debug.Log("[WS] 연결 종료");
        _ws.OnMessage += OnMessage;
        await _ws.Connect();
    }

    void Update()
    {
#if !UNITY_WEBGL || UNITY_EDITOR
        _ws?.DispatchMessageQueue();
#endif
        _frameCount++;
        if (Time.time - _fpsTimer >= 1f)
        {
            _fps = _frameCount / (Time.time - _fpsTimer);
            _frameCount = 0;
            _fpsTimer = Time.time;
        }

        PosePayload pose;
        lock (_lock) { pose = _latestPose; }
        if (pose == null) return;

        float t0 = Time.realtimeSinceStartup;
        UpdateSkeleton(pose);
        _guiUnityRender = (Time.realtimeSinceStartup - t0) * 1000f;
        _guiE2E = _guiPythonTotal + _guiUnityRender;
    }

    void OnMessage(byte[] bytes)
    {
        string json = System.Text.Encoding.UTF8.GetString(bytes);
        try
        {
            var p = JsonUtility.FromJson<PosePayload>(json);
            if (p == null) return;
            lock (_lock) { _latestPose = p; }
            if (p.latency != null)
            {
                _guiCapture     = p.latency.capture_ms;
                _guiInfer       = p.latency.infer_ms;
                _guiSend        = p.latency.send_ms;
                _guiPythonTotal = p.latency.total_ms;
            }
        }
        catch (Exception e) { Debug.LogWarning($"[JSON] {e.Message}"); }
    }

    void BuildSkeleton()
    {
        foreach (var name in KP_NAMES)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            go.name = $"joint_{name}";
            go.transform.SetParent(transform);
            go.transform.localScale = Vector3.one * 0.06f;
            go.GetComponent<Renderer>().material.color = skeletonColor;
            Destroy(go.GetComponent<Collider>());
            go.SetActive(false);
            _joints[name] = go;
        }

        int n = BONE_PAIRS.GetLength(0);
        for (int i = 0; i < n; i++)
        {
            var go = new GameObject($"bone_{i}");
            go.transform.SetParent(transform);
            var lr = go.AddComponent<LineRenderer>();
            lr.startWidth = lr.endWidth = 0.025f;
            lr.material = new Material(Shader.Find("Sprites/Default"));
            lr.startColor = lr.endColor = skeletonColor;
            lr.positionCount = 2;
            lr.enabled = false;
            _bones[$"bone_{i}"] = lr;
        }
    }

    void UpdateSkeleton(PosePayload pose)
    {
        if (pose.keypoints == null) return;

        var pos   = new Vector3[17];
        var confs = new float[17];

        for (int i = 0; i < pose.keypoints.Length && i < 17; i++)
        {
            var kp = pose.keypoints[i];
            confs[i] = kp.confidence;
            float wx = (kp.x_norm - 0.5f) * -skeletonScale;
            float wy = (1f - kp.y_norm - 0.5f) * skeletonScale;
            pos[i] = skeletonOrigin + new Vector3(wx, wy, 0f);

            var joint = _joints[KP_NAMES[i]];
            bool vis = kp.confidence >= confidenceThreshold;
            joint.SetActive(vis);
            if (vis)
            {
                joint.transform.position = pos[i];
                joint.GetComponent<Renderer>().material.color =
                    kp.confidence > 0.6f ? skeletonColor : lowConfColor;
            }
        }

        int n = BONE_PAIRS.GetLength(0);
        for (int i = 0; i < n; i++)
        {
            int a = BONE_PAIRS[i, 0], b = BONE_PAIRS[i, 1];
            var lr = _bones[$"bone_{i}"];
            bool vis = confs[a] >= confidenceThreshold && confs[b] >= confidenceThreshold;
            lr.enabled = vis;
            if (vis)
            {
                lr.SetPosition(0, pos[a]);
                lr.SetPosition(1, pos[b]);
                float avg = (confs[a] + confs[b]) * 0.5f;
                lr.startColor = lr.endColor = avg > 0.6f ? skeletonColor : lowConfColor;
            }
        }
    }

    void OnGUI()
    {
        if (!showHUD) return;
        var s = new GUIStyle(GUI.skin.box) { fontSize = 15, alignment = TextAnchor.UpperLeft };
        s.normal.textColor = new Color(0f, 0.9f, 0.63f);
        GUI.Box(new Rect(10, 10, 265, 195),
            $"[KKLL Latency]\n" +
            $"  Unity FPS     : {_fps:F1}\n" +
            $"  capture       : {_guiCapture:F1} ms\n" +
            $"  MoveNet infer : {_guiInfer:F1} ms\n" +
            $"  WS send       : {_guiSend:F1} ms\n" +
            $"  Python E2E    : {_guiPythonTotal:F1} ms\n" +
            $"  Unity render  : {_guiUnityRender:F2} ms\n" +
            $"  ──────────────────\n" +
            $"  Total E2E     : {_guiE2E:F1} ms", s);
    }

    async void OnApplicationQuit()
    {
        if (_ws != null && _ws.State == WebSocketState.Open)
            await _ws.Close();
    }
}
