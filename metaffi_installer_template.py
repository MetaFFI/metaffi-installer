import base64
import io
import platform
import re
import shlex
import shutil
import sys
import ctypes
import os
import traceback
import typing
import zipfile
import subprocess
import importlib
import sys

def ensure_package(package_name, pip_package_name=None):
	try:
		importlib.import_module(package_name)
	except ImportError:
		import subprocess
		import sys
		print(f"Installing {package_name}...")
		
		if pip_package_name is None:
			pip_package_name = package_name
			
		subprocess.check_call([sys.executable, "-m", "pip", "install", pip_package_name])
		
		print(f"{package_name} installed successfully!")


# Example: Check and install colorama
ensure_package("pycrosskit")
from pycrosskit.envariables import SysEnv

windows_x64_zip = 'windows_x64_zip_data'
ubuntu_x64_zip = 'ubuntu_x64_zip_data'
METAFFI_VERSION = '0.0.0'

is_silent = False

run_api_tests_script = """
import os
import sys
import subprocess
import glob

# iterate over all the directories in $METAFFI_HOME (the plugins) but "include" directory
# for each directory, check if the directory contains a "plugin_api_tests" directory
# if it doesn't, print a warning message and continue to the next directory
# if it does, run "run_api_tests.py" in the "plugin_api_tests" directory
# if the script fails, print an error message and exit with a non-zero exit code
metaffi_home = os.environ['METAFFI_HOME']
if metaffi_home is None:
	print('METAFFI_HOME is not set')
	sys.exit(1)

metaffi_home = os.path.abspath(metaffi_home)

# iterate over all the directories in $METAFFI_HOME (the plugins) but "include" directory
for plugindir in os.listdir(metaffi_home):
	if plugindir == 'include':
		continue
		
	if not os.path.isdir(f'{metaffi_home}/{plugindir}'): # skip files
		continue
	
	# find run_api_tests.py in plugin directory using glob
	run_api_tests_script_path = glob.glob(f"{metaffi_home}/{plugindir}/**/run_api_tests.py", recursive=True)
	if len(run_api_tests_script_path) == 0:
		print(f'Warning: {plugindir} does not have API tests (run_api_tests.py) - skipping...')
		continue

	if len(run_api_tests_script_path) > 1:
		print(f'Error: {plugindir} has more than one run_api_tests.py script - skipping...')
		continue
		
	run_api_tests_script_path = run_api_tests_script_path[0]
		
	# run "run_api_tests.py" in the "plugin_api_tests" directory using "subprocess"
	# make sure the STDOUT and STDERR are written to the console and the current directory
	# of the process is the "plugin_api_tests" directory
	print(f'Running API tests for {plugindir} ({run_api_tests_script_path})')
	
	try:
		# get run_api_tests_script_path directory
		plugin_tests_dir = os.path.dirname(run_api_tests_script_path)	
	
		subprocess.run([sys.executable, run_api_tests_script_path], cwd=plugin_tests_dir, check=True)
	except subprocess.CalledProcessError as e:
		print(f'Error: {run_api_tests_script_path} failed with exit code {e.returncode}')
		sys.exit(e.returncode)

print('All tests passed')
"""

# ====================================

def ask_user(input_text: str, default: str, valid_answers: list | None) -> str:
	global is_silent
	
	if is_silent:
		if default is None or default == '':
			raise Exception(f"internal error - missing default value in silent mode.\n{input_text}\n{valid_answers}")
		return default
	
	done = False
	
	msg = input_text
	if valid_answers is not None:
		msg += ' [' + '/'.join(valid_answers) + '] '
	if default is not None and default != '':
		msg += f'(default: {default}) '
	msg += ' - '
	
	answer = None
	
	while not done:
		answer = input(msg)
		answer = answer.strip()
		
		if answer == '' and default is not None and default != '':
			answer = default
		
		if valid_answers is not None:
			if answer.lower() not in [s.lower() for s in valid_answers]:
				print('Not a valid input.')
				continue
		
		done = True
	
	assert answer is not None
	return answer


def is_windows():
	return platform.system() == 'Windows'


def is_ubuntu():
	if platform.system() != 'Linux':
		return False
	
	import distro # type: ignore - applies only to linux
	return distro.name() == 'Ubuntu'


def is_path_string_valid(maybepath: str) -> bool:
	try:
		os.path.abspath(maybepath)
		return True
	except:
		return False


def get_install_dir(default_dir: str):
	install_dir = None
	
	# If METAFFI_HOME environment variable is set, return its value
	if "METAFFI_HOME" in os.environ:
		install_dir = os.environ["METAFFI_HOME"]
	
	# Otherwise, ask the user for the installation directory
	else:
		done = False
		while not done:
			# Ask the user for the input
			user_input = ask_user(f"Where to install? Notice due to limitations in some languages, it is recommended not to use whitespaces.", default_dir, None)
			
			user_input = os.path.expanduser(os.path.expandvars(user_input))
			
			if ' ' in user_input:
				print('Installation directory mustn\'t contains whitespace')
				continue
			
			if not is_path_string_valid(user_input):
				print(f'Given path "{user_input}" is not valid')
				continue
			
			are_you_sure = ask_user(f'Are you sure you want to install to "{user_input}"?', 'y', ['y', 'n'])
			if are_you_sure.strip().lower() == 'n':
				continue
			
			install_dir = user_input
			done = True
	
	assert install_dir is not None
	install_dir = os.path.abspath(install_dir)
	print('installing to ' + install_dir)
	return install_dir


# Define the function
def unpack_into_directory(base64_zip_file, target_directory):
	# Decode the base64 string to a byte array
	zip_data = base64.b64decode(base64_zip_file)
	
	zip_data = io.BytesIO(zip_data)  # to clear a pycharm warning
	
	# Create a zip file object from the byte array
	# Specify the compression type and level
	zf = zipfile.ZipFile(zip_data, "r", zipfile.ZIP_DEFLATED, compresslevel=9)
	
	# Check if the target directory exists
	if not os.path.exists(target_directory):
		# Create the target directory
		os.makedirs(target_directory)
	
	# Extract all the files from the zip file object to the target directory
	zf.extractall(target_directory)


refresh_env: typing.Callable


def command(command: str, raise_if_command_fail: bool = False, is_refresh_envvars: bool = True):
	global refresh_env
	global is_silent
	
	if is_windows():
		print(f'{os.getcwd()}> {command}')
	else:
		print(f'{os.getcwd()}$ {command}')
	
	# create a process object with the command line
	if is_refresh_envvars:
		refresh_env()
	
	try:
		command_split = shlex.split(os.path.expanduser(os.path.expandvars(command)))
		
		env = os.environ.copy()
		if is_silent and not is_windows():
			env["DEBIAN_FRONTEND"] = "noninteractive"
		
		output = subprocess.run(command_split, capture_output=True, text=True, env=env)
	except subprocess.CalledProcessError as e:
		if raise_if_command_fail:
			raise Exception(f'Failed running "{command}" with exit code {e.returncode}. Output:\n{str(e.stdout)}{str(e.stderr)}')
		
		# your code to handle the exception
		return e.returncode, str(e.stdout), str(e.stderr)
	except FileNotFoundError as e:
		if raise_if_command_fail:
			raise Exception(f'Failed running {command} with {e.strerror}.\nfile: {e.filename}')
		
		return f'Failed running {command} with {e.strerror}\n{e}.\nfile: {e.filename}', '', ''
	
	all_stdout = output.stdout
	all_stderr = output.stderr
	
	# if the return code is not zero, raise an exception
	return output.returncode, str(all_stdout).strip(), str(all_stderr).strip()


def run_shell(command: str, raise_if_command_fail: bool = False):
	global refresh_env
	
	if is_windows():
		shell = 'cmd.exe'
		print(f'{os.getcwd()}> {command}')
	else:
		shell = "/bin/bash"
		print(f'{os.getcwd()}$ {command}')
	
	# create a process object with the command line
	refresh_env()
	try:
		command_split = shlex.split(os.path.expanduser(os.path.expandvars(command)))
		output = subprocess.run(command_split, executable=shell, capture_output=True, text=True, shell=True)
	except subprocess.CalledProcessError as e:
		
		if raise_if_command_fail:
			raise Exception(f'Failed running "{command}" with exit code {e.returncode}. Output:\n{str(e.stdout)}{str(e.stderr)}')
		
		# your code to handle the exception
		return e.returncode, str(e.stdout), str(e.stderr)
	except FileNotFoundError as e:
		if raise_if_command_fail:
			raise Exception(f'Failed running {command} with {e.strerror}.\nfile: {e.filename}')
		
		return 1, '', f'Failed running {command} with {e.strerror}.\nfile: {e.filename}'
	
	all_stdout = str(output.stdout).strip()
	all_stderr = str(output.stderr).strip()
	
	if raise_if_command_fail and output.returncode != 0:
		raise Exception(f'Failed running "{command}" with exit code {output.returncode}. Output:\n{all_stdout}{all_stderr}')
	
	# if the return code is not zero, raise an exception
	return output.returncode, all_stdout, all_stderr


# ========== windows ===========


def set_windows_system_environment_variable(name: str, val: str):
	import winreg
	
	# already set correctly, no need to set
	if name in os.environ and val == os.environ[name]:
		return
	
	# Open the registry key for system environment variables
	key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "System\\CurrentControlSet\\Control\\Session Manager\\Environment", 0, winreg.KEY_ALL_ACCESS)
	# Set the value of the environment variable
	# Use REG_EXPAND_SZ as the type to allow references to other variables
	winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, val)
	# Close the key
	winreg.CloseKey(key)
	# Notify the system that the environment variables have changed
	# Use HWND_BROADCAST and WM_SETTINGCHANGE messages
	ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "Environment")
	
	print(f'Setting system-wide environment variable {name} to {val}')


def set_windows_user_environment_variable(name: str, val: str):
	import winreg
	
	# open the registry key for the current user's environment variables
	key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", access=winreg.KEY_WRITE)
	
	# set the value of the environment variable in the registry
	winreg.SetValueEx(key, name, 0, winreg.REG_SZ, val)
	
	# close the registry key
	winreg.CloseKey(key)
	
	# broadcast a message to all windows that the environment has changed
	HWND_BROADCAST = 0xFFFF
	WM_SETTINGCHANGE = 0x1A
	SMTO_ABORTIFHUNG = 0x0002
	result = ctypes.c_long()
	SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW
	SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, u"Environment", SMTO_ABORTIFHUNG, 5000, ctypes.byref(result))


# Define the function
def add_to_path_environment_variable(path):
	import winreg
	
	# Open the registry key for system environment variables
	key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "System\\CurrentControlSet\\Control\\Session Manager\\Environment", 0, winreg.KEY_ALL_ACCESS)
	
	# Get the current value of the Path variable
	current_path = winreg.QueryValueEx(key, "Path")[0]
	
	# Check if the given path is already in the Path variable
	if not any(os.path.samefile(path, os.path.expanduser(os.path.expandvars(p))) for p in current_path.split(";")):
		# Append the given path to the Path variable
		new_path = current_path + ";" + path
		
		# Set the new value of the Path variable
		# Use REG_EXPAND_SZ as the type to allow references to other variables
		winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
		
		# Notify the system that the environment variables have changed
		# Use HWND_BROADCAST and WM_SETTINGCHANGE messages
		ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "Environment")
		
		print(f'Adding {path} to PATH environment variable')


def refresh_windows_env():
	import winreg
	
	# system environment variables
	key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, "System\\CurrentControlSet\\Control\\Session Manager\\Environment", access=winreg.KEY_READ)
	
	# get the number of values in the key
	num_values = winreg.QueryInfoKey(key)[1]
	
	# loop through the values
	for i in range(num_values):
		# get the name and value of the environment variable
		name, value, _ = winreg.EnumValue(key, i)
		# update the os.environ dictionary with the new value
		value = os.path.expandvars(os.path.expanduser(value))
		os.environ[name] = value
	
	# close the registry key
	winreg.CloseKey(key)
	
	# broadcast a message to all windows that the environment has changed
	HWND_BROADCAST = 0xFFFF
	WM_SETTINGCHANGE = 0x1A
	SMTO_ABORTIFHUNG = 0x0002
	result = ctypes.c_long()
	SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW
	SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, u"Environment", SMTO_ABORTIFHUNG, 5000, ctypes.byref(result))
	
	# user environment variables
	# open the registry key for the current user's environment variables
	key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", access=winreg.KEY_READ)
	
	# get the number of values in the key
	num_values = winreg.QueryInfoKey(key)[1]
	
	# loop through the values
	for i in range(num_values):
		# get the name and value of the environment variable
		name, value, _ = winreg.EnumValue(key, i)
		# update the os.environ dictionary with the new value
		value = os.path.expandvars(os.path.expanduser(value))
		if name in os.environ and name.lower() == 'path':
			os.environ[name] += ';' + value
		else:
			os.environ[name] = value
	
	# close the registry key
	winreg.CloseKey(key)
	
	# broadcast a message to all windows that the environment has changed
	HWND_BROADCAST = 0xFFFF
	WM_SETTINGCHANGE = 0x1A
	SMTO_ABORTIFHUNG = 0x0002
	result = ctypes.c_long()
	SendMessageTimeoutW = ctypes.windll.user32.SendMessageTimeoutW
	SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, u"Environment", SMTO_ABORTIFHUNG, 5000, ctypes.byref(result))


def refresh_ubuntu_env():
	from dotenv import load_dotenv
	
	load_dotenv("/etc/environment")
	load_dotenv("~/.profile")
	

if is_windows():
	refresh_env = refresh_windows_env
elif is_ubuntu():
	refresh_env = refresh_ubuntu_env


def install_windows() -> str:
	global windows_x64_zip
	
	# verify running as admin
	is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
	if not is_admin:
		raise Exception('User must have admin privileges')
	
	refresh_windows_env()  # refresh environment variables, in case the environment is not up-to-date
	
	
	print()
	print('==== Starting installation ====')
	print()
	
	# get install dir
	install_dir = get_install_dir("c:\\MetaFFI\\")
	
	# unpack zip into install dir
	unpack_into_directory(windows_x64_zip, install_dir)
	
	# setting METAFFI_HOME environment variable
	set_windows_system_environment_variable("METAFFI_HOME", install_dir)
	
	# add install_dir and install_dir\bin to PATH
	add_to_path_environment_variable(install_dir)
	
	return install_dir


# -------------------------------


def get_ubuntu_environment_variable(file: str, name: str) -> str | None:
	# Execute the command and capture the output
	err_code, stdout, stderr = run_shell(f"grep -q '{name}=' {file}")
	
	if err_code != 0:
		return None
	
	err_code, stdout, stderr = run_shell(f"grep '{name}=' {file} | cut -d '=' -f 2")
	
	# Check the return code and get the value
	if err_code != 0:
		raise Exception(f'Failed to get the value of the environment variable in {file}: {stdout}{stderr}')
	
	return stdout.strip()


def get_ubuntu_user_environment_variable(name: str) -> str | None:
	return get_ubuntu_environment_variable(name, '~/.profile')


def get_ubuntu_machine_environment_variable(name: str) -> str | None:
	return get_ubuntu_environment_variable(name, '/etc/environment')


def set_ubuntu_environment_variable(file: str, name: str, value: str):
	existing_val = get_ubuntu_environment_variable(name, file)
	
	if existing_val is not None:  # env var exists
		if existing_val == value:
			return
		
		update_value = ask_user(f'Existing {name} is {existing_val}, do you want me to update it to {value} in {file}?', 'y', ['y', 'n'])
		if update_value == 'n':
			raise Exception(f'{name} must be {value} in order to continue. Make sure {name} points to the required python and try again')
		
		print(f'Updating environment variable {name}={value} in {file}')
		
		# update value
		err_code, stdout, stderr = run_shell(f"sed -i 's/{name}={existing_val}/{name}={value}/g' {file}")
		if err_code != 0:
			raise Exception(f'Failed to update {name} environment variable in {file}: {stdout}{stderr}')
		return
	
	else:  # var doesn't exist
		print(f'Adding environment variable {name}={value} in {file}')
		err_code, stdout, stderr = run_shell(f"echo 'export {name}={value}' >> {file}")
		if err_code != 0:
			raise Exception(f"Failed to add {name} environment variable to {file}: {stdout}{stderr}")
	
	refresh_env()


def set_ubuntu_system_environment_variable(name: str, value: str):
	"""Set environment variable in /etc/environment and update current shell"""
	try:
		from dotenv import load_dotenv

		# Read existing environment variables using python-dotenv
		load_dotenv('/etc/environment')
		
		# Update the environment variable
		os.environ[name] = value
		
		# Write back to /etc/environment
		with open('/etc/environment', 'w') as f:
			for key, val in os.environ.items():
				if not key.startswith('_'):  # Skip internal variables
					f.write(f'{key}={val}\n')
		
		refresh_env()
		
	except Exception as e:
		print(f"Error setting environment variable: {e}")
		raise


def make_metaffi_available_globally(install_dir: str):
	if not os.path.exists(f'{install_dir}/metaffi'):
		# execute "ls -l {installdir}" and print the output

		err_code, stdout, stderr = run_shell(f'ls -l {install_dir}')
		if err_code != 0:
			raise Exception(f'Failed to list the contents of {install_dir}: {stdout}{stderr}')
		
		print(stdout)

		raise Exception(f'{install_dir}/metaffi is missing')
	
	res = os.system(f'chmod u+x {install_dir}/metaffi')
	if res != 0:
		raise Exception(f'Failed to make {install_dir}/metaffi executable. return value: {res}')

	# create a symbolic link to /usr/bin/metaffi
	res = os.system(f'ln -sf {install_dir}/metaffi /usr/bin/metaffi')
	if res != 0:
		raise Exception(f'Failed to create a symbolic link to /usr/bin/metaffi. return value: {res}')


def install_ubuntu() -> str:
	global ubuntu_x64_zip
	
	# verify running as admin
	is_admin = os.getuid() == 0 # pyright: ignore
	if not is_admin:
		raise Exception('Installer must run as sudo')
	
	print()
	print('==== Starting installation ====')
	print()
	
	# get install dir
	install_dir = get_install_dir("/usr/local/metaffi/")
	
	# unpack zip into install dir
	unpack_into_directory(ubuntu_x64_zip, install_dir)
	
	make_metaffi_available_globally(install_dir)
	
	# setting METAFFI_HOME environment variable
	# set_ubuntu_environment_variable("~/.profile", "METAFFI_HOME", install_dir)
	os.system('sed -i "/export METAFFI_HOME=/d" ~/.profile')
	os.system(f'echo "export METAFFI_HOME={install_dir}" >> ~/.profile')
	os.environ['METAFFI_HOME'] = install_dir
 
	# make uninstaller executable
	os.system(f'chmod u+x {install_dir}/uninstall')
	
	return install_dir


# -------------------------------


def set_installer_flags():
	global is_silent
	
	for arg in sys.argv:
		arg = arg.lower()
		
		if arg == '-h' or arg == '--help' or arg == '/?' or arg == '/h':
			print('MetaFFI Installer')
			print('-s - silent mode (using defaults)')
			return False
		
		if arg == "/s" or arg == "-s":
			is_silent = True
		
			
	return True


def main():
	global run_api_tests_script

	if not set_installer_flags():  # returns is continue running installer
		return
	
	try:
		install_dir = None
		if platform.system() == 'Windows':
			install_dir = install_windows()
		elif platform.system() == 'Linux':
			import distro # pyright: ignore
			if distro.name() == 'Ubuntu':
				install_dir = install_ubuntu()
			else:
				print("Currently, MetaFFI doesn't support {} distribution".format(distro.name()), file=sys.stderr)
				exit(1)
		else:
			print("Currently, MetaFFI doesn't support {}".format(platform.system()), file=sys.stderr)
			exit(1)

		if install_dir is None:
			print('Installation Directory is empty?! Something went wrong', file=sys.stderr)
			exit(3)

		# write "run_api_tests_script" script to install directory\run_api_tests.py
		with open(os.path.join(install_dir, 'run_api_tests.py'), 'w') as f:
			f.write(run_api_tests_script)
	
  
	except Exception as exp:
		traceback.print_exc()
		exit(2)
	
	print('\nInstallation Complete!')
	print('Notice you might need to logout/login or reboot to apply the')
	print('environment variables changes (like METAFFI_HOME)')
	
	if platform.system() != 'Windows':
		print('\nYou can set METAFFI_HOME now by running the following command:')
		print(f'source ~/.profile')


if __name__ == '__main__':
	main()
