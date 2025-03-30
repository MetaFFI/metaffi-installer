import glob
import os
import zipfile
import io
import base64
import shutil
import re
from typing import List
import platform
import subprocess
from version import METAFFI_VERSION
from pycrosskit.envariables import SysEnv

metaffi_ubuntu_home = os.getenv('METAFFI_UBUNTU_HOME')
assert metaffi_ubuntu_home is not None, 'METAFFI_UBUNTU_HOME is not set'
assert os.path.isdir(metaffi_ubuntu_home), f'METAFFI_UBUNTU_HOME is not a directory. metaffi_ubuntu_home={metaffi_ubuntu_home}. current dir={os.getcwd()}'
metaffi_ubuntu_home += '/'

metaffi_win_home = os.getenv('METAFFI_WIN_HOME')
assert metaffi_win_home is not None, 'METAFFI_WIN_HOME is not set'
assert os.path.isdir(metaffi_win_home), f'METAFFI_WIN_HOME is not a directory. metaffi_home={metaffi_win_home}. current dir={os.getcwd()}'
metaffi_win_home += '/'


def zip_installer_files(files: List[str], root: str):
	# Create a file-like object in memory
	buffer = io.BytesIO()
	
	# Create a zip file object and write the files to it
	# Use the highest compression level
	with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
		for file in files:
			the_root = root
			arcname = file
			is_specifies_arcname = False
			if isinstance(file, tuple):
				is_specifies_arcname = True
				arcname = file[1]
				file = file[0]
			
			# Read the file from the filename using the parameters and value "root+file"
			# Write the file into the zip with the filename written in "file" value
			if is_specifies_arcname:  # don't use root, as files are not in the METAFFI_HOME dir
				zf.write(file, arcname=arcname)
			else:
				if os.path.isabs(file):
					zf.write(file, arcname=arcname)
				else:
					zf.write(the_root + file, arcname=arcname)
	
	# Get the byte array from the buffer
	return buffer.getvalue()


def create_installer_file(python_source_filename, windows_zip, ubuntu_zip, version):
	# Encode the binary data to base64 strings
	windows_zip_str = base64.b64encode(windows_zip)
	ubuntu_zip_str = base64.b64encode(ubuntu_zip)
	
	# Open the source file in read mode
	with open('metaffi_installer_template.py', "r") as f:
		# Read the source code as a string
		source_code = f.read()
	
	# Find and replace the variables with the encoded strings
	source_code = re.sub(r"windows_x64_zip\s*=\s*.+", f"windows_x64_zip = {windows_zip_str}", source_code, count=1)
	source_code = re.sub(r"ubuntu_x64_zip\s*=\s*.+", f"ubuntu_x64_zip = {ubuntu_zip_str}", source_code, count=1)
	source_code = re.sub(r"METAFFI_VERSION\s*=\s*.+", f"METAFFI_VERSION = '{version}'", source_code, count=1)
	
	# Open the source file in write mode
	with open(python_source_filename, "w") as f:
		# Write the updated source code to the file
		f.write(source_code)


def create_uninstaller_exe():
	print("Creating Windows uninstaller executable...")
	subprocess.run(['pip', 'install', 'pyinstaller'], check=True)
	
	# Create temp directory for build
	temp_dir = os.path.join(os.getcwd(), 'temp_build')
	os.makedirs(temp_dir, exist_ok=True)
	
	try:
		# Copy template to temp directory
		shutil.copy('uninstall_template.py', os.path.join(temp_dir, 'uninstaller.py'))
		
		# Create the exe in temp directory
		subprocess.run(['pyinstaller', '--onefile', '--console', '--name', 'uninstall',
					   '--distpath', temp_dir,
					   os.path.join(temp_dir, 'uninstaller.py')], check=True)
		
		# Copy the generated exe to installers_output
		shutil.copy2(os.path.join(temp_dir, 'uninstall.exe'),
					'./installers_output/uninstall.exe')
		
	finally:
		# Cleanup
		if os.path.exists('build'):
			shutil.rmtree('build')
		for spec_file in glob.glob('uninstall.spec'):
			os.remove(spec_file)
		shutil.rmtree(temp_dir)


def create_uninstaller_elf():
	print("Creating Linux uninstaller executable...")
	
	# Create temp directory for build
	temp_dir = os.path.join(os.getcwd(), 'temp_build')
	os.makedirs(temp_dir, exist_ok=True)
	
	try:
		# Copy template to temp directory
		shutil.copy('uninstall_template.py', os.path.join(temp_dir, 'uninstaller.py'))
		
		# Convert Windows paths to WSL paths, handling both uppercase and lowercase drive letters
		def to_wsl_path(path):
			path = path.replace('\\', '/')
			# Handle both uppercase and lowercase drive letters
			if path.startswith('C:'):
				path = '/mnt/c' + path[2:]
			elif path.startswith('c:'):
				path = '/mnt/c' + path[2:]
			return path
		
		wsl_temp_dir = to_wsl_path(temp_dir)
		wsl_output_dir = to_wsl_path(os.path.join(os.getcwd(), 'installers_output'))
		
		# Use WSL to run PyInstaller
		wsl_command = f"""
		cd "{wsl_temp_dir}"
		python3 -m pip install pyinstaller
		pyinstaller --onefile --console \
			--name uninstall \
			--distpath "{wsl_temp_dir}" \
			uninstaller.py
		cp "{wsl_temp_dir}/uninstall" "{wsl_output_dir}/"
		"""
		
		subprocess.run(['wsl', '-e', 'bash', '-c', wsl_command], check=True)
		
	finally:
		# Cleanup
		shutil.rmtree(temp_dir)
		if os.path.exists('build'):
			shutil.rmtree('build')
		for spec_file in glob.glob('uninstall.spec'):
			os.remove(spec_file)


def get_windows_metaffi_files():
	files = []
	
	# metaffi
	system32 = os.environ['SystemRoot']+'/system32/'
	files.extend(['xllr.dll', 'metaffi.exe', 'uninstall.exe',  # Added uninstall.exe
				 (f'{system32}msvcp140.dll', 'msvcp140.dll'),
				 (f'{system32}vcruntime140_1d.dll', 'vcruntime140_1d.dll'),
				 (f'{system32}vcruntime140d.dll', 'vcruntime140d.dll'),
				 'boost_filesystem*.dll', 'boost_program_options*.dll',
				 (f'{system32}msvcp140d.dll', 'msvcp140d.dll'),
				 (f'{system32}ucrtbased.dll', 'ucrtbased.dll')])
	
	# include files
	includes = glob.glob(f'{metaffi_win_home}/include/*')
	includes = ['include/' + os.path.basename(incfile) for incfile in includes]
	files.extend(includes)
	
	# Expand any glob patterns in file list
	expanded_files = []
	for file_entry in files:
		if isinstance(file_entry, str) and '*' in file_entry:
			matches = glob.glob(os.path.join(metaffi_win_home, file_entry))
			if not matches:
				raise Exception(f"No files found matching pattern: {file_entry}")
			expanded_files.extend(os.path.relpath(match, metaffi_win_home) for match in matches)
		else:
			expanded_files.append(file_entry)
	
	return expanded_files


def get_ubuntu_metaffi_files():
	files = []
	
	# metaffi
	files.extend(['xllr.so', 'metaffi', 'uninstall',  # Added uninstall
				 'libboost_filesystem.so.*',
				 'libboost_program_options.so.*',
				 'libboost_thread.so.*'])
	
	# include files
	includes = glob.glob(f'{metaffi_ubuntu_home}/include/*')
	includes = ['include/' + os.path.basename(incfile) for incfile in includes]
	files.extend(includes)
	
	# Expand any glob patterns in file list
	expanded_files = []
	for file_entry in files:
		if isinstance(file_entry, str) and '*' in file_entry:
			matches = glob.glob(os.path.join(metaffi_ubuntu_home, file_entry))
			if not matches:
				raise Exception(f"No files found matching pattern: {file_entry}")
			expanded_files.extend(os.path.relpath(match, metaffi_ubuntu_home) for match in matches)
		else:
			expanded_files.append(file_entry)
	
	return expanded_files


def create_windows_exe():
	print("Creating Windows executable...")
	subprocess.run(['pip', 'install', 'pyinstaller'], check=True)
	
	# Create the exe in the installers_output directory with console window
	subprocess.run(['pyinstaller', '--onefile', '--console', '--name', f'metaffi-installer-{METAFFI_VERSION}', 
				   '--distpath', './installers_output',
				   './installers_output/metaffi_installer.py'], check=True)
	
	# Cleanup PyInstaller artifacts
	if os.path.exists('build'):
		shutil.rmtree('build')
	# Cleanup spec files
	for spec_file in glob.glob('metaffi-installer-*.spec'):
		os.remove(spec_file)


def create_linux_executable():
	print("Creating Linux executable...")
	
	# Use WSL to run PyInstaller with all required imports
	wsl_command = """
	# Install PyInstaller and required packages
	python3 -m pip install pyinstaller pycrosskit python-dotenv

	# Create the executable with all required imports
	pyinstaller --onefile --console \
		--hidden-import pycrosskit \
		--hidden-import pycrosskit.envariables \
		--hidden-import python-dotenv \
		--hidden-import dotenv \
		--name metaffi-installer-{} \
		--distpath ./installers_output \
		./installers_output/metaffi_installer.py
	""".format(METAFFI_VERSION)
	
	if platform.system() == 'Windows':
		subprocess.run(['wsl', '-e', 'bash', '-c', wsl_command], check=True)
	else:
		subprocess.run(wsl_command, check=True)


def create_linux_deb():
	print("Creating Linux DEB...")
	
	# Create necessary directories
	os.makedirs('./installers_output/DEBIAN', exist_ok=True)
	os.makedirs('./installers_output/usr/local/bin', exist_ok=True)

	# Create control file
	control_content = """Package: metaffi
Version: {}
Architecture: amd64
Maintainer: MetaFFI
Description: MetaFFI - Multi-Lingual Interoperability System
""".format(METAFFI_VERSION)

	# Create postinst script that runs our executable and sets environment
	postinst_content = """#!/bin/bash
set -e

# Use . instead of source for better shell compatibility
. ~/.profile

echo "Running MetaFFI installer..."
/usr/local/bin/metaffi-installer -s || {
    echo "ERROR: MetaFFI installation failed"
    exit 1
}

echo "MetaFFI installation completed successfully"
exit 0
"""

	# Create prerm script that runs uninstaller before package removal
	prerm_content = """#!/bin/sh
set -e

# Run uninstaller if it exists
if [ -z "$METAFFI_HOME" ]; then
    echo "WARNING: METAFFI_HOME environment variable not set, cannot run uninstaller"
elif [ ! -f "$METAFFI_HOME/uninstall" ]; then
    echo "WARNING: MetaFFI uninstaller not found at $METAFFI_HOME/uninstall"
else
    echo "Running MetaFFI uninstaller..."
    "$METAFFI_HOME/uninstall" || {
        echo "WARNING: MetaFFI uninstaller failed with exit code $?"
    }
fi

exit 0
"""

	# Write the files
	with open('./installers_output/DEBIAN/control', 'w', newline='\n') as f:
		f.write(control_content)
	
	with open('./installers_output/DEBIAN/postinst', 'w', newline='\n') as f:
		f.write(postinst_content)
		
	with open('./installers_output/DEBIAN/prerm', 'w', newline='\n') as f:
		f.write(prerm_content)

	# Copy the PyInstaller-generated executable
	shutil.copy2(f'./installers_output/metaffi-installer-{METAFFI_VERSION}',
				'./installers_output/usr/local/bin/metaffi-installer')

	# Set permissions
	os.chmod('./installers_output/usr/local/bin/metaffi-installer', 0o755)
	os.chmod('./installers_output/DEBIAN/postinst', 0o755)
	os.chmod('./installers_output/DEBIAN/prerm', 0o755)  # Make prerm executable
	os.chmod('./installers_output/DEBIAN/control', 0o644)

	# Build in WSL temp directory
	wsl_command = """
	TEMP_DIR=$(mktemp -d)
	
	# Create DEBIAN directory
	mkdir -p "$TEMP_DIR/DEBIAN"
	cp installers_output/DEBIAN/control "$TEMP_DIR/DEBIAN/"
	cp installers_output/DEBIAN/postinst "$TEMP_DIR/DEBIAN/"
	cp installers_output/DEBIAN/prerm "$TEMP_DIR/DEBIAN/"
	
	# Create usr/local/bin directory
	mkdir -p "$TEMP_DIR/usr/local/bin"
	cp installers_output/usr/local/bin/metaffi-installer "$TEMP_DIR/usr/local/bin/"
	
	# Build the DEB
	dpkg-deb --build "$TEMP_DIR" installers_output/metaffi_{}_amd64.deb
	rm -rf "$TEMP_DIR"
	""".format(METAFFI_VERSION)
	
	if platform.system() == 'Windows':
		subprocess.run(['wsl', '-e', 'bash', '-c', wsl_command], check=True)
	else:
		subprocess.run(wsl_command, check=True)

	# Cleanup DEBIAN and usr directories
	debian_dir = './installers_output/DEBIAN'
	usr_dir = './installers_output/usr'
	
	if os.path.exists(debian_dir):
		shutil.rmtree(debian_dir)
	if os.path.exists(usr_dir):
		shutil.rmtree(usr_dir)


def main():
	# Create uninstallers first
	create_uninstaller_exe()
	create_uninstaller_elf()
	
	# Copy uninstallers to their respective METAFFI_HOME directories
	print("Copying uninstallers to METAFFI_HOME directories...")
	shutil.copy2('./installers_output/uninstall.exe', metaffi_win_home)
	shutil.copy2('./installers_output/uninstall', metaffi_ubuntu_home)
	
	windows_files = get_windows_metaffi_files()
	ubuntu_files = get_ubuntu_metaffi_files()

	windows_zip = zip_installer_files(windows_files, metaffi_win_home)
	ubuntu_zip = zip_installer_files(ubuntu_files, metaffi_ubuntu_home)
	
	os.makedirs('./installers_output', exist_ok=True)
	shutil.copy('metaffi_installer_template.py', './installers_output/metaffi_installer.py')
	
	create_installer_file('./installers_output/metaffi_installer.py', windows_zip, ubuntu_zip, METAFFI_VERSION)
	
	# Create both packages regardless of platform
	create_windows_exe()
	create_linux_executable()
	create_linux_deb()
	
	print('Done')


if __name__ == '__main__':

	# Change to the directory containing this script
	script_dir = os.path.dirname(os.path.abspath(__file__))
	os.chdir(script_dir)

	main()
