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

    def run_bundle(self, cfg: dict[str, Any], selected_keys: list[str] | None = None) -> BindingResult:
        """Run variable analysis then checks, combining output as a bundle."""
        parts: list[str] = []
        all_ok = True

        variable_result = self.run_variable_analysis(cfg)
        all_ok = all_ok and variable_result.ok
        parts.append("[Variable Analysis]\n" + variable_result.output)

        checks_result = self.run_checks(cfg, selected_keys)
        all_ok = all_ok and checks_result.ok
        parts.append("[Checks]\n" + checks_result.output)

        return BindingResult(ok=all_ok, output="\n\n".join(parts))

    def run_checks(self, cfg: dict[str, Any], selected_keys: list[str] | None = None) -> BindingResult:
        """Run enabled analyzer checks, optionally filtered to selected_keys.

        Replicates app._run_checks behaviour without the interactive pause.
        """
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")

        def _execute() -> None:
            analyzers = app_module._get_enabled_analyzers()
            if selected_keys is not None:
                selected = {key.casefold() for key in selected_keys}
                analyzers = [spec for spec in analyzers if spec.key.casefold() in selected]
            if not analyzers:
                print("No matching checks found")
                return
            print("--- Running checks ---")
            for target_name, project_bp, graph in app_module._iter_loaded_projects(cfg):
                context = app_module.AnalysisContext(
                    base_picture=project_bp,
                    graph=graph,
                    debug=cfg.get("debug", False),
                    target_is_library=app_module._target_is_library(cfg, project_bp, graph),
                    config=cfg,
                )
                print(f"\n=== Target: {target_name} ===")
                for spec in analyzers:
                    print(f"\n=== {spec.name} ({spec.key}) ===")
                    report = spec.run(context)
                    report = app_module.apply_rule_profile_to_report(spec.key, report, cfg)
                    print(report.summary())

        return _capture_output(_execute)

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
    "SattLintBinding",
    "suggest_workspace_ha_config",
]
