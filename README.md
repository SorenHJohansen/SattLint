# SattLint

SattLint is a cross-platform tool for people who write SattLine and want help checking code, tracing dependencies, and generating Word documentation.

This guide is written for coworkers who just want to get it running quickly. No Git knowledge is needed.

---

## What SattLint Does

SattLint can help you:

* check whether a SattLine file parses correctly
* analyze a full program or library together with its dependencies
* find issues such as unused variables, written-but-never-read variables, and shadowing
* generate FS-style Word documentation as a `.docx` file
* inspect parser outputs when something looks wrong

---

## What You Need

* Windows or Linux
* Python **3.13 or newer**
* **pipx** (used to install and run SattLint cleanly)
* A local copy of your SattLine code

---

## Installation (pipx only)

### 1. Get SattLint

You need a local copy of the SattLint folder.

Use one of these:

* Download the repository as a ZIP file and extract it
* Copy the SattLint folder from a coworker or shared drive

Example locations:

* Linux: `~/SattLint`
* Windows: `C:\Tools\SattLint`

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

Open a terminal **inside the SattLint folder** and run:

```bash
pipx install .
```

This installs SattLint globally (but isolated), so you can run it from anywhere.

---

### 4. Start SattLint

```bash
sattlint
```

That opens the interactive menu.

---

## Updating SattLint

If you receive a newer version:

1. Replace your SattLint folder with the new version
2. Run:

```bash
pipx reinstall sattlint
```

---

## First-Time Setup

The first time SattLint runs, it creates a config file automatically.

* **Windows:**
  `%APPDATA%\sattlint\config.toml`

* **Linux:**
  `~/.config/sattlint/config.toml`

### Configure it

1. Start SattLint

2. Choose `3) Setup`

3. Set:

  * `program_dir` -> your SattLine program folder
  * `ABB_lib_dir` -> shared or ABB libraries
  * `other_lib_dirs` -> any additional libraries
  * `analyzed_programs_and_libraries` -> what to analyze
  * `12) Edit graphics rules` -> define expected module invocation or clipping rules saved in JSON

4. Save with `9) Save configuration`

5. Choose `4) Tools`

6. Run `1) Self-check diagnostics`

**Important:**
Use names *without file extensions*

+ `MyProgram`
- `MyProgram.s`

---

## Daily Use

Start SattLint:

```bash
sattlint
```

Main menu:

* `1) Analyze` -> run curated checks, variable reports, and registry-backed analyzers
* `2) Documentation` -> preview unit scope and generate Word docs
* `3) Setup` -> change paths, targets, mode, and cache settings
* `4) Tools` -> run self-check, inspect dumps, and refresh cached ASTs
* `5) Help` -> first-time guidance and workflow explanations

Inside `Analyze`, use `Full analyzer suite` for a broad pass and the focused submenus when you want specific reports or debugging tools.

Graphics layout specification workflow:

* `3) Setup` -> `12) Edit graphics rules` to add or update expected invocation coordinates, invocation flags, and clipping-related values
* Use `unit:` selectors when a module should look the same in every detected unit, for example `unit:L1` or `unit:L1.L2.UnitControl`
* Use `equipment:` selectors when a module should look the same inside every equipment module, for example `equipment:L1.L2.EquipModPanelShort`
* Exact relative paths are still available for one-off cases, but the normalized `unit:` and `equipment:` selectors avoid hardcoding unit names such as `ApplTank` or equipment-module names such as `Empty`
* Moduletype rules still identify modules by resolved `ModuleType` name and can optionally be narrowed with `unit:`, `equipment:`, or exact-path selectors
* `1) Analyze` -> `3) Structure & modules` -> `4) Validate graphics rules` to report modules that are not to spec
* `4) Tools` -> `1) Self-check diagnostics` to confirm the graphics rules JSON path and whether the file is valid

---

## Check One File Quickly

```bash
sattlint syntax-check /path/to/Program.s
```

`syntax-check` also accepts `.g` and `.y` graphics files and validates literal `PictureDisplay` targets. When you validate a `.s` or `.x` source file, SattLint also checks the matching graphics sidecar when present: official mode uses `.y`, while draft-mode lookup prefers `.g` and falls back to `.y`.

Output:

* `OK` → valid file
* Error message → invalid file

---

## Generate Word Documentation

1. Start SattLint
2. Choose `2) Documentation`
3. Choose `1) Generate documentation`

You can optionally scope by units before generating.

Output is a `.docx` file.

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
pipx reinstall sattlint
```

---

### Targets not found

Check:

* Names have no extensions
* Paths in config are correct
* Mode (`official` / `draft`) matches files

---

### Missing libraries

Add missing folders to:

* `ABB_lib_dir`
* `other_lib_dirs`

---

### Results look outdated

Run:

```
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

```
CONTRIBUTING.md
```

---

## License

SattLint is released under the MIT License.
