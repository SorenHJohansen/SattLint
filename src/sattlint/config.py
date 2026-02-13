"""Configuration management for SattLint."""
from __future__ import annotations

import os
import sys
import tomllib
import tomli_w
from pathlib import Path

DEFAULT_CONFIG = {
    "root": "",
    "mode": "official",
    "scan_root_only": False,
    "fast_cache_validation": True,
    "debug": False,
    "program_dir": "",
    "ABB_lib_dir": "",
    "icf_dir": "",
    "other_lib_dirs": [],
}

def get_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    cfg_dir = base / "sattlint"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.toml"


def load_config(path: Path) -> tuple[dict, bool]:
    if not path.exists():
        print(f"⚠ No config found, creating default: {path}")
        cfg = DEFAULT_CONFIG.copy()
        save_config(path, cfg)
        return cfg, True

    with path.open("rb") as f:
        cfg = tomllib.load(f)

    merged = DEFAULT_CONFIG.copy()
    merged.update(cfg)
    merged.pop("ignore_ABB_lib", None)
    return merged, False


def save_config(path: Path, cfg: dict) -> None:
    def normalize(v):
        if isinstance(v, Path):
            return str(v)
        if isinstance(v, (list, tuple)):
            return [normalize(x) for x in v]
        if isinstance(v, dict):
            return {k: normalize(x) for k, x in v.items()}
        if v is None:
            raise ValueError(
                "Cannot serialize None to TOML. Provide a default value or omit the key."
            )
        return v

    with path.open("wb") as f:
        tomli_w.dump(normalize(cfg), f)


def root_exists(root: str, cfg: dict) -> bool:
    dirs = [Path(cfg["program_dir"])] + [Path(p) for p in cfg["other_lib_dirs"]]

    if cfg["mode"] == "draft":
        extensions = [".s", ".x"]  # Try draft first, fallback to official
    else:
        extensions = [".x"]  # Official only

    for d in dirs:
        if not d.exists():
            continue
        for ext in extensions:
            if (d / f"{root}{ext}").exists():
                return True

    return False


def self_check(cfg: dict) -> bool:
    print("\n--- Self-check diagnostics ---")
    ok = True

    # Python version
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ required")
        ok = False
    else:
        print(f"✔ Python {sys.version.split()[0]}")

    # Required keys
    required_keys = [
        "root",
        "mode",
        "scan_root_only",
        "fast_cache_validation",
        "debug",
        "program_dir",
        "ABB_lib_dir",
        "icf_dir",
        "other_lib_dirs",
    ]
    for k in required_keys:
        if k not in cfg:
            print(f"❌ Missing config key: {k}")
            ok = False

    # Directories
    for name in ("program_dir", "ABB_lib_dir", "icf_dir"):
        raw = cfg.get(name, "")
        if not raw:
            print(f"⚠ {name} not set")
            continue
        p = Path(raw)
        if not p.exists():
            print(f"❌ {name} does not exist: {p}")
            ok = False
        elif not os.access(p, os.R_OK):
            print(f"❌ {name} not readable: {p}")
            ok = False
        else:
            print(f"✔ {name}: {p}")

    # other_lib_dirs
    for p in cfg.get("other_lib_dirs", []):
        path = Path(p)
        if not path.exists():
            print(f"⚠ other_lib_dirs entry missing: {path}")
        else:
            print(f"✔ other_lib_dirs: {path}")

    # Root existence
    if root_exists(cfg.get("root", ""), cfg):
        print(f"✔ Root program/library found: {cfg['root']}")
    else:
        print(f"❌ Root program/library not found: {cfg.get('root')}")
        ok = False

    print("------------------------------\n")
    return ok
