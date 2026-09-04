"""Phase-0 analyzer counter benchmark (Phase G guardrail).

Asserts that a full multi-analyzer run on a corpus target performs exactly the
canonical heavy work once:

- ``process-root-traversals == 1``    (the instance-aware variables traversal)
- ``variable-root-traversals == 1``   (same, per-target shared counter)
- ``variable-foundation-builds == 1`` (the AST-derived foundation, built once)

This guards against the regression the design doc forbids: analyzers that re-run
the expensive variables collection instead of consuming the shared ``collected_views`` /
``derived_reports``. The target defaults to a corpus target available in this repo
(the proprietary ``KaHAMPCSøjleLib`` corpus is not shipped here); pass ``--target`` to
point at a configured real target.

Usage:
    .venv/bin/python scripts/benchmark_analyzer_counters.py \
        --target MinimalProgram [--repeat 1]

Exit code is 0 when all counters meet the bound, nonzero otherwise.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import os
import sys
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sattlint import (  # noqa: E402
    app,
    app_analysis,
)
from sattlint._app_analysis_checks import collect_run_checks_result  # noqa: E402
from sattlint.analyzers.variables._variables_execution import (  # noqa: E402
    count_process_root_traversals,
)

CORPUS_VALID_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus" / "valid"

# Analyze from freshly-loaded projects, bypassing the project-level analysis-result cache
# (which would otherwise replay the original traversal count and skip real work).
_ITER_LOADED_PROJECTS_NO_RESULT_CACHE = functools.partial(app_analysis.iter_loaded_projects, use_cache=False)

# The analyzer set that exercises the layered pipeline: variables (collection), then
# sfc and mms-interface as derived consumers of the shared collection. Foundation is
# built once; the whole pipeline must share one traversal.
_DEFAULT_CHECKS = ("variables", "sfc", "mms-interface")


def _build_cfg(target_name: str) -> dict[str, object]:
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg.update(
        {
            "program_dir": str(CORPUS_VALID_DIR),
            "ABB_lib_dir": str(CORPUS_VALID_DIR),
            "icf_dir": str(CORPUS_VALID_DIR),
            "other_lib_dirs": [],
            "analyzed_programs_and_libraries": [target_name],
            "mode": "draft",
        }
    )
    return cfg


def _parse_target_counters(profile: str | None) -> dict[str, int]:
    """Extract the counter integers from a ``shared_artifact_profile`` string."""
    parsed: dict[str, int] = {}
    if not profile:
        return parsed
    for label in ("variable-foundation-builds", "variable-root-traversals"):
        marker = f"{label}="
        if marker in profile:
            raw = profile.split(marker, 1)[1].split(",", 1)[0]
            with contextlib.suppress(ValueError):
                parsed[label] = int(raw)
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--target", default="MinimalProgram", help="Corpus target name under tests/fixtures/corpus/valid/"
    )
    parser.add_argument("--repeat", type=int, default=1, help="Number of measurement iterations (default 1)")
    parser.add_argument("--checks", nargs="+", default=list(_DEFAULT_CHECKS), help="Analyzer keys to run")
    args = parser.parse_args(argv)

    # Enable the per-target shared-artifact profile string so the counters we assert are
    # surfaced on the result targets.
    os.environ["SATTLINT_PROFILE_ANALYZERS"] = "1"

    failures: list[str] = []
    for rep in range(1, args.repeat + 1):
        # Isolate from the persistent foundation/AST caches so each iteration measures a
        # genuinely cold heavy computation (a warm disk foundation would report 0 builds).
        with TemporaryDirectory(prefix="sattlint-benchmark-cache-") as scratch_cache_dir:
            os.environ["XDG_CACHE_HOME"] = scratch_cache_dir
            process_before = count_process_root_traversals()
            result = collect_run_checks_result(
                _build_cfg(args.target),
                list(args.checks),
                iter_loaded_projects_fn=_ITER_LOADED_PROJECTS_NO_RESULT_CACHE,
            )
        process_traversals = count_process_root_traversals() - process_before

        target_counters: dict[str, int] = {}
        for target in result.targets:
            target_counters.update(_parse_target_counters(target.shared_artifact_profile))

        foundation_builds = target_counters.get("variable-foundation-builds")
        root_traversals = target_counters.get("variable-root-traversals")

        ok = process_traversals == 1 and foundation_builds == 1 and root_traversals == 1
        print(
            f"{'PASS' if ok else 'FAIL'} iter {rep}: "
            f"process-root-traversals={process_traversals} "
            f"variable-foundation-builds={foundation_builds} "
            f"variable-root-traversals={root_traversals}"
        )
        if not ok:
            failures.append(
                f"iter {rep}: expected foundation-builds==1 and root-traversals==1, "
                f"got foundation={foundation_builds} root={root_traversals}; "
                f"process-root-traversals={process_traversals}"
            )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print(f"OK: {args.target} runs heavy collection exactly once (1 traversal, 1 foundation build).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
