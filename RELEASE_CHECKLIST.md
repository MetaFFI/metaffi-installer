# MetaFFI Installer Release Checklist

## Inputs

- [ ] `METAFFI_WIN_HOME` points to built Windows MetaFFI output.
- [ ] `METAFFI_UBUNTU_HOME` points to built Ubuntu MetaFFI output.
- [ ] Core + plugins are built and their required files exist.

## Build

- [ ] Build Windows core installer:
  - `python build_installer.py --target windows --version <version> --output-name metaffi-installer-<version>-windows`
- [ ] Build Ubuntu core installer:
  - `python build_installer.py --target ubuntu --version <version> --output-name metaffi-installer-<version>-ubuntu`
- [ ] Build combined core installer from the two OS-specific installers:
  - `python build_combined_installer.py --windows-installer <win-exe> --ubuntu-installer <ubuntu-bin> --version <version> --output installers_output/metaffi-installer-<version>`
- [ ] Build plugin installers:
  - `python build_plugin_installer.py <plugin-dev-dir> <plugin-name>`

## CI Gate

- [ ] Before packaging installers, run all CTests and require pass (including tests repo tests):
  - `ctest --test-dir <build-dir> -C <build-type> --output-on-failure`

## Validate Installer Contract

- [ ] Plugin installer supports:
  - `--check-prerequisites`
  - `--print-prerequisites`
  - `--install`
  - `--uninstall`
- [ ] Short aliases supported:
  - `-c`, `-p`, `-i`, `-u`, `-s`

## Validate MetaFFI CLI Orchestration

- [ ] Local install:
  - `metaffi --plugin --install <local-installer-path>`
- [ ] URL install:
  - `metaffi --plugin --install <installer-url>`
- [ ] Remove plugin:
  - `metaffi --plugin --remove <plugin-name>`
- [ ] Confirm list:
  - `metaffi --plugin --list`

## Validate Uninstall Fallback Order

- [ ] Executable uninstaller path works first.
- [ ] Script fallback works when executable is absent.
- [ ] Python fallback works with warning when both are absent.

## Publish Artifacts

- [ ] Upload core installer artifacts.
- [ ] Upload plugin installer artifacts.
- [ ] Publish checksums/signatures (if required).
