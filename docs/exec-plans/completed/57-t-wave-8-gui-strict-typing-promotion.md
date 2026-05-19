# T-Wave-8 GUI Strict Typing Promotion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes all 19 files under `src/sattlint_gui` strict-clean under Pyright and promotes them into `tool.pyright.strict`. After this work lands, `src/sattlint_gui` will be the last unpromoted root, `tool.sattlint.typing_ratchet.strict_roots` can be widened to include it, and the repo will be exactly one config change away from collapsing `pyproject.toml` to `typeCheckingMode = "strict"` globally (via the global-strict ratchet path introduced alongside this plan).

The observable proof is that all 19 GUI files pass `pyright` under strict mode with 0 errors, all focused GUI and analyzer tests remain green, and `pyproject.toml` is updated with the new strict entries plus a matching approval record under `.github/approvals/ratchet-rebaseline-*.md`.

## Progress

- [x] Capture the live baseline: the current worktree no longer matches the original 204-error snapshot; the first fresh strict probe showed 112 GUI errors, then 94 after the first owner-file fixes.
- [x] Fix the tkinter annotation gaps in `src/sattlint_gui/frames/config_frame.py` (current worktree: 6 strict errors, now 0).
- [x] Fix the dynamic app-binding facade in `src/sattlint_gui/binding.py` (current worktree: 19 strict errors, now 0).
- [x] Fix the callback and worker typing gaps in `src/sattlint_gui/frames/analyze_frame.py` (current worktree: 22 strict errors, now 0).
- [x] Fix the shared analyzer checklist widget in `src/sattlint_gui/widgets/analyzer_list.py` (current worktree: 15 strict errors, now 0).
- [x] Fix the remaining frame files: `tools_frame.py`, `results_frame.py`, `docs_frame.py`, and `sidebar.py` are strict-clean; `analyze_frame.py` stayed clean after the shared widget fixes.
- [x] Fix the support files: `widgets/console.py`, `widgets/report_view.py`, `widgets/target_list.py`, and `window.py` are strict-clean; `binding.py` and `widgets/analyzer_list.py` remain clean.
- [x] Update `pyproject.toml` to add the 19 GUI files to `tool.pyright.strict`, add `src/sattlint_gui` to `tool.sattlint.typing_ratchet.strict_roots`, and add the approval record.
- [x] Run focused validation: `bash scripts/run_repo_python.sh -m pyright src/sattlint_gui`, `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_gui.py -x -q --tb=short`, `bash scripts/run_repo_python.sh -m ruff check src/sattlint_gui`, and `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short` all passed.
- [x] Collapse `pyproject.toml` to `typeCheckingMode = "strict"` globally and remove the explicit strict list.

## Surprises & Discoveries

- The attached plan baseline was stale against the live worktree. The first fresh strict probe found 112 GUI errors, not 204, and `config_frame.py` had already shrunk from the planned 92 errors to 6.
- The dominant remaining GUI strict failures still match the plan's qualitative diagnosis: tkinter callback and widget APIs expose loosely typed members, so focused parent annotations plus narrow `cast()` helpers clear the errors without changing behavior.
- `binding.py` is now a strict-clean typed facade over `sattlint.app`; the controlling fix was an explicit app-module protocol plus typed helpers for the legacy underscore methods, not broader GUI changes.
- After the shared-widget fixes landed, the remaining package-level strict probe fell to only `sidebar.py` and `window.py`; both were resolved with minimal tkinter parent and method-call typing helpers, and the package now passes strict pyright end to end.
- The broader `tests/ -k "gui or sattlint_gui"` command pulled in an unrelated `sattlint.docgenerator.classification` import seam during collection, so the focused GUI proof was routed to `tests/test_gui.py`, which passed after restoring the config-frame helper seam used by the SimpleNamespace-based doubles.

## Decision Log

- Decision: execute GUI cleanup in file-size order (largest-cluster-first).
  Rationale: `config_frame.py` alone accounts for 45 % of all errors; fixing it first unblocks the most downstream annotation gaps.
  Date/Author: 2026-05-19 / Copilot (Claude Sonnet 4.6)
- Decision: keep the global-strict collapse as a separate optional final step.
  Rationale: collapsing to `typeCheckingMode = "strict"` touches a protected path with different approval semantics than the per-file promotion; separating the steps keeps each reviewable.
  Date/Author: 2026-05-19 / Copilot (Claude Sonnet 4.6)

## Outcomes & Retrospective

- The GUI package is strict-clean in the live worktree, and the repo has now completed the optional follow-up collapse to global `typeCheckingMode = "strict"` for `src`.
- The explicit `tool.pyright.strict` list and `tool.sattlint.typing_ratchet.strict_roots` entries were removed after a temporary global-strict probe and the checked-in `pyproject.toml` both proved clean.
- Focused proof passed for the GUI slice, the collapsed global strict config, GUI-targeted pytest, GUI Ruff, and the ratchet-policy pytest suite.

## Context and Orientation

The 19 GUI owner files and their current strict error counts:

| File | Strict errors |
|---|---|
| `src/sattlint_gui/frames/config_frame.py` | 92 |
| `src/sattlint_gui/frames/analyze_frame.py` | 22 |
| `src/sattlint_gui/binding.py` | 18 |
| `src/sattlint_gui/widgets/analyzer_list.py` | 15 |
| `src/sattlint_gui/frames/tools_frame.py` | 14 |
| `src/sattlint_gui/frames/results_frame.py` | 13 |
| `src/sattlint_gui/frames/docs_frame.py` | 12 |
| `src/sattlint_gui/widgets/console.py` | 4 |
| `src/sattlint_gui/widgets/report_view.py` | 4 |
| `src/sattlint_gui/widgets/target_list.py` | 4 |
| `src/sattlint_gui/frames/sidebar.py` | 3 |
| `src/sattlint_gui/window.py` | 3 |
| Other GUI files | 0 |

Error-rule breakdown across all 204 errors:

| Rule | Count |
|---|---|
| `reportUnknownArgumentType` | 58 |
| `reportUnknownMemberType` | 57 |
| `reportUnknownParameterType` | 27 |
| `reportUnknownVariableType` | 21 |
| `reportMissingParameterType` | 20 |
| `reportUnknownLambdaType` | 9 |
| `reportMissingTypeArgument` | 8 |
| Other | 4 |

The dominant pattern is tkinter API surfaces returning `Any` or untyped. The fix strategy is to add explicit `cast()` calls, narrow typed locals, and annotate callback/command parameters rather than attempting to wrap the tkinter stubs.

This plan does NOT touch the ratchet machinery — that was updated separately in the same wave (see the global-strict ratchet change shipped alongside this plan). Once this plan is complete, the ratchet will accept either the per-file list or the collapsed global-strict config.

## Concrete Steps

Run all commands from the repository root.

**1. Probe current error baseline:**

```bash
python3 -c "
import tempfile, json, subprocess, os
cfg = {'include': ['src/sattlint_gui'], 'typeCheckingMode': 'strict',
       'pythonVersion': '3.13', 'venvPath': '.', 'venv': '.venv',
       'extraPaths': ['src'], 'reportMissingTypeStubs': False}
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, dir='.') as f:
    json.dump(cfg, f); tmp = f.name
result = subprocess.run(['bash', 'scripts/run_repo_python.sh', '-m', 'pyright', '--outputjson', '--project', tmp],
                        capture_output=True, text=True)
os.unlink(tmp)
data = json.loads(result.stdout)
errors = [d for d in data.get('generalDiagnostics', []) if d['severity'] == 'error']
print(len(errors), 'errors')
for e in errors[:30]:
    print(e['file'].split('src/')[-1], e['range']['start']['line']+1, e.get('rule'), e['message'][:80])
"
```

**2. Fix GUI files in cluster order (largest first).**

Preferred fixes:

- Add explicit `cast(SomeType, widget.cget(...))` when tkinter getters return `Any`.
- Annotate `command=` and event-callback parameters with `Callable[..., None]` or the narrowest type that satisfies the slot.
- Replace bare `lambda` with typed `def` helpers when the lambda body has untyped bindings.
- Use `Final[str]` for string constants.

**3. After all 204 errors are gone, run the proof:**

```bash
bash scripts/run_repo_python.sh -m pyright src/sattlint_gui
bash scripts/run_repo_python.sh -m pytest --no-cov tests/ -k "gui or sattlint_gui" -x -q --tb=short
bash scripts/run_repo_python.sh -m ruff check src/sattlint_gui
```

**4. Update `pyproject.toml`:**

- Add all 19 `src/sattlint_gui/**/*.py` paths to `tool.pyright.strict`.
- Add `"src/sattlint_gui"` to `tool.sattlint.typing_ratchet.strict_roots`.
- Add `.github/approvals/ratchet-rebaseline-<date>-gui.md`.

**5. Run ratchet proof:**

```bash
bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short
```

**6. Optional global-strict collapse (separate approval):**

If all files in all roots are clean, replace the explicit strict list with:

```toml
[tool.pyright]
include = ["src"]
typeCheckingMode = "strict"
pythonVersion = "3.13"
venvPath = "."
venv = ".venv"
extraPaths = ["src"]
reportMissingTypeStubs = false
```

And remove `tool.sattlint.typing_ratchet.strict_roots` (the ratchet accepts global-strict mode once `typeCheckingMode = "strict"` and no `strict` list is present).
