"""Profile ONE analyzer in true isolation: load the graph once, then time only the
analyzer invocation (so load/parse cost is excluded from the analyzer profile).

Loads via the same code path the CLI uses, then calls run_registry_analyzer with a
warm shared-artifacts context so dependencies can reuse previously computed results.
"""

from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sattlint.analysis_dispatch import (  # noqa: E402
    get_registry_analyzer_spec,
    run_registry_analyzer,
    run_variables_registry_report,
)
from sattlint.app_analysis import iter_loaded_projects  # noqa: E402
from sattlint.config_types import ConfigDict  # noqa: E402

from sattlint.analyzers.framework import build_analysis_context  # noqa: E402
from sattlint.project import load_project  # noqa: E402


def build_merged_cfg(project_path: str, target_name: str) -> ConfigDict:
    project = load_project(Path(project_path).expanduser().resolve())
    cfg = project.to_default_merged_config_dict()
    cfg["analyzed_programs_and_libraries"] = [target_name]
    cfg["debug"] = True
    return cfg


def load_target(cfg: ConfigDict, target_name: str) -> Any:
    for name, bp, graph in iter_loaded_projects(cfg, use_cache=False):
        if name == target_name:
            return bp, graph
    raise RuntimeError(f"target {target_name!r} not loaded")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--cprofile", action="store_true")
    args = parser.parse_args()

    cfg = build_merged_cfg(args.project, args.target)
    bp, graph = load_target(cfg, args.target)
    print(f"loaded {args.target}: source_files loaded")

    spec = get_registry_analyzer_spec(args.key)
    context = build_analysis_context(
        bp,
        graph=graph,
        debug=True,
        target_is_library=bool(getattr(graph, "target_is_library", False)),
        config=cfg,
        create_shared_artifacts=True,
    )

    requires = cast(tuple[str, ...], getattr(spec, "requires", ()))
    if "variables" in requires:
        print(f"pre-running variables dependency for {args.key} ...")
        run_variables_registry_report(context)

    path: Path | None = None
    if args.cprofile:
        profiler = cProfile.Profile()
        profiler.enable()
        t0 = perf_counter()
        report = run_registry_analyzer(spec, context)
        dt = perf_counter() - t0
        profiler.disable()
        out = REPO_ROOT / "artifacts" / "profile"
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{args.key}_isolated.pstats"
        profiler.dump_stats(str(path))
    else:
        t0 = perf_counter()
        report = run_registry_analyzer(spec, context)
        dt = perf_counter() - t0

    n_issues = len(getattr(report, "issues", []))
    print(f"{args.key}: wall={dt * 1000:.1f}ms issues={n_issues}")
    if args.cprofile and path is not None:
        print(f"pstats written to {path}")
        print("top by cumulative:")
        stats = pstats.Stats(str(path))
        stats.sort_stats(pstats.SortKey.CUMULATIVE).print_stats(25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
