# Pull Request

## Summary

- Task ID:
- Branch:
- Worktree:
- Handoff: `.ai/handoffs/<task-id>.json`

## Validation

- [ ] `python scripts/run_ai_edit_gate.py` ran for touched Python files, or Ruff-on-save handled the same fixes
- [ ] Focused owner validation ran
- [ ] `python -m pre_commit run --all-files` ran
- [ ] `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` ran
- [ ] Context health still passes when AI-control files changed

Commands run:

```text
paste commands here
```

## Risks

- Remaining risk 1

## Reviewer Notes

- Architecture or security follow-up
