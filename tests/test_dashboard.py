"""Tests for the Flask dashboard routes."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dashboard import app
from NotionClient import save_config


@pytest.fixture
def client(tmp_path, monkeypatch):
    cfg_path = str(tmp_path / "config.json")
    monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
    monkeypatch.setattr("dashboard.CONFIG_PATH", cfg_path)
    save_config({"databases": []})
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestDashboardRoutes:
    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Notion-iCal Dashboard" in resp.data

    def test_settings_get(self, client):
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert b"Settings" in resp.data

    def test_add_database_get(self, client):
        resp = client.get("/databases/add")
        assert resp.status_code == 200
        assert b"Add Database" in resp.data

    def test_add_and_delete_database(self, client, tmp_path, monkeypatch):
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("dashboard.CONFIG_PATH", cfg_path)

        resp = client.post("/databases/add", data={
            "name": "Vacation",
            "database_id": "abc-123",
            "output_file": "vacation.ics",
            "prop_title": "Name",
            "prop_date": "Date",
            "prop_category": "",
            "prop_group": "",
            "uppercase_categories": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Vacation" in resp.data

        # Delete it
        resp = client.post("/databases/delete/0", follow_redirects=True)
        assert resp.status_code == 200

    def test_edit_database(self, client, tmp_path, monkeypatch):
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("dashboard.CONFIG_PATH", cfg_path)
        save_config({
            "databases": [{
                "name": "Old",
                "database_id": "db-1",
                "output_file": "old.ics",
                "property_mappings": {"title": "Name", "date": "Date",
                                      "category": "Type", "group": "Class"},
                "uppercase_categories": [],
            }]
        })

        resp = client.get("/databases/edit/0")
        assert resp.status_code == 200
        assert b"Old" in resp.data

        resp = client.post("/databases/edit/0", data={
            "name": "New",
            "database_id": "db-1",
            "output_file": "new.ics",
            "prop_title": "Name",
            "prop_date": "Date",
            "prop_category": "Type",
            "prop_group": "Class",
            "uppercase_categories": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"New" in resp.data
