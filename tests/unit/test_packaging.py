from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pdf2foundry.builder.packaging import PackCompileError, _resolve_foundry_cli, compile_pack


def test_compile_pack_builds_command_and_handles_missing_sources(tmp_path: Path) -> None:
    module_dir = tmp_path / "mod"
    module_dir.mkdir()
    # no sources yet
    with pytest.raises(PackCompileError):
        compile_pack(module_dir, "p")


def test_compile_pack_invokes_npx(monkeypatch: Any, tmp_path: Path) -> None:
    module_dir = tmp_path / "mod"
    src = module_dir / "sources" / "journals"
    # output path created implicitly by compile
    src.mkdir(parents=True)

    called: dict[str, Any] = {}

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, cwd: Path | None = None) -> Any:
        called["cmd"] = cmd
        # Read the script the packaging wrote to disk for assertions
        try:
            script_path = Path(cmd[1]) if len(cmd) > 1 else None
            if script_path and script_path.exists():
                called["js"] = script_path.read_text(encoding="utf-8")
        except Exception:
            pass

        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    compile_pack(module_dir, "pack")

    # Using a file-based Node script to avoid quoting issues
    assert called["cmd"][0] == "node"
    assert called["cmd"][1].endswith("__compile_pack.js")
    js = called.get("js", "")
    assert "compilePack(" in js and "@foundryvtt/foundryvtt-cli" in js


def test_compile_pack_surfaces_cli_error(monkeypatch: Any, tmp_path: Path) -> None:
    module_dir = tmp_path / "mod"
    src = module_dir / "sources" / "journals"
    src.mkdir(parents=True)

    class E(subprocess.CalledProcessError):
        pass

    def fake_run(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.CalledProcessError(1, ["npx"], "", "boom")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(PackCompileError):
        compile_pack(module_dir, "pack")


# Tests for Foundry CLI resolution strategies


def test_resolve_foundry_cli_local_project(tmp_path: Path) -> None:
    """Test Strategy 1: Local project node_modules detection."""
    # Create a mock project structure
    project_root = tmp_path / "project"
    package_json = project_root / "package.json"
    foundry_cli = project_root / "node_modules" / "@foundryvtt" / "foundryvtt-cli"

    package_json.parent.mkdir(parents=True)
    foundry_cli.parent.mkdir(parents=True)
    package_json.write_text('{"name": "test"}')
    foundry_cli.write_text("module content")

    # Mock __file__ to be inside the project
    mock_file = project_root / "src" / "pdf2foundry" / "builder" / "packaging.py"
    mock_file.parent.mkdir(parents=True)

    with patch("pdf2foundry.builder.packaging.__file__", str(mock_file)):
        require_path, working_dir = _resolve_foundry_cli()

    # Should find local installation
    expected_path = str(foundry_cli).replace("\\", "/")
    assert require_path == expected_path
    assert working_dir == project_root


def test_resolve_foundry_cli_global_installation() -> None:
    """Test Strategy 2: Global npm installation detection."""
    mock_global_path = "/usr/local/lib/node_modules/@foundryvtt/foundryvtt-cli/index.mjs"

    # Mock no local project (no package.json found)
    with (
        patch("pdf2foundry.builder.packaging.__file__", "/some/random/path/packaging.py"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value.stdout = mock_global_path
        mock_run.return_value.returncode = 0

        require_path, working_dir = _resolve_foundry_cli()

    # Should find global installation
    assert require_path == mock_global_path.replace("\\", "/")
    assert working_dir is None  # No specific working directory needed


def test_resolve_foundry_cli_fallback_to_package_name() -> None:
    """Test Strategy 3: Fallback to package name resolution."""
    # Mock no local project and failed global resolution
    with (
        patch("pdf2foundry.builder.packaging.__file__", "/some/random/path/packaging.py"),
        patch("subprocess.run") as mock_run,
    ):
        # Simulate subprocess failure (global resolution fails)
        mock_run.side_effect = subprocess.CalledProcessError(1, ["node"])

        require_path, working_dir = _resolve_foundry_cli()

    # Should fallback to package name
    assert require_path == "@foundryvtt/foundryvtt-cli"
    assert working_dir is None


def test_resolve_foundry_cli_subprocess_timeout() -> None:
    """Test Strategy 2 with subprocess timeout fallback."""
    # Mock no local project
    with (
        patch("pdf2foundry.builder.packaging.__file__", "/some/random/path/packaging.py"),
        patch("subprocess.run") as mock_run,
    ):
        # Simulate subprocess timeout
        mock_run.side_effect = subprocess.TimeoutExpired(["node"], 10)

        require_path, working_dir = _resolve_foundry_cli()

    # Should fallback to package name
    assert require_path == "@foundryvtt/foundryvtt-cli"
    assert working_dir is None


def test_resolve_foundry_cli_node_not_found() -> None:
    """Test Strategy 2 with Node.js not found fallback."""
    # Mock no local project
    with (
        patch("pdf2foundry.builder.packaging.__file__", "/some/random/path/packaging.py"),
        patch("subprocess.run") as mock_run,
    ):
        # Simulate Node.js not found
        mock_run.side_effect = FileNotFoundError("node not found")

        require_path, working_dir = _resolve_foundry_cli()

    # Should fallback to package name
    assert require_path == "@foundryvtt/foundryvtt-cli"
    assert working_dir is None


def test_compile_pack_uses_resolved_cli_path(monkeypatch: Any, tmp_path: Path) -> None:
    """Test that compile_pack uses the resolved CLI path and working directory."""
    module_dir = tmp_path / "mod"
    src = module_dir / "sources" / "journals"
    src.mkdir(parents=True)

    # Mock CLI resolution to return specific path and working directory
    mock_cli_path = "/custom/path/to/foundryvtt-cli"
    mock_working_dir = tmp_path / "custom_project"
    mock_working_dir.mkdir()

    called: dict[str, Any] = {}

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, cwd: Path | None = None) -> Any:
        called["cmd"] = cmd
        called["cwd"] = cwd
        # Read the script content
        try:
            script_path = Path(cmd[1]) if len(cmd) > 1 else None
            if script_path and script_path.exists():
                called["js"] = script_path.read_text(encoding="utf-8")
        except Exception:
            pass

        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return R()

    def mock_resolve_cli() -> tuple[str, Path | None]:
        return mock_cli_path, mock_working_dir

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("pdf2foundry.builder.packaging._resolve_foundry_cli", mock_resolve_cli)

    compile_pack(module_dir, "pack")

    # Verify the resolved CLI path is used in the script
    js = called.get("js", "")
    assert mock_cli_path in js

    # Verify the working directory is passed to subprocess.run
    assert called["cwd"] == mock_working_dir


def test_compile_pack_handles_cli_resolution_failure(monkeypatch: Any, tmp_path: Path) -> None:
    """Test that compile_pack handles CLI resolution failures gracefully."""
    module_dir = tmp_path / "mod"
    src = module_dir / "sources" / "journals"
    src.mkdir(parents=True)

    def mock_resolve_cli_failure() -> tuple[str, Path | None]:
        raise RuntimeError("CLI resolution failed")

    monkeypatch.setattr("pdf2foundry.builder.packaging._resolve_foundry_cli", mock_resolve_cli_failure)

    with pytest.raises(PackCompileError) as exc_info:
        compile_pack(module_dir, "pack")

    # Should wrap the resolution error with helpful message
    assert "Failed to resolve Foundry CLI installation" in str(exc_info.value)
    assert "npm install -g @foundryvtt/foundryvtt-cli" in str(exc_info.value)
