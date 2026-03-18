# Notion-iCal

Sync Notion databases to iCalendar (`.ics`) files that you can import into
Google Calendar, Outlook, Apple Calendar, or any other calendar app.

## Features

- **Multiple databases** – sync a team calendar, vacation calendar, class
  deadlines, or any other Notion database in one go.
- **Web dashboard** – a simple browser UI so that non-technical users can
  configure databases, update the Notion token, and trigger syncs.
- **Configurable property mappings** – map any Notion property names (Title,
  Date, Category, Group) to match your database setup.
- **Docker support** – one-command deployment with `docker compose up`.
- **Pagination** – handles large databases (>100 items) automatically.
- **Date & datetime** – supports both all-day and timed events, including
  start/end ranges.

## Quick Start

### 1. Get a Notion API Token

Go to <https://www.notion.so/my-integrations>, create a new integration, and
copy the token.

### 2. Share Your Database

Open your Notion database → **Share** → invite the integration.

### 3. Clone & Install

```bash
git clone https://github.com/Gut-Einern-e-V/Notion-iCal.git
cd Notion-iCal
python -m venv env && source env/bin/activate
pip install -r requirements.txt
```

### 4. Configure

Copy the example config and set your token:

```bash
cp .env.example .env        # then edit .env with your NOTION_TOKEN
```

Edit `config.json` to add your databases (or use the web dashboard):

```json
{
  "databases": [
    {
      "name": "Team Calendar",
      "database_id": "your-database-id",
      "output_file": "team.ics",
      "property_mappings": {
        "title": "Name",
        "date": "Date",
        "category": "Type",
        "group": "Team"
      },
      "uppercase_categories": ["Exam"]
    }
  ]
}
```

### 5a. Command-Line Sync

```bash
python main.py
```

### 5b. Web Dashboard

```bash
python dashboard.py
# Open http://localhost:5000
```

### 6. Import the `.ics` File

Import the generated `.ics` file into your favourite calendar application.

## Docker Deployment

```bash
docker compose up -d
```

The dashboard will be available at `http://localhost:5000`.
Configuration is persisted via the mounted `config.json` and `.env` files.

To update to a newer version:

```bash
git pull
docker compose up -d --build
```

## Configuration Reference

| Environment Variable | Description | Default |
|---|---|---|
| `NOTION_TOKEN` | Notion integration API token | *(required)* |
| `DATABASE_ID` | Fallback database ID (legacy) | – |
| `DASHBOARD_PORT` | Port for the web dashboard | `5000` |
| `FLASK_SECRET_KEY` | Secret key for Flask sessions | `notion-ical-dev-key` |
| `FLASK_DEBUG` | Set to `1` to enable debug mode | `0` |
| `DASHBOARD_PASSWORD` | Password to protect the dashboard UI | *(disabled)* |
| `SYNC_INTERVAL_MINUTES` | Auto-sync interval in minutes (`0` to disable) | `30` |
| `BASE_URL` | External URL for feed links (for reverse proxies / tunnels) | *(auto-detected)* |

## Auto-Sync

The dashboard automatically syncs all configured databases in the background
on a configurable interval.  This means your iCal subscription URLs always
serve up-to-date data without any manual action.

- Set `SYNC_INTERVAL_MINUTES` to control how often syncs run (default: every
  30 minutes).
- Set `SYNC_INTERVAL_MINUTES=0` to disable auto-sync (manual sync only).
- The first sync runs immediately when the dashboard starts.
- You can still trigger a manual sync from the dashboard at any time.

```bash
# .env
SYNC_INTERVAL_MINUTES=15   # sync every 15 minutes
```

## Reverse Proxy & Tailscale Tunnels

By default, the dashboard generates feed URLs using the address from the
incoming request (e.g. `http://localhost:5000/`).  When the service is behind
a reverse proxy or a Tailscale Funnel / tunnel, the auto-detected address will
be wrong.

Set `BASE_URL` to the externally reachable address so that the generated
calendar-subscription links work for everyone:

```bash
# .env
BASE_URL=https://my-machine.tail12345.ts.net
```

The value may include a port and/or path prefix — a trailing slash is added
automatically if missing.  When `BASE_URL` is not set, the service falls back
to auto-detection.

## Calendar Subscriptions

Each configured database gets two subscription URLs:

- **Share URL (read-only)** – safe to give to external people.  They can
  subscribe to the calendar but have no management access.
- **Admin URL (read/write)** – for internal use.  Keep this URL private.

Both URLs serve the same calendar data.  Having two separate tokens means you
can **revoke external access** (regenerate the share URL) without breaking
your own subscriptions, and vice-versa.

Copy the appropriate URL from the dashboard and add it as a **calendar
subscription** in Google Calendar, Apple Calendar, Outlook, or any app that
supports iCal feeds.

- **No password required** for feed URLs — calendar apps don't support
  authentication, so each feed uses an unguessable token in the URL instead.
- **Regenerate** a feed URL from the dashboard if you need to revoke access.
  Existing subscribers will need the new link.

## Dashboard Password Protection

Set `DASHBOARD_PASSWORD` in your `.env` file (or environment) to require a
password before accessing the dashboard.  When set, users are redirected to a
login page.  Feed URLs remain publicly accessible (they are secured by their
secret tokens).

```bash
# .env
DASHBOARD_PASSWORD=my-secret-password
```

If `DASHBOARD_PASSWORD` is not set, the dashboard is open (useful for
development or when it's only reachable over a private network).

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Project Structure

```
├── NotionClient.py        # Core: Notion API client & iCal export
├── main.py                # CLI entry point
├── dashboard.py           # Flask web dashboard
├── config.json            # Database configurations
├── requirements.txt       # Python dependencies
├── templates/             # Dashboard HTML templates
├── tests/                 # Test suite
├── Dockerfile
└── docker-compose.yml
```
