import os

from datetime import datetime
from pathlib import Path

import pytest

from flask import url_for
from werkzeug.datastructures import MultiDict

from homelog import database
from homelog.app import app as flask_app, compute_filters


@pytest.fixture(autouse=True)
def mock_db(monkeypatch):
    # don't use :memory: because we don't have a db singleton
    monkeypatch.setenv("DATABASE_URL", "sqlite:///_test.db")
    yield
    if (db_path := Path("_test.db")).exists():
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
    records = list(db["test_model"].all())
    assert len(records) == 1

    # send valid value with created_at
    created_at = datetime(2020, 12, 31)
    r = post_measurement(client, json={"measurement": 2, "created_at": created_at.isoformat()})
    assert r.status_code == 201
    db = database.connect()
    records = list(db["test_model"].find(value=2.0))
    assert len(records) == 1
    assert records[0]["created_at"].year == 2020


def test_compute_filters():
    cols = ["col1", "col2"]
    args = MultiDict(
        [("col1", "value1"), ("col1", "value1_bis"), ("col2__gt", "value2"), ("col3", "value3")]
    )
    filters = compute_filters(args, cols)
    assert filters == {
        "col1": {"in": ["value1", "value1_bis"]},
        "col2": {"gt": "value2"},
    }
