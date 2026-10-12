import { useMemo, useRef, useState } from 'react';
import { readLatencySample, summarizeLatency, type LatencySample } from '../00_shared/latencyTelemetry';

export function useLatencyMetrics() {
  const samplesRef = useRef<LatencySample[]>([]);
  const [version, setVersion] = useState(0);

  function recordIncoming(message: unknown) {
    const sample = readLatencySample(message, Date.now());
    if (!sample) return;
    samplesRef.current.push(sample);
    if (samplesRef.current.length > 1000) {
      samplesRef.current.splice(0, samplesRef.current.length - 1000);
    }
    setVersion((value) => value + 1);
  }

  const summary = useMemo(() => {
    const samples = samplesRef.current;
    const relay = samples.filter((sample) => sample.relayOnly);
    const processed = samples.filter((sample) => !sample.relayOnly);
    return {
      relayClientToApp: summarizeLatency(relay.map((sample) => sample.clientToReceiveMs ?? NaN)),
      relayServerToApp: summarizeLatency(relay.map((sample) => sample.serverToReceiveMs ?? NaN)),
      processedClientToApp: summarizeLatency(processed.map((sample) => sample.clientToReceiveMs ?? NaN)),
      processedServerToApp: summarizeLatency(processed.map((sample) => sample.serverToReceiveMs ?? NaN)),
    };
  }, [version]);

  function toJson() {
    return {
      createdAt: new Date().toISOString(),
      summary,
      samples: samplesRef.current,
    };
  }

  function reset() {
    samplesRef.current = [];
    setVersion((value) => value + 1);
  }

  return { recordIncoming, summary, toJson, reset };
}
