"""Web dashboard for Notion-iCal configuration.

Run with: python dashboard.py
Then open http://localhost:5000 in your browser.
"""

import json
import os
import logging

from dotenv import load_dotenv, set_key
from flask import Flask, render_template, request, redirect, url_for, flash

from NotionClient import NotionClient, load_config, save_config, CONFIG_PATH

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "notion-ical-dev-key")

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

logging.basicConfig(level=logging.INFO)


@app.route("/")
def index():
    config = load_config()
    notion_token = os.getenv("NOTION_TOKEN", "")
    token_display = f"{notion_token[:8]}..." if len(notion_token) > 8 else notion_token
    return render_template(
        "index.html",
        databases=config.get("databases", []),
        token_display=token_display,
        token_set=bool(notion_token),
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        token = request.form.get("notion_token", "").strip()
        if token:
            set_key(ENV_PATH, "NOTION_TOKEN", token)
            os.environ["NOTION_TOKEN"] = token
            flash("Notion token updated.", "success")
        return redirect(url_for("settings"))

    notion_token = os.getenv("NOTION_TOKEN", "")
    token_display = f"{notion_token[:8]}..." if len(notion_token) > 8 else notion_token
    return render_template("settings.html", token_display=token_display,
                           token_set=bool(notion_token))


@app.route("/databases/add", methods=["GET", "POST"])
def add_database():
    if request.method == "POST":
        config = load_config()
        db_entry = _db_entry_from_form(request.form)
        config.setdefault("databases", []).append(db_entry)
        save_config(config)
        flash(f"Database '{db_entry['name']}' added.", "success")
        return redirect(url_for("index"))
    return render_template("database_form.html", db=None, action="Add")


@app.route("/databases/edit/<int:idx>", methods=["GET", "POST"])
def edit_database(idx):
    config = load_config()
    dbs = config.get("databases", [])
    if idx < 0 or idx >= len(dbs):
        flash("Database not found.", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        dbs[idx] = _db_entry_from_form(request.form)
        save_config(config)
        flash(f"Database '{dbs[idx]['name']}' updated.", "success")
        return redirect(url_for("index"))
    return render_template("database_form.html", db=dbs[idx], action="Edit")


@app.route("/databases/delete/<int:idx>", methods=["POST"])
def delete_database(idx):
    config = load_config()
    dbs = config.get("databases", [])
    if 0 <= idx < len(dbs):
        removed = dbs.pop(idx)
        save_config(config)
        flash(f"Database '{removed['name']}' removed.", "success")
    return redirect(url_for("index"))


@app.route("/sync", methods=["POST"])
def sync():
    token = os.getenv("NOTION_TOKEN", "")
    if not token:
        flash("Notion token not configured. Go to Settings first.", "error")
        return redirect(url_for("index"))
    client = NotionClient(token)
    results = client.sync_all()
    for r in results:
        if r["error"]:
            flash(f"Error syncing {r['name']}: {r['error']}", "error")
        else:
            flash(f"Synced {r['name']}: {r['event_count']} events → {r['output_file']}",
                  "success")
    return redirect(url_for("index"))


def _db_entry_from_form(form):
    return {
        "name": form.get("name", "").strip(),
        "database_id": form.get("database_id", "").strip(),
        "output_file": form.get("output_file", "calendar.ics").strip(),
        "property_mappings": {
            "title": form.get("prop_title", "Name").strip(),
            "date": form.get("prop_date", "Date").strip(),
            "category": form.get("prop_category", "Type").strip(),
            "group": form.get("prop_group", "Class").strip(),
        },
        "uppercase_categories": [
            c.strip()
            for c in form.get("uppercase_categories", "").split(",")
            if c.strip()
        ],
    }


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
