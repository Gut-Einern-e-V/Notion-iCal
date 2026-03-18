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

## Calendar Subscriptions

Each configured database gets a unique, secret subscription URL like:

```
https://your-host/feed/<token>/calendar.ics
```

Copy the URL from the dashboard and add it as a **calendar subscription** in
Google Calendar, Apple Calendar, Outlook, or any app that supports iCal feeds.

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
