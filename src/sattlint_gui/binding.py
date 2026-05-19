from __future__ import annotations

import importlib
import io
from collections.abc import Callable, Iterator
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from sattline_parser.models.ast_model import BasePicture
from sattlint.analyzers.framework import AnalysisContext, AnalyzerSpec, Report
from sattlint.console import print_output
from sattlint.models.project_graph import ProjectGraph
from sattlint.reporting.variables_report import IssueKind

ConfigDict = dict[str, Any]
LoadedConfig = tuple[ConfigDict, bool]
LoadedProject = tuple[str, BasePicture, ProjectGraph]


class AppModuleProtocol(Protocol):
    CONFIG_PATH: Path
    AnalysisContext: type[AnalysisContext]

    def get_graphics_rules_path(self) -> Path: ...

    def load_config(self, path: Path) -> LoadedConfig: ...

    def save_config(self, path: Path, cfg: ConfigDict) -> None: ...

    def self_check(self, cfg: ConfigDict) -> bool: ...

    def ensure_ast_cache(self, cfg: ConfigDict) -> bool: ...

    def run_variable_analysis(self, cfg: ConfigDict, kinds: set[IssueKind] | None) -> None: ...

    def run_docgen_command(
        self,
        cfg: ConfigDict,
        *,
        output_dir: str,
        output_path: str | None = None,
        use_cache: bool = True,
    ) -> object: ...

    def apply_rule_profile_to_report(self, key: str, report: Report, cfg: ConfigDict) -> Report: ...

    def target_exists(self, target: str, cfg: ConfigDict) -> bool: ...


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
_FALLBACK_CONFIG: ConfigDict = {
    "analyzed_programs_and_libraries": [],
    "mode": "draft",
}
_app_module: AppModuleProtocol | None = None


def _get_app_module() -> AppModuleProtocol:
    global _app_module
    if _app_module is None:
        _app_module = cast(AppModuleProtocol, importlib.import_module("sattlint.app"))
    return _app_module


def _capture_output(func: Callable[..., object], *args: object, **kwargs: object) -> BindingResult:
    buffer = io.StringIO()
    ok = True
    value: object | None = None
    with redirect_stdout(buffer), redirect_stderr(buffer):
        try:
            value = func(*args, **kwargs)
        except Exception as exc:
            ok = False
            print_output(f"Error: {exc}")
    output = buffer.getvalue().strip()
    if not output:
        output = "OK" if ok else "Failed"
    return BindingResult(ok=ok, output=output, value=value)


def _module_attr(app_module: AppModuleProtocol, name: str) -> object:
    module_dict = cast(dict[str, object], cast(Any, app_module).__dict__)
    return module_dict[name]


def _get_enabled_analyzers(app_module: AppModuleProtocol) -> list[AnalyzerSpec]:
    getter = cast(Callable[[], list[AnalyzerSpec]], _module_attr(app_module, "_get_enabled_analyzers"))
    return getter()


def _iter_loaded_projects(app_module: AppModuleProtocol, cfg: ConfigDict) -> Iterator[LoadedProject]:
    iterator = cast(Callable[[ConfigDict], Iterator[LoadedProject]], _module_attr(app_module, "_iter_loaded_projects"))
    return iterator(cfg)


def _target_is_library(
    app_module: AppModuleProtocol,
    cfg: ConfigDict,
    project_bp: BasePicture,
    graph: ProjectGraph,
) -> bool:
    predicate = cast(
        Callable[[ConfigDict, BasePicture, ProjectGraph], bool],
        _module_attr(app_module, "_target_is_library"),
    )
    return predicate(cfg, project_bp, graph)


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def suggest_workspace_ha_config(cfg: ConfigDict | None = None) -> ConfigDict:
    base_cfg = dict(cfg or _FALLBACK_CONFIG)
    root = _workspace_root()
    libs_root = root / "Libs" / "HA"
    program_dir = libs_root / "UnitLib"
    abb_lib_dir = libs_root / "ABBLib"
    icf_dir = libs_root / "ICF"
    other_lib_dirs = [
        libs_root / "ProjectLib",
        libs_root / "NNELib",
        libs_root / "PPLib",
    ]

    for key, candidate in (
        ("program_dir", program_dir),
        ("ABB_lib_dir", abb_lib_dir),
        ("icf_dir", icf_dir),
    ):
        current = str(base_cfg.get(key) or "").strip()
        if not current and candidate.exists():
            base_cfg[key] = str(candidate)

    current_other_libs = [str(item).strip() for item in base_cfg.get("other_lib_dirs", []) if str(item).strip()]
    seen = {item.casefold() for item in current_other_libs}
    for candidate in other_lib_dirs:
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
    def config_path(self) -> Path:
        try:
            return _get_app_module().CONFIG_PATH
        except Exception:
            return _FALLBACK_CONFIG_PATH

    @property
    def graphics_rules_path(self) -> Path:
        try:
            return _get_app_module().get_graphics_rules_path()
        except Exception:
            return self.config_path.with_name("graphics_rules.json")

    def load_config(self) -> ConfigDict:
        try:
            app_module = _get_app_module()
            loaded = app_module.load_config(app_module.CONFIG_PATH)
        except Exception:
            return suggest_workspace_ha_config(_FALLBACK_CONFIG)
        return suggest_workspace_ha_config(dict(loaded[0]))

    def save_config(self, cfg: ConfigDict) -> BindingResult:
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")
        return _capture_output(app_module.save_config, app_module.CONFIG_PATH, cfg)

    def run_self_check(self, cfg: ConfigDict) -> BindingResult:
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")
        return _capture_output(app_module.self_check, cfg)

    def ensure_ast_cache(self, cfg: ConfigDict) -> BindingResult:
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")
        return _capture_output(app_module.ensure_ast_cache, cfg)

    def run_variable_analysis(self, cfg: ConfigDict, kinds: set[IssueKind] | None = None) -> BindingResult:
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")
        return _capture_output(app_module.run_variable_analysis, cfg, kinds)

    def run_docgen(self, cfg: ConfigDict, *, output_dir: str, output_path: str | None = None) -> BindingResult:
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

    def run_bundle(self, cfg: ConfigDict, selected_keys: list[str] | None = None) -> BindingResult:
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

    def run_checks(self, cfg: ConfigDict, selected_keys: list[str] | None = None) -> BindingResult:
        """Run enabled analyzer checks, optionally filtered to selected_keys.

        Replicates app._run_checks behaviour without the interactive pause.
        """
        try:
            app_module = _get_app_module()
        except Exception as exc:
            return BindingResult(ok=False, output=f"Error: {exc}")

        def _execute() -> None:
            analyzers = _get_enabled_analyzers(app_module)
            if selected_keys is not None:
                selected = {key.casefold() for key in selected_keys}
                analyzers = [spec for spec in analyzers if spec.key.casefold() in selected]
            if not analyzers:
                print_output("No matching checks found")
                return
            print_output("--- Running checks ---")
            for target_name, project_bp, graph in _iter_loaded_projects(app_module, cfg):
                context = app_module.AnalysisContext(
                    base_picture=project_bp,
                    graph=graph,
                    debug=bool(cfg.get("debug", False)),
                    target_is_library=_target_is_library(app_module, cfg, project_bp, graph),
                    config=cfg,
                )
                print_output(f"\n=== Target: {target_name} ===")
                for spec in analyzers:
                    print_output(f"\n=== {spec.name} ({spec.key}) ===")
                    report = spec.run(context)
                    report = app_module.apply_rule_profile_to_report(spec.key, report, cfg)
                    print_output(report.summary())

        return _capture_output(_execute)

    def list_enabled_analyzers(self) -> list[AnalyzerDescriptor]:
        try:
            app_module = _get_app_module()
        except Exception:
            return []
        return [AnalyzerDescriptor(key=spec.key, name=spec.name) for spec in _get_enabled_analyzers(app_module)]

    def target_exists(self, target: str, cfg: ConfigDict) -> bool:
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
