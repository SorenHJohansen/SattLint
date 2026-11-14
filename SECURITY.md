# Security Policy

## Supported versions

Only the latest published release receives security fixes. Older releases are
not patched, so upgrade before reporting:

```bash
python3 -m pip install --user --upgrade sattlint
```

## Reporting a vulnerability

Report privately through GitHub's private vulnerability reporting:

<https://github.com/SorenHJohansen/SattLint/security/advisories/new>

Do not open a public issue for a suspected vulnerability. A useful report
includes:

- the SattLint version from `sattlint --version`,
- the operating system and Python version,
- the smallest `.slproj`, SattLine sample, ICF file, or graphics companion that
  triggers the problem,
- what happened, and what you expected instead.

You can expect an acknowledgement, an assessment of impact, and either a fix or
a documented decision not to fix. SattLint is maintained by one person, so
timelines are best effort.

## Scope

SattLint reads program files, project files, and library trees from disk, then
renders the results in a terminal user interface. In scope:

- crashes, hangs, or unbounded memory use triggered by input in the analyzers,
  ICF validation, graphics validation, or project loading
- path traversal or unintended file access in project discovery, cache
  handling, or report output
- terminal control sequence injection through analyzed source text or file
  names
- weaknesses in the published package or its release workflow

Out of scope:

- analysis results that are wrong but do not crash or hang, report those as a
  normal issue with a minimal sample
- vulnerabilities in `sattline-parser`, `lark`, `textual`, or another
  dependency, report those upstream, though a note here is welcome if a
  version constraint needs to change
- programs you do not have permission to share

Never include secrets, customer names, or private library paths in a report.
Reduce the sample to the smallest reproduction that still triggers the problem.
