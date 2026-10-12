// ----------------------------------------------------------------------------
// AvatarController.cs
//
// Real-time SMPL-X avatar control via WebSocket.
// Receives body_pose (63 axis-angle floats) + global_orient (3 floats) from
// the FastAPI server and applies them directly to the SMPL-X Unity model
// using the official SMPLX.cs QuatFromRodrigues() and SetLocalJointRotation().
//
// Setup:
//   1. Import SMPLX_UnityProject_20241205.zip into your Unity project
//   2. Place an SMPL-X prefab (e.g. smplx-neutral) in the Scene
//   3. Attach this script to the SAME GameObject that has the SMPLX component
//   4. Set serverUrl in the Inspector
//   5. Run server.py → Unity Play
//
// Requirements: Unity 2021.3+, SMPLX Unity package (SMPLX.cs, FBX, etc.)
// ----------------------------------------------------------------------------

using System;
using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

[RequireComponent(typeof(SMPLX))]
public class AvatarController : MonoBehaviour
{
    // ========================================================================
    // Inspector Settings
    // ========================================================================

    [Header("WebSocket Connection")]
    [Tooltip("FastAPI server WebSocket URL")]
    public string serverUrl = "ws://127.0.0.1:8000/ws/pose";

    [Tooltip("User id saved with completed exercise sessions")]
    public string userId = "anonymous";

    [Tooltip("Exercise type saved with completed exercise sessions")]
    public string exerciseType = "squat";

    [Tooltip("Automatically reconnect on disconnect")]
    public bool autoReconnect = true;

    [Tooltip("Seconds between reconnect attempts")]
    public float reconnectInterval = 2.0f;

    [Header("Smoothing")]
    [Tooltip("Interpolation speed for joint rotations (higher = faster response)")]
    [Range(1f, 60f)]
    public float smoothingSpeed = 15.0f;

    [Tooltip("Interpolation speed for root position")]
    [Range(1f, 60f)]
    public float rootSmoothingSpeed = 10.0f;

    [Header("Options")]
    [Tooltip("Apply root (pelvis) translation from server data")]
    public bool applyRootPosition = true;

    [Tooltip("Snap feet to ground plane after pose update")]
    public bool snapToGround = true;

    [Tooltip("Hand pose to use (Flat or Relaxed)")]
    public SMPLX.HandPose handPose = SMPLX.HandPose.Relaxed;

    [Header("Debug")]
    public bool logFrames = false;

    // ========================================================================
    // SMPL-X Body Joint Names (21 joints, matches body_pose order)
    // pelvis (index 0) is driven by global_orient, not body_pose
    // ========================================================================

    private static readonly string[] BodyJointNames = new string[]
    {
        "left_hip",          // body_pose[0:3]
        "right_hip",         // body_pose[3:6]
        "spine1",            // body_pose[6:9]
        "left_knee",         // body_pose[9:12]
        "right_knee",        // body_pose[12:15]
        "spine2",            // body_pose[15:18]
        "left_ankle",        // body_pose[18:21]
        "right_ankle",       // body_pose[21:24]
        "spine3",            // body_pose[24:27]
        "left_foot",         // body_pose[27:30]
        "right_foot",        // body_pose[30:33]
        "neck",              // body_pose[33:36]
        "left_collar",       // body_pose[36:39]
        "right_collar",      // body_pose[39:42]
        "head",              // body_pose[42:45]
        "left_shoulder",     // body_pose[45:48]
        "right_shoulder",    // body_pose[48:51]
        "left_elbow",        // body_pose[51:54]
        "right_elbow",       // body_pose[54:57]
        "left_wrist",        // body_pose[57:60]
        "right_wrist",       // body_pose[60:63]
    };

    // ========================================================================
    // Private State
    // ========================================================================

    private SMPLX _smplx;
    private ClientWebSocket _webSocket;
    private CancellationTokenSource _cancellation;
    private readonly ConcurrentQueue<PoseFrame> _frameQueue = new ConcurrentQueue<PoseFrame>();

    // Current and target rotations for smooth interpolation
    private Quaternion[] _currentRotations;    // [0]=pelvis, [1..21]=body joints
    private Quaternion[] _targetRotations;     // same layout
    private Vector3 _targetRootPosition;
    private bool _hasReceivedPose = false;

    // Connection state
    private bool _isConnected;
    private float _reconnectTimer;

    // ========================================================================
    // Data Structures
    // ========================================================================

    private struct PoseFrame
    {
        public float[] GlobalOrient;  // 3 floats (axis-angle for pelvis)
        public float[] BodyPose;      // 63 floats (21 joints × 3 axis-angle)
        public float[] Betas;         // 10 floats (optional shape params)
        public string FeedbackLabel;
        public float KneeAngle;
    }

    // JSON classes matching server.py response (fit_result_to_json)
    [Serializable] private class ServerResponse
    {
        public string status;
        public FitPayload fit;
        public FeedbackPayload feedback;
    }

    [Serializable] private class FitPayload
    {
        public string backend;
        public float[] global_orient;   // 3 floats
        public float[] body_pose;       // 63 floats
        public float[][] joints_3d;     // 17×3 (unused here, SMPLX handles it)
    }

    [Serializable] private class FeedbackPayload
    {
        public string label;
        public float knee_angle_deg;
    }

    // ========================================================================
    // Unity Lifecycle
    // ========================================================================

    private void Start()
    {
        _smplx = GetComponent<SMPLX>();
        if (_smplx == null)
        {
            Debug.LogError("[AvatarController] SMPLX component not found on this GameObject.");
            enabled = false;
            return;
        }

        // Initialize rotation arrays: index 0 = pelvis, indices 1-21 = body joints
        int totalJoints = 1 + BodyJointNames.Length; // 22
        _currentRotations = new Quaternion[totalJoints];
        _targetRotations = new Quaternion[totalJoints];
        for (int i = 0; i < totalJoints; i++)
        {
            _currentRotations[i] = Quaternion.identity;
            _targetRotations[i] = Quaternion.identity;
        }

        _targetRootPosition = transform.position;

        // Apply initial hand pose
        _smplx.SetHandPose(handPose);

        Connect();
    }

    private void Update()
    {
        // Drain queue: keep only the latest frame
        PoseFrame latest = default;
        bool hasFrame = false;
        while (_frameQueue.TryDequeue(out PoseFrame frame))
        {
            latest = frame;
            hasFrame = true;
        }

        if (hasFrame)
        {
            ProcessPoseFrame(latest);
        }

        // Auto-reconnect
        if (autoReconnect && !_isConnected)
        {
            _reconnectTimer -= Time.deltaTime;
            if (_reconnectTimer <= 0f)
            {
                _reconnectTimer = reconnectInterval;
                Connect();
            }
        }
    }

    private void LateUpdate()
    {
        if (!_hasReceivedPose) return;

        float t = 1f - Mathf.Exp(-smoothingSpeed * Time.deltaTime);
        float rootT = 1f - Mathf.Exp(-rootSmoothingSpeed * Time.deltaTime);

        // --- Pelvis (global_orient) ---
        _currentRotations[0] = Quaternion.Slerp(_currentRotations[0], _targetRotations[0], t);
        _smplx.SetLocalJointRotation("pelvis", _currentRotations[0]);

        // --- 21 Body Joints ---
        for (int i = 0; i < BodyJointNames.Length; i++)
        {
            int idx = i + 1;
            _currentRotations[idx] = Quaternion.Slerp(_currentRotations[idx], _targetRotations[idx], t);
            _smplx.SetLocalJointRotation(BodyJointNames[i], _currentRotations[idx]);
        }

        // --- Pose Correctives (skin deformation quality) ---
        _smplx.UpdatePoseCorrectives();

        // --- Root Position ---
        if (applyRootPosition)
        {
            transform.position = Vector3.Lerp(transform.position, _targetRootPosition, rootT);
        }

        // --- Ground snap ---
        if (snapToGround)
        {
            _smplx.SnapToGroundPlane();
        }
    }

    private void OnDestroy()
    {
        Disconnect();
    }

    // ========================================================================
    // Pose Processing
    // ========================================================================

    private void ProcessPoseFrame(PoseFrame frame)
    {
        _hasReceivedPose = true;

        // --- Global orient → pelvis rotation ---
        if (frame.GlobalOrient != null && frame.GlobalOrient.Length >= 3)
        {
            _targetRotations[0] = SMPLX.QuatFromRodrigues(
                frame.GlobalOrient[0],
                frame.GlobalOrient[1],
                frame.GlobalOrient[2]
            );
        }

        // --- Body pose → 21 joint rotations ---
        if (frame.BodyPose != null && frame.BodyPose.Length >= 63)
        {
            for (int i = 0; i < BodyJointNames.Length; i++)
            {
                int offset = i * 3;
                _targetRotations[i + 1] = SMPLX.QuatFromRodrigues(
                    frame.BodyPose[offset + 0],
                    frame.BodyPose[offset + 1],
                    frame.BodyPose[offset + 2]
                );
            }
        }

        // --- Beta shapes (optional, usually set once) ---
        if (frame.Betas != null && frame.Betas.Length > 0)
        {
            for (int i = 0; i < Mathf.Min(frame.Betas.Length, SMPLX.NUM_BETAS); i++)
            {
                _smplx.betas[i] = frame.Betas[i];
            }
            _smplx.SetBetaShapes();
        }

        if (logFrames)
        {
            Debug.Log($"[AvatarController] {frame.FeedbackLabel} | knee={frame.KneeAngle:F1}°");
        }
    }

    // ========================================================================
    // WebSocket Communication
    // ========================================================================

    public void Connect()
    {
        Disconnect();
        _cancellation = new CancellationTokenSource();
        _ = WebSocketLoop(_cancellation.Token);
    }

    public void Disconnect()
    {
        _isConnected = false;
        if (_cancellation != null)
        {
            _cancellation.Cancel();
            _cancellation.Dispose();
            _cancellation = null;
        }
        if (_webSocket != null)
        {
            try { _webSocket.Dispose(); } catch { /* ignore */ }
            _webSocket = null;
        }
    }

    private async Task WebSocketLoop(CancellationToken token)
    {
        try
        {
            _webSocket = new ClientWebSocket();
            _webSocket.Options.KeepAliveInterval = TimeSpan.FromSeconds(10);

            Debug.Log($"[AvatarController] Connecting to {serverUrl}...");
            await _webSocket.ConnectAsync(new Uri(serverUrl), token);
            _isConnected = true;
            Debug.Log("[AvatarController] Connected!");

            byte[] buffer = new byte[1024 * 128]; // 128KB for large responses

            while (_webSocket.State == WebSocketState.Open && !token.IsCancellationRequested)
            {
                StringBuilder sb = new StringBuilder();
                WebSocketReceiveResult result;

                do
                {
                    result = await _webSocket.ReceiveAsync(
                        new ArraySegment<byte>(buffer), token
                    );

                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        Debug.Log("[AvatarController] Server closed connection.");
                        _isConnected = false;
                        return;
                    }

                    sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                }
                while (!result.EndOfMessage);

                ParseServerMessage(sb.ToString());
            }
        }
        catch (OperationCanceledException) { }
        catch (WebSocketException ex)
        {
            Debug.LogWarning($"[AvatarController] WebSocket error: {ex.Message}");
        }
        catch (Exception ex)
        {
            Debug.LogError($"[AvatarController] Error: {ex}");
        }
        finally
        {
            _isConnected = false;
            _reconnectTimer = reconnectInterval;
            Debug.Log("[AvatarController] Disconnected.");
        }
    }

    /// <summary>
    /// Start a new server-side exercise session.
    /// </summary>
    public async void StartExerciseSession()
    {
        await SendJsonAsync(
            "{\"data_type\":\"session_start\",\"user_id\":\"" + EscapeJson(userId) +
            "\",\"exercise_type\":\"" + EscapeJson(exerciseType) + "\"}"
        );
    }

    /// <summary>
    /// End the active server-side session and save its final summary to MySQL.
    /// </summary>
    public async void EndExerciseSession()
    {
        await SendJsonAsync("{\"data_type\":\"session_end\"}");
    }

    /// <summary>
    /// Send 2D keypoints to the server for processing.
    /// Call from your camera/VR pose extraction pipeline.
    /// </summary>
    public async void SendKeypoints(float[][] keypoints17x3, string frameId = null)
    {
        if (_webSocket == null || _webSocket.State != WebSocketState.Open) return;

        try
        {
            StringBuilder sb = new StringBuilder();
            sb.Append("{\"data_type\":\"keypoints\"");
            if (frameId != null)
                sb.Append(",\"frame_id\":\"").Append(frameId).Append("\"");
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
        catch (Exception ex)
        {
            Debug.LogWarning($"[AvatarController] Send failed: {ex.Message}");
        }
    }

    private async Task SendJsonAsync(string json)
    {
        if (_webSocket == null || _webSocket.State != WebSocketState.Open) return;

        byte[] msg = Encoding.UTF8.GetBytes(json);
        await _webSocket.SendAsync(
            new ArraySegment<byte>(msg),
            WebSocketMessageType.Text,
            true,
            _cancellation?.Token ?? CancellationToken.None
        );
    }

    private static string EscapeJson(string value)
    {
        return (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
    }

    private void ParseServerMessage(string json)
    {
        try
        {
            ServerResponse response = JsonUtility.FromJson<ServerResponse>(json);
            if (response == null || response.status != "ok" || response.fit == null)
                return;

            PoseFrame frame = new PoseFrame
            {
                GlobalOrient = response.fit.global_orient,
                BodyPose = response.fit.body_pose,
                Betas = null,  // Set once via Inspector if needed
                FeedbackLabel = response.feedback?.label ?? "",
                KneeAngle = response.feedback?.knee_angle_deg ?? 0f,
            };

            _frameQueue.Enqueue(frame);
        }
        catch (Exception ex)
        {
            if (logFrames)
                Debug.LogWarning($"[AvatarController] Parse error: {ex.Message}");
        }
    }

    // ========================================================================
    // Public API
    // ========================================================================

    public bool IsConnected => _isConnected;

    /// <summary>
    /// Manually feed SMPL-X parameters without WebSocket.
    /// Useful for testing with pre-recorded data.
    /// </summary>
    public void FeedPose(float[] globalOrient3, float[] bodyPose63)
    {
        _frameQueue.Enqueue(new PoseFrame
        {
            GlobalOrient = globalOrient3,
            BodyPose = bodyPose63,
            FeedbackLabel = "",
            KneeAngle = 0f,
        });
    }
}
