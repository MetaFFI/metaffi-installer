import argparse
import base64
import glob
import io
import json
import os
import platform
import re
import shutil
import subprocess
import zipfile
from typing import List, Tuple, Union

from version import METAFFI_VERSION


FileEntry = Union[str, Tuple[str, str]]


def get_ubuntu_version_tag() -> str:
	"""Returns the Ubuntu version as a compact tag (e.g. '2204', '2404').

	On Linux, reads from /etc/os-release. On Windows, queries WSL.
	Falls back to 'unknown' if detection fails.
	"""
	try:
		if platform.system() == "Linux":
			with open("/etc/os-release", "r") as f:
				for line in f:
					if line.startswith("VERSION_ID="):
						ver = line.strip().split("=", 1)[1].strip('"')
						return ver.replace(".", "")
		else:
			# Query WSL for the Ubuntu version
			result = subprocess.run(
				["wsl", "-e", "bash", "-c", ". /etc/os-release && echo $VERSION_ID"],
				capture_output=True, text=True, timeout=10
			)
			if result.returncode == 0:
				ver = result.stdout.strip().strip('"')
				if ver:
					return ver.replace(".", "")
	except Exception as e:
		print(f"Warning: could not detect Ubuntu version: {e}")

	return "unknown"


def get_project_root() -> str:
	"""Returns the MetaFFI project root (parent of metaffi-installer/)."""
	return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_output_dir(target: str, config: str) -> str:
	"""Derives the output directory path from convention: {project_root}/output/{os}/x64/{config}/."""
	os_name = {"windows": "windows", "ubuntu": "ubuntu"}[target]
	path = os.path.join(get_project_root(), "output", os_name, "x64", config)
	assert os.path.isdir(path), f"Output dir not found: {path}"
	return path.replace("\\", "/") + "/"


def load_manifest() -> dict:
	"""Reads installer_manifest.json from the script directory."""
	manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "installer_manifest.json")
	with open(manifest_path, "r") as f:
		return json.load(f)


def resolve_manifest_files(entries: list, output_dir: str) -> List[FileEntry]:
	"""Resolves manifest entries into a list of file entries for zip_installer_files().

	Each entry can be:
	- A string: relative glob/path resolved against output_dir
	- A dict with 'src' and 'dest': src supports env var expansion and globs.
	  If relative, resolved against output_dir. If dest ends with '/', basename is appended.
	  If 'optional' is true, missing files produce a warning instead of an error.

	Returns a list of strings (relative paths) and (abs_src, arcname) tuples.
	"""
	result: List[FileEntry] = []

	for entry in entries:
		if isinstance(entry, str):
			# Simple string entry — relative glob against output_dir
			matches = glob.glob(os.path.join(output_dir, entry))
			if not matches:
				raise FileNotFoundError(f"No files found matching pattern: {entry} in {output_dir}")

			for match in matches:
				rel = os.path.relpath(match, output_dir).replace("\\", "/")
				result.append(rel)

		elif isinstance(entry, dict):
			src_pattern = entry["src"]
			dest = entry["dest"]
			optional = entry.get("optional", False)

			# Expand environment variables in src
			src_pattern = os.path.expandvars(src_pattern)

			# If relative, resolve against output_dir
			if not os.path.isabs(src_pattern):
				src_pattern = os.path.join(output_dir, src_pattern)

			# Normalize path separators
			src_pattern = src_pattern.replace("\\", "/")

			# Expand globs
			matches = glob.glob(src_pattern)

			if not matches:
				if optional:
					print(f"Warning: optional file not found, skipping: {src_pattern}")
					continue
				else:
					raise FileNotFoundError(f"Required file not found: {src_pattern}")

			for match in matches:
				abs_src = match.replace("\\", "/")

				# If dest ends with '/', put file into that directory keeping its basename
				if dest.endswith("/"):
					arcname = dest + os.path.basename(match)
				else:
					arcname = dest

				result.append((abs_src, arcname))

		else:
			raise ValueError(f"Unexpected manifest entry type: {type(entry)}")

	return result


def zip_installer_files(files: List[FileEntry], root: str):
	buffer = io.BytesIO()
	with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
		for file in files:
			arcname = file
			is_specifies_arcname = False
			if isinstance(file, tuple):
				is_specifies_arcname = True
				arcname = file[1]
				file = file[0]

			if is_specifies_arcname:
				zf.write(file, arcname=arcname)
			else:
				if os.path.isabs(file):
					zf.write(file, arcname=arcname)
				else:
					zf.write(root + file, arcname=arcname)

	return buffer.getvalue()


def create_installer_file(python_source_filename: str, windows_zip: bytes, ubuntu_zip: bytes, version: str):
	windows_zip_str = base64.b64encode(windows_zip)
	ubuntu_zip_str = base64.b64encode(ubuntu_zip)

	with open("templates/metaffi_installer_template.py", "r") as f:
		source_code = f.read()

	source_code = re.sub(r"windows_x64_zip\s*=\s*.+", f"windows_x64_zip = {windows_zip_str}", source_code, count=1)
	source_code = re.sub(r"ubuntu_x64_zip\s*=\s*.+", f"ubuntu_x64_zip = {ubuntu_zip_str}", source_code, count=1)
	source_code = re.sub(r"METAFFI_VERSION\s*=\s*.+", f"METAFFI_VERSION = '{version}'", source_code, count=1)

	with open(python_source_filename, "w") as f:
		f.write(source_code)


def create_uninstaller_exe():
	print("Creating Windows uninstaller executable...")
	subprocess.run(["pip", "install", "pyinstaller"], check=True)

	temp_dir = os.path.join(os.getcwd(), "temp_build")
	os.makedirs(temp_dir, exist_ok=True)

	try:
		shutil.copy("templates/uninstall_template.py", os.path.join(temp_dir, "uninstaller.py"))
		subprocess.run(
			[
				"pyinstaller",
				"--onefile",
				"--console",
				"--name",
				"uninstall",
				"--distpath",
				temp_dir,
				os.path.join(temp_dir, "uninstaller.py"),
			],
			check=True,
		)
		shutil.copy2(os.path.join(temp_dir, "uninstall.exe"), "./installers_output/uninstall.exe")
	finally:
		if os.path.exists("build"):
			shutil.rmtree("build", ignore_errors=True)
		for spec_file in glob.glob("uninstall.spec"):
			os.remove(spec_file)
		shutil.rmtree(temp_dir, ignore_errors=True)


def create_uninstaller_elf():
	print("Creating Linux uninstaller executable...")
	temp_dir = os.path.join(os.getcwd(), "temp_build")
	os.makedirs(temp_dir, exist_ok=True)

	try:
		shutil.copy("templates/uninstall_template.py", os.path.join(temp_dir, "uninstaller.py"))

		if platform.system() == "Windows":
			def to_wsl_path(path: str):
				path = path.replace("\\", "/")
				if path.startswith("C:") or path.startswith("c:"):
					path = "/mnt/c" + path[2:]
				return path

			wsl_temp_dir = to_wsl_path(temp_dir)
			wsl_output_dir = to_wsl_path(os.path.join(os.getcwd(), "installers_output"))
			wsl_command = f"""
			cd "{wsl_temp_dir}"
			python3 -m venv .venv
			source .venv/bin/activate
			pip install pyinstaller
			pyinstaller --onefile --console --name uninstall --distpath "{wsl_temp_dir}" uninstaller.py
			cp "{wsl_temp_dir}/uninstall" "{wsl_output_dir}/"
			"""
			subprocess.run(["wsl", "-e", "bash", "-c", wsl_command], check=True)
		else:
			subprocess.run(["python3", "-m", "pip", "install", "pyinstaller"], check=True)
			subprocess.run(
				[
					"pyinstaller",
					"--onefile",
					"--console",
					"--name",
					"uninstall",
					"--distpath",
					"./installers_output",
					os.path.join(temp_dir, "uninstaller.py"),
				],
				check=True,
			)
	finally:
		shutil.rmtree(temp_dir, ignore_errors=True)
		if os.path.exists("build"):
			shutil.rmtree("build", ignore_errors=True)
		for spec_file in glob.glob("uninstall.spec"):
			os.remove(spec_file)


def get_windows_metaffi_files(output_dir: str) -> List[FileEntry]:
	"""Loads Windows file list from the manifest and resolves against output_dir."""
	manifest = load_manifest()
	return resolve_manifest_files(manifest["windows"]["files"], output_dir)


def get_ubuntu_metaffi_files(output_dir: str) -> List[FileEntry]:
	"""Loads Ubuntu file list from the manifest and resolves against output_dir."""
	manifest = load_manifest()
	return resolve_manifest_files(manifest["ubuntu"]["files"], output_dir)


def create_windows_exe(output_file_py: str, output_name: str):
	print("Creating Windows executable...")
	subprocess.run(["pip", "install", "pyinstaller"], check=True)
	subprocess.run(
		[
			"pyinstaller",
			"--onefile",
			"--console",
			"--name",
			output_name,
			"--distpath",
			"./installers_output",
			output_file_py,
		],
		check=True,
	)
	if os.path.exists("build"):
		shutil.rmtree("build", ignore_errors=True)
	for spec_file in glob.glob("metaffi-installer-*.spec"):
		os.remove(spec_file)
	for spec_file in glob.glob(f"{output_name}.spec"):
		os.remove(spec_file)


def create_linux_executable(output_file_py: str, output_name: str):
	print("Creating Linux executable...")
	if platform.system() == "Windows":
		if os.path.isabs(output_file_py):
			output_file_py = output_file_py[0].lower() + output_file_py[1:]
			output_file_py = output_file_py.replace(":", "").replace("\\", "/")
			output_file_py = "/mnt/" + output_file_py

		wsl_command = """
		python3 -m venv .venv
		source .venv/bin/activate
		pip install pyinstaller pycrosskit python-dotenv distro
		pyinstaller --onefile --console --hidden-import pycrosskit --hidden-import pycrosskit.envariables --hidden-import python-dotenv --hidden-import dotenv --hidden-import distro --name {} --distpath ./installers_output {}
		""".format(
			output_name, output_file_py
		)
		subprocess.run(["wsl", "-e", "bash", "-c", wsl_command], check=True)
	else:
		subprocess.run(["python3", "-m", "pip", "install", "pyinstaller", "pycrosskit", "python-dotenv", "distro"], check=True)
		subprocess.run(
			[
				"pyinstaller",
				"--onefile",
				"--console",
				"--hidden-import",
				"pycrosskit",
				"--hidden-import",
				"pycrosskit.envariables",
				"--hidden-import",
				"python-dotenv",
				"--hidden-import",
				"dotenv",
				"--hidden-import",
				"distro",
				"--name",
				output_name,
				"--distpath",
				"./installers_output",
				output_file_py,
			],
			check=True,
		)

	if os.path.exists("build"):
		shutil.rmtree("build", ignore_errors=True)
	for spec_file in glob.glob(f"{output_name}.spec"):
		os.remove(spec_file)


def cleanup_temp_files(*paths: str):
	for p in paths:
		if p and os.path.exists(p):
			os.remove(p)


def build_windows_installer(version: str, output_name: str | None, config: str):
	output_dir = get_output_dir("windows", config)
	os.makedirs("./installers_output", exist_ok=True)

	create_uninstaller_exe()
	shutil.copy2("./installers_output/uninstall.exe", output_dir)

	windows_files = get_windows_metaffi_files(output_dir)
	windows_zip = zip_installer_files(windows_files, output_dir)

	output_file_py = "./installers_output/metaffi_installer_windows.py"
	shutil.copy("templates/metaffi_installer_template.py", output_file_py)
	create_installer_file(output_file_py, windows_zip, b"", version)

	if output_name is None or output_name == "":
		output_name = f"metaffi-installer-{version}-windows"

	create_windows_exe(output_file_py, output_name)
	cleanup_temp_files(output_file_py, "./installers_output/uninstall.exe")
	return f"./installers_output/{output_name}.exe"


def build_ubuntu_installer(version: str, output_name: str | None, config: str):
	output_dir = get_output_dir("ubuntu", config)
	os.makedirs("./installers_output", exist_ok=True)

	create_uninstaller_elf()
	shutil.copy2("./installers_output/uninstall", output_dir)

	ubuntu_files = get_ubuntu_metaffi_files(output_dir)
	ubuntu_zip = zip_installer_files(ubuntu_files, output_dir)

	output_file_py = "./installers_output/metaffi_installer_ubuntu.py"
	shutil.copy("templates/metaffi_installer_template.py", output_file_py)
	create_installer_file(output_file_py, b"", ubuntu_zip, version)

	if output_name is None or output_name == "":
		ubuntu_tag = get_ubuntu_version_tag()
		output_name = f"metaffi-installer-{version}-ubuntu-{ubuntu_tag}"

	create_linux_executable(output_file_py, output_name)
	cleanup_temp_files(output_file_py, "./installers_output/uninstall")
	return f"./installers_output/{output_name}"


def build_all_installers(version: str, config: str):
	windows_output_dir = get_output_dir("windows", config)
	ubuntu_output_dir = get_output_dir("ubuntu", config)
	os.makedirs("./installers_output", exist_ok=True)

	create_uninstaller_exe()
	create_uninstaller_elf()

	shutil.copy2("./installers_output/uninstall.exe", windows_output_dir)
	shutil.copy2("./installers_output/uninstall", ubuntu_output_dir)

	windows_files = get_windows_metaffi_files(windows_output_dir)
	ubuntu_files = get_ubuntu_metaffi_files(ubuntu_output_dir)

	windows_zip = zip_installer_files(windows_files, windows_output_dir)
	ubuntu_zip = zip_installer_files(ubuntu_files, ubuntu_output_dir)

	output_file_py = "./installers_output/metaffi_installer.py"
	shutil.copy("templates/metaffi_installer_template.py", output_file_py)
	create_installer_file(output_file_py, windows_zip, ubuntu_zip, version)

	ubuntu_tag = get_ubuntu_version_tag()
	create_windows_exe(output_file_py, f"metaffi-installer-{version}-windows")
	create_linux_executable(output_file_py, f"metaffi-installer-{version}-ubuntu-{ubuntu_tag}")
	cleanup_temp_files(output_file_py, "./installers_output/uninstall.exe", "./installers_output/uninstall")


def prompt_choice(prompt_text: str, flag: str, choices: list[str], default: str | None = None) -> str:
	"""Prompts the user to pick from a list of choices via stdin."""
	choices_display = []
	for c in choices:
		if c == default:
			choices_display.append(f"{c} (default)")
		else:
			choices_display.append(c)

	print(f"\n{prompt_text} ({flag})")
	for i, label in enumerate(choices_display, 1):
		print(f"  {i}. {label}")

	while True:
		hint = f" [{default}]" if default else ""
		raw = input(f"Enter choice (1-{len(choices)}){hint}: ").strip()

		# Empty input → use default if available
		if raw == "" and default is not None:
			return default

		# Accept the choice text directly (case-insensitive)
		for c in choices:
			if raw.lower() == c.lower():
				return c

		# Accept numeric index
		try:
			idx = int(raw)
			if 1 <= idx <= len(choices):
				return choices[idx - 1]
		except ValueError:
			pass

		print(f"Invalid choice. Please enter a number 1-{len(choices)} or one of: {', '.join(choices)}")


def prompt_string(prompt_text: str, flag: str, default: str | None = None) -> str:
	"""Prompts the user for a free-text value via stdin."""
	hint = f" [{default}]" if default else ""
	raw = input(f"\n{prompt_text} ({flag}){hint}: ").strip()
	if raw == "" and default is not None:
		return default
	if raw == "":
		raise ValueError(f"A value is required for: {prompt_text}")
	return raw


def main():
	parser = argparse.ArgumentParser(
		description="Build MetaFFI installers",
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog="""examples:
  %(prog)s --target windows --config Debug
  %(prog)s --target ubuntu --config Release --version 1.0.0
  %(prog)s --target all --config Debug
  %(prog)s                                    (interactive prompts)"""
	)
	parser.add_argument("--target", choices=["all", "windows", "ubuntu"], default=None,
						help="Target platform: all, windows, or ubuntu")
	parser.add_argument("--version", default=None,
						help=f"Installer version (default: {METAFFI_VERSION})")
	parser.add_argument("--config", default=None,
						help="Build configuration: Debug or Release (default: Debug)")
	parser.add_argument("--output-name", default=None,
						help="Output installer name without extension (default: auto-generated)")
	args = parser.parse_args()

	# Prompt for any missing switches
	target = args.target if args.target is not None else prompt_choice(
		"Select target platform:", "--target", ["all", "windows", "ubuntu"], default="all"
	)

	version = args.version if args.version is not None else prompt_string(
		"Enter version", "--version", default=METAFFI_VERSION
	)

	config = args.config if args.config is not None else prompt_choice(
		"Select build configuration:", "--config", ["Debug", "Release"], default="Debug"
	)

	# Only prompt for output-name if the flag was not provided at all
	output_name_provided = args.output_name is not None
	output_name = args.output_name
	if output_name is not None and output_name.lower() == "auto":
		output_name = None
	if not output_name_provided and target != "all":
		raw = input(f"\nOptional output installer name, without extension (--output-name) [auto]: ").strip()
		if raw and raw.lower() != "auto":
			output_name = raw

	# Build
	if target == "all":
		build_all_installers(version, config)
		print("Done")
		return

	if target == "windows":
		output = build_windows_installer(version, output_name, config)
		print(f"Done. Built: {os.path.abspath(output)}")
		return

	if target == "ubuntu":
		output = build_ubuntu_installer(version, output_name, config)
		print(f"Done. Built: {os.path.abspath(output)}")
		return

	raise ValueError(f"Unknown target: {target}")


if __name__ == "__main__":
	script_dir = os.path.dirname(os.path.abspath(__file__))
	os.chdir(script_dir)
	main()
