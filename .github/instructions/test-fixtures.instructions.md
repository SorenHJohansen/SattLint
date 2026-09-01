---
description: "Use when changing SattLint test fixtures, sample SattLine files, or golden analysis artifacts. Covers fixture shape and minimal SattLine validity rules."
name: "Test Fixture Instructions"
applyTo: ["tests/fixtures/**", "tests/test_analyzer_guardrails.py"]
---
# Test Fixtures

- Keep fixtures minimal and purpose-built for one behavior or regression.
- For SattLine parser fixtures, preserve the three header `STRING` lines before `BasePicture` unless the fixture is intentionally invalid.
- Use repo-relative paths inside fixtures and expectations.
- Update goldens or fixtures only when the behavioral contract changes, and validate the nearest fixture-backed test first.
