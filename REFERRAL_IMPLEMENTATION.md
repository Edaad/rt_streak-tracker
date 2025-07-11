# Referral System Implementation

## Overview
A simple and clean referral tracking system has been added to the Poker Streak Tracker Bot. This system allows admins to add referrals, automatically tracks when referred players reach the 250-hand milestone, and allows users to look up their referrals.

## Features

### `/referral` Command (Admin Only)
- **Usage**: `/referral`
- **Access**: Admin users only
- **Flow**:
  1. Enter the username of the player who was referred
  2. Enter how many hands the referred player has played so far (0 if starting fresh)
  3. Enter the username of the player who made the referral
  4. Confirmation and save to Google Sheets

### `/lookuprefs` Command (All Users)
- **Usage**: `/lookuprefs`
- **Access**: All users
- **Flow**:
  1. Enter your GG username
  2. View organized list of all players you referred
  3. See current hands played and bonus status for each referral

### Automatic Processing
- **Integration**: Runs automatically during daily data processing
- **Milestone**: Detects when referred players reach 250 hands
- **Output**: Displays referral bonus notifications in the daily processing results

### Google Sheets Integration
- **Sheet Name**: "Referrals"
- **Columns**:
  - `ReferredPlayer`: Username of the player who was referred
  - `HandsPlayed`: Total hands played by the referred player
  - `ReferrerPlayer`: Username of the player who made the referral

## Files Added/Modified

### New Files:
- `referral_system.py` - Contains the `ReferralSystem` class with all referral logic
- `test_referral_system.py` - Test script to verify the system works

### Modified Files:
- `poker_bot.py` - Added `/referral` command and conversation handlers
- `poker_streak_tracker.py` - Added referral processing to daily data handling
- `config.py` - Updated to handle both local and Heroku environments

## Usage Examples

### Adding a Referral (Admin Only):
1. Admin types `/referral`
2. Bot: "Enter the username of the player who was referred:"
3. Admin: `new_player123`
4. Bot: "Enter how many hands new_player123 has played so far (enter 0 if starting fresh):"
5. Admin: `0`
6. Bot: "Enter the username of the player who referred new_player123:"
7. Admin: `veteran_player`
8. Bot: "✅ Successfully added referral: veteran_player referred new_player123"

### Looking Up Your Referrals (All Users):
1. User types `/lookuprefs`
2. Bot: "Enter your GG username to see the players you referred:"
3. User: `veteran_player`
4. Bot displays:
```
📊 REFERRALS FOR VETERAN_PLAYER
==============================

🎯 new_player123
   Hands: 150
   Status: 100 hands to bonus

🎯 another_player
   Hands: 300
   Status: 🎁 BONUS EARNED

==============================
Total Referrals: 2
Bonuses Earned: 1
```

### Daily Processing Output:
```
🎡 WHEEL SPIN SCHEDULE TODAY 🎡
==============================
player1 hit 7 day streak, their Wheel 1 spin will be at 7:30 PM today
==============================

🎉 REFERRAL BONUSES TODAY 🎉
==============================
🎁 new_player123 hit 250 hands milestone! veteran_player should receive a referral bonus!
==============================

--- PROCESSING COMPLETE ---
Total players processed: 150
Updated Players: 45
New Players: 3
Players that lost streaks: 12
Wheel winners: 1
Referral bonuses: 1
History records updated: 48
```

## Error Handling

### Validation:
- Prevents duplicate referrals (error if player already on list)
- Validates hands played (must be 0 or greater)
- Admin-only access control
- Self-referral prevention

### Error Messages:
- "Error: That player is already on the referral list."
- "❌ You don't have permission to use this command."
- "Please enter a valid number (0 or greater)."

## Key Functions

### ReferralSystem Class:
- `add_referral(referred_player, hands_played, referrer_player)` - Add new referral
- `update_hands_and_check_milestone(daily_players_data)` - Process daily updates
- `load_referrals_data()` - Load data from Google Sheets
- `save_referrals_data(df)` - Save data to Google Sheets

### Integration Points:
- Telegram bot `/referral` command
- Daily data processing in `process_daily_data()`
- Google Sheets "Referrals" worksheet

## Installation Notes

### Requirements:
- All existing dependencies (already in requirements.txt)
- No additional packages needed

### Configuration:
- Uses existing Google Sheets credentials
- Works with current bot permissions
- Backward compatible with existing functionality

## Testing

Run the test script to verify everything works:
```bash
python test_referral_system.py
```

The system is designed to be:
- **Simple**: Clean `/referral` command flow
- **Robust**: Error handling and validation
- **Integrated**: Seamless with existing daily processing
- **Scalable**: Easy to extend with additional features

All functionality is contained in the `referral_system.py` file with minimal changes to existing code.
