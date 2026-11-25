# Documentation Maintenance

Documentation is part of the product. Stale documentation is worse than
missing documentation because it teaches the wrong behavior with confidence.

## The contract

- `docs/` is the canonical documentation set.
- Root documents (`README.md`, `FEATURE_GUIDE.md`, `ARCHITECTURE.md`,
  `CONTRIBUTING.md`, `SUPPORT.md`) stay short and point into `docs/`.
- Every page is reachable from [docs/README.md](README.md).
- Behavior changes update the owning page in the same pull request.
- Released behavior changes also get a `CHANGELOG.md` entry.
- Historical plans are listed separately and are not treated as current
  behavior.

## The docs checker

`scripts/check_docs.py` runs in CI and can be run locally:

```bash
python scripts/check_docs.py
```

It checks:

1. **Relative link targets exist.** A link such as `[page](page.md)` or
   `[section](../README.md)` must resolve to a real path relative to the file
   that contains it.
2. **Heading anchors resolve.** A link such as `[rules](#rules)` or
   `[rules](other.md#rules)` must name a heading that exists in the target
   Markdown file. Anchors are computed with GitHub-style heading slugs,
   including duplicate-heading suffixes.
3. **Every docs page is indexed.** Every Markdown file under `docs/` must be
   linked from [docs/README.md](README.md). A new page that is not in the index
   fails the check.

The checker ignores:

- external URLs, `mailto:`, `tel:`, `ftp:`, and `git@` targets;
- fenced code blocks and inline code spans, so examples are not treated as
  links;
- historical parser-upgrade plans, whose links intentionally name old paths.

External URLs are not fetched on pull requests. Network checks are flaky and
slow; the deterministic gate covers the repository's own links.

## Markdown style

markdownlint runs over root Markdown, `docs/**/*.md`, `.github/**/*.md`, and
fixtures. The repository configuration sets:

- dash bullets;
- ordered list prefixes;
- asterisk emphasis and strong text;
- sibling-only duplicate heading checks;
- a very high line-length limit for prose, with code blocks and tables exempt.

Practical rules:

- use ATX headings (`#`, `##`, ...);
- leave a blank line before and after headings, lists, and fenced code blocks;
- give every fenced code block a language;
- use `-` for unordered lists;
- do not use emphasis as a heading;
- avoid trailing spaces and multiple consecutive blank lines;
- keep tables readable even though the table column style rule is relaxed.

## Adding a page

1. Choose a page that owns one subject. Do not create a second page with
   overlapping authority.
2. Add the file under `docs/` with a kebab-case name.
3. Add it to the correct table in [docs/README.md](README.md), including a
   one-line description of when to read it.
4. Link related pages from the new page.
5. Run the checker and markdownlint.
6. Update any root document that should point to the new page.

## Updating a page

When behavior changes, update the page that owns the behavior:

| Change | Owning page |
| --- | --- |
| Install, first run, first analysis | [Getting started](getting-started.md) |
| `.slproj` keys or path rules | [Project files](project-files.md) |
| User configuration, defaults, analyzer settings | [Configuration](configuration.md) |
| Command, flag, output payload, exit code | [CLI reference](cli.md) |
| Analyzer key, rule behavior, selection | [Analyzers](analyzers.md) |
| Layer, module ownership, runtime entry point | [Architecture](architecture.md) |
| Loader, parser binding, project graph | [Project loading](project-loading.md) |
| Run flow, context, findings, persistence | [Analysis pipeline](analysis-pipeline.md) |
| Symbol, type, scope, access semantics | [Resolution and semantics](resolution-and-semantics.md) |
| Cache key, invalidation, run store | [Caching and runs](caching-and-runs.md) |
| Change Review behavior or artifacts | [Change Review](change-review.md) |
| Textual views and interaction | [Interactive UI](interactive-ui.md) |
| Setup, code rules, analyzer development | [Development](development.md) |
| Test placement, fixtures, fuzzing | [Testing](testing.md) |
| Workflow, gate, release | [CI and release](ci-and-release.md) |
| User-visible failure and diagnosis | [Troubleshooting](troubleshooting.md) |
| Term definitions | [Glossary](glossary.md) |

If a change touches several pages, make one coherent edit rather than leaving a
partial update behind.

## Reviewing documentation

A documentation review checks:

- every claim matches the code or the tested behavior;
- no command, path, key, or exit code is invented;
- examples are runnable or clearly marked as illustrative;
- links point to the right page and the right anchor;
- the index describes the page accurately;
- no customer name, private path, or internal identifier appears in prose,
  examples, or fixtures;
- the changelog has an entry for user-facing behavior.

## What not to do

- Do not create a second source of truth for behavior that another page owns.
- Do not copy a large table between pages; link to the owner.
- Do not document a temporary workaround as if it were the intended design.
- Do not leave a historical plan in the live navigation without labeling it.
- Do not add a page and forget the index; the checker will reject it.

## Related pages

- [CI and release](ci-and-release.md)
- [Development](development.md)
- [README](README.md)
