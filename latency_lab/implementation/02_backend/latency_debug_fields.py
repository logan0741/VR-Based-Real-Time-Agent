"""Reference helpers for adding latency fields to final/s02_backend/server.py."""

from __future__ import annotations

import time
from typing import Any, Dict


def now_epoch_ms() -> int:
    return int(time.time() * 1000)


def relay_debug_fields(message: Dict[str, Any]) -> Dict[str, Any]:
    server_received_ms = now_epoch_ms()
    return {
        "relay_only": True,
        "client_timestamp_ms": message.get("client_timestamp_ms"),
        "server_received_ms": server_received_ms,
        "server_relay_sent_ms": now_epoch_ms(),
    }


def attach_processed_debug(response: Dict[str, Any], source_message: Dict[str, Any]) -> Dict[str, Any]:
    response.setdefault("debug", {})
    response["debug"]["client_timestamp_ms"] = source_message.get("client_timestamp_ms")
    response["debug"]["server_processed_at_ms"] = now_epoch_ms()
    return response
