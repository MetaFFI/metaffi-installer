import os
import sys
import glob
import re
from github import Github, GithubException

# --- CONFIGURATION ---
GITHUB_REPO = "MetaFFI/metaffi-root"
INSTALLERS_DIR = os.path.join(os.path.dirname(__file__), "installers_output")
EXE_PATTERN = os.path.join(INSTALLERS_DIR, "pyinstaller-*.exe")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable not set.")
    sys.exit(1)

# --- LOCATE INSTALLER ---
exe_files = glob.glob(EXE_PATTERN)
if len(exe_files) == 0:
    print("No pyinstaller-*.exe file found in ./installers_output/")
    sys.exit(1)
elif len(exe_files) > 1:
    print("Error: More than one .exe file found:")
    for f in exe_files:
        print(" -", f)
    sys.exit(1)

exe_path = exe_files[0]
exe_filename = os.path.basename(exe_path)

# Extract version from filename
match = re.match(r"pyinstaller-(\d+\.\d+\.\d+)\.exe", exe_filename)
if not match:
    print(f"Error: Filename '{exe_filename}' does not match expected pattern.")
    sys.exit(1)

version = match.group(1)
release_tag = f"v{version}"

# --- CONNECT TO GITHUB ---
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)

# --- CREATE OR GET RELEASE ---
try:
    release = repo.get_release(release_tag)
    print(f"ℹ️ Release '{release_tag}' already exists.")
except GithubException as e:
    if e.status == 404:
        print(f"🚀 Creating new release: {release_tag}")
        release = repo.create_git_release(
            tag=release_tag,
            name=release_tag,
            message=f"Auto-generated release for MetaFFI {version}",
            draft=False,
            prerelease=False,
            latest=True
        )
    else:
        print(f"GitHub API error: {e}")
        sys.exit(1)

# --- UPLOAD ASSET ---
# Check if asset already uploaded
existing_assets = [a.name for a in release.get_assets()]
if exe_filename in existing_assets:
    print(f"File '{exe_filename}' already exists in the release. Skipping upload.")
else:
    print(f"Uploading '{exe_filename}' to GitHub release '{release_tag}'...")
    with open(exe_path, 'rb') as exe_file:
        release.upload_asset(
            path=exe_path,
            name=exe_filename,
            label=exe_filename,
            content_type="application/vnd.microsoft.portable-executable"
        )
    print("Upload complete.")
