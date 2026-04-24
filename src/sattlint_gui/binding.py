from __future__ import annotations

import importlib
import io
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AnalyzerDescriptor:
    key: str
    name: str


@dataclass(frozen=True, slots=True)
class BindingResult:
    ok: bool
    output: str
    value: Any = None


@dataclass(frozen=True, slots=True)
class DemoTarget:
    name: str
    reason: str


_FALLBACK_CONFIG_PATH = Path("sattlint.json")
_FALLBACK_CONFIG = {
    "analyzed_programs_and_libraries": [],
    "mode": "draft",
}
_APP_MODULE: Any = None


def _get_app_module() -> Any:
    global _APP_MODULE
    if _APP_MODULE is None:
        _APP_MODULE = importlib.import_module("sattlint.app")
    return _APP_MODULE


def _capture_output(func, *args, **kwargs) -> BindingResult:
    buffer = io.StringIO()
    ok = True
    value: Any = None
    with redirect_stdout(buffer), redirect_stderr(buffer):
        try:
            value = func(*args, **kwargs)
        except Exception as exc:
            ok = False
            print(f"Error: {exc}")
    output = buffer.getvalue().strip()
    if not output:
        output = "OK" if ok else "Failed"
    return BindingResult(ok=ok, output=output, value=value)


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def suggest_workspace_ha_config(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    base_cfg = dict(cfg or _FALLBACK_CONFIG)
    root = _workspace_root()
    libs_root = root / "Libs" / "HA"
    suggestions = {
        "program_dir": libs_root / "UnitLib",
        "ABB_lib_dir": libs_root / "ABBLib",
        "icf_dir": libs_root / "ICF",
        "other_lib_dirs": [
            libs_root / "ProjectLib",
            libs_root / "NNELib",
            libs_root / "PPLib",
        ],
    }

    for key in ("program_dir", "ABB_lib_dir", "icf_dir"):
        current = str(base_cfg.get(key) or "").strip()
        candidate = suggestions[key]
        if not current and candidate.exists():
            base_cfg[key] = str(candidate)

    current_other_libs = [str(item).strip() for item in base_cfg.get("other_lib_dirs", []) if str(item).strip()]
    seen = {item.casefold() for item in current_other_libs}
    for candidate in suggestions["other_lib_dirs"]:
        if not candidate.exists():
            continue
        candidate_str = str(candidate)
        if candidate_str.casefold() in seen:
            continue
        current_other_libs.append(candidate_str)
        seen.add(candidate_str.casefold())
    base_cfg["other_lib_dirs"] = current_other_libs
    return base_cfg


def select_demo_target(cfg: dict[str, Any]) -> DemoTarget | None:
    configured = [str(item).strip() for item in cfg.get("analyzed_programs_and_libraries", []) if str(item).strip()]
    if configured:
        return DemoTarget(name=configured[0], reason="first configured analysis target")

    program_dir = Path(str(cfg.get("program_dir") or "")).expanduser()
    mode = str(cfg.get("mode") or "official").strip().lower()
    if not program_dir.exists() or not program_dir.is_dir():
        return None

    suffixes = (".s", ".x") if mode == "draft" else (".x",)
    candidates = sorted(path.stem for path in program_dir.iterdir() if path.is_file() and path.suffix.lower() in suffixes)
    if not candidates:
        return None
    return DemoTarget(name=candidates[0], reason=f"first {mode} target discovered in program_dir")


class SattLintBinding:
    @property
    def config_path(self):
        try:
            return _get_app_module().CONFIG_PATH
        except Exception:
            return _FALLBACK_CONFIG_PATH

    @property
    def graphics_rules_path(self):
        try:
            return _get_app_module().get_graphics_rules_path()
        except Exception:
            return self.config_path.with_name("graphics_rules.json")

    def load_config(self) -> dict[str, Any]:
        try:
            app_module = _get_app_module()
            loaded = app_module.load_config(app_module.CONFIG_PATH)
        except Exception:
            return suggest_workspace_ha_config(_FALLBACK_CONFIG)
        if isinstance(loaded, tuple):
            return suggest_workspace_ha_config(dict(loaded[0]))
        return suggest_workspace_ha_config(dict(loaded))

    def save_config(self, cfg: dict[str, Any]) -> BindingResult:
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")
        return _capture_output(app_module.save_config, app_module.CONFIG_PATH, cfg)

    def run_self_check(self, cfg: dict[str, Any]) -> BindingResult:
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")
        return _capture_output(app_module.self_check, cfg)

    def ensure_ast_cache(self, cfg: dict[str, Any]) -> BindingResult:
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")
        return _capture_output(app_module.ensure_ast_cache, cfg)

    def run_variable_analysis(self, cfg: dict[str, Any], kinds: Any = None) -> BindingResult:
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")
        return _capture_output(app_module.run_variable_analysis, cfg, kinds)

    def run_docgen(self, cfg: dict[str, Any], *, output_dir: str, output_path: str | None = None) -> BindingResult:
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")
        return _capture_output(
            app_module.run_docgen_command,
            cfg,
            output_dir=output_dir,
            output_path=output_path,
            use_cache=True,
        )

    def select_demo_target(self, cfg: dict[str, Any]) -> DemoTarget | None:
        return select_demo_target(cfg)

    def run_demo(self, cfg: dict[str, Any]) -> BindingResult:
        demo_target = self.select_demo_target(cfg)
        if demo_target is None:
            return BindingResult(
                ok=False,
                output="Error: no demo target available. Add a target or configure program_dir with SattLine files.",
            )

        demo_cfg = dict(cfg)
        demo_cfg["analyzed_programs_and_libraries"] = [demo_target.name]
        self_check = self.run_self_check(demo_cfg)
        variable_analysis = self.run_variable_analysis(demo_cfg)
        combined_output = (
            f"Demo target: {demo_target.name} ({demo_target.reason})\n\n"
            f"[Self-check]\n{self_check.output}\n\n"
            f"[Variable Analysis]\n{variable_analysis.output}"
        )
        return BindingResult(ok=self_check.ok and variable_analysis.ok, output=combined_output, value=demo_target.name)

    def list_enabled_analyzers(self) -> list[AnalyzerDescriptor]:
        try:
            app_module = _get_app_module()
        except Exception:
            return []
        return [AnalyzerDescriptor(key=spec.key, name=spec.name) for spec in app_module._get_enabled_analyzers()]

    def target_exists(self, target: str, cfg: dict[str, Any]) -> bool:
        try:
            app_module = _get_app_module()
        except Exception:
            return False
        return bool(app_module.target_exists(target, cfg))


__all__ = [
    "AnalyzerDescriptor",
    "BindingResult",
    "DemoTarget",
    "SattLintBinding",
    "select_demo_target",
    "suggest_workspace_ha_config",
]
