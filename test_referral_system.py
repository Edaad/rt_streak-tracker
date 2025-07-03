#!/usr/bin/env python3
"""
Test script for the referral system
"""

from referral_system import ReferralSystem
import config


def test_referral_system():
    print("Testing Referral System...")

    try:
        # Initialize the referral system
        referral_system = ReferralSystem("credentials.json", config.MASTER_SHEET_ID)
        print("✅ Referral system initialized successfully")

        # Test loading data (should work even if empty)
        df = referral_system.load_referrals_data()
        print(f"✅ Loaded referrals data: {len(df)} rows")

        print("\nReferral system is ready to use!")
        print("Available functions:")
        print("- add_referral(referred_player, hands_played, referrer_player)")
        print("- update_hands_and_check_milestone(daily_players_data)")

    except Exception as e:
        print(f"❌ Error testing referral system: {e}")


if __name__ == "__main__":
    test_referral_system()
