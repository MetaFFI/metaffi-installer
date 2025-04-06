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