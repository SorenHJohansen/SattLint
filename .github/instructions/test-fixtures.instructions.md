---
description: "Use when changing SattLint test fixtures, corpus manifests, sample SattLine files, or golden analysis artifacts. Covers fixture shape, corpus layout, and minimal SattLine validity rules."
name: "Test Fixture Instructions"
applyTo: ["tests/fixtures/**", "tests/test_corpus.py", "tests/test_phase0_guardrails.py"]
---
# Test Fixtures

- Keep fixtures minimal and purpose-built for one behavior or regression.
- For SattLine parser fixtures, preserve the three header `STRING` lines before `BasePicture` unless the fixture is intentionally invalid.
- Keep corpus files in the existing `valid/`, `invalid/`, `edge_cases/`, and `manifests/` layout.
- Use repo-relative paths inside manifests and artifact expectations.
- Update goldens or manifests only when the behavioral contract changes, and validate the nearest corpus or fixture-backed test first.
