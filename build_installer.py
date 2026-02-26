import argparse
import base64
import glob
import io
import os
import platform
import re
import shutil
import subprocess
import zipfile
from typing import List
from version import METAFFI_VERSION


def get_required_env_dir(env_name: str) -> str:
	value = os.getenv(env_name)
	assert value is not None and value != "", f"{env_name} is not set"
	assert os.path.isdir(value), f"{env_name} is not a directory. value={value}. current dir={os.getcwd()}"
	return value.replace("\\", "/") + "/"


def zip_installer_files(files: List[str], root: str):
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
			python3 -m pip install pyinstaller
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


def get_windows_metaffi_files(metaffi_win_home: str):
	files = []
	system32 = os.environ["SystemRoot"] + "/system32/"
	files.extend(["xllr.dll", "metaffi.exe", "uninstall.exe", "boost_filesystem*.dll", "boost_program_options*.dll"])

	required_runtime = [
		(f"{system32}msvcp140.dll", "msvcp140.dll"),
	]
	optional_runtime = [
		(f"{system32}vcruntime140_1d.dll", "vcruntime140_1d.dll"),
		(f"{system32}vcruntime140d.dll", "vcruntime140d.dll"),
		(f"{system32}msvcp140d.dll", "msvcp140d.dll"),
		(f"{system32}ucrtbased.dll", "ucrtbased.dll"),
	]

	for src, dst in required_runtime:
		if not os.path.isfile(src):
			raise FileNotFoundError(f"Required runtime file not found: {src}")
		files.append((src, dst))

	for src, dst in optional_runtime:
		if os.path.isfile(src):
			files.append((src, dst))
		else:
			print(f"Warning: optional runtime file not found, skipping: {src}")

	includes = glob.glob(f"{metaffi_win_home}/include/*")
	includes = ["include/" + os.path.basename(incfile) for incfile in includes]
	files.extend(includes)

	expanded_files = []
	for file_entry in files:
		if isinstance(file_entry, str) and "*" in file_entry:
			matches = glob.glob(os.path.join(metaffi_win_home, file_entry))
			if not matches:
				raise Exception(f"No files found matching pattern: {file_entry}")
			expanded_files.extend(os.path.relpath(match, metaffi_win_home) for match in matches)
		else:
			expanded_files.append(file_entry)

	return expanded_files


def get_ubuntu_metaffi_files(metaffi_ubuntu_home: str):
	files = []
	files.extend(
		[
			"xllr.so",
			"metaffi",
			"uninstall",
			"libboost_filesystem.so.*",
			"libboost_program_options.so.*",
			"libboost_thread.so.*",
		]
	)

	includes = glob.glob(f"{metaffi_ubuntu_home}/include/*")
	includes = ["include/" + os.path.basename(incfile) for incfile in includes]
	files.extend(includes)

	expanded_files = []
	for file_entry in files:
		if isinstance(file_entry, str) and "*" in file_entry:
			matches = glob.glob(os.path.join(metaffi_ubuntu_home, file_entry))
			if not matches:
				raise Exception(f"No files found matching pattern: {file_entry}")
			expanded_files.extend(os.path.relpath(match, metaffi_ubuntu_home) for match in matches)
		else:
			expanded_files.append(file_entry)

	return expanded_files


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
		python3 -m pip install pyinstaller pycrosskit python-dotenv
		pyinstaller --onefile --console --hidden-import pycrosskit --hidden-import pycrosskit.envariables --hidden-import python-dotenv --hidden-import dotenv --name {} --distpath ./installers_output {}
		""".format(
			output_name, output_file_py
		)
		subprocess.run(["wsl", "-e", "bash", "-c", wsl_command], check=True)
	else:
		subprocess.run(["python3", "-m", "pip", "install", "pyinstaller", "pycrosskit", "python-dotenv"], check=True)
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


def build_windows_installer(version: str, output_name: str | None):
	metaffi_win_home = get_required_env_dir("METAFFI_WIN_HOME")
	os.makedirs("./installers_output", exist_ok=True)

	create_uninstaller_exe()
	shutil.copy2("./installers_output/uninstall.exe", metaffi_win_home)

	windows_files = get_windows_metaffi_files(metaffi_win_home)
	windows_zip = zip_installer_files(windows_files, metaffi_win_home)

	output_file_py = "./installers_output/metaffi_installer_windows.py"
	shutil.copy("templates/metaffi_installer_template.py", output_file_py)
	create_installer_file(output_file_py, windows_zip, b"", version)

	if output_name is None or output_name == "":
		output_name = f"metaffi-installer-{version}-windows"

	create_windows_exe(output_file_py, output_name)
	cleanup_temp_files(output_file_py, "./installers_output/uninstall.exe")
	return f"./installers_output/{output_name}.exe"


def build_ubuntu_installer(version: str, output_name: str | None):
	# On Ubuntu, fall back to METAFFI_HOME if METAFFI_UBUNTU_HOME is not set
	env_name = "METAFFI_UBUNTU_HOME"
	if not os.getenv(env_name) and platform.system() == "Linux":
		env_name = "METAFFI_HOME"
	metaffi_ubuntu_home = get_required_env_dir(env_name)
	os.makedirs("./installers_output", exist_ok=True)

	create_uninstaller_elf()
	shutil.copy2("./installers_output/uninstall", metaffi_ubuntu_home)

	ubuntu_files = get_ubuntu_metaffi_files(metaffi_ubuntu_home)
	ubuntu_zip = zip_installer_files(ubuntu_files, metaffi_ubuntu_home)

	output_file_py = "./installers_output/metaffi_installer_ubuntu.py"
	shutil.copy("templates/metaffi_installer_template.py", output_file_py)
	create_installer_file(output_file_py, b"", ubuntu_zip, version)

	if output_name is None or output_name == "":
		output_name = f"metaffi-installer-{version}-ubuntu"

	create_linux_executable(output_file_py, output_name)
	cleanup_temp_files(output_file_py, "./installers_output/uninstall")
	return f"./installers_output/{output_name}"


def build_all_installers(version: str):
	metaffi_ubuntu_home = get_required_env_dir("METAFFI_UBUNTU_HOME")
	metaffi_win_home = get_required_env_dir("METAFFI_WIN_HOME")
	os.makedirs("./installers_output", exist_ok=True)

	create_uninstaller_exe()
	create_uninstaller_elf()

	shutil.copy2("./installers_output/uninstall.exe", metaffi_win_home)
	shutil.copy2("./installers_output/uninstall", metaffi_ubuntu_home)

	windows_files = get_windows_metaffi_files(metaffi_win_home)
	ubuntu_files = get_ubuntu_metaffi_files(metaffi_ubuntu_home)

	windows_zip = zip_installer_files(windows_files, metaffi_win_home)
	ubuntu_zip = zip_installer_files(ubuntu_files, metaffi_ubuntu_home)

	output_file_py = "./installers_output/metaffi_installer.py"
	shutil.copy("templates/metaffi_installer_template.py", output_file_py)
	create_installer_file(output_file_py, windows_zip, ubuntu_zip, version)

	create_windows_exe(output_file_py, f"metaffi-installer-{version}")
	create_linux_executable(output_file_py, f"metaffi-installer-{version}")
	cleanup_temp_files(output_file_py, "./installers_output/uninstall.exe", "./installers_output/uninstall")


def main():
	parser = argparse.ArgumentParser(description="Build MetaFFI installers")
	parser.add_argument("--target", choices=["all", "windows", "ubuntu"], default="all")
	parser.add_argument("--version", default=METAFFI_VERSION)
	parser.add_argument("--output-name", default=None, help="Optional output installer name (without extension)")
	args = parser.parse_args()

	if args.target == "all":
		build_all_installers(args.version)
		print("Done")
		return
	if args.target == "windows":
		output = build_windows_installer(args.version, args.output_name)
		print(f"Done. Built: {os.path.abspath(output)}")
		return
	if args.target == "ubuntu":
		output = build_ubuntu_installer(args.version, args.output_name)
		print(f"Done. Built: {os.path.abspath(output)}")
		return

	raise ValueError(f"Unknown target: {args.target}")


if __name__ == "__main__":
	script_dir = os.path.dirname(os.path.abspath(__file__))
	os.chdir(script_dir)
	main()
