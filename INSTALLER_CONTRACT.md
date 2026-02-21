# MetaFFI Installer Contract

## Scope

This document defines the runtime contract for MetaFFI plugin installers and uninstallers.

## Plugin Installer CLI

Plugin installer executables/scripts must support:

- `-c`, `--check-prerequisites`: validate prerequisites only, no installation side-effects.
- `-p`, `--print-prerequisites`: print required prerequisites.
- `-i`, `--install`: install plugin.
- `-u`, `--uninstall`: uninstall plugin.
- `-s`, `--silent`: non-interactive mode (uses defaults).

Backward compatibility:

- Positional legacy actions are accepted: `install`, `uninstall`, `check-prerequisites`, `print-prerequisites`.
- No action defaults to install.

## Exit Codes

- `0`: success.
- `1`: contract-expected failure (for example, prerequisite check failed).
- non-zero (other): runtime/internal failure.

## Plugin Uninstaller Precedence

MetaFFI CLI and core uninstaller use this order:

1. Executable uninstaller:
   - Windows: `uninstall_plugin.exe`
   - Linux: `uninstall_plugin`
2. Script wrapper:
   - Windows: `uninstall.bat`
   - Linux: `uninstall.sh`
3. Legacy Python fallback:
   - `uninstall_plugin.py`
   - `uninstall.py`

If fallback reaches Python script, emit a deprecation warning.

## Core Uninstaller Policy

- Continue uninstalling remaining plugins even if one plugin uninstall fails.
- Report all plugin uninstall failures at the end.
- Exit with failure if any plugin uninstall failed.

## Build System Boundary

- Installer packaging is not built via CMake in this phase.
- CMake remains responsible for native project build artifacts only.
