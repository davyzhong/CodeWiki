from typer.main import get_command
from typer.testing import CliRunner

from knowledge_compiler.spikes.main import app


def test_cli_exposes_run_subcommand() -> None:
    assert "run" in get_command(app).commands
    result = CliRunner().invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "--repo-template" in result.stdout
