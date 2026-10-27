"""
Tests for scripts/verify_persistence.py (TASK-P1-09E).
Validates that persistence marker seeding, verification, and cleanup logic
executes properly and handles both present and missing state.
"""
import os
import pytest
from scripts.verify_persistence import (
    seed_persistence_marker,
    verify_persistence_marker,
    MARKER_BHUMI_ID,
    MARKER_STORAGE_FILE
)


from tests.conftest import TEST_DATABASE_URL


def test_verify_persistence_lifecycle(db_session, monkeypatch):
    """Verifies that seed and verify functions execute and clean up cleanly."""
    # Ensure storage points to a local directory for test and database points to test db
    monkeypatch.setenv("STORAGE_ADAPTER", "local")
    monkeypatch.setattr("scripts.verify_persistence.settings.DATABASE_URL", TEST_DATABASE_URL)

    # 1. Seed state
    seed_success = seed_persistence_marker()
    assert seed_success is True

    # 2. Verify state and cleanup
    verify_success = verify_persistence_marker()
    assert verify_success is True


def test_verify_persistence_fails_when_marker_missing(monkeypatch):
    """Verifies that verify_persistence_marker returns False when markers are absent."""
    monkeypatch.setenv("STORAGE_ADAPTER", "local")
    monkeypatch.setattr("scripts.verify_persistence.settings.DATABASE_URL", TEST_DATABASE_URL)

    # Calling verify without seeding should detect missing marker and return False
    res = verify_persistence_marker()
    assert res is False

