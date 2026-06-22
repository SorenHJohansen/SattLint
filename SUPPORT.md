# SattLint Support

This document explains what is currently supported, where to ask for help, and when to use a public issue versus a private security report.

## Start here

Before opening an issue, check:

- the [public support matrix](docs/references/public-support-matrix.md) for stable, preview, and internal-only surfaces
- the [README](README.md) for install and command examples
- the [security policy](SECURITY.md) if the problem might expose credentials, private code, or another vulnerability

## What is supported

The current stable support contract is intentionally small:

- Windows and Linux
- Python 3.13+
- `sattlint --version`
- `sattlint syntax-check`
- `sattlint repo-audit`
- `sattlint-lsp`

Preview surfaces such as the interactive menu, GUI, broader config-driven workflows, and the local VS Code client are still useful, but they do not yet carry the same compatibility promise or response expectation.

## Which path to use

| Need | Route |
| --- | --- |
| Bug in a stable or preview feature | Open a GitHub issue with the bug template |
| Feature idea or product feedback | Open a GitHub issue with the feature request template |
| Usage question or uncertainty about stable vs preview scope | Read this file and the support matrix first, then open an issue if the docs still do not answer it |
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
- **Preview surfaces**: Features documented as preview may change or be removed without a deprecation cycle. Their status is documented in the [public support matrix](docs/references/public-support-matrix.md).
- **Migration path**: When a stable feature is deprecated, the CHANGELOG entry includes a migration path or recommended alternative.
