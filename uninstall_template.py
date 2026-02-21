# iterate over all the directories in $METAFFI_HOME (the plugins) but "include" directory
# for each directory, check if the directory contains a "uninstall.sh" script
# if it doesn't, print a warning message and force-delete the directory recursively
# if it does, run "uninstall.sh" in the directory and then force-delete the directory recursively (if the directory still exists)

# delete $METAFFI_HOME directory
# remove METAFFI_HOME from the environment variables (make sure it is removed permanently)
import importlib
import sys
import subprocess




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


ensure_package("shutil")
ensure_package("pycrosskit")

import os
import sys
import subprocess
import platform
import shutil
from pycrosskit.envariables import SysEnv

def run_uninstaller(uninstaller_path: str, uninstaller_type: str):
	print(f'Executing uninstaller: {uninstaller_path}')
	if uninstaller_type == 'exe':
		subprocess.run([uninstaller_path], check=True)
	elif uninstaller_type == 'script':
		if platform.system() == 'Windows':
			subprocess.run(['cmd', '/c', uninstaller_path], check=True)
		else:
			subprocess.run(['bash', uninstaller_path], check=True)
	elif uninstaller_type == 'python':
		print('WARNING: Falling back to legacy Python plugin uninstaller.')
		subprocess.run([sys.executable, uninstaller_path], check=True)
	else:
		raise ValueError(f'Unknown uninstaller type: {uninstaller_type}')


def get_uninstaller_candidates(plugin_dir: str) -> list[tuple[str, str]]:
	if platform.system() == 'Windows':
		return [
			(os.path.join(plugin_dir, 'uninstall_plugin.exe'), 'exe'),
			(os.path.join(plugin_dir, 'uninstall.bat'), 'script'),
			(os.path.join(plugin_dir, 'uninstall_plugin.py'), 'python'),
			(os.path.join(plugin_dir, 'uninstall.py'), 'python'),
		]
	return [
		(os.path.join(plugin_dir, 'uninstall_plugin'), 'exe'),
		(os.path.join(plugin_dir, 'uninstall.sh'), 'script'),
		(os.path.join(plugin_dir, 'uninstall_plugin.py'), 'python'),
		(os.path.join(plugin_dir, 'uninstall.py'), 'python'),
	]


metaffi_home = os.environ.get('METAFFI_HOME')
if metaffi_home is None or metaffi_home == '':
	print('METAFFI_HOME is not set.')
	print('if you try to uninstall MetaFFI, please remove the installation directory manually, and remove METAFFI_HOME from the environment variables')
	print('for each plugin, you will need to run their corresponding uninstall script if such exists. If not, you will need to remove the plugin directory manually and revert their environmental changes')
	sys.exit(1)

metaffi_home = os.path.abspath(metaffi_home)
plugin_failures = []

for plugindir in os.listdir(metaffi_home):
	if plugindir == 'include':
		continue

	plugin_dir = os.path.join(metaffi_home, plugindir)
	if not os.path.isdir(plugin_dir):
		continue
	
	print(f'Uninstalling {plugindir}')

	selected_uninstaller = None
	for candidate, ctype in get_uninstaller_candidates(plugin_dir):
		if os.path.isfile(candidate):
			selected_uninstaller = (candidate, ctype)
			break

	try:
		if selected_uninstaller is not None:
			run_uninstaller(selected_uninstaller[0], selected_uninstaller[1])
		else:
			print(f'WARNING: No uninstaller found for plugin "{plugindir}", deleting plugin directory directly.')

		if os.path.exists(plugin_dir):
			shutil.rmtree(plugin_dir, ignore_errors=True)
	except subprocess.CalledProcessError as e:
		error_msg = f'Error: plugin "{plugindir}" uninstaller failed with exit code {e.returncode}'
		print(error_msg)
		plugin_failures.append(error_msg)
	except Exception as e:
		error_msg = f'Error: plugin "{plugindir}" uninstall failed: {e}'
		print(error_msg)
		plugin_failures.append(error_msg)


try:
	SysEnv().unset('METAFFI_HOME')
except Exception as e:
	pass

# if windows - remove METAFFI_HOME from the environment variables permanently
# using powershell
if platform.system() == 'Windows':
	subprocess.run(['powershell', '[System.Environment]::SetEnvironmentVariable("METAFFI_HOME", $null, "Machine")'], check=True)
if platform.system() == 'Linux':
	os.system('sed -i "/METAFFI_HOME/d" ~/.profile')


shutil.rmtree(metaffi_home, ignore_errors=True)

if len(plugin_failures) > 0:
	print('Uninstallation completed with plugin failures:')
	for failure in plugin_failures:
		print(f'  - {failure}')
	sys.exit(3)

print('Uninstallation completed successfully')

sys.exit(0)

