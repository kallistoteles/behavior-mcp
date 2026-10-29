"""The recorder must isolate feature evidence, including repeated task IDs."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

RECORDER = Path(__file__).resolve().parents[2] / "scripts/record-test"


@pytest.mark.parametrize("explicit", [False, True])
def test_recorder_paths_and_history(tmp_path, explicit):
    feature = "specs/002-remaining-behavior-models"
    other = tmp_path / "specs/001-agent-native-systems/evidence/tdd/T001.json"
    other.parent.mkdir(parents=True)
    other.write_text('{"sentinel": true}\n')
    prefix = [sys.executable, str(RECORDER)]
    if explicit:
        prefix += ["--feature-dir", feature]
    for phase, code in [("red", 7), ("red", 8), ("green", 0), ("green", 0)]:
        run = subprocess.run(
            [*prefix, "T001", phase, sys.executable, "-c", f"raise SystemExit({code})"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert run.returncode == 0, run.stderr
    destination = tmp_path / (feature if explicit else "specs/001-agent-native-systems")
    record = json.loads((destination / "evidence/tdd/T001.json").read_text())
    assert record["red"]["exit_code"] == 8
    assert record["red_history"][0]["exit_code"] == 7
    assert record["green_history"][0]["exit_code"] == 0
    if explicit:
        assert json.loads(other.read_text()) == {"sentinel": True}
