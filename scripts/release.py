#!/usr/bin/env python3

import logging
import os
import subprocess
import sys
from pathlib import Path

import requests
import tomli
import tomli_w
from click import command, confirm, option
from click.termui import prompt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=False)

# Package configuration for pdf2foundry (single package)
PACKAGE_CONFIG = {
    "name": "pdf2foundry",
    "pyproject_path": "pyproject.toml",
    "create_release": True,
}


# Configure logging
def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO

    # Create a custom formatter for cleaner output
    class CleanFormatter(logging.Formatter):
        def format(self, record):
            if record.levelname == "INFO":
                return record.getMessage()
            elif record.levelname == "ERROR":
                return f"❌ {record.getMessage()}"
            elif record.levelname == "DEBUG":
                return f"🔍 {record.getMessage()}"
            else:
                return f"{record.levelname}: {record.getMessage()}"

    # Remove any existing handlers
    logger = logging.getLogger(__name__)
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create console handler with custom formatter
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(CleanFormatter())

    logging.basicConfig(level=level, handlers=[console_handler], force=True)

    logger.setLevel(level)
    return logger


def get_current_version() -> str:
    """Get the current version from pyproject.toml."""
    logger = logging.getLogger(__name__)
    pyproject_path = PACKAGE_CONFIG["pyproject_path"]
    logger.debug(f"Reading current version from {pyproject_path}")

    if not Path(pyproject_path).exists():
        logger.error(f"pyproject.toml not found at {pyproject_path}")
        sys.exit(1)

    with open(pyproject_path, "rb") as f:
        pyproject = tomli.load(f)
    version = pyproject["project"]["version"]
    logger.debug(f"Current version: {version}")
    return version


def update_version(new_version: str, dry_run: bool = False) -> None:
    """Update the version in pyproject.toml."""
    logger = logging.getLogger(__name__)
    pyproject_path = PACKAGE_CONFIG["pyproject_path"]

    if dry_run:
        logger.info(f"[DRY RUN] Would update version in {pyproject_path} to {new_version}")
        return

    logger.info(f"Updating version in {pyproject_path} to {new_version}")
    with open(pyproject_path, "rb") as f:
        pyproject = tomli.load(f)

    pyproject["project"]["version"] = new_version

    with open(pyproject_path, "wb") as f:
        tomli_w.dump(pyproject, f)
    logger.debug("Version updated successfully")


def run_command(cmd: str, dry_run: bool = False) -> tuple[str, str]:
    """Run a shell command and return stdout and stderr."""
    logger = logging.getLogger(__name__)
    if dry_run and not cmd.startswith(
        (
            "git status",
            "git branch",
            "git log",
            "git fetch",
            "git rev-list",
            "git remote",
            "git rev-parse",
        )
    ):
        logger.debug(f"[DRY RUN] Would execute: {cmd}")
        return "", ""

    logger.debug(f"Executing command: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Command failed: {cmd}")
        logger.error(f"Error: {result.stderr}")
    return result.stdout.strip(), result.stderr.strip()


def check_git_status(dry_run: bool = False) -> bool:
    """Check if the working directory is clean."""
    logger = logging.getLogger(__name__)
    logger.debug("Checking git status")
    stdout, _ = run_command("git status --porcelain", dry_run)
    if stdout:
        logger.error("There are uncommitted changes. Please commit or stash them first.")
        if not dry_run:
            sys.exit(1)
        return False
    logger.debug("Git status check passed")
    return True


def check_current_branch(dry_run: bool = False) -> bool:
    """Check if we're on the main branch."""
    logger = logging.getLogger(__name__)
    logger.debug("Checking current branch")
    stdout, _ = run_command("git branch --show-current", dry_run)
    if stdout != "main":
        logger.error("Not on main branch. Please switch to main branch first.")
        if not dry_run:
            sys.exit(1)
        return False
    logger.debug("Current branch check passed")
    return True


def check_unpushed_commits(dry_run: bool = False) -> bool:
    """Check if there are any unpushed commits."""
    logger = logging.getLogger(__name__)
    logger.debug("Checking for unpushed commits")
    stdout, _ = run_command("git log origin/main..HEAD", dry_run)
    if stdout:
        logger.error("There are unpushed commits. Please push all changes before creating a release.")
        if not dry_run:
            sys.exit(1)
        return False
    logger.debug("No unpushed commits found")
    return True


def get_github_token(dry_run: bool = False) -> str:
    """Get GitHub token from environment variable."""
    logger = logging.getLogger(__name__)
    logger.debug("Getting GitHub token from environment")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN not found in .env file.")
        if not dry_run:
            sys.exit(1)
        return ""
    return token


def extract_repo_info(git_url: str, dry_run: bool = False) -> str:
    """
    Extract GitHub username and repository name from git remote URL.

    Returns the repo info in format "username/repo"
    """
    logger = logging.getLogger(__name__)
    logger.debug(f"Extracting repo info from: {git_url}")

    # Handle HTTPS URLs: https://github.com/username/repo.git
    if git_url.startswith("https://github.com/"):
        parts = git_url.replace("https://github.com/", "").replace(".git", "").split("/")
        if len(parts) >= 2:
            repo_path = "/".join(parts[:2])
            logger.debug(f"Extracted repo path from HTTPS URL: {repo_path}")
            return repo_path

    # Handle SSH URLs with ssh:// prefix: ssh://git@github.com/username/repo.git
    elif git_url.startswith("ssh://git@github.com/"):
        parts = git_url.replace("ssh://git@github.com/", "").replace(".git", "").split("/")
        if len(parts) >= 2:
            repo_path = "/".join(parts[:2])
            logger.debug(f"Extracted repo path from SSH URL (with prefix): {repo_path}")
            return repo_path

    # Handle SSH URLs without prefix: git@github.com:username/repo.git
    elif git_url.startswith("git@github.com:"):
        parts = git_url.replace("git@github.com:", "").replace(".git", "").split("/")
        if len(parts) >= 1:
            repo_path = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
            logger.debug(f"Extracted repo path from SSH URL (without prefix): {repo_path}")
            return repo_path

    logger.error(f"Could not parse repository path from Git URL: {git_url}")
    if dry_run:
        return "unknown/repo"
    sys.exit(1)


def create_github_release(version: str, token: str, dry_run: bool = False) -> None:
    """Create a GitHub release."""
    logger = logging.getLogger(__name__)
    tag_name = f"v{version}"

    if dry_run:
        logger.info(f"[DRY RUN] Would create GitHub release for version {version} with tag {tag_name}")
        return

    logger.info(f"Creating GitHub release for version {version}")
    # Get the latest commits for release notes
    stdout, _ = run_command("git log --pretty=format:'%h %s' -n 10")
    release_notes = f"## Changes for v{version}\n\n```\n{stdout}\n```"

    # Create release
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "tag_name": tag_name,
        "name": f"PDF2Foundry v{version}",
        "body": release_notes,
        "draft": False,
        "prerelease": "b" in version or "a" in version or "rc" in version,
    }

    # Get repository info
    stdout, _ = run_command("git remote get-url origin", dry_run)
    logger.debug(f"Raw Git remote URL: {stdout}")

    repo_url = extract_repo_info(stdout, dry_run)
    logger.debug(f"Parsed repository URL: {repo_url}")

    response = requests.post(f"https://api.github.com/repos/{repo_url}/releases", headers=headers, json=data)

    if response.status_code != 201:
        logger.error(f"Error creating GitHub release: {response.text}")
        sys.exit(1)
    logger.info("GitHub release created successfully")


def check_main_up_to_date(dry_run: bool = False) -> bool:
    """Check if local main branch is up to date with remote main."""
    logger = logging.getLogger(__name__)
    logger.debug("Checking if main branch is up to date")
    stdout, _ = run_command("git fetch origin main", dry_run)
    stdout, _ = run_command("git rev-list HEAD...origin/main --count", dry_run)
    if stdout != "0":
        logger.error("Local main branch is not up to date with remote main. Please pull the latest changes first.")
        if not dry_run:
            sys.exit(1)
        return False
    logger.debug("Main branch is up to date")
    return True


def check_release_notes_updated(new_version: str, dry_run: bool = False) -> bool:
    """Check if RELEASE_NOTES.md has been updated with the new version."""
    logger = logging.getLogger(__name__)
    logger.debug(f"Checking if RELEASE_NOTES.md has been updated for version {new_version}")

    release_notes_path = Path("RELEASE_NOTES.md")
    if not release_notes_path.exists():
        logger.error("RELEASE_NOTES.md file not found in the repository root")
        if not dry_run:
            sys.exit(1)
        return False

    try:
        with open(release_notes_path, encoding="utf-8") as f:
            content = f.read()

        # Look for the version section at the beginning of the file
        # Expected format: ## Version X.Y.Z - Date
        import re

        # Extract the first version section after the title
        lines = content.split("\n")
        version_pattern = r"^## Version (\d+\.\d+\.\d+(?:[ab]\d+|rc\d+)?)"

        for line in lines:
            if line.startswith("## Version"):
                match = re.match(version_pattern, line)
                if match:
                    found_version = match.group(1)
                    logger.debug(f"Found version section in RELEASE_NOTES.md: {found_version}")

                    if found_version == new_version:
                        logger.debug("Release notes are up to date with the new version")
                        return True
                    else:
                        logger.error(f"RELEASE_NOTES.md has not been updated for version {new_version}")
                        logger.error(f"Found version {found_version} but expected {new_version}")
                        logger.error("Please add a release notes section for the new version at the top of RELEASE_NOTES.md")
                        logger.error(f"Expected format: ## Version {new_version} - <Date>")
                        if not dry_run:
                            sys.exit(1)
                        return False
                break

        # If we get here, no version section was found
        logger.error("No version section found in RELEASE_NOTES.md")
        logger.error(f"Please add a release notes section for version {new_version}")
        logger.error(f"Expected format: ## Version {new_version} - <Date>")
        if not dry_run:
            sys.exit(1)
        return False

    except Exception as e:
        logger.error(f"Error reading RELEASE_NOTES.md: {e}")
        if not dry_run:
            sys.exit(1)
        return False


def check_github_workflows(dry_run: bool = False) -> bool:
    """Check if all GitHub Actions workflows are passing."""
    logger = logging.getLogger(__name__)
    logger.debug("Checking GitHub Actions workflow status")

    # Get repository info
    stdout, _ = run_command("git remote get-url origin", dry_run)
    logger.debug(f"Raw Git remote URL: {stdout}")

    repo_url = extract_repo_info(stdout, dry_run)
    logger.debug(f"Parsed repository URL: {repo_url}")

    if repo_url == "unknown/repo" and dry_run:
        logger.error("Could not parse repository URL - this would fail in a real run")
        return False

    # Get GitHub token
    token = get_github_token(dry_run)
    if not token and dry_run:
        logger.error("GitHub token not available - this would fail in a real run")
        return False
    elif not token:
        return False

    logger.debug("GitHub token obtained")

    # Get the latest workflow runs
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # First check for running workflows
    logger.debug("Checking for running workflows")

    response = requests.get(
        f"https://api.github.com/repos/{repo_url}/actions/runs",
        headers=headers,
        params={"branch": "main", "status": "in_progress", "per_page": 5},
    )

    if response.status_code != 200:
        logger.error(f"Error checking GitHub Actions status: {response.text}")
        if not dry_run:
            sys.exit(1)
        return False

    runs = response.json()["workflow_runs"]
    if runs:
        logger.error("There are workflows still running. Please wait for them to complete.")
        for run in runs:
            logger.error(f"- {run['name']} is running: {run['html_url']}")
        if not dry_run:
            sys.exit(1)
        return False

    # Get current commit hash
    current_commit, _ = run_command("git rev-parse HEAD", dry_run)
    logger.debug(f"Current commit hash: {current_commit}")

    # Then check completed workflows
    logger.debug("Checking completed workflows")
    response = requests.get(
        f"https://api.github.com/repos/{repo_url}/actions/runs",
        headers=headers,
        params={"branch": "main", "status": "completed", "per_page": 10},
    )

    if response.status_code != 200:
        logger.error(f"Error checking GitHub Actions status: {response.text}")
        if not dry_run:
            sys.exit(1)
        return False

    runs = response.json()["workflow_runs"]
    if not runs:
        logger.error("No recent workflow runs found. Please ensure workflows are running.")
        if not dry_run:
            sys.exit(1)
        return False

    # Check the most recent run for each workflow
    workflows = {}
    for run in runs:
        workflow_name = run["name"]
        if workflow_name not in workflows:
            workflows[workflow_name] = run

    # Define workflows that should be excluded from strict commit matching
    # These are typically scheduled workflows or external workflows
    excluded_workflows = {"Scheduled", "Dependabot"}

    # Define critical workflows that must pass and match current commit
    critical_workflows = {"CI", "E2E Test Orchestrator"}

    for workflow_name, run in workflows.items():
        if run["conclusion"] != "success":
            logger.error(f"Workflow '{workflow_name}' is not passing. Latest run status: {run['conclusion']}")
            logger.error(f"Please check the workflow run at: {run['html_url']}")
            if not dry_run:
                sys.exit(1)
            return False

        # Check if the workflow run matches our current commit
        # Skip this check for excluded workflows (like scheduled ones)
        if workflow_name in excluded_workflows:
            logger.debug(f"Skipping commit check for excluded workflow: {workflow_name}")
            continue

        if run["head_sha"] != current_commit:
            # For critical workflows, this is an error
            if workflow_name in critical_workflows:
                logger.error(
                    f"Critical workflow '{workflow_name}' was run on a different commit. "
                    "Please ensure it runs on the current commit."
                )
                logger.error(f"Current commit: {current_commit}")
                logger.error(f"Workflow commit: {run['head_sha']}")
                logger.error(f"Workflow run: {run['html_url']}")
                if not dry_run:
                    sys.exit(1)
                return False
            else:
                # For non-critical workflows, just log a warning
                logger.debug(f"Non-critical workflow '{workflow_name}' was run on a different commit (this is acceptable)")
                logger.debug(f"Current commit: {current_commit}")
                logger.debug(f"Workflow commit: {run['head_sha']}")

    logger.info("All critical workflows are passing and match the current commit")
    logger.info("GitHub workflows check completed successfully")
    return True


def calculate_new_version(current_version: str, bump_type: int, custom_version: str | None = None) -> str:
    """Calculate new version based on bump type."""
    if bump_type == 5 and custom_version is not None:
        # Validate custom version format
        import re

        version_pattern = r"^\d+\.\d+\.\d+(?:[ab]\d+|rc\d+)?$"
        if not re.match(version_pattern, custom_version):
            raise ValueError(
                f"Invalid version format: {custom_version}. "
                "Expected format: X.Y.Z, X.Y.Za<num>, X.Y.Zb<num>, or X.Y.Zrc<num>"
            )
        return custom_version

    # Handle pre-release versions by extracting base version
    base_version = current_version
    if "a" in current_version:
        base_version = current_version.split("a")[0]
    elif "b" in current_version:
        base_version = current_version.split("b")[0]
    elif "rc" in current_version:
        base_version = current_version.split("rc")[0]

    if bump_type == 1:  # Major
        major, minor, patch = map(int, base_version.split(".")[:3])
        return f"{major + 1}.0.0"
    elif bump_type == 2:  # Minor
        major, minor, patch = map(int, base_version.split(".")[:3])
        return f"{major}.{minor + 1}.0"
    elif bump_type == 3:  # Patch
        major, minor, patch = map(int, base_version.split(".")[:3])
        return f"{major}.{minor}.{patch + 1}"
    elif bump_type == 4:  # Pre-release
        if "a" in current_version:
            base_version, alpha_num = current_version.split("a")
            return f"{base_version}a{int(alpha_num) + 1}"
        elif "b" in current_version:
            base_version, beta_num = current_version.split("b")
            return f"{base_version}b{int(beta_num) + 1}"
        elif "rc" in current_version:
            base_version, rc_num = current_version.split("rc")
            return f"{base_version}rc{int(rc_num) + 1}"
        else:
            return f"{current_version}a1"

    return current_version


def get_development_status_classifier(version: str) -> str:
    """
    Determine the appropriate Development Status classifier based on version.

    Rules:
    - Any version with 'a' (alpha): "3 - Alpha"
    - Any version with 'b' (beta): "4 - Beta"
    - Any version with 'rc' (release candidate): "4 - Beta"
    - Everything else: "5 - Production/Stable"
    """
    logger = logging.getLogger(__name__)
    logger.debug(f"Determining development status for version: {version}")

    version_lower = version.lower()

    if "a" in version_lower:
        status = "Development Status :: 3 - Alpha"
        logger.debug(f"Alpha version detected: {status}")
        return status
    elif "b" in version_lower or "rc" in version_lower:
        status = "Development Status :: 4 - Beta"
        logger.debug(f"Beta/RC version detected: {status}")
        return status
    else:
        status = "Development Status :: 5 - Production/Stable"
        logger.debug(f"Stable version detected: {status}")
        return status


def update_development_status_classifier(version: str, dry_run: bool = False) -> None:
    """Update the Development Status classifier in pyproject.toml."""
    logger = logging.getLogger(__name__)
    pyproject_path = PACKAGE_CONFIG["pyproject_path"]

    # Determine the correct classifier
    new_classifier = get_development_status_classifier(version)

    if dry_run:
        logger.info(f"[DRY RUN] Would update Development Status classifier in {pyproject_path} to '{new_classifier}'")
        return

    logger.info(f"Updating Development Status classifier in {pyproject_path}")

    # Read current pyproject.toml
    with open(pyproject_path, "rb") as f:
        pyproject = tomli.load(f)

    # Update the classifier
    if "project" in pyproject and "classifiers" in pyproject["project"]:
        classifiers = pyproject["project"]["classifiers"]

        # Find and replace existing Development Status classifier
        updated = False
        for i, classifier in enumerate(classifiers):
            if classifier.startswith("Development Status ::"):
                old_classifier = classifier
                classifiers[i] = new_classifier
                updated = True
                logger.debug(f"Replaced '{old_classifier}' with '{new_classifier}'")
                break

        # If no Development Status classifier exists, add it
        if not updated:
            classifiers.insert(0, new_classifier)  # Add at the beginning
            logger.debug(f"Added new classifier: '{new_classifier}'")
    else:
        # Create classifiers section if it doesn't exist
        if "project" not in pyproject:
            pyproject["project"] = {}
        pyproject["project"]["classifiers"] = [new_classifier]
        logger.debug(f"Created new classifiers section with: '{new_classifier}'")

    # Write back to file
    with open(pyproject_path, "wb") as f:
        tomli_w.dump(pyproject, f)

    logger.debug("Development Status classifier updated successfully")


@command()
@option(
    "--dry-run",
    is_flag=True,
    help="Simulate the release process without making any changes",
)
@option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def release(dry_run: bool = False, verbose: bool = False):
    """Create a new release for PDF2Foundry.

    This script releases the CURRENT version, then bumps to the next development version.
    The process is: 1) Release current version 2) Bump to next version 3) Commit version bump.
    """
    # Setup logging
    logger = setup_logging(verbose)

    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")

    # Run initial safety checks
    initial_check_results = {}
    initial_check_results["git_status"] = check_git_status(dry_run)
    initial_check_results["current_branch"] = check_current_branch(dry_run)
    initial_check_results["unpushed_commits"] = check_unpushed_commits(dry_run)
    initial_check_results["main_up_to_date"] = check_main_up_to_date(dry_run)
    initial_check_results["github_workflows"] = check_github_workflows(dry_run)

    # In dry run mode, show summary of initial checks
    if dry_run:
        print("📋 INITIAL SAFETY CHECKS")
        print("─" * 50)

        failed_initial_checks = []
        for check_name, passed in initial_check_results.items():
            status = "✅" if passed else "❌"
            check_display_name = check_name.replace("_", " ").title()
            print(f"{status} {check_display_name}")
            if not passed:
                failed_initial_checks.append(check_display_name)

        if failed_initial_checks:
            print(f"\n⚠️  {len(failed_initial_checks)} issue(s) need to be fixed:")
            for check in failed_initial_checks:
                print(f"   • {check}")
            print("\n💡 Continuing to show what would happen after fixes...\n")
        else:
            print("\n✅ All initial checks passed!\n")
    else:
        # In real mode, exit if any initial check failed
        if not all(initial_check_results.values()):
            logger.error("One or more initial safety checks failed. Aborting release.")
            sys.exit(1)

    current_version = get_current_version()

    # Check if release notes have been updated for the CURRENT version (the one we're releasing)
    release_notes_check = check_release_notes_updated(current_version, dry_run)

    # Combine all check results
    all_check_results = initial_check_results.copy()
    all_check_results["release_notes_updated"] = release_notes_check

    # Display current version that will be released
    print(f"\n📦 RELEASING VERSION: {current_version}")
    print("─" * 40)

    # Show release notes check result
    if dry_run:
        print("\n📋 RELEASE NOTES CHECK")
        print("─" * 30)
        status = "✅" if release_notes_check else "❌"
        print(f"{status} Release Notes Updated for {current_version}")
        if not release_notes_check:
            print(f"   ⚠️  RELEASE_NOTES.md needs to be updated for version {current_version}")
        print()

    # Get next development version strategy
    print("\n🔢 NEXT DEVELOPMENT VERSION OPTIONS")
    print("─" * 45)
    print("After releasing the current version, what should the next development version be?")

    # Calculate and show actual version examples based on current version
    major_version = calculate_new_version(current_version, 1)
    minor_version = calculate_new_version(current_version, 2)
    patch_version = calculate_new_version(current_version, 3)
    prerelease_version = calculate_new_version(current_version, 4)

    print(f"1. Major ({current_version} → {major_version})")
    print(f"2. Minor ({current_version} → {minor_version})")
    print(f"3. Patch ({current_version} → {patch_version})")
    print(f"4. Pre-release ({current_version} → {prerelease_version})")
    print("5. Custom (specify exact version)")

    choice = prompt("Select next development version bump type", type=int)

    custom_version = None
    if choice == 5:
        print(f"\nCurrent version: {current_version}")
        print("Enter the next development version (format: X.Y.Z, X.Y.Za<num>, X.Y.Zb<num>, or X.Y.Zrc<num>)")
        print("Examples: 1.2.3, 0.5.0, 2.1.0a1, 1.0.0b2, 1.0.0rc1")

        while True:
            custom_version = prompt("Next development version").strip()
            if not custom_version:
                logger.error("Version cannot be empty")
                continue

            try:
                # Validate the version format using the same logic as calculate_new_version
                import re

                version_pattern = r"^\d+\.\d+\.\d+(?:[ab]\d+|rc\d+)?$"
                if not re.match(version_pattern, custom_version):
                    logger.error("Invalid version format. Expected format: X.Y.Z, X.Y.Za<num>, X.Y.Zb<num>, or X.Y.Zrc<num>")
                    continue
                break
            except Exception as e:
                logger.error(f"Invalid version: {e}")
                continue

    elif choice not in [1, 2, 3, 4]:
        logger.error("Invalid choice")
        sys.exit(1)

    # Calculate next development version
    try:
        next_dev_version = calculate_new_version(current_version, choice, custom_version)
    except ValueError as e:
        logger.error(f"Version calculation failed: {e}")
        sys.exit(1)

    # Ask for confirmation before proceeding further
    print("\n📋 RELEASE PLAN")
    print("─" * 20)
    print(f"1. Release current version: {current_version}")
    print(f"2. Bump to next development version: {next_dev_version}")

    if not confirm("Proceed with this release plan?", default=True):
        logger.error("Release aborted by user.")
        if dry_run:
            return
        sys.exit(1)

    if dry_run:
        print("\n🚀 PLANNED RELEASE ACTIONS")
        print("─" * 50)

        print("\n1️⃣  Create GitHub release for CURRENT version:")
        print(f"   • Release version: {current_version}")
        tag_name = f"v{current_version}"
        print(f"   • Create tag: {tag_name}")
        print("   • Push tag to GitHub")
        print(f"   • Create GitHub release: PDF2Foundry v{current_version}")

        print("\n2️⃣  Bump to NEXT development version:")
        print(f"   • Update pyproject.toml version: {current_version} → {next_dev_version}")

        # Show classifier updates
        current_classifier = get_development_status_classifier(current_version)
        next_classifier = get_development_status_classifier(next_dev_version)
        if current_classifier != next_classifier:
            print(f"   • Update classifier: {current_classifier} → {next_classifier}")
        else:
            print(f"   • Classifier: {next_classifier} (no change)")

        print("\n3️⃣  Commit and push version bump:")
        print("   • Stage updated pyproject.toml")
        print("   • Create commit: 'chore(release): bump to next development version'")
        print("   • Push to remote repository")

        print("\n" + "─" * 50)

        # Check all results including release notes
        all_failed_checks = []
        for check_name, passed in all_check_results.items():
            if not passed:
                check_display_name = check_name.replace("_", " ").title()
                all_failed_checks.append(check_display_name)

        if all_failed_checks:
            print("⚠️  NEXT STEPS")
            print(f"   Fix {len(all_failed_checks)} issue(s) before running the release:")
            for check in all_failed_checks:
                print(f"   • {check}")
            print("\n   Then run: python scripts/release.py")
        else:
            print("✅ READY TO RELEASE")
            print("   All checks passed! Run: python scripts/release.py")

        return

    # In real mode, exit if any check failed (including release notes)
    if not all(all_check_results.values()):
        logger.error("One or more safety checks failed. Aborting release.")
        sys.exit(1)

    # STEP 1: Create GitHub release for CURRENT version
    logger.info(f"Creating GitHub release for current version: {current_version}")

    # Create and push tag for CURRENT version
    tag_name = f"v{current_version}"
    run_command(f'git tag -a {tag_name} -m "Release PDF2Foundry v{current_version}"', dry_run)
    run_command("git push origin main --tags", dry_run)

    # Create GitHub release for CURRENT version
    token = get_github_token(dry_run)
    create_github_release(current_version, token, dry_run)

    # STEP 2: Bump to next development version
    logger.info(f"Bumping to next development version: {next_dev_version}")

    # Update version in pyproject.toml
    update_version(next_dev_version, dry_run)

    # Update Development Status classifier
    update_development_status_classifier(next_dev_version, dry_run)

    # Create commit with version bump
    run_command("git add pyproject.toml", dry_run)
    run_command('git commit -m "chore(release): bump to next development version"', dry_run)

    # Push the version bump commit to remote
    run_command("git push origin main", dry_run)

    print("\n🎉 RELEASE COMPLETED SUCCESSFULLY!")
    print("─" * 40)
    print(f"\n📦 Released version: v{current_version}")
    print(f"🔄 Next development version: {next_dev_version}")
    print("   Development Status classifier updated automatically")
    print("   Version bump committed and pushed to remote repository")


if __name__ == "__main__":
    release()
