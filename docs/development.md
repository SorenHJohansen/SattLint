# Development

This page covers local setup, the working rules that shape the codebase, and the
first checks to run when changing SattLint. Test placement and CI details are in
[Testing](testing.md) and [CI and release](ci-and-release.md).

## Requirements

- Python 3.13 or newer.
- Git.
- `uv` for the locked development environment (recommended).
- A SattLine codebase when you need real-target behavior.

## Setup

```bash
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint
uv sync --locked --extra dev
```

Use `uv run` for commands so they use the locked environment:

```bash
uv run python -m pytest -q --tb=short
uv run ruff check .
uv run pyright src/sattlint tests
```

The fallback environment is:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The lockfile is authoritative in CI. Regenerate `uv.lock` with `uv lock` when
you change dependencies and commit it with the change.

## Repository layout

| Path | Contents |
| --- | --- |
| `src/sattlint/` | Product source. |
| `tests/` | Owner suites, regression tests, and fixtures. |
| `scripts/` | Repository tooling, including the docs checker and fuzzers. |
| `.github/` | Workflows, issue templates, pull request template, and scoped instruction files. |
| `docs/` | Canonical documentation. |
| `pyproject.toml` | Package metadata, dependencies, tool configuration. |
| `mise.toml` | Local tool versions. |
| `uv.lock` | Locked dependency graph. |

## Working rules

### Start from the owning seam

Find the file or symbol that owns the behavior. Change that seam instead of
patching a caller. Widen only when the local check passes.

### Keep changes local

- One concern per pull request.
- Prefer the smallest useful diff.
- Separate refactors from behavior changes.
- Do not delete unfamiliar code without understanding its replacement.
- No placeholder TODOs in merged code.

### Types and data shapes

- Production code outside `src/sattlint/ui/` is Pyright strict-clean.
- Prefer typed records and dataclasses over dictionaries and tuples.
- Use named attribute access, never positional indexing of a data shape.
- Return typed result objects instead of multi-value tuples.
- Avoid `Any`; when it is unavoidable, keep it at a boundary and document why.
- Dispatch with typed callables, not reflection or attribute-name strings.
- Make invalid states unrepresentable at construction.

The Textual shell is a deliberate Pyright carve-out. It drives dynamic widget
APIs that are not practical under strict typing; the full test suite exercises
it instead.

### Case-insensitive identifiers

SattLine identifiers are case-insensitive. Compare with `casefold()`, use the
shared casefolding helpers, and cover mixed-case behavior in tests.

### No silent fallbacks

Failures are explicit and actionable:

- a malformed project is rejected with a message that names the problem;
- a strict validation path raises the first structural error;
- an analyzer failure is recorded, not hidden;
- a cache miss is a miss, not a partially trusted result.

### Shared utilities before local copies

Look for an existing helper in `core/`, `analyzers/shared/`, or `utils/` before
adding a traversal, casefold comparison, or path helper. Extend the shared seam
when it is the right owner.

### File and function size

Prefer focused modules over one large file. Keep a module below roughly 500
lines when practical, treat 800 lines as a hard review trigger, and keep
functions short enough to read in one screen.

### Parser boundary

- The parser is an external package with an exact pin.
- `parser_api.py` is the single import surface for parser symbols.
- Do not add parser logic to SattLint.
- Do not change the parser pin without a deliberate AST migration and a review
  of the conversion layer.

### Documentation

Behavior changes update the page that owns the behavior in the same pull
request. See [Documentation maintenance](documentation.md).

## Local validation ladder

1. Focused test for the touched surface.
2. Ruff lint and format on the touched files.
3. Pyright on the touched files or on `src/sattlint tests`.
4. Pre-commit hygiene.
5. Full suite before pushing.

```bash
python -m pytest tests/<owner>/test_<topic>.py -q --tb=short
python -m ruff check <touched-files>
python -m ruff format --check <touched-files>
python -m pyright src/sattlint tests
python -m pre_commit run --all-files
python -m pytest -q --tb=short
```

See [Testing](testing.md) for the owner-suite map.

## Adding an analyzer

The registry is the single rule catalog.

1. Write the analyzer with a thin public `analyze_*` entry point.
2. Put implementation on a class or focused helper modules.
3. Add a declarative spec with key, name, description, category, scope, and
   context inputs.
4. Add delivery metadata with acceptance tests and shared-artifact ownership.
5. Add a focused owner test and a minimal fixture.
6. Update [Analyzers](analyzers.md) and any project examples that list keys.
7. Run the analyzer architecture tests.

A plugin analyzer uses the public registration API instead:

```python
from sattlint.analyzers.plugin import register_analyzer


@register_analyzer(key="my-check", name="My check")
def my_check(context):
    ...
    return report
```

The key must not collide with a built-in analyzer, and registration must happen
before the catalog is first built.

## Dependency policy

- Prefer the standard library.
- A new dependency needs a clear reason, a maintenance check, and a security
  review.
- `sattline-parser` is pinned exactly because its AST is a contract.
- Development tools are pinned to avoid formatter and type-checker drift.
- Remove unused dependencies aggressively.

## Pull requests

Before opening a pull request:

- run the focused check for the changed surface;
- run the full gate for source or test changes;
- update docs and the changelog for user-facing behavior;
- fill in the pull request template with commands run and remaining risk;
- keep customer names, private paths, and internal identifiers out of prose,
  fixtures, tests, and commits.

The repository is public. Describe behavior, not origin.

## Related pages

- [Testing](testing.md)
- [CI and release](ci-and-release.md)
- [Documentation maintenance](documentation.md)
- [Architecture](architecture.md)
