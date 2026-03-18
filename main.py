from dotenv import load_dotenv
import os
import logging

from NotionClient import NotionClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main():
    load_dotenv()
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        logging.error("NOTION_TOKEN is not set. Please configure your .env file.")
        return

    client = NotionClient(notion_token)
    results = client.sync_all()

    for r in results:
        if r["error"]:
            logging.error("  %s: %s", r["name"], r["error"])
        else:
            logging.info("  %s: %d events → %s", r["name"], r["event_count"],
                         r["output_file"])


if __name__ == "__main__":
    main()
