#!/usr/bin/env bash
set -euo pipefail

WORKFLOW="manual-build-installers.yml"
REPO="MetaFFI/metaffi-installer"
VERSION=""
BUILD_TYPE=""
PUBLISH=""

print_help() {
	cat <<'EOF'
Run MetaFFI manual CI workflow.

Usage:
  ./run_ci.sh [options]

Options:
  --version <value>       Installer version (example: 0.3.1)
  --build-type <value>    CMake build type: Debug | Release | RelWithDebInfo
  --publish <value>       Publish release assets: true | false
  --repo <value>          GitHub repo in owner/name form (default: MetaFFI/metaffi-installer)
  --workflow <value>      Workflow file/name (default: manual-build-installers.yml)
  -h, --help              Show this help

Examples:
  ./run_ci.sh --version 0.3.1 --build-type Release --publish false
  ./run_ci.sh --version 0.3.1 --build-type RelWithDebInfo --publish true --repo MetaFFI/metaffi-installer
EOF
}

normalize_publish() {
	local value
	value="$(echo "${1}" | tr '[:upper:]' '[:lower:]')"
	case "${value}" in
		true|false) echo "${value}" ;;
		yes|y|1) echo "true" ;;
		no|n|0) echo "false" ;;
		*) return 1 ;;
	esac
}

validate_build_type() {
	case "${1}" in
		Debug|Release|RelWithDebInfo) return 0 ;;
		*) return 1 ;;
	esac
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--version)
			[[ $# -ge 2 ]] || { echo "Missing value for --version"; exit 1; }
			VERSION="$2"
			shift 2
			;;
		--build-type)
			[[ $# -ge 2 ]] || { echo "Missing value for --build-type"; exit 1; }
			BUILD_TYPE="$2"
			shift 2
			;;
		--publish)
			[[ $# -ge 2 ]] || { echo "Missing value for --publish"; exit 1; }
			PUBLISH="$2"
			shift 2
			;;
		--repo)
			[[ $# -ge 2 ]] || { echo "Missing value for --repo"; exit 1; }
			REPO="$2"
			shift 2
			;;
		--workflow)
			[[ $# -ge 2 ]] || { echo "Missing value for --workflow"; exit 1; }
			WORKFLOW="$2"
			shift 2
			;;
		-h|--help)
			print_help
			exit 0
			;;
		*)
			echo "Unknown argument: $1"
			print_help
			exit 1
			;;
	esac
done

if [[ -z "${VERSION}" ]]; then
	read -r -p "Missing --version. Example: 0.3.1. Enter version: " VERSION
fi
while [[ -z "${VERSION}" ]]; do
	read -r -p "Version cannot be empty. Example: 0.3.1. Enter version: " VERSION
done

if [[ -z "${BUILD_TYPE}" ]]; then
	read -r -p "Missing --build-type. Allowed: Debug | Release | RelWithDebInfo. Example: Release. Enter build type: " BUILD_TYPE
fi
while ! validate_build_type "${BUILD_TYPE}"; do
	read -r -p "Invalid build type '${BUILD_TYPE}'. Allowed: Debug | Release | RelWithDebInfo. Enter build type: " BUILD_TYPE
done

if [[ -z "${PUBLISH}" ]]; then
	read -r -p "Missing --publish. Allowed: true | false. Example: false. Enter publish flag: " PUBLISH
fi
while ! PUBLISH="$(normalize_publish "${PUBLISH}")"; do
	read -r -p "Invalid publish value. Allowed: true | false (or yes/no, 1/0). Enter publish flag: " PUBLISH
done

if ! command -v gh >/dev/null 2>&1; then
	echo "GitHub CLI ('gh') not found in PATH."
	exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
	echo "GitHub CLI is not authenticated. Run: gh auth login"
	exit 1
fi

echo "Running workflow..."
echo "  repo: ${REPO}"
echo "  workflow: ${WORKFLOW}"
echo "  version: ${VERSION}"
echo "  build_type: ${BUILD_TYPE}"
echo "  publish: ${PUBLISH}"

gh workflow run "${WORKFLOW}" \
	-R "${REPO}" \
	-f "version=${VERSION}" \
	-f "build_type=${BUILD_TYPE}" \
	-f "publish=${PUBLISH}"

echo "Workflow dispatch submitted."
