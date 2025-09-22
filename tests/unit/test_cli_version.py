from __future__ import annotations

from typer.testing import CliRunner

from pdf2foundry import __version__
from pdf2foundry.cli import app


def test_cli_version_command_and_flag() -> None:
    runner = CliRunner()
    res1 = runner.invoke(app, ["version"])
    assert res1.exit_code == 0
    assert __version__ in res1.stdout

    res2 = runner.invoke(app, ["--version"])
    assert res2.exit_code == 0
    assert __version__ in res2.stdout
