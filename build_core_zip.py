"""
Build a core files zip from the installer manifest.

Produces a zip containing the MetaFFI core files (xllr, metaffi CLI,
headers, etc.) that can be extracted directly into METAFFI_HOME without
needing the PyInstaller-wrapped installer.

Usage:
  python build_core_zip.py --target <windows|ubuntu> --version <version> --build-type <Debug|Release>

Output:
  installers_output/metaffi-core-<version>-<build_type>-<target>.zip
"""

import argparse
import glob
import json
import os
import sys
import zipfile


def resolve_output_dir(target: str, build_type: str) -> str:
	"""Determine the build output directory from environment or convention."""
	if target == "windows":
		env_var = "METAFFI_WIN_HOME"
	else:
		env_var = "METAFFI_UBUNTU_HOME"

	output_dir = os.environ.get(env_var)
	if not output_dir:
		output_dir = os.environ.get("METAFFI_HOME")
	if not output_dir:
		raise EnvironmentError(
			f"Neither {env_var} nor METAFFI_HOME is set. "
			f"Set one to point at the build output directory."
		)
	return output_dir


def collect_files(manifest_entries: list, output_dir: str) -> list[tuple[str, str]]:
	"""Resolve manifest entries into (absolute_path, arcname) pairs."""
	result = []

	for entry in manifest_entries:
		if isinstance(entry, str):
			matches = glob.glob(os.path.join(output_dir, entry))
			if not matches:
				raise FileNotFoundError(f"No files found matching: {entry} in {output_dir}")
			for match in matches:
				arcname = os.path.relpath(match, output_dir).replace("\\", "/")
				result.append((match, arcname))

		elif isinstance(entry, dict):
			src_pattern = entry["src"]
			dest = entry["dest"]
			optional = entry.get("optional", False)

			# Expand environment variables
			src_pattern = os.path.expandvars(src_pattern)

			# Resolve relative paths against output_dir
			if not os.path.isabs(src_pattern):
				src_pattern = os.path.join(output_dir, src_pattern)

			src_pattern = src_pattern.replace("\\", "/")
			matches = glob.glob(src_pattern)

			if not matches:
				if optional:
					print(f"  [skip] optional file not found: {src_pattern}")
					continue
				else:
					raise FileNotFoundError(f"Required file not found: {src_pattern}")

			for match in matches:
				if dest.endswith("/"):
					arcname = dest + os.path.basename(match)
				else:
					arcname = dest
				result.append((match, arcname))

	return result


def main():
	parser = argparse.ArgumentParser(description="Build MetaFFI core files zip")
	parser.add_argument("--target", required=True, choices=["windows", "ubuntu"])
	parser.add_argument("--version", required=True)
	parser.add_argument("--build-type", required=True)
	args = parser.parse_args()

	# Load manifest
	manifest_path = os.path.join(os.path.dirname(__file__), "installer_manifest.json")
	with open(manifest_path, "r") as f:
		manifest = json.load(f)

	target_manifest = manifest.get(args.target)
	if not target_manifest:
		print(f"Error: no manifest entries for target '{args.target}'", file=sys.stderr)
		sys.exit(1)

	output_dir = resolve_output_dir(args.target, args.build_type)
	print(f"Core zip: target={args.target}, version={args.version}, build_type={args.build_type}")
	print(f"Output dir: {output_dir}")

	# Collect files from manifest
	files = collect_files(target_manifest["files"], output_dir)

	# Create zip
	os.makedirs("installers_output", exist_ok=True)
	zip_name = f"metaffi-core-{args.version}-{args.build_type}-{args.target}.zip"
	zip_path = os.path.join("installers_output", zip_name)

	with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
		for abs_path, arcname in files:
			print(f"  + {arcname}")
			zf.write(abs_path, arcname)

	file_size = os.path.getsize(zip_path)
	print(f"\nCreated: {os.path.abspath(zip_path)} ({file_size:,} bytes)")


if __name__ == "__main__":
	main()
