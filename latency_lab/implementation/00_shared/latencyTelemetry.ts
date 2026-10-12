export type LatencyStage = 'viewer_send' | 'server_relay' | 'processed_feedback' | 'app_receive';

export type LatencyProbe = {
  frameId: string;
  viewerCreatedAtMs: number;
  clientTimestampMs: number;
};

export type LatencySample = {
  frameId: string;
  stage: LatencyStage;
  dataType?: string;
  relayOnly: boolean;
  clientToReceiveMs?: number;
  serverQueueMs?: number;
  serverToReceiveMs?: number;
  receivedAtMs: number;
};

export function createLatencyPayload(frameId: string): LatencyProbe {
  return {
    frameId,
    viewerCreatedAtMs: performance.now(),
    clientTimestampMs: Date.now(),
  };
}

export function readLatencySample(message: any, receivedAtMs = Date.now()): LatencySample | null {
  const frameId = String(message?.frame_id ?? '');
  if (!frameId) return null;

  const debug = message?.debug ?? {};
  const clientTimestampMs = Number(debug.client_timestamp_ms ?? message.client_timestamp_ms);
  const serverRelaySentMs = Number(debug.server_relay_sent_ms);
  const serverProcessedAtMs = Number(debug.server_processed_at_ms);
  const serverSentMs = Number.isFinite(serverRelaySentMs) ? serverRelaySentMs : serverProcessedAtMs;
  const relayOnly = Boolean(debug.relay_only);

  return {
    frameId,
    stage: relayOnly ? 'server_relay' : 'processed_feedback',
    dataType: message?.data_type,
    relayOnly,
    clientToReceiveMs: Number.isFinite(clientTimestampMs) ? receivedAtMs - clientTimestampMs : undefined,
    serverQueueMs:
      Number.isFinite(clientTimestampMs) && Number.isFinite(serverSentMs)
        ? serverSentMs - clientTimestampMs
        : undefined,
    serverToReceiveMs: Number.isFinite(serverSentMs) ? receivedAtMs - serverSentMs : undefined,
    receivedAtMs,
  };
}

export function summarizeLatency(values: number[]) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) {
    return { count: 0, avgMs: null, medianMs: null, p95Ms: null, maxMs: null };
  }
  const pick = (ratio: number) => sorted[Math.min(sorted.length - 1, Math.floor((sorted.length - 1) * ratio))];
  const avg = sorted.reduce((sum, value) => sum + value, 0) / sorted.length;
  return {
    count: sorted.length,
    avgMs: Number(avg.toFixed(3)),
    medianMs: Number(pick(0.5).toFixed(3)),
    p95Ms: Number(pick(0.95).toFixed(3)),
    maxMs: Number(sorted[sorted.length - 1].toFixed(3)),
  };
}
