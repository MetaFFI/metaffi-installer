import base64
import io
import argparse
import platform
import re
import shlex
import shutil
import sys
import ctypes
import os
import tempfile
import traceback
import typing
import zipfile
import subprocess
import urllib.request

windows_x64_zip = 'windows_x64_zip_data'
ubuntu_x64_zip = 'ubuntu_x64_zip_data'
PLUGIN_VERSION = '0.0.0'
PLUGIN_NAME=""
is_silent = False

def setup_environment():
	pass

def check_prerequisites() -> bool:
	pass

def print_prerequisites():
	pass

# ====================================

def install_pip_package(package_name: str):
	command = f"pip show {package_name}"
	err_code, stdout, stderr = run_command(command, False, False)
	
	if err_code != 0:
		reply = ask_user(f'{package_name} python package is required for the installation, do you want me to install it?', 'y', ['y', 'n'])
		if reply == 'n':
			raise Exception(f'Cannot continue without {package_name}, please install it and try again')
		
		command = f"{sys.executable} -m pip install {package_name}"
		err_code, stdout, stderr = run_command(command, True, False)
		if err_code != 0:
			raise Exception(f"Failed installing {package_name} with the command {command}. Error code {err_code}. Output:\n{stdout}{stderr}")


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


def run_command(command: str, raise_if_command_fail: bool = False, is_refresh_envvars: bool = True):
	global refresh_env
	
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



# ========== unitests ==========

def get_exe_format(execname):
	if platform.system() == 'Windows':
		return f'{execname}.exe'
	else:
		return f'./{execname}'



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


def install():
	global windows_x64_zip
	global ubuntu_x64_zip

	if not check_prerequisites():
		print('Prerequisites not met. Please make sure all prerequisites are installed and try again.')
		print_prerequisites()
		sys.exit(1)

	x64_zip = None
	
	if is_windows():
		refresh_windows_env()  # refresh environment variables, in case the environment is not up-to-date

		x64_zip = windows_x64_zip
	elif is_ubuntu():
		# verify running as root
		is_admin = os.getuid() == 0 # pyright: ignore
		if not is_admin:
			raise Exception('Installer must run as sudo')
		
		refresh_ubuntu_env()  # refresh environment variables, in case the environment is not up-to-date

		x64_zip = ubuntu_x64_zip
	else:
		raise Exception('Unsupported OS')
	
	assert x64_zip is not None, 'x64_zip should not be None by now... Something is wrong...'

	print()
	print('==== Starting installation ====')
	print()
	
	# get install dir
	metaffi_home = os.environ.get('METAFFI_HOME')
	if metaffi_home is None:
		print('METAFFI_HOME environment variable is not set. Make sure METAFFI has been installed')
		sys.exit(1)

	# create metaffi_home/plugin_name dir
	print('Creating plugin directory...')
	install_dir = os.path.join(metaffi_home, PLUGIN_NAME)
	if not os.path.exists(install_dir):
		os.makedirs(install_dir)

	# unpack zip into install dir
	print('Unpacking zip into plugin directory...')
	unpack_into_directory(x64_zip, install_dir)
	
	# setup environment
	print('Setting up environment...')
	setup_environment()
 
	# if ubuntu, make uninstall as executable
	print('Making uninstall executable and script...')
	if is_ubuntu():
		os.chmod(os.path.join(install_dir, 'uninstall_plugin'), 0o755)
  
  
	# create uninstall script for windows or linux that copies uninstall executable to temp directory and executes it
	if is_windows():
		uninstall_script_content = f"""@echo off
set TEMP_DIR=%TEMP%\\metaffi_uninstall_%RANDOM%
mkdir "%TEMP_DIR%"
copy "{install_dir}\\uninstall_plugin.exe" "%TEMP_DIR%\\uninstall_plugin.exe"
"%TEMP_DIR%\\uninstall_plugin.exe"
rmdir /S /Q "%TEMP_DIR%"
"""
		with open(f'{install_dir}/uninstall.bat', 'w') as f:
			f.write(uninstall_script_content)
	else:
		uninstall_script_content = f"""#!/bin/bash
TEMP_DIR=$(mktemp -d)
cp "{install_dir}/uninstall_plugin" "$TEMP_DIR/uninstall_plugin"
chmod +x "$TEMP_DIR/uninstall_plugin"
"$TEMP_DIR/uninstall_plugin"
rm -rf "$TEMP_DIR"
"""
		with open(f'{install_dir}/uninstall.sh', 'w') as f:
			f.write(uninstall_script_content)
   
		os.chmod(f'{install_dir}/uninstall.sh', 0o755)


	return install_dir

	


# -------------------------------


def run_subprocess(command: list[str], description: str):
	print(f'Executing ({description}): {" ".join(command)}')
	subprocess.run(command, check=True)


def uninstall() -> str:
	metaffi_home = os.environ.get('METAFFI_HOME')
	if metaffi_home is None or metaffi_home == '':
		raise Exception('METAFFI_HOME environment variable is not set. Cannot uninstall plugin.')

	install_dir = os.path.join(metaffi_home, PLUGIN_NAME)
	if not os.path.isdir(install_dir):
		raise Exception(f'Plugin installation directory does not exist: {install_dir}')

	if is_windows():
		candidates = [
			(os.path.join(install_dir, 'uninstall_plugin.exe'), 'exe'),
			(os.path.join(install_dir, 'uninstall.bat'), 'script'),
			(os.path.join(install_dir, 'uninstall_plugin.py'), 'python'),
			(os.path.join(install_dir, 'uninstall.py'), 'python'),
		]
	else:
		candidates = [
			(os.path.join(install_dir, 'uninstall_plugin'), 'exe'),
			(os.path.join(install_dir, 'uninstall.sh'), 'script'),
			(os.path.join(install_dir, 'uninstall_plugin.py'), 'python'),
			(os.path.join(install_dir, 'uninstall.py'), 'python'),
		]

	executed = False
	for candidate, ctype in candidates:
		if not os.path.isfile(candidate):
			continue

		executed = True
		if ctype == 'exe':
			run_subprocess([candidate], 'plugin executable uninstaller')
		elif ctype == 'script':
			if is_windows():
				run_subprocess(['cmd', '/c', candidate], 'plugin script uninstaller')
			else:
				run_subprocess(['bash', candidate], 'plugin script uninstaller')
		elif ctype == 'python':
			print('WARNING: Falling back to legacy Python plugin uninstaller.')
			run_subprocess([sys.executable, candidate], 'legacy python uninstaller')

		break

	if not executed:
		raise Exception(
			f'No uninstaller found in {install_dir}. Expected one of: '
			f'uninstall_plugin(.exe), uninstall.(bat|sh), uninstall_plugin.py, uninstall.py'
		)

	if os.path.isdir(install_dir):
		shutil.rmtree(install_dir, ignore_errors=True)

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


def set_ubuntu_user_environment_variable(name: str, value: str):
	set_ubuntu_environment_variable('~/.profile', name, value)


def set_ubuntu_machine_environment_variable(name: str, value: str):
	set_ubuntu_system_environment_variable(name, value)


def check_python_ubuntu_installed(version: str):
	# split the version number into major, minor, and micro parts
	major, minor = map(int, version.split("."))
	
	# construct the executable file name based on the version number
	exe_name = f"python{major}.{minor}"
	
	# try to run the executable file using subprocess
	exit_code, stdout, stderr = run_command(f'{exe_name} --version')
	
	if exit_code != 0 or not stdout.strip().startswith(f"Python {version}"):
		reply = ask_user(f'Python {exe_name} is not installed, do you want me to install it for you?', 'y', ['y', 'n'])
		if reply == 'n':
			raise Exception(f"{exe_name} cannot be found. Please check your Python {version} is installed, and in PATH environment variable")
		
		# install python and python-dev (for the libraries to embed python in C)
		exit_code, stdout, stderr = run_command(f'apt install {exe_name} {exe_name}-dev -y')
		if exit_code != 0:
			raise Exception(f'Failed to install {exe_name}. Output\n{stdout}{stderr}')


def set_ubuntu_system_environment_variable(name: str, value: str):
	# construct the file name for the environment file
	env_file = "/etc/environment"
	
	# read the existing lines from the environment file
	with open(env_file, "r") as f:
		lines = f.readlines()
	
	# check if the environment variable already exists in the environment file
	for i, line in enumerate(lines):
		if line.startswith(f"{name}="):
			# get the current value of the environment variable
			current_value = line.split("=")[1].strip()
			if current_value == value:
				# if the value is the same, do nothing
				return
			else:
				# if the value is different, replace the line with the new value
				lines[i] = f"{name}={value}\n"
				break
	else:
		# if the environment variable does not exist, append a new line with the name and value
		lines.append(f"{name}={value}\n")
	
	# write the modified lines back to the environment file
	with open(env_file, "w") as f:
		f.writelines(lines)
	
	refresh_env()


def make_metaffi_available_globally(install_dir: str):
	run_command(f'chmod u+x {install_dir}/metaffi', True)
	run_command(f'ln -s {install_dir}/metaffi /usr/bin/metaffi', True)


# -------------------------------


def parse_action_and_flags():
	parser = argparse.ArgumentParser(description=f'MetaFFI Plugin Installer ({PLUGIN_NAME})')
	parser.add_argument('legacy_action', nargs='?', choices=['install', 'uninstall', 'check-prerequisites', 'print-prerequisites'])
	parser.add_argument('-c', '--check-prerequisites', action='store_true', help='Check plugin prerequisites only')
	parser.add_argument('-p', '--print-prerequisites', action='store_true', help='Print prerequisites only')
	parser.add_argument('-i', '--install', action='store_true', help='Install plugin')
	parser.add_argument('-u', '--uninstall', action='store_true', help='Uninstall plugin')
	parser.add_argument('-s', '--silent', action='store_true', help='Silent mode')
	args = parser.parse_args()

	flag_actions = []
	if args.check_prerequisites:
		flag_actions.append('check-prerequisites')
	if args.print_prerequisites:
		flag_actions.append('print-prerequisites')
	if args.install:
		flag_actions.append('install')
	if args.uninstall:
		flag_actions.append('uninstall')

	if len(flag_actions) > 1:
		raise Exception(f'Choose only one action flag. Got: {flag_actions}')

	action = flag_actions[0] if len(flag_actions) == 1 else None

	if args.legacy_action is not None:
		if action is not None and action != args.legacy_action:
			raise Exception(f'Conflicting actions: positional={args.legacy_action} flag={action}')
		action = args.legacy_action

	if action is None:
		# Backward-compatible default behavior
		action = 'install'

	return action, args.silent


def main():
	global is_silent

	try:
		action, is_silent = parse_action_and_flags()

		if action == 'check-prerequisites':
			if check_prerequisites():
				print('Prerequisites check passed')
				exit(0)
			print('Prerequisites check failed')
			print_prerequisites()
			exit(1)

		if action == 'print-prerequisites':
			print_prerequisites()
			exit(0)

		if action == 'install':
			install_dir = install()
			print('\nInstallation Complete!\nNotice you might need to logout/login or reboot to apply environmental changes\n')
			print(f'To uninstall the plugin, run the "uninstall_plugin" at the plugin installation directory: {install_dir}\n')
			exit(0)

		if action == 'uninstall':
			uninstalled_dir = uninstall()
			print(f'Plugin uninstalled successfully from: {uninstalled_dir}')
			exit(0)

		raise Exception(f'Unsupported action: {action}')
	except Exception:
		traceback.print_exc()
		exit(2)

if __name__ == '__main__':
	main()
