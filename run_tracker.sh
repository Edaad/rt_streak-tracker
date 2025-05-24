#!/bin/bash

# Poker Streak Tracker Shell Script
MASTER_FILE="data/master_streak.xlsx"

# Create data directory if it doesn't exist
mkdir -p data

# Display header
echo "Poker Streak Tracker"
echo "==================="

# Function to display menu
show_menu() {
  echo
  echo "Choose an option:"
  echo "1. Process new daily data"
  echo "2. Look up player streak status"
  echo "3. View help"
  echo "4. Revive a player's streak (Admin)"
  echo "5. Exit"
  echo
}

# Function to display help
show_help() {
  echo
  echo "POKER STREAK TRACKER HELP"
  echo "========================"
  echo "This tool tracks poker players who play 100+ hands per day."
  echo
  echo "Daily data file format:"
  echo "- Excel file (.xlsx)"
  echo "- Must have columns: \"Username\" and \"Hands\""
  echo "- One row per player"
  echo
  echo "Master file:"
  echo "- Located at: $MASTER_FILE"
  echo "- Tracks each player's current streak"
  echo "- Automatically backs up before changes"
  echo
  echo "Player Lookup:"
  echo "- Lets you search for a player's current streak status"
  echo "- Shows their latest status and highest streak achieved"
  echo
  echo "Revive Streak (Admin):"
  echo "- Allows admins to restore or set a specific streak for a player"
  echo "- Updates both master and history files"
  echo
  read -p "Press Enter to continue..."
}

# Main loop
while true; do
  show_menu
  read -p "Enter your choice (1-5): " choice
  
  case $choice in
    1)
      echo
      read -p "Enter path to daily data Excel file: " daily_file
      
      if [ ! -f "$daily_file" ]; then
        echo "File not found: $daily_file"
        continue
      fi
      
      python3 poker_streak_tracker.py --daily "$daily_file" --master "$MASTER_FILE"
      ;;
    2)
      echo
      python3 poker_streak_tracker.py --lookup --master "$MASTER_FILE"
      ;;
    3)
      show_help
      ;;
    4)
      echo
      echo "REVIVE PLAYER STREAK (ADMIN FUNCTION)"
      echo "===================================="
      read -p "Enter player username: " username
      read -p "Enter streak value to set: " streak_value
      
      # Check if value is a valid number
      if ! [[ "$streak_value" =~ ^[0-9]+$ ]]; then
        echo "Error: Streak must be a positive number"
        continue
      fi
      
      python3 poker_streak_tracker.py --revive --username "$username" --streak "$streak_value" --master "$MASTER_FILE"
      ;;
    5)
      echo
      echo "Goodbye!"
      exit 0
      ;;
    *)
      echo "Invalid choice. Please try again."
      ;;
  esac
done