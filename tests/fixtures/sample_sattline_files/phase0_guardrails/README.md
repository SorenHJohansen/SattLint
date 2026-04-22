# Phase 0 Guardrail Fixtures

These fixtures are intentionally narrow. Each file targets one Wave 1 feature family so new analyzer work can add or update tests without editing broad sample programs.

- `CyclomaticComplexityHigh.s`: high-complexity equation-block control flow.
- `NamingRoleMismatch.s`: variable naming-style drift.
- `ParameterDrift.s`: divergent literal parameter mappings across instances.
- `RequiredParameterConnection.s`: used module parameter left unmapped.
- `ScanLoopCost.s`: scan-cycle resource usage in equation-block code.
