# MetaFFI Installer Modernization Plan

- [x] **Manual GitHub CI For Build + Installers (New)**
- [x] **Split Installers (Windows/Ubuntu) + Combined Packager (New)**
- [x] **CI Gate: Run All CTests Before Installer Packaging (New)**
- [x] **Fail-Fast Guardrails**
- [x] **Contract Definition**
- [x] **Plugin Installer Template Update**
- [x] **CLI Plugin Orchestration Fix**
- [x] **Core Uninstaller Alignment**
- [x] **Legacy Compatibility + Deprecation**
- [ ] **Tests (Unit + Integration)**
- [ ] **Docs + Release Flow**
- [ ] **Docker Validation Spec (Deferred to containers)**

## 0) GitHub CI Manual Pipeline (Current Focus)

- [x] Add manual `workflow_dispatch` workflow in `metaffi-installer`.
- [x] Workflow clones only `metaffi-root`; dependency repos are cloned by CMake verify logic.
- [x] Build MetaFFI artifacts on Windows runner.
- [x] Build MetaFFI artifacts on Ubuntu runner.
- [x] Run full CTest suite (including `tests` repo) on each platform before packaging installers.
- [x] Build Windows-specific installer artifact.
- [x] Build Ubuntu-specific installer artifact.
- [x] Build combined installer by packaging the two OS-specific installers.
- [x] Upload all three installer artifacts on dry-run (`publish=false`).
- [x] Publish all three installer assets on release (`publish=true`).

## Fail-Fast Rules (Mandatory)

- [ ] Stop immediately and ask the user if any required artifact/interface is missing or ambiguous.
- [ ] Stop immediately and ask the user if command-line contract conflicts with existing release artifacts.
- [ ] Stop immediately and ask the user before changing behavior that can break existing installer links/usages.
- [ ] Stop immediately and ask the user if plugin uninstall precedence cannot be enforced exactly:
  - executable -> script -> python script
- [ ] Fail build/validation on first contract violation (do not continue silently).

## 1) Contract Definition

- [x] Create/approve single installer CLI contract for plugin installers:
  - `--check-prerequisites`
  - `--print-prerequisites`
  - `--install`
  - `--uninstall`
  - optional `--silent`
- [x] Define exit-code contract (`0` success, non-zero failure).
- [x] Define required uninstall artifact precedence:
  - Windows: `uninstall_plugin.exe` -> `uninstall.bat` -> `uninstall_plugin.py`/`uninstall.py`
  - Linux: `uninstall_plugin` -> `uninstall.sh` -> `uninstall_plugin.py`/`uninstall.py`
- [x] Add explicit deprecation policy for Python fallback path (warning on use).

## 2) Plugin Installer Template Update (`metaffi-installer`)

- [x] Update plugin installer template argument parsing to support contract flags.
- [x] Ensure `--check-prerequisites` is install-free and fail-fast.
- [x] Ensure `--install` performs prerequisite gate first.
- [x] Ensure `--uninstall` entrypoint is available and deterministic.
- [x] Keep executable uninstallers as primary artifacts.

## 3) MetaFFI CLI Orchestration Fix (`metaffi-core/CLI`)

- [x] Fix `metaffi --plugin --install <url-or-path>` to run installer by explicit URL/path robustly.
- [x] Support executable/script/python installer invocation selection by file type/platform.
- [x] Pass modern flags first (`--check-prerequisites`, `--install`), fallback only when necessary.
- [x] Improve error output with attempted commands and reasons.
- [x] Implement remove flow fallback chain exactly:
  - executable -> script -> python script
- [x] Emit warning when fallback reaches Python uninstaller.

## 4) Core Uninstaller Alignment (`metaffi-installer/uninstall_template.py`)

- [x] Align plugin removal logic with same precedence chain.
- [x] Keep cascade uninstall behavior (plugins first, then core).
- [x] Make cleanup idempotent and fail-fast on non-recoverable errors.
- [x] Define per-plugin failure policy (stop vs continue) and enforce consistently.

## 5) Legacy Compatibility + Deprecation

- [x] Keep compatibility with existing plugin artifacts where possible.
- [x] Detect old layouts and route via fallback chain.
- [x] Print explicit deprecation warnings for legacy Python-only uninstall.
- [ ] Document removal timeline for legacy path (date/version to be approved).

## 6) Testing

### Unit
- [ ] Invocation resolver: executable/script/python selection.
- [ ] Fallback precedence ordering tests.
- [ ] Warning emission tests for legacy fallback.
- [ ] Exit-code propagation tests.

### Integration
- [ ] Install plugin from local path via `metaffi --plugin --install`.
- [ ] Install plugin from URL via `metaffi --plugin --install`.
- [ ] Remove plugin with only executable uninstaller.
- [ ] Remove plugin with only script wrapper.
- [ ] Remove plugin with only python script (warning expected).
- [ ] Core uninstall cascades through plugins correctly.

### Fail-Fast Validation
- [ ] Contract violation test aborts immediately.
- [ ] Missing required uninstall artifact chain reports actionable error and stops.

## 7) Docs + Release Flow

- [ ] Update installer usage docs to reflect hybrid model.
- [x] Document explicit URL/path plugin install workflow.
- [x] Keep CMake out of installer build path for this phase.
- [x] Add release checklist for core + plugin installer artifacts.

## 8) Docker Validation Spec (Deferred)

- [ ] Define Windows container validation sequence (to implement later in `containers`).
- [ ] Define Ubuntu container validation sequence (to implement later in `containers`).
- [ ] Define pass/fail gates and artifact log capture.

## Open Questions (Must Stop and Ask)

- [x] Confirm exact failure policy in core uninstaller when one plugin uninstall fails:
  - stop immediately, or continue and report all failures?
- [x] Confirm legacy cutoff target version/date for removing Python fallback path.
- [x] Confirm final argument naming style (`--install` etc.) for backward compatibility with existing plugin installers.
