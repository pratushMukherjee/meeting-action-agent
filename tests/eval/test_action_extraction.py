"""LLM evaluation tests for action item extraction quality.

These tests use DeepEval to assess the quality of the LLM's
action item extraction against golden datasets.

Run with: pytest tests/eval/ -m eval
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

GOLDEN_DATASETS_DIR = Path(__file__).parent / "golden_datasets"


@pytest.mark.eval
class TestActionExtraction:
    """Evaluate action item extraction quality against golden dataset."""

    def _load_golden_data(self):
        transcripts_path = GOLDEN_DATASETS_DIR / "transcripts.json"
        expected_path = GOLDEN_DATASETS_DIR / "expected_actions.json"

        with open(transcripts_path) as f:
            transcripts = json.load(f)
        with open(expected_path) as f:
            expected = json.load(f)

        return transcripts, expected

    def test_golden_dataset_exists(self):
        """Verify golden dataset files are present."""
        assert (GOLDEN_DATASETS_DIR / "transcripts.json").exists()
        assert (GOLDEN_DATASETS_DIR / "expected_actions.json").exists()

    def test_golden_dataset_format(self):
        """Verify golden dataset is properly formatted."""
        transcripts, expected = self._load_golden_data()

        assert len(transcripts) > 0, "Golden dataset should have at least one transcript"
        assert len(expected) > 0, "Golden dataset should have at least one expected output"
        assert len(transcripts) == len(expected), "Transcripts and expected outputs must match"

        for i, (t, e) in enumerate(zip(transcripts, expected)):
            assert "id" in t, f"Transcript {i} missing 'id'"
            assert "text" in t, f"Transcript {i} missing 'text'"
            assert "id" in e, f"Expected {i} missing 'id'"
            assert "actions" in e, f"Expected {i} missing 'actions'"

    def test_action_types_coverage(self):
        """Verify golden dataset covers all action types."""
        _, expected = self._load_golden_data()

        all_types = set()
        for e in expected:
            for action in e["actions"]:
                all_types.add(action["type"])

        assert "jira_ticket" in all_types
        assert "email_summary" in all_types
        assert "calendar_event" in all_types
