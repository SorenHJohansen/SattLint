#!/usr/bin/env python3
from __future__ import annotations

# ruff: noqa: E402
import argparse
import builtins
import copy
import json
import signal
import sys
import traceback
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from sattline_parser.models.ast_model import BasePicture, FrameModule, ModuleTypeInstance, SingleModule
from sattlint import app
from sattlint import console as console_module
from sattlint.analyzers import variables as variables_module


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    description: str
    runner: Callable[[dict[str, Any]], int | None]
    inputs: list[str]
    watch_paths: tuple[Path, ...] = ()
    blocked_reason: str | None = None


@dataclass(frozen=True)
class TargetContext:
    target_name: str
    variable_name: str | None
    module_name: str | None
    module_path: str | None
    module_local_var: str | None
    documentation_instance_path: str | None
    documentation_moduletype_name: str | None
    graphics_relative_module_path: str | None
    graphics_selector_has_options: bool


@dataclass(frozen=True)
class AuditContext:
    config_path: Path
    graphics_rules_path: Path
    cfg: dict[str, Any]
    default_config_created: bool
    analyzed_targets: list[str]
    extra_target_name: str | None
    enabled_analyzer_keys: list[str]
    variable_analysis_keys: list[str]
    targets_loaded: bool
    target_context: TargetContext | None
    load_error: str | None = None


@dataclass(frozen=True)
class WatchedPathResult:
    path: str
    existed_before: bool
    exists_after: bool
    changed: bool


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    description: str
    status: str
    stdout_path: str
    stderr_path: str
    inputs_path: str
    error: str | None = None
    exit_code: int | None = None
    blocked_reason: str | None = None
    watched_paths: list[WatchedPathResult] = field(default_factory=list)


class ScenarioTimedOutError(TimeoutError):
    pass


class _StatusCapture:
    def __init__(self, output: StringIO) -> None:
        self._output = output

    def __enter__(self) -> Callable[[str], None]:
        def _update(message: str) -> None:
            self._output.write(f"[status] {message}\n")

        return _update

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


@contextmanager
def _time_limit(seconds: int) -> Iterator[None]:
    if seconds <= 0:
        yield
        return

    def _handle_timeout(_signum: int, _frame: object) -> None:
        raise ScenarioTimedOutError(f"Scenario timed out after {seconds} seconds")

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _normalize_name(name: str) -> str:
    return name.replace("/", "-").replace(" ", "-")


def _make_input(responses: Sequence[str]) -> Callable[[str], str]:
    iterator = iter(responses)

    def _input(_prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration as exc:
            raise AssertionError("No more input responses provided") from exc

    return _input


def _find_module_with_localvar(base_picture: BasePicture) -> tuple[list[str], str] | None:
    def walk(modules: Sequence[Any] | None, path: list[str]) -> tuple[list[str], str] | None:
        for module in modules or []:
            if not hasattr(module, "header"):
                continue
            module_path = [*path, module.header.name]
            if isinstance(module, SingleModule):
                if module.localvariables:
                    return module_path, module.localvariables[0].name
                found = walk(module.submodules, module_path)
                if found is not None:
                    return found
            elif isinstance(module, FrameModule):
                found = walk(module.submodules, module_path)
                if found is not None:
                    return found
            elif isinstance(module, ModuleTypeInstance):
                moduletype = next(
                    (
                        candidate
                        for candidate in (base_picture.moduletype_defs or [])
                        if candidate.name.casefold() == module.moduletype_name.casefold()
                    ),
                    None,
                )
                if moduletype is not None and moduletype.localvariables:
                    return module_path, moduletype.localvariables[0].name
        return None

    return walk(getattr(base_picture, "submodules", None), [base_picture.header.name])


def _pick_any_module_name(base_picture: BasePicture) -> str | None:
    found = _find_module_with_localvar(base_picture)
    if found is not None:
        return found[0][-1]
    for module in getattr(base_picture, "submodules", None) or []:
        if hasattr(module, "header"):
            return module.header.name
    return None


def _pick_any_variable_name(base_picture: BasePicture, graph: Any) -> str | None:
    analyzer = variables_module.VariablesAnalyzer(
        base_picture,
        debug=False,
        fail_loudly=False,
        unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
    )
    for values in analyzer._any_var_index.values():
        for variable in values:
            name = getattr(variable, "name", None)
            if isinstance(name, str) and name.strip():
                return name
    return None


def _scan_extra_target_name(cfg: dict[str, Any]) -> str | None:
    configured = {target.casefold() for target in cfg.get("analyzed_programs_and_libraries", [])}
    suffixes = {".g", ".l", ".s", ".x"}
    roots = [
        Path(str(cfg.get("program_dir") or "")),
        Path(str(cfg.get("ABB_lib_dir") or "")),
        *(Path(str(path)) for path in cfg.get("other_lib_dirs", [])),
    ]
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for file_path in root.rglob("*"):
            if file_path.suffix.casefold() not in suffixes:
                continue
            if file_path.stem.casefold() in configured:
                continue
            return file_path.stem
    return None


def _build_documentation_context(
    cfg: dict[str, Any], base_picture: BasePicture, graph: Any
) -> tuple[str | None, str | None]:
    documentation_cfg = app.config_module.get_documentation_config(cfg)
    documentation_cfg["units"] = {"mode": "all", "instance_paths": [], "moduletype_names": []}
    classification = app.classify_documentation_structure(
        base_picture,
        documentation_config=documentation_cfg,
        unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
    )
    candidates = app.discover_documentation_unit_candidates(classification)
    if not candidates:
        return None, None
    first = candidates[0]
    return getattr(first, "short_path", None), getattr(first, "moduletype_label", None) or getattr(
        first, "moduletype_name", None
    )


def _build_graphics_context(cfg: dict[str, Any]) -> tuple[str | None, bool]:
    try:
        options = app._discover_graphics_rule_selector_options(
            cfg,
            selector_field="relative_module_path",
            module_kind="frame",
        )
    except Exception:
        options = []
    if options:
        return str(options[0]["selector_value"]), True
    try:
        for target_name, base_picture, graph in app._iter_loaded_projects(cfg):
            entries = app._collect_graphics_layout_entries_for_target(target_name, base_picture, graph)
            for entry in entries:
                selector_value = str(entry.get("relative_module_path") or "").strip()
                if selector_value:
                    return selector_value, False
    except Exception:
        return None, False
    return None, False


def _base_audit_context(
    *,
    cfg: dict[str, Any],
    default_config_created: bool,
    analyzed_targets: list[str],
    extra_target_name: str | None,
    enabled_analyzer_keys: list[str],
    variable_analysis_keys: list[str],
    targets_loaded: bool,
    load_error: str | None = None,
) -> AuditContext:
    return AuditContext(
        config_path=app.CONFIG_PATH,
        graphics_rules_path=app.get_graphics_rules_path(),
        cfg=cfg,
        default_config_created=default_config_created,
        analyzed_targets=analyzed_targets,
        extra_target_name=extra_target_name,
        enabled_analyzer_keys=enabled_analyzer_keys,
        variable_analysis_keys=variable_analysis_keys,
        targets_loaded=targets_loaded,
        target_context=None,
        load_error=load_error,
    )


def load_audit_context(*, include_target_details: bool = True) -> AuditContext:
    cfg, default_config_created = app.load_config(app.CONFIG_PATH)
    analyzed_targets = list(cfg.get("analyzed_programs_and_libraries", []))
    extra_target_name = _scan_extra_target_name(cfg)
    enabled_analyzer_keys = [spec.key for spec in app._get_enabled_analyzers()]
    variable_analysis_keys = sorted(app.VARIABLE_ANALYSES)

    if not analyzed_targets:
        return _base_audit_context(
            cfg=cfg,
            default_config_created=default_config_created,
            analyzed_targets=analyzed_targets,
            extra_target_name=extra_target_name,
            enabled_analyzer_keys=enabled_analyzer_keys,
            variable_analysis_keys=variable_analysis_keys,
            targets_loaded=False,
        )

    if not include_target_details:
        return _base_audit_context(
            cfg=cfg,
            default_config_created=default_config_created,
            analyzed_targets=analyzed_targets,
            extra_target_name=extra_target_name,
            enabled_analyzer_keys=enabled_analyzer_keys,
            variable_analysis_keys=variable_analysis_keys,
            targets_loaded=True,
        )

    try:
        target_name, base_picture, graph = next(app._iter_loaded_projects(cfg))
    except StopIteration:
        return _base_audit_context(
            cfg=cfg,
            default_config_created=default_config_created,
            analyzed_targets=analyzed_targets,
            extra_target_name=extra_target_name,
            enabled_analyzer_keys=enabled_analyzer_keys,
            variable_analysis_keys=variable_analysis_keys,
            targets_loaded=False,
        )
    except Exception as exc:
        return _base_audit_context(
            cfg=cfg,
            default_config_created=default_config_created,
            analyzed_targets=analyzed_targets,
            extra_target_name=extra_target_name,
            enabled_analyzer_keys=enabled_analyzer_keys,
            variable_analysis_keys=variable_analysis_keys,
            targets_loaded=False,
            load_error=str(exc),
        )

    module_with_localvar = _find_module_with_localvar(base_picture)
    module_path = ".".join(module_with_localvar[0][1:]) if module_with_localvar is not None else None
    module_local_var = module_with_localvar[1] if module_with_localvar is not None else None
    variable_name = _pick_any_variable_name(base_picture, graph) or module_local_var
    module_name = _pick_any_module_name(base_picture)
    documentation_instance_path, documentation_moduletype_name = _build_documentation_context(cfg, base_picture, graph)
    graphics_relative_module_path, graphics_selector_has_options = _build_graphics_context(cfg)

    return AuditContext(
        config_path=app.CONFIG_PATH,
        graphics_rules_path=app.get_graphics_rules_path(),
        cfg=cfg,
        default_config_created=default_config_created,
        analyzed_targets=analyzed_targets,
        extra_target_name=extra_target_name,
        enabled_analyzer_keys=enabled_analyzer_keys,
        variable_analysis_keys=variable_analysis_keys,
        targets_loaded=True,
        target_context=TargetContext(
            target_name=target_name,
            variable_name=variable_name,
            module_name=module_name,
            module_path=module_path,
            module_local_var=module_local_var,
            documentation_instance_path=documentation_instance_path,
            documentation_moduletype_name=documentation_moduletype_name,
            graphics_relative_module_path=graphics_relative_module_path,
            graphics_selector_has_options=graphics_selector_has_options,
        ),
    )


@contextmanager
def patched_menu_io(inputs: Sequence[str], output: StringIO) -> Iterator[None]:
    original_input = builtins.input
    original_clear_screen = app.clear_screen
    original_pause = app.pause
    original_live_status_line = console_module.live_status_line
    builtins.input = _make_input(inputs)
    app.clear_screen = lambda: None
    app.pause = lambda: None
    console_module.live_status_line = lambda: _StatusCapture(output)
    try:
        yield
    finally:
        builtins.input = original_input
        app.clear_screen = original_clear_screen
        app.pause = original_pause
        console_module.live_status_line = original_live_status_line


def _snapshot_watch_paths(paths: Sequence[Path]) -> dict[Path, tuple[bool, int | None, int | None]]:
    snapshot: dict[Path, tuple[bool, int | None, int | None]] = {}
    for path in paths:
        if path.exists():
            stat = path.stat()
            snapshot[path] = (True, stat.st_mtime_ns, stat.st_size)
        else:
            snapshot[path] = (False, None, None)
    return snapshot


def _diff_watch_paths(before: dict[Path, tuple[bool, int | None, int | None]]) -> list[WatchedPathResult]:
    results: list[WatchedPathResult] = []
    for path, previous in before.items():
        existed_before, mtime_before, size_before = previous
        exists_after = path.exists()
        changed = existed_before != exists_after
        if exists_after:
            stat = path.stat()
            if not changed:
                changed = stat.st_mtime_ns != mtime_before or stat.st_size != size_before
        results.append(
            WatchedPathResult(
                path=_display_path(path),
                existed_before=existed_before,
                exists_after=exists_after,
                changed=changed,
            )
        )
    return results


def _blocked(name: str, description: str, reason: str) -> ScenarioSpec:
    return ScenarioSpec(name=name, description=description, runner=lambda _cfg: 0, inputs=[], blocked_reason=reason)


def _run_with_debug(cfg: dict[str, Any], action: Callable[[dict[str, Any]], int | None]) -> int | None:
    cfg["debug"] = True
    app.apply_debug(cfg)
    return action(cfg)


def _limit_to_first_target_if_needed(spec_name: str, cfg: dict[str, Any]) -> None:
    if not spec_name.startswith(
        (
            "documentation.",
            "tools.",
            "dump.",
            "analysis.",
            "variables.",
            "modules.",
            "interfaces.",
            "code-quality.",
            "catalog.",
            "advanced.",
        )
    ):
        return
    analyzed_targets = list(cfg.get("analyzed_programs_and_libraries", []))
    if analyzed_targets:
        cfg["analyzed_programs_and_libraries"] = analyzed_targets[:1]


def _graphics_add_inputs(context: AuditContext) -> list[str] | None:
    target_context = context.target_context
    if target_context is None or target_context.graphics_relative_module_path is None:
        return None
    selector_inputs = (
        ["1"] if target_context.graphics_selector_has_options else [target_context.graphics_relative_module_path]
    )
    return [
        "1",
        "1",
        *selector_inputs,
        "CLI audit rule",
        "1,2,3,4,5",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "b",
    ]


def _scenario_needs_target_details(name: str) -> bool:
    return name in {
        "graphics.add-rule",
        "graphics.remove-rule",
        "graphics.save-rules",
        "variables.datatype-usage",
        "variables.debug-usage",
        "variables.module-localvar",
        "modules.compare-variants",
        "modules.find-instances",
        "advanced.datatype-usage",
        "advanced.variable-trace",
        "advanced.module-localvar",
    }


def build_scenarios(context: AuditContext, *, output_dir: Path) -> list[ScenarioSpec]:
    scenarios: list[ScenarioSpec] = [
        ScenarioSpec(
            "startup.help",
            "Launch app.main([--debug]) and route through Help.",
            lambda _cfg: app.main(["--debug"]),
            ["5", "q"],
        ),
        ScenarioSpec(
            "startup.tools-route",
            "Launch app.main([--debug]) and route through Tools.",
            lambda _cfg: app.main(["--debug"]),
            ["4", "b", "q"],
        ),
        ScenarioSpec(
            "setup.route",
            "Open Setup from the startup path and return.",
            lambda _cfg: app.main(["--debug"]),
            ["3", "b", "q"],
        ),
    ]

    if context.targets_loaded:
        scenarios.extend(
            [
                ScenarioSpec(
                    "startup.analyze-route",
                    "Open Analyze from the startup path and return.",
                    lambda _cfg: app.main(["--debug"]),
                    ["1", "b", "q"],
                ),
                ScenarioSpec(
                    "startup.documentation-route",
                    "Open Documentation from the startup path and return.",
                    lambda _cfg: app.main(["--debug"]),
                    ["2", "b", "q"],
                ),
            ]
        )
    else:
        scenarios.extend(
            [
                _blocked(
                    "startup.analyze-route",
                    "Open Analyze from the startup path and return.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "startup.documentation-route",
                    "Open Documentation from the startup path and return.",
                    "No analyzed targets are configured or loadable.",
                ),
            ]
        )

    same_program_dir = str(context.cfg.get("program_dir") or "")
    same_abb_dir = str(context.cfg.get("ABB_lib_dir") or "")
    same_icf_dir = str(context.cfg.get("icf_dir") or "")
    other_lib_dir = str((context.cfg.get("other_lib_dirs") or [same_program_dir or same_abb_dir or str(REPO_ROOT)])[0])

    if context.extra_target_name is not None:
        scenarios.append(
            ScenarioSpec(
                "setup.add-target",
                "Run Setup option 1 Add analysis target.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["1", context.extra_target_name, "y", "b"],
            )
        )
    else:
        scenarios.append(
            _blocked(
                "setup.add-target",
                "Run Setup option 1 Add analysis target.",
                "No extra target was discovered in the configured directories.",
            )
        )

    if context.analyzed_targets:
        scenarios.append(
            ScenarioSpec(
                "setup.remove-target",
                "Run Setup option 2 Remove analysis target.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["2", "1", "y", "b"],
            )
        )
    else:
        scenarios.append(
            _blocked(
                "setup.remove-target",
                "Run Setup option 2 Remove analysis target.",
                "No analyzed targets are configured.",
            )
        )

    scenarios.extend(
        [
            ScenarioSpec(
                "setup.toggle-mode",
                "Run Setup option 3 Toggle mode.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["3", "y", "b"],
            ),
            ScenarioSpec(
                "setup.toggle-scan-root-only",
                "Run Setup option 4 Toggle scan_root_only.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["4", "y", "b"],
            ),
            ScenarioSpec(
                "setup.toggle-fast-cache-validation",
                "Run Setup option 5 Toggle fast_cache_validation.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["5", "y", "b"],
            ),
            ScenarioSpec(
                "setup.change-program-dir",
                "Run Setup option 6 Change program_dir.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["6", same_program_dir, "y", "b"],
            ),
            ScenarioSpec(
                "setup.change-abb-lib-dir",
                "Run Setup option 7 Change ABB_lib_dir.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["7", same_abb_dir, "y", "b"],
            ),
            ScenarioSpec(
                "setup.edit-other-lib-dirs",
                "Run Setup option 8 Edit other_lib_dirs via add flow.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["8", "y", other_lib_dir, "b"],
            ),
            ScenarioSpec(
                "setup.save-config",
                "Run Setup option 9 Save configuration.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["9", "y", "b"],
                watch_paths=(context.config_path,),
            ),
            ScenarioSpec(
                "setup.change-icf-dir",
                "Run Setup option 10 Change icf_dir.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["10", same_icf_dir, "y", "b"],
            ),
            ScenarioSpec(
                "setup.toggle-debug",
                "Run Setup option 11 Toggle debug.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["11", "y", "b"],
            ),
            ScenarioSpec(
                "setup.toggle-telemetry",
                "Run Setup option 12 Toggle telemetry.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["12", "y", "b"],
            ),
            ScenarioSpec(
                "setup.graphics-route",
                "Run Setup option 13 and return from Graphics rules.",
                lambda cfg: _run_with_debug(cfg, app.config_menu),
                ["13", "b", "b"],
            ),
        ]
    )

    graphics_add_inputs = _graphics_add_inputs(context)
    if graphics_add_inputs is None:
        scenarios.extend(
            [
                _blocked(
                    "graphics.add-rule",
                    "Run Graphics rules option 1 Add or replace rule.",
                    "No usable graphics selector value could be discovered.",
                ),
                _blocked(
                    "graphics.remove-rule",
                    "Run Graphics rules option 2 Remove rule.",
                    "No usable graphics selector value could be discovered.",
                ),
                _blocked(
                    "graphics.save-rules",
                    "Run Graphics rules option 3 Save rules.",
                    "No usable graphics selector value could be discovered.",
                ),
            ]
        )
    else:
        scenarios.extend(
            [
                ScenarioSpec(
                    "graphics.add-rule",
                    "Run Graphics rules option 1 Add or replace rule.",
                    lambda cfg: _run_with_debug(cfg, app.graphics_rules_menu),
                    graphics_add_inputs,
                ),
                ScenarioSpec(
                    "graphics.remove-rule",
                    "Run Graphics rules option 2 Remove rule after adding one.",
                    lambda cfg: _run_with_debug(cfg, app.graphics_rules_menu),
                    [*graphics_add_inputs[:-1], "2", "1", "b"],
                ),
                ScenarioSpec(
                    "graphics.save-rules",
                    "Run Graphics rules option 3 Save rules after adding one.",
                    lambda cfg: _run_with_debug(cfg, app.graphics_rules_menu),
                    [*graphics_add_inputs[:-1], "3", "b"],
                    watch_paths=(context.graphics_rules_path,),
                ),
            ]
        )

    if not context.targets_loaded:
        scenarios.extend(
            [
                _blocked(
                    "documentation.generate",
                    "Run Documentation option 1 Generate documentation.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "documentation.preview",
                    "Run Documentation option 2 Preview unit candidates.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "documentation.reset-scope",
                    "Run Documentation option 3 Use all detected units.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "documentation.scope-by-moduletype",
                    "Run Documentation option 4 Scope by moduletype.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "documentation.scope-by-instance-path",
                    "Run Documentation option 5 Scope by instance path.",
                    "No analyzed targets are configured or loadable.",
                ),
            ]
        )
    else:
        target_context = context.target_context
        doc_outputs = [str((output_dir / f"{target}_FS.docx").resolve()) for target in context.analyzed_targets]
        scenarios.extend(
            [
                ScenarioSpec(
                    "documentation.generate",
                    "Run Documentation option 1 Generate documentation.",
                    lambda cfg: _run_with_debug(cfg, app.documentation_menu),
                    ["1", *doc_outputs, "b"],
                    watch_paths=tuple(Path(path) for path in doc_outputs),
                ),
                ScenarioSpec(
                    "documentation.preview",
                    "Run Documentation option 2 Preview unit candidates.",
                    lambda cfg: _run_with_debug(cfg, app.documentation_menu),
                    ["2", "b"],
                ),
                ScenarioSpec(
                    "documentation.reset-scope",
                    "Run Documentation option 3 Use all detected units.",
                    lambda cfg: _run_with_debug(cfg, app.documentation_menu),
                    ["3", "b"],
                ),
                ScenarioSpec(
                    "documentation.scope-by-moduletype",
                    "Run Documentation option 4 Scope by moduletype.",
                    lambda cfg: _run_with_debug(cfg, app.documentation_menu),
                    [
                        "4",
                        (target_context.documentation_moduletype_name if target_context else None) or "ApplTank",
                        "b",
                    ],
                ),
                ScenarioSpec(
                    "documentation.scope-by-instance-path",
                    "Run Documentation option 5 Scope by instance path.",
                    lambda cfg: _run_with_debug(cfg, app.documentation_menu),
                    ["5", (target_context.documentation_instance_path if target_context else None) or "UnitA", "b"],
                ),
            ]
        )

    scenarios.extend(
        [
            ScenarioSpec(
                "tools.self-check",
                "Run Tools option 1 Self-check diagnostics.",
                lambda cfg: _run_with_debug(cfg, app.tools_menu),
                ["1", "b"],
            ),
            ScenarioSpec(
                "tools.dump-route",
                "Run Tools option 2 Diagnostics and dumps route.",
                lambda cfg: _run_with_debug(cfg, app.tools_menu),
                ["2", "b", "b"],
            ),
            ScenarioSpec(
                "tools.source-diff",
                "Run Tools option 3 Source diff report.",
                lambda cfg: _run_with_debug(cfg, app.tools_menu),
                ["3", "b"],
            ),
            ScenarioSpec(
                "tools.refresh-ast",
                "Run Tools option 4 Refresh cached ASTs.",
                lambda cfg: _run_with_debug(cfg, app.tools_menu),
                ["4", "y", "b"],
            ),
        ]
    )

    for name, description, inputs in [
        ("dump.parse-tree", "Run Diagnostics and dumps option 1 Dump parse tree.", ["1", "y", "b"]),
        ("dump.ast", "Run Diagnostics and dumps option 2 Dump AST.", ["2", "y", "b"]),
        ("dump.dependency-graph", "Run Diagnostics and dumps option 3 Dump dependency graph.", ["3", "y", "b"]),
        ("dump.variable-report", "Run Diagnostics and dumps option 4 Print variable report.", ["4", "y", "b"]),
    ]:
        if context.targets_loaded:
            scenarios.append(ScenarioSpec(name, description, lambda cfg: _run_with_debug(cfg, app.dump_menu), inputs))
        else:
            scenarios.append(_blocked(name, description, "No analyzed targets are configured or loadable."))

    if not context.targets_loaded:
        scenarios.extend(
            [
                _blocked(
                    "analysis.full-suite",
                    "Run Analyze option 1 Full analyzer suite.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "analysis.variable-route",
                    "Run Analyze option 2 Variable issues route.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "analysis.module-route",
                    "Run Analyze option 3 Structure and modules route.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "analysis.interface-route",
                    "Run Analyze option 4 Interfaces and communication route.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "analysis.code-quality-route",
                    "Run Analyze option 5 Code quality route.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "analysis.catalog-route",
                    "Run Analyze option 6 Analyzer catalog route.",
                    "No analyzed targets are configured or loadable.",
                ),
                _blocked(
                    "analysis.advanced-route",
                    "Run Analyze option 7 Advanced analysis and debug route.",
                    "No analyzed targets are configured or loadable.",
                ),
            ]
        )
    else:
        target_context = context.target_context
        scenarios.extend(
            [
                ScenarioSpec(
                    "analysis.full-suite",
                    "Run Analyze option 1 Full analyzer suite.",
                    lambda cfg: _run_with_debug(cfg, app.analysis_menu),
                    ["1", "b"],
                ),
                ScenarioSpec(
                    "analysis.variable-route",
                    "Run Analyze option 2 Variable issues route.",
                    lambda cfg: _run_with_debug(cfg, app.analysis_menu),
                    ["2", "b", "b"],
                ),
                ScenarioSpec(
                    "analysis.module-route",
                    "Run Analyze option 3 Structure and modules route.",
                    lambda cfg: _run_with_debug(cfg, app.analysis_menu),
                    ["3", "b", "b"],
                ),
                ScenarioSpec(
                    "analysis.interface-route",
                    "Run Analyze option 4 Interfaces and communication route.",
                    lambda cfg: _run_with_debug(cfg, app.analysis_menu),
                    ["4", "b", "b"],
                ),
                ScenarioSpec(
                    "analysis.code-quality-route",
                    "Run Analyze option 5 Code quality route.",
                    lambda cfg: _run_with_debug(cfg, app.analysis_menu),
                    ["5", "b", "b"],
                ),
                ScenarioSpec(
                    "analysis.catalog-route",
                    "Run Analyze option 6 Analyzer catalog route.",
                    lambda cfg: _run_with_debug(cfg, app.analysis_menu),
                    ["6", "b", "b"],
                ),
                ScenarioSpec(
                    "analysis.advanced-route",
                    "Run Analyze option 7 Advanced analysis and debug route.",
                    lambda cfg: _run_with_debug(cfg, app.analysis_menu),
                    ["7", "b", "b"],
                ),
            ]
        )
        for key in context.variable_analysis_keys:
            label, _kinds = app.VARIABLE_ANALYSES[key]
            scenarios.append(
                ScenarioSpec(
                    f"variables.{key}",
                    f"Run Variable issues option {key} {label}.",
                    lambda cfg: _run_with_debug(cfg, app.variable_usage_submenu),
                    [key, "b"],
                )
            )
        scenarios.extend(
            [
                ScenarioSpec(
                    "variables.datatype-usage",
                    "Run Variable issues option 23 Datatype usage analysis.",
                    lambda cfg: _run_with_debug(cfg, app.variable_usage_submenu),
                    ["23", (target_context.variable_name if target_context else None) or "Dv", "b"],
                    blocked_reason=None
                    if target_context and target_context.variable_name
                    else "No live variable name was discovered from the loaded target.",
                ),
                ScenarioSpec(
                    "variables.debug-usage",
                    "Run Variable issues option 24 Variable usage trace.",
                    lambda cfg: _run_with_debug(cfg, app.variable_usage_submenu),
                    ["24", (target_context.variable_name if target_context else None) or "Dv", "b"],
                    blocked_reason=None
                    if target_context and target_context.variable_name
                    else "No live variable name was discovered from the loaded target.",
                ),
                ScenarioSpec(
                    "variables.module-localvar",
                    "Run Variable issues option 25 Module local variable analysis.",
                    lambda cfg: _run_with_debug(cfg, app.variable_usage_submenu),
                    [
                        "25",
                        (target_context.module_path if target_context else None) or "",
                        (target_context.module_local_var if target_context else None) or "Dv",
                        "b",
                    ],
                    blocked_reason=None
                    if target_context and target_context.module_path and target_context.module_local_var
                    else "No live module local-variable context was discovered.",
                ),
                ScenarioSpec(
                    "modules.compare-variants",
                    "Run Structure and modules option 1 Compare module variants.",
                    lambda cfg: _run_with_debug(cfg, app.module_analysis_submenu),
                    ["1", (target_context.module_name if target_context else None) or "", "", "b"],
                    blocked_reason=None
                    if target_context and target_context.module_name
                    else "No module name was discovered from the loaded target.",
                ),
                ScenarioSpec(
                    "modules.find-instances",
                    "Run Structure and modules option 2 Find module instances.",
                    lambda cfg: _run_with_debug(cfg, app.module_analysis_submenu),
                    ["2", (target_context.module_name if target_context else None) or "", "b"],
                    blocked_reason=None
                    if target_context and target_context.module_name
                    else "No module name was discovered from the loaded target.",
                ),
                ScenarioSpec(
                    "modules.inspect-tree",
                    "Run Structure and modules option 3 Inspect module tree.",
                    lambda cfg: _run_with_debug(cfg, app.module_analysis_submenu),
                    ["3", "3", "b"],
                ),
                ScenarioSpec(
                    "modules.validate-graphics-rules",
                    "Run Structure and modules option 4 Validate graphics rules.",
                    lambda cfg: _run_with_debug(cfg, app.module_analysis_submenu),
                    ["4", "b"],
                ),
                ScenarioSpec(
                    "interfaces.mms-variables",
                    "Run Interfaces and communication option 1 MMS interface variables.",
                    lambda cfg: _run_with_debug(cfg, app.interface_communication_submenu),
                    ["1", "b"],
                ),
                ScenarioSpec(
                    "interfaces.validate-icf",
                    "Run Interfaces and communication option 2 Validate ICF paths.",
                    lambda cfg: _run_with_debug(cfg, app.interface_communication_submenu),
                    ["2", "b"],
                ),
                ScenarioSpec(
                    "interfaces.format-icf",
                    "Run Interfaces and communication option 3 Format ICF files.",
                    lambda cfg: _run_with_debug(cfg, app.interface_communication_submenu),
                    ["3", "b"],
                ),
                ScenarioSpec(
                    "code-quality.comment-code",
                    "Run Code quality option 1 Commented-out code.",
                    lambda cfg: _run_with_debug(cfg, app.code_quality_submenu),
                    ["1", "b"],
                ),
                ScenarioSpec(
                    "catalog.full-suite",
                    "Run Analyzer catalog option 1 Full analyzer suite.",
                    lambda cfg: _run_with_debug(cfg, app.analyzer_catalog_menu),
                    ["1", "b"],
                ),
            ]
        )
        for index, key in enumerate(context.enabled_analyzer_keys, start=2):
            scenarios.append(
                ScenarioSpec(
                    f"catalog.{key}",
                    f"Run Analyzer catalog option {index} for analyzer {key}.",
                    lambda cfg: _run_with_debug(cfg, app.analyzer_catalog_menu),
                    [str(index), "b"],
                )
            )
        scenarios.extend(
            [
                ScenarioSpec(
                    "advanced.datatype-usage",
                    "Run Advanced analysis and debug option 1 Datatype usage analysis.",
                    lambda cfg: _run_with_debug(cfg, app.advanced_analysis_menu),
                    ["1", (target_context.variable_name if target_context else None) or "Dv", "b"],
                    blocked_reason=None
                    if target_context and target_context.variable_name
                    else "No live variable name was discovered from the loaded target.",
                ),
                ScenarioSpec(
                    "advanced.variable-trace",
                    "Run Advanced analysis and debug option 2 Variable usage trace.",
                    lambda cfg: _run_with_debug(cfg, app.advanced_analysis_menu),
                    ["2", (target_context.variable_name if target_context else None) or "Dv", "b"],
                    blocked_reason=None
                    if target_context and target_context.variable_name
                    else "No live variable name was discovered from the loaded target.",
                ),
                ScenarioSpec(
                    "advanced.module-localvar",
                    "Run Advanced analysis and debug option 3 Module local variable analysis.",
                    lambda cfg: _run_with_debug(cfg, app.advanced_analysis_menu),
                    [
                        "3",
                        (target_context.module_path if target_context else None) or "",
                        (target_context.module_local_var if target_context else None) or "Dv",
                        "b",
                    ],
                    blocked_reason=None
                    if target_context and target_context.module_path and target_context.module_local_var
                    else "No live module local-variable context was discovered.",
                ),
            ]
        )

    return scenarios


def run_scenario(
    spec: ScenarioSpec, context: AuditContext, *, output_dir: Path, timeout_seconds: int
) -> ScenarioResult:
    scenario_dir = output_dir / _normalize_name(spec.name)
    scenario_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = scenario_dir / "stdout.txt"
    stderr_path = scenario_dir / "stderr.txt"
    inputs_path = scenario_dir / "inputs.json"
    _write_text(inputs_path, json.dumps(spec.inputs, indent=2) + "\n")

    if spec.blocked_reason is not None:
        _write_text(stdout_path, "")
        _write_text(stderr_path, "")
        return ScenarioResult(
            name=spec.name,
            description=spec.description,
            status="blocked",
            stdout_path=_display_path(stdout_path),
            stderr_path=_display_path(stderr_path),
            inputs_path=_display_path(inputs_path),
            blocked_reason=spec.blocked_reason,
        )

    cfg_copy = copy.deepcopy(context.cfg)
    _limit_to_first_target_if_needed(spec.name, cfg_copy)
    stdout_buffer = StringIO()
    stderr_buffer = StringIO()
    watch_snapshot = _snapshot_watch_paths(spec.watch_paths)
    try:
        with (
            _time_limit(timeout_seconds),
            patched_menu_io(spec.inputs, stdout_buffer),
            redirect_stdout(stdout_buffer),
            redirect_stderr(stderr_buffer),
        ):
            exit_code = spec.runner(cfg_copy)
        status = "passed"
        error = None
    except Exception as exc:
        exit_code = None
        status = "failed"
        error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        traceback.print_exc(file=stderr_buffer)

    _write_text(stdout_path, stdout_buffer.getvalue())
    _write_text(stderr_path, stderr_buffer.getvalue())
    return ScenarioResult(
        name=spec.name,
        description=spec.description,
        status=status,
        stdout_path=_display_path(stdout_path),
        stderr_path=_display_path(stderr_path),
        inputs_path=_display_path(inputs_path),
        error=error,
        exit_code=exit_code,
        watched_paths=_diff_watch_paths(watch_snapshot),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drive the interactive SattLint menu tree and capture transcripts.")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "artifacts" / "tmp" / "cli-menu-audit"),
        help="Directory for transcripts and summary JSON.",
    )
    parser.add_argument("--scenario", action="append", default=[], help="Run only the named scenario. Repeatable.")
    parser.add_argument(
        "--scenario-timeout", type=int, default=30, help="Per-scenario timeout in seconds. Use 0 to disable."
    )
    parser.add_argument("--list-scenarios", action="store_true", help="Print scenario names and exit.")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    context = load_audit_context(include_target_details=False)

    scenarios = build_scenarios(context, output_dir=output_dir)
    scenarios_by_name = {scenario.name: scenario for scenario in scenarios}

    if args.list_scenarios:
        for scenario in scenarios:
            print(scenario.name)
        return 0

    selected_names = list(args.scenario)
    if selected_names:
        missing = [name for name in selected_names if name not in scenarios_by_name]
        if missing:
            print("Unknown scenarios: " + ", ".join(sorted(missing)), file=sys.stderr)
            return 2
        selected = [scenarios_by_name[name] for name in selected_names]
    else:
        selected = scenarios

    results = [
        run_scenario(spec, context, output_dir=output_dir, timeout_seconds=args.scenario_timeout) for spec in selected
    ]
    summary = {
        "context": {
            "config_path": str(context.config_path),
            "graphics_rules_path": str(context.graphics_rules_path),
            "default_config_created": context.default_config_created,
            "analyzed_targets": context.analyzed_targets,
            "extra_target_name": context.extra_target_name,
            "enabled_analyzer_keys": context.enabled_analyzer_keys,
            "variable_analysis_keys": context.variable_analysis_keys,
            "targets_loaded": context.targets_loaded,
            "load_error": context.load_error,
            "target_context": asdict(context.target_context) if context.target_context is not None else None,
        },
        "results": [asdict(result) for result in results],
    }
    summary_path = output_dir / "summary.json"
    _write_text(summary_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")

    passed = sum(1 for result in results if result.status == "passed")
    blocked = sum(1 for result in results if result.status == "blocked")
    failed = sum(1 for result in results if result.status == "failed")
    print(f"cli-menu-audit: passed={passed} blocked={blocked} failed={failed}")
    print(f"cli-menu-audit: summary={_display_path(summary_path)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
