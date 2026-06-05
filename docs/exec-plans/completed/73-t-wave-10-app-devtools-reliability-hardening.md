# T-Wave-10 App and Devtools Reliability Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

Several high and medium severity reliability bugs were found in the app CLI and devtools surface during the 2026-06-02 code review. This plan fixes them as a group because they share a common theme: subtle control-flow gaps where error states silently succeed, destructive operations lack guards, or shared utilities produce outputs incompatible with the platform they run on.

After this work lands:

- Quoted git porcelain paths (paths with spaces or non-ASCII characters) are correctly parsed by `_detect_changed_files`, so `--recommend-checks`, `--check-my-changes`, and finish-gate routing no longer silently miss affected files.
- `repo_audit_entrypoints._shell_command` produces POSIX-safe command strings on Linux, consistent with the `_pipeline_finish_gate.py` side that already uses `shlex.join`.
- `_path_size_bytes` in `ai_gc.py` has the same `OSError` guard as its sibling `_path_mtime`, so AI GC report generation does not crash when files disappear between discovery and stat.
- `telemetry-summary` does not require a valid config file â€” it bypasses config loading when the command is `telemetry-summary`, matching the behavior the handler already implements by deleting `cfg` immediately.
- Staged repo-audit runs clean up their temp directory when readiness validation fails, preventing orphaned temp trees from accumulating under `artifacts/`.
- The `coordination_lock_state` TOCTOU window is closed: the lock file is only deleted if it still contains the current PID.

## Progress

- [x] Read `src/sattlint/devtools/_pipeline_execution.py` lines 97â€“130 to understand the full `_detect_changed_files` implementation and the test coverage at `tests/test_pipeline_owner_coverage.py:147`.
- [x] Fix `_detect_changed_files` to unquote git porcelain-quoted paths. Git quotes paths that contain spaces, `\n`, `\t`, `"`, or non-ASCII bytes using C-style quoting (surrounding double quotes + backslash escapes). Detect whether a path segment is quoted (starts with `"`) and apply `codecs.decode(inner, "unicode_escape")` or equivalent unquoting before adding to `changed_files`.
- [x] Add test cases to `test_pipeline_owner_coverage.py` (or its nearest test file) for porcelain output lines containing a quoted path with a space and a quoted path with a non-ASCII character, asserting both are correctly extracted.
- [x] Fix `repo_audit_entrypoints._shell_command` at `src/sattlint/devtools/repo_audit_entrypoints.py:61` to use `shlex.join` instead of `subprocess.list2cmdline`. Add `import shlex` at the top of that file if not already present.
- [x] Fix `_path_size_bytes` in `src/sattlint/devtools/ai_gc.py` to add `try/except OSError: continue` around `child.stat().st_size` inside the rglob loop, matching the `_path_mtime` pattern immediately below.
- [x] Fix `telemetry-summary` to skip config loading. In `src/sattlint/cli/entry.py`, move `telemetry-summary` out of the `command in (...)` config-loading block. Handle it before the block: check `if command == "telemetry-summary"` before the config load attempt and dispatch directly to `run_telemetry_summary_command_fn` with `config_path=resolved_config_path` and the format/output args. Remove `"telemetry-summary"` from the `command in (...)` set.
- [x] Fix `run_staged_repo_audit` in `src/sattlint/devtools/repo_audit_runs.py` to clean up the staged temp directory when readiness validation raises. Wrap the `readiness_check(staged_output_dir)` call in a `try/except` and call `shutil.rmtree(staged_output_dir, ignore_errors=True)` in the except branch before re-raising.
- [x] Fix the `_hold_lock` TOCTOU in `src/sattlint/devtools/coordination_lock_state.py`. After `os.close(lock_fd)`, before calling `lock_path.unlink`, read the current PID from the lock file and only unlink if the file still contains the current process's PID. If the file is missing or contains a different PID, skip the unlink.
- [x] Write or extend focused regression tests for: porcelain path unquoting (new cases in pipeline tests), `_path_size_bytes` OSError resilience (new case in ai_gc tests or devtools tests), `telemetry-summary` bypasses config loading (assert it succeeds even when config path is invalid).
- [x] Run `pyright` over touched production files and confirm zero type errors. A broader run that included touched test files still reported pre-existing strict-typing noise in `tests/test_cli.py` unrelated to this plan.
- [x] Run the full test suite and confirm no regressions.

## Surprises & Discoveries

- Git porcelain quoting for non-ASCII paths is byte-oriented, so decoding via a Python `bytes` literal was the simplest local fix. Parsing the quoted text as `b"..."` preserved octal escapes such as `\303\270`, which then decoded cleanly to UTF-8 filenames like `søren/file.s`.
- The explicit CLI proof for `telemetry-summary` with `--config /dev/null` reached the telemetry handler immediately and reported `Telemetry file not found: /dev/telemetry.jsonl`, which confirmed the config-load bypass. The command currently exits `2` for that missing-file case, but it no longer fails in config loading.
- A touched-file `pyright` run that included tests surfaced long-standing strict-typing noise in `tests/test_cli.py`. Restricting the proof to the touched production files showed `0 errors`, which is the relevant signal for this plan's code changes.

## Decision Log

- Decision: fix all six issues in one plan rather than splitting them.
  Rationale: all six issues are small, localized, and do not interact with each other. Grouping them avoids six separate plans with overlapping validation steps and simplifies the reviewer's diff surface. Each fix is contained to one or two lines.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: use `shlex.join` for `_shell_command` rather than a conditional that chooses `shlex.join` on Linux and `list2cmdline` on Windows.
  Rationale: this is an AI-only repo. The review explicitly notes that the current `list2cmdline` output is "a bad fit for an AI-only repo that expects agents to reuse those commands verbatim." The pipeline side already uses `shlex.join`. Consistency on the Linux/AI-first platform outweighs theoretical Windows compatibility for AI-facing report strings.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

- Decision: for the lock file TOCTOU fix, read the file and compare PID rather than using `fcntl.flock`.
  Rationale: switching the lock implementation from `O_CREAT | O_EXCL` to `fcntl.flock` would change the observable contract of the lock (the file contains a PID; `flock` uses a file descriptor held open). The minimal fix is a read-and-compare before unlink. This closes the TOCTOU window without changing the lock protocol.
  Date/Author: 2026-06-02 / Copilot (Claude Sonnet 4.6)

## Outcomes & Retrospective

- All six reliability fixes landed in one pass without widening beyond the named helper seams.
- Focused regression tests now cover: quoted git porcelain paths with spaces and non-ASCII bytes, staged repo-audit cleanup on readiness failure, AI GC stat races, POSIX shell command rendering, telemetry-summary config bypass, and the lock-file unlink guard.
- Validation evidence: focused pytest slice passed (`83 passed`), touched production-file `pyright` passed (`0 errors, 0 warnings, 0 informations`), and the full repo test suite passed (`2644 passed, 34 warnings`).

## Context and Orientation

This plan touches six files across the app CLI and devtools layers.

**Porcelain path quoting** (`_pipeline_execution.py:117â€“124`): git `status --porcelain` outputs one line per changed file. The format is two-character status code followed by a space and then the path. When the path contains special characters (spaces, backslashes, non-ASCII bytes, and others), git wraps it in double quotes and uses C-style escape sequences inside. The current parser slices `raw_line[3:]` and looks for `" -> "` to detect renames, but it does not check whether the resulting path is quoted. This means filenames like `"my file.s"` become `my file.s` (correct) only if the parser happens to strip the outer quotes, but the current code does not: it adds the raw text including the quotes to `changed_files`. The correct fix is: if `path_text.startswith('"')` and `path_text.endswith('"')`, unquote by stripping the outer quotes and interpreting the inner `\n`, `\t`, `\\`, `\"`, and octal sequences.

**`list2cmdline` vs `shlex.join`** (`repo_audit_entrypoints.py:61`): `subprocess.list2cmdline` is a Windows-specific formatter. On Linux it escapes with backslashes in a way that is only correct for `cmd.exe`, not `sh` or `bash`. The `_pipeline_finish_gate.py:22` side already uses `shlex.join`. Fixing `repo_audit_entrypoints._shell_command` to use `shlex.join` makes both sides consistent and ensures AI-facing report strings are valid shell.

**`_path_size_bytes` missing OSError guard** (`ai_gc.py:60â€“72`): the function uses `path.rglob("*")` to discover files and then calls `child.stat().st_size`. If a file is deleted between discovery and stat, `stat()` raises `FileNotFoundError` (a subclass of `OSError`). The sibling `_path_mtime` has `try/except OSError: continue` around the same pattern. Adding the same guard to `_path_size_bytes` makes them consistent.

**`telemetry-summary` config dependency** (`entry.py:274`, `app_cli_commands.py:181`): the CLI currently routes `telemetry-summary` through the config-loading block. However, `run_telemetry_summary_command` immediately does `del cfg` â€” it does not use the config at all. Its only path dependency is `telemetry_output_path_fn(config_path)`, which derives the telemetry file path from the config file path, not from the parsed config contents. So a malformed or absent config should not prevent the telemetry inspector from running. Moving `telemetry-summary` out of the config-loading block fixes this. The `config_path` (the raw path string) is available before config loading.

**Staged run temp-dir leak** (`repo_audit_runs.py:108â€“118`): `run_staged_repo_audit` calls `build_staging_output_dir` to create a temp directory, then immediately calls `readiness_check`. If readiness raises an exception, the temp directory is never removed. The fix is to wrap `readiness_check` in a `try/except BaseException` and remove the staging dir in the handler before re-raising.

**Lock file TOCTOU** (`coordination_lock_state.py:160â€“163`): after `os.close(lock_fd)` and before `lock_path.unlink(missing_ok=True)`, another process can legitimately acquire the lock (creating a new file at the same path with its own PID). The `unlink` then removes that process's live lock file. The fix is to read the lock file content immediately before unlinking and compare it to `str(os.getpid())`. Only unlink if the file still contains the current PID. Use `missing_ok=True` already in place for the case where the file was removed externally.

## Plan of Work

Fix the six issues in order of their impact.

For `_detect_changed_files` in `_pipeline_execution.py`: after stripping `raw_line[3:]`, check `if path_text.startswith('"') and path_text.endswith('"')`. If so, strip the outer quotes and decode the inner string using `bytes(path_text[1:-1], "raw_unicode_escape").decode("unicode_escape")` â€” or simpler, use `ast.literal_eval(path_text)` which already handles Python's C-style string literals (which match git's quoting format exactly for the ASCII-escape portion). Verify the rename case still works: in `a -> b`, both `a` and `b` may independently be quoted; split on `" -> "` first, then unquote each part.

For `repo_audit_entrypoints._shell_command`: replace `subprocess.list2cmdline(command)` with `shlex.join(command)`. Add `import shlex` to the import block if absent.

For `_path_size_bytes` in `ai_gc.py`: add `try/except OSError: continue` around `total += child.stat().st_size` inside the rglob loop.

For `telemetry-summary` in `entry.py`: remove `"telemetry-summary"` from the tuple in the `if command in (...)` line. Add a new block before the config-loading block (after the `--list-checks` early exit at line 268):

    if command == "telemetry-summary":
        if run_telemetry_summary_command_fn is None:
            raise RuntimeError("telemetry-summary handler is required")
        return _exit_code(
            run_telemetry_summary_command_fn(
                {},
                config_path=resolved_config_path,
                output_format=getattr(args, "format", "text"),
                output_path=getattr(args, "output", None),
            ),
            fallback=exit_success,
        )

Note: `run_telemetry_summary_command` does `del cfg` immediately, so passing an empty dict `{}` is safe for the no-config path.

For `repo_audit_runs.py`: in `run_staged_repo_audit`, wrap the `readiness_check` call:

    try:
        readiness_report = readiness_check(staged_output_dir)
    except BaseException:
        shutil.rmtree(staged_output_dir, ignore_errors=True)
        raise

For `coordination_lock_state.py`'s `_hold_lock` finally block: replace `lock_path.unlink(missing_ok=True)` with:

    try:
        current_pid_text = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        current_pid_text = ""
    if current_pid_text == str(os.getpid()):
        lock_path.unlink(missing_ok=True)

## Concrete Steps

Run all commands from the repository root.

After fixing `_detect_changed_files`, verify the fix with a synthetic test:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/ -k "detect_changed_files or pipeline_owner" -x -q --tb=short

After fixing `telemetry-summary`, verify it works without a real config:

    bash scripts/run_repo_python.sh -m sattlint --config /dev/null telemetry-summary 2>&1 || echo "exit $?"

Expected: either a "Telemetry file not found" message (correct â€” no telemetry file exists) and exit 1, or a successful summary. It must NOT crash with a config-load error.

Run pyright over all touched files:

    bash scripts/run_repo_python.sh -m pyright \
      src/sattlint/devtools/_pipeline_execution.py \
      src/sattlint/devtools/repo_audit_entrypoints.py \
      src/sattlint/devtools/ai_gc.py \
      src/sattlint/devtools/repo_audit_runs.py \
      src/sattlint/devtools/coordination_lock_state.py \
      src/sattlint/cli/entry.py

Run the full test suite:

    bash scripts/run_repo_python.sh -m pytest --no-cov -x -q --tb=short

## Validation and Acceptance

Acceptance is met when all of the following are true:

1. A synthetic porcelain line `XY "path with spaces/file.s"` is correctly parsed to `path with spaces/file.s` by `_detect_changed_files`.
2. `_shell_command(["python", "-m", "sattlint"])` returns `python -m sattlint` (POSIX quoting, no Windows backslashes).
3. `_path_size_bytes` does not raise when a file in an rglob result is deleted before stat.
4. `sattlint telemetry-summary` (with an absent or broken config) exits with "Telemetry file not found", not a config-load error.
5. A failed `readiness_check` in `run_staged_repo_audit` does not leave a temp directory under `artifacts/`.
6. `pyright` and `pytest --no-cov -x` both pass over all touched files.

## Idempotence and Recovery

All fixes are localized two-to-five line changes. Each can be reverted independently. The lock TOCTOU fix adds a read before unlink; if the read fails with OSError (e.g., NFS or race), the guard treats the file as owned by another process and skips the unlink, which is the conservative-safe outcome.

## Artifacts and Notes

The six issues by location:

    High:    _pipeline_execution.py:117-124  â€” quoted porcelain paths silently wrong
    High:    repo_audit_entrypoints.py:61    â€” list2cmdline produces Windows escaping on Linux
    High:    ai_gc.py:60-68                  â€” _path_size_bytes missing OSError guard
    Medium:  entry.py:274                    â€” telemetry-summary unnecessarily blocked by config load
    Medium:  repo_audit_runs.py:108-118      â€” staged run leaks temp dir on readiness failure
    Medium:  coordination_lock_state.py:160  â€” TOCTOU between close() and unlink()

## Interfaces and Dependencies

No public API changes. All fixes are internal to the devtools and CLI layers. The `telemetry-summary` behavior change is visible to users only in the "broken config" case â€” it now works instead of failing.
