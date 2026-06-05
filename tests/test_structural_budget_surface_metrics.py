from __future__ import annotations

import json

from sattlint.devtools import pipeline, structural_reports


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_collect_structural_budget_report_tracks_surface_metric_maxima(tmp_path):
    _write(tmp_path / "src" / "pkg" / "dep_a.py", "def helper():\n    return 1\n")
    _write(tmp_path / "src" / "pkg" / "dep_b.py", "class Runner:\n    pass\n")
    _write(
        tmp_path / "src" / "pkg" / "surface.py",
        "import os, sys\n"
        "from pkg import dep_a\n"
        "from pkg.dep_b import Runner\n\n"
        "PUBLIC_CONST = 1\n\n"
        "class PublicThing:\n"
        "    pass\n\n"
        "def public_function():\n"
        "    if True:\n"
        "        for index in range(1):\n"
        "            while index < 1:\n"
        "                return dep_a.helper()\n"
        "    return Runner()\n",
    )

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["summary"]["import_max_count"] == 4
    assert report["summary"]["dependency_max_count"] == 2
    assert report["summary"]["public_symbol_max_count"] == 3
    assert report["summary"]["nesting_max_depth"] == 3
    assert report["metrics"]["import_max_count"] == 4
    assert report["metrics"]["dependency_max_count"] == 2
    assert report["metrics"]["public_symbol_max_count"] == 3
    assert report["metrics"]["nesting_max_depth"] == 3
    assert report["module_import_counts"][0] == {"path": "src/pkg/surface.py", "import_count": 4}
    assert report["module_dependency_counts"][0] == {"path": "src/pkg/surface.py", "dependency_count": 2}
    assert report["module_public_symbol_counts"][0] == {
        "path": "src/pkg/surface.py",
        "public_symbol_count": 3,
    }
    assert report["function_nesting_depths"][0]["path"] == "src/pkg/surface.py"
    assert report["function_nesting_depths"][0]["qualname"] == "public_function"
    assert report["function_nesting_depths"][0]["nesting_depth"] == 3


def test_evaluate_change_scoped_structural_surface_proof_flags_changed_file_regression(tmp_path):
    _write(tmp_path / "src" / "pkg" / "dep_a.py", "def helper():\n    return 1\n")
    _write(
        tmp_path / "src" / "pkg" / "surface.py",
        "import os\n"
        "from pkg import dep_a\n\n"
        "PUBLIC_CONST = 1\n\n"
        "def public_function(items):\n"
        "    if items:\n"
        "        for item in items:\n"
        "            while item:\n"
        "                return dep_a.helper()\n"
        "    return None\n",
    )
    _write(
        tmp_path / "artifacts" / "analysis" / "structural_budget_ratchet.json",
        json.dumps(
            {
                "kind": "sattlint.structural_budget_ratchet",
                "schema_version": 3,
                "metrics": {
                    "import_max_count": 1,
                    "dependency_max_count": 0,
                    "public_symbol_max_count": 1,
                    "nesting_max_depth": 2,
                },
            },
            indent=2,
        ),
    )

    proof = pipeline.evaluate_change_scoped_structural_surface_proof(
        repo_root=tmp_path,
        changed_files=["src/pkg/surface.py"],
    )

    assert proof["status"] == "fail"
    assert proof["checked_files"] == ["src/pkg/surface.py"]
    assert proof["metrics_by_path"]["src/pkg/surface.py"] == {
        "import_max_count": 2,
        "dependency_max_count": 1,
        "public_symbol_max_count": 2,
        "nesting_max_depth": 3,
    }
    assert {violation["metric"] for violation in proof["violations"]} == {
        "import_max_count",
        "dependency_max_count",
        "public_symbol_max_count",
        "nesting_max_depth",
    }
