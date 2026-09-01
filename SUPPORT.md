# SattLint Support

This document is the single support contract for SattLint. It defines what is
supported, what is preview, what has been removed, where to ask for help, and
when to use a public issue versus a private security report. README, package
metadata, and feature guides link here rather than define competing matrices.

## Start here

Before opening an issue, check:

- the [README](README.md) for install and command examples
- the [security policy](SECURITY.md) if the problem might expose credentials, private code, or another vulnerability

## What is supported

| Surface | Status | Notes |
| --- | --- | --- |
| `sattlint --version` | Stable | Confirms the installed package boots and reports a version |
| `sattlint syntax-check` | Stable | Strict single-file syntax validation for SattLine source |
| `sattlint analyze` (`.slproj` project analysis) | Stable | Analyzes a program or library with its dependencies using the heuristic analyzers |
| ICF and graphics analysis | Stable | Validates and formats ICF files and checks graphics rules |
| Textual interactive UI | Preview | Guided setup and menu-driven analysis workflows; layout and wording may evolve |
| `sattlint validate-config`, `sattlint cache-prune`, `sattlint format-icf` | Preview | Config-driven helpers that are useful today but not part of the smallest stable contract |

- **Platforms:** Windows and Linux with Python 3.13 or newer. macOS contributor workflows may work but are not part of the stable contract.
- **Configuration:** `.slproj` project files and `~/.config/sattlint/config.toml` (or `%APPDATA%\sattlint\config.toml`).
- **Public Python API:** importing `sattlint` from Python is supported; details are covered in [docs/public/python-api.md](docs/public/python-api.md). Internal modules may change without notice.

## Removed surfaces

The following surfaces are intentionally not part of SattLint and should not be
used:

- **Language Server Protocol (LSP)** / `sattlint-lsp` — removed
- **DOCX documentation generation** — removed
- **Repository audit** (`sattlint repo-audit`) — removed
- **Simulation and telemetry-summary commands** — removed

## Which path to use

| Need | Route |
| --- | --- |
| Bug in a stable or preview feature | Open a GitHub issue with the bug template |
| Feature idea or product feedback | Open a GitHub issue with the feature request template |
| Usage question or uncertainty about stable vs preview scope | Read this file first, then open an issue if the docs still do not answer it |
| Security vulnerability, secret leak, or private-path exposure | Follow [SECURITY.md](SECURITY.md) and report it privately |

## What to include in a good report

Include as much of this as you can:

- SattLint version from `sattlint --version`
- install method (`pipx`, editable install, or source checkout)
- operating system and Python version
- the exact command you ran
- a minimal reproduction or sample file if it is safe to share
- expected behavior and actual behavior

## Response expectations

- Stable-surface bugs are the highest priority for public follow-up.
- Preview-surface issues are handled on a best-effort basis and may be resolved by narrowing the documented preview scope instead of preserving exact behavior.
- Internal-only files and AI coordination surfaces may change without compatibility notice.

## Deprecation Policy

SattLint follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Once a feature is part of the stable public surface, the following rules apply:

- **Deprecation notice**: A feature scheduled for removal is announced in the CHANGELOG with the version in which it became deprecated. A runtime deprecation warning may be emitted when applicable.
- **Minimum support window**: A deprecated stable feature remains functional for at least one minor release after the deprecation announcement.
- **Major version bumps**: Breaking changes are reserved for major version releases (e.g., 1.x → 2.0). A minor release may introduce deprecation warnings but must not break the stable API or CLI contract.
- **Preview surfaces**: Features documented as preview may change or be removed without a deprecation cycle. Their status is documented in the "What is supported" table above.
- **Migration path**: When a stable feature is deprecated, the CHANGELOG entry includes a migration path or recommended alternative.
