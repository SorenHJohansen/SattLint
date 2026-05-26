from types import SimpleNamespace

from sattline_parser.models.ast_model import BasePicture, ModuleHeader
from sattlint import semantic_analysis as semantic_analysis_module


def test_project_lsp_report_diagnostics_skips_non_list_issue_payloads(monkeypatch):
    monkeypatch.setattr(semantic_analysis_module, "build_module_diagnostic_sites", lambda _base_picture: {})
    monkeypatch.setattr(
        semantic_analysis_module,
        "merge_diagnostic_projection_results",
        lambda *reports: ("merged", reports),
    )
    monkeypatch.setattr("sattlint.analyzers.registry.SEMANTIC_LAYER_ANALYZER_KEY", "semantic-layer")
    monkeypatch.setattr(
        "sattlint.analyzers.registry.get_default_analyzer_catalog",
        lambda: SimpleNamespace(
            analyzers=[
                SimpleNamespace(
                    delivery=SimpleNamespace(lsp_exposed=True),
                    spec=SimpleNamespace(
                        key="custom-analyzer",
                        run=lambda _context: SimpleNamespace(issues=("not-a-list",)),
                    ),
                )
            ]
        ),
    )

    result = semantic_analysis_module._project_lsp_report_diagnostics(
        BasePicture(header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))),
        SimpleNamespace(unavailable_libraries=()),
        debug=False,
    )

    assert result == ("merged", ())
