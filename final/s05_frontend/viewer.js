/**
 * VR Pose Viewer — Real-time 2D Skeleton Rendering Engine
 *
 * Connects to the FastAPI WebSocket server, receives COCO-17 keypoints,
 * and renders skeleton overlays on HTML Canvas. Designed to run in
 * Meta Quest 3's browser for VR-based real-time pose feedback.
 */

// ================================================================
// COCO 17 Skeleton Definition
// ================================================================

const COCO_JOINTS = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle"
];

const COCO_BONES = [
    [0, 1], [0, 2], [1, 3], [2, 4],           // Head
    [5, 6],                                     // Shoulders
    [5, 7], [7, 9],                             // Left arm
    [6, 8], [8, 10],                            // Right arm
    [5, 11], [6, 12],                           // Torso
    [11, 12],                                   // Hips
    [11, 13], [13, 15],                         // Left leg
    [12, 14], [14, 16],                         // Right leg
];

const BONE_COLORS = {
    head:  "#b388ff",
    torso: "#4a9eff",
    left:  "#00e5ff",
    right: "#00e676",
    hip:   "#ff9100",
};

function getBoneColor(i, j) {
    if (i <= 4 || j <= 4) return BONE_COLORS.head;
    if ((i === 5 && j === 6) || (i === 5 && j === 11) || (i === 6 && j === 12)) return BONE_COLORS.torso;
    if (i === 11 && j === 12) return BONE_COLORS.hip;
    if ([5, 7, 9, 11, 13, 15].includes(i) && [5, 7, 9, 11, 13, 15].includes(j)) return BONE_COLORS.left;
    return BONE_COLORS.right;
}

// ================================================================
// State
// ================================================================

let ws = null;
let isConnected = false;
let frameCount = 0;
let lastFrameTime = 0;
let fpsBuffer = [];
const mirrorCheckbox = document.getElementById("mirror-mode");

// Gradient cache: recreated only when canvas dimensions change
const _gradCache = new Map();
function getCachedBackground(ctx, cacheKey) {
    const w = ctx.canvas.width, h = ctx.canvas.height;
    const cached = _gradCache.get(cacheKey);
    if (cached && cached.w === w && cached.h === h) return cached.grad;
    const grad = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w * 0.7);
    grad.addColorStop(0, "#0d0d18");
    grad.addColorStop(1, "#08080e");
    _gradCache.set(cacheKey, { w, h, grad });
    return grad;
}

// Expert pose data (loaded from server)
let expertFrames = [];       // Array of {frame, keypoints}
let expertFrameIndex = 0;    // Current playback index
let expertLoaded = false;

// ================================================================
// WebSocket Connection
// ================================================================

function connect() {
    let url = document.getElementById("server-url").value.trim();

    // HTTPS 페이지에서는 반드시 wss:// 사용, 포트 번호 제거
    if (location.protocol === "https:") {
        url = url.replace(/^ws:\/\//, "wss://").replace(/:8000\//, "/").replace(/:8000$/, "");
    }
    document.getElementById("server-url").value = url;

    if (ws && ws.readyState <= 1) {
        ws.close();
    }

    try {
        ws = new WebSocket(url);
    } catch (e) {
        console.error("WebSocket creation failed:", e);
        return;
    }

    ws.onopen = () => {
        isConnected = true;
        updateConnectionUI(true);
        console.log("[Viewer] Connected to", url);
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleFrame(data);
        } catch (e) {
            console.warn("[Viewer] Parse error:", e);
        }
    };

    ws.onclose = () => {
        isConnected = false;
        updateConnectionUI(false);
        console.log("[Viewer] Disconnected");
        // Auto-reconnect after 3 seconds
        setTimeout(() => {
            if (!isConnected) connect();
        }, 3000);
    };

    ws.onerror = (err) => {
        console.warn("[Viewer] WebSocket error:", err);
    };
}

function updateConnectionUI(connected) {
    const badge = document.getElementById("connection-badge");
    const btn = document.getElementById("connect-btn");
    if (connected) {
        badge.textContent = "Connected";
        badge.className = "badge connected";
        btn.textContent = "Disconnect";
    } else {
        badge.textContent = "Disconnected";
        badge.className = "badge disconnected";
        btn.textContent = "Connect";
    }
}

// ================================================================
// Frame Handler
// ================================================================

function handleFrame(data) {
    if (data.status !== "ok") return;

    frameCount++;
    const now = performance.now();

    // FPS calculation
    if (lastFrameTime > 0) {
        const dt = now - lastFrameTime;
        fpsBuffer.push(1000 / dt);
        if (fpsBuffer.length > 30) fpsBuffer.shift();
        const avgFps = fpsBuffer.reduce((a, b) => a + b, 0) / fpsBuffer.length;
        document.getElementById("fps-display").textContent = `${avgFps.toFixed(0)} FPS`;
    }
    lastFrameTime = now;

    // Latency
    const latency = data.debug?.inference_ms ?? 0;
    document.getElementById("latency-display").textContent = `${latency.toFixed(1)}ms`;

    // Draw user skeleton from keypoints_2d
    const keypoints = data.keypoints_2d;
    if (keypoints && keypoints.length === 17) {
        drawSkeleton("user-canvas", keypoints, true);
        document.getElementById("user-overlay").classList.add("hidden");
    }

    // Expert skeleton is driven by its own independent loop (see startExpertLoop)

    // Update feedback
    updateFeedback(data.feedback);

    // Update frame info
    document.getElementById("frame-counter").textContent = `Frame: ${data.frame_id || frameCount}`;
    const smoothingInfo = data.debug?.smoothing_enabled ? `ON (${data.debug.smoothing_frame})` : "OFF";
    document.getElementById("smoothing-status").textContent = `Smoothing: ${smoothingInfo}`;
}

// ================================================================
// Skeleton Drawing
// ================================================================

function drawSkeleton(canvasId, keypoints, isUser) {
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;
    const mirror = isUser && mirrorCheckbox.checked;

    ctx.clearRect(0, 0, w, h);

    // Background gradient (cached — recreated only on resize)
    ctx.fillStyle = getCachedBackground(ctx, isUser ? "user" : "expert");
    ctx.fillRect(0, 0, w, h);

    // Normalize keypoints to canvas space
    const points = normalizeToCanvas(keypoints, w, h, mirror);

    // Draw bones
    ctx.lineWidth = 3;
    ctx.lineCap = "round";
    for (const [i, j] of COCO_BONES) {
        const p1 = points[i];
        const p2 = points[j];
        if (!p1 || !p2) continue;

        ctx.strokeStyle = getBoneColor(i, j);
        ctx.globalAlpha = 0.85;
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
    }

    // Draw joints
    ctx.globalAlpha = 1.0;
    for (let i = 0; i < points.length; i++) {
        const p = points[i];
        if (!p) continue;

        // Outer glow
        ctx.beginPath();
        ctx.arc(p.x, p.y, 6, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0, 229, 255, 0.15)";
        ctx.fill();

        // Inner dot
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = "#00e5ff";
        ctx.fill();

        // White center
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
    }
}

function normalizeToCanvas(keypoints, canvasW, canvasH, mirror) {
    // Auto-detect coordinate format:
    // MoveNet: [y, x, confidence] — values in 0~1, nose y ≈ 0.15~0.3
    // Pixel:   [x, y, z] — values can be large (640x480 or 1920x1080)
    //
    // Heuristic: if all values in [0,1] range AND nose (col0) is near the
    // top (smallest among body joints), it's MoveNet [y,x,conf] format.
    let max0 = -Infinity, min0 = Infinity, max1 = -Infinity, min1 = Infinity;
    const col0 = new Array(keypoints.length);
    const col1 = new Array(keypoints.length);
    for (let _i = 0; _i < keypoints.length; _i++) {
        const v0 = keypoints[_i][0], v1 = keypoints[_i][1];
        col0[_i] = v0; col1[_i] = v1;
        if (v0 > max0) max0 = v0;
        if (v0 < min0) min0 = v0;
        if (v1 > max1) max1 = v1;
        if (v1 < min1) min1 = v1;
    }
    const allNormalized = max0 <= 1.5 && max1 <= 1.5 && min0 >= -0.5 && min1 >= -0.5;
    const range0 = max0 - min0;
    const range1 = max1 - min1;

    // MoveNet [y,x,conf]: nose col0 should be near top (small value),
    // ankle col0 should be near bottom (large value)
    const noseCol0 = col0[0];  // nose
    const ankleCol0 = Math.max(col0[15] || 0, col0[16] || 0);  // ankles
    const isMoveNetYX = allNormalized && noseCol0 < ankleCol0;

    // Extract x, y based on detected format
    const points2D = keypoints.map(kp => {
        if (isMoveNetYX) {
            return { rawX: kp[1], rawY: kp[0] };  // swap: [y,x] → x,y
        } else {
            return { rawX: kp[0], rawY: kp[1] };   // already [x,y]
        }
    });

    // Find bounding box
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    for (const p of points2D) {
        if (p.rawX < minX) minX = p.rawX;
        if (p.rawX > maxX) maxX = p.rawX;
        if (p.rawY < minY) minY = p.rawY;
        if (p.rawY > maxY) maxY = p.rawY;
    }

    let rangeX = maxX - minX || 0.001;
    let rangeY = maxY - minY || 0.001;

    // For side-view data (very narrow horizontal range), enforce minimum
    // aspect ratio so the skeleton doesn't become an ultra-thin vertical line.
    // A standing person is roughly 1:3 (width:height) at minimum.
    const minAspect = 0.3;  // minimum width / height ratio
    if (rangeX / rangeY < minAspect) {
        const targetRangeX = rangeY * minAspect;
        const padX = (targetRangeX - rangeX) / 2;
        minX -= padX;
        maxX += padX;
        rangeX = targetRangeX;
    }

    const padding = 0.08;
    const scaleX = canvasW * (1 - 2 * padding) / rangeX;
    const scaleY = canvasH * (1 - 2 * padding) / rangeY;
    const scale = Math.min(scaleX, scaleY);

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    return points2D.map(p => {
        let x = (p.rawX - centerX) * scale + canvasW / 2;
        const y = (p.rawY - centerY) * scale + canvasH / 2;
        if (mirror) x = canvasW - x;
        return { x, y };
    });
}

// ================================================================
// Feedback & Fatigue UI
// ================================================================

function updateFeedback(feedback) {
    if (!feedback) return;

    // Score: use server-computed DTW score directly
    const score = typeof feedback.score === "number" ? feedback.score : 0;
    updateScore(score);

    // Rep count with pop animation
    const repEl = document.getElementById("rep-count");
    if (repEl) {
        const prev = parseInt(repEl.textContent, 10) || 0;
        const next = feedback.rep_count ?? 0;
        repEl.textContent = next;
        if (next > prev) {
            repEl.style.transform = "scale(1.4)";
            setTimeout(() => { repEl.style.transform = "scale(1)"; }, 200);
        }
    }

    // Feedback message + severity styling
    const labelEl = document.getElementById("feedback-label");
    const msg = feedback.message || feedback.label || "";
    const severity = feedback.severity || "";
    labelEl.textContent = msg;
    labelEl.className = "feedback-label";
    if (severity === "error") labelEl.classList.add("bad");
    else if (severity === "warning") labelEl.classList.add("warning");
    else if (score >= 70) labelEl.classList.add("good");

    // Body part secondary detail
    const detailEl = document.getElementById("knee-angle");
    if (detailEl) {
        detailEl.textContent = feedback.body_part ? `부위: ${feedback.body_part}` : "";
    }

    // Muscle fatigue dots
    if (feedback.muscle_fatigue) {
        updateFatigueDots(feedback.muscle_fatigue);
    }
}

function updateScore(score) {
    const scoreEl = document.getElementById("score-value");
    const ringFill = document.getElementById("score-ring-fill");

    scoreEl.textContent = score;

    // Ring progress (circumference = 2 * π * 52 ≈ 327)
    const circumference = 327;
    const offset = circumference * (1 - score / 100);
    ringFill.style.strokeDashoffset = offset;

    // Color based on score
    if (score >= 80) {
        ringFill.style.stroke = "#00e676";
    } else if (score >= 50) {
        ringFill.style.stroke = "#ff9100";
    } else {
        ringFill.style.stroke = "#ff3d00";
    }
}

function updateFatigueDots(fatigue) {
    for (const [muscle, level] of Object.entries(fatigue)) {
        const dot = document.getElementById(`dot-${muscle}`);
        if (!dot) continue;
        dot.className = "fatigue-dot";
        if (level === "med") dot.classList.add("med");
        else if (level === "high") dot.classList.add("high");
    }
}

// ================================================================
// Expert Pose Loader
// ================================================================

function startExpertLoop() {
    const FPS = 24;
    setInterval(() => {
        if (!expertLoaded || expertFrames.length === 0) return;
        // 시각 기반 인덱스 — viewer/app 모두 같은 프레임을 동시에 표시
        expertFrameIndex = Math.floor(Date.now() / (1000 / FPS)) % expertFrames.length;
        const frame = expertFrames[expertFrameIndex];
        const kpts = frame.keypoints ?? frame;
        if (kpts && kpts.length === 17) {
            drawSkeleton("expert-canvas", kpts, false);
            document.getElementById("expert-overlay").classList.add("hidden");
        }
    }, 1000 / FPS);
}

async function loadExpertPoses() {
    const baseUrl = location.origin || "http://127.0.0.1:8000";
    try {
        const resp = await fetch(`${baseUrl}/api/expert`);
        const data = await resp.json();
        if (data.status === "ok" && data.frames && data.frames.length > 0) {
            expertFrames = data.frames;
            expertFrameIndex = 0;
            expertLoaded = true;
            console.log(`[Viewer] Expert poses loaded: ${data.filename} (${data.total_frames} frames)`);
        } else {
            console.warn("[Viewer] No expert poses available:", data.message);
        }
    } catch (e) {
        console.warn("[Viewer] Failed to load expert poses:", e);
    }
}

// ================================================================
// Init
// ================================================================

document.getElementById("connect-btn").addEventListener("click", () => {
    if (isConnected && ws) {
        ws.close();
    } else {
        connect();
    }
});

// ================================================================
// Webcam + Browser-Side Pose Detection (TF.js MoveNet)
// ================================================================

let poseDetector = null;
let cameraRunning = false;
let lastSendMs = 0;
let isDetecting = false;
const SEND_INTERVAL_MS = 66;   // 15fps to server; local skeleton still draws immediately.
const DETECT_INTERVAL_MS = 33; // 30fps display (browser-local)

async function startCamera() {
    const btn = document.getElementById("camera-btn");
    const statusEl = document.getElementById("camera-status");

    if (cameraRunning) {
        stopCamera();
        return;
    }

    try {
        statusEl.textContent = "모델 로딩...";
        btn.disabled = true;

        // Load MoveNet LIGHTNING (fast, ~20ms) only once
        if (!poseDetector) {
            await tf.ready();
            poseDetector = await poseDetection.createDetector(
                poseDetection.SupportedModels.MoveNet,
                { modelType: poseDetection.movenet.modelType.SINGLEPOSE_LIGHTNING }
            );
        }

        // Get webcam stream
        const video = document.getElementById("webcam-video");
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: "user" }
        });
        video.srcObject = stream;
        await new Promise((resolve, reject) => {
            video.onloadeddata = resolve;
            video.onerror = reject;
        });
        await video.play();

        cameraRunning = true;
        btn.textContent = "📷 웹캠 중지";
        btn.disabled = false;
        statusEl.textContent = "카메라 ON";
        statusEl.style.color = "#00e676";

        // Auto-connect WebSocket if not already connected
        if (!isConnected) connect();

        detectLoop();
    } catch (err) {
        console.error("[Camera]", err);
        statusEl.textContent = "오류: " + err.message;
        statusEl.style.color = "#ff3d00";
        btn.textContent = "📷 웹캠 시작";
        btn.disabled = false;
    }
}

function stopCamera() {
    cameraRunning = false;
    const video = document.getElementById("webcam-video");
    if (video && video.srcObject) {
        video.srcObject.getTracks().forEach(t => t.stop());
        video.srcObject = null;
    }
    const btn = document.getElementById("camera-btn");
    const statusEl = document.getElementById("camera-status");
    btn.textContent = "📷 웹캠 시작";
    statusEl.textContent = "카메라 꺼짐";
    statusEl.style.color = "#888";
}

async function detectLoop() {
    if (!cameraRunning || !poseDetector) return;

    const now = performance.now();
    const video = document.getElementById("webcam-video");

    if (!isDetecting && now - lastSendMs >= SEND_INTERVAL_MS && isConnected && ws && ws.readyState === WebSocket.OPEN && video.readyState >= 2) {
        isDetecting = true;
        try {
            const poses = await poseDetector.estimatePoses(video);
            if (poses && poses.length > 0) {
                // TF.js returns pixel coords; normalize to [0,1] matching KEYPOINT_FORMAT=movenet_yx
                const vw = video.videoWidth || 640;
                const vh = video.videoHeight || 480;
                const payload = poses[0].keypoints.map(kp => [kp.y / vh, kp.x / vw, kp.score ?? 0.9]);
                drawSkeleton("user-canvas", payload, true);
                document.getElementById("user-overlay").classList.add("hidden");
                ws.send(JSON.stringify({
                    data_type: "keypoints",
                    frame_id: `cam_${frameCount}`,
                    client_timestamp_ms: Date.now(),
                    payload
                }));
                lastSendMs = now;
            }
        } catch (e) {
            console.warn("[Detect]", e);
        } finally {
            isDetecting = false;
        }
    }

    requestAnimationFrame(detectLoop);
}

document.getElementById("camera-btn").addEventListener("click", startCamera);

// ================================================================
// High-DPI canvas support
function initDPR() {
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    if (dpr <= 1) return;
    ["expert-canvas", "user-canvas"].forEach(id => {
        const canvas = document.getElementById(id);
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        const w = Math.round(rect.width) || 480;
        const h = Math.round(rect.height) || 640;
        if (w < 10 || h < 10) return; // layout not ready yet
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        // CSS size is controlled by stylesheet — no inline style needed
    });
}

// ================================================================
// Auto-connect and load expert data on page load
window.addEventListener("load", () => {
    // Auto-adjust WebSocket URL based on protocol and host
    if (location.hostname !== "127.0.0.1" && location.hostname !== "localhost") {
        const wsProto = location.protocol === "https:" ? "wss" : "ws";
        const wsPort = location.protocol === "https:" ? "" : ":8000";
        const wsUrl = `${wsProto}://${location.hostname}${wsPort}/ws/pose`;
        document.getElementById("server-url").value = wsUrl;
    }
    // Scale canvases for high-DPI screens (one frame after layout)
    requestAnimationFrame(initDPR);
    // Load expert reference poses and start independent loop
    loadExpertPoses();
    startExpertLoop();
    // Connect WebSocket
    setTimeout(connect, 500);
});
