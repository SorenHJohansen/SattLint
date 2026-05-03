# Metrics History

Store curated repository health snapshots here.

- Use `python scripts/repo_health.py --audit-dir artifacts/audit --history-output metrics/history/<name>.json` to write a snapshot.
- Keep snapshots small and machine-readable.
- Prefer milestone or nightly names over per-commit spam.
- History powers the trend summary in `scripts/repo_health.py`.
