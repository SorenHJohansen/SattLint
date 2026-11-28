# SattLint Documentation

This directory is the canonical documentation set for SattLint. It explains
what the tool does, how the code is organized, how a run travels through the
pipeline, and how to keep the documentation itself correct.

Every page is versioned with the code. When behavior, configuration, command
output, or architecture changes, update the page that owns that behavior in the
same pull request.

## Start here

| Page | Read it when you want to |
| --- | --- |
| [Overview](overview.md) | Understand what SattLint is, who it serves, and how the pieces fit. |
| [Getting started](getting-started.md) | Install SattLint, create a project, and run the first analysis. |
| [Project files](project-files.md) | Write or review a `.slproj` file and understand every setting. |
| [Configuration](configuration.md) | Understand the user configuration, defaults, merging, and validation. |
| [CLI reference](cli.md) | Automate SattLint with the headless commands and stable output contracts. |
| [Adopting SattLint in CI](consumer-ci.md) | Add SattLint to a team pipeline with SARIF, a baseline, and review artifacts. |
| [Analyzers](analyzers.md) | Choose analyzers, understand what each one reports, and add your own. |

## How SattLint works

| Page | Read it when you want to |
| --- | --- |
| [Architecture](architecture.md) | See the layers, module ownership, dependency direction, and runtime entry points. |
| [Project loading](project-loading.md) | Follow a target from `.slproj` to a loaded semantic project graph. |
| [Analysis pipeline](analysis-pipeline.md) | Follow a selected analyzer through loading, execution, findings, and run storage. |
| [Resolution and semantics](resolution-and-semantics.md) | Understand symbols, record types, scopes, aliases, and access tracking. |
| [Caching and runs](caching-and-runs.md) | Understand cache keys, invalidation, cache safety, and run history. |
| [Change Review](change-review.md) | Understand the official-versus-draft semantic review capability. |
| [Interactive UI](interactive-ui.md) | Use the Textual shell and understand how it drives the application layer. |

## Working on SattLint

| Page | Read it when you want to |
| --- | --- |
| [Development](development.md) | Set up the environment, follow the code rules, and add an analyzer. |
| [Testing](testing.md) | Find the right test, fixture, and validation command for a change. |
| [CI and release](ci-and-release.md) | Understand the workflows, gates, packaging, and release process. |
| [Documentation maintenance](documentation.md) | Add or update documentation and keep the docs checks green. |
| [Troubleshooting](troubleshooting.md) | Diagnose installation, configuration, loading, cache, UI, and review problems. |
| [Glossary](glossary.md) | Resolve a SattLine or SattLint term quickly. |

## Related root documents

- [README](../README.md) is the short product introduction.
- [Feature Guide](../FEATURE_GUIDE.md) is the compact headless command reference.
- [Architecture summary](../ARCHITECTURE.md) is the short architectural overview.
- [Contributing](../CONTRIBUTING.md) covers contribution and release workflow.
- [Support](../SUPPORT.md) defines the stable and preview surfaces.
- [Changelog](../CHANGELOG.md) records released behavior.
- [Security policy](../SECURITY.md) explains private vulnerability reporting.

## Documentation contract

The documentation set is part of the product, not an afterthought.

- **Behavior changes update docs in the same pull request.** A changed flag,
  configuration key, output field, exit code, finding label, or architecture
  boundary is not complete until its page is updated.
- **Every page is reachable from this index.** The docs checker fails when a
  Markdown file under `docs/` is not linked from this page.
- **Relative links and heading anchors must resolve.** The docs checker follows
  relative links to files and validates `#fragment` anchors against the target
  page's headings.
- **Markdown style is checked by markdownlint.** Use dash bullets, ordered list
  prefixes, fenced code blocks with a language, and a blank line around
  headings, lists, and fences.
- **Historical records stay historical.** A plan that intentionally names
  removed paths lives under `docs/` and is listed in the historical section
  below, but it is not a live description of the current product.

Run the checks locally before pushing:

```bash
python scripts/check_docs.py
python -m pre_commit run --all-files
```

CI runs the same link and index checks in the `Docs` job, and markdownlint
runs against every Markdown file listed in `.markdownlint-cli2.jsonc`.

## Historical records

These documents record past parser-upgrade planning. They are kept for context
and may reference paths or designs that no longer exist.

- [Parser upgrade plan](parser-upgrade-plan.md)
- [Parser upgrade plan for the 2026.11.5 release](parser-upgrade-plan-2026.11.5.md)
