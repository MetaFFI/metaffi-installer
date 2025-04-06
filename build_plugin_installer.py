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
	- check_prerequisites()->bool - Called during install - checks if the prerequisites are met.
	- print_prerequisites() - Called during install - prints the prerequisites.
	- setup_environment() - Called during install - sets up the environment for the plugin.
 													Executed after the files are installed.
	
 
	- get_files(win_metaffi_home, ubuntu_metaffi_home)->Tuple[Dict[str, str], Dict[str, str]]
							Called during installer build - returns a dict of files to be installed for windows and ubuntu.
							First in tuple is for windows, second is for ubuntu.
							Dict keys are the target file names using relative path to the installed plugin directory.
							Dict values are full paths to the files during build.
	- (optional) post_copy_files() - Called during installer build
 									 Called after copying the files returned by get_files() and packaging them
 	- get_version() - Called during installer build - returns the version of the plugin.
	

2. uninstall_plugin.py:
	- Script MUST have a main
 	- Executed to uninstall the plugin, or called by the MetaFFI uninstaller.
  	- The plugin directory will be removed by MetaFFI uninstaller.
 	
  	- Use the script for any cleanup excluding deleteing the plugin directory.	
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
	
	# Use lambda functions for replacements to handle backslashes correctly
	source_code = re.sub(r'def\s+setup_environment\s*\(\s*\)\s*:\s*\n\s*pass\s*\n', lambda m: setup_environment_code, source_code, count=1)
	source_code = re.sub(r'def\s+check_prerequisites\s*\(\s*\)\s*->\s*bool\s*:\s*\n\s*pass\s*\n', lambda m: check_prerequisites_code, source_code, count=1)
	source_code = re.sub(r'def\s+print_prerequisites\s*\(\s*\)\s*:\s*\n\s*pass\s*\n', lambda m: print_prerequisites_code, source_code, count=1)
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


def create_windows_exe(input_file_py, plugin_name, output_exec_name=None):
	print("Creating Windows executable...")
	subprocess.run(['pip', 'install', 'pyinstaller'], check=True)

	
	if output_exec_name is None:
		output_exec_name = f'metaffi-plugin-installer-{METAFFI_VERSION}-{plugin_name}.exe'

	if '.exe' not in output_exec_name.lower():
		output_exec_name = f'{output_exec_name}.exe'
 
	# Create the exe in the installers_output directory with console window
	subprocess.run(['pyinstaller', '--onefile', '--console', '--name', output_exec_name, 
				   '--distpath', './installers_output',
				   input_file_py], check=True)
	
	# Cleanup PyInstaller artifacts
	if os.path.exists('build'):
		shutil.rmtree('build', ignore_errors=True)
  
	print(f'Created Windows executable: {os.path.abspath(f"./installers_output/{output_exec_name}")}"')
	assert os.path.exists(f'{os.path.abspath(f"./installers_output/{output_exec_name}")}'), f'{os.path.abspath(f"./installers_output/{output_exec_name}")} not found.'
  
  
def create_linux_executable(input_file_py, plugin_name, output_exec_name=None):
	print("Creating Linux executable...")
 
	if output_exec_name is None:
		output_exec_name = f'metaffi-plugin-installer-{METAFFI_VERSION}-{plugin_name}'
 
 
	if platform.system() == 'Windows':
		# if input_file_py is a full path:
  		# make sure the drive letter (and only drive letter)is lowercase, everything else remains the same
		# remove drive letter colon :
  		# add "/mnt"
		# replace "\" with "/"	
		if os.path.isabs(input_file_py):
			input_file_py = input_file_py[0].lower() + input_file_py[1:]
			input_file_py = input_file_py.replace(':', '').replace('\\', '/')
			input_file_py = '/mnt/' + input_file_py
 
	# Use WSL to run PyInstaller with all required imports
	wsl_command = """
	# Install PyInstaller and required packages
	python3 -m pip install pyinstaller pycrosskit python-dotenv

	# Create the executable with all required imports
	pyinstaller --onefile --console --hidden-import pycrosskit --hidden-import pycrosskit.envariables --hidden-import python-dotenv --hidden-import dotenv --name {} --distpath ./installers_output {}
	""".format(output_exec_name, input_file_py)
	
	if platform.system() == 'Windows':
		subprocess.run(['wsl', '-e', 'bash', '-c', wsl_command], check=True)
	else:
		# Run the command directly with shell=True, just like in build_installer.py
		subprocess.run(wsl_command, shell=True, check=True)
  
	# Cleanup PyInstaller artifacts
	if os.path.exists('build'):
		shutil.rmtree('build', ignore_errors=True)
  
	print(f'Created Ubuntu executable: {os.path.abspath(f"./installers_output/{output_exec_name}")}"')
	assert os.path.exists(f'{os.path.abspath(f"./installers_output/{output_exec_name}")}'), f'{os.path.abspath(f"./installers_output/{output_exec_name}")} not found in ./installers_output'


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

	if not hasattr(build_plugin_installer_helper, 'get_version') or not callable(build_plugin_installer_helper.get_version):
		print('Error: get_version() function not found in build_plugin_installer_helper.py')
		sys.exit(1)

	if not hasattr(build_plugin_installer_helper, 'post_copy_files') or not callable(build_plugin_installer_helper.post_copy_files):
		is_post_copy_files = False

	print('Building installer for plugin: ', plugin_name)

	METAFFI_WIN_HOME = os.getenv('METAFFI_WIN_HOME')
	assert METAFFI_WIN_HOME is not None, 'METAFFI_WIN_HOME is not set'
	assert METAFFI_WIN_HOME != '', 'METAFFI_WIN_HOME is empty'

	METAFFI_UBUNTU_HOME = os.getenv('METAFFI_UBUNTU_HOME')
	assert METAFFI_UBUNTU_HOME is not None, 'METAFFI_UBUNTU_HOME is not set'
	assert METAFFI_UBUNTU_HOME != '', 'METAFFI_UBUNTU_HOME is empty'

	windows_files, ubuntu_files = build_plugin_installer_helper.get_files(METAFFI_WIN_HOME, METAFFI_UBUNTU_HOME)

	version = build_plugin_installer_helper.get_version()

	if is_post_copy_files:
		build_plugin_installer_helper.post_copy_files()

	# make sure that "uninstall_plugin.py" file exists in windows_files and ubuntu_files
	# it could be the suffix of a string in windows_files or ubuntu_files, doesn't have to be a match
	assert any('uninstall_plugin.py' in file for file in windows_files), f'uninstall_plugin.py not found in returned Windows plugin files: {windows_files}'
	assert any('uninstall_plugin.py' in file for file in ubuntu_files), f'uninstall_plugin.py not found in returned Ubuntu plugin files: {ubuntu_files}'

	# make uninstall_plugin.py an executable for windows and ubuntu using pyinstaller
	create_windows_exe(f'{plugin_dev_dir}/uninstall_plugin.py', plugin_name, 'uninstall_plugin.exe')
	create_linux_executable(f'{plugin_dev_dir}/uninstall_plugin.py', plugin_name, 'uninstall_plugin')
 
	# make sure uninstall_plugin.exe and uninstall_plugin exist in ./installers_output
	assert os.path.exists('./installers_output/uninstall_plugin.exe'), 'uninstall_plugin.exe not found in ./installers_output'
	assert os.path.exists('./installers_output/uninstall_plugin'), 'uninstall_plugin not found in ./installers_output'
 
	# copy from installers_output to plugin_dev_dir
	shutil.move(f'./installers_output/uninstall_plugin.exe', f'{plugin_dev_dir}/uninstall_plugin.exe')
	shutil.move(f'./installers_output/uninstall_plugin', f'{plugin_dev_dir}/uninstall_plugin')
 
	# replace the uninstall_plugin.py file with the executable as full path
	# replace the uninstall_plugin.py file with the executable as
	del windows_files['uninstall_plugin.py']
	windows_files['uninstall_plugin.exe'] = f'{plugin_dev_dir}/uninstall_plugin.exe'

	del ubuntu_files['uninstall_plugin.py']
	ubuntu_files['uninstall_plugin'] = f'{plugin_dev_dir}/uninstall_plugin'

	windows_zipped_files = zip_installer_files(windows_files, plugin_dev_dir)
	ubuntu_zipped_files = zip_installer_files(ubuntu_files, plugin_dev_dir)
 
	# remove the executables from the plugin_dev_dir after zipping
	os.remove(f'{plugin_dev_dir}/uninstall_plugin.exe')
	os.remove(f'{plugin_dev_dir}/uninstall_plugin')

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
	
	create_plugin_installer_file(f'./installers_output/metaffi_plugin_{plugin_name}_{version}_installer.py', plugin_name, windows_zipped_files, ubuntu_zipped_files, setup_environment_code, check_prerequisites_code, print_prerequisites_code)
	
	# use pyinstaller to create the windows and ubuntu installers
	# place it in the installers_output directory
	# (call relevant functions to do that)
	create_windows_exe(f'./installers_output/metaffi_plugin_{plugin_name}_{version}_installer.py', plugin_name)
	create_linux_executable(f'./installers_output/metaffi_plugin_{plugin_name}_{version}_installer.py', plugin_name)
	
	# remove the metaffi_plugin_{plugin_name}_{version}_installer.py file
	os.remove(f'./installers_output/metaffi_plugin_{plugin_name}_{version}_installer.py')
	
	# cleanup *.spec files in the current directory
	for file in os.listdir('.'):
		if file.endswith('.spec'):
			os.remove(file)
 
	print('Done')
	
 
	
if __name__ == '__main__':
	
	# make sure the installers_output directory exists
	if not os.path.exists('./installers_output'):
		os.makedirs('./installers_output')
		
	# set the current directory to this script's directory
	os.chdir(os.path.dirname(os.path.abspath(__file__)))
 
	main()
