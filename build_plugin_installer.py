import glob
import os
from posixpath import isabs
import zipfile
import io
import base64
import shutil
import re
from typing import List, Tuple, Dict
import platform
import subprocess
from version import METAFFI_VERSION
import sys
from colorama import Fore


"""
Expected files in plugin directory:
1. build_plugin_installer_helper.py:
	- check_prerequisites()->bool function that checks if the prerequisites are met.
	- print_prerequisites() function that prints the prerequisites.
	- get_files(win_metaffi_home, ubuntu_metaffi_home)->Tuple[Dict[str, str], Dict[str, str]] function that returns a list of files to be installed for windows and ubuntu.
	- setup_environment() function that sets up the environment for the plugin. Will be executed after the files are installed.
	- (optional) post_copy_files() called after the files have been copied to the installer

2. uninstall_plugin.py:
	- Script with its own main, teardowns the environment and removes the files installed OUTSIDE the plugin directory.
	- The plugin directory will be removed by MetaFFI uninstaller.
"""


def zip_installer_files(files: Dict[str, str], root: str):
	# Create a file-like object in memory
	buffer = io.BytesIO()
	
	# Create a zip file object and write the files to it
	# Use the highest compression level
	with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
		for arcname, local_file_path in files.items():
			the_root = root
			
			# Read the file from the filename using the parameters and value "root+file"
			# Write the file into the zip with the filename written in "file" value
			if os.path.isabs(local_file_path):
				if not os.path.exists(local_file_path):
					raise FileNotFoundError(f"File not found: '{local_file_path}'")

				zf.write(local_file_path, arcname=arcname)
			else:
				if not os.path.exists(the_root + local_file_path):
					raise FileNotFoundError(f"File not found. root: '{the_root}' relative: '{local_file_path}'")

				zf.write(the_root + local_file_path, arcname=arcname)
	
	# Get the byte array from the buffer
	return buffer.getvalue()


def create_plugin_installer_file(generated_installer_name: str, plugin_name: str, windows_zip: bytes, ubuntu_zip: bytes, setup_environment_code: str, check_prerequisites_code: str, print_prerequisites_code: str, version: str = METAFFI_VERSION):
	# Encode the binary data to base64 strings
	windows_zip_str = base64.b64encode(windows_zip)
	ubuntu_zip_str = base64.b64encode(ubuntu_zip)
	
	# Open the source file in read mode
	with open('metaffi_plugin_installer_template.py', "r") as f:
		# Read the source code as a string
		source_code = f.read()
	
	# Find and replace the variables with the encoded strings
	source_code = re.sub(r"windows_x64_zip\s*=\s*.+", f"windows_x64_zip = {windows_zip_str}", source_code, count=1)
	source_code = re.sub(r"ubuntu_x64_zip\s*=\s*.+", f"ubuntu_x64_zip = {ubuntu_zip_str}", source_code, count=1)
	source_code = re.sub(r"PLUGIN_VERSION\s*=\s*.+", f"METAFFI_VERSION = '{version}'", source_code, count=1)
	source_code = re.sub('def setup_environment\\(\\):\n\tpass\n', setup_environment_code, source_code, count=1)
	source_code = re.sub('def check_prerequisites\\(\\) -> bool:\n\tpass\n', check_prerequisites_code, source_code, count=1)
	source_code = re.sub('def print_prerequisites\\(\\):\n\tpass\n', print_prerequisites_code, source_code, count=1)
	source_code = re.sub(r'PLUGIN_NAME=""', f'PLUGIN_NAME="{plugin_name}"', source_code, count=1)
	
	# Open the source file in write mode
	with open(generated_installer_name, "w") as f:
		# Write the updated source code to the file
		f.write(source_code)


def extract_setup_environment_code(file_path) -> str | None:
	"""
	Reads a Python file and extracts the source code of the "setup_environment" function.
	Ensures that the indentation uses tabs.
	"""
	with open(file_path, 'r') as f:
		content = f.read()

	# Use regular expressions to find the "setup_environment" function
	pattern = r"def\s+setup_environment\s*\([^)]*\)\s*:\s*(.*?)(?=\ndef|$)"
	match = re.search(pattern, content, re.DOTALL)

	if match:
		# Extract the function code
		function_code = match.group(1)

		# Replace spaces with tabs for consistent indentation
		function_code_with_tabs = function_code.replace('    ', '\t')
		function_code_with_tabs = f'def setup_environment():\n\t{function_code_with_tabs}'

		return function_code_with_tabs
	else:
		return None
	

def extract_check_prerequisites_code(file_path) -> str | None:
	"""
	Reads a Python file and extracts the source code of the "check_prerequisites" function.
	Ensures that the indentation uses tabs.
	"""
	with open(file_path, 'r') as f:
		content = f.read()

	# Use regular expressions to find the "check_prerequisites" function
	pattern = r"def\s+check_prerequisites\s*\([^)]*\)\s*->\s*bool\s*:\s*(.*?)(?=\ndef|$)"
	match = re.search(pattern, content, re.DOTALL)

	if match:
		# Extract the function code
		function_code = match.group(1)

		# Replace spaces with tabs for consistent indentation
		function_code_with_tabs = function_code.replace('    ', '\t')
		function_code_with_tabs = f'def check_prerequisites() -> bool:\n\t{function_code_with_tabs}'

		return function_code_with_tabs
	else:
		return None
	
def extract_print_prerequisites_code(file_path) -> str | None:
	"""
	Reads a Python file and extracts the source code of the "print_prerequisites" function.
	Ensures that the indentation uses tabs.
	"""
	with open(file_path, 'r') as f:
		content = f.read()

	# Use regular expressions to find the "print_prerequisites" function
	pattern = r"def\s+print_prerequisites\s*\([^)]*\)\s*:\s*(.*?)(?=\ndef|$)"
	match = re.search(pattern, content, re.DOTALL)

	if match:
		# Extract the function code
		function_code = match.group(1)

		# Replace spaces with tabs for consistent indentation
		function_code_with_tabs = function_code.replace('    ', '\t')
		function_code_with_tabs = f'def print_prerequisites():\n\t{function_code_with_tabs}'

		return function_code_with_tabs
	else:
		return None

def main():

	# make sure there's 2 argument: 1. specifies the plugin directory 2. the name of the plugin (output directory)
	
	# make sure there's 2 arguments
	if len(sys.argv) != 3:
		print('Usage: python build_plugin_installer.py <plugin_dev_dir> <plugin_name>')
		sys.exit(1)

	plugin_dev_dir = sys.argv[1]
	plugin_name = sys.argv[2]

	metaffi_home = os.getenv('METAFFI_HOME')
	assert metaffi_home is not None, 'METAFFI_HOME is not set'

	if not os.path.isabs(plugin_dev_dir):
		print('Set plugin_dev_dir to an absolute path')
		sys.exit(2)

	# make sure the plugin has a build_plugin_installer_helper.py file
	if not os.path.isfile(f'{plugin_dev_dir}/build_plugin_installer_helper.py'):
		print(f'Error: {plugin_dev_dir}/build_plugin_installer_helper.py not found')
		sys.exit(1)

	# load the build_plugin_installer_helper.py file and call the "get_files()" function that
	# returns a list of files or directories to be installed in the plugin directory
	sys.path.append(plugin_dev_dir)
	import build_plugin_installer_helper

	is_post_copy_files = True

	# make sure the script has a get_files() function and a setup_environment() function
	if not hasattr(build_plugin_installer_helper, 'get_files') or not callable(build_plugin_installer_helper.get_files):
		print('Error: get_files() function not found in build_plugin_installer_helper.py')
		sys.exit(1)

	if not hasattr(build_plugin_installer_helper, 'setup_environment') or not callable(build_plugin_installer_helper.setup_environment):
		print('Error: setup_environment() function not found in build_plugin_installer_helper.py')
		sys.exit(1)

	if not hasattr(build_plugin_installer_helper, 'check_prerequisites') or not callable(build_plugin_installer_helper.check_prerequisites):
		print('Error: check_prerequisites() function not found in build_plugin_installer_helper.py')
		sys.exit(1)

	if not hasattr(build_plugin_installer_helper, 'print_prerequisites') or not callable(build_plugin_installer_helper.print_prerequisites):
		print('Error: print_prerequisites() function not found in build_plugin_installer_helper.py')
		sys.exit(1)

	if not hasattr(build_plugin_installer_helper, 'post_copy_files') or not callable(build_plugin_installer_helper.post_copy_files):
		is_post_copy_files = False

	print('Building installer for plugin: ', plugin_name)

	SCONS_OUTPUT_WIN_METAFFI_HOME = os.getenv('SCONS_OUTPUT_WIN_METAFFI_HOME')
	assert SCONS_OUTPUT_WIN_METAFFI_HOME is not None, 'SCONS_OUTPUT_WIN_METAFFI_HOME is not set'
	assert SCONS_OUTPUT_WIN_METAFFI_HOME != '', 'SCONS_OUTPUT_WIN_METAFFI_HOME is empty'

	SCONS_OUTPUT_UBUNTU_METAFFI_HOME = os.getenv('SCONS_OUTPUT_UBUNTU_METAFFI_HOME')
	assert SCONS_OUTPUT_UBUNTU_METAFFI_HOME is not None, 'SCONS_OUTPUT_UBUNTU_METAFFI_HOME is not set'
	assert SCONS_OUTPUT_UBUNTU_METAFFI_HOME != '', 'SCONS_OUTPUT_UBUNTU_METAFFI_HOME is empty'

	windows_files, ubuntu_files = build_plugin_installer_helper.get_files(SCONS_OUTPUT_WIN_METAFFI_HOME, SCONS_OUTPUT_UBUNTU_METAFFI_HOME)

	if is_post_copy_files:
		build_plugin_installer_helper.post_copy_files()

	# make sure that "uninstall_plugin.py" file exists in windows_files and ubuntu_files
	# it could be the suffix of a string in windows_files or ubuntu_files, doesn't have to be a match
	assert any('uninstall_plugin.py' in file for file in windows_files), f'uninstall_plugin.py not found in returned Windows plugin files: {windows_files}'
	assert any('uninstall_plugin.py' in file for file in ubuntu_files), f'uninstall_plugin.py not found in Ubuntu plugin files: {ubuntu_files}'

	windows_zipped_files = zip_installer_files(windows_files, plugin_dev_dir)
	ubuntu_zipped_files = zip_installer_files(ubuntu_files, plugin_dev_dir)

	# extract the setup_environment function from the build_plugin_installer_helper.py file
	setup_environment_code = extract_setup_environment_code(f'{plugin_dev_dir}/build_plugin_installer_helper.py')
	if setup_environment_code is None:
		print('Error: Failed to extract setup_environment()')
		sys.exit(1)

	# extract the check_prerequisites function from the build_plugin_installer_helper.py file
	check_prerequisites_code = extract_check_prerequisites_code(f'{plugin_dev_dir}/build_plugin_installer_helper.py')
	if check_prerequisites_code is None:
		print('Error: Failed to extract check_prerequisites()')
		sys.exit(1)

	# extract the print_prerequisites function from the build_plugin_installer_helper.py file
	print_prerequisites_code = extract_print_prerequisites_code(f'{plugin_dev_dir}/build_plugin_installer_helper.py')
	if print_prerequisites_code is None:
		print('Error: Failed to extract print_prerequisites()')
		sys.exit(1)
	
	create_plugin_installer_file(f'metaffi_plugin_{plugin_name}_installer.py', plugin_name, windows_zipped_files, ubuntu_zipped_files, setup_environment_code, check_prerequisites_code, print_prerequisites_code)
	
	
if __name__ == '__main__':
	main()
