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

2. Choose `4) Edit config`

3. Set:

   * `program_dir` → your SattLine program folder
   * `ABB_lib_dir` → shared/ABB libraries
   * `other_lib_dirs` → any additional libraries
   * `analyzed_programs_and_libraries` → what to analyze

4. Save with `9) Save config`

5. Run `5) Self-check diagnostics`

**Important:**
Use names *without file extensions*

✔ `MyProgram`
✘ `MyProgram.s`

---

## Daily Use

Start SattLint:

```bash
sattlint
```

Main menu:

* `1) Analyses` → run checks
* `2) Dump outputs` → inspect parser data
* `3) Documentation` → generate Word docs
* `4) Edit config` → change setup
* `5) Self-check diagnostics` → verify setup
* `6) Force refresh cached AST` → fix stale results

---

## Check One File Quickly

```bash
sattlint syntax-check /path/to/Program.s
```

Output:

* `OK` → valid file
* Error message → invalid file

---

## Generate Word Documentation

1. Start SattLint
2. Choose `3) Documentation`
3. Choose `1) Generate documentation`

You can optionally scope by units before generating.

Output is a `.docx` file.

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