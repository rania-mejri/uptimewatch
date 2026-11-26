import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["API_KEY"] = "test-key"

import httpx
from fastapi.testclient import TestClient

from app.checker import check_one
from app.main import app
from app.models import Monitor

HEADERS = {"X-API-Key": "test-key"}
EXAMPLE = {"name": "Exemple", "url": "https://example.com"}


def test_health():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_create_requires_api_key():
    with TestClient(app) as client:
        r = client.post("/monitors", json=EXAMPLE)
        assert r.status_code == 401


def test_create_and_list_monitor():
    with TestClient(app) as client:
        r = client.post("/monitors", json=EXAMPLE, headers=HEADERS)
        assert r.status_code == 201
        ids = [m["id"] for m in client.get("/monitors").json()]
        assert r.json()["id"] in ids


def test_invalid_url_is_rejected():
    with TestClient(app) as client:
        bad = {"name": "x", "url": "pas-une-url"}
        r = client.post("/monitors", json=bad, headers=HEADERS)
        assert r.status_code == 422


def test_check_one_up_and_down():
    monitor = Monitor(id=1, name="t", url="https://example.com")
    for code, expected in [(200, True), (503, False)]:

        def handler(request, c=code):
            return httpx.Response(c)

        transport = httpx.MockTransport(handler)
        with httpx.Client(transport=transport) as client:
            check, _ = check_one(client, monitor)
        assert check.is_up is expected
