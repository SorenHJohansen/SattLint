# Pull Request

## Summary

- What changed and why:
- Linked issue, if any:

## Scope check

- [ ] The change addresses one concern and keeps the diff to the smallest
      useful size.
- [ ] Analyzer behavior outside the stated scope is unchanged.
- [ ] No SattLine source outside this repository was edited.
- [ ] No customer names, private paths, or internal identifiers were added to
      prose, fixtures, tests, or commit messages.

## Verification

- [ ] Focused test or command for the changed surface
- [ ] `python -m pre_commit run --all-files`
- [ ] `python -m ruff check .`
- [ ] `python -m ruff format --check .`
- [ ] `python -m pyright src/sattlint tests`
- [ ] `python -m pytest -q --tb=short`
- [ ] `python scripts/check_docs.py` when Markdown changed

Commands run:

```text
paste commands here
```

## Tests and fixtures

- [ ] New behavior has a test that fails without the change.
- [ ] Fixtures are minimal and safe to publish.
- [ ] CLI payloads, finding labels, and their tests still agree.

## Compatibility

- [ ] CLI flags, JSON `schema_version`, exit codes, and documented labels are
      unchanged, or the change is recorded in `CHANGELOG.md`.
- [ ] `.slproj` keys remain backward compatible, or the change is recorded.

## Documentation

- [ ] `README.md`, `FEATURE_GUIDE.md`, or `docs/` updated for user-facing
      changes.
- [ ] `CHANGELOG.md` has an entry under `[Unreleased]`.
- [ ] No dash punctuation was added to prose.

## Generated files

- [ ] No build output, cache directory, or coverage report was edited by hand.
- [ ] `uv.lock` was regenerated with `uv lock` when dependencies changed.

## Risks

- Remaining risk:
