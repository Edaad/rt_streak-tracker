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
                title=self.referrals_sheet_name, rows=1000, cols=3
            )
            # Add headers
            headers = ["ReferredPlayer", "HandsPlayed", "ReferrerPlayer"]
            self.referrals_worksheet.insert_row(headers, 1)

    def load_referrals_data(self):
        """Load referrals data from Google Sheets."""
        try:
            records = self.referrals_worksheet.get_all_records()
            if not records:
                return pd.DataFrame(
                    columns=["ReferredPlayer", "HandsPlayed", "ReferrerPlayer"]
                )
            return pd.DataFrame(records)
        except Exception as e:
            print(f"Error loading referrals data: {e}")
            return pd.DataFrame(
                columns=["ReferredPlayer", "HandsPlayed", "ReferrerPlayer"]
            )

    def save_referrals_data(self, df):
        """Save referrals data to Google Sheets."""
        try:
            # Clear existing data
            self.referrals_worksheet.clear()

            # Add headers
            headers = ["ReferredPlayer", "HandsPlayed", "ReferrerPlayer"]
            self.referrals_worksheet.insert_row(headers, 1)

            # Add data
            if not df.empty:
                data = df.values.tolist()
                for i, row in enumerate(data, start=2):
                    self.referrals_worksheet.insert_row(row, i)
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
        """Update hands played for referred players and check for 250 hand milestone."""
        # Load referrals data
        df = self.load_referrals_data()

        if df.empty:
            return []

        milestone_messages = []

        # Update hands for each referred player
        for index, row in df.iterrows():
            referred_player = row["ReferredPlayer"]
            current_hands = int(row["HandsPlayed"])
            referrer = row["ReferrerPlayer"]

            # Check if this player played today
            if referred_player in daily_players_data:
                daily_hands = daily_players_data[referred_player]
                new_total_hands = current_hands + daily_hands

                # Check for 250 hand milestone
                if current_hands < 250 and new_total_hands >= 250:
                    milestone_messages.append(
                        f"🎁 {referred_player} hit 250 hands milestone! {referrer} should receive a referral bonus!"
                    )

                # Update the hands in dataframe
                df.at[index, "HandsPlayed"] = new_total_hands

        # Save updated data back to sheets
        if not df.empty:
            self.save_referrals_data(df)

        return milestone_messages
