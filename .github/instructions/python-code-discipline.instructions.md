---
description: "Use when changing Python implementation or tests in SattLint. Covers dead-code discipline, getattr boundaries, module cohesion, and side-effect documentation."
name: "Python Code Discipline"
applyTo: ["src/**/*.py", "tests/**/*.py", "scripts/**/*.py"]
---
# Python Code Discipline

- Delete dead code instead of parking unused helpers, flags, or compatibility branches. If a symbol must stay for dynamic discovery or external entry points, make that seam explicit with a test, export, or documented caller rather than leaving it looking unused.
- Use `getattr` only at real dynamic or optional boundaries. Do not use it to dodge typed contracts, hide required attributes, or silently substitute for a direct field access that the owning type should expose.
- Keep modules cohesive: extend the nearest owning seam before adding another cross-module helper, and do not mix unrelated responsibilities in one file just to avoid a new module.
- Call out meaningful side effects in code and tests when a function mutates shared state, caches, diagnostics, threads, environment variables, files, or process state. Side-effect-heavy helpers should make their writes and teardown obligations obvious at the call site.
