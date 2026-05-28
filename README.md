# SattLint

SattLint is a Python toolkit for SattLine projects. It can syntax-check individual files, audit repository health, run deeper analysis, generate DOCX documentation, and expose a language-server entrypoint.

## Public support contract

- **Stable on Windows and Linux:** `sattlint --version`, `sattlint syntax-check`, `sattlint repo-audit`, and `sattlint-lsp`
- **Preview:** the interactive CLI menu, config-driven analysis and documentation workflows, and the local VS Code client in [vscode/sattline-vscode](vscode/sattline-vscode)
- **Internal-only:** AI coordination files, generated audit artifacts, and maintainer automation

For the full contract, see the [public support matrix](docs/references/public-support-matrix.md). For help and issue routing, see [SUPPORT.md](SUPPORT.md). For vulnerabilities, see [SECURITY.md](SECURITY.md). For contributor expectations, see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). For development setup, see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Quick start from a source checkout

The current public branch is still installed from source. To evaluate it today:

1. Clone or download this repository.
2. Install `pipx`.
3. Run `pipx install .` from the repository root.
4. Verify the install with `sattlint --version`.
5. Run `sattlint syntax-check tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s`.

---

## AI-First Repository Docs

For AI contributors and multi-agent work, start here:

- `AGENTS.md`
- `docs/context-loading-order.md`
- `docs/repo-map.md`
- `docs/architecture.md`
- `docs/quality-gates.md`
- `docs/ai-workflows.md`
- `docs/exec-plans/completed/ai-first-repo-hardening.md`
- `docs/exec-plans/tech-debt-tracker.md`

---

## AI-First Quick Start

For repository operations, use these in order:

- `python scripts/run_ai_edit_gate.py`
- `python -m pre_commit run --all-files`
- `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`
- `python scripts/repo_health.py --check --audit-dir artifacts/audit`

`python scripts/run_ai_edit_gate.py` auto-fixes touched Python files with Ruff and runs `context_health.py --check` when the touched files are part of the AI-control plane.

In VS Code, the workspace also recommends `wanderleyferreiradealbuquerque.context-optimizer`.
Use `@context-optimizer /audit` before expanding AI control files such as `AGENTS.md` or scoped instruction sets.

---

## What SattLint Does

SattLint can help you:

- check whether a SattLine file parses correctly
- analyze a full program or library together with its dependencies
- find issues such as unused variables, written-but-never-read variables, and shadowing
- generate FS-style Word documentation as a `.docx` file
- inspect parser outputs when something looks wrong

---

## What You Need

- Windows or Linux for the stable public command surface
- Python **3.13 or newer**
- **pipx** (used to install and run SattLint cleanly)
- macOS only on a contributor best-effort basis for now
- A local copy of your SattLine code

---

## Installation from this repository

### 1. Get the source

Clone the repository:

```bash
git clone https://github.com/SorenHJohansen/SattLint.git
cd SattLint
```

If you prefer not to use Git, download the repository ZIP from GitHub and extract it to a working folder first.

---

### 2. Install pipx

#### Linux

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Restart your terminal after this.

#### Windows

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Restart your terminal after this.

---

### 3. Install SattLint

Open a terminal in the repository root and run:

```bash
pipx install .
```

This installs SattLint globally but in an isolated environment, so you can run it from anywhere.

---

### 4. Verify the stable command surface

```bash
sattlint --version
sattlint syntax-check tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s
```

---

### 5. Try the preview workflows

```bash
sattlint
```

That opens the interactive menu. The menu and other config-driven workflows are preview surfaces in the current public contract.

For non-interactive use, SattLint also exposes subcommands:

```bash
sattlint syntax-check path/to/Program.s
sattlint analyze
sattlint analyze --list-checks
sattlint validate-config
sattlint format-icf
sattlint format-icf --check
sattlint docgen --output-dir docs-out
sattlint repo-audit --profile quick --fail-on high
```

Shared flags for config-driven commands:

```bash
sattlint --config path/to/config.toml analyze
sattlint --config path/to/config.toml --no-cache analyze
sattlint --config path/to/config.toml validate-config
sattlint --quiet repo-audit --profile quick
```

For the full command surface and script entry points, see [docs/references/cli-commands.md](docs/references/cli-commands.md).

For contributor-only dashboards and AI workflow contracts, see [docs/quality-gates.md](docs/quality-gates.md), [docs/ai-workflows.md](docs/ai-workflows.md), [.ai/tasks/task-contract.schema.json](.ai/tasks/task-contract.schema.json), and [.ai/handoffs/handoff.schema.json](.ai/handoffs/handoff.schema.json).

---

## Updating SattLint

If you installed from a source checkout:

1. Update your local checkout.
2. Run:

```bash
pipx install --force .
```

When the published package becomes available, installed releases should use `pipx upgrade sattlint` instead.

---

## First-Time Setup

The first time SattLint runs, it creates a config file automatically.

- **Windows:**
  `%APPDATA%\sattlint\config.toml`

- **Linux:**
  `~/.config/sattlint/config.toml`

### Configure it

1. Start SattLint

2. Choose `3) Setup`

3. Set:

    - `program_dir` -> your SattLine program folder
    - `ABB_lib_dir` -> shared or ABB libraries
    - `other_lib_dirs` -> any additional libraries
    - `analyzed_programs_and_libraries` -> what to analyze
    - `10) Change icf_dir` -> directory used for ICF validation and formatting
    - `12) Edit graphics rules` -> define expected module invocation or clipping rules saved in JSON

4. Save with `9) Save configuration`

5. Choose `4) Tools`

6. Run `1) Self-check diagnostics`

**Important:**
Use names *without file extensions*

- `MyProgram`
- ~~`MyProgram.s`~~

---

## Daily Use

Start SattLint:

```bash
sattlint
```

Or run a specific automation command:

```bash
sattlint syntax-check FILE
sattlint analyze
sattlint format-icf
sattlint validate-config
```

`syntax-check` and `repo-audit` are part of the current stable contract. The interactive menu, analysis, formatting, validation, and DOCX-generation workflows remain preview surfaces.

Main menu:

- `1) Analyze` -> run curated checks, variable reports, and registry-backed analyzers
- `2) Documentation` -> preview unit scope and generate Word docs
- `3) Setup` -> change paths, targets, mode, and cache settings
- `4) Tools` -> run self-check, inspect dumps, and refresh cached ASTs
- `5) Help` -> first-time guidance and workflow explanations

Inside `Analyze`, use `Full analyzer suite` for a broad pass and the focused submenus when you want specific reports or debugging tools.

Graphics layout specification workflow:

- `3) Setup` -> `12) Edit graphics rules` to add or update expected invocation coordinates, invocation flags, and clipping-related values
- Use `unit:` selectors when a module should look the same in every detected unit, for example `unit:L1` or `unit:L1.L2.UnitControl`
- Use `equipment:` selectors when a module should look the same inside every equipment module, for example `equipment:L1.L2.EquipModPanelShort`
- Exact relative paths are still available for one-off cases, but the normalized `unit:` and `equipment:` selectors avoid hardcoding unit names such as `ApplTank` or equipment-module names such as `Empty`
- Moduletype rules still identify modules by resolved `ModuleType` name and can optionally be narrowed with `unit:`, `equipment:`, or exact-path selectors
- `1) Analyze` -> `3) Structure & modules` -> `4) Validate graphics rules` to report modules that are not to spec
- `4) Tools` -> `1) Self-check diagnostics` to confirm the graphics rules JSON path and whether the file is valid

---

## Check One File Quickly

```bash
sattlint syntax-check /path/to/Program.s
```

`syntax-check` also accepts `.g` and `.y` graphics files and validates literal `PictureDisplay` targets. When you validate a `.s` or `.x` source file, SattLint also checks the matching graphics sidecar when present: official mode uses `.y`, while draft-mode lookup prefers `.g` and falls back to `.y`.

Output:

- `OK` -> valid file
- Error message -> invalid file

Exit codes:

- `0` -> success
- `1` -> command ran and found a real problem in the input or repository
- `2` -> invalid arguments or invalid configuration input

---

1. **View Results**: Auto-switches to Results view with formatted output
2. **Generate Docs**: Switch to Documentation view and click "Generate DOCX"

### Keyboard & Mouse

- **Sidebar**: Click view names to switch between Analyze, Config, Docs, Tools, and Results
- **Buttons**: Click action buttons to start tasks (no right-click menu)
- **History**: Click history entries in Results view to see details
- **Scrolling**: All text areas support scrollbars

### Status Bar

The status bar at the bottom shows current action and task progress (e.g., "Self-check running...", "Documentation generation finished").

---

## Need Guidance In The App

If you are unsure where to start:

1. Open `5) Help`
2. Follow the first-run checklist shown there
3. Use `sattlint syntax-check /path/to/Program.s` when you only want to validate one file quickly

---

## Common Problems

### `sattlint` not found

pipx is not on your PATH.

Fix:

```bash
pipx ensurepath
```

Restart terminal.

---

### Python version error

Install Python 3.13+ and reinstall:

```bash
pipx install --force .
```

---

### Targets not found

Check:

- Names have no extensions
- Paths in config are correct
- Mode (`official` / `draft`) matches files

---

### Missing libraries

Add missing folders to:

- `ABB_lib_dir`
- `other_lib_dirs`

---

### Results look outdated

Run:

```text
6) Force refresh cached AST
```

---

## If It Was Already Installed For You

You can usually just run:

```bash
sattlint
```

---

## For Developers

This README is focused on usage.

For development setup, tests, and tooling, see:

```text
CONTRIBUTING.md
```

---

## License

SattLint is released under the MIT License.
