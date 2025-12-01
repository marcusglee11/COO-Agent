import pytest
from click.testing import CliRunner
from coo.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_demo_receipt_format(runner, tmp_path):
    db_path = tmp_path / "coo.db"
    
    result = runner.invoke(cli, ["--db-path", str(db_path), "run-demo"])
    assert result.exit_code == 0
    output = result.output
    
    # Check Prefix
    assert "[coo] Running deterministic demo mission ..." in output
    
    # Check Headings Order
    # We can check indices
    idx_mission = output.find("Mission")
    idx_input = output.find("Input")
    idx_summary = output.find("Summary (AI Output)")
    idx_det = output.find("Determinism")
    idx_inspect = output.find("Inspect")
    
    assert idx_mission != -1
    assert idx_input != -1
    assert idx_summary != -1
    assert idx_det != -1
    assert idx_inspect != -1
    
    assert idx_mission < idx_input < idx_summary < idx_det < idx_inspect
    
    # Check Mission Block ID format
    # Find line starting with "  ID: "
    lines = output.splitlines()
    id_line = next((line for line in lines if line.strip().startswith("ID: ")), None)
    assert id_line is not None
    # Verify it's not empty
    assert len(id_line.strip()) > 4
    
    # Check Determinism Sentence
    assert "This result is reproducible on this machine." in output
    
    # Check Inspect Block
    inspect_lines = [line.strip() for line in lines if line.strip().startswith("coo ")]
    # Should contain "coo mission ..." and "coo logs ..."
    assert any(l.startswith("coo mission ") for l in inspect_lines)
    assert any(l.startswith("coo logs ") for l in inspect_lines)
