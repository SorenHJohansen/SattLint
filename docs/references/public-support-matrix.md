# Public Support Matrix

This matrix defines the current public support contract for SattLint. `Stable` means the surface is part of the documented compatibility promise and release rehearsal. `Preview` means the surface ships in the repository but may still change shape, UX, or scope between releases. `Internal-only` means the surface exists for maintainers, CI, or AI workflow plumbing and should not be treated as a public automation contract.

| Surface | Status | Supported platforms | Scope | Notes |
| --- | --- | --- | --- | --- |
| `sattlint --version` and installed CLI bootstrap | Stable | Windows, Linux | Confirms the installed package boots and reports a version | Part of release smoke validation |
| `sattlint syntax-check` | Stable | Windows, Linux | Strict single-file syntax validation for SattLine source and graphics sidecars | Release smoke uses the checked-in grammar sample |
| `sattlint repo-audit` | Stable | Windows, Linux | Repository audit CLI, check catalog, and public-readiness checks | Full profile is supported but can be slower on larger repos |
| `sattlint-lsp` | Stable | Windows, Linux | Standalone Python language-server entrypoint | Editor clients may add preview behavior on top |
| `sattlint analyze`, `sattlint validate-config`, `sattlint format-icf`, and `sattlint docgen` | Preview | Windows, Linux | Richer config-driven analysis, formatting, and documentation workflows | Useful today, but not yet part of the smallest stable release contract |
| Interactive `sattlint` menu | Preview | Windows, Linux | Guided setup and menu-driven workflows | Menu layout and wording may still evolve |
| `sattlint-gui` | Preview | Windows, Linux | Desktop shell for config editing, diagnostics, and workflow helpers | Public support remains best-effort while the surface matures |
| `vscode/sattline-vscode/` | Preview | Local preview use | Repository-local VS Code client for the Python LSP | Not yet published under a public marketplace publisher |
| `.ai/`, `artifacts/`, `metrics/`, repo helper scripts, and GitHub automation internals | Internal-only | Maintainer-only | AI coordination, generated artifacts, release plumbing, and internal tooling | May change without compatibility notice |

## Notes

- Stable platform targets are Windows and Linux with Python 3.13 or newer.
- macOS contributor workflows may work, but they are not part of the stable support contract yet.
- Security issues follow [SECURITY.md](../../SECURITY.md). Non-security help and issue routing follow [SUPPORT.md](../../SUPPORT.md).
