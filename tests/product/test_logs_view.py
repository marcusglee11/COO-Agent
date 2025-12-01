import pytest
import re
from click.testing import CliRunner
from coo.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_logs_view(runner, tmp_path):
    db_path = tmp_path / "coo.db"
    
    # Run demo to generate a mission
    result = runner.invoke(cli, ["--db-path", str(db_path), "run-demo"])
    assert result.exit_code == 0
    
    # Extract ID
    match = re.search(r"ID: ([a-f0-9\-]+)", result.output)
    assert match
    mission_id = match.group(1)
    
    # Run logs view
    result = runner.invoke(cli, ["--db-path", str(db_path), "logs", mission_id])
    assert result.exit_code == 0
    output = result.output
    
    lines = output.splitlines()
    assert len(lines) > 0
    
    # Verify format: [NNNN] STATE=...
    assert any("STATE=INIT" in line for line in lines)
    assert any("STATE=MODEL_REQUEST" in line for line in lines)
    assert any("STATE=MODEL_RESPONSE" in line for line in lines)
    assert any("STATE=COMPLETE" in line for line in lines)
    
    # Verify sorting (implied by sequence numbers)
    # Check that sequence numbers increase
    # Check that sequence numbers increase
    seq_nums = []
    for line in lines:
        m = re.match(r"\[(\d+)\]", line)
        if m:
            seq_nums.append(int(m.group(1)))
            
    assert seq_nums == sorted(seq_nums)
