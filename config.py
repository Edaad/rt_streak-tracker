import os
import json

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MASTER_SHEET_ID = os.getenv("MASTER_SHEET_ID")
ADMIN_USERS = os.getenv("ADMIN_USERS", "").split(",")
DEFAULT_HANDS_THRESHOLD = int(os.getenv("DEFAULT_HANDS_THRESHOLD", "100"))

# JSON string from env var (credentials.json)
GOOGLE_CREDS_JSON = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
