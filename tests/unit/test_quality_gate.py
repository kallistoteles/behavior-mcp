"""A passing gate must not hide unimplemented behavior behind skipped tests."""

import os
import subprocess
import sys
from pathlib import Path


def test_skipped_tests_fail_the_required_quality_gate(tmp_path):
    root = Path(__file__).resolve().parents[2]
    sample = tmp_path / "test_skipped.py"
    sample.write_text(
        'import pytest\n@pytest.mark.skip(reason="not built")\ndef test_required_behavior(): pass\n'
    )
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "tests.conftest", str(sample)],
        cwd=tmp_path,
        env=dict(os.environ, PYTHONPATH=str(root)),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert "1 skipped" in result.stdout
    assert result.returncode != 0, (
        "Required quality checks cannot succeed through skipped tests"
    )
