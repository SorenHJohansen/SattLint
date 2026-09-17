# Analyzer Guardrail Fixtures

These fixtures are intentionally narrow. Each file targets one analyzer feature family so new analyzer work can add or update tests without editing broad sample programs.

- `CyclomaticComplexityHigh.s`: high-complexity equation-block control flow.
- `ScanLoopCost.s`: scan-cycle resource usage in equation-block code.
