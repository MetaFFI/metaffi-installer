## MetaFFI v0.3.1

### Changes
- **Static linking**: All core and plugin libraries now link vcpkg dependencies statically (`x64-windows-static-md` / `x64-linux-dynamic`), eliminating runtime vcpkg DLL/SO path issues on end-user machines.
- **Build system hardening**: Improved vcpkg detection, manifest-mode fallback, and port-name normalization in CMake macros.
- **Python CMake integration**: Python resolved via `find_program` for more reliable cross-environment builds.
- **pip stability**: Stabilized pip package installation across CI and local environments.
- **Go plugin**: Restored and updated with the new SDK; CGO include flags now correctly propagated in CTest runners.
- **JVM plugin**: Restored with the new SDK; JAVA_HOME kept aligned with Java executable across CTest runs; `DestroyJavaVM` hang avoided by letting process exit handle cleanup.
- **Python3 plugin**: PATH handling in CTest runners corrected.
- **C++ plugin**: New plugin installer for C/C++ language support. Includes runtime (`xllr.cpp`), API (`metaffi.api.cpp`), compiler (`metaffi.compiler.cpp`), IDL (`metaffi.idl.cpp`), and libclang.
- **CI**: Dual-platform CI (Windows + Ubuntu) fully green; all 10 release artifacts produced automatically (2 installers + 8 plugin zips).

### Known Issues
- `java->go` MetaFFI full benchmark crashes (ShouldNotReachHere / handle-release lifecycle) — investigation ongoing.
- `java->python3` MetaFFI `xcall_no_params_ret` bug causes `object_method` benchmark failure.
- Go + JVM on Windows: VEH/SEH interaction (Go issues #47576, #58542) mitigated via `CreateThread` wrapper but root cause is an upstream Go bug.
