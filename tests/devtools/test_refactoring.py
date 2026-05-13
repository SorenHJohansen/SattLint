import json

from sattlint.devtools import refactoring


def _program_source() -> str:
    return (
        '"Syntax version 2.23, date: 2026-05-04-12:00:00.000 N"\n'
        '"Original file date: ---"\n'
        '"Program date: 2026-05-04-12:00:00.000, name: Main"\n'
        "\n"
        "BasePicture Invocation\n"
        "   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0   \n"
        "    ) : MODULEDEFINITION DateCode_ 1\n"
        "\n"
        "\n"
        "LOCALVARIABLES   \n"
        "   Flag: integer := 0;   \n"
        "\n"
        "\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )   \n"
        "\n"
        "ModuleCode\n"
        "   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        "      Flag = Flag + 1;   \n"
        "\n"
        "\n"
        "ENDDEF (*BasePicture*);   \n"
    )


def test_build_refactoring_candidate_normalizes_layout_and_proves_safety(tmp_path):
    source_file = tmp_path / "Program" / "Main.s"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(_program_source(), encoding="utf-8")

    candidate, transformed_text = refactoring.build_refactoring_candidate(
        source_file,
        workspace_root=tmp_path,
    )

    assert transformed_text is not None
    assert candidate["status"] == "ok"
    assert candidate["changed"] is True
    assert candidate["applied"] is False
    assert candidate["safety_contract"] == {
        "preview_first": True,
        "safe_to_apply": True,
        "justification": "Whitespace normalization preserved the structural AST summary and semantic snapshot signature.",
    }
    assert candidate["safety_checks"] == {
        "original_parse_ok": True,
        "transformed_parse_ok": True,
        "structural_summary_equal": True,
        "semantic_signature_equal": True,
    }
    assert candidate["summary"]["changed_line_count"] > 0
    assert candidate["diff"][0].startswith("--- Program/Main.s")
    assert candidate["diff"][1].startswith("+++ Program/Main.s")
    assert transformed_text.endswith("\n")
    assert "  \n" not in transformed_text
    assert "\n\n\n" not in transformed_text


def test_build_refactoring_report_applies_safe_changes(tmp_path):
    source_file = tmp_path / "Program" / "Main.s"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text(_program_source(), encoding="utf-8")

    report = refactoring.build_refactoring_report(
        tmp_path,
        apply=True,
    )

    assert report["status"] == "ok"
    assert report["apply_mode"] == "apply"
    assert report["summary"] == {
        "selected_entry_count": 1,
        "changed_candidate_count": 1,
        "safe_candidate_count": 1,
        "applied_change_count": 1,
        "error_count": 0,
    }
    assert report["candidates"][0]["source_file"] == "Program/Main.s"
    assert report["candidates"][0]["applied"] is True
    assert "  \n" not in source_file.read_text(encoding="utf-8")
    assert "\n\n\n" not in source_file.read_text(encoding="utf-8")


def test_main_writes_report_and_progress(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.refactoring",
        "report_kind": "refactoring-preview",
        "status": "ok",
        "workspace_root": ".",
        "refactoring_kind": "normalize-layout",
        "apply_mode": "dry-run",
        "summary": {
            "selected_entry_count": 1,
            "changed_candidate_count": 0,
            "safe_candidate_count": 1,
            "applied_change_count": 0,
            "error_count": 0,
        },
        "candidates": [],
        "selection_errors": [],
    }

    def _build_refactoring_report(*_args, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        assert progress_callback is not None
        progress_callback("Refactoring: discovering workspace sources")
        return expected_report

    monkeypatch.setattr(refactoring, "build_refactoring_report", _build_refactoring_report)

    output_dir = tmp_path / "artifacts"
    exit_code = refactoring.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--dry-run",
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Refactoring: discovering workspace sources" in captured.err
    assert json.loads(captured.out) == expected_report
    assert json.loads((output_dir / refactoring.DEFAULT_OUTPUT_FILENAME).read_text(encoding="utf-8")) == expected_report
