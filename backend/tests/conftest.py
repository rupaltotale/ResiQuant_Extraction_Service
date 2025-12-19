import os
import sys
import pathlib
import pytest

# Ensure backend directory is on sys.path for reliable imports
_HERE = pathlib.Path(__file__).resolve().parent
_BACKEND_DIR = _HERE.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    # Ensure tests control whether LLM runs by setting API key explicitly
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    yield


@pytest.fixture()
def app():
    from app import app as flask_app
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
