# SattLint

SattLint is a cross-platform tool for people who write SattLine and want help checking code, tracing dependencies, and generating Word documentation.

This README is written for coworkers who want to install and use the tool. You do not need Git. You do not need to know Python beyond copying a few commands once.

## What SattLint Does

SattLint can help you:

- check whether a SattLine file parses correctly
- analyze a full program or library together with its dependencies
- find issues such as unused variables, written-but-never-read variables, shadowing, and related code-quality problems
- generate FS-style Word documentation as a `.docx` file
- inspect parser outputs when something looks wrong

## What You Need

- Windows or Linux
- Python 3.13 or newer
- pipx (recommended for easy terminal access)
- A local copy of your SattLine code folders
- VS Code, PowerShell/Windows Terminal, or Linux terminal

Git is not required.

## Install Without Git

### Linux (using pipx)

1. Install pipx (if not already installed):
   ```bash
   pip install pipx
   pipx ensurepath
   ```

2. Install SattLint:
   ```bash
   pipx install .
   ```

3. Start SattLint:
   ```bash
   sattlint
   ```

To update later, run `pipx upgrade sattlint` in the SattLint folder.

### Linux (alternative - manual venv)

If you prefer not to use pipx:

1. Get SattLint:
   - Download the repository as a ZIP file from GitHub and extract it.
   - Copy a prepared SattLint folder from a coworker.

   Assume the folder is extracted to something like:
   ```text
   ~/SattLint
   ```

2. Install Python 3.13 from python.org or your package manager.

3. Open a terminal in the SattLint folder and run:
   ```bash
   python3.13 -m venv .venv
   .venv/bin/pip install --upgrade pip
   .venv/bin/pip install .
   ```

4. Start SattLint:
   ```bash
   .venv/bin/sattlint
   ```

### Windows (using pipx)

1. Install pipx (if not already installed):
   ```powershell
   pip install pipx
   pipx ensurepath
   ```

2. Install SattLint:
   ```powershell
   pipx install .
   ```

3. Start SattLint:
   ```powershell
   sattlint
   ```

To update later, run `pipx upgrade sattlint` in the SattLint folder.

### Windows (alternative - manual venv)

#### 1. Get SattLint

Use one of these options:

1. Download the repository as a ZIP file from GitHub and extract it.
2. Copy a prepared SattLint folder from a shared drive or from a coworker.

For the rest of this guide, assume the folder is extracted to something like:

```text
C:\Tools\SattLint
```

### 2. Install Python

Install Python 3.13 from python.org.

During installation, make sure Python is available from the terminal.

### 3. Open a terminal in the SattLint folder

In VS Code:

1. Open the SattLint folder.
2. Open the terminal.

Or in Windows Explorer:

1. Open the SattLint folder.
2. Click the address bar.
3. Type `powershell` and press Enter.

### 4. Run the one-time install commands

Copy and run these commands exactly:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .
```

If `py -3.13` does not work, try:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install .
```

### 5. Start SattLint

Run:

```powershell
.\.venv\Scripts\sattlint.exe
```

That opens the interactive menu.

## First-Time Setup

The first time SattLint starts, it creates its config file automatically.

On Windows the config file is stored here:

```text
%APPDATA%\sattlint\config.toml
```

On Linux the config file is stored here:

```text
~/.config/sattlint/config.toml
```

Use the menu to fill in the settings:

1. Choose `4) Edit config`.
2. Set `program_dir` to the folder that contains the SattLine programs you want to analyze.
3. Set `ABB_lib_dir` to your ABB or shared base library folder.
4. Add any extra library folders under `other_lib_dirs`.
5. Set `icf_dir` if you use ICF-related checks.
6. Add one or more program or library names under `analyzed_programs_and_libraries`.
7. Choose the right mode: `official` or `draft`.
8. Choose `9) Save config`.
9. Go back to the main menu.
10. Run `5) Self-check diagnostics`.

Important: when you add a program or library name, use the name without the file extension.

Example:

- use `MyProgram`
- do not use `MyProgram.s`
- do not use `MyProgram.x`

## Which Settings Mean What

- `program_dir`: your main SattLine program folder
- `ABB_lib_dir`: the ABB or shared library folder
- `other_lib_dirs`: any additional project library folders
- `icf_dir`: folder with ICF files if you use them
- `analyzed_programs_and_libraries`: the root items SattLint should analyze
- `mode`: choose `official` for official files, or `draft` for draft files
- `scan_root_only`: only scan the selected roots and skip wider dependency loading
- `fast_cache_validation`: keeps startup faster by reusing cached parser data when possible
- `debug`: prints more internal detail when troubleshooting

## Daily Use

Start the tool with:

```bash
sattlint
```

Main menu overview:

- `1) Analyses`: run the built-in code checks
- `2) Dump outputs`: inspect parse trees, ASTs, and related internal outputs
- `3) Documentation`: generate a Word document for the configured targets
- `4) Edit config`: change folders, targets, and other settings
- `5) Self-check diagnostics`: verify that paths and Python setup still look correct
- `6) Force refresh cached AST`: rebuild cached parser data if results look stale

## Generate Word Documentation

To create documentation:

1. Start SattLint.
2. Choose `3) Documentation`.
3. Choose `1) Generate documentation`.
4. Accept the proposed output file name, or enter your own.

SattLint can also limit documentation to selected units:

- `2) Preview detected unit candidates`
- `4) Scope by unit moduletype name(s)`
- `5) Scope by unit instance path(s)`

The output is a `.docx` file that you can open in Word.

## Check One File Quickly

If you only want to know whether one SattLine file parses correctly, you do not need the full interactive menu.

**Linux/Windows (with pipx):**
```bash
sattlint syntax-check /path/to/Program.s
```

If the file is valid, SattLint prints:

```text
OK
```

If the file is invalid, SattLint prints a short error message with line information when possible.

## Updating SattLint

**With pipx:**
```bash
pipx upgrade sattlint
```

If the update behaves strangely, run `pipx reinstall sattlint`.

## Common Problems

### `py` is not recognized

Python is either not installed, or not available in the terminal. Reinstall Python 3.13 and make sure terminal access is enabled.

### SattLint says Python 3.13+ is required

Install Python 3.13 or newer, then recreate the `.venv` folder.

### A target cannot be found

Check all of these:

- the target name is listed without `.s`, `.x`, `.l`, or `.z`
- `program_dir`, `ABB_lib_dir`, and `other_lib_dirs` point to the correct folders
- the selected `mode` matches the files you want to analyze

### Libraries are missing during analysis

Usually this means one of the library folders is missing from config. Add the missing folder under `ABB_lib_dir` or `other_lib_dirs`, save the config, and try again.

### Results look old or wrong after many file changes

Run `6) Force refresh cached AST` from the main menu.

## If Someone Already Installed It For You

If a coworker already prepared the SattLint folder on your machine, you can usually skip the install section and just run:

```bash
sattlint
```

## For Developers

This README is intentionally focused on everyday users.

If you want development setup, tests, or VS Code extension details, see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

SattLint is released under the MIT License.
