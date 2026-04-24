---
description: "Fix or change DOCX generation, documentation classification, FS grouping, unit scope selection, or documentation workflows using the docgen specialist"
name: "Documentation Generation Change"
argument-hint: "Describe documentation-generation change to make"
agent: "Documentation Generation"
---
Investigate and implement the requested documentation-generation change in SattLint.

Requirements:
- Read `.github/coordination/current-work.md` before first edit and claim touched files when useful.
- Anchor on `src/sattlint/docgenerator/` or the nearest app or GUI docgen entry point instead of broad repo exploration.
- Preserve existing classification and scope boundaries unless the request explicitly changes them.
- Choose the first focused validation route from [validation map](../skills/validation-routing/references/validation-map.md) and matching docgen instructions.
- Report changed files, validation run, and any classification, artifact, or workflow behavior that callers must absorb.
