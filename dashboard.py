"""Web dashboard for Notion-iCal configuration.

Run with: python dashboard.py
Then open http://localhost:5000 in your browser.
"""

import functools
import json
import os
import secrets
import logging
import threading
from datetime import datetime, timezone

from dotenv import load_dotenv, set_key
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, send_file, abort,
)

from NotionClient import NotionClient, load_config, save_config, CONFIG_PATH

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "notion-ical-dev-key")

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background auto-sync scheduler
# ---------------------------------------------------------------------------

_sync_lock = threading.Lock()
_last_sync_time = None
_last_sync_results = None
_scheduler_thread = None
_scheduler_stop = threading.Event()


def _get_sync_interval():
    """Return the configured sync interval in minutes, or 0 to disable."""
    try:
        return int(os.getenv("SYNC_INTERVAL_MINUTES", "30"))
    except (ValueError, TypeError):
        return 30


def _run_sync():
    """Execute a sync and store the results (thread-safe)."""
    global _last_sync_time, _last_sync_results
    token = os.getenv("NOTION_TOKEN", "")
    if not token:
        logger.warning("Auto-sync skipped: NOTION_TOKEN not set")
        return
    with _sync_lock:
        try:
            client = NotionClient(token)
            results = client.sync_all()
            _last_sync_time = datetime.now(timezone.utc)
            _last_sync_results = results
            for r in results:
                if r["error"]:
                    logger.error("Auto-sync error for %s: %s", r["name"], r["error"])
                else:
                    logger.info("Auto-synced %s: %d events", r["name"], r["event_count"])
        except Exception:
            logger.exception("Auto-sync failed")


def _scheduler_loop():
    """Background loop that runs sync on a fixed interval."""
    interval = _get_sync_interval()
    if interval <= 0:
        logger.info("Auto-sync disabled (SYNC_INTERVAL_MINUTES=0)")
        return
    logger.info("Auto-sync started: every %d minute(s)", interval)
    # Initial sync on startup
    _run_sync()
    while not _scheduler_stop.wait(timeout=interval * 60):
        _run_sync()


def start_scheduler():
    """Start the background sync scheduler (called once at startup)."""
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()


def stop_scheduler():
    """Stop the background sync scheduler."""
    _scheduler_stop.set()
    if _scheduler_thread is not None:
        _scheduler_thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------

def _get_dashboard_password():
    """Return the configured dashboard password, or *None* if auth is disabled."""
    return os.getenv("DASHBOARD_PASSWORD") or None


def login_required(view):
    """Decorator that redirects unauthenticated users to the login page.

    If ``DASHBOARD_PASSWORD`` is not set, all requests are allowed through
    (backwards-compatible with the previous behaviour).
    """
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if _get_dashboard_password() and not session.get("authenticated"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    password = _get_dashboard_password()
    if not password:
        return redirect(url_for("index"))

    if request.method == "POST":
        if request.form.get("password") == password:
            session["authenticated"] = True
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        flash("Incorrect password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.pop("authenticated", None)
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard routes (protected)
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    config = load_config()
    notion_token = os.getenv("NOTION_TOKEN", "")
    token_display = f"{notion_token[:8]}..." if len(notion_token) > 8 else notion_token
    sync_interval = _get_sync_interval()
    return render_template(
        "index.html",
        databases=config.get("databases", []),
        token_display=token_display,
        token_set=bool(notion_token),
        sync_interval=sync_interval,
        last_sync_time=_last_sync_time,
    )


@app.route("/settings", methods=["GET", "POST"])
@login_required
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
@login_required
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
@login_required
def edit_database(idx):
    config = load_config()
    dbs = config.get("databases", [])
    if idx < 0 or idx >= len(dbs):
        flash("Database not found.", "error")
        return redirect(url_for("index"))
    if request.method == "POST":
        edited = _db_entry_from_form(request.form)
        # Preserve existing feed token and read token
        edited["feed_token"] = dbs[idx].get("feed_token", _generate_feed_token())
        edited["read_token"] = dbs[idx].get("read_token", _generate_feed_token())
        dbs[idx] = edited
        save_config(config)
        flash(f"Database '{dbs[idx]['name']}' updated.", "success")
        return redirect(url_for("index"))
    return render_template("database_form.html", db=dbs[idx], action="Edit")


@app.route("/databases/delete/<int:idx>", methods=["POST"])
@login_required
def delete_database(idx):
    config = load_config()
    dbs = config.get("databases", [])
    if 0 <= idx < len(dbs):
        removed = dbs.pop(idx)
        save_config(config)
        flash(f"Database '{removed['name']}' removed.", "success")
    return redirect(url_for("index"))


@app.route("/databases/regenerate-token/<int:idx>", methods=["POST"])
@login_required
def regenerate_token(idx):
    config = load_config()
    dbs = config.get("databases", [])
    if 0 <= idx < len(dbs):
        dbs[idx]["feed_token"] = _generate_feed_token()
        save_config(config)
        flash(f"Admin URL for '{dbs[idx]['name']}' regenerated. "
              "Update any existing calendar subscriptions.", "success")
    return redirect(url_for("index"))


@app.route("/databases/regenerate-read-token/<int:idx>", methods=["POST"])
@login_required
def regenerate_read_token(idx):
    config = load_config()
    dbs = config.get("databases", [])
    if 0 <= idx < len(dbs):
        dbs[idx]["read_token"] = _generate_feed_token()
        save_config(config)
        flash(f"Read-only share URL for '{dbs[idx]['name']}' regenerated. "
              "Update any existing shared subscriptions.", "success")
    return redirect(url_for("index"))


@app.route("/sync", methods=["POST"])
@login_required
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


# ---------------------------------------------------------------------------
# Public iCal feed (token-authenticated)
# ---------------------------------------------------------------------------

@app.route("/feed/<token>/<path:filename>")
def feed(token, filename):
    """Serve an .ics file if the token matches a configured database.

    Both ``feed_token`` (read-write / admin) and ``read_token`` (read-only /
    share) are accepted.  The served content is identical — the two tokens
    exist so they can be revoked independently.
    """
    config = load_config()
    for db in config.get("databases", []):
        is_admin = db.get("feed_token") == token
        is_read = db.get("read_token") == token
        if (is_admin or is_read) and db.get("output_file") == filename:
            filepath = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), filename
            )
            if os.path.isfile(filepath):
                return send_file(
                    filepath,
                    mimetype="text/calendar",
                    as_attachment=False,
                    download_name=filename,
                )
            abort(404)
    abort(404)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_feed_token():
    """Generate a cryptographically secure feed token."""
    return secrets.token_urlsafe(32)


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
        "feed_token": _generate_feed_token(),
        "read_token": _generate_feed_token(),
    }


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "5000"))
    start_scheduler()
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
