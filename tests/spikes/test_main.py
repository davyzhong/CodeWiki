from typer.main import get_command
from typer.testing import CliRunner

from knowledge_compiler.spikes.main import app


def test_cli_exposes_run_subcommand() -> None:
    # Assert against command metadata, not rendered help: rich's layout
    # varies with terminal width and library version; the option set is
    # the actual contract.
    command = get_command(app).commands["run"]
    result = CliRunner().invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    params = {param.name for param in command.params}
    assert "repo_template" in params
