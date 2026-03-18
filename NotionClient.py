import requests
from datetime import datetime
from icalendar import Calendar, Event
import os
import json
import logging

logger = logging.getLogger(__name__)

NOTION_API_VERSION = "2022-06-28"
DEFAULT_OUTPUT_FILE = "Notion.ics"
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    """Load database configurations from config.json."""
    if not os.path.exists(CONFIG_PATH):
        return {"databases": []}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(config):
    """Save database configurations to config.json."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


class NotionClient:

    def __init__(self, token):
        self.token = token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        }

    def _fetch_all_pages(self, database_id):
        """Fetch all pages from a Notion database, handling pagination."""
        api_url = f"https://api.notion.com/v1/databases/{database_id}/query"
        all_results = []
        payload = {
            "sorts": [
                {
                    "timestamp": "last_edited_time",
                    "direction": "ascending",
                }
            ]
        }
        has_more = True
        while has_more:
            response = requests.post(api_url, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()
            all_results.extend(data.get("results", []))
            has_more = data.get("has_more", False)
            if has_more:
                payload["start_cursor"] = data["next_cursor"]
        return all_results

    def get_database(self, database_id, property_mappings=None,
                     uppercase_categories=None):
        """Fetch events from a single Notion database.

        Args:
            database_id: The Notion database ID.
            property_mappings: Dict mapping logical names to Notion property
                names.  Keys: title, date, category, group.
            uppercase_categories: List of category values whose titles should
                be uppercased.

        Returns:
            A list of event dicts with keys: title, date, url.
        """
        if property_mappings is None:
            property_mappings = {
                "title": "Name",
                "date": "Date",
                "category": "Type",
                "group": "Class",
            }
        if uppercase_categories is None:
            uppercase_categories = ["Assignment", "Exam"]

        title_prop = property_mappings.get("title", "Name")
        date_prop = property_mappings.get("date", "Date")
        category_prop = property_mappings.get("category", "Type")
        group_prop = property_mappings.get("group", "Class")

        items = self._fetch_all_pages(database_id)
        events = []

        for item in items:
            props = item.get("properties", {})
            try:
                title = props[title_prop]["title"][0]["plain_text"]
            except (KeyError, IndexError):
                logger.warning("Skipping item with missing title property")
                continue

            # Optional category
            category = ""
            try:
                category = props[category_prop]["select"]["name"]
            except (KeyError, TypeError):
                pass

            if category in uppercase_categories:
                title = title.upper()

            # Optional group / label
            group = ""
            try:
                group = props[group_prop]["select"]["name"]
            except (KeyError, TypeError):
                pass

            # Date (required)
            try:
                date_info = props[date_prop]["date"]
                start_str = date_info["start"]
                end_str = date_info.get("end")
            except (KeyError, TypeError):
                logger.warning("Skipping item '%s' with missing date", title)
                continue

            start = _parse_date(start_str)
            end = _parse_date(end_str) if end_str else None

            item_url = item.get("url", "")

            summary = f"{title} [{group}]" if group else title
            events.append({
                "title": summary,
                "date": start,
                "end": end,
                "url": item_url,
            })

        return events

    def sync_all(self):
        """Sync all configured databases and write .ics files.

        Returns:
            A list of dicts with keys: name, output_file, event_count, error.
        """
        config = load_config()
        results = []
        for db in config.get("databases", []):
            # Fall back to DATABASE_ID env var for legacy single-database setups
            db_id = db.get("database_id") or os.getenv("DATABASE_ID", "")
            if not db_id:
                results.append({
                    "name": db.get("name", "Unknown"),
                    "output_file": db.get("output_file", ""),
                    "event_count": 0,
                    "error": "No database_id configured",
                })
                continue
            try:
                events = self.get_database(
                    db_id,
                    property_mappings=db.get("property_mappings"),
                    uppercase_categories=db.get("uppercase_categories"),
                )
                output_file = db.get("output_file", DEFAULT_OUTPUT_FILE)
                export_ical(events, output_file)
                results.append({
                    "name": db.get("name", "Unknown"),
                    "output_file": output_file,
                    "event_count": len(events),
                    "error": None,
                })
            except Exception as exc:
                logger.exception("Failed to sync database %s", db.get("name"))
                results.append({
                    "name": db.get("name", "Unknown"),
                    "output_file": db.get("output_file", ""),
                    "event_count": 0,
                    "error": str(exc),
                })
        return results


def _parse_date(date_str):
    """Parse a Notion date string, supporting both date and datetime."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {date_str}")


def export_ical(events, output_file="Notion.ics"):
    """Write a list of event dicts to an iCalendar file."""
    cal = Calendar()
    cal.add("prodid", "-//Notion-iCal//EN")
    cal.add("version", "2.0")

    for item in events:
        event = Event()
        event.add("summary", item["title"])
        start = item["date"]
        if hasattr(start, "hour") and (start.hour or start.minute):
            event.add("dtstart", start)
        else:
            event.add("dtstart", start.date() if hasattr(start, "date") else start)
        if item.get("end"):
            end = item["end"]
            if hasattr(end, "hour") and (end.hour or end.minute):
                event.add("dtend", end)
            else:
                event.add("dtend", end.date() if hasattr(end, "date") else end)
        if item.get("url"):
            event.add("url", item["url"])
        cal.add_component(event)

    with open(output_file, "wb") as f:
        f.write(cal.to_ical())
    logger.info("Wrote %d events to %s", len(events), output_file)