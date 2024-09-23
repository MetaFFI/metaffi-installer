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


def get_windows_metaffi_files():
	files = []
	
	# metaffi
	system32 = os.environ['SystemRoot']+'/system32/'
	files.extend(['xllr.dll', 'metaffi.exe', (f'{system32}msvcp140.dll', 'msvcp140.dll'), (f'{system32}vcruntime140_1d.dll', 'vcruntime140_1d.dll'), (f'{system32}vcruntime140d.dll', 'vcruntime140d.dll'), 'boost_filesystem.dll', 'boost_program_options.dll', (f'{system32}msvcp140d.dll', 'msvcp140d.dll'), (f'{system32}ucrtbased.dll', 'ucrtbased.dll')])
	
	metaffi_home = os.getenv('SCONS_OUTPUT_WIN_METAFFI_HOME')
	assert metaffi_home is not None, 'SCONS_OUTPUT_WIN_METAFFI_HOME is not set'
	metaffi_home = './../' + metaffi_home.replace('\\', '/')
	assert os.path.isdir(metaffi_home), f'SCONS_OUTPUT_WIN_METAFFI_HOME is not a directory. metaffi_home={metaffi_home}. current dir={os.getcwd()}'

	# include files
	includes = glob.glob(f'{metaffi_home}/include/*')
	includes = ['include/' + os.path.basename(incfile) for incfile in includes]
	files.extend(includes)
	
	return files


def get_ubuntu_metaffi_files():
	files = []

	metaffi_home = os.getenv('SCONS_OUTPUT_UBUNTU_METAFFI_HOME')
	assert metaffi_home is not None, 'SCONS_OUTPUT_UBUNTU_METAFFI_HOME is not set'
	metaffi_home = './../' + metaffi_home.replace('\\', '/')
	assert os.path.isdir(metaffi_home), f'SCONS_OUTPUT_UBUNTU_METAFFI_HOME is not a directory. metaffi_home={metaffi_home}. current dir={os.getcwd()}'
	
	# metaffi
	files.extend(['xllr.so', 'metaffi', 'libboost_filesystem.so.1.85.0', 'libboost_program_options.so.1.85.0', 'libboost_stacktrace_from_exception.so.1.85.0', 'libboost_thread.so.1.85.0'])
	
	# include files
	includes = glob.glob(f'{metaffi_home}/include/*')
	includes = ['include/' + os.path.basename(incfile) for incfile in includes]
	files.extend(includes)
	
	return files


def main():

	windows_files = get_windows_metaffi_files()
	ubuntu_files = get_ubuntu_metaffi_files()
	
	windows_zip = zip_installer_files(windows_files, f'./../output/windows/x64/debug/')
	ubuntu_zip = zip_installer_files(ubuntu_files, './../output/ubuntu/x64/debug/')
	
	shutil.copy('metaffi_installer_template.py', 'metaffi_installer.py')
	
	create_installer_file('metaffi_installer.py', windows_zip, ubuntu_zip, METAFFI_VERSION)
		
	print('Done')


if __name__ == '__main__':
	main()
