import json
from google.oauth2 import service_account

# Try to load the credentials
try:
    credentials = service_account.Credentials.from_service_account_file(
        "credentials.json", scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    print("Credentials loaded successfully")
    print(f"Service account email: {credentials.service_account_email}")
except Exception as e:
    print(f"Error loading credentials: {e}")
