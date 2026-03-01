"""
Build a plugin installer zip from a lang-plugin-* directory.

Usage:
  python build_plugin_installer.py --plugin <path-to-lang-plugin-dir> --target <windows|ubuntu> [--config <Debug|Release>] [--version <version>] [--output-dir <path>]

Output:
  installers_output/metaffi-plugin-<name>-<version>-<platform>.zip
"""

import argparse
import glob
import json
import os
import shutil
import sys
import zipfile


class PluginInstallerBuilder:
	"""Reads a plugin manifest and packages the plugin into a distributable zip."""

	def __init__(self, plugin_dir: str, target: str, config: str, version_override: str | None, output_dir_override: str | None):
		self.plugin_dir = os.path.abspath(plugin_dir)
		self.install_dir = os.path.join(self.plugin_dir, 'install')
		self.target = target
		self.config = config

		# Load and validate the manifest (lives under install/)
		manifest_path = os.path.join(self.install_dir, 'plugin_manifest.json')
		if not os.path.isfile(manifest_path):
			raise FileNotFoundError(f"plugin_manifest.json not found in {self.install_dir}")

		with open(manifest_path, 'r') as f:
			self.manifest = json.load(f)

		self.plugin_name = self.manifest['name']
		self.version = version_override or self.manifest.get('version', '0.0.0')

		# Determine the build output base directory
		# --output-dir overrides $METAFFI_HOME as the base for resolving file patterns
		if output_dir_override:
			base_dir = os.path.abspath(output_dir_override)
		else:
			base_dir = os.environ.get('METAFFI_HOME')
			if base_dir is None:
				raise EnvironmentError("METAFFI_HOME is not set (use --output-dir to override)")

		self.output_dir = os.path.join(base_dir, self.plugin_name)
		if not os.path.isdir(self.output_dir):
			raise FileNotFoundError(f"Plugin output directory not found: {self.output_dir}")

	def _resolve_output_globs(self) -> list[tuple[str, str]]:
		"""Resolve files.<platform> glob patterns against the CMake output dir.

		Returns list of (arcname, absolute_path) tuples.
		"""
		platform_key = self.target
		patterns = self.manifest.get('files', {}).get(platform_key, [])
		if not patterns:
			raise ValueError(f"No files listed for platform '{platform_key}' in manifest")

		results: list[tuple[str, str]] = []
		for pattern in patterns:
			# Resolve glob against the output directory
			full_pattern = os.path.join(self.output_dir, pattern)
			matched = glob.glob(full_pattern, recursive=True)

			if not matched:
				raise FileNotFoundError(
					f"Pattern '{pattern}' matched no files in {self.output_dir}"
				)

			for abs_path in matched:
				if os.path.isdir(abs_path):
					continue

				# Skip __pycache__ directories and .pyc files
				if '__pycache__' in abs_path or abs_path.endswith('.pyc'):
					continue

				# Archive name is relative to the output dir
				rel = os.path.relpath(abs_path, self.output_dir).replace('\\', '/')
				results.append((rel, abs_path))

		return results

	def _resolve_extra_files(self) -> list[tuple[str, str]]:
		"""Resolve extra_files glob patterns against the plugin source directory.

		Returns list of (arcname, absolute_path) tuples.
		"""
		extra = self.manifest.get('extra_files', {})
		results: list[tuple[str, str]] = []

		for pattern, target_prefix in extra.items():
			full_pattern = os.path.join(self.plugin_dir, pattern)
			matched = glob.glob(full_pattern, recursive=True)

			if not matched:
				print(f"WARNING: extra_files pattern '{pattern}' matched no files")
				continue

			for abs_path in matched:
				if os.path.isdir(abs_path):
					continue

				# Skip __pycache__ and .pyc files
				if '__pycache__' in abs_path or abs_path.endswith('.pyc'):
					continue

				# Archive name: target_prefix + relative path from the pattern base
				pattern_base = os.path.dirname(os.path.join(self.plugin_dir, pattern.split('*')[0]))
				rel = os.path.relpath(abs_path, pattern_base).replace('\\', '/')
				arcname = target_prefix.rstrip('/') + '/' + rel if target_prefix else rel
				results.append((arcname, abs_path))

		return results

	def build(self) -> str:
		"""Build the plugin zip and return the output path."""

		# Collect all files
		output_files = self._resolve_output_globs()
		extra_files = self._resolve_extra_files()

		# Ensure output directory exists
		os.makedirs('installers_output', exist_ok=True)

		zip_name = f"metaffi-plugin-{self.plugin_name}-{self.version}-{self.target}.zip"
		zip_path = os.path.join('installers_output', zip_name)

		print(f"Building plugin installer: {zip_name}")
		print(f"  Plugin: {self.plugin_name}")
		print(f"  Version: {self.version}")
		print(f"  Target: {self.target}")
		print(f"  Output dir: {self.output_dir}")

		with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
			# Add plugin_manifest.json (from install/ subdir)
			manifest_path = os.path.join(self.install_dir, 'plugin_manifest.json')
			zf.write(manifest_path, arcname='plugin_manifest.json')
			print(f"  + plugin_manifest.json")

			# Add plugin_hooks.py (from install/ subdir)
			hooks_path = os.path.join(self.install_dir, 'plugin_hooks.py')
			if os.path.isfile(hooks_path):
				zf.write(hooks_path, arcname='plugin_hooks.py')
				print(f"  + plugin_hooks.py")
			else:
				print(f"  WARNING: plugin_hooks.py not found in {self.install_dir}")

			# Add output files (DLLs/SOs, jars, etc.)
			for arcname, abs_path in output_files:
				zf.write(abs_path, arcname=arcname)
				print(f"  + {arcname}")

			# Add extra files (tests, helpers, etc.)
			for arcname, abs_path in extra_files:
				zf.write(abs_path, arcname=arcname)
				print(f"  + {arcname} (extra)")

		file_size = os.path.getsize(zip_path)
		print(f"\nCreated: {os.path.abspath(zip_path)} ({file_size:,} bytes)")
		return zip_path


def main():
	parser = argparse.ArgumentParser(description='Build a MetaFFI plugin installer zip')
	parser.add_argument('--plugin', required=True, help='Path to the lang-plugin-* directory')
	parser.add_argument('--target', required=True, choices=['windows', 'ubuntu'], help='Target platform')
	parser.add_argument('--config', default='Debug', choices=['Debug', 'Release'], help='Build configuration (default: Debug)')
	parser.add_argument('--version', default=None, help='Version override (default: from manifest)')
	parser.add_argument('--output-dir', default=None, help='Build output base directory (default: $METAFFI_HOME). Plugin files are resolved under <output-dir>/<plugin-name>/')
	args = parser.parse_args()

	if not os.path.isdir(args.plugin):
		print(f"Error: Plugin directory not found: {args.plugin}")
		sys.exit(1)

	builder = PluginInstallerBuilder(
		plugin_dir=args.plugin,
		target=args.target,
		config=args.config,
		version_override=args.version,
		output_dir_override=args.output_dir
	)

	builder.build()
	print("Done")


if __name__ == '__main__':
	# Set working directory to this script's directory
	os.chdir(os.path.dirname(os.path.abspath(__file__)))
	main()
