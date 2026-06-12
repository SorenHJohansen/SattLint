# AI Check Catalog

Generated from the pipeline and repo-audit check registries.
Regenerate with `python -m sattlint.devtools.ai --write`.

## Pipeline Checks

### `ruff`

- Label: Run Ruff
- Owner surface: python-style
- Estimated cost: low
- AI summary: Use after touched Python edits for fast style, import-order, and lint hygiene proof.
- AI instruction files:
  - `.github/instructions/sattline-invariants.instructions.md`
- Owner tests:
  - `tests/test_pipeline_run.py`
- Command: `sattlint-analysis-pipeline --profile full --check ruff --output-dir artifacts/generated/ai-work-map/pipeline`

### `pyright`

- Label: Run pyright
- Owner surface: python-types
- Estimated cost: low
- AI summary: Use when touched Python files need static type proof before widening to broader finish gates.
- AI instruction files:
  - `.github/instructions/sattline-invariants.instructions.md`
- Owner tests:
  - `tests/test_pipeline_run.py`
- Command: `sattlint-analysis-pipeline --profile full --check pyright --output-dir artifacts/generated/ai-work-map/pipeline`

### `pytest`

- Label: Run pytest
- Owner surface: python-tests
- Estimated cost: medium
- AI summary: Use targeted owner pytest first for behavior proof on Python changes.
- AI instruction files:
  - `.github/instructions/sattline-invariants.instructions.md`
  - `.github/instructions/python-tests.instructions.md`
- Owner tests:
  - `tests/test_pipeline_run.py`
  - `tests/test_pipeline_run_recommendations.py`
- Command: `sattlint-analysis-pipeline --profile full --check pytest --output-dir artifacts/generated/ai-work-map/pipeline`

### `vulture`

- Label: Run Vulture
- Owner surface: dead-code
- Estimated cost: medium
- AI summary: Use when dead-code proof is relevant for Python infra or audit-facing changes.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_pipeline_run.py`
- Command: `sattlint-analysis-pipeline --profile full --check vulture --output-dir artifacts/generated/ai-work-map/pipeline`

### `bandit`

- Label: Run Bandit
- Owner surface: security
- Estimated cost: medium
- AI summary: Use when security-sensitive Python edits need static security scan proof.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_pipeline_run.py`
- Command: `sattlint-analysis-pipeline --profile full --check bandit --output-dir artifacts/generated/ai-work-map/pipeline`

### `structural-reports`

- Label: Collect structural reports
- Owner surface: structural
- Estimated cost: high
- AI summary: Use when architecture, dependency, or structural-budget artifacts need regeneration.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_pipeline_collection_graphs.py`
  - `tests/test_pipeline_run.py`
- Command: `sattlint-analysis-pipeline --profile full --check structural-reports --output-dir artifacts/generated/ai-work-map/pipeline`

### `trace`

- Label: Collect trace report
- Owner surface: trace
- Estimated cost: medium
- AI summary: Use when parser, analyzer, or workspace-loading edits need trace or profiling artifacts.
- AI instruction files:
  - `.github/instructions/parser-analysis.instructions.md`
  - `.github/instructions/workspace-lsp.instructions.md`
- Owner tests:
  - `tests/test_pipeline_phase2.py`
- Command: `sattlint-analysis-pipeline --profile full --check trace --output-dir artifacts/generated/ai-work-map/pipeline`

### `corpus`

- Label: Run corpus suite
- Owner surface: corpus
- Estimated cost: high
- AI summary: Use when parser or analyzer changes need corpus-level regression proof.
- AI instruction files:
  - `.github/instructions/parser-analysis.instructions.md`
  - `.github/instructions/test-fixtures.instructions.md`
- Owner tests:
  - `tests/parser/test_corpus.py`
- Command: `sattlint-analysis-pipeline --profile full --check corpus --output-dir artifacts/generated/ai-work-map/pipeline`

## Repo Audit Checks

### `text-scan`

- Label: Scan repository text for leaks and local paths
- Owner surface: text-scan
- Estimated cost: low
- AI summary: Use when documentation or Python sources may have leaked local paths, secrets, or unsafe text.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part1.py`
- Command: `sattlint-repo-audit --profile full --check text-scan --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `local-ci-parity`

- Label: Detect local-versus-CI parity drift in paths, test guards, and local dependency roots
- Owner surface: local-ci-parity
- Estimated cost: low
- AI summary: Use when changes may rely on local-only paths, guards, or machine-specific assumptions.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part1.py`
- Command: `sattlint-repo-audit --profile full --check local-ci-parity --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `documented-commands`

- Label: Check documented commands against implemented CLI surfaces
- Owner surface: cli-docs
- Estimated cost: low
- AI summary: Use when CLI help, command docs, or agent reference commands must stay in sync with implementation.
- AI instruction files:
  - `.github/instructions/cli-app.instructions.md`
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part1.py`
- Command: `sattlint-repo-audit --profile full --check documented-commands --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `unused-config-keys`

- Label: Report declared but unused config keys
- Owner surface: config
- Estimated cost: low
- AI summary: Use when config declarations or config consumers change and unused keys may drift.
- AI instruction files:
  - `.github/instructions/cli-app.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part1.py`
- Command: `sattlint-repo-audit --profile full --check unused-config-keys --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `architecture`

- Label: Run repository architecture checks
- Owner surface: architecture
- Estimated cost: medium
- AI summary: Use when Python architecture, import layering, or module-size constraints may shift.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part1.py`
  - `tests/test_repo_audit_part2.py`
- Command: `sattlint-repo-audit --profile full --check architecture --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `structural-report`

- Label: Translate structural report findings into repo-audit findings
- Owner surface: structural
- Estimated cost: medium
- AI summary: Use when structural budget artifacts or their translation into findings may change.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part4.py`
- Command: `sattlint-repo-audit --profile full --check structural-report --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `cli`

- Label: Validate CLI descriptions and subcommand help
- Owner surface: cli
- Estimated cost: low
- AI summary: Use when CLI parser descriptions, subcommand help, or interactive command surfaces change.
- AI instruction files:
  - `.github/instructions/cli-app.instructions.md`
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part1.py`
- Command: `sattlint-repo-audit --profile full --check cli --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `logging`

- Label: Check library modules for unexpected print calls
- Owner surface: logging
- Estimated cost: low
- AI summary: Use when library code changes may introduce unexpected prints or weak failure-path diagnostics.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part1.py`
- Command: `sattlint-repo-audit --profile full --check logging --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `ai-gc`

- Label: Report stale AI-generated artifacts and oversized local coordination state
- Owner surface: ai-hygiene
- Estimated cost: low
- AI summary: Use when AI-generated artifacts, coordination state, or related cleanup policy changes.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part7.py`
- Command: `sattlint-repo-audit --profile full --check ai-gc --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `ignored-repo-paths`

- Label: Detect ignored repo-local dependency references
- Owner surface: path-safety
- Estimated cost: low
- AI summary: Use when repo-local ignored paths or hidden dependency roots may leak into tracked code.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part2.py`
- Command: `sattlint-repo-audit --profile full --check ignored-repo-paths --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `harness-freshness`

- Label: Enforce AI harness freshness for instructions, agents, links, and generated maps
- Owner surface: harness-freshness
- Estimated cost: low
- AI summary: Use when AI instructions, agents, generated routing maps, or other AI-control surfaces change.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_ai_work_map.py`
  - `tests/test_repo_audit_part5.py`
- Command: `sattlint-repo-audit --profile full --check harness-freshness --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `coverage`

- Label: Translate low-coverage modules into audit findings
- Owner surface: coverage
- Estimated cost: low
- AI summary: Use when coverage artifacts or audit-facing coverage recommendations may change.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part1.py`
  - `tests/test_repo_audit_part3.py`
- Command: `sattlint-repo-audit --profile full --check coverage --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `public-readiness`

- Label: Check public-repository readiness files and metadata
- Owner surface: public-readiness
- Estimated cost: low
- AI summary: Use when top-level repo hygiene, public metadata, or publish-facing docs may drift.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part3.py`
- Command: `sattlint-repo-audit --profile full --check public-readiness --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `verify-recommendations`

- Label: Verify recommendation metadata and routing catalog coverage
- Owner surface: recommendations
- Estimated cost: low
- AI summary: Use when routing catalogs, recommendation metadata, or generated AI registry outputs change.
- AI instruction files:
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_pipeline_run.py`
  - `tests/test_repo_audit_part8.py`
  - `tests/test_recommendation_routing.py`
- Command: `sattlint-repo-audit --profile full --check verify-recommendations --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`

### `cli-consistency`

- Label: Build the full CLI consistency report
- Owner surface: cli-docs
- Estimated cost: low
- AI summary: Use when CLI consistency reporting or command-reference alignment changes.
- AI instruction files:
  - `.github/instructions/cli-app.instructions.md`
  - `.github/instructions/repo-audit.instructions.md`
- Owner tests:
  - `tests/test_repo_audit_part7.py`
- Command: `sattlint-repo-audit --profile full --check cli-consistency --skip-pipeline --fail-on high --output-dir artifacts/generated/ai-work-map`
