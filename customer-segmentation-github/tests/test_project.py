"""Smoke tests using the committed starter dataset."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class StarterDatasetTests(unittest.TestCase):
    def run_script(self, script: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [PYTHON, str(ROOT / "src" / script), "--dir", str(ROOT / "starter")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_validation_passes(self):
        result = self.run_script("validate_data.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS 187", result.stdout)
        self.assertIn("FAIL 0", result.stdout)

    def test_evaluation_runs(self):
        result = self.run_script("evaluate_actions.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CHAMPIONS", result.stdout)
        self.assertIn("marketing_sends", result.stdout)


if __name__ == "__main__":
    unittest.main()
