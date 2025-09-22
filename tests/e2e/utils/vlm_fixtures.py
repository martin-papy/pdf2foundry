"""VLM test fixtures and setup utilities.

This module contains pytest fixtures and setup utilities for VLM E2E testing.
"""

import os
from pathlib import Path

import pytest

from .vlm_test_helpers import choose_fixture


@pytest.fixture(scope="session")
def hf_cache_dir(tmp_path_factory) -> Path:
    """Create a session-scoped Hugging Face cache directory."""
    cache_dir = tmp_path_factory.mktemp("hf_cache")
    return cache_dir


@pytest.fixture
def vlm_env(hf_cache_dir: Path) -> dict[str, str]:
    """Prepare environment variables for VLM testing."""
    env = {
        "HF_HOME": str(hf_cache_dir),
    }

    # Pass through HF_TOKEN if available
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        env["HF_TOKEN"] = hf_token

    return env


@pytest.fixture
def test_fixture(fixtures_dir: Path) -> Path:
    """Get the best available fixture for VLM testing."""
    return choose_fixture(fixtures_dir)
