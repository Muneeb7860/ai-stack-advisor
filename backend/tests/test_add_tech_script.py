"""
Tests for scripts/add_tech.py validation and authoring tool.
"""
import copy
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from add_tech import REQUIRED_FIELDS, VALID_DOMAINS, VALID_RINGS, validate_tech_entry


@pytest.fixture
def sample_valid_tech():
    return {
        "id": "test-logger",
        "name": "Test Logger",
        "category": "log-analytics",
        "domain": "observability",
        "surfaces": ["backend"],
        "maturity": {"ring": "adopt", "source_id": "twr34"},
        "hiring_pool": "medium",
        "hiring_source_id": "so2025",
        "license": "Apache-2.0",
        "hosting": ["self", "cloud"],
        "exit_cost": "low",
        "tco_shape": "eng-heavy",
        "best_when": ["lightweight structured logging"],
        "avoid_when": ["no logging needed"],
        "alternatives": ["otel"],
        "innovation_token_cost": 0,
        "signal_keywords": ["test logger", "test-log"],
    }


def test_validate_tech_entry_accepts_valid_entry(sample_valid_tech):
    errors = validate_tech_entry(sample_valid_tech, existing_ids=set())
    assert len(errors) == 0


def test_validate_tech_entry_rejects_duplicate_id(sample_valid_tech):
    errors = validate_tech_entry(sample_valid_tech, existing_ids={"test-logger"})
    assert any("already exists" in e for e in errors)


@pytest.mark.parametrize("missing_field", [
    "id",
    "name",
    "domain",
    "maturity",
    "best_when",
    "avoid_when",
    "signal_keywords",
    "innovation_token_cost",
])
def test_validate_tech_entry_rejects_missing_required_field(sample_valid_tech, missing_field):
    bad_entry = copy.deepcopy(sample_valid_tech)
    del bad_entry[missing_field]
    errors = validate_tech_entry(bad_entry, existing_ids=set())
    assert len(errors) > 0


def test_validate_tech_entry_rejects_invalid_domain(sample_valid_tech):
    bad_entry = copy.deepcopy(sample_valid_tech)
    bad_entry["domain"] = "invalid-domain-xyz"
    errors = validate_tech_entry(bad_entry, existing_ids=set())
    assert any("Invalid domain" in e for e in errors)


def test_validate_tech_entry_rejects_invalid_maturity_ring(sample_valid_tech):
    bad_entry = copy.deepcopy(sample_valid_tech)
    bad_entry["maturity"] = {"ring": "nonexistent-ring"}
    errors = validate_tech_entry(bad_entry, existing_ids=set())
    assert any("invalid maturity ring" in e.lower() or "must be an object with 'ring'" in e.lower() for e in errors)
