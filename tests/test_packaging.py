from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from pdf2foundry.builder.packaging import PackCompileError, compile_pack


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

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool) -> Any:
        called["cmd"] = cmd

        class R:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    compile_pack(module_dir, "pack")

    # Using Node API via -e script
    assert called["cmd"][0:2] == ["node", "-e"]
    js = called["cmd"][2]
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
