import argparse
import base64
import os
from version import METAFFI_VERSION


def read_bytes(path: str) -> bytes:
	with open(path, "rb") as f:
		return f.read()


def create_combined_installer_script(windows_installer: str, ubuntu_installer: str, version: str, output_path: str):
	windows_payload = base64.b64encode(read_bytes(windows_installer)).decode("ascii")
	ubuntu_payload = base64.b64encode(read_bytes(ubuntu_installer)).decode("ascii")

	content = f"""#!/usr/bin/env python3
import base64
import os
import platform
import subprocess
import sys
import tempfile

METAFFI_VERSION = "{version}"
WINDOWS_INSTALLER = "{os.path.basename(windows_installer)}"
UBUNTU_INSTALLER = "{os.path.basename(ubuntu_installer)}"
WINDOWS_PAYLOAD_B64 = "{windows_payload}"
UBUNTU_PAYLOAD_B64 = "{ubuntu_payload}"


def write_payload(path: str, payload_b64: str):
    with open(path, "wb") as f:
        f.write(base64.b64decode(payload_b64.encode("ascii")))


def run_installer(installer_path: str):
    args = [installer_path] + sys.argv[1:]
    result = subprocess.run(args, check=False)
    sys.exit(result.returncode)


def main():
    system_name = platform.system()
    with tempfile.TemporaryDirectory(prefix="metaffi_installer_") as temp_dir:
        if system_name == "Windows":
            installer_path = os.path.join(temp_dir, WINDOWS_INSTALLER)
            write_payload(installer_path, WINDOWS_PAYLOAD_B64)
            run_installer(installer_path)
            return

        if system_name == "Linux":
            installer_path = os.path.join(temp_dir, UBUNTU_INSTALLER)
            write_payload(installer_path, UBUNTU_PAYLOAD_B64)
            os.chmod(installer_path, 0o755)
            run_installer(installer_path)
            return

        print(f"Unsupported OS for MetaFFI installer: {{system_name}}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
"""

	with open(output_path, "w", newline="\n") as f:
		f.write(content)

	# make executable on non-Windows hosts
	if os.name != "nt":
		os.chmod(output_path, 0o755)


def main():
	parser = argparse.ArgumentParser(description="Build combined MetaFFI installer from OS-specific installers")
	parser.add_argument("--windows-installer", required=True, help="Path to windows installer (.exe)")
	parser.add_argument("--ubuntu-installer", required=True, help="Path to ubuntu installer")
	parser.add_argument("--version", default=METAFFI_VERSION)
	parser.add_argument("--output", default=None, help="Output combined installer path")
	args = parser.parse_args()

	if not os.path.isfile(args.windows_installer):
		raise FileNotFoundError(f"Windows installer not found: {args.windows_installer}")
	if not os.path.isfile(args.ubuntu_installer):
		raise FileNotFoundError(f"Ubuntu installer not found: {args.ubuntu_installer}")

	if args.output is None or args.output == "":
		os.makedirs("./installers_output", exist_ok=True)
		output = os.path.abspath(f"./installers_output/metaffi-installer-{args.version}")
	else:
		output = os.path.abspath(args.output)
		os.makedirs(os.path.dirname(output), exist_ok=True)

	create_combined_installer_script(args.windows_installer, args.ubuntu_installer, args.version, output)
	print(f"Done. Built combined installer: {output}")


if __name__ == "__main__":
	script_dir = os.path.dirname(os.path.abspath(__file__))
	os.chdir(script_dir)
	main()
