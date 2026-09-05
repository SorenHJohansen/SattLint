# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportPrivateUsage=false
"""End-to-end crash-sweep tests for the full analysis pipeline.

These tests load real SattLine fixtures through the project loader and run the
entire enabled analyzer registry, failing on any unexpected analyzer exception.
Unit tests build the AST by factory, so parser-only constructs (such as a
compound header enable expression that becomes a BoolOp tail) are never
exercised without a real file. This suite closes that gap.
"""

from pathlib import Path

import pytest

from sattlint.analyzers.dispatch import get_cli_dispatch_analyzers, run_registry_analyzer
from sattlint.analyzers.framework import build_analysis_context
from sattlint.analyzers.registry import get_enabled_analyzers
from sattlint.engine import CodeMode, SattLineProjectLoader, SattLineProjectLoaderConfig, merge_project_basepicture

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "sample_sattline_files"

# Add a fixture here whenever a real file surfaces a new analyzer crash shape.
# The file must load through SattLineProjectLoader without a strict-validation
# failure so the sweep reaches the analyzers.
ANALYZER_CRASH_FIXTURES = ("EnableExpr",)


def _load_base_picture(stem: str):
    fixture = FIXTURE_DIR / f"{stem}.s"
    loader = SattLineProjectLoader(
        SattLineProjectLoaderConfig(
            program_dir=fixture.parent,
            other_lib_dirs=[],
            abb_lib_dir=fixture.parent,
            mode=CodeMode.DRAFT,
            debug=False,
            use_file_ast_cache=False,
        )
    )
    graph = loader.resolve(fixture.stem, strict=False)
    base_picture = merge_project_basepicture(graph.ast_by_name[fixture.stem], graph)
    return base_picture, graph


@pytest.mark.parametrize("stem", ANALYZER_CRASH_FIXTURES)
def test_full_analysis_pipeline_does_not_crash_on_real_fixture(stem: str) -> None:
    base_picture, graph = _load_base_picture(stem)
    context = build_analysis_context(base_picture, graph=graph, debug=False, create_shared_artifacts=True)
    analyzers = get_cli_dispatch_analyzers(selected_keys=None, get_enabled_analyzers_fn=get_enabled_analyzers)
    assert analyzers, "expected at least one enabled analyzer"
    assert context.shared_artifacts is not None, "shared artifacts should be created"

    for spec in analyzers:
        try:
            report = run_registry_analyzer(spec, context)
        except Exception as exc:
            raise AssertionError(f"{stem}.s: analyzer '{spec.key}' raised {type(exc).__name__}: {exc}") from exc
        context.shared_artifacts.reports_by_analyzer_key[spec.key] = report
