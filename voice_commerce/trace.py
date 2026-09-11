from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from voice_commerce.config import TRACE_DIR


def new_trace_id() -> str:
    return uuid.uuid4().hex[:12]


def write_trace(trace: dict[str, Any], trace_dir: Path | None = None) -> Path:
    directory = trace_dir or TRACE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        **trace,
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    path = directory / f"{payload['trace_id']}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
