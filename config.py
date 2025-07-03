import os
import json

# For local development, use environment variables with fallbacks
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MASTER_SHEET_ID = os.getenv("MASTER_SHEET_ID")
ADMIN_USERS = os.getenv("ADMIN_USERS", "").split(",")
DEFAULT_HANDS_THRESHOLD = int(os.getenv("DEFAULT_HANDS_THRESHOLD", "100"))

# For credentials, try environment variable first, then fall back to local file
try:
    # Try to load from environment variable (for Heroku)
    GOOGLE_CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
except (TypeError, json.JSONDecodeError):
    # Fall back to local credentials file (for development)
    try:
        with open("credentials.json", "r") as f:
            GOOGLE_CREDS_JSON = json.load(f)
    except FileNotFoundError:
        GOOGLE_CREDS_JSON = None
