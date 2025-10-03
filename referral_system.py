import pandas as pd
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials


class ReferralSystem:
    def __init__(self, credentials, master_sheet_id):
        """Initialize the referral system with Google Sheets integration."""
        self.master_sheet_id = master_sheet_id
        self.referrals_sheet_name = "Referrals"
        self.headers = [
            "ReferredPlayer",
            "HandsPlayed",
            "ReferrerPlayer",
            "BonusSent",
            "BonusSentAt",
        ]

        # Initialize Google Sheets connection
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]

        # Handle both credential file path (local) and credential dict (Heroku)
        if isinstance(credentials, str):
            # Local development - credentials is a file path
            creds = ServiceAccountCredentials.from_json_keyfile_name(credentials, scope)
        else:
            # Heroku deployment - credentials is a dict
            creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope)

        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(master_sheet_id)

        # Create referrals worksheet if it doesn't exist
        self._ensure_referrals_sheet_exists()

    def _ensure_referrals_sheet_exists(self):
        """Create the Referrals worksheet if it doesn't exist."""
        try:
            self.referrals_worksheet = self.sheet.worksheet(self.referrals_sheet_name)
        except gspread.WorksheetNotFound:
            # Create the worksheet with headers
            self.referrals_worksheet = self.sheet.add_worksheet(
                title=self.referrals_sheet_name, rows=1000, cols=len(self.headers)
            )
            # Add headers
            self.referrals_worksheet.insert_row(self.headers, 1)
        else:
            # Ensure required headers exist (for already-created sheets)
            try:
                existing_headers = self.referrals_worksheet.row_values(1)
            except Exception:
                existing_headers = []
            if existing_headers != self.headers:
                # Normalize headers (this will be enforced on next save as well)
                # Extend columns if needed
                if len(existing_headers) < len(self.headers):
                    # Try to resize columns to fit new headers
                    try:
                        self.referrals_worksheet.resize(cols=len(self.headers))
                    except Exception:
                        pass
                # Write the canonical headers row
                self.referrals_worksheet.update('A1', [self.headers])

    def load_referrals_data(self):
        """Load referrals data from Google Sheets and normalize schema."""
        try:
            records = self.referrals_worksheet.get_all_records()
            df = pd.DataFrame(records) if records else pd.DataFrame()
        except Exception as e:
            print(f"Error loading referrals data: {e}")
            df = pd.DataFrame()

        # Ensure required columns exist
        for col in self.headers:
            if col not in df.columns:
                df[col] = ""  # temporary default; types coerced below

        # Coerce types / defaults
        # ReferredPlayer, ReferrerPlayer as string
        df["ReferredPlayer"] = df["ReferredPlayer"].astype(str).str.strip()
        df["ReferrerPlayer"] = df["ReferrerPlayer"].astype(str).str.strip()

        # HandsPlayed as integer (missing -> 0)
        df["HandsPlayed"] = pd.to_numeric(df["HandsPlayed"], errors="coerce").fillna(0).astype(int)

        # BonusSent as boolean (missing/blank -> False)
        df["BonusSent"] = df["BonusSent"].astype(str).str.lower().isin(["true", "1", "yes", "y"]) if not df.empty else df["BonusSent"]
        df["BonusSent"] = df["BonusSent"].fillna(False).astype(bool)

        # BonusSentAt as string timestamp or empty
        df["BonusSentAt"] = df["BonusSentAt"].astype(str)

        # Keep only canonical columns in the right order
        df = df.reindex(columns=self.headers)

        return df

    def save_referrals_data(self, df):
        """Save referrals data to Google Sheets in canonical schema/order."""
        try:
            # Ensure correct columns/order
            if not set(self.headers).issubset(set(df.columns)):
                for col in self.headers:
                    if col not in df.columns:
                        df[col] = ""
            df = df.reindex(columns=self.headers)

            # Clear existing data and write headers + rows
            self.referrals_worksheet.clear()
            self.referrals_worksheet.insert_row(self.headers, 1)

            if not df.empty:
                data = df.values.tolist()
                # Bulk update for performance
                cell_range = f"A2:E{len(data)+1}"
                self.referrals_worksheet.update(cell_range, data)
        except Exception as e:
            print(f"Error saving referrals data: {e}")

    def add_referral(self, referred_player, hands_played, referrer_player):
        """Add a new referral to the system."""
        # Load existing data
        df = self.load_referrals_data()

        # Check for duplicates
        if not df.empty and referred_player in df["ReferredPlayer"].values:
            return False, "Error: That player is already on the referral list."

        # Add new referral
        new_referral = pd.DataFrame(
            {
                "ReferredPlayer": [referred_player],
                "HandsPlayed": [int(hands_played)],
                "ReferrerPlayer": [referrer_player],
                "BonusSent": [False],
                "BonusSentAt": [""],
            }
        )

        df = pd.concat([df, new_referral], ignore_index=True)

        # Save back to sheets
        self.save_referrals_data(df)

        return (
            True,
            f"✅ Successfully added referral: {referrer_player} referred {referred_player}",
        )

    def update_hands_and_check_milestone(self, daily_players_data):
        """Update hands played and emit a milestone message once per player upon reaching ≥250 hands.

        This will also catch players that were initially logged at ≥250 hands by sending the
        milestone the next time processing runs (provided BonusSent is still False).
        """
        # Load referrals data
        df = self.load_referrals_data()
        if df.empty:
            return []

        milestone_messages = []
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        for index, row in df.iterrows():
            referred_player = row["ReferredPlayer"]
            current_hands = int(row["HandsPlayed"]) if pd.notnull(row["HandsPlayed"]) else 0
            referrer = row["ReferrerPlayer"]
            bonus_sent = bool(row.get("BonusSent", False))

            # Use 0 if player didn't play today
            daily_hands = int(daily_players_data.get(referred_player, 0))
            new_total_hands = current_hands + daily_hands

            # Determine if we should send milestone
            crossed_now = (current_hands < 250) and (new_total_hands >= 250)
            already_overlooked = (current_hands >= 250) and (not bonus_sent)

            if (crossed_now or already_overlooked) and not bonus_sent:
                milestone_messages.append(
                    f"🎁 {referred_player} hit 250 hands milestone! {referrer} should receive a referral bonus!"
                )
                df.at[index, "BonusSent"] = True
                df.at[index, "BonusSentAt"] = now

            # Persist the updated hands total (even if zero today)
            df.at[index, "HandsPlayed"] = new_total_hands

        # Save updated data back to sheets
        self.save_referrals_data(df)
        return milestone_messages

    def lookup_referrals(self, referrer_username):
        """Look up all referrals for a given referrer."""
        # Load referrals data
        df = self.load_referrals_data()

        if df.empty:
            return []

        # Filter referrals for this referrer
        referrer_referrals = df[df["ReferrerPlayer"] == referrer_username]

        if referrer_referrals.empty:
            return []

        # Convert to list of dictionaries with bonus status
        referrals = []
        for _, row in referrer_referrals.iterrows():
            hands_played = int(row["HandsPlayed"])
            referrals.append({
                "referred_player": row["ReferredPlayer"],
                "hands_played": hands_played,
                "bonus_received": hands_played >= 250
            })

        return referrals
