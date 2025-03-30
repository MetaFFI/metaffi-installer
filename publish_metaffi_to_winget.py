import subprocess

# Update with each new version
package_id = "MetaFFI.MetaFFI"
version = "0.3.1"  # <-- change this each time
installer_url = "https://github.com/MetaFFI/metaffi-root/releases/download/v0.3.1/metaffi_installer.exe"
silent_args = "-s"

# Command
cmd = [
    "wingetcreate", "update", package_id,
    "--version", version,
    "--url", installer_url,
    "--silent", silent_args
]

print("Publishing updated version to winget...")
subprocess.run(cmd, check=True)
print("Update submitted.")
