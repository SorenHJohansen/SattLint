# Design Docs Index

Index of design documents and owner hints.

## Core Principles

| Doc | Purpose | Status | Owner |
| ----- | --------- | -------- | ------- |
| [core-beliefs.md](core-beliefs.md) | Golden principles, agent legibility rules | Active | All agents |
| [index.md](index.md) | This file | Active | All agents |

## Architecture

| Doc | Purpose | Status | Owner |
| ----- | --------- | -------- | ------- |
| [../public/architecture.md](../public/architecture.md) | Canonical high-level architecture summary | Active | All agents |
| [../../ARCHITECTURE.md](../../ARCHITECTURE.md) | Compatibility pointer for legacy links | Active | All agents |
| [../exec-plans/architecture-upgrade-plan.md](../exec-plans/architecture-upgrade-plan.md) | Unified architecture upgrade plan (merged app-layer + reliability refactor) | Active | All agents |
| [../exec-plans/analyzer-execution-refactor.md](../exec-plans/analyzer-execution-refactor.md) | Deferred registry/execution refactors (Phases R1–R4) | Deferred | All agents |
| [../exec-plans/release-1.0-and-doc-alignment.md](../exec-plans/release-1.0-and-doc-alignment.md) | Release 1.0 blockers, doc alignment, Part C/D cleanup | Active | All agents |
| [../exec-plans/library-resolution-and-config-cleanup.md](../exec-plans/library-resolution-and-config-cleanup.md) | Library resolution + config surface cleanup | Implemented | All agents |
| [../exec-plans/tests-cleanup-and-hardening.md](../exec-plans/tests-cleanup-and-hardening.md) | Tests layout + confidence hardening | Complete | All agents |
| [../exec-plans/enforcement-gaps.md](../exec-plans/enforcement-gaps.md) | Missing enforcement (casefold, coverage) + enforcement-section reconciliation | Active | All agents |
| [analyzer-performance-architecture.md](analyzer-performance-architecture.md) | Analyzer performance & extensibility plan (layered pipeline, cached foundation) | Proposed | All agents |

## Adding New Docs

1. Create doc in appropriate `docs/` subdirectory
2. Add entry to this index with status and owner
3. Link from `AGENTS.md` if globally relevant
