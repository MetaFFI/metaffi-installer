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

metaffi_home = os.environ['METAFFI_HOME']
if metaffi_home is None:
	print('METAFFI_HOME is not set.')
	print('if you try to uninstall MetaFFI, please remove the installation directory manually, and remove METAFFI_HOME from the environment variables')
	print('for each plugin, you will need to run their corresponding uninstall script if such exists. If not, you will need to remove the plugin directory manually and revert their environmental changes')
	sys.exit(1)

metaffi_home = os.path.abspath(metaffi_home)
for plugindir in os.listdir(metaffi_home):
	if plugindir == 'include':
		continue
	
	print(f'Uninstalling {plugindir}')
	
	uninstall_script_path = os.path.join(metaffi_home, plugindir, 'uninstall_plugin.py')
	if not os.path.isfile(uninstall_script_path):
		shutil.rmtree(os.path.join(metaffi_home, plugindir), ignore_errors=True)
		continue
	
	try:
		subprocess.run([uninstall_script_path], check=True)
		
		# if directory still exists, force-delete it
		if os.path.exists(os.path.join(metaffi_home, plugindir)):
			shutil.rmtree(os.path.join(metaffi_home, plugindir), ignore_errors=True)
	except subprocess.CalledProcessError as e:
		print(f'Error: {uninstall_script_path} failed with exit code {e.returncode}')
		sys.exit(e.returncode)

SysEnv().unset('METAFFI_HOME')

# if windows - remove METAFFI_HOME from the environment variables permanently
# using powershell
if platform.system() == 'Windows':
	subprocess.run(['powershell', '[System.Environment]::SetEnvironmentVariable("METAFFI_HOME", $null, "Machine")'], check=True)
if platform.system() == 'Linux':
	os.system('sed -i "/METAFFI_HOME/d" ~/.profile')


shutil.rmtree(metaffi_home, ignore_errors=True)

print('Uninstallation completed successfully')

sys.exit(0)
