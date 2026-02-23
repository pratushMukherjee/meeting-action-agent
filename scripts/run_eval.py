"""Run the LLM evaluation suite against the golden dataset."""

from __future__ import annotations

import subprocess
import sys


def main():
    """Run evaluation tests with detailed output."""
    print("Running Meeting Action Agent Evaluation Suite")
    print("=" * 50)

    result = subprocess.run(
        [
            sys.executable, "-m", "pytest",
            "tests/eval/",
            "-m", "eval",
            "-v",
            "--tb=short",
        ],
        cwd=str(__import__("pathlib").Path(__file__).parent.parent),
    )

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
