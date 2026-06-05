# Design Docs Index

Index of design documents, verification status, and owner hints.
Part of harness-engineering progressive disclosure strategy.

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
| (add domain-specific architecture docs here) | | | |

## Execution Plans

| Plan | Purpose | Status | Owner |
| ------ | --------- | -------- | ------- |
| `docs/exec-plans/` archive | Historical execution plans are no longer kept as checked-in design-doc links in this index. | Retired | Maintainers |

## References

| Doc | Purpose | Status | Owner |
| ----- | --------- | -------- | ------- |
| [../references/cli-commands.md](../references/cli-commands.md) | Canonical CLI scripts and major command usage | Active | CLI docs |

## Verification Status

- [x] `AGENTS.md` under 100 lines
- [x] `docs/public/architecture.md` is the canonical architecture doc
- [x] `ARCHITECTURE.md` exists as a compatibility pointer
- [x] `docs/design-docs/core-beliefs.md` exists
- [x] `docs/design-docs/index.md` exists
- [x] `docs/exec-plans/completed/` remains as the retained archive directory
- [x] `docs/quality-score.md` created
- [x] `docs/references/` with llms.txt files
- [x] Doc-gardening agent (`sattlint-doc-gardener`)
- [ ] Coverage threshold >= 40% (TD-004)

## Adding New Docs

1. Create doc in appropriate `docs/` subdirectory
2. Add entry to this index with status and owner
3. Link from `AGENTS.md` if globally relevant
4. Update verification status when complete
