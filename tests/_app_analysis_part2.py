# ruff: noqa: F403, F405
from ._app_analysis_test_support import *


def test_run_module_duplicates_analysis_rejects_empty_name(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "   ")
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis.run_module_duplicates_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=lambda *_args, **_kwargs: pytest.fail("should not load projects"),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No module name provided" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_duplicates_analysis_uses_selected_instances(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []
    matches = [
        (["Root", "Area", "PumpA"], SimpleNamespace(datecode=101)),
        (["Root", "Area", "PumpB"], SimpleNamespace(datecode=None)),
        (["Root", "Area", "PumpC"], SimpleNamespace(datecode=303)),
    ]
    captured: dict[str, object] = {}

    monkeypatch.setattr(builtins, "input", make_input(["Pump", "1, 3-2"]))
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "find_modules_by_name", lambda *_args, **_kwargs: matches)
    monkeypatch.setattr(
        app_analysis,
        "compare_modules",
        lambda selected: (
            captured.update({"selected": selected}) or SimpleNamespace(summary=lambda: "comparison summary")
        ),
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_module_duplicates",
        lambda *_args, **_kwargs: pytest.fail("should use explicit comparison path"),
    )

    app_analysis.run_module_duplicates_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert captured["selected"] == matches
    assert any("Found 3 instance(s) for 'Pump':" in line for line in lines)
    assert any("comparison summary" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_duplicates_analysis_requires_two_selected_instances(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []
    matches = [
        (["Root", "PumpA"], SimpleNamespace(datecode=101)),
        (["Root", "PumpB"], SimpleNamespace(datecode=202)),
    ]

    monkeypatch.setattr(builtins, "input", make_input(["Pump", "1"]))
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "find_modules_by_name", lambda *_args, **_kwargs: matches)
    monkeypatch.setattr(
        app_analysis,
        "compare_modules",
        lambda *_args, **_kwargs: pytest.fail("should skip compare when fewer than two indices are selected"),
    )

    app_analysis.run_module_duplicates_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Need at least two instances to compare; skipping." in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_find_by_name_lists_matches_and_reports_errors(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    def fake_find_modules(_project_bp, module_name, debug=False):
        if module_name == "Pump":
            return [(["Root", "PumpA"], SimpleNamespace(datecode=101))]
        if module_name == "Missing":
            return []
        raise RuntimeError("boom")

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "Pump, Missing, Boom")
    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "find_modules_by_name", fake_find_modules)

    app_analysis.run_module_find_by_name(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Found 1 module instance(s) for 'Pump':" in line for line in lines)
    assert any("No modules found with name 'Missing'." in line for line in lines)
    assert any("Error during search: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_module_find_by_name_updates_live_status(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(builtins, "input", lambda _prompt="": "Pump")
    monkeypatch.setattr(app_analysis, "emit_output", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(app_analysis.console_module, "live_status_line", lambda: FakeLiveStatusLine())
    monkeypatch.setattr(
        app_analysis,
        "find_modules_by_name",
        lambda *_args, **_kwargs: [(["Root", "PumpA"], SimpleNamespace(datecode=101))],
    )

    app_analysis.run_module_find_by_name(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=None,
    )

    assert updates == ["Finding module instances in TargetA: Pump"]


def test_run_module_tree_debug_uses_default_depth_on_invalid_input(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []
    captured: dict[str, object] = {}

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(
        app_analysis,
        "debug_module_structure",
        lambda project_bp, max_depth=0: captured.update({"project_bp": project_bp, "max_depth": max_depth}),
    )

    app_analysis.run_module_tree_debug(
        app.DEFAULT_CONFIG.copy(),
        prompt_fn=lambda _message, _default: "not-a-number",
        iter_loaded_projects_fn=cast(Any, lambda *_args, **_kwargs: iter([("TargetA", "bp", SimpleNamespace())])),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert captured == {"project_bp": "bp", "max_depth": 10}
    assert any("Invalid depth; using default 10" in line for line in lines)
    assert pauses == ["pause"]


def test_run_checks_reports_no_matching_checks_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy(),
        ["missing-check"],
        get_enabled_analyzers_fn=lambda: [SimpleNamespace(key="variables", name="Variables")],
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("No matching checks found" in line for line in lines)
    assert pauses == ["pause"]


def test_run_checks_runs_selected_non_default_cli_exposed_analyzer(monkeypatch):
    lines: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    class MutableReport:
        def __init__(self) -> None:
            self.name = "BasePicture"

        def summary(self) -> str:
            return f"state inference summary for {self.name}"

    report = MutableReport()

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy(),
        ["state_inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(unavailable_libraries=set()),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state_inference",
                name="State inference",
                run=lambda _context: report,
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert any("State inference (state_inference)" in line for line in lines)
    assert any("state inference summary for TargetA" in line for line in lines)
    assert not any("state inference summary for BasePicture" in line for line in lines)


def test_run_checks_updates_live_status_for_active_analyzer(monkeypatch):
    updates: list[str] = []

    class FakeLiveStatusLine:
        def __enter__(self):
            return updates.append

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(app_analysis, "emit_output", lambda _message: None)
    monkeypatch.setattr(app_analysis.console_module, "live_status_line", lambda: FakeLiveStatusLine())

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy(),
        ["state_inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(unavailable_libraries=set()),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state_inference",
                name="State inference",
                run=lambda _context: SimpleNamespace(summary=lambda: "state inference summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert updates == ["Analyzing TargetA: State inference (state_inference)"]


def test_run_checks_uses_cached_report_when_available(monkeypatch):
    lines: list[str] = []
    run_calls: list[str] = []
    load_keys: list[str] = []
    validate_calls: list[tuple[object, bool]] = []
    save_calls: list[tuple[str, object, frozenset[Path]]] = []

    class MutableReport:
        def __init__(self, name: str) -> None:
            self.name = name
            self.issues: list[object] = []

        def summary(self) -> str:
            return f"state inference summary for {self.name}"

    cached_report = MutableReport("BasePicture")

    class FakeReportCache:
        def __init__(self, cache_dir):
            assert cache_dir == Path("report-cache-dir")

        def load(self, key):
            load_keys.append(key)
            return {"report": cached_report}

        def validate(self, payload, *, fast=False):
            validate_calls.append((payload, fast))
            return True

        def save(self, key, *, report, files):
            save_calls.append((key, report, frozenset(files)))
            return True

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "AnalysisReportCache", FakeReportCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("report-cache-dir"))
    monkeypatch.setattr(
        app_analysis,
        "compute_analysis_report_cache_key",
        lambda project_key, analyzer_key: f"{project_key}:{analyzer_key}",
    )

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy(),
        ["state_inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(
                            unavailable_libraries=set(),
                            analysis_cache_key="project-key",
                            analysis_manifest_files=frozenset({Path("programs/TargetA.s")}),
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state_inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or MutableReport("Live"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert run_calls == []
    assert load_keys == ["project-key:state_inference"]
    assert validate_calls == [({"report": cached_report}, False)]
    assert save_calls == []
    assert any("state inference summary for TargetA" in line for line in lines)


def test_run_checks_rebuilds_report_cache_when_cached_payload_is_stale(monkeypatch):
    lines: list[str] = []
    run_calls: list[str] = []
    load_keys: list[str] = []
    save_calls: list[tuple[str, object, frozenset[Path]]] = []

    class MutableReport:
        def __init__(self, name: str) -> None:
            self.name = name
            self.issues: list[object] = []

        def summary(self) -> str:
            return f"state inference summary for {self.name}"

    class FakeReportCache:
        def __init__(self, cache_dir):
            assert cache_dir == Path("report-cache-dir")

        def load(self, key):
            load_keys.append(key)
            return {"report": MutableReport("Stale")}

        def validate(self, payload, *, fast=False):
            del payload, fast
            return False

        def save(self, key, *, report, files):
            save_calls.append((key, report, frozenset(files)))
            return True

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(app_analysis, "AnalysisReportCache", FakeReportCache)
    monkeypatch.setattr(app_analysis, "get_cache_dir", lambda: Path("report-cache-dir"))
    monkeypatch.setattr(
        app_analysis,
        "compute_analysis_report_cache_key",
        lambda project_key, analyzer_key: f"{project_key}:{analyzer_key}",
    )

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy(),
        ["state_inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(
                            unavailable_libraries=set(),
                            analysis_cache_key="project-key",
                            analysis_manifest_files=frozenset({Path("programs/TargetA.s")}),
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state_inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or MutableReport("Live"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert run_calls == ["run"]
    assert load_keys == ["project-key:state_inference"]
    assert save_calls == [
        (
            "project-key:state_inference",
            save_calls[0][1],
            frozenset({Path("programs/TargetA.s")}),
        )
    ]
    assert any("state inference summary for TargetA" in line for line in lines)


def test_run_checks_bypasses_report_cache_when_use_cache_disabled(monkeypatch):
    run_calls: list[str] = []

    class ForbiddenReportCache:
        def __init__(self, _cache_dir):
            pytest.fail("report cache should be bypassed when use_cache is false")

    monkeypatch.setattr(app_analysis, "AnalysisReportCache", ForbiddenReportCache)

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy() | {"use_cache": False},
        ["state_inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(
                            unavailable_libraries=set(),
                            analysis_cache_key="project-key",
                            analysis_manifest_files=frozenset({Path("programs/TargetA.s")}),
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state_inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert run_calls == ["run"]


def test_run_checks_bypasses_report_cache_when_debug_enabled(monkeypatch):
    run_calls: list[str] = []

    class ForbiddenReportCache:
        def __init__(self, _cache_dir):
            pytest.fail("report cache should be bypassed when debug is true")

    monkeypatch.setattr(app_analysis, "AnalysisReportCache", ForbiddenReportCache)

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy() | {"debug": True},
        ["state_inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(
                            unavailable_libraries=set(),
                            analysis_cache_key="project-key",
                            analysis_manifest_files=frozenset({Path("programs/TargetA.s")}),
                        ),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state_inference",
                name="State inference",
                run=lambda _context: run_calls.append("run") or SimpleNamespace(issues=[], summary=lambda: "summary"),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=None,
    )

    assert run_calls == ["run"]


def test_run_checks_handles_keyboard_interrupt_and_pauses(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis.run_checks(
        app.DEFAULT_CONFIG.copy(),
        ["state_inference"],
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    (
                        "TargetA",
                        SimpleNamespace(header=SimpleNamespace(name="TargetA")),
                        SimpleNamespace(unavailable_libraries=set()),
                    )
                ]
            ),
        ),
        get_enabled_analyzers_fn=lambda: [
            SimpleNamespace(
                key="state_inference",
                name="State inference",
                run=lambda _context: (_ for _ in ()).throw(KeyboardInterrupt()),
            )
        ],
        target_is_library_fn=lambda *_args, **_kwargs: False,
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Operation canceled. Returning to the menu." in line for line in lines)
    assert pauses == ["pause"]


def test_run_icf_validation_covers_missing_dir_invalid_dir_and_empty_file_list(monkeypatch, tmp_path):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    app_analysis.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (None, []),
        load_program_ast_fn=lambda *_args, **_kwargs: pytest.fail("should not load program"),
        pause_fn=lambda: pauses.append("pause-none"),
    )

    missing_dir = tmp_path / "missing-icf"
    app_analysis.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (missing_dir, [missing_dir / "ProgramA.icf"]),
        load_program_ast_fn=lambda *_args, **_kwargs: pytest.fail("should not load program"),
        pause_fn=lambda: pauses.append("pause-missing"),
    )

    valid_dir = tmp_path / "icf"
    valid_dir.mkdir()
    app_analysis.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (valid_dir, []),
        load_program_ast_fn=lambda *_args, **_kwargs: pytest.fail("should not load program"),
        pause_fn=lambda: pauses.append("pause-empty"),
    )

    assert any("icf_dir is not set in the config" in line for line in lines)
    assert any(f"icf_dir does not exist or is not a directory: {missing_dir}" in line for line in lines)
    assert any(f"No .icf files found in {valid_dir}" in line for line in lines)
    assert pauses == ["pause-none", "pause-missing", "pause-empty"]


def test_run_module_localvar_analysis_rejects_empty_module_path_and_variable(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["", "UnitA", ""]))

    def load_project_fn(_cfg):
        return (SimpleNamespace(header=SimpleNamespace(name="BasePicture")), SimpleNamespace())

    app_analysis.run_module_localvar_analysis(
        app.DEFAULT_CONFIG.copy(),
        load_project_fn=cast(Any, load_project_fn),
        pause_fn=lambda: pauses.append("pause-module"),
    )
    app_analysis.run_module_localvar_analysis(
        app.DEFAULT_CONFIG.copy(),
        load_project_fn=cast(Any, load_project_fn),
        pause_fn=lambda: pauses.append("pause-var"),
    )

    assert any("No module path provided" in line for line in lines)
    assert any("No variable name provided" in line for line in lines)
    assert pauses == ["pause-module", "pause-var"]


def test_run_module_localvar_analysis_reports_success_and_errors(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["UnitA", "Dv"]))

    reporting_module = pytest.importorskip("sattlint.analyzers.variable_usage_reporting")
    monkeypatch.setattr(reporting_module, "analyze_module_localvar_fields", lambda *_args, **_kwargs: "field report")

    app_analysis.run_module_localvar_analysis(
        app.DEFAULT_CONFIG.copy(),
        load_project_fn=cast(
            Any,
            lambda _cfg: (SimpleNamespace(header=SimpleNamespace(name="BasePicture")), SimpleNamespace()),
        ),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    ("TargetA", "bp-a", SimpleNamespace()),
                    ("TargetB", "bp-b", SimpleNamespace()),
                ]
            ),
        ),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("=== Target: TargetA ===" in line for line in lines)
    assert any("field report" in line for line in lines)
    assert pauses == ["pause"]


def test_menu_wrappers_delegate_to_underlying_callbacks():
    calls: list[tuple[str, object]] = []

    app_analysis.run_analysis_menu(app.DEFAULT_CONFIG.copy(), analysis_menu_fn=lambda cfg: calls.append(("run", cfg)))
    app_analysis.variable_analysis_menu(
        app.DEFAULT_CONFIG.copy(), analysis_menu_fn=lambda cfg: calls.append(("var", cfg))
    )
    app_analysis.run_checks_menu(
        app.DEFAULT_CONFIG.copy(),
        run_checks_fn=lambda cfg, selected: calls.append(("checks", selected if selected is not None else cfg)),
    )

    assert calls[0][0] == "run"
    assert calls[1][0] == "var"
    assert calls[2] == ("checks", app.DEFAULT_CONFIG.copy())


def test_run_mms_interface_analysis_reports_summary_and_errors(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))

    class MutableReport:
        def __init__(self) -> None:
            self.basepicture_name = "BasePicture"

        def summary(self) -> str:
            return f"mms summary for {self.basepicture_name}"

    def fake_mms(project_bp, debug=False, config=None):
        if project_bp == "bp-b":
            raise RuntimeError("boom")
        return MutableReport()

    monkeypatch.setattr(app_analysis, "analyze_mms_interface_variables", fake_mms)

    app_analysis.run_mms_interface_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    ("TargetA", "bp-a", SimpleNamespace()),
                    ("TargetB", "bp-b", SimpleNamespace()),
                ]
            ),
        ),
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("mms summary for TargetA" in line for line in lines)
    assert not any("mms summary for BasePicture" in line for line in lines)
    assert any("Error during analysis for TargetB: boom" in line for line in lines)
    assert pauses == ["pause"]


def test_run_icf_validation_reports_entryless_files_load_failures_and_summary(monkeypatch, tmp_path):
    lines: list[str] = []
    pauses: list[str] = []
    icf_dir = tmp_path / "icf"
    icf_dir.mkdir()
    empty_file = icf_dir / "Empty.icf"
    broken_file = icf_dir / "Broken.icf"
    valid_file = icf_dir / "Valid.icf"
    for path in (empty_file, broken_file, valid_file):
        path.write_text("dummy", encoding="utf-8")

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(
        app_analysis,
        "parse_icf_file",
        lambda path: [] if path.name == "Empty.icf" else [SimpleNamespace()],
    )
    monkeypatch.setattr(app_analysis.engine_module, "merge_project_basepicture", lambda bp, _graph: bp)

    def fake_load_program(_cfg, program_name):
        if program_name == "Broken":
            raise RuntimeError("load failed")
        return "bp-valid", SimpleNamespace(ast_by_name={})

    def fake_validate(program_bp, entries, expected_program, debug=False, moduletype_index=None):
        assert program_bp == "bp-valid"
        assert expected_program == "Valid"
        return SimpleNamespace(
            total_entries=3,
            valid_entries=2,
            issues=[object()],
            skipped_entries=1,
            summary=lambda: "icf report",
        )

    app_analysis.run_icf_validation(
        app.DEFAULT_CONFIG.copy(),
        configured_icf_files_fn=lambda _cfg: (icf_dir, [empty_file, broken_file, valid_file]),
        load_program_ast_fn=cast(Any, fake_load_program),
        validate_icf_entries_against_program_fn=fake_validate,
        pause_fn=lambda: pauses.append("pause"),
    )

    assert any("Empty.icf: no entries found" in line for line in lines)
    assert any("Broken.icf: failed to load program 'Broken': load failed" in line for line in lines)
    assert any("icf report" in line for line in lines)
    assert any("Files processed: 3" in line for line in lines)
    assert any("Files failed: 1" in line for line in lines)
    assert any("Entries: 3" in line for line in lines)
    assert any("Valid: 2" in line for line in lines)
    assert any("Invalid: 1" in line for line in lines)
    assert any("Skipped: 1" in line for line in lines)
    assert pauses == ["pause"]


def test_run_debug_variable_usage_and_comment_code_analysis_cover_empty_success_and_error(monkeypatch):
    lines: list[str] = []
    pauses: list[str] = []

    monkeypatch.setattr(app_analysis, "emit_output", lambda message: lines.append(message))
    monkeypatch.setattr(builtins, "input", make_input(["", "FlowVar"]))
    monkeypatch.setattr(
        app_analysis, "debug_variable_usage", lambda bp, var_name, debug=False: f"debug:{bp}:{var_name}"
    )
    monkeypatch.setattr(
        app_analysis,
        "analyze_comment_code_files",
        lambda paths, root_name: SimpleNamespace(
            summary=lambda: f"comment:{root_name}:{sorted(str(path) for path in paths)}"
        ),
    )

    app_analysis.run_debug_variable_usage(app.DEFAULT_CONFIG.copy(), pause_fn=lambda: pauses.append("pause-empty"))
    app_analysis.run_debug_variable_usage(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [
                    ("TargetA", "bp-a", SimpleNamespace()),
                    ("TargetB", "bp-b", SimpleNamespace()),
                ]
            ),
        ),
        pause_fn=lambda: pauses.append("pause-debug"),
    )
    app_analysis.run_comment_code_analysis(
        app.DEFAULT_CONFIG.copy(),
        iter_loaded_projects_fn=cast(
            Any,
            lambda *_args, **_kwargs: iter(
                [("TargetA", SimpleNamespace(header=SimpleNamespace(name="Root")), "graph")]
            ),
        ),
        source_paths_for_current_target_fn=lambda _project_bp, _graph: {Path("A.s"), Path("B.s")},
        pause_fn=lambda: pauses.append("pause-comment"),
    )

    assert any("No variable name provided" in line for line in lines)
    assert any("debug:bp-a:FlowVar" in line for line in lines)
    assert any("debug:bp-b:FlowVar" in line for line in lines)
    assert any("comment:TargetA:['A.s', 'B.s']" in line for line in lines)
    assert pauses == ["pause-empty", "pause-debug", "pause-comment"]
