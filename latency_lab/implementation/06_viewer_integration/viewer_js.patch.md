# `viewer_2d/viewer.js` Integration

Replace the current WebSocket send block:

```javascript
ws.send(JSON.stringify({
  data_type: "keypoints",
  frame_id: `cam_${frameCount}`,
  payload
}));
```

with:

```javascript
const frameId = `cam_${frameCount}`;
ws.send(JSON.stringify({
  data_type: "keypoints",
  frame_id: frameId,
  client_timestamp_ms: Date.now(),
  latency_probe: {
    frameId,
    viewerCreatedAtMs: performance.now(),
    clientTimestampMs: Date.now()
  },
  payload
}));
```

The existing immediate local skeleton draw should stay in place. That path is
important because it confirms camera detection is working even if server relay
latency increases.
