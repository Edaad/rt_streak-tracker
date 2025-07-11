#!/usr/bin/env python3
"""
Test script for the lookup referrals functionality
"""

from referral_system import ReferralSystem
import config


def test_lookup_referrals():
    print("Testing Lookup Referrals Functionality...")

    try:
        # Initialize the referral system
        referral_system = ReferralSystem(
            config.GOOGLE_CREDS_JSON, config.MASTER_SHEET_ID
        )
        print("✅ Referral system initialized successfully")

        # Load referrals data
        df = referral_system.load_referrals_data()
        print(f"✅ Loaded referrals data: {len(df)} rows")

        if not df.empty:
            print("\nCurrent referrals in system:")
            print(df.to_string(index=False))

            # Get unique referrers
            referrers = df["ReferrerPlayer"].unique()
            print(f"\nUnique referrers: {list(referrers)}")

            # Test lookup for each referrer
            for referrer in referrers:
                print(f"\n--- Testing lookup for {referrer} ---")
                user_referrals = df[
                    df["ReferrerPlayer"].str.lower() == referrer.lower()
                ]

                total_referrals = len(user_referrals)
                bonuses_earned = 0

                print(f"Total referrals: {total_referrals}")

                for _, row in user_referrals.iterrows():
                    referred_player = row["ReferredPlayer"]
                    hands_played = int(row["HandsPlayed"])

                    if hands_played >= 250:
                        status = "🎁 BONUS EARNED"
                        bonuses_earned += 1
                    else:
                        remaining = 250 - hands_played
                        status = f"{remaining} hands to bonus"

                    print(f"  🎯 {referred_player}: {hands_played:,} hands - {status}")

                print(f"Bonuses earned: {bonuses_earned}")
        else:
            print("No referrals found in system")

    except Exception as e:
        print(f"❌ Error testing lookup referrals: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_lookup_referrals()
