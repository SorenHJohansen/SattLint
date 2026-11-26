# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
from pathlib import Path
from types import SimpleNamespace
from typing import (
    Any,
    cast,
)

import pytest
from sattline_parser.project import ProjectLoadError

from sattlint.analyzers import catalog as analysis_catalog_module
from sattlint.application import (
    checks_execution,
)
from sattlint.application import (
    project as project_application,
)
from sattlint.config.types import ConfigDict
from sattlint.core.syntax import CodeMode
from sattlint.models.project_graph import ProjectGraph
from sattlint.parser_api import BasePicture
from sattlint.project import (
    loading as analysis_loading_module,
)
from sattlint.project import loading_support as loading_support_module
from sattlint.project import (
    support as support_module,
)
from sattlint.project.parser_adapter import ParserProjectBinding
from tests.helpers import AnalysisGraphStub, named_object


def test_app_analysis_wrappers_delegate_to_underlying_helpers(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        support_module,
        "target_validation_warnings",
        lambda target, warnings: [f"{target}:{len(warnings)}"],
    )
    monkeypatch.setattr(
        project_application, "_iter_loaded_projects", lambda *_args, **_kwargs: iter([("TargetA", "bp", "g")])
    )
    monkeypatch.setattr(project_application, "_source_paths_for_current_target", lambda *_args: {Path("TargetA.s")})
    monkeypatch.setattr(project_application, "_target_is_library", lambda *_args: True)
    monkeypatch.setattr(analysis_catalog_module, "get_selectable_analyzers", lambda: ["variables"])

    assert project_application._target_validation_warnings("TargetA", ["a", "b"]) == ["TargetA:2"]
    assert list(project_application.iter_loaded_projects(cast(ConfigDict, {}))) == [("TargetA", "bp", "g")]
    assert project_application.source_paths_for_current_target(cast(Any, "bp"), cast(Any, "graph")) == {
        Path("TargetA.s")
    }
    assert project_application.target_is_library(cast(ConfigDict, {}), cast(Any, "bp"), cast(Any, "graph")) is True
    assert checks_execution.get_enabled_analyzers() == ["variables"]


def test_target_validation_warnings_keeps_controllib_dependency_warning():
    assert project_application._target_validation_warnings(
        "ColumnLib",
        [
            "ColumnLib: dependency 'controllib' unavailable: expected proprietary dependency",
            "ColumnLib: warning one",
            "dep_b: warning two",
        ],
    ) == [
        "ColumnLib: dependency 'controllib' unavailable: expected proprietary dependency",
        "ColumnLib: warning one",
    ]


def test_analysis_loading_helpers_cover_target_accessors_and_refresh_formatting(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(support_module, "get_analyzed_targets", lambda cfg: ["TargetA"])
    monkeypatch.setattr(support_module, "require_analyzed_targets", lambda cfg: ["TargetB"])

    assert project_application._get_analyzed_targets(cast(ConfigDict, {})) == ["TargetA"]
    assert project_application._require_analyzed_targets(cast(ConfigDict, {})) == ["TargetB"]
    assert loading_support_module._workspace_dependency_suffixes("draft") == (".l", ".z")
    assert loading_support_module._workspace_dependency_suffixes("official") == (".z",)
    assert loading_support_module._workspace_dependency_suffixes(CodeMode.DRAFT) == (".l", ".z")
    assert loading_support_module._workspace_dependency_suffixes(CodeMode.OFFICIAL) == (".z",)
    assert loading_support_module._format_refresh_stage_timings(
        {"load_or_parse": 0.1, "validate": 0.2},
        refresh_mode="ast-only",
    ) == ("AST refresh stage totals: load_or_parse=0.1000s, validate=0.2000s, graphics=skipped, index=skipped")


def test_analysis_loading_reverse_consumer_helpers_cover_scan_and_queueing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    program_dir = tmp_path / "programs"
    other_dir = tmp_path / "other"
    error_dir = tmp_path / "error"
    missing_dir = tmp_path / "missing"
    program_dir.mkdir()
    other_dir.mkdir()
    error_dir.mkdir()

    (program_dir / "consumer.l").write_text("", encoding="utf-8")
    (program_dir / "consumer.z").write_text("", encoding="utf-8")
    (program_dir / "selected.l").write_text("", encoding="utf-8")
    (program_dir / "notes.txt").write_text("", encoding="utf-8")
    (other_dir / "consumer.z").write_text("", encoding="utf-8")
    (other_dir / "remote.z").write_text("", encoding="utf-8")

    original_iterdir = Path.iterdir

    def fake_iterdir(path: Path):
        if path == error_dir:
            raise OSError("boom")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    cfg = {
        "program_dir": str(program_dir),
        "other_lib_dirs": [str(other_dir), str(error_dir), str(missing_dir)],
        "mode": "draft",
    }

    # Draft prefers ``.l`` and falls back to ``.z`` when a program has no
    # ``.l`` sidecar, so every program keeps its dependency list.
    assert list(
        loading_support_module._iter_workspace_reverse_library_consumer_dependency_files(cast(ConfigDict, cfg))
    ) == [
        ("consumer", program_dir / "consumer.l"),
        ("selected", program_dir / "selected.l"),
        ("remote", other_dir / "remote.z"),
    ]

    visits: list[tuple[str, Path]] = []
    deps_paths = {
        "CandidateA": program_dir / "CandidateA.z",
        "NoDeps": program_dir / "NoDeps.z",
        "NoPath": None,
        "DupLocal": program_dir / "CandidateA.z",
        # The consumer closure asks for the consumers of every discovered
        # consumer; ``selected.l`` has no dependency list, so the walk stops.
        "Selected": program_dir / "selected.l",
    }
    deps_map = {
        None: ["Selected"],
        program_dir / "CandidateA.z": ["Selected"],
        program_dir / "NoDeps.z": ["Other"],
        other_dir / "Remote.z": ["Selected"],
        other_dir / "Ignore.z": ["Other"],
    }

    class FakeLoader:
        def _visit(
            self,
            target_name: str,
            graph: ProjectGraph,
            syntax_only: bool,
            requester_dir: Path | None = None,
            syntax_check: bool = False,
        ) -> None:
            self.visit_target(target_name, graph, syntax_only, requester_dir, syntax_check)

        def _find_deps_with_context(self, target_name: str, requester_dir: Path | None = None) -> Path | None:
            del requester_dir
            return deps_paths[target_name]

        def _read_deps(self, deps_path: Path | None) -> list[str]:
            return deps_map.get(deps_path, [])

        def visit_target(
            self,
            target_name: str,
            graph: ProjectGraph,
            syntax_only: bool,
            requester_dir: Path | None,
            syntax_check: bool,
        ) -> None:
            del graph, syntax_only, syntax_check
            assert requester_dir is not None
            visits.append((target_name, requester_dir))

        def find_dependency_path(self, target_name: str) -> Path | None:
            return self._find_deps_with_context(target_name)

        def read_dependency_names(self, deps_path: Path | None) -> list[str]:
            return self._read_deps(deps_path)

    loader = FakeLoader()

    def find_dependency_path_fn(target_name: str) -> Path | None:
        return loader.find_dependency_path(target_name)

    def read_dependency_names_fn(deps_path: Path | None) -> list[str]:
        return loader.read_dependency_names(deps_path)

    def visit_targets_fn(targets: list[tuple[str, Path | None]]) -> None:
        for target_name, requester_dir in targets:
            loader.visit_target(target_name, cast(ProjectGraph, "graph"), False, requester_dir, False)

    # The target's program/library classification takes no part in consumer
    # discovery: any dependant that references the selected target loads.
    monkeypatch.setattr(
        loading_support_module,
        "_iter_workspace_reverse_library_consumer_dependency_files",
        lambda _cfg: iter(
            [
                ("Selected", program_dir / "selected.l"),
                ("NoIterPath", None),
                ("Remote", other_dir / "Remote.z"),
                ("Ignore", other_dir / "Ignore.z"),
                ("CandidateA", program_dir / "CandidateA.z"),
            ]
        ),
    )

    analysis_loading_module._include_reverse_library_consumers(
        cast(ConfigDict, cfg),
        selected_target="Selected",
        root_bp=cast(BasePicture, named_object("BasePicture")),
        graph=cast(Any, "graph"),
        find_dependency_path_fn=find_dependency_path_fn,
        read_dependency_names_fn=read_dependency_names_fn,
        visit_targets_fn=visit_targets_fn,
        require_analyzed_targets_fn=lambda _cfg: ["Selected", "CandidateA", "NoDeps", "NoPath", "DupLocal"],
    )

    assert visits == [
        ("CandidateA", program_dir),
        ("DupLocal", program_dir),
        ("Remote", other_dir),
    ]


def test_analysis_loading_cache_manifest_files_adds_companions_and_dependency_manifests():
    cfg = {"program_dir": "programs", "mode": "draft"}
    target_a = SimpleNamespace(header=SimpleNamespace(name="TargetA"), origin_file=None)
    target_b = SimpleNamespace(header=SimpleNamespace(name="TargetB"), origin_file=None)
    graph = AnalysisGraphStub(
        source_files={Path("programs/TargetA.s")},
        ast_by_name={"TargetA": target_a, "TargetB": target_b},
    )
    graph.record_root_origin("TargetA", source_path=Path("programs/TargetA.s"), library_name="programs")
    graph.record_root_origin("TargetB", source_path=Path("libraries/TargetB.s"), library_name="libraries")

    def resolve_graphics_companion_path_fn(source_path: Path, **_kwargs: object) -> Path:
        return source_path.with_suffix(".g")

    manifest_files = analysis_loading_module.cache_manifest_files(
        cast(ConfigDict, cfg),
        cast(ProjectGraph, graph),
        find_dependency_path_fn=lambda target_name: (
            Path("libraries" if target_name == "TargetB" else "programs") / f"{target_name}.z"
        ),
        resolve_graphics_companion_path_fn=resolve_graphics_companion_path_fn,
    )

    assert manifest_files == {
        Path("programs/TargetA.s"),
        Path("programs/TargetA.g"),
        Path("programs/TargetA.z"),
        Path("libraries/TargetB.z"),
        Path("programs"),
    }


def test_visit_targets_into_graph_keeps_consumers_that_load(monkeypatch: pytest.MonkeyPatch):
    converted: list[str] = []
    failures: list[tuple[str, str]] = []

    def fake_load_parser_project(
        _binding: ParserProjectBinding, targets: list[str], **_kwargs: object
    ) -> SimpleNamespace:
        raise ProjectLoadError(targets[0], "missing code file")

    def fake_load_parser_projects(
        _binding: ParserProjectBinding, targets: list[str], **_kwargs: object
    ) -> dict[str, SimpleNamespace]:
        results: dict[str, SimpleNamespace] = {}
        for name in targets:
            if name == "ConsumerB":
                results[name] = SimpleNamespace(project=None, error=ProjectLoadError(name, "missing code file"))
            else:
                results[name] = SimpleNamespace(project=SimpleNamespace(names=(name,)), error=None)
        return results

    def fake_convert_project_into_graph(
        _project: object,
        _graph: ProjectGraph,
        *,
        binding: ParserProjectBinding,
        root_name: str,
        strict: bool,
        lib_names: dict[str, str],
        extra_roots: tuple[Path, ...] = (),
    ) -> None:
        del binding, strict, lib_names, extra_roots
        converted.append(root_name)

    def fake_record_project_load_failure(_graph: ProjectGraph, name: str, exception: BaseException) -> None:
        failures.append((name, str(exception)))

    monkeypatch.setattr(analysis_loading_module, "load_parser_project", fake_load_parser_project)
    monkeypatch.setattr(analysis_loading_module, "load_parser_projects", fake_load_parser_projects)
    monkeypatch.setattr(analysis_loading_module, "convert_project_into_graph", fake_convert_project_into_graph)
    monkeypatch.setattr(analysis_loading_module, "record_project_load_failure", fake_record_project_load_failure)

    analysis_loading_module._visit_targets_into_graph(
        cast(Any, object()),
        ProjectGraph(),
        [("ConsumerA", None), ("ConsumerB", None)],
        lib_names={},
    )

    assert converted == ["ConsumerA"]
    assert [name for name, _message in failures] == ["ConsumerB"]
    assert "missing code file" in failures[0][1]


def test_visit_targets_into_graph_batch_marks_every_consumer_as_root(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, tuple[str, ...]]] = []

    def fake_convert_project_into_graph(
        _project: object,
        _graph: ProjectGraph,
        *,
        binding: ParserProjectBinding,
        root_name: str,
        strict: bool,
        lib_names: dict[str, str],
        extra_roots: tuple[str, ...] = (),
    ) -> None:
        del binding, strict, lib_names
        calls.append((root_name, tuple(extra_roots)))

    monkeypatch.setattr(
        analysis_loading_module,
        "load_parser_project",
        lambda _binding, targets, **_kwargs: SimpleNamespace(names=tuple(targets)),
    )
    monkeypatch.setattr(analysis_loading_module, "convert_project_into_graph", fake_convert_project_into_graph)

    analysis_loading_module._visit_targets_into_graph(
        cast(Any, object()),
        ProjectGraph(),
        [("ConsumerA", None), ("ConsumerB", None)],
        lib_names={},
    )

    # The shared project validates both consumers as roots, so a consumer that
    # is also another consumer's dependency keeps its root-scope diagnostics.
    assert calls == [("ConsumerA", ("ConsumerB",))]


def test_record_project_load_failure_names_the_program_message_and_dependency():
    graph = ProjectGraph()

    loading_support_module.record_project_load_failure(
        graph,
        "Consumer",
        ProjectLoadError("Dep", "missing code file", dependency="Dep"),
    )

    failure = graph.failures["CONSUMER"]
    assert failure.name == "Consumer"
    assert failure.line is None
    assert failure.column is None
    assert "missing code file" in failure.message
    assert "dependency 'Dep'" in failure.message
    assert graph.missing == [failure.message]


def test_analysis_loading_cache_manifest_files_adds_distribution_companions(tmp_path: Path):
    draft_body = tmp_path / "Draft.s"
    official_body = tmp_path / "Official.x"
    for path in (draft_body, official_body):
        path.write_text("", encoding="utf-8")
    draft_companion = draft_body.with_suffix(".p")
    official_companion = official_body.with_suffix(".q")
    for path in (draft_companion, official_companion):
        path.write_text("", encoding="utf-8")

    graph = ProjectGraph(source_files={draft_body, official_body})

    manifest_files = analysis_loading_module.cache_manifest_files(
        cast(ConfigDict, {"program_dir": str(tmp_path), "mode": "draft"}),
        graph,
        find_dependency_path_fn=lambda _target_name: None,
        resolve_graphics_companion_path_fn=lambda _source_path, **_kwargs: None,
    )

    assert manifest_files == {draft_body, draft_companion, official_body, official_companion, tmp_path}


def test_reverse_consumer_scan_prefers_the_mode_sidecar_and_falls_back(tmp_path: Path):
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    (program_dir / "Both.l").write_text("", encoding="utf-8")
    (program_dir / "Both.z").write_text("", encoding="utf-8")
    (program_dir / "OfficialOnly.z").write_text("", encoding="utf-8")

    draft = loading_support_module._iter_workspace_reverse_library_consumer_dependency_files(
        cast(ConfigDict, {"program_dir": str(program_dir), "other_lib_dirs": [], "mode": "draft"})
    )
    assert list(draft) == [
        ("Both", program_dir / "Both.l"),
        ("OfficialOnly", program_dir / "OfficialOnly.z"),
    ]

    official = loading_support_module._iter_workspace_reverse_library_consumer_dependency_files(
        cast(ConfigDict, {"program_dir": str(program_dir), "other_lib_dirs": [], "mode": "official"})
    )
    assert list(official) == [("Both", program_dir / "Both.z"), ("OfficialOnly", program_dir / "OfficialOnly.z")]


def test_cache_manifest_uses_one_mode_for_both_companion_families():
    graph = AnalysisGraphStub(source_files={Path("programs/Target.s")})
    seen: dict[str, object] = {}

    def graphics_companion(_source: Path, *, mode: CodeMode | None = None) -> None:
        seen["graphics"] = mode
        return None

    def distribution_companion(_source: Path, *, mode: CodeMode | None = None) -> None:
        seen["distribution"] = mode
        return None

    analysis_loading_module.cache_manifest_files(
        cast(ConfigDict, {}),
        cast(ProjectGraph, graph),
        find_dependency_path_fn=lambda _name: None,
        resolve_graphics_companion_path_fn=graphics_companion,
        resolve_distribution_companion_path_fn=distribution_companion,
    )

    assert str(seen["graphics"]) == "CodeMode.OFFICIAL"
    assert str(seen["distribution"]) == "LoadMode.OFFICIAL"


def test_reverse_consumer_scan_ignores_a_missing_program_dir():
    assert (
        list(loading_support_module._iter_workspace_reverse_library_consumer_dependency_files(cast(ConfigDict, {})))
        == []
    )
