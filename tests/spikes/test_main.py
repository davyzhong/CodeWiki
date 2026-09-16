from typer.main import get_command
from typer.testing import CliRunner

from knowledge_compiler.spikes.main import app


def test_cli_exposes_run_subcommand() -> None:
    import re

    assert "run" in get_command(app).commands
    result = CliRunner().invoke(
        app, ["run", "--help"], env={"COLUMNS": "220"}
    )

    assert result.exit_code == 0
    # Rich wraps/truncates help to the terminal width; force a wide
    # render and collapse whitespace so CI terminals cannot break this.
    flattened = re.sub(r"\s+", "", result.stdout)
    assert "--repo-template" in flattened
