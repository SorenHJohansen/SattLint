# T-Wave-8 GUI Strict Typing Promotion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes all 19 files under `src/sattlint_gui` strict-clean under Pyright and promotes them into `tool.pyright.strict`. After this work lands, `src/sattlint_gui` will be the last unpromoted root, `tool.sattlint.typing_ratchet.strict_roots` can be widened to include it, and the repo will be exactly one config change away from collapsing `pyproject.toml` to `typeCheckingMode = "strict"` globally (via the global-strict ratchet path introduced alongside this plan).

The observable proof is that all 19 GUI files pass `pyright` under strict mode with 0 errors, all focused GUI and analyzer tests remain green, and `pyproject.toml` is updated with the new strict entries plus a matching approval record under `.github/approvals/ratchet-rebaseline-*.md`.

## Progress

- [ ] Capture the live baseline: 204 strict-mode errors across 13 files, dominated by `reportUnknownArgumentType` (58), `reportUnknownMemberType` (57), and `reportUnknownParameterType` (27).
- [ ] Fix the tkinter annotation gaps in `src/sattlint_gui/frames/config_frame.py` (92 errors, the largest cluster).
- [ ] Fix the remaining frame files: `analyze_frame.py` (22), `tools_frame.py` (14), `results_frame.py` (13), `docs_frame.py` (12), `sidebar.py` (3).
- [ ] Fix the support files: `binding.py` (18), `widgets/analyzer_list.py` (15), `widgets/console.py` (4), `widgets/report_view.py` (4), `widgets/target_list.py` (4), `window.py` (3), plus the 1-error cluster in `frames/analyze_frame.py`.
- [ ] Update `pyproject.toml` to add the 19 GUI files to `tool.pyright.strict`, add `src/sattlint_gui` to `tool.sattlint.typing_ratchet.strict_roots`, and add the approval record.
- [ ] Run focused validation: `bash scripts/run_repo_python.sh -m pyright src/sattlint_gui`, focused GUI tests, touched-file Ruff, and ratchet-policy proof.
- [ ] Collapse `pyproject.toml` to `typeCheckingMode = "strict"` globally and remove the explicit strict list.

## Surprises & Discoveries

_Update as work proceeds._

## Decision Log

- Decision: execute GUI cleanup in file-size order (largest-cluster-first).
  Rationale: `config_frame.py` alone accounts for 45 % of all errors; fixing it first unblocks the most downstream annotation gaps.
  Date/Author: 2026-05-19 / Copilot (Claude Sonnet 4.6)
- Decision: keep the global-strict collapse as a separate optional final step.
  Rationale: collapsing to `typeCheckingMode = "strict"` touches a protected path with different approval semantics than the per-file promotion; separating the steps keeps each reviewable.
  Date/Author: 2026-05-19 / Copilot (Claude Sonnet 4.6)

## Outcomes & Retrospective

_Fill in after completion._

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
