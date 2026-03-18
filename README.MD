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
