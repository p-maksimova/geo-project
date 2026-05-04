import pytest
from fastapi.testclient import TestClient
from app import create_app


@pytest.fixture(scope="session")
def client():
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
