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
| [../../ARCHITECTURE.md](../../ARCHITECTURE.md) | Top-level domain map, layering | Active | All agents |
| (add domain-specific architecture docs here) | | | |

## Execution Plans

| Plan | Purpose | Status | Owner |
| ------ | --------- | -------- | ------- |
| [../exec-plans/tech-debt-tracker.md](../exec-plans/tech-debt-tracker.md) | Known technical debt | Active | Doc-gardening agent |
| (add active plans here as `../exec-plans/active/*.md`) | | | |

## References

| Doc | Purpose | Status | Owner |
| ----- | --------- | -------- | ------- |
| [../references/cli-commands.md](../references/cli-commands.md) | Canonical CLI scripts and major command usage | Active | CLI docs |

## Verification Status

- [x] `AGENTS.md` under 100 lines
- [x] `ARCHITECTURE.md` exists at root
- [x] `docs/design-docs/core-beliefs.md` exists
- [x] `docs/design-docs/index.md` exists
- [x] `docs/exec-plans/tech-debt-tracker.md` exists
- [x] `docs/quality-score.md` created
- [x] `docs/references/` with llms.txt files
- [x] Doc-gardening agent (`sattlint-doc-gardener`)
- [ ] Coverage threshold ≥ 40% (TD-004)

## Adding New Docs

1. Create doc in appropriate `docs/` subdirectory
2. Add entry to this index with status and owner
3. Link from `AGENTS.md` if globally relevant
4. Update verification status when complete
