import subprocess

# Configuration
package_id = "MetaFFI.MetaFFI"
version = "0.3.0"
installer_url = "https://github.com/MetaFFI/metaffi-root/releases/download/v0.3.0/metaffi_installer.exe"
silent_args = "-s"

# Command
cmd = [
    "wingetcreate", "new", package_id,
    "--version", version,
    "--url", installer_url,
    "--silent", silent_args,
    "--save"
]

print("Running initial wingetcreate (first-time submission)...")
subprocess.run(cmd, check=True)
print("Now you can manually edit the saved manifest files if needed.")

# Submit command (after editing YAML)
submit_path = f"manifests\\M\\MetaFFI\\MetaFFI\\{version}"
cmd_submit = ["wingetcreate", "submit", submit_path]

print(f"Submitting manifest from {submit_path}...")
subprocess.run(cmd_submit, check=True)
print("Submission complete.")

