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

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from sattline_parser import parse_source_file  # noqa: E402

from sattlint import (  # noqa: E402
    app,
    app_analysis,
)
from sattlint._app_analysis_checks import collect_run_checks_result  # noqa: E402
from sattlint.app_analysis import ChecksRunResult  # noqa: E402

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
            # Forces collect_stage_timings=True in _app_analysis_loading.py.
            "debug": True,
        }
    )
    return cfg


def _run_analyze_once(cfg: dict[str, object], selected_keys: list[str] | None) -> RunMetrics:
    started_at = perf_counter()
    result = collect_run_checks_result(  # type: ignore[arg-type]
        cfg,
        selected_keys,
        iter_loaded_projects_fn=_ITER_LOADED_PROJECTS_NO_RESULT_CACHE,
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


def _cmd_analyze(args: argparse.Namespace) -> None:
    cfg = _build_cfg(args.target)
    file_count = len(list(CORPUS_VALID_DIR.glob("*.s")))
    source_bytes = sum(f.stat().st_size for f in CORPUS_VALID_DIR.glob("*.s"))
    _print_run_header(
        target_or_file=args.target,
        extra={"program_dir_files": file_count, "program_dir_bytes": source_bytes},
        args=args,
    )

    def run_once() -> RunMetrics:
        return _run_analyze_once(cfg, args.check or None)

    if args.cprofile:
        _run_cprofile(args, run_once, output_stem=args.target)
    else:
        _run_baseline_repeats(args, run_once)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    ast_parser = subparsers.add_parser("ast")
    ast_parser.add_argument("--file", required=True, help="Path to a .s file, relative to repo root")
    ast_parser.set_defaults(func=_cmd_ast)

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--target", required=True, help="Target name under tests/fixtures/corpus/valid/")
    analyze_parser.add_argument("--check", action="append", default=[], metavar="KEY", help="Analyzer key (repeatable)")
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
