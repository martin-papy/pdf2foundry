"""Pack compilation validation utilities for E2E tests."""

import json
import os
from pathlib import Path


def validate_pack_artifacts(module_dir: Path, packs_dir: Path) -> None:
    """
    Validate that pack artifacts are properly created and structured.

    Args:
        module_dir: Path to the module directory
        packs_dir: Path to the packs directory

    Raises:
        AssertionError: If validation fails
    """
    # Check packs directory exists and is non-empty
    assert packs_dir.exists(), f"Packs directory was not created: {packs_dir}"
    assert packs_dir.is_dir(), f"Packs path is not a directory: {packs_dir}"

    pack_contents = list(packs_dir.iterdir())
    assert pack_contents, f"Packs directory is empty: {packs_dir}"

    # Load module.json to check pack declarations
    module_json_path = module_dir / "module.json"
    assert module_json_path.exists(), f"Module.json not found: {module_json_path}"

    with module_json_path.open() as f:
        module_data = json.load(f)

    # Validate each declared pack exists
    packs_config = module_data.get("packs", [])
    assert packs_config, "No packs declared in module.json"

    for pack_config in packs_config:
        pack_name = pack_config.get("name")
        pack_path = pack_config.get("path")
        pack_type = pack_config.get("type")

        assert pack_name, f"Pack missing name: {pack_config}"
        assert pack_path, f"Pack missing path: {pack_config}"
        assert pack_type, f"Pack missing type: {pack_config}"

        # Check pack path is relative and uses forward slashes
        assert not Path(pack_path).is_absolute(), f"Pack path should be relative: {pack_path}"
        assert "/" in pack_path or "\\" not in pack_path, f"Pack path should use forward slashes: {pack_path}"

        # Check actual pack file/directory exists
        # The pack_path in module.json is relative to module root, but we create it under packs/
        actual_pack_path = packs_dir / pack_name
        assert actual_pack_path.exists(), f"Pack not found at expected path: {actual_pack_path}"

        # Validate pack structure based on type
        if actual_pack_path.is_dir():
            # LevelDB directory format
            validate_leveldb_pack(actual_pack_path, pack_name)
        else:
            # Legacy .db file format
            validate_legacy_pack_file(actual_pack_path, pack_name)


def validate_leveldb_pack(pack_dir: Path, pack_name: str) -> None:
    """
    Validate LevelDB pack directory structure.

    Args:
        pack_dir: Path to the LevelDB pack directory
        pack_name: Name of the pack for error messages
    """
    # Check for LevelDB sentinel files
    leveldb_files = ["CURRENT", "LOCK", "LOG"]
    manifest_files = list(pack_dir.glob("MANIFEST-*"))
    sst_files = list(pack_dir.glob("*.sst")) + list(pack_dir.glob("*.ldb"))

    found_files = []
    for sentinel_file in leveldb_files:
        if (pack_dir / sentinel_file).exists():
            found_files.append(sentinel_file)

    if manifest_files:
        found_files.extend([f.name for f in manifest_files])

    if sst_files:
        found_files.extend([f.name for f in sst_files])

    # Debug information for CI
    if not found_files:
        print(f"DEBUG: Pack directory contents for {pack_name}: {list(pack_dir.iterdir())}")
        for item in pack_dir.iterdir():
            if item.is_file():
                print(f"  File: {item.name} ({item.stat().st_size} bytes)")
            else:
                print(f"  Directory: {item.name}/")

        # Check parent directory structure for more context
        parent_dir = pack_dir.parent
        print(f"DEBUG: Parent directory ({parent_dir}) contents: {list(parent_dir.iterdir())}")

        # Check if pack_dir actually exists and is a directory
        print(f"DEBUG: Pack directory exists: {pack_dir.exists()}")
        print(f"DEBUG: Pack directory is dir: {pack_dir.is_dir()}")

    # If pack directory is empty, this might be a Foundry CLI issue
    # Let's be more lenient and check if the directory at least exists
    if not pack_dir.exists():
        raise AssertionError(f"Pack directory does not exist: {pack_dir}")

    if not pack_dir.is_dir():
        raise AssertionError(f"Pack path is not a directory: {pack_dir}")

    # If directory exists but is empty, this indicates pack compilation failed
    if not list(pack_dir.iterdir()):
        raise AssertionError(f"Pack directory is empty - pack compilation failed: {pack_dir}")

    assert found_files, f"No LevelDB sentinel files found in pack {pack_name}: {pack_dir}"

    # Check that files are non-empty (basic sanity check)
    for file_path in pack_dir.iterdir():
        if (
            file_path.is_file()
            and file_path.stat().st_size == 0
            and file_path.name not in ["LOCK"]
            and not file_path.name.endswith(".log")
        ):
            # Allow some files to be empty (like LOCK and log files)
            raise AssertionError(f"Pack file {file_path.name} in {pack_name} is empty")


def validate_legacy_pack_file(pack_file: Path, pack_name: str) -> None:
    """
    Validate legacy .db pack file.

    Args:
        pack_file: Path to the .db pack file
        pack_name: Name of the pack for error messages
    """
    assert pack_file.stat().st_size > 0, f"Legacy pack file {pack_name} is empty: {pack_file}"


def expose_ci_artifacts(packs_dir: Path) -> None:
    """
    Expose pack artifacts for CI artifact collection when running in GitHub Actions.

    This function prints the packs directory path and contents for CI systems
    to potentially collect as build artifacts for manual testing.

    Args:
        packs_dir: Path to the packs directory to expose
    """
    if not (os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("CI") == "true"):
        return

    print("\n=== CI ARTIFACT EXPOSURE ===")
    print(f"Packs directory: {packs_dir}")

    if packs_dir.exists():
        print("Pack contents:")
        for item in packs_dir.rglob("*"):
            if item.is_file():
                size = item.stat().st_size
                print(f"  {item.relative_to(packs_dir)} ({size} bytes)")
            else:
                print(f"  {item.relative_to(packs_dir)}/")
    else:
        print("Packs directory does not exist")

    print("=== END CI ARTIFACT EXPOSURE ===\n")
