---
description: "Fix a parser, grammar, transformer, analyzer, or strict-validation issue in SattLint using the parser specialist"
name: "Parser Fix"
argument-hint: "Describe parser or validation bug to fix"
agent: "Parser Analysis"
---

# Parser Fix

Investigate and fix the requested parser or strict-validation issue in SattLint.

## Requirements

- Read `.git/sattlint-ai-coordination/current_work_lock.json` before first edit and claim exact touched files before the first edit.
- Anchor on the controlling parser, transformer, analyzer, or validation code path instead of broad repo exploration.
- Preserve strict-validation semantics unless the requested behavior explicitly changes them.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) and matching parser instructions.
- Report the changed files, validation run, and any preserved invariants that were at risk.
