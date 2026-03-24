FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/Gut-Einern-e-V/Notion-iCal"
LABEL org.opencontainers.image.description="Sync Notion databases to iCalendar (.ics) files"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

EXPOSE 5000

CMD ["python", "dashboard.py"]
