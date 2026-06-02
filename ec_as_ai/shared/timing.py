# -*- coding: utf-8 -*-
"""Timing helpers for request and module latency metadata."""

from __future__ import annotations

import time
from typing import Any, Dict, List, MutableMapping


def perf_counter() -> float:
    """Return a monotonic timestamp for elapsed-time measurement."""
    return time.perf_counter()


def elapsed_ms(start: float) -> float:
    """Return elapsed milliseconds rounded for display and JSON output."""
    return round((time.perf_counter() - start) * 1000, 2)


def add_module_timing(
    timing: MutableMapping[str, Any],
    module_name: str,
    duration_ms: float,
) -> None:
    """Accumulate duration for a named processing module."""
    modules = timing.setdefault("modules", {})
    module = modules.setdefault(
        module_name,
        {"count": 0, "total_ms": 0.0, "last_ms": 0.0},
    )
    module["count"] += 1
    module["total_ms"] = round(module["total_ms"] + duration_ms, 2)
    module["last_ms"] = round(duration_ms, 2)


def attach_timing_to_messages(
    messages: List[Dict[str, Any]],
    timing: Dict[str, Any],
) -> None:
    """Attach timing metadata to every outgoing message."""
    for message in messages:
        custom = message.get("custom")
        if not isinstance(custom, dict):
            custom = {}
            message["custom"] = custom
        custom["timing"] = timing


__all__ = [
    "add_module_timing",
    "attach_timing_to_messages",
    "elapsed_ms",
    "perf_counter",
]
