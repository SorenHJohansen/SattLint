from __future__ import annotations

import re
import sys
from pathlib import Path

WSL_DRIVE_PATH_RE = re.compile(r"^/mnt/(?P<drive>[a-zA-Z])(?:/(?P<rest>.*))?$")


def normalize_payload_path_text(raw_path: str) -> str:
    cleaned = raw_path.strip().strip("`'\"")
    cleaned = cleaned.replace("\\", "/")
    if sys.platform != "win32":
        return cleaned

    match = WSL_DRIVE_PATH_RE.match(cleaned)
    if not match:
        return cleaned

    drive = match.group("drive").upper()
    rest = match.group("rest") or ""
    return f"{drive}:/{rest}"


def resolve_payload_cwd(raw_cwd: str | None) -> Path:
    return Path(normalize_payload_path_text(raw_cwd or ".")).resolve()
