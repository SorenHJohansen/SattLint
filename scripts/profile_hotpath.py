"""Ad-hoc profiling for the AST-generation and analyzer hot paths.

Not a benchmark: this only reports numbers for a single machine/run. See
/memories/session/plan.md ("AST + Analyzer Instrumentation & Profiling") for the full protocol.

Two subcommands:

  ast      Parses a single SattLine source file directly via sattline_parser (no workspace
           loading, no analyzers). Use this for the "realistic" UnCompressedFullGrammar.s
           fixture, which contains multiple module definitions and cannot be loaded as a
           single named workspace target.

  analyze  Runs `collect_run_checks_result()` against a workspace target under
           tests/fixtures/corpus/valid/. The loader is invoked exactly once per rep, inside
           this single call, so load cost and analyze cost share one call graph on purpose --
           never call load_project_graph separately before this.

Both subcommands support:
  --repeat N     Run N times, report median wall time (default 5).
  --cprofile     Run once under cProfile instead of timing repeats, dump a .pstats file.
  --cache cold|warm   cold = fresh empty AST cache per rep; warm = one untimed warm-up rep
                      then reuse across measured reps. Controlled via a scratch XDG_CACHE_HOME.

Usage:
    .venv/bin/python scripts/profile_hotpath.py ast \
        --file tests/fixtures/corpus/valid/UnCompressedFullGrammar.s --repeat 5
    .venv/bin/python scripts/profile_hotpath.py analyze \
        --target MinimalProgram --check comment-code --cache warm
    .venv/bin/python scripts/profile_hotpath.py analyze \
        --target MinimalProgram --check comment-code --cprofile
    .venv/bin/python scripts/profile_hotpath.py analyze \
        --project ~/.config/sattlint/OG.slproj --target KaHAMPCSøjleLib --check comment-code
"""

from __future__ import annotations

import argparse
import cProfile
import functools
import os
import statistics
import subprocess
import sys
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sattline_parser import parse_source_file  # noqa: E402

from sattlint import (  # noqa: E402
    app,
    app_analysis,
)
from sattlint._app_analysis_checks import collect_run_checks_result  # noqa: E402
from sattlint.analyzers.registry import get_enabled_analyzers  # noqa: E402
from sattlint.app_analysis import ChecksRunResult  # noqa: E402
from sattlint.config_types import ConfigDict  # noqa: E402
from sattlint.project import load_project  # noqa: E402

# The project-level analysis-result cache (separate from the per-file AST cache) replays the
# stage/analyzer timings recorded on the ORIGINAL load on every cache hit, so a warm rep would
# otherwise report stale instrumented_ms alongside a near-zero real wall_ms. Force it off so
# --cache only varies the per-file AST cache we actually care about here.
_ITER_LOADED_PROJECTS_NO_RESULT_CACHE = functools.partial(app_analysis.iter_loaded_projects, use_cache=False)

CORPUS_VALID_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus" / "valid"


@dataclass(frozen=True, slots=True)
class RunMetrics:
    wall_ms: float
    instrumented_ms: float

    @property
    def unattributed_ms(self) -> float:
        return max(self.wall_ms - self.instrumented_ms, 0.0)


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _print_run_header(*, target_or_file: str, extra: dict[str, object], args: argparse.Namespace) -> None:
    print(f"commit={_git_commit()} python={sys.version.split()[0]} cache={args.cache}")
    for key, value in extra.items():
        print(f"{key}={value}", end=" ")
    print()
    print(f"target={target_or_file} checks={getattr(args, 'check', None) or '<n/a>'} repeat={args.repeat}")


def _run_ast_once(file_path: Path) -> RunMetrics:
    started_at = perf_counter()
    parse_source_file(file_path)
    wall_ms = (perf_counter() - started_at) * 1000.0
    # Direct parsing has no separate stage-timing sink; wall time IS the instrumented time.
    return RunMetrics(wall_ms=wall_ms, instrumented_ms=wall_ms)


def _instrumented_ms(result: ChecksRunResult) -> float:
    total = 0.0
    for target in result.targets:
        if target.stage_timings_ms:
            total += sum(target.stage_timings_ms.values())
        total += sum(a.duration_ms or 0.0 for a in target.analyzers)
    return total


def _build_cfg(target_name: str) -> ConfigDict:
    cfg = deepcopy(app.DEFAULT_CONFIG)
    cfg.update(
        {
            "program_dir": str(CORPUS_VALID_DIR),
            "ABB_lib_dir": str(CORPUS_VALID_DIR),
            "icf_dir": str(CORPUS_VALID_DIR),
            "other_lib_dirs": [],
            "analyzed_programs_and_libraries": [target_name],
            "mode": "draft",
            # Forces collect_stage_timings=True in _app_analysis_loading.py.
            "debug": True,
        }
    )
    return cfg


def _build_cfg_from_project(project_path: Path) -> ConfigDict:
    project = load_project(project_path)
    cfg = project.to_default_merged_config_dict()
    # Overwrite the configured target list: profiling focuses on a single target
    # unless --target is explicitly passed; the caller fills this in.
    cfg["analyzed_programs_and_libraries"] = []
    # debug=True forces collect_stage_timings=True and per-analyzer timings.
    cfg["debug"] = True
    return cfg


def _all_enabled_analyzers_fn() -> list[Any]:
    return list(get_enabled_analyzers())


def _run_analyze_once(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
) -> RunMetrics:
    started_at = perf_counter()
    result = collect_run_checks_result(
        cfg,
        selected_keys,
        iter_loaded_projects_fn=_ITER_LOADED_PROJECTS_NO_RESULT_CACHE,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
    )
    wall_ms = (perf_counter() - started_at) * 1000.0
    return RunMetrics(wall_ms=wall_ms, instrumented_ms=_instrumented_ms(result))


def _run_baseline_repeats(args: argparse.Namespace, run_once: Callable[[], RunMetrics]) -> None:
    if args.cache == "warm":
        run_once()  # untimed warm-up

    wall_samples: list[float] = []
    instrumented_samples: list[float] = []
    unattributed_samples: list[float] = []
    for rep in range(1, args.repeat + 1):
        if args.cache == "cold":
            with TemporaryDirectory(prefix="sattlint-profile-cache-") as rep_cache_dir:
                os.environ["XDG_CACHE_HOME"] = rep_cache_dir
                metrics = run_once()
        else:
            metrics = run_once()
        wall_samples.append(metrics.wall_ms)
        instrumented_samples.append(metrics.instrumented_ms)
        unattributed_samples.append(metrics.unattributed_ms)
        print(
            f"  rep {rep}: wall_ms={metrics.wall_ms:.2f} "
            f"instrumented_ms={metrics.instrumented_ms:.2f} "
            f"unattributed_ms={metrics.unattributed_ms:.2f}"
        )

    print(
        "median: "
        f"wall_ms={statistics.median(wall_samples):.2f} "
        f"instrumented_ms={statistics.median(instrumented_samples):.2f} "
        f"unattributed_ms={statistics.median(unattributed_samples):.2f}"
    )


def _run_cprofile(args: argparse.Namespace, run_once: Callable[[], RunMetrics], output_stem: str) -> None:
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output_stem}_{args.cache}.pstats"

    profiler = cProfile.Profile()
    profiler.enable()
    metrics = run_once()
    profiler.disable()
    profiler.dump_stats(str(output_path))

    print(f"wall_ms={metrics.wall_ms:.2f} instrumented_ms={metrics.instrumented_ms:.2f}")
    print(f"pstats written to {output_path}")
    print(f"inspect with: .venv/bin/python -m pstats {output_path}")


def _cmd_ast(args: argparse.Namespace) -> None:
    file_path = REPO_ROOT / args.file
    _print_run_header(target_or_file=str(file_path), extra={"source_bytes": file_path.stat().st_size}, args=args)

    def run_once() -> RunMetrics:
        return _run_ast_once(file_path)

    if args.cprofile:
        _run_cprofile(args, run_once, output_stem=file_path.stem)
    else:
        _run_baseline_repeats(args, run_once)


def _print_analyzer_report(result: ChecksRunResult) -> None:
    for target in result.targets:
        print(f"\n=== {target.target_name} ({len(target.analyzers)} analyzers) ===")
        rows = sorted(
            (
                (a.name, a.key, a.duration_ms or 0.0, a.issue_count if a.issue_count is not None else 0)
                for a in target.analyzers
            ),
            key=lambda row: row[2],
            reverse=True,
        )
        name_width = max(len(name) for name, _key, _dur, _cnt in rows) if rows else 0
        print(f"{'analyzer':<{name_width}}  {'key':<30} {'duration_ms':>10}  {'issues':>6}")
        for name, key, duration_ms, issues in rows:
            print(f"{name:<{name_width}}  {key:<30} {duration_ms:>10.2f}  {issues:>6}")


def _cmd_analyze(args: argparse.Namespace) -> None:
    if args.project:
        project_path = Path(args.project).expanduser().resolve()
        cfg = _build_cfg_from_project(project_path)
        if args.target:
            cfg["analyzed_programs_and_libraries"] = [args.target]
        _print_run_header(target_or_file=f"project:{project_path}", extra={}, args=args)
        print(f"targets={args.target or cfg.get('analyzed_programs_and_libraries')}")
    else:
        cfg = _build_cfg(args.target)
        file_count = len(list(CORPUS_VALID_DIR.glob("*.s")))
        source_bytes = sum(f.stat().st_size for f in CORPUS_VALID_DIR.glob("*.s"))
        _print_run_header(
            target_or_file=args.target,
            extra={"program_dir_files": file_count, "program_dir_bytes": source_bytes},
            args=args,
        )

    enabled_fn = _all_enabled_analyzers_fn if args.all else None

    if args.cprofile:
        output_stem = args.target or Path(args.project or "project").stem
        _run_cprofile(
            args,
            lambda: _run_analyze_once(cfg, args.check or None, get_enabled_analyzers_fn=enabled_fn),
            output_stem=output_stem,
        )
        return

    started_at = perf_counter()
    result = collect_run_checks_result(
        cfg,
        args.check or None,
        iter_loaded_projects_fn=_ITER_LOADED_PROJECTS_NO_RESULT_CACHE,
        get_enabled_analyzers_fn=enabled_fn,
    )
    wall_ms = (perf_counter() - started_at) * 1000.0
    print(f"wall_ms={wall_ms:.2f} instrumented_ms={_instrumented_ms(result):.2f}")
    _print_analyzer_report(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    ast_parser = subparsers.add_parser("ast")
    ast_parser.add_argument("--file", required=True, help="Path to a .s file, relative to repo root")
    ast_parser.set_defaults(func=_cmd_ast)

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument(
        "--target",
        default=None,
        help="Target name under tests/fixtures/corpus/valid/ (or an override when --project is set)",
    )
    analyze_parser.add_argument(
        "--project",
        default=None,
        help="Path to an .slproj project file to profile (paths resolved relative to the project)",
    )
    analyze_parser.add_argument("--check", action="append", default=[], metavar="KEY", help="Analyzer key (repeatable)")
    analyze_parser.add_argument(
        "--all",
        action="store_true",
        help="Run every registered enabled batch-dispatch analyzer (all except the semantic layer)",
    )
    analyze_parser.set_defaults(func=_cmd_analyze)

    for sub in (ast_parser, analyze_parser):
        sub.add_argument("--cache", choices=["cold", "warm"], default="warm")
        sub.add_argument("--repeat", type=int, default=5)
        sub.add_argument("--cprofile", action="store_true", help="Dump a .pstats file instead of timing repeats")
        sub.add_argument("--output-dir", default="artifacts/profile", help="Where --cprofile writes .pstats files")

    args = parser.parse_args(argv)

    with TemporaryDirectory(prefix="sattlint-profile-cache-") as scratch_cache_dir:
        os.environ["XDG_CACHE_HOME"] = scratch_cache_dir
        args.func(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
