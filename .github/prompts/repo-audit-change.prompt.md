---
description: "Change repo audit checks, pipeline artifacts, or public-readiness scans in SattLint using the repo-audit specialist"
name: "Repo Audit Change"
argument-hint: "Describe repo-audit or pipeline change to make"
agent: "Repo Audit"
---

# Repo Audit Change

Investigate and implement the requested repo-audit or analysis-pipeline change in SattLint.

## Requirements

- Read `.git/sattlint-ai-coordination/current_work_lock.json` before first edit and claim exact touched files before the first edit.
- Extend existing audit or pipeline seams instead of adding parallel registries or artifact formats.
- Keep outputs machine-readable and actionable.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) and matching repo-audit instructions.
- Report changed files, validation run, and any artifact or contract changes that downstream checks must absorb.
