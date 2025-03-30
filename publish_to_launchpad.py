import os
import shutil
import subprocess
import sys
import re
from pathlib import Path
import hashlib
from datetime import datetime
import requests
import json

# Global constants
PPA_NAME = "green-fuzer/metaffi"
DISTRIBUTIONS = ['jammy', 'kinetic', 'noble']
MAINTAINER = "T. C. S. <green.fuzer+launchpad@gmail.com>"
TEAM_EMAIL = "team@metaffi.com"
GITHUB_URL = "https://github.com/MetaFFI/metaffi"
LAUNCHPAD_API_URL = "https://api.launchpad.net/1.0"

# Multiline strings
CONTROL_FILE_CONTENT = """Source: metaffi
Section: utils
Priority: optional
Maintainer: T. C. S. <green.fuzer+launchpad@gmail.com>
Build-Depends: debhelper-compat (= 10)
Standards-Version: 4.5.0

Package: metaffi
Architecture: amd64
Depends: ${shlibs:Depends}, ${misc:Depends}
Description: MetaFFI - Multi-Lingual Interoperability System
 MetaFFi is a tool for creating foreign function interfaces.
"""

RULES_FILE_CONTENT = """#!/usr/bin/make -f
%:
	dh $@
"""

COPYRIGHT_FILE_CONTENT = f"""Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: metaffi
Source: {GITHUB_URL}

Files: *
Copyright: 2024 MetaFFI Team <{TEAM_EMAIL}>
License: MIT

Files: debian/*
Copyright: 2024 MetaFFI Team <{TEAM_EMAIL}>
License: MIT
"""

def is_windows():
	return sys.platform == "win32"

def convert_to_wsl_path(windows_path):
	path = windows_path.replace('C:', '/mnt/c').replace('c:', '/mnt/c')
	path = path.replace('\\', '/')
	if not path.startswith('/'):
		path = '/' + path
	return path

def run_command(cmd, cwd=None):
	try:
		print(f"Running command: {' '.join(cmd)} - cwd: {cwd}")
		result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=cwd)
		return result.stdout
	except subprocess.CalledProcessError as e:
		print(f"Command failed: {' '.join(cmd)}")
		print("Error output:", e.stderr)
		print("Standard output:", e.stdout)
		raise

def check_requirements():
	required_packages = [
		'gpg', 'dput', 'devscripts', 'build-essential', 'debhelper'
	]
	missing_packages = []
	try:
		result = subprocess.run(['dpkg', '-l'] + required_packages, capture_output=True, text=True, check=True)
		installed_packages = result.stdout.split('\n')
		for package in required_packages:
			if not any(package in line and 'ii' in line for line in installed_packages):
				missing_packages.append(package)
		if missing_packages:
			print(f"Missing required packages: {', '.join(missing_packages)}")
			print("Please install them using:")
			print("sudo apt install " + " ".join(missing_packages))
			sys.exit(1)
	except subprocess.CalledProcessError as e:
		print(f"Failed to check installed packages: {e}")
		sys.exit(1)

def setup_temp_dir(distro):
	script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
	temp_dir = script_dir / f"launchpad_temp_{distro}"
	if temp_dir.exists():
		shutil.rmtree(temp_dir)
	temp_dir.mkdir(parents=True, exist_ok=True)
	return temp_dir

def extract_version_from_deb(deb_file):
	match = re.match(r'metaffi_(\d+\.\d+\.\d+)_amd64\.deb', deb_file.name)
	if not match:
		raise ValueError(f"Invalid DEB filename format: {deb_file.name}")
	return match.group(1)

def increment_version(version):
	# Split version into base version and revision
	parts = version.split('.')
	if len(parts) == 3:  # If version is like 0.3.0
		return f"{version}.1"
	elif len(parts) == 4:  # If version is like 0.3.0.1
		base = '.'.join(parts[:3])
		rev = int(parts[3])
		return f"{base}.{rev + 1}"
	return f"{version}.1"  # Fallback case

def get_deb_file():
	deb_pattern = "metaffi_*_amd64.deb"
	script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
	search_dir = script_dir / "installers_output"
	deb_files = list(search_dir.glob(deb_pattern))
	if not deb_files:
		print(f"No DEB file found matching pattern: {deb_pattern}")
		print(f"Searched in directory: {search_dir}")
		sys.exit(1)
	if len(deb_files) > 1:
		print("Error: Multiple DEB files found. Please ensure only one DEB file exists.")
		for deb in deb_files:
			print(f"- {deb.name}")
		sys.exit(1)
	return deb_files[0]

def extract_deb_contents(deb_file, temp_dir):
	run_command(['dpkg-deb', '-x', str(deb_file), str(temp_dir / 'extracted')])
	run_command(['dpkg-deb', '--control', str(deb_file), str(temp_dir / 'extracted/DEBIAN')])

def create_source_directory_structure(temp_dir, version, distro):
	source_dir = temp_dir / f'metaffi-{version}-{distro}'
	source_dir.mkdir(parents=True, exist_ok=True)
	return source_dir

def copy_deb_contents(source_dir, temp_dir):
	usr_dir = temp_dir / 'extracted/usr'
	for sub in ['bin', 'lib', 'include']:
		src = usr_dir / sub
		dest = source_dir / f'usr/{sub}'
		if src.exists():
			shutil.copytree(src, dest, dirs_exist_ok=True)

def create_debian_directory(source_dir):
	debian_dir = source_dir / 'debian'
	debian_dir.mkdir(parents=True, exist_ok=True)
	return debian_dir

def create_source_format_file(debian_dir):
	source_format_dir = debian_dir / 'source'
	source_format_dir.mkdir(parents=True, exist_ok=True)
	with open(source_format_dir / 'format', 'w') as f:
		f.write("3.0 (quilt)\n")
	with open(source_format_dir / 'options', 'w') as f:
		f.write("extend-diff-ignore = \"^[a-zA-Z0-9]+: [0-9]+\"\n")
		f.write("tar-ignore = .git\n")
		f.write("tar-ignore = .gitignore\n")
		f.write("tar-ignore = .gitattributes\n")

def create_control_file(debian_dir):
	with open(debian_dir / 'control', 'w') as f:
		f.write(CONTROL_FILE_CONTENT)

def create_rules_file(debian_dir):
	with open(debian_dir / 'rules', 'w') as f:
		f.write(RULES_FILE_CONTENT)
	os.chmod(debian_dir / 'rules', 0o755)

def create_changelog(debian_dir, version, distro):
	now = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
	with open(debian_dir / 'changelog', 'w') as f:
		f.write(f"""metaffi ({version}) {distro}; urgency=medium

  * Initial release

 -- {MAINTAINER}  {now}\n""")

def create_copyright_file(debian_dir):
	with open(debian_dir / 'copyright', 'w') as f:
		f.write(COPYRIGHT_FILE_CONTENT)

def create_upstream_tarball(temp_dir, version, distro):
	# Use the full version including the fourth number for the tarball name
	run_command(['tar', 'czf', f'metaffi_{version}.orig.tar.gz', f'metaffi-{version}-{distro}'], cwd=temp_dir)

def create_postinst_file(debian_dir):
    postinst_path = debian_dir / 'postinst'
    with open(postinst_path, 'w') as f:
        f.write("""#!/bin/bash
set -e

echo "[postinst] Running MetaFFI installer..."

# Run the MetaFFI installer binary
if [ -x /usr/lib/metaffi/metaffi-installer ]; then
    /usr/lib/metaffi/metaffi-installer --install
else
    echo "Warning: metaffi-installer not found or not executable"
fi

exit 0
""")
    os.chmod(postinst_path, 0o755)

def create_source_package(deb_file, version, temp_dir, distro):
	extract_deb_contents(deb_file, temp_dir)
	source_dir = create_source_directory_structure(temp_dir, version, distro)
	copy_deb_contents(source_dir, temp_dir)
	debian_dir = create_debian_directory(source_dir)
	create_source_format_file(debian_dir)
	create_control_file(debian_dir)
	create_postinst_file(debian_dir)
	create_rules_file(debian_dir)
	create_changelog(debian_dir, version, distro)
	create_copyright_file(debian_dir)
	create_upstream_tarball(temp_dir, version, distro)

def get_gpg_fingerprint():
	output = run_command(['gpg', '--list-secret-keys', '--fingerprint'])
	lines = output.splitlines()
	for i, line in enumerate(lines):
		if line.strip().startswith("sec") and i + 1 < len(lines):
			raw_fingerprint = lines[i + 1].strip().replace(" ", "")
			if len(raw_fingerprint) == 40:
				return raw_fingerprint
	raise ValueError("GPG fingerprint not found.")

def build_source_package(temp_dir, version, distro):
	fingerprint = get_gpg_fingerprint()
	source_dir = temp_dir / f'metaffi-{version}-{distro}'
	run_command(['dpkg-buildpackage', '-S', '-sa', f'-k{fingerprint}'], cwd=source_dir)
	if not (temp_dir / f'metaffi_{version}_source.changes').exists():
		raise FileNotFoundError("Changes file not found after build.")

def upload_to_launchpad(temp_dir, version, distro):
	changes_file = temp_dir / f'metaffi_{version}_source.changes'
	try:
		run_command(['dput', f'ppa:{PPA_NAME}', str(changes_file)])
		return True
	except subprocess.CalledProcessError as e:
		if 'already exists' in e.stderr:
			return False
		raise

def check_version_exists(version):
	"""Check if a version exists in the Launchpad PPA for a specific distribution."""
	# Extract owner and PPA name from PPA_NAME
	owner, ppa_name = PPA_NAME.split('/')
	
	# Construct the API URL for published binaries in the PPA
	url = f"{LAUNCHPAD_API_URL}/~{owner}/+archive/ubuntu/{ppa_name}?ws.op=getPublishedBinaries"
	
	# Get the published binaries information
	response = requests.get(url)
	if response.status_code != 200:
		raise RuntimeError(f"Failed to access Launchpad API: {response.status_code}")
		
	data = response.json()
	
	# Check if this version exists for the specified distribution
	for entry in data.get("entries", []):
		# Extract distro name from link
		distro_arch_link = entry.get("distro_arch_series_link", "")
		entry_distro = distro_arch_link.split("/")[-2] if distro_arch_link else "unknown"
		
		if (entry.get("source_package_name") == "metaffi" and
			entry.get("source_package_version") == version):
			print(f"Found existing version {entry['source_package_version']}")
			return True
			
	return False

def find_next_available_version(base_version):
	"""Find the next available version number for the package."""
	version = base_version
	while check_version_exists(version):
		print(f"Version {version} already exists, incrementing...")
		version = increment_version(version)
  
	jammy_version = version
	noble_version = increment_version(jammy_version)
  
	return {
		'jammy': jammy_version,
		'noble': noble_version
	}

def main():
	if is_windows():
		print("Running on Windows, rerunning in WSL...")
		script_path = os.path.abspath(__file__)
		wsl_path = convert_to_wsl_path(script_path)
		wsl_command = f"cd {os.path.dirname(wsl_path)} && python3 {os.path.basename(wsl_path)}"
		subprocess.run(['wsl', 'bash', '-c', wsl_command], check=True)
		return

	check_requirements()
	deb_file = get_deb_file()
	base_version = extract_version_from_deb(deb_file)
	print(f"Using DEB file: {deb_file} (base version: {base_version})")

	versions = find_next_available_version(base_version)

	for distro in DISTRIBUTIONS:
		print(f"\nProcessing distro: {distro}")
		# Find the next available version for this distro
		version = versions[distro]
		print(f"Using version: {version} for {distro}")
		
		temp_dir = setup_temp_dir(distro)
		try:
			create_source_package(deb_file, version, temp_dir, distro)
			build_source_package(temp_dir, version, distro)
			if upload_to_launchpad(temp_dir, version, distro):
				print(f"Package uploaded successfully for {distro}!")
			else:
				print(f"Failed to upload package for {distro}")
		except Exception as e:
			print(f"Error while processing distro {distro}: {e}")
			print("Preserving temp directory for debugging:", temp_dir)
			raise

	print("\nAll packages uploaded. Users can now install with:")
	print(f"sudo add-apt-repository ppa:{PPA_NAME}")
	print("sudo apt update")
	print("sudo apt install metaffi")

if __name__ == '__main__':
	main()
