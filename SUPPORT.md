# Support

SattLint is maintained by a single developer. Support is provided through
GitHub only, on a best-effort basis. There is no paid support, no service-level
agreement, and no private email channel.

## Stable surface

The stable surface is the behavior documented in `README.md` and
`FEATURE_GUIDE.md`. Changes to it are recorded in `CHANGELOG.md`.

- Installation from PyPI on Windows and Linux with Python 3.13 or newer.
- The interactive shell started by running `sattlint` with no arguments,
  including the views and keyboard shortcuts documented in `README.md`.
- The headless commands documented in `FEATURE_GUIDE.md`:
  `project show`, `analyzers list`, `analyze`, `findings`, and `show`.
- Their documented flags, the JSON `schema_version` envelope, NDJSON records,
  and the documented exit codes.
- `.slproj` project files and the configuration keys documented in `README.md`.
- The documented finding labels and stable finding IDs.

Compatibility is expected within a release line, but SattLint uses calendar
versioning, not semantic versioning. Read the changelog before upgrading a
pinned dependency.

## Preview surface

The preview surface may change between releases without a deprecation cycle.
If it breaks for you, open an issue, but pin a version if you depend on it.

- Anything not documented in `README.md` or `FEATURE_GUIDE.md`.
- Run history, cache files, and report artifacts under the configured cache and
  output directories.
- Interactive shell layout, wording, and key bindings beyond what `README.md`
  documents.
- Report and Change Review artifact formats.
- The internal Python package (`sattlint.*`) as an import surface. Use the CLI
  for automation.

## Issue routing

- Bug in a stable or preview surface: open a
  [bug report](https://github.com/SorenHJohansen/SattLint/issues/new?template=bug_report.md).
- Feature request: open a
  [feature request](https://github.com/SorenHJohansen/SattLint/issues/new?template=feature_request.md).
- Usage question: open a
  [question](https://github.com/SorenHJohansen/SattLint/issues/new?template=question.md)
  or start a
  [discussion](https://github.com/SorenHJohansen/SattLint/discussions).
- Security vulnerability: follow
  [SECURITY.md](SECURITY.md) and report privately.
- Language grammar, parsing, and parser-owned validation: report against
  [sattline-parser](https://github.com/SorenHJohansen/sattline-parser/issues).
  SattLint consumes that library and does not own the grammar.

## What is out of scope

- Analysis of SattLine programs you cannot share a safe sample of.
- Support for Python versions below 3.13 or for operating systems other than
  Windows and Linux.
- Custom builds, forks, and local patches.
- Requests to add findings or change analyzer policy without a reproducible
  sample that shows the current behavior is wrong.

## Response expectations

Issues are triaged when time allows. A good report, with a version, a minimal
sample, and the exact command, is usually answered faster than a description
of symptoms. Fixes ship in the next release rather than as ad hoc builds.
