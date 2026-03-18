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
    # Ensure no password requirement by default for existing tests
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
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
                "feed_token": "test-token-abc",
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


class TestAuth:
    """Test dashboard password protection."""

    def test_no_password_allows_access(self, client):
        """Without DASHBOARD_PASSWORD, all routes are accessible."""
        resp = client.get("/")
        assert resp.status_code == 200

    def test_password_redirects_to_login(self, client, monkeypatch):
        monkeypatch.setenv("DASHBOARD_PASSWORD", "secret123")
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_login_page_renders(self, client, monkeypatch):
        monkeypatch.setenv("DASHBOARD_PASSWORD", "secret123")
        resp = client.get("/login")
        assert resp.status_code == 200
        assert b"Dashboard Password" in resp.data

    def test_login_wrong_password(self, client, monkeypatch):
        monkeypatch.setenv("DASHBOARD_PASSWORD", "secret123")
        resp = client.post("/login", data={"password": "wrong"}, follow_redirects=True)
        assert b"Incorrect password" in resp.data

    def test_login_correct_password(self, client, monkeypatch):
        monkeypatch.setenv("DASHBOARD_PASSWORD", "secret123")
        resp = client.post("/login", data={"password": "secret123"}, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Notion-iCal Dashboard" in resp.data

    def test_logout(self, client, monkeypatch):
        monkeypatch.setenv("DASHBOARD_PASSWORD", "secret123")
        # Login first
        client.post("/login", data={"password": "secret123"})
        # Logout
        resp = client.post("/logout")
        assert resp.status_code == 302
        # Should be redirected to login now
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    def test_login_no_password_set_redirects_to_index(self, client):
        """If no password is configured, /login redirects to index."""
        resp = client.get("/login")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")


class TestFeed:
    """Test public iCal feed endpoint."""

    def test_feed_valid_token(self, client, tmp_path, monkeypatch):
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("dashboard.CONFIG_PATH", cfg_path)

        # Create a dummy .ics file
        ics_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test.ics")
        ics_path = os.path.normpath(ics_path)
        with open(ics_path, "wb") as f:
            f.write(b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")

        save_config({
            "databases": [{
                "name": "Test",
                "database_id": "db-1",
                "output_file": "test.ics",
                "feed_token": "valid-token-123",
            }]
        })

        try:
            resp = client.get("/feed/valid-token-123/test.ics")
            assert resp.status_code == 200
            assert resp.content_type == "text/calendar; charset=utf-8"
        finally:
            os.unlink(ics_path)

    def test_feed_invalid_token(self, client, tmp_path, monkeypatch):
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("dashboard.CONFIG_PATH", cfg_path)
        save_config({
            "databases": [{
                "name": "Test",
                "database_id": "db-1",
                "output_file": "test.ics",
                "feed_token": "valid-token-123",
            }]
        })
        resp = client.get("/feed/wrong-token/test.ics")
        assert resp.status_code == 404

    def test_feed_wrong_filename(self, client, tmp_path, monkeypatch):
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("dashboard.CONFIG_PATH", cfg_path)
        save_config({
            "databases": [{
                "name": "Test",
                "database_id": "db-1",
                "output_file": "test.ics",
                "feed_token": "valid-token-123",
            }]
        })
        resp = client.get("/feed/valid-token-123/other.ics")
        assert resp.status_code == 404

    def test_feed_no_auth_needed(self, client, tmp_path, monkeypatch):
        """Feed endpoint works even when dashboard password is set."""
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("dashboard.CONFIG_PATH", cfg_path)
        monkeypatch.setenv("DASHBOARD_PASSWORD", "secret123")

        ics_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "test2.ics")
        ics_path = os.path.normpath(ics_path)
        with open(ics_path, "wb") as f:
            f.write(b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")

        save_config({
            "databases": [{
                "name": "Test",
                "database_id": "db-1",
                "output_file": "test2.ics",
                "feed_token": "feed-token-456",
            }]
        })

        try:
            resp = client.get("/feed/feed-token-456/test2.ics")
            assert resp.status_code == 200
            assert resp.content_type == "text/calendar; charset=utf-8"
        finally:
            os.unlink(ics_path)


class TestRegenerateToken:
    """Test feed token regeneration."""

    def test_regenerate_token(self, client, tmp_path, monkeypatch):
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("dashboard.CONFIG_PATH", cfg_path)
        save_config({
            "databases": [{
                "name": "Test",
                "database_id": "db-1",
                "output_file": "test.ics",
                "feed_token": "old-token",
            }]
        })

        resp = client.post("/databases/regenerate-token/0", follow_redirects=True)
        assert resp.status_code == 200

        from NotionClient import load_config
        config = load_config()
        assert config["databases"][0]["feed_token"] != "old-token"

    def test_add_database_generates_feed_token(self, client, tmp_path, monkeypatch):
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        monkeypatch.setattr("dashboard.CONFIG_PATH", cfg_path)
        save_config({"databases": []})

        client.post("/databases/add", data={
            "name": "New",
            "database_id": "db-new",
            "output_file": "new.ics",
            "prop_title": "Name",
            "prop_date": "Date",
            "prop_category": "",
            "prop_group": "",
            "uppercase_categories": "",
        })

        from NotionClient import load_config
        config = load_config()
        assert config["databases"][0].get("feed_token")
        assert len(config["databases"][0]["feed_token"]) > 20
