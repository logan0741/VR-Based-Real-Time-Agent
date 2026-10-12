# Latency Implementation Kit

This folder contains the code needed to reproduce the latency pipeline in the
main app, viewer, and backend.

The files are split by runtime stage so they can be copied into the main branch
without guessing where each piece belongs.

## Folder Map

- `00_shared/latencyTelemetry.ts`: shared browser telemetry helpers.
- `01_viewer/viewerLatency.js`: viewer-side camera/send instrumentation.
- `02_backend/latency_debug_fields.py`: backend timestamp fields to add to `/ws/pose`.
- `03_app/useLatencyMetrics.ts`: app-side receive metrics hook.
- `04_report/latencyReportWriter.ts`: browser-side JSON report builder.
- `APPLY_TO_MAIN.md`: exact integration steps.

The runnable measurement suite remains one level up in `latency_lab`.
