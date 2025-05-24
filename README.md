# Poker Streak Tracker

A simple tool to track poker players who maintain a streak of playing 100+ hands per day.

## Setup

1. **Install Python** (3.6 or newer)
2. **Install required packages**:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Windows:
Double-click `run_tracker.bat` and follow the prompts.

### Mac/Linux:
1. Make the script executable:
   ```
   chmod +x run_tracker.sh
   ```
2. Run the script:
   ```
   ./run_tracker.sh
   ```

### Manual Usage:
Run directly with Python:
```
python poker_streak_tracker.py --daily "path/to/daily_data.xlsx" --master "data/master_streak.xlsx"
```

## File Format Requirements

### Daily Data File:
- Excel file (.xlsx)
- Must contain columns: "Username" and "Hands"
- One row per player

### Master File:
- Excel file (.xlsx)
- Contains "Username" and "Streak" columns
- Created automatically if it doesn't exist
- Backed up before each update

## How It Works

1. For each player in the daily file:
   - If they played 100+ hands, their streak increases by 1
   - If they played <100 hands, their streak resets to 0
   - If they're new, they're added to the master file

## Parameters

- `--daily`: Path to daily Excel file (required)
- `--master`: Path to master Excel file (default: data/master_streak.xlsx)
- `--threshold`: Minimum hands to count towards streak (default: 100)