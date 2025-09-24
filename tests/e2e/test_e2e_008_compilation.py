"""E2E-008: Pack Compilation (Foundry CLI) Test.

This test validates Foundry CLI integration for compiling LevelDB packs from the
generated module and ensures resulting pack structure and installability signals are correct.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.pack_validation import expose_ci_artifacts, validate_pack_artifacts
from utils.validation import validate_module_json


@dataclass
class FoundryCLIInfo:
    """Information about resolved Foundry CLI command and capabilities."""

    command: list[str]
    input_flag: str
    output_flag: str
    supports_dry_run: bool = False
    version: str | None = None


@pytest.fixture(scope="session")
def resolve_foundry_cli() -> FoundryCLIInfo:
    """
    Resolve and validate Foundry CLI availability and capabilities.

    This fixture:
    1. Checks Node.js >= 20 availability
    2. Resolves CLI by preferring $FOUNDRY_CLI_CMD, else probing 'fvtt' then 'npx --yes @foundryvtt/foundry-cli'
    3. Runs '<cmd> --help' to confirm availability of 'package pack' and discover supported flags
    4. Returns structured CLI information or skips test if unavailable

    Returns:
        FoundryCLIInfo with command list and normalized flag mapping

    Raises:
        pytest.skip: If any precondition fails (Node.js, CLI availability, etc.)
    """
    # Check Node.js version >= 20
    try:
        result = subprocess.run(["node", "-v"], capture_output=True, text=True, timeout=10, check=True)
        node_version = result.stdout.strip()
        # Parse version (format: v20.x.x)
        if not node_version.startswith("v"):
            pytest.skip(f"Unexpected Node.js version format: {node_version}")

        major_version = int(node_version[1:].split(".")[0])
        if major_version < 20:
            pytest.skip(f"Node.js version {node_version} is below required v20.x.x")

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("Node.js not found or not accessible")
    except (ValueError, IndexError):
        pytest.skip(f"Could not parse Node.js version: {node_version}")

    # Resolve Foundry CLI command
    cli_candidates = []

    # 1. Check environment variable first
    if foundry_cli_cmd := os.getenv("FOUNDRY_CLI_CMD"):
        cli_candidates.append(foundry_cli_cmd.split())

    # 2. Try 'fvtt' binary
    if shutil.which("fvtt"):
        cli_candidates.append(["fvtt"])

    # 3. Try npx with Foundry CLI package
    if shutil.which("npx"):
        cli_candidates.append(["npx", "--yes", "@foundryvtt/foundryvtt-cli"])

    if not cli_candidates:
        pytest.skip("No Foundry CLI candidates found (no fvtt, npx, or FOUNDRY_CLI_CMD)")

    # Test each candidate to find a working one
    for candidate_cmd in cli_candidates:
        try:
            # Test basic help command
            help_result = subprocess.run([*candidate_cmd, "--help"], capture_output=True, text=True, timeout=30, check=True)

            help_output = help_result.stdout.lower()

            # Check if 'package pack' subcommand is available
            if "package" not in help_output or "pack" not in help_output:
                continue

            # Test package pack help to discover flags
            try:
                pack_help_result = subprocess.run(
                    [*candidate_cmd, "package", "pack", "--help"], capture_output=True, text=True, timeout=30, check=True
                )
                pack_help = pack_help_result.stdout.lower()

                # Determine input/output flag names for Foundry CLI
                input_flag = "--inputDirectory"
                output_flag = "--outputDirectory"

                # Check for short form flags
                if "--in" in pack_help:
                    input_flag = "--in"
                if "--out" in pack_help:
                    output_flag = "--out"

                # Check for dry-run support
                supports_dry_run = "--dry-run" in pack_help or "--dry" in pack_help

                # Try to get version info
                version = None
                try:
                    version_result = subprocess.run(
                        [*candidate_cmd, "--version"], capture_output=True, text=True, timeout=10, check=True
                    )
                    version = version_result.stdout.strip()
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    pass  # Version not critical

                return FoundryCLIInfo(
                    command=candidate_cmd,
                    input_flag=input_flag,
                    output_flag=output_flag,
                    supports_dry_run=supports_dry_run,
                    version=version,
                )

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue  # Try next candidate

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue  # Try next candidate

    pytest.skip("No working Foundry CLI found with 'package pack' support")


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.tier2
@pytest.mark.pack
@pytest.mark.slow
def test_pdf2foundry_pack_compilation(resolve_foundry_cli: FoundryCLIInfo, tmp_path: Path, fixtures_dir: Path) -> None:
    """
    Test PDF2Foundry CLI pack compilation with --compile-pack flag.

    This test:
    1. Runs PDF2Foundry convert with --compile-pack flag
    2. Validates that both sources and compiled packs are created
    3. Ensures proper LevelDB structure and non-empty content
    4. Tests the integration between PDF2Foundry and Foundry CLI

    Args:
        resolve_foundry_cli: Foundry CLI info (ensures CLI is available)
        tmp_path: Temporary directory for test isolation
        fixtures_dir: Directory containing test PDF fixtures
    """
    # Ensure Foundry CLI is available (this will skip if not)
    _ = resolve_foundry_cli  # Used for dependency injection/skipping

    # Get input fixture - use minimal PDF for faster testing
    try:
        input_pdf = fixtures_dir / "ci-minimal.pdf"
        if not input_pdf.exists():
            input_pdf = fixtures_dir / "basic.pdf"
        if not input_pdf.exists():
            pytest.skip("No suitable input PDF fixture found")
    except Exception:
        pytest.skip("Could not access PDF fixtures")

    # Set up output directory
    output_dir = tmp_path / "output"
    module_id = "test-pack-compilation"
    module_title = "Test Pack Compilation Module"

    # Run PDF2Foundry with --compile-pack flag
    cli_binary = os.getenv("PDF2FOUNDRY_CLI", "pdf2foundry")
    cmd = [
        cli_binary,
        "convert",
        str(input_pdf),
        "--mod-id",
        module_id,
        "--mod-title",
        module_title,
        "--out-dir",
        str(output_dir),
        "--compile-pack",  # This is what we're testing!
        "--no-toc",  # Faster generation
        "--tables",
        "image-only",  # Avoid complex table processing
    ]

    # Execute PDF2Foundry conversion with pack compilation
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes for conversion + compilation
            check=False,  # Don't raise on non-zero exit, we'll handle it
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"PDF2Foundry pack compilation timed out after 600s. Command: {' '.join(cmd)}")

    # Check for successful execution
    if result.returncode != 0:
        pytest.fail(
            f"PDF2Foundry pack compilation failed with exit code {result.returncode}\n"
            f"Command: {' '.join(cmd)}\n"
            f"Stdout: {result.stdout}\n"
            f"Stderr: {result.stderr}"
        )

    # Validate the generated module structure
    module_dir = output_dir / module_id
    assert module_dir.exists(), f"Module directory was not created: {module_dir}"

    # Validate that both sources AND packs were created
    sources_dir = module_dir / "sources"
    packs_dir = module_dir / "packs"

    assert sources_dir.exists(), f"Sources directory was not created: {sources_dir}"
    assert packs_dir.exists(), f"Packs directory was not created: {packs_dir}"

    # Validate pack artifacts were created and are valid
    validate_pack_artifacts(module_dir, packs_dir)

    # Expose artifacts for CI collection if in CI environment
    expose_ci_artifacts(packs_dir)


# Test for conversion without pack compilation (baseline)
@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.tier2
@pytest.mark.pack
def test_pdf2foundry_without_pack_compilation(
    resolve_foundry_cli: FoundryCLIInfo, tmp_path: Path, fixtures_dir: Path
) -> None:
    """
    Test PDF2Foundry CLI without --compile-pack flag (baseline test).

    This test validates that normal conversion works and that packs are NOT
    created when --compile-pack is not specified.

    Args:
        resolve_foundry_cli: Foundry CLI info (ensures CLI is available)
        tmp_path: Temporary directory for test isolation
        fixtures_dir: Directory containing test PDF fixtures
    """
    # Ensure Foundry CLI is available (this will skip if not)
    _ = resolve_foundry_cli  # Used for dependency injection/skipping

    # Get input fixture
    try:
        input_pdf = fixtures_dir / "ci-minimal.pdf"
        if not input_pdf.exists():
            input_pdf = fixtures_dir / "basic.pdf"
        if not input_pdf.exists():
            pytest.skip("No suitable input PDF fixture found")
    except Exception:
        pytest.skip("Could not access PDF fixtures")

    # Set up output directory
    output_dir = tmp_path / "output"
    module_id = "test-no-pack-compilation"
    module_title = "Test No Pack Compilation Module"

    # Run PDF2Foundry WITHOUT --compile-pack flag
    cli_binary = os.getenv("PDF2FOUNDRY_CLI", "pdf2foundry")
    cmd = [
        cli_binary,
        "convert",
        str(input_pdf),
        "--mod-id",
        module_id,
        "--mod-title",
        module_title,
        "--out-dir",
        str(output_dir),
        # Note: NO --compile-pack flag
        "--no-toc",  # Faster generation
        "--tables",
        "image-only",  # Avoid complex table processing
    ]

    # Execute PDF2Foundry conversion without pack compilation
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes should be enough
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"PDF2Foundry conversion timed out after 300s. Command: {' '.join(cmd)}")

    # Check for successful execution
    if result.returncode != 0:
        pytest.fail(
            f"PDF2Foundry conversion failed with exit code {result.returncode}\n"
            f"Command: {' '.join(cmd)}\n"
            f"Stdout: {result.stdout}\n"
            f"Stderr: {result.stderr}"
        )

    # Validate the generated module structure
    module_dir = output_dir / module_id
    assert module_dir.exists(), f"Module directory was not created: {module_dir}"

    # Validate that sources were created but packs are empty
    sources_dir = module_dir / "sources"
    packs_dir = module_dir / "packs"

    assert sources_dir.exists(), f"Sources directory was not created: {sources_dir}"

    # The packs directory may exist but should be empty (no compiled packs)
    if packs_dir.exists():
        pack_contents = list(packs_dir.iterdir())
        # Allow the pack directory structure to exist but it should be empty or contain only empty directories
        for item in pack_contents:
            if item.is_dir():
                # Check if the pack directory is empty (no LevelDB files)
                pack_files = list(item.iterdir())
                assert not pack_files, f"Pack directory should be empty without --compile-pack: {item} contains {pack_files}"
            else:
                # No files should exist at the packs level
                raise AssertionError(f"Unexpected file in packs directory without --compile-pack: {item}")

    # Validate module.json exists and is valid
    module_json_path = module_dir / "module.json"
    assert module_json_path.exists(), f"Module.json was not created: {module_json_path}"

    validation_errors = validate_module_json(module_json_path)
    assert not validation_errors, f"Module.json validation failed: {validation_errors}"


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.tier2
@pytest.mark.pack
@pytest.mark.slow
def test_pdf2foundry_nightly_full_run(resolve_foundry_cli: FoundryCLIInfo, tmp_path: Path, fixtures_dir: Path) -> None:
    """
    Full nightly test run with comprehensive PDF2Foundry pack compilation.

    This test is designed to run in CI nightly builds and provides
    comprehensive logging and artifact exposure for manual verification.
    Uses a more complex PDF and additional options for thorough testing.

    Args:
        resolve_foundry_cli: Foundry CLI information and capabilities
        tmp_path: Temporary directory for test isolation
        fixtures_dir: Directory containing test PDF fixtures
    """
    # Skip if not in nightly CI environment
    if not (os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("CI_NIGHTLY") == "true"):
        pytest.skip("Nightly test only runs in CI nightly environment")

    cli_info = resolve_foundry_cli

    print("\n=== NIGHTLY PDF2FOUNDRY PACK COMPILATION TEST ===")
    print(f"Foundry CLI: {' '.join(cli_info.command)}")
    print(f"Version: {cli_info.version or 'Unknown'}")
    print(f"Input flag: {cli_info.input_flag}")
    print(f"Output flag: {cli_info.output_flag}")
    print(f"Supports dry-run: {cli_info.supports_dry_run}")

    # Get input fixture - use more comprehensive PDF for nightly testing
    try:
        input_pdf = fixtures_dir / "comprehensive-manual.pdf"
        if not input_pdf.exists():
            input_pdf = fixtures_dir / "basic.pdf"
        if not input_pdf.exists():
            pytest.skip("No suitable input PDF fixture found for nightly testing")
    except Exception:
        pytest.skip("Could not access PDF fixtures for nightly testing")

    print(f"Input PDF: {input_pdf}")

    # Set up output directory
    output_dir = tmp_path / "output"
    module_id = "nightly-pack-test"
    module_title = "Nightly Pack Compilation Test"

    # Run PDF2Foundry with --compile-pack and comprehensive options
    cli_binary = os.getenv("PDF2FOUNDRY_CLI", "pdf2foundry")
    cmd = [
        cli_binary,
        "convert",
        str(input_pdf),
        "--mod-id",
        module_id,
        "--mod-title",
        module_title,
        "--out-dir",
        str(output_dir),
        "--compile-pack",  # This is what we're testing!
        "--toc",  # Include TOC for comprehensive test
        "--tables",
        "auto",  # Test table processing
        "--verbose",
        "-v",  # Verbose logging for nightly
    ]

    print(f"Executing command: {' '.join(cmd)}")

    # Execute PDF2Foundry conversion with pack compilation
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1200,  # 20 minutes for comprehensive nightly run
            check=False,
        )

        print(f"Command completed with exit code: {result.returncode}")
        if result.stdout:
            print(f"Stdout:\n{result.stdout}")
        if result.stderr:
            print(f"Stderr:\n{result.stderr}")

    except subprocess.TimeoutExpired:
        pytest.fail(f"Nightly PDF2Foundry pack compilation timed out after 1200s. Command: {' '.join(cmd)}")

    # Check for successful execution
    if result.returncode != 0:
        pytest.fail(
            f"Nightly PDF2Foundry pack compilation failed with exit code {result.returncode}\n"
            f"Command: {' '.join(cmd)}\n"
            f"Stdout: {result.stdout}\n"
            f"Stderr: {result.stderr}"
        )

    # Validate the generated module structure
    module_dir = output_dir / module_id
    assert module_dir.exists(), f"Module directory was not created: {module_dir}"

    # Validate that both sources AND packs were created
    sources_dir = module_dir / "sources"
    packs_dir = module_dir / "packs"

    assert sources_dir.exists(), f"Sources directory was not created: {sources_dir}"
    assert packs_dir.exists(), f"Packs directory was not created: {packs_dir}"

    print(f"Module directory: {module_dir}")
    print(f"Sources directory: {sources_dir}")
    print(f"Packs directory: {packs_dir}")

    # Validate pack artifacts
    validate_pack_artifacts(module_dir, packs_dir)

    # Expose artifacts for CI collection
    expose_ci_artifacts(packs_dir)

    print("=== NIGHTLY TEST COMPLETED SUCCESSFULLY ===\n")
