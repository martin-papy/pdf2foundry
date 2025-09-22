import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


@pytest.fixture
def isolate_logging():
    """Isolate logging configuration between tests to prevent CI issues.

    This fixture prevents logging StreamHandler issues that occur in CI environments
    where stderr/stdout streams may be closed during test cleanup.

    Use this fixture explicitly in tests that have logging issues in CI.
    """
    # Store original logging state
    original_handlers = logging.root.handlers[:]
    original_level = logging.root.level

    # Clear all handlers to prevent stream access issues
    logging.root.handlers.clear()

    # Add a null handler that won't cause stream issues
    null_handler = logging.NullHandler()
    logging.root.addHandler(null_handler)

    yield

    # Restore original logging state
    logging.root.handlers.clear()
    logging.root.handlers.extend(original_handlers)
    logging.root.setLevel(original_level)
