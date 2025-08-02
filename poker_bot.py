import logging
import os
import tempfile
from datetime import datetime
import pandas as pd
import random
import openpyxl
import config

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
)
from oauth2client.service_account import ServiceAccountCredentials
import config


# Google Sheets imports
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Import PokerStreakTracker class
from poker_streak_tracker import PokerStreakTracker

# Import ReferralSystem
from referral_system import ReferralSystem

# Constants for conversation states
CHOOSING, PROCESSING_DATA, LOOKING_UP_PLAYER, REVIVING_STREAK, REVIVING_STREAK_VALUE = (
    range(5)
)
CONFIRMING_REVIVAL = 5

# Referral conversation states
REFERRAL_REFERRED, REFERRAL_HANDS, REFERRAL_REFERRER = range(6, 9)

# Lookup referrals conversation state
LOOKUP_REFS_USERNAME = 9

ADMIN_USERS = config.ADMIN_USERS

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# Google Sheets Helper
class GoogleSheetsHelper:
    def __init__(self, credentials_file, master_sheet_id, history_sheet_id=None):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            config.GOOGLE_CREDS_JSON, scope
        )

        self.client = gspread.authorize(credentials)

        # Store sheet IDs
        self.master_sheet_id = master_sheet_id
        self.history_sheet_id = history_sheet_id or master_sheet_id

        # Open sheets
        self.master_sheet = self.client.open_by_key(master_sheet_id).worksheet("Master")
        if self.history_sheet_id == self.master_sheet_id:
            self.history_sheet = self.client.open_by_key(master_sheet_id).worksheet(
                "History"
            )
        else:
            self.history_sheet = self.client.open_by_key(history_sheet_id).worksheet(
                "Sheet1"
            )

    def load_master_data(self):
        """Load data from master sheet to pandas DataFrame"""
        records = self.master_sheet.get_all_records()
        if not records:
            return pd.DataFrame(columns=["Username", "Streak"])
        return pd.DataFrame(records)

    def load_history_data(self):
        """Load data from history sheet to pandas DataFrame"""
        records = self.history_sheet.get_all_records()
        if not records:
            return pd.DataFrame(
                columns=[
                    "Username",
                    "LastUpdate",
                    "UpdateDate",
                    "CurrentStreak",
                    "HighestStreak",
                ]
            )
        return pd.DataFrame(records)

    def save_master_data(self, df):
        """Save pandas DataFrame to master sheet"""
        # Clear the sheet except for header
        self.master_sheet.resize(rows=1)
        # Update with new data
        if not df.empty:
            self.master_sheet.update([df.columns.values.tolist()] + df.values.tolist())
        else:
            self.master_sheet.update([["Username", "Streak"]])

    def save_history_data(self, df):
        """Save pandas DataFrame to history sheet"""
        # Clear the sheet except for header
        self.history_sheet.resize(rows=1)
        # Update with new data
        if not df.empty:
            self.history_sheet.update([df.columns.values.tolist()] + df.values.tolist())
        else:
            self.history_sheet.update(
                [
                    [
                        "Username",
                        "LastUpdate",
                        "UpdateDate",
                        "CurrentStreak",
                        "HighestStreak",
                    ]
                ]
            )


# Sheets Adapter for PokerStreakTracker
class GoogleSheetsAdapter:
    def __init__(self, sheets_helper):
        self.sheets_helper = sheets_helper
        self.temp_dir = tempfile.mkdtemp()
        self.master_file_path = os.path.join(self.temp_dir, "master_streak.xlsx")
        self.history_file_path = os.path.join(
            self.temp_dir, "master_streak_history.xlsx"
        )

        # Initial sync from sheets to local files
        self.sync_from_sheets()

    def sync_from_sheets(self):
        """Download data from Google Sheets to local Excel files"""
        # Get data from sheets
        master_df = self.sheets_helper.load_master_data()
        history_df = self.sheets_helper.load_history_data()

        # Save to local files
        master_df.to_excel(self.master_file_path, index=False)
        history_df.to_excel(self.history_file_path, index=False)

    def sync_to_sheets(self):
        """Upload data from local Excel files to Google Sheets"""
        # Read local files
        master_df = pd.read_excel(self.master_file_path)
        history_df = pd.read_excel(self.history_file_path)

        # Upload to sheets
        self.sheets_helper.save_master_data(master_df)
        self.sheets_helper.save_history_data(history_df)

    def get_tracker(self, hands_threshold=100):
        """Create a PokerStreakTracker instance with local files"""
        # Sync before creating tracker
        self.sync_from_sheets()
        return PokerStreakTracker(
            self.master_file_path, hands_threshold, self.history_file_path
        )


# Capture output for sending via Telegram
class OutputCapture:
    def __init__(self):
        self.buffer = []
        self.output = ""

    def write(self, text):
        self.buffer.append(text)

    def get_output(self):
        self.output = "".join(self.buffer)
        return self.output

    def clear(self):
        self.buffer = []
        self.output = ""


# Function to split long messages for Telegram (max 4096 chars)
def split_message(message, max_length=4000):
    """Split a long message into chunks for Telegram"""
    if len(message) <= max_length:
        return [message]

    chunks = []
    current_chunk = ""

    for line in message.split("\n"):
        if len(current_chunk) + len(line) + 1 > max_length:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            if current_chunk:
                current_chunk += "\n"
            current_chunk += line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# Telegram bot commands
def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    update.message.reply_text(
        "👋 Welcome to the Poker Streak Tracker Bot!\n\n"
        "This bot tracks player streaks for poker games, awarding wheel spins at 7, 14, 21, etc. day milestones.\n\n"
        "Use /lookup to check your streak status.\n"
        "Use /lookuprefs to see players you referred.\n"
        "You can use /cancel at any time to cancel the current operation."
    )


def wheel_command(update: Update, context: CallbackContext) -> int:
    """Show the admin menu when the command /wheel is issued."""
    # Only allow admin users to access the wheel menu
    if update.effective_user.username not in ADMIN_USERS:
        update.message.reply_text(
            "⛔ You don't have permission to use this function.\n"
            "Use /lookup to check player streak status."
        )
        return ConversationHandler.END

    user = update.effective_user
    logger.info(f"Admin {user.first_name} ({user.username}) accessed the wheel menu")

    keyboard = [
        [InlineKeyboardButton("1. View help", callback_data="help")],
        [InlineKeyboardButton("2. Process new daily data", callback_data="process")],
        [
            InlineKeyboardButton(
                "3. Look up player streak status", callback_data="lookup"
            )
        ],
        [InlineKeyboardButton("4. Revive a player's streak", callback_data="revive")],
        [InlineKeyboardButton("5. Manage referrals", callback_data="referral")],
        [InlineKeyboardButton("6. Exit", callback_data="exit")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Admin Menu:\n\nType /cancel at any time to exit from any menu.",
        reply_markup=reply_markup,
    )
    return CHOOSING


def lookup_command(update: Update, context: CallbackContext) -> int:
    """Handle the /lookup command for all users."""
    keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Enter the player's username to look up:\n\n"
        "Type /cancel or use the Cancel button to exit.",
        reply_markup=reply_markup,
    )
    return LOOKING_UP_PLAYER


def referral_command(update: Update, context: CallbackContext) -> int:
    """Handle the /referral command for admin users only."""
    # Check if user is admin
    if update.effective_user.username not in ADMIN_USERS:
        update.message.reply_text("❌ You don't have permission to use this command.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Enter the username of the player who was referred:\n\n"
        "Type /cancel or use the Cancel button to exit.",
        reply_markup=reply_markup,
    )
    return REFERRAL_REFERRED


def add_referral_referred(update: Update, context: CallbackContext) -> int:
    """Handle the referred player username input."""
    # Handle cancel button press
    if update.callback_query and update.callback_query.data == "cancel":
        update.callback_query.answer()
        update.callback_query.edit_message_text("Operation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    # Check if user is admin
    if update.effective_user.username not in ADMIN_USERS:
        update.message.reply_text("❌ You don't have permission to use this command.")
        return ConversationHandler.END

    # Handle text input
    if not update.message or not update.message.text:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.effective_message.reply_text(
            "Please enter a valid username.\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REFERRAL_REFERRED

    referred_player = update.message.text.strip()

    if not referred_player:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Please enter a valid username.\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REFERRAL_REFERRED

    # Store the referred player
    context.user_data["referred_player"] = referred_player

    keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"Enter how many hands {referred_player} has played so far (enter 0 if starting fresh):\n\n"
        "Type /cancel or use the Cancel button to exit.",
        reply_markup=reply_markup,
    )
    return REFERRAL_HANDS


def add_referral_hands(update: Update, context: CallbackContext) -> int:
    """Handle the hands played input."""
    # Handle cancel button press
    if update.callback_query and update.callback_query.data == "cancel":
        update.callback_query.answer()
        update.callback_query.edit_message_text("Operation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    # Handle text input
    if not update.message or not update.message.text:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.effective_message.reply_text(
            "Please enter a valid number (0 or greater).\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REFERRAL_HANDS

    try:
        hands_played = int(update.message.text.strip())
        if hands_played < 0:
            keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(
                "Please enter a valid number (0 or greater).\n\n"
                "Type /cancel or use the Cancel button to exit.",
                reply_markup=reply_markup,
            )
            return REFERRAL_HANDS
    except ValueError:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Please enter a valid number (0 or greater).\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REFERRAL_HANDS

    # Store the hands played
    context.user_data["hands_played"] = hands_played
    referred_player = context.user_data["referred_player"]

    keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"Enter the username of the player who referred {referred_player}:\n\n"
        "Type /cancel or use the Cancel button to exit.",
        reply_markup=reply_markup,
    )
    return REFERRAL_REFERRER


def add_referral_referrer(update: Update, context: CallbackContext) -> int:
    """Handle the referrer username input and save the referral."""
    # Handle cancel button press
    if update.callback_query and update.callback_query.data == "cancel":
        update.callback_query.answer()
        update.callback_query.edit_message_text("Operation cancelled.")
        context.user_data.clear()
        return ConversationHandler.END

    # Handle text input
    if not update.message or not update.message.text:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.effective_message.reply_text(
            "Please enter a valid username.\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REFERRAL_REFERRER

    referrer_player = update.message.text.strip()

    if not referrer_player:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Please enter a valid username.\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REFERRAL_REFERRER

    # Get stored data
    referred_player = context.user_data["referred_player"]
    hands_played = context.user_data["hands_played"]

    # Check if player is referring themselves - triggering new heroku deployment
    if referred_player.lower() == referrer_player.lower():
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "❌ A player cannot refer themselves. Please try again.\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REFERRAL_REFERRER

    try:
        # Initialize referral system - use config which handles both local and Heroku
        if config.GOOGLE_CREDS_JSON:
            referral_system = ReferralSystem(
                config.GOOGLE_CREDS_JSON, config.MASTER_SHEET_ID
            )
        else:
            update.message.reply_text("❌ Error: Credentials not configured properly.")
            context.user_data.clear()
            return ConversationHandler.END

        # Add the referral
        success, message = referral_system.add_referral(
            referred_player, hands_played, referrer_player
        )

        update.message.reply_text(message)

        # Clear user data
        context.user_data.clear()

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error adding referral: {e}")
        update.message.reply_text(
            "❌ An error occurred while adding the referral. Please try again later."
        )
        context.user_data.clear()
        return ConversationHandler.END


def lookuprefs_command(update: Update, context: CallbackContext) -> int:
    """Handle the /lookuprefs command for all users."""
    keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "Enter your username to look up your referrals:\n\n"
        "Type /cancel or use the Cancel button to exit.",
        reply_markup=reply_markup,
    )
    return LOOKUP_REFS_USERNAME


def lookup_refs_username(update: Update, context: CallbackContext) -> int:
    """Handle the username input for referral lookup."""
    # Handle cancel button press
    if update.callback_query and update.callback_query.data == "cancel":
        update.callback_query.answer()
        update.callback_query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END

    username = update.message.text.strip() if update.message else ""

    if not username:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Please enter a valid username.\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return LOOKUP_REFS_USERNAME

    try:
        # Initialize referral system
        if config.GOOGLE_CREDS_JSON:
            referral_system = ReferralSystem(
                config.GOOGLE_CREDS_JSON, config.MASTER_SHEET_ID
            )
        else:
            update.message.reply_text("❌ Google credentials not configured properly.")
            return ConversationHandler.END

        # Look up referrals
        referrals = referral_system.lookup_referrals(username)

        if not referrals:
            update.message.reply_text(f"No referrals found for '{username}'.")
        else:
            # Format the response
            response = f"📋 REFERRALS FOR {username.upper()}\n"
            response += "=" * 30 + "\n\n"

            for i, referral in enumerate(referrals, 1):
                response += f"{i}. {referral['referred_player']}\n"
                response += f"   Hands: {referral['hands_played']}\n"

                if referral["bonus_received"]:
                    response += "   Status: 🎁 Bonus received \n"
                else:
                    remaining = max(0, 250 - referral["hands_played"])
                    response += f"   Status: 🔄 {remaining} hands to bonus\n"
                response += "\n"

            response += "=" * 30

            update.message.reply_text(response)

        return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error looking up referrals: {e}")
        update.message.reply_text(
            "❌ An error occurred while looking up referrals. Please try again later."
        )
        return ConversationHandler.END


def button_handler(update: Update, context: CallbackContext) -> int:
    """Handle button presses from the inline keyboard."""
    query = update.callback_query
    query.answer()

    if query.data == "process":
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "Please upload the daily Excel file (.xlsx)\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return PROCESSING_DATA

    elif query.data == "lookup":
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "Enter the player's username to look up:\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return LOOKING_UP_PLAYER

    elif query.data == "help":
        help_text = (
            "*POKER STREAK TRACKER HELP*\n"
            "========================\n"
            "This tool tracks poker players who play 100+ hands per day.\n\n"
            "*Daily data file format:*\n"
            "- Excel file (.xlsx)\n"
            "- Must include 'Member Statistics' sheet\n"
            "- Player usernames in column J\n"
            "- Hands played in column EV\n\n"
            "*Streak Rules:*\n"
            "- Players must play 100+ hands per day\n"
            "- Missing a day resets streak to 0\n"
            "- Milestones at 7, 14, 21, etc. days earn wheel spins\n\n"
            "*Player Lookup:*\n"
            "- Shows player's current streak status\n"
            "- Displays highest streak achieved\n\n"
            "*Revive Streak (Admin):*\n"
            "- Allows admins to restore a player's streak\n"
            "- Updates history records\n\n"
            "*Cancelling Operations:*\n"
            "- Type /cancel at any time to exit the current operation\n"
            "- Use Cancel buttons when available"
        )
        query.edit_message_text(text=help_text, parse_mode="Markdown")
        return ConversationHandler.END

    elif query.data == "revive":
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "Enter the player's username whose streak you want to revive:\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REVIVING_STREAK

    elif query.data == "referral":
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "Enter the username of the player who was referred:\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REFERRAL_REFERRED

    elif query.data == "exit" or query.data == "cancel":
        query.edit_message_text(
            "Operation cancelled. Type /wheel to access admin menu again."
        )
        return ConversationHandler.END

    else:
        return ConversationHandler.END


def process_file(update: Update, context: CallbackContext) -> int:
    """Process the uploaded Excel file."""
    # Handle cancel button press
    if update.callback_query and update.callback_query.data == "cancel":
        update.callback_query.answer()
        update.callback_query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END

    # First check if user is admin
    if update.effective_user.username not in ADMIN_USERS:
        update.message.reply_text("⛔ You don't have permission to use this function.")
        return ConversationHandler.END

    if not update.message.document:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Please upload an Excel file (.xlsx)\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return PROCESSING_DATA

    file = update.message.document
    if not file.file_name.endswith(".xlsx"):
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Please upload an Excel file with .xlsx extension\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return PROCESSING_DATA

    try:
        # Send a processing message
        processing_msg = update.message.reply_text("⏳ Processing file... Please wait.")

        # Download the file
        file_obj = context.bot.get_file(file.file_id)
        temp_file = os.path.join(tempfile.mkdtemp(), file.file_name)
        file_obj.download(temp_file)

        # Get the sheets adapter from context
        sheets_adapter = context.bot_data.get("sheets_adapter")
        if not sheets_adapter:
            update.message.reply_text("⚠️ Error: Google Sheets adapter not configured.")
            return ConversationHandler.END

        # Create a tracker with the adapter
        tracker = sheets_adapter.get_tracker()

        # Capture output to send via Telegram
        output_capture = OutputCapture()
        orig_print = print

        # Replace print with our capture function
        def telegram_print(*args, **kwargs):
            text = " ".join(map(str, args))
            output_capture.write(text + "\n")
            orig_print(*args, **kwargs)

        # Process the file with captured output
        import builtins

        builtins.print = telegram_print

        result = tracker.process_daily_data(temp_file)

        # Restore original print function
        builtins.print = orig_print

        # Get the captured output
        output = output_capture.get_output()

        # Sync changes back to Google Sheets
        sheets_adapter.sync_to_sheets()

        # Delete the processing message
        context.bot.delete_message(
            chat_id=update.effective_chat.id, message_id=processing_msg.message_id
        )

        # Send the result in chunks if needed
        output_chunks = split_message(output)

        # First send success message
        update.message.reply_text("✅ Processing completed successfully!")

        # Then send all output chunks
        for chunk in output_chunks:
            update.message.reply_text(chunk)

        # Clean up
        if os.path.exists(temp_file):
            os.remove(temp_file)

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        update.message.reply_text(f"❌ Error processing file: {str(e)}")

    return ConversationHandler.END


def lookup_player(update: Update, context: CallbackContext) -> int:
    """Look up a player's streak status."""
    # Handle cancel button press
    if update.callback_query and update.callback_query.data == "cancel":
        update.callback_query.answer()
        update.callback_query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END

    username = update.message.text.strip() if update.message else ""

    if not username:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Please enter a valid username.\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return LOOKING_UP_PLAYER

    # Get the sheets adapter from context
    sheets_adapter = context.bot_data.get("sheets_adapter")
    if not sheets_adapter:
        update.message.reply_text("⚠️ Error: Google Sheets adapter not configured.")
        return ConversationHandler.END

    # Create a tracker with the adapter
    tracker = sheets_adapter.get_tracker()

    # Look up player
    player_data = tracker.lookup_player(username)

    if player_data is None:
        update.message.reply_text(f"⚠️ Player '{username}' not found in the database.")
    else:
        # Format the player data WITHOUT Markdown to avoid parsing errors
        reply = (
            f"📊 PLAYER STATUS\n"
            f"========================\n"
            f"Username: {player_data['Username']}\n"
            f"Status: {player_data['LastUpdate']}\n"
            f"Last updated: {player_data['UpdateDate']}\n"
            f"Current streak: {player_data['CurrentStreak']}\n"
            f"Highest streak: {player_data['HighestStreak']}\n"
            f"========================"
        )
        # Remove parse_mode="Markdown" to avoid parsing errors
        update.message.reply_text(reply)

    return ConversationHandler.END


def revive_streak_user(update: Update, context: CallbackContext) -> int:
    """Get username for streak revival."""
    # Handle cancel button press
    if update.callback_query and update.callback_query.data == "cancel":
        update.callback_query.answer()
        update.callback_query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END

    # Check if user is admin
    if update.effective_user.username not in ADMIN_USERS:
        update.message.reply_text("⛔ You don't have permission to use this function.")
        return ConversationHandler.END

    username = update.message.text.strip() if update.message else ""

    if not username:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Please enter a valid username.\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REVIVING_STREAK

    # Store the username in context
    context.user_data["revive_username"] = username

    keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"Enter the streak value to set for {username}:\n\n"
        "Type /cancel or use the Cancel button to exit.",
        reply_markup=reply_markup,
    )

    return REVIVING_STREAK_VALUE


def revive_streak_value(update: Update, context: CallbackContext) -> int:
    """Process the streak value for revival."""
    # Handle cancel button press
    if update.callback_query and update.callback_query.data == "cancel":
        update.callback_query.answer()
        update.callback_query.edit_message_text("Operation cancelled.")
        return ConversationHandler.END

    try:
        streak_value = int(update.message.text.strip()) if update.message else 0

        if streak_value < 1:
            keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(
                "Streak value must be at least 1.\n\n"
                "Type /cancel or use the Cancel button to exit.",
                reply_markup=reply_markup,
            )
            return REVIVING_STREAK_VALUE

        # Retrieve username from context
        username = context.user_data.get("revive_username")
        if not username:
            update.message.reply_text("Error: Username not found.")
            return ConversationHandler.END

        # Get the sheets adapter from context
        sheets_adapter = context.bot_data.get("sheets_adapter")
        if not sheets_adapter:
            update.message.reply_text("⚠️ Error: Google Sheets adapter not configured.")
            return ConversationHandler.END

        # Create a tracker with the adapter
        tracker = sheets_adapter.get_tracker()

        # Try to revive streak
        result, message = tracker.revive_player_streak(username, streak_value)

        # Handle confirmation case
        if result == "confirm":
            keyboard = [
                [
                    InlineKeyboardButton(
                        "Yes", callback_data=f"confirm_yes_{username}_{streak_value}"
                    ),
                    InlineKeyboardButton("No", callback_data="confirm_no"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(
                f"⚠️ *WARNING*: {message}\nDo you want to proceed?",
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
            return CONFIRMING_REVIVAL
        else:
            if result:
                # Success
                sheets_adapter.sync_to_sheets()
                update.message.reply_text(f"✅ {message}")
            else:
                # Error
                update.message.reply_text(f"❌ {message}")

            return ConversationHandler.END

    except ValueError:
        keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Please enter a valid number.\n\n"
            "Type /cancel or use the Cancel button to exit.",
            reply_markup=reply_markup,
        )
        return REVIVING_STREAK_VALUE


def confirm_revival(update: Update, context: CallbackContext) -> int:
    """Handle confirmation for streak revival."""
    query = update.callback_query
    query.answer()

    if query.data.startswith("confirm_yes_"):
        # Extract username and streak from callback data
        _, _, username, streak_value = query.data.split("_")
        streak_value = int(streak_value)

        # Get the sheets adapter from context
        sheets_adapter = context.bot_data.get("sheets_adapter")
        if not sheets_adapter:
            query.edit_message_text("⚠️ Error: Google Sheets adapter not configured.")
            return ConversationHandler.END

        # Create a tracker with the adapter
        tracker = sheets_adapter.get_tracker()

        # Confirm streak revival
        result, message = tracker.confirm_revive_streak(username, streak_value)

        if result:
            # Sync changes to Google Sheets
            sheets_adapter.sync_to_sheets()
            query.edit_message_text(f"✅ {message}")
        else:
            query.edit_message_text(f"❌ {message}")
    elif query.data == "confirm_no":
        query.edit_message_text("❌ Operation cancelled.")
    else:
        query.edit_message_text("❌ Operation cancelled.")

    return ConversationHandler.END


def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel and end the conversation."""
    if update.message:
        update.message.reply_text("⚠️ Operation cancelled.")
    return ConversationHandler.END


def error_handler(update: Update, context: CallbackContext) -> None:
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=True)

    # Notify user of error
    if update.effective_message:
        update.effective_message.reply_text(
            "❌ An error occurred while processing your request."
        )


def main():
    """Run the bot."""
    # Configuration
    telegram_token = config.TELEGRAM_TOKEN
    master_sheet_id = config.MASTER_SHEET_ID

    # Create the Updater and pass it your bot's token
    updater = Updater(telegram_token)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Initialize Google Sheets integration
    sheets_helper = GoogleSheetsHelper(None, master_sheet_id)
    sheets_adapter = GoogleSheetsAdapter(sheets_helper)

    # Store the adapter in the bot_data for access in all handlers
    dp.bot_data["sheets_adapter"] = sheets_adapter

    # Define a cancel handler that can be used outside of conversations
    dp.add_handler(CommandHandler("cancel", cancel))

    # Define wheel conversation handler (admin only)
    wheel_handler = ConversationHandler(
        entry_points=[CommandHandler("wheel", wheel_command)],
        states={
            CHOOSING: [CallbackQueryHandler(button_handler)],
            PROCESSING_DATA: [
                MessageHandler(Filters.document, process_file),
                CallbackQueryHandler(process_file),  # To handle cancel button
            ],
            LOOKING_UP_PLAYER: [
                MessageHandler(Filters.text & ~Filters.command, lookup_player),
                CallbackQueryHandler(lookup_player),  # To handle cancel button
            ],
            REVIVING_STREAK: [
                MessageHandler(Filters.text & ~Filters.command, revive_streak_user),
                CallbackQueryHandler(revive_streak_user),  # To handle cancel button
            ],
            REVIVING_STREAK_VALUE: [
                MessageHandler(Filters.text & ~Filters.command, revive_streak_value),
                CallbackQueryHandler(revive_streak_value),  # To handle cancel button
            ],
            CONFIRMING_REVIVAL: [CallbackQueryHandler(confirm_revival)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Define lookup conversation handler (all users)
    lookup_handler = ConversationHandler(
        entry_points=[CommandHandler("lookup", lookup_command)],
        states={
            LOOKING_UP_PLAYER: [
                MessageHandler(Filters.text & ~Filters.command, lookup_player),
                CallbackQueryHandler(lookup_player),  # To handle cancel button
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Define referral conversation handler (admin only)
    referral_handler = ConversationHandler(
        entry_points=[CommandHandler("referral", referral_command)],
        states={
            REFERRAL_REFERRED: [
                MessageHandler(Filters.text & ~Filters.command, add_referral_referred),
                CallbackQueryHandler(add_referral_referred),  # To handle cancel button
            ],
            REFERRAL_HANDS: [
                MessageHandler(Filters.text & ~Filters.command, add_referral_hands),
                CallbackQueryHandler(add_referral_hands),  # To handle cancel button
            ],
            REFERRAL_REFERRER: [
                MessageHandler(Filters.text & ~Filters.command, add_referral_referrer),
                CallbackQueryHandler(add_referral_referrer),  # To handle cancel button
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Define lookup referrals conversation handler (all users)
    lookup_refs_handler = ConversationHandler(
        entry_points=[CommandHandler("lookuprefs", lookuprefs_command)],
        states={
            LOOKUP_REFS_USERNAME: [
                MessageHandler(Filters.text & ~Filters.command, lookup_refs_username),
                CallbackQueryHandler(lookup_refs_username),  # To handle cancel button
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(wheel_handler)
    dp.add_handler(lookup_handler)
    dp.add_handler(referral_handler)
    dp.add_handler(lookup_refs_handler)

    # Add error handler
    dp.add_error_handler(error_handler)

    # Start the Bot
    updater.start_polling()
    logger.info("Bot started. Press Ctrl+C to stop.")

    # Run the bot until you press Ctrl-C
    updater.idle()


if __name__ == "__main__":
    main()
