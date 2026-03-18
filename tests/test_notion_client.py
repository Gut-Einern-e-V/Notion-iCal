"""Tests for NotionClient core logic (no API calls needed)."""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

# Ensure the project root is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from NotionClient import (
    NotionClient,
    _parse_date,
    export_ical,
    load_config,
    save_config,
    CONFIG_PATH,
)


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_date_only(self):
        dt = _parse_date("2026-03-18")
        assert dt == datetime(2026, 3, 18)

    def test_datetime_with_timezone(self):
        dt = _parse_date("2026-03-18T14:30:00+02:00")
        assert dt.hour == 14
        assert dt.minute == 30

    def test_datetime_without_timezone(self):
        dt = _parse_date("2026-03-18T09:00:00")
        assert dt.hour == 9

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Unrecognised date format"):
            _parse_date("not-a-date")

    def test_none_returns_none(self):
        assert _parse_date(None) is None


# ---------------------------------------------------------------------------
# export_ical
# ---------------------------------------------------------------------------

class TestExportIcal:
    def test_writes_ics_file(self, tmp_path):
        events = [
            {
                "title": "Meeting",
                "date": datetime(2026, 4, 1),
                "end": None,
                "url": "https://notion.so/abc",
            },
            {
                "title": "Deadline",
                "date": datetime(2026, 5, 10, 14, 0),
                "end": datetime(2026, 5, 10, 15, 0),
                "url": "",
            },
        ]
        out = str(tmp_path / "test.ics")
        export_ical(events, out)
        with open(out, "rb") as f:
            content = f.read()
        assert b"BEGIN:VCALENDAR" in content
        assert b"Meeting" in content
        assert b"Deadline" in content
        assert b"END:VCALENDAR" in content

    def test_empty_events_produces_valid_ical(self, tmp_path):
        out = str(tmp_path / "empty.ics")
        export_ical([], out)
        with open(out, "rb") as f:
            content = f.read()
        assert b"BEGIN:VCALENDAR" in content
        assert b"END:VCALENDAR" in content


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

class TestConfig:
    def test_save_and_load(self, tmp_path, monkeypatch):
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        data = {"databases": [{"name": "Test", "database_id": "abc"}]}
        save_config(data)
        loaded = load_config()
        assert loaded["databases"][0]["name"] == "Test"

    def test_load_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("NotionClient.CONFIG_PATH", str(tmp_path / "nope.json"))
        assert load_config() == {"databases": []}


# ---------------------------------------------------------------------------
# NotionClient.get_database
# ---------------------------------------------------------------------------

SAMPLE_RESULTS = [
    {
        "properties": {
            "Name": {"title": [{"plain_text": "Homework 1"}]},
            "Date": {"date": {"start": "2026-04-01", "end": None}},
            "Type": {"select": {"name": "Assignment"}},
            "Class": {"select": {"name": "Math"}},
        },
        "url": "https://notion.so/1",
    },
    {
        "properties": {
            "Name": {"title": [{"plain_text": "Final Exam"}]},
            "Date": {"date": {"start": "2026-06-15T09:00:00"}},
            "Type": {"select": {"name": "Exam"}},
            "Class": {"select": {"name": "Physics"}},
        },
        "url": "https://notion.so/2",
    },
]


class TestGetDatabase:
    @patch("NotionClient.requests.post")
    def test_basic_fetch(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": SAMPLE_RESULTS,
            "has_more": False,
        }
        mock_post.return_value = mock_resp

        client = NotionClient("fake-token")
        events = client.get_database("fake-db-id")

        assert len(events) == 2
        # Assignment title should be uppercased
        assert events[0]["title"] == "HOMEWORK 1 [Math]"
        assert events[1]["title"] == "FINAL EXAM [Physics]"

    @patch("NotionClient.requests.post")
    def test_pagination(self, mock_post):
        page1 = MagicMock()
        page1.raise_for_status = MagicMock()
        page1.json.return_value = {
            "results": SAMPLE_RESULTS[:1],
            "has_more": True,
            "next_cursor": "cursor-abc",
        }
        page2 = MagicMock()
        page2.raise_for_status = MagicMock()
        page2.json.return_value = {
            "results": SAMPLE_RESULTS[1:],
            "has_more": False,
        }
        mock_post.side_effect = [page1, page2]

        client = NotionClient("fake-token")
        events = client.get_database("fake-db-id")
        assert len(events) == 2
        assert mock_post.call_count == 2

    @patch("NotionClient.requests.post")
    def test_missing_optional_fields(self, mock_post):
        """Items without category or group should still be processed."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {
                    "properties": {
                        "Name": {"title": [{"plain_text": "Simple Event"}]},
                        "Date": {"date": {"start": "2026-07-01"}},
                    },
                    "url": "https://notion.so/3",
                }
            ],
            "has_more": False,
        }
        mock_post.return_value = mock_resp

        client = NotionClient("fake-token")
        events = client.get_database("fake-db-id")
        assert len(events) == 1
        assert events[0]["title"] == "Simple Event"


# ---------------------------------------------------------------------------
# sync_all
# ---------------------------------------------------------------------------

class TestSyncAll:
    @patch("NotionClient.requests.post")
    def test_sync_with_configured_databases(self, mock_post, tmp_path, monkeypatch):
        cfg_path = str(tmp_path / "config.json")
        monkeypatch.setattr("NotionClient.CONFIG_PATH", cfg_path)
        config = {
            "databases": [
                {
                    "name": "Team",
                    "database_id": "db-123",
                    "output_file": str(tmp_path / "team.ics"),
                    "property_mappings": {
                        "title": "Name",
                        "date": "Date",
                        "category": "Type",
                        "group": "Class",
                    },
                    "uppercase_categories": [],
                }
            ]
        }
        with open(cfg_path, "w") as f:
            json.dump(config, f)

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": SAMPLE_RESULTS,
            "has_more": False,
        }
        mock_post.return_value = mock_resp

        client = NotionClient("fake-token")
        results = client.sync_all()

        assert len(results) == 1
        assert results[0]["error"] is None
        assert results[0]["event_count"] == 2
        assert os.path.exists(str(tmp_path / "team.ics"))
