---
description: "Change repo audit checks, pipeline artifacts, or public-readiness scans in SattLint using the repo-audit specialist"
name: "Repo Audit Change"
argument-hint: "Describe repo-audit or pipeline change to make"
agent: "Repo Audit"
---
Investigate and implement the requested repo-audit or analysis-pipeline change in SattLint.

Requirements:
- Read `.github/coordination/current-work.md` before first edit and claim touched files when useful.
- Extend existing audit or pipeline seams instead of adding parallel registries or artifact formats.
- Keep outputs machine-readable and actionable.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) and matching repo-audit instructions.
- Report changed files, validation run, and any artifact or contract changes that downstream checks must absorb.
