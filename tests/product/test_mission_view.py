import pytest
import re
from click.testing import CliRunner
from coo.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_mission_view(runner, tmp_path):
    db_path = tmp_path / "coo.db"
    
    # Run demo to generate a mission
    result = runner.invoke(cli, ["--db-path", str(db_path), "run-demo"])
    assert result.exit_code == 0
    
    # Extract ID
    # ID: <UUID>
    match = re.search(r"ID: ([a-f0-9\-]+)", result.output)
    assert match
    mission_id = match.group(1)
    
    # Run mission view
    result = runner.invoke(cli, ["--db-path", str(db_path), "mission", mission_id])
    assert result.exit_code == 0
    output = result.output
    
    # Verify Header
    assert f"Mission {mission_id}" in output
    assert "Type: DEMO_V1_1" in output
    assert "Status: COMPLETED" in output
    
    # Verify Timeline
    assert "Timeline" in output
    # Check for #0001
    assert "  #0001 INIT" in output
    assert "  #0002 MODEL_REQUEST" in output
    assert "  #0003 MODEL_RESPONSE" in output
    assert "  #0004 COMPLETE" in output
