"""
Pytest configuration and fixtures for VB_Converter.
"""

import os
import pytest
from fastapi.testclient import TestClient

# Set test environment before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"

from hienfeld_api.app import app


@pytest.fixture(scope="session")
def client():
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_policy_text():
    """Sample policy text for tests."""
    return "Dekking voor schade aan het motorrijtuig is meeverzekerd conform artikel 5."


@pytest.fixture
def sample_conditions_text():
    """Sample conditions text for tests."""
    return """
    Artikel 5 - Dekking motorrijtuigen
    Wij verzekeren schade aan het motorrijtuig volgens de voorwaarden van deze polis.
    """
