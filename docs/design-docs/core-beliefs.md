# Core Beliefs - Golden Principles for SattLint

Agent-first principles that keep this codebase legible, consistent, and maintainable.

## Governance

### 0. If It Cannot Be Enforced, It Will Drift (Meta-Principle)

Every important rule should map to:

- lint rule
- CI check
- automated agent review
- or required PR template item

### 2. AGENTS.md Is Table of Contents, Not Encyclopedia

- Keep it short and pointed — a table of contents, not an encyclopedia
- Point to deeper docs, don't duplicate them
- Update only on material change to architecture/invariants

## Enforcement

### 10. No Silent Fallbacks

Failures must be explicit and actionable.

- Parser: clear error messages with remediation hints
- Analyzers: confidence levels, not guesswork

### Enforcement Mechanisms

Every principle must have enforcement:

- Architecture boundaries → `tests/test_dependency_guard.py`
- Doc freshness → reviewed during each exec-plan pass (no automated stale-doc scanner)
- Casefold enforcement → `tests/test_casefolding_guard.py`
- Shared utility reuse → shared helpers live in `src/sattlint/analyzers/shared/` and `src/sattlint/utils/`; duplication is caught in review (no automated detector)
- File size → reviewed during each exec-plan pass (no mechanical cap)

## Repository Knowledge

### 1. Repository Knowledge Is System of Record

Knowledge lives in-repo or it doesn't exist for agents.

- No external docs (Google Docs, Slack threads, oral tradition)
- Design decisions → `docs/design-docs/`
- Plans → `docs/exec-plans/`
- Tech debt → tracked in `docs/exec-plans/` (active plans and follow-ups)

## Docs Rot

### 11. Docs Rot Is Technical Debt

Stale documentation is worse than no documentation.

- Docs are checked for staleness during each exec-plan pass (see `docs/exec-plans/release-1.0-and-doc-alignment.md`); links must be valid; dead links are lint errors
- Version docs with code (same PR when behavior changes)
- Links must be valid; dead links are lint errors

## Security

### 12. Security By Default

No secrets, PII, or machine-specific paths in outputs.

- Redact by type/category, not raw values
- Report `SQHJ`-style paths as sensitive
- Prefer repo-relative paths in all artifacts

## Architecture

### 7. Strict Boundaries, Local Autonomy

Enforced architecture with freedom inside boundaries.

- Parser core never imports application code
- CLI/TUI → Core → Analyzers/Engine → Parser (dependency direction)
- Within a module, agent has freedom of expression

### 8. Machine-Readable Outputs

Reports serve both humans and agents.

- Findings: structured (severity, confidence, location)
- Logs: key=value, issue-scoped
- No pretty-printed tables that hide structure

## Boundaries

### 4. Parse, Don't Validate

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

Key insight: Parsing subsumes validation. When you parse, you don't need to validate separately—the validation is a natural side effect of construction.

## Shared Utilities

### 5. Shared Utilities Over Hand-Rolled Helpers

Centralize invariants in shared code.

- Common patterns → `src/sattlint/core/` or the external `sattline-parser` package
- Don't replicate logic across analyzers
- When in doubt, refactor to shared utility

## Complexity

### 16. Namespaces and File Structure

Filesystem is the agent's primary interface.

- Treat directory structure as an interface
- Name files descriptively: `billing/compute.py` over `utils/helpers.py`
- Prefer many small well-scoped files
- Small files reduce truncation risk in context loading

### 17. Complexity Budget

- Max file size: 500 lines preferred, 800 hard cap
- Max function size: 50 lines preferred
- Max cyclomatic complexity thresholds
- Refactor before extending oversized modules
- Large files trigger decomposition PRs

## Typing

### 14. End-to-End Static Types

Eliminate illegal states through typing.

- Every data layer has typed representation (AST, config, DB)
- OpenAPI contracts for external APIs
- Types shrink the search space of possible actions

### 26. Objects Over Dicts/Tuples

Typed objects (dataclasses/classes) over ad-hoc dicts/tuples for data shapes.

- Named attribute access, never positional/numeric indexing (`item.value`, never `item[0]`)
- Multi-value returns are typed result objects, not tuples
- No "stringly-typed" dicts with magic keys (extends #4)
- Invalid states are unrepresentable by construction (see #4)

### 27. Strict Typing by Default

Prefer the strictest sound typing the codebase supports.

- Touched files stay Pyright strict-clean
- Eliminate avoidable `Any`; `Any` is a documented, justified exception, not a default
- Typed boundaries over loose `dict[str, object]` plumbing

## Development Workflow

### 13. Fast Ephemeral Dev Environments

Agent workflow spawns many processes. Make it cheap.

- One command creates fresh environment
- Worktree-per-feature when working with agents
- Ports, caches, DBs must be configurable or conflict-free

## Testing

### 6. Case-Insensitive Identifiers Everywhere

SattLine identifiers are case-insensitive.

- Compare with `.casefold()` always
- Tests must cover mixed-case scenarios
- No silent case-sensitive shortcuts

### 9. Tests Are Contracts

Tests document expected behavior; failures are spec violations.

- New feature → new test (same PR)
- Changing behavior → update tests (same PR)
- No disabling tests to make suite pass

### 15. Tests Are Executable Proof (Refined)

100% coverage is a phase change.

- 100% line coverage target
- Mutation testing for critical paths
- Behavior-focused tests over superficial execution
- Coverage is necessary, not sufficient
- At 95% you're making decisions about "important enough"
- At 100% there's no ambiguity—if a line isn't covered, you just added it
- Coverage report becomes the todo list
- Tests force the agent to demonstrate behavior, not just "seem right"

## Change Isolation

### 18. Local Change Radius

AI can unintentionally create broad regressions.

- PRs should minimize touched files
- Refactors separate from behavior changes
- Mechanical changes isolated
- Broad rewrites require explicit justification
- Agents should prefer smallest viable delta

## AI Optimization

### 3. Progressive Disclosure

Agents start with small, stable entry point (`AGENTS.md`), follow pointers to depth.

- `AGENTS.md` -> `docs/public/architecture.md` -> domain-specific docs
- Subsystem instructions in `.github/instructions/*.md`
- Never dump 1000-line manual into context

### 19. Deterministic Style

- One formatter only
- One import sorter
- One type checker
- One test framework
- No style debates in PRs
- Generated code must be reproducible

### 20. Minimize Cognitive Surface Area

- Prefer explicit APIs over implicit conventions
- Avoid deep inheritance
- Avoid metaprogramming unless essential
- Avoid "magic" registries without clear contracts
- Every subsystem should have:
  - clear entrypoint
  - clear invariants
  - bounded context

### 21. Observable by Default

- Structured logs
- Reproducible failures
- Debug artifacts
- Explainable analyzer outputs
- Every major decision path traceable

### 22. Dependency Skepticism

- Prefer stdlib first
- New dependency requires explicit justification
- Every dependency adds:
  - maintenance burden
  - security risk
  - context complexity
- Remove unused dependencies aggressively

### 23. One Path Forward

- Deprecated paths must have removal timelines
- No parallel architectures without sunset plan
- Temporary compatibility layers documented
- Dead code removal prioritized

### 29. Typed Dispatch Over Reflection

Typed callables over `getattr`/attribute-name strings for dispatch.

- Analyzer execution and command routing use statically typed callables
- No runtime reflection for dispatch when a typed callable works
- Avoid "magic" registries without clear contracts (see #20)

## Quality

### 25. Root Cause Before Remedy

- Symptom fixes incomplete without cause analysis
- Solve bug classes, not individual bugs
- Shared solutions preferred over local patches
- Repeated issue classes trigger architectural review
- Every fix must reduce future issue probability

### 28. Right Solution, Not Safe Solution

Do the correct, root-cause fix even when a compatibility shim lands faster.

- "Safe" workarounds that preserve the wrong shape are deferred debt
- No new compatibility seam without a removal timeline (see #23)
- Delete indirection rather than relocate it
- Change callers rather than preserving obsolete internal APIs

## Agent Guardrails

### 24. Agent Guardrails

- No speculative refactors without evidence
- No deleting unfamiliar code without replacement validation
- No broad renames without dependency analysis
- No TODO placeholders in merged code
- Uncertainty must be surfaced explicitly
