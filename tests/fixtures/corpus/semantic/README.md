# Semantic Corpus Fixtures

This directory is intentionally split by reuse pattern rather than by rule family.

- `workspace/` contains fixtures referenced only by workspace semantic corpus manifests.
- `analyzer/` contains fixtures referenced only by direct analyzer corpus manifests.
- `shared/` contains fixtures reused by both workspace and analyzer manifests.

Keep new fixtures in the narrowest bucket that matches actual manifest usage. If a fixture starts in one bucket and later gains a second consumer type, move it to `shared/` and update the manifest paths together.
