# Nuke Dev Setup — Agent Workflow

Step-by-step workflow the agent follows to automate environment setup. Execute each step, validate, and only prompt the user when required.

> **Source of truth:** The canonical setup instructions live in
> [DEVELOPMENT.md](../../../DEVELOPMENT.md) and [README.md](../../../README.md).
> This guide tells the agent *how to automate* those steps — refer to the source docs for full details.

## Step 0: Detect OS

**Action:** Determine the operating system.

**Windows:**
```powershell
[System.Environment]::OSVersion.Platform
```

**Linux/macOS:**
```bash
uname -s
```

Store the OS for use in subsequent steps (paths and commands differ per platform).

## Step 1: Verify Python 3.9+

**Action:** Check Python version.

```bash
python3 --version
```

On Windows, also try:
```powershell
python --version
```

**If missing or < 3.9:** Inform user to install Python 3.9+ from https://www.python.org/downloads/. Wait for confirmation.

## Step 2: Detect Nuke Installation

**Action:** Search for Nuke at default install locations.

**Windows:**
```powershell
Get-ChildItem "C:\Program Files" -Directory | Where-Object {$_.Name -match "^Nuke\d+\.\d+v\d+$"} | Sort-Object Name -Descending
```

**Linux:**
```bash
ls -d /usr/local/Nuke* 2>/dev/null | sort -rV
```

**macOS:**
```bash
ls -d /Applications/Nuke* 2>/dev/null | sort -rV
```

**If found:** Use the newest version. Display it and confirm with user. Store the Nuke install path and version.

**If not found:** Prompt user to install Nuke (15 or 16) or enter a custom path. Validate the path contains the Nuke executable.

Determine the Nuke Python executable path:
- **Windows:** `<NUKE_DIR>\python.exe` (e.g. `C:\Program Files\Nuke16.0v2\python.exe`)
- **Linux:** `<NUKE_DIR>/python` (e.g. `/usr/local/Nuke16.0v2/python`)
- **macOS:** `<NUKE_DIR>/Nuke<VERSION>.app/Contents/MacOS/python` (e.g. `/Applications/Nuke16.0v2/Nuke16.0v2.app/Contents/MacOS/python`)

Verify it works:
```bash
<NUKE_PYTHON> --version
```

## Step 3: Install Hatch

**Action:** Check if hatch is installed.

```bash
hatch --version
```

**If not installed:**
```bash
python3 -m pip install hatch
```

On Windows:
```powershell
python -m pip install hatch
```

Verify installation:
```bash
hatch --version
```

## Step 4: Build the Package

**Action:** Build wheel and source distributions from the repo root.

```bash
hatch build
```

Expected output in `dist/`:
- `deadline_cloud_for_nuke-<VERSION>-py3-none-any.whl`
- `deadline_cloud_for_nuke-<VERSION>.tar.gz`

Verify build artifacts exist.

## Step 5: Install into Nuke's Python

**Action:** Install the package and the deadline-cloud client library into Nuke's bundled Python. Run these from the repo root directory.

**Windows:**
```powershell
& "<NUKE_DIR>\python.exe" -m pip install -e .
& "<NUKE_DIR>\python.exe" -m pip install -e <path-to-deadline-cloud>
```

If `deadline-cloud` is not cloned locally, install from PyPI:
```powershell
& "<NUKE_DIR>\python.exe" -m pip install deadline
```

**Linux:**
```bash
<NUKE_DIR>/python -m pip install -e .
<NUKE_DIR>/python -m pip install deadline
```

**macOS:**
```bash
<NUKE_DIR>/Nuke<VERSION>.app/Contents/MacOS/python -m pip install -e .
<NUKE_DIR>/Nuke<VERSION>.app/Contents/MacOS/python -m pip install deadline
```

**Note:** Admin/sudo may be required if Nuke is installed in a system directory.

## Step 6: Configure Environment Variables

**Action:** Set `NUKE_PATH` to the repo's `src` directory so Nuke finds the submitter menu.

**Windows:**
```powershell
[Environment]::SetEnvironmentVariable("NUKE_PATH", "<REPO_ROOT>\src", [EnvironmentVariableTarget]::User)
[Environment]::SetEnvironmentVariable("NUKE_EXECUTABLE", "<NUKE_DIR>\Nuke<VERSION>.exe", [EnvironmentVariableTarget]::User)
[Environment]::SetEnvironmentVariable("DEADLINE_ENABLE_DEVELOPER_OPTIONS", "true", [EnvironmentVariableTarget]::User)
```

**Linux/macOS (add to ~/.bashrc or ~/.zshrc):**
```bash
export NUKE_PATH="<REPO_ROOT>/src"
export NUKE_EXECUTABLE="<NUKE_DIR>/Nuke<VERSION>"
export DEADLINE_ENABLE_DEVELOPER_OPTIONS=true
```

## Step 7: Install Test Dependencies

**Action:** Install test packages using hatch.

```bash
hatch run test --help
```

This triggers hatch to create the test environment and install all test dependencies (pytest, coverage, etc.) as defined in `pyproject.toml`.

Alternatively, install manually:
```bash
python3 -m pip install -r requirements-testing.txt
```

## Step 8: Display Summary

```
✓ Nuke Dev Setup Complete!

Installed:
  - Python: [VERSION]
  - Hatch: [VERSION]
  - Nuke: [VERSION] at [PATH]
  - Package installed to Nuke Python: [PATH]

Environment Variables:
  - NUKE_PATH=[REPO_ROOT]/src
  - NUKE_EXECUTABLE=[NUKE_EXECUTABLE_PATH]
  - DEADLINE_ENABLE_DEVELOPER_OPTIONS=true

Next Steps:
  1. Launch Nuke — the AWS Deadline submitter should appear in the menu
  2. Run tests: hatch run test
  3. Run linting: hatch run lint
  4. Run formatting: hatch run fmt
```

## Troubleshooting

### Nuke Not Found
If Nuke is not at the default location, set `NUKE_EXECUTABLE` manually:
```bash
export NUKE_EXECUTABLE=/path/to/Nuke16.0
```

### pip Install Fails in Nuke Python
Nuke's bundled Python may not include pip. Install it:
```bash
<NUKE_PYTHON> -m ensurepip --upgrade
```

### Submitter Not Appearing in Nuke Menu
Verify `NUKE_PATH` is set correctly and points to the repo's `src` directory:
```bash
echo $NUKE_PATH
ls $NUKE_PATH/menu.py
```

### Hatch Not Found After Install
Restart your terminal or add the scripts directory to PATH:
```bash
# Linux/macOS
export PATH="$HOME/.local/bin:$PATH"
```
```powershell
# Windows
$env:PATH = "$env:APPDATA\Python\Python311\Scripts;$env:PATH"
```
