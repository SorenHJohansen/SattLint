# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses calendar versioning (`vYYYY.M.number`) to match
`sattline-parser`.

## [Unreleased]

### Added

- Change Review: a TUI-only semantic diff and impact analysis between the
  official and draft versions of a configured project, producing a compact
  JSON + Markdown review artifact. Triggered from the Analyze view via the
  `Generate Change Review` button; output directory configured through the
  App Settings `review.output_dir` setting.

## [2026.9.2] - 2026-09-10

### Fixed

- The released wheel was missing `sattlint/ui/app_textual.tcss`, so a bare
  `sattlint` invocation (interactive Textual shell) crashed with
  `FileNotFoundError`. The UI stylesheet is now declared as package data so it
  ships in the wheel.
- Added a clean-wheel smoke check (`import sattlint.ui.app_textual`) to the
  Linux, Windows, and publish gates so missing package data fails CI instead of
  breaking installs after release.

## [2026.9.1] - 2026-09-09

### Added

- Strict single-file syntax validation via the `syntax-check` CLI command.
- Configurable heuristic static analysis (`analyze`) over `.slproj` project files.
- `.slproj` project scaffolding via `sattlint init`, explicit `--project PATH`,
  and auto-discovery from the current working directory.
- ICF validation and graphics-rule analysis.
- Textual interactive UI for guided setup, analysis, and tools workflows.
- Config validation (`validate-config`) and cache pruning (`cache-prune`).
- Single-source package version export via `sattlint.__version__`.
- CLI `--version` support.
- Release and security repository metadata.

## [0.1.1] - 2026-04-23

### Added

- Static analysis and parser validation for SattLine projects.
- Non-interactive `syntax-check` CLI command for strict single-file validation.
- Analysis pipeline entry points.

### Notes

- This entry establishes the changelog baseline for future tagged releases.

[2026.9.2]: https://github.com/SorenHJohansen/SattLint/releases/tag/v2026.9.2
[2026.9.1]: https://github.com/SorenHJohansen/SattLint/releases/tag/v2026.9.1
