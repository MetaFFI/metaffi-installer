@echo off
setlocal EnableDelayedExpansion

set "WORKFLOW=manual-build-installers.yml"
set "REPO=MetaFFI/metaffi-installer"
set "VERSION="
set "BUILD_TYPE="
set "PUBLISH="

if "%~1"=="" goto after_parse

:parse_args
if "%~1"=="" goto after_parse

if /I "%~1"=="-h" goto show_help
if /I "%~1"=="--help" goto show_help

if /I "%~1"=="--version" (
	if "%~2"=="" (
		echo Missing value for --version
		exit /b 1
	)
	set "VERSION=%~2"
	shift
	shift
	goto parse_args
)

if /I "%~1"=="--build-type" (
	if "%~2"=="" (
		echo Missing value for --build-type
		exit /b 1
	)
	set "BUILD_TYPE=%~2"
	shift
	shift
	goto parse_args
)

if /I "%~1"=="--publish" (
	if "%~2"=="" (
		echo Missing value for --publish
		exit /b 1
	)
	set "PUBLISH=%~2"
	shift
	shift
	goto parse_args
)

if /I "%~1"=="--repo" (
	if "%~2"=="" (
		echo Missing value for --repo
		exit /b 1
	)
	set "REPO=%~2"
	shift
	shift
	goto parse_args
)

if /I "%~1"=="--workflow" (
	if "%~2"=="" (
		echo Missing value for --workflow
		exit /b 1
	)
	set "WORKFLOW=%~2"
	shift
	shift
	goto parse_args
)

echo Unknown argument: %~1
goto show_help_error

:after_parse
if "%VERSION%"=="" (
	set /p VERSION=Missing --version. Example: 0.3.1. Enter version: 
)
:ask_version_again
if "%VERSION%"=="" (
	set /p VERSION=Version cannot be empty. Example: 0.3.1. Enter version: 
	goto ask_version_again
)

if "%BUILD_TYPE%"=="" (
	set /p BUILD_TYPE=Missing --build-type. Allowed: Debug ^| Release ^| RelWithDebInfo. Example: Release. Enter build type: 
)

:validate_build_type
if /I "%BUILD_TYPE%"=="Debug" goto build_type_ok
if /I "%BUILD_TYPE%"=="Release" goto build_type_ok
if /I "%BUILD_TYPE%"=="RelWithDebInfo" goto build_type_ok
set /p BUILD_TYPE=Invalid build type "%BUILD_TYPE%". Allowed: Debug ^| Release ^| RelWithDebInfo. Enter build type: 
goto validate_build_type

:build_type_ok
if "%PUBLISH%"=="" (
	set /p PUBLISH=Missing --publish. Allowed: true ^| false. Example: false. Enter publish flag: 
)

:normalize_publish
if /I "%PUBLISH%"=="true" set "PUBLISH=true" & goto publish_ok
if /I "%PUBLISH%"=="false" set "PUBLISH=false" & goto publish_ok
if /I "%PUBLISH%"=="yes" set "PUBLISH=true" & goto publish_ok
if /I "%PUBLISH%"=="y" set "PUBLISH=true" & goto publish_ok
if /I "%PUBLISH%"=="1" set "PUBLISH=true" & goto publish_ok
if /I "%PUBLISH%"=="no" set "PUBLISH=false" & goto publish_ok
if /I "%PUBLISH%"=="n" set "PUBLISH=false" & goto publish_ok
if /I "%PUBLISH%"=="0" set "PUBLISH=false" & goto publish_ok
set /p PUBLISH=Invalid publish value. Allowed: true ^| false ^(or yes/no, 1/0^). Enter publish flag: 
goto normalize_publish

:publish_ok
where gh >nul 2>nul
if errorlevel 1 (
	echo GitHub CLI ^('gh'^) not found in PATH.
	exit /b 1
)

gh auth status >nul 2>nul
if errorlevel 1 (
	echo GitHub CLI is not authenticated. Run: gh auth login
	exit /b 1
)

echo Running workflow...
echo   repo: %REPO%
echo   workflow: %WORKFLOW%
echo   version: %VERSION%
echo   build_type: %BUILD_TYPE%
echo   publish: %PUBLISH%

gh workflow run "%WORKFLOW%" -R "%REPO%" -f "version=%VERSION%" -f "build_type=%BUILD_TYPE%" -f "publish=%PUBLISH%"
if errorlevel 1 exit /b 1

echo Workflow dispatch submitted.
exit /b 0

:show_help
echo Run MetaFFI manual CI workflow.
echo.
echo Usage:
echo   run_ci.bat [options]
echo.
echo Options:
echo   --version ^<value^>       Installer version ^(example: 0.3.1^)
echo   --build-type ^<value^>    CMake build type: Debug ^| Release ^| RelWithDebInfo
echo   --publish ^<value^>       Publish release assets: true ^| false
echo   --repo ^<value^>          GitHub repo in owner/name form ^(default: MetaFFI/metaffi-installer^)
echo   --workflow ^<value^>      Workflow file/name ^(default: manual-build-installers.yml^)
echo   -h, --help                Show this help
echo.
echo Examples:
echo   run_ci.bat --version 0.3.1 --build-type Release --publish false
echo   run_ci.bat --version 0.3.1 --build-type RelWithDebInfo --publish true --repo MetaFFI/metaffi-installer
exit /b 0

:show_help_error
call :show_help
exit /b 1
