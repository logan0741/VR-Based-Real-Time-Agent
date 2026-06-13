# Latency Suite Summary

- Local URL: `ws://127.0.0.1:8000/ws/pose`
- Cloudflare URL: `wss://pt.gun-hee.com/ws/pose`
- Frames: `90`
- FPS: `30.0`

## Key Numbers

- Local app relay avg: `4.235 ms`
- Cloudflare app relay avg: `201.012 ms`
- Local app processed avg: `9.509 ms`
- Cloudflare app processed avg: `205.692 ms`

## Reading

- If local latency is low but Cloudflare latency is high, the current bottleneck is outside the backend preprocessing path.
- If both local and Cloudflare are high, inspect backend preprocessing, queueing, and frame dropping.
- `relay` is the live skeleton path. `processed` is the feedback/scoring path.
