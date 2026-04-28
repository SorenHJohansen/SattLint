# Core Beliefs - Golden Principles for SattLint

Agent-first principles that keep this codebase legible, consistent, and maintainable.
Violations trigger the doc-gardening agent to open fix-up PRs.

## 1. Repository Knowledge Is System of Record

Knowledge lives in-repo or it doesn't exist for agents.
- No external docs (Google Docs, Slack threads, oral tradition)
- Design decisions → `docs/design-docs/`
- Plans → `docs/exec-plans/`
- Tech debt → `docs/exec-plans/tech-debt-tracker.md`

## 2. AGENTS.md Is Table of Contents, Not Encyclopedia

- Keep under 100 lines (enforced by lint)
- Point to deeper docs, don't duplicate them
- Update only on material change to architecture/invariants

## 3. Progressive Disclosure

Agents start with small, stable entry point (`AGENTS.md`), follow pointers to depth.
- `AGENTS.md` → `ARCHITECTURE.md` → domain-specific docs
- Subsystem instructions in `.github/instructions/*.md`
- Never dump 1000-line manual into context

## 4. Parse, Don't Validate

Data shapes validated at boundaries (parser, config, analyzer inputs).
- Use AST models, not dicts with magic keys
- Validate early, fail clearly, no silent fallbacks
- `sattlint syntax-check` is strict by design

**Construction-time parsing**: Transform data into stronger types at construction, not at validation.
- Use `__post_init__` in dataclasses to parse and normalize on construction
- Make invalid states unrepresentable by construction
- If parsing fails, fail immediately with clear error—don't return "invalid" objects

**Example** (validate):
```python
def validate(x):
    if not is_valid(x):
        raise ValueError("invalid")
    return x  # caller must check or risk runtime error
```

**Example** (parse - preferred):
```python
@dataclass
class ParsedX:
    value: int
    
    def __post_init__(self):
        if self.value < 0:
            raise ValueError("value must be non-negative")
        self.value = abs(self.value)  # normalize
```

Key insight: Parsing subsumes validation. When you parse, you don't need to
validate separately—the validation is a natural side effect of construction.

## 5. Shared Utilities Over Hand-Rolled Helpers

Centralize invariants in shared code.
- Common patterns → `src/sattlint/core/` or `src/sattline_parser/`
- Don't replicate logic across analyzers
- When in doubt, refactor to shared utility

## 6. Case-Insensitive Identifiers Everywhere

SattLine identifiers are case-insensitive.
- Compare with `.casefold()` always
- Tests must cover mixed-case scenarios
- No silent case-sensitive shortcuts

## 7. Strict Boundaries, Local Autonomy

Enforced architecture with freedom inside boundaries.
- Parser core never imports application code
- LSP → Core → Analyzers/Engine → Parser (dependency direction)
- Within a module, agent has freedom of expression

## 8. Machine-Readable Outputs

Reports serve both humans and agents.
- Findings: structured (severity, confidence, location)
- Artifacts: JSON in `artifacts/`
- Logs: key=value, issue-scoped
- No pretty-printed tables that hide structure

## 9. Tests Are Contracts

Tests document expected behavior; failures are spec violations.
- New feature → new test (same PR)
- Changing behavior → update tests (same PR)
- No disabling tests to make suite pass

## 10. No Silent Fallbacks

Failures must be explicit and actionable.
- Parser: clear error messages with remediation hints
- Analyzers: confidence levels, not guesswork
- LSP: degrade only in documented ways (unavailable deps, dirty buffers)

## 11. Docs Rot Is Technical Debt

Stale documentation is worse than no documentation.
- Doc-gardening agent scans for stale docs weekly
- Version docs with code (same PR when behavior changes)
- Links must be valid; dead links are lint errors

## 12. Security By Default

No secrets, PII, or machine-specific paths in outputs.
- Redact by type/category, not raw values
- Report `SQHJ`-style paths as sensitive
- Prefer repo-relative paths in all artifacts

## 15. Fast Ephemeral Dev Environments

Agent workflow spawns many processes. Make it cheap.
- One command creates fresh environment
- Worktree-per-feature when working with agents
- Ports, caches, DBs must be configurable or conflict-free

## 16. End-to-End Static Types

Eliminate illegal states through typing.
- Every data layer has typed representation (AST, config, DB)
- OpenAPI contracts for external APIs
- Types shrink the search space of possible actions

## 17. Tests Are Executable Proof

100% coverage is a phase change.
- At 95% you're making decisions about "important enough"
- At 100% there's no ambiguity—if a line isn't covered, you just added it
- Coverage report becomes the todo list
- Tests force the agent to demonstrate behavior, not just "seem right"

## 18. Namespaces and File Structure

Filesystem is the agent's primary interface.
- Treat directory structure as an interface
- Name files descriptively: `billing/compute.py` over `utils/helpers.py`
- Prefer many small well-scoped files
- Small files reduce truncation risk in context loading
