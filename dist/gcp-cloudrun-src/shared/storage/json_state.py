from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


def load_json_file(path: str | Path | None, default: Any) -> Any:
    if path is None:
        return default

    file_path = Path(path)
    if not file_path.exists():
        return default

    return json.loads(file_path.read_text(encoding="utf-8"))


def save_json_file(path: str | Path | None, payload: Any) -> None:
    if path is None:
        return

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=file_path.parent,
        prefix=f"{file_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(json.dumps(payload, indent=2))
        temp_path = Path(handle.name)
    temp_path.replace(file_path)
