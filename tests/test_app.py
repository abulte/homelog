import os

from pathlib import Path

import pytest

from flask import url_for

from homelog import database
from homelog.app import app as flask_app


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    # don't use :memory: because we don't have a db singleton
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    yield
    if (db_path := Path("test.db")).exists():
        db_path.unlink()


@pytest.fixture
def app():
    return flask_app


def post_measurement(client, custom_headers=None, **kwargs):
    default_headers = {"x-api-key": os.getenv("HOMELOG_API_KEY")}
    headers = custom_headers if custom_headers is not None else default_headers
    kwargs["headers"] = headers
    return client.post(url_for("api_model", model="test_model"), **kwargs)


def test_api_model(client):
    # forget auth
    r = post_measurement(client, custom_headers={})
    assert r.status_code == 401

    # send no json
    r = post_measurement(client)
    assert r.status_code == 415

    # send malformed json
    r = post_measurement(client, json={})
    assert r.status_code == 400
    assert r.json == {"error": "No JSON data"}

    # send invalid value
    r = post_measurement(client, json={"measurement": "str"})
    assert r.status_code == 400
    assert "NOT_FLOATABLE" in r.json["error"]

    # send valid value
    r = post_measurement(client, json={"measurement": 1})
    assert r.status_code == 201
    db = database.connect()
    print(db.tables)
    records = list(db["test_model"].all())
    assert len(records) == 1
