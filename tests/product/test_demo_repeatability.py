import pytest
import os
import shutil
from click.testing import CliRunner
from coo.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def clean_env(tmp_path):
    # Set up temporary DB path
    db_path = tmp_path / "coo.db"
    # Set up temporary demo output path
    demo_dir = tmp_path / "demo"
    return db_path, demo_dir

def test_demo_repeatability(runner, clean_env):
    db_path, demo_dir = clean_env
    
    # Run 1
    result1 = runner.invoke(cli, ["--db-path", str(db_path), "run-demo"])
    assert result1.exit_code == 0
    output1 = result1.output
    
    # Run 2
    result2 = runner.invoke(cli, ["--db-path", str(db_path), "run-demo"])
    assert result2.exit_code == 0
    output2 = result2.output
    
    # Helper to parse receipt
    def parse_receipt(output):
        sections = {}
        current_section = None
        lines = output.splitlines()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line == "Mission":
                current_section = "Mission"
                sections[current_section] = []
            elif line == "Summary (AI Output)":
                current_section = "AI Output"
                sections[current_section] = []
            elif line == "Determinism":
                current_section = "Determinism"
                sections[current_section] = []
            elif line == "Inspect":
                current_section = "Inspect"
                sections[current_section] = []
            elif current_section:
                sections[current_section].append(line)
                
        return sections

    receipt1 = parse_receipt(output1)
    receipt2 = parse_receipt(output2)
    
    # Assert AI Output is identical string
    assert "\n".join(receipt1["AI Output"]) == "\n".join(receipt2["AI Output"])
    
    # Assert Determinism block is identical
    assert "\n".join(receipt1["Determinism"]) == "\n".join(receipt2["Determinism"])
    
    # Assert Mission block matches EXCEPT ID and Timestamps
    # Mission block lines: ID, Type, Status, Started, Finished, Steps
    def normalize_mission_block(lines):
        normalized = []
        for line in lines:
            if line.startswith("ID:") or line.startswith("Started:") or line.startswith("Finished:"):
                continue
            normalized.append(line)
        return normalized
        
    assert normalize_mission_block(receipt1["Mission"]) == normalize_mission_block(receipt2["Mission"])
    
    # Inspect block will differ in IDs, so we check structure
    assert len(receipt1["Inspect"]) == 2
    assert receipt1["Inspect"][0].startswith("coo mission ")
    assert receipt1["Inspect"][1].startswith("coo logs ")
